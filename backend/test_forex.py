"""Offline EUR/USD connector, date-policy and scheduler regression tests."""

import datetime as dt
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import automation
import datasets
import market_data
import server

UTC = dt.timezone.utc


def fx_rows(count=100, offset=0):
    dates = market_data.weekdays("2025-01-01", "2025-12-31")[offset : offset + count]
    return [{"date": d, "close": 1.05 + i * 0.0001} for i, d in enumerate(dates)]


def fx_payload(rows):
    return {
        "Meta Data": {"2. From Symbol": "EUR", "3. To Symbol": "USD", "6. Time Zone": "UTC"},
        "Time Series FX (Daily)": {r["date"]: {"4. close": str(r["close"])} for r in rows},
    }


class ForexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_db = server.DB
        server.DB = Path(self.temp.name) / "fx.sqlite3"
        server.init()

    def tearDown(self):
        server.DB = self.old_db
        self.temp.cleanup()

    def test_current_date_and_weekend_bars_excluded(self):
        rows = fx_rows()
        rows.append({"date": "2025-01-04", "close": 1.1})
        today = dt.date.fromisoformat(rows[-2]["date"])
        result = market_data.normalize_fx(
            fx_payload(rows), dt.datetime.combine(today, dt.time(12), UTC)
        )
        self.assertEqual(len(result), 99)
        self.assertTrue(all(dt.date.fromisoformat(r["date"]).weekday() < 5 for r in result))
        self.assertTrue(all(r["date"] < str(today) for r in result))

    def test_bad_pair_timezone_price_and_future_date_rejected(self):
        rows = fx_rows()
        wrong = fx_payload(rows)
        wrong["Meta Data"]["3. To Symbol"] = "GBP"
        zone = fx_payload(rows)
        zone["Meta Data"]["6. Time Zone"] = "US/Eastern"
        invalid = fx_payload(rows)
        invalid["Time Series FX (Daily)"][rows[0]["date"]]["4. close"] = "NaN"
        future = fx_payload(rows)
        future["Time Series FX (Daily)"]["2099-01-01"] = {"4. close": "1.2"}
        for data in (wrong, zone, invalid, future, {"Information": "Quota exceeded"}):
            with self.assertRaises(market_data.ProviderError):
                market_data.normalize_fx(data)

    def test_missing_weekdays_recorded_and_not_forward_filled(self):
        rows = fx_rows(101)
        missing = rows.pop(20)["date"]
        normalized = market_data.normalize_fx(fx_payload(rows))
        self.assertEqual(len(normalized), 100)
        self.assertEqual(market_data.metadata("EURUSD", normalized)["missing_weekdays"], [missing])
        self.assertNotIn(missing, {r["date"] for r in normalized})

    def test_forex_grid_differs_from_equity_holiday_calendar(self):
        self.assertEqual(
            market_data.future_dates("2025-07-03", 2, market_data.FX_CALENDAR),
            ["2025-07-04", "2025-07-07"],
        )
        self.assertEqual(market_data.future_dates("2025-07-03", 1, "XNYS"), ["2025-07-07"])
        before, _ = automation.release_window(
            dt.datetime(2025, 7, 5, 0, 30, tzinfo=UTC), 60, "EURUSD"
        )
        after, next_time = automation.release_window(
            dt.datetime(2025, 7, 5, 1, 1, tzinfo=UTC), 60, "EURUSD"
        )
        self.assertEqual(before, "2025-07-03")
        self.assertEqual(after, "2025-07-04")
        self.assertEqual(next_time, "2025-07-08T01:00:00+00:00")

    def test_transport_uses_fx_endpoint_parameters(self):
        with patch.dict(os.environ, {"ALPHAVANTAGE_API_KEY": "test-key"}):
            with patch(
                "urllib.request.urlopen",
                return_value=io.BytesIO(json.dumps(fx_payload(fx_rows())).encode()),
            ) as fetch:
                rows, _ = market_data.fetch_daily("EURUSD")
        url = fetch.call_args.args[0].full_url
        self.assertIn("function=FX_DAILY", url)
        self.assertIn("from_symbol=EUR", url)
        self.assertIn("to_symbol=USD", url)
        self.assertEqual(len(rows), 100)

    def test_fx_sync_snapshot_forecast_and_automatic_deduplication(self):
        rows = fx_rows()
        with patch.object(
            market_data, "fetch_daily", return_value=(rows, json.dumps(fx_payload(rows)))
        ):
            first = server.sync_market("EURUSD")
            with server.conn() as c:
                c.execute("UPDATE ingestion_jobs SET started='2000-01-01T00:00:00+00:00'")
            second = server.sync_market("EURUSD")
        self.assertEqual(first["dataset_id"], second["dataset_id"])
        self.assertFalse(second["changed"])
        r = server.experiment("EURUSD", "naive", 30)
        self.assertEqual(r["mae"], r["baseline_mae"])
        self.assertEqual(r["dataset"]["calendar"], market_data.FX_CALENDAR)
        self.assertTrue(all(dt.date.fromisoformat(p["date"]).weekday() < 5 for p in r["forecast"]))
        config = {**automation.settings(), "symbols": ["EURUSD"], "sync_enabled": False}
        runner = automation.Runner(
            server.conn, Mock(), server.experiment, server.save_experiment, config
        )
        runner.tick()
        runner.tick()
        with server.conn() as c:
            self.assertEqual(
                c.execute("SELECT COUNT(*) FROM runs WHERE origin='automatic'").fetchone()[0], 1
            )
        self.assertIn("EURUSD", runner.status()["next_market_releases"])

    def test_merge_preserves_overlap_and_rejects_disconnected_history(self):
        old = fx_rows()
        merged = market_data.validate_merge("EURUSD", old, fx_rows(100, 1))
        self.assertEqual(len(merged), 101)
        with self.assertRaisesRegex(ValueError, "no overlap"):
            market_data.validate_merge("EURUSD", old, fx_rows(100, 140))


if __name__ == "__main__":
    unittest.main()
