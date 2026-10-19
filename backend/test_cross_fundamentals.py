"""Macro and BTC provider fixtures; no external requests."""

import copy
import datetime as dt
import json
import os
import unittest
from unittest.mock import Mock, patch

import cross_fundamentals as x
import fundamentals as f
import test_fundamentals as fixtures

NOW = dt.datetime(2026, 10, 19, tzinfo=dt.timezone.utc)


def macro_fixture():
    def monthly(year, value):
        return {"date": f"{year}-09-01", "value": str(value)}

    return {
        "us_rate": {
            "observations": [
                {"date": "2026-10-16", "value": "4.0"},
                {"date": "2026-10-17", "value": "."},
            ]
        },
        "us_cpi": {"observations": [monthly(2025, 100), monthly(2026, 103)]},
        "ea_hicp": {"observations": [monthly(2025, 100), monthly(2026, 102)]},
        "ecb": "KEY,TIME_PERIOD,OBS_VALUE\n" + x.ECB_KEY + ",2026-10-16,2\n",
    }


def btc_fixture():
    result = {}
    for key, (_, unit) in x.CHARTS.items():
        vals = []
        for days, value in [(8, 100), (1, 110), (0, 999)]:
            date = NOW - dt.timedelta(days=days)
            vals.append({"x": date.timestamp(), "y": value})
        result[key] = {"status": "ok", "unit": unit, "values": vals}
    return result


class ExtractionTests(unittest.TestCase):
    def test_macro_formulas_and_source_dates(self):
        a = x.macro(macro_fixture(), NOW)["metrics"]
        self.assertAlmostEqual(a["us_inflation"]["value"], 3)
        self.assertAlmostEqual(a["ea_inflation"]["value"], 2)
        self.assertEqual(a["rate_spread"]["value"], 2)
        self.assertEqual(a["rate_spread"]["observation_date"], "2026-10-16")

    def test_missing_exact_year_ago_not_nearest(self):
        raw = macro_fixture()
        raw["us_cpi"]["observations"][0]["date"] = "2025-08-01"
        self.assertIsNone(x.macro(raw, NOW)["metrics"]["us_inflation"]["value"])

    def test_spread_requires_same_date(self):
        raw = macro_fixture()
        raw["ecb"] = raw["ecb"].replace("2026-10-16", "2026-10-15")
        self.assertIsNone(x.macro(raw, NOW)["metrics"]["rate_spread"]["value"])

    def test_ecb_wrong_series_rejected(self):
        raw = macro_fixture()
        raw["ecb"] = raw["ecb"].replace(x.ECB_KEY, "WRONG")
        with self.assertRaises(ValueError):
            x.macro(raw, NOW)

    def test_missing_fred_observation_is_not_zero(self):
        raw = macro_fixture()
        raw["us_rate"]["observations"] = [{"date": "2026-10-17", "value": "."}]
        with self.assertRaises(ValueError):
            x.macro(raw, NOW)

    def test_future_observations_excluded(self):
        raw = macro_fixture()
        raw["us_rate"]["observations"].append({"date": "2099-01-01", "value": 99})
        self.assertEqual(x.macro(raw, NOW)["metrics"]["us_rate"]["value"], 4)

    def test_stale_macro_flag(self):
        self.assertTrue(
            x.macro(macro_fixture(), NOW + dt.timedelta(days=90))["metrics"]["us_rate"]["stale"]
        )

    def test_conflicting_duplicate_rejected(self):
        with self.assertRaises(ValueError):
            x.points([{"date": "2026-10-16", "value": 1}, {"date": "2026-10-16", "value": 2}], NOW)

    def test_invalid_numeric_rejected(self):
        for val in (True, "NaN", "Infinity"):
            with self.assertRaises(ValueError):
                x.numeric(val)

    def test_provider_http_error_does_not_expose_key_or_url(self):
        import urllib.error

        with patch.dict(os.environ, {"FRED_API_KEY": "a" * 32}):
            with patch.object(
                x.urllib.request,
                "urlopen",
                side_effect=urllib.error.HTTPError(
                    "https://provider?api_key=secret", 429, "secret", {}, None
                ),
            ):
                with self.assertRaises(x.ProviderError) as err:
                    x.fetch("us_rate", NOW)
        self.assertIn("429", str(err.exception))
        self.assertNotIn("secret", str(err.exception))
        self.assertNotIn("https", str(err.exception))

    def test_btc_closed_days_and_exact_change(self):
        a = x.bitcoin(btc_fixture(), NOW)["metrics"]
        self.assertEqual(a["hash-rate"]["value"], 110)
        self.assertAlmostEqual(a["hash-rate"]["change_7d_pct"], 10)
        self.assertEqual(a["hash-rate"]["observation_date"], "2026-10-18")

    def test_btc_legacy_unit_aliases(self):
        raw = btc_fixture()
        raw["hash-rate"]["unit"] = "Hash Rate"
        raw["difficulty"]["unit"] = "Difficulty"
        raw["n-transactions"]["unit"] = "Transactions"
        self.assertEqual(x.bitcoin(raw, NOW)["metrics"]["hash-rate"]["unit"], "TH/s")

    def test_btc_missing_day_no_interpolation(self):
        raw = btc_fixture()
        for body in raw.values():
            body["values"] = body["values"][1:]
        self.assertIsNone(x.bitcoin(raw, NOW)["metrics"]["hash-rate"]["change_7d_pct"])

    def test_supply_and_unit_validation(self):
        raw = btc_fixture()
        raw["total-bitcoins"]["values"][0]["y"] = 22_000_000
        with self.assertRaises(ValueError):
            x.bitcoin(raw, NOW)
        raw = btc_fixture()
        raw["hash-rate"]["unit"] = "BTC"
        with self.assertRaises(ValueError):
            x.bitcoin(raw, NOW)


