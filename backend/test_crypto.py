"""BTC/USD offline regression tests; no authenticated network requests."""

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


def crypto_rows(count=100, offset=0):
    first = dt.date(2025, 1, 1) + dt.timedelta(days=offset)
    return [
        {"date": (first + dt.timedelta(days=i)).isoformat(), "close": 80000.0 + i}
        for i in range(count)
    ]


def crypto_payload(rows, qualified=False):
    return {
        "Meta Data": {
            "2. Digital Currency Code": "BTC",
            "4. Market Code": "USD",
            "7. Time Zone": "UTC",
        },
        "Time Series (Digital Currency Daily)": {
            r["date"]: (
                {"4a. close (USD)": str(r["close"]), "4b. close (USD)": str(r["close"])}
                if qualified
                else {"4. close": str(r["close"])}
            )
            for r in rows
        },
    }


class CryptoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_db = server.DB
        server.DB = Path(self.temp.name) / "crypto.sqlite3"
        server.init()

    def tearDown(self):
        server.DB = self.old_db
        self.temp.cleanup()

    def sync(self, rows):
        with server.conn() as c:
            c.execute("UPDATE ingestion_jobs SET started='2000-01-01T00:00:00+00:00'")
        with patch.object(
            market_data, "fetch_daily", return_value=(rows, json.dumps(crypto_payload(rows)))
        ):
            return server.sync_market("BTCUSD")

    def test_weekends_retained_and_current_date_excluded(self):
        rows = crypto_rows(101)
        today = dt.date.fromisoformat(rows[-1]["date"])
        result = market_data.normalize_crypto(
            crypto_payload(rows), dt.datetime.combine(today, dt.time(12), UTC)
        )
        self.assertEqual(result, rows[:-1])
        self.assertTrue(any(dt.date.fromisoformat(r["date"]).weekday() == 5 for r in result))
        self.assertTrue(any(dt.date.fromisoformat(r["date"]).weekday() == 6 for r in result))

    def test_plain_and_qualified_close_formats(self):
        rows = crypto_rows()
        self.assertEqual(market_data.normalize_crypto(crypto_payload(rows)), rows)
        self.assertEqual(market_data.normalize_crypto(crypto_payload(rows, True)), rows)
        conflict = crypto_payload(rows, True)
        conflict["Time Series (Digital Currency Daily)"][rows[0]["date"]]["4b. close (USD)"] = "1"
        with self.assertRaises(market_data.ProviderError):
            market_data.normalize_crypto(conflict)

    def test_invalid_pair_timezone_gaps_and_prices_rejected(self):
        rows = crypto_rows()
        wrong = crypto_payload(rows)
        wrong["Meta Data"]["2. Digital Currency Code"] = "ETH"
        usdt = crypto_payload(rows)
        usdt["Meta Data"]["4. Market Code"] = "USDT"
        zone = crypto_payload(rows)
        zone["Meta Data"]["7. Time Zone"] = "US/Eastern"
        gap = crypto_payload(rows)
        gap["Time Series (Digital Currency Daily)"].pop(rows[20]["date"])
        price = crypto_payload(rows)
        price["Time Series (Digital Currency Daily)"][rows[0]["date"]]["4. close"] = "NaN"
        for data in (wrong, usdt, zone, gap, price, {"Information": "quota exceeded"}):
            with self.assertRaises(market_data.ProviderError):
                market_data.normalize_crypto(data)

    def test_request_parameters_do_not_send_compact_option(self):
        with patch.dict(os.environ, {"ALPHAVANTAGE_API_KEY": "test-key"}):
            with patch(
                "urllib.request.urlopen",
                return_value=io.BytesIO(json.dumps(crypto_payload(crypto_rows())).encode()),
            ) as fetch:
                rows, _ = market_data.fetch_daily("BTCUSD")
        url = fetch.call_args.args[0].full_url
        self.assertIn("function=DIGITAL_CURRENCY_DAILY", url)
        self.assertIn("symbol=BTC", url)
        self.assertIn("market=USD", url)
        self.assertNotIn("outputsize", url)
        self.assertEqual(len(rows), 100)

    def test_calendar_and_scheduler_include_saturday_sunday(self):
        self.assertEqual(
            market_data.future_dates("2025-07-04", 2, market_data.CRYPTO_CALENDAR),
            ["2025-07-05", "2025-07-06"],
        )
        target, next_time = automation.release_window(
            dt.datetime(2025, 7, 6, 1, 1, tzinfo=UTC), 60, "BTCUSD"
        )
        self.assertEqual(target, "2025-07-05")
        self.assertEqual(next_time, "2025-07-07T01:00:00+00:00")
        self.assertIn("BTCUSD", automation.settings()["symbols"])

    def test_sync_snapshots_auto_forecast_and_gap_preservation(self):
        rows = crypto_rows()
        first = self.sync(rows)
        repeat = self.sync(rows)
        self.assertEqual(first["dataset_id"], repeat["dataset_id"])
        self.assertFalse(repeat["changed"])
        extended = self.sync(crypto_rows(100, 1))
        self.assertEqual(extended["rows"], 101)
        config = {**automation.settings(), "symbols": ["BTCUSD"], "sync_enabled": False}
        runner = automation.Runner(
            server.conn, Mock(), server.experiment, server.save_experiment, config
        )
        runner.tick()
        runner.tick()
        with server.conn() as c:
            self.assertEqual(
                c.execute("SELECT COUNT(*) FROM runs WHERE origin='automatic'").fetchone()[0], 1
            )
            self.assertEqual(
                datasets.current(c, "BTCUSD")["metadata"]["calendar"], market_data.CRYPTO_CALENDAR
            )
        with self.assertRaisesRegex(ValueError, "missing calendar dates"):
            self.sync(crypto_rows(100, 150))
        with server.conn() as c:
            self.assertEqual(datasets.current(c, "BTCUSD")["id"], extended["dataset_id"])
        self.assertIn("BTCUSD", runner.status()["next_market_releases"])

    def test_minimum_history_and_all_horizons(self):
        rows = crypto_rows(70)
        self.assertEqual(len(market_data.normalize_crypto(crypto_payload(rows))), 70)
        self.sync(rows)
        for horizon in (1, 7, 14, 30):
            result = server.experiment("BTCUSD", "naive", horizon)
            self.assertEqual(result["mae"], result["baseline_mae"])
            self.assertGreaterEqual(result["samples"], 10)
            self.assertEqual(len(result["forecast"]), horizon)


if __name__ == "__main__":
    unittest.main()