class StorageTests(unittest.TestCase):
    setUp = fixtures.StorageTests.setUp
    tearDown = fixtures.StorageTests.tearDown
    connect = fixtures.StorageTests.connect

    def init_cross(self):
        with self.connect() as c:
            x.init_schema(c)

    def loader(self, key, now):
        return copy.deepcopy(btc_fixture()[key])

    def test_btc_no_key_cache_and_raw_snapshot(self):
        self.init_cross()
        with patch.dict(os.environ, {"FRED_API_KEY": "", "SEC_USER_AGENT": ""}):
            first = f.sync(self.connect, "BTCUSD", self.loader, NOW)
            loader = Mock(side_effect=AssertionError("cache should not fetch"))
            second = f.sync(self.connect, "BTCUSD", loader, NOW + dt.timedelta(hours=1))
        self.assertEqual(first["snapshot_id"], second["snapshot_id"])
        self.assertTrue(second["cached"])
        loader.assert_not_called()
        with self.connect() as c:
            row = c.execute("SELECT snapshot_id FROM cross_fundamental_raw").fetchone()
            self.assertEqual(row[0], first["snapshot_id"])

    def test_failure_preserves_snapshot_and_hides_secrets(self):
        self.init_cross()
        first = f.sync(self.connect, "BTCUSD", self.loader, NOW)
        loader = Mock(side_effect=RuntimeError("https://provider?api_key=secret"))
        with self.assertRaises(ValueError) as err:
            f.sync(self.connect, "BTCUSD", loader, NOW + dt.timedelta(hours=7))
        self.assertNotIn("secret", str(err.exception))
        self.assertEqual(f.cached(self.connect, "BTCUSD")["snapshot_id"], first["snapshot_id"])
        self.assertEqual(f.cached(self.connect, "BTCUSD")["last_job"]["status"], "failed")

    def test_fred_key_required_without_requests(self):
        self.init_cross()
        loader = Mock()
        with patch.dict(os.environ, {"FRED_API_KEY": ""}):
            with self.assertRaisesRegex(ValueError, "FRED_API_KEY"):
                f.sync(self.connect, "EURUSD", loader, NOW)
        loader.assert_not_called()

    def test_macro_storage_has_no_key(self):
        self.init_cross()
        key = "a" * 32
        raw = macro_fixture()
        raw["us_rate"]["extra"] = key
        with patch.dict(os.environ, {"FRED_API_KEY": key}):
            result = f.sync(self.connect, "EURUSD", lambda k, n: raw[k], NOW)
        self.assertTrue(result["has_data"])
        with self.connect() as c:
            self.assertNotIn(
                key, c.execute("SELECT payload FROM cross_fundamental_raw").fetchone()[0]
            )

    def test_worker_skips_missing_fred_but_runs_btc(self):
        self.init_cross()
        syncer = Mock()
        with patch.dict(os.environ, {"FRED_API_KEY": ""}):
            runner = f.Runner(
                self.connect,
                syncer=syncer,
                clock=lambda: NOW,
                symbols=list(x.SYMBOLS),
                credential=x.credential,
                enabled=True,
            )
            runner.tick(NOW)
        self.assertEqual(syncer.call_count, 1)
        self.assertEqual(syncer.call_args.args[0], "BTCUSD")
        self.assertEqual(runner.status()["states"][1]["status"], "missing_contact")

    def test_http_routes_read_and_sync_btc(self):
        from http.client import HTTPConnection
        import threading
        from pathlib import Path
        import server

        previous = server.DB
        server.DB = Path(self.path)
        http = None
        try:
            server.init()
            http = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
            thread = threading.Thread(target=http.serve_forever, daemon=True)
            thread.start()
            client = HTTPConnection("127.0.0.1", http.server_port, timeout=5)
            client.request("GET", "/api/fundamentals?symbol=BTCUSD")
            response = client.getresponse()
            self.assertEqual(response.status, 200)
            self.assertFalse(json.loads(response.read())["has_data"])
            with patch.object(x, "fetch", side_effect=lambda k, n: btc_fixture()[k]):
                client.request(
                    "POST",
                    "/api/fundamentals/sync",
                    json.dumps({"symbol": "BTCUSD"}),
                    {"Content-Type": "application/json"},
                )
                response = client.getresponse()
                self.assertEqual(response.status, 200)
                self.assertTrue(json.loads(response.read())["has_data"])
            client.close()
        finally:
            if http:
                http.shutdown()
                http.server_close()
            server.DB = previous
