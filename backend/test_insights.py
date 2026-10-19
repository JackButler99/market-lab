"""Snapshot-bound interpretation tests. No provider or language-model requests."""

import copy
import datetime as dt
import json
from pathlib import Path
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from unittest.mock import patch

import cross_fundamentals as x
import fundamentals as f
import insights as i
import server
from test_cross_fundamentals import NOW, btc_fixture, macro_fixture
from test_fundamentals import fixtures


def equity_payload():
    return {
        "has_data": True,
        "snapshot_id": "fixture-equity",
        "fetched_at": NOW.isoformat(),
        "analysis": f.extract(*fixtures(), "AAPL", NOW.date()),
        "last_job": None,
    }


def cross_payload(symbol):
    a = x.macro(macro_fixture(), NOW) if symbol == "EURUSD" else x.bitcoin(btc_fixture(), NOW)
    return {
        "has_data": True,
        "snapshot_id": "fixture-cross",
        "fetched_at": NOW.isoformat(),
        "analysis": a,
        "last_job": None,
    }


def cards(report):
    return {c["id"]: c for c in report["cards"]}


class InterpretationTests(unittest.TestCase):
    def test_three_reading_levels_share_facts_and_sources(self):
        for symbol, payload in [
            ("AAPL", equity_payload()),
            ("EURUSD", cross_payload("EURUSD")),
            ("BTCUSD", cross_payload("BTCUSD")),
        ]:
            report = i.build(payload, symbol, now=NOW)
            self.assertEqual(report["snapshot_id"], payload["snapshot_id"])
            for c in report["cards"]:
                self.assertEqual(set(c["readings"]), {"beginner", "intermediate", "expert"})
                self.assertEqual(len(set(c["readings"].values())), 3)
                self.assertTrue(c["caveat"])
                self.assertTrue(c["evidence"])

    def test_equity_ratios_and_contiguous_growth(self):
        c = cards(i.build(equity_payload(), "AAPL", now=NOW))
        self.assertAlmostEqual(c["revenue"]["comparison"]["value"], 20)
        self.assertEqual(c["net_margin"]["value"], 20)
        self.assertEqual(c["free_cash_flow"]["value"], 30)
        self.assertEqual(c["cash_conversion"]["value"], 40 / 24)
        self.assertEqual(c["liabilities_assets"]["value"], 100)

    def test_selected_historical_year_not_latest(self):
        report = i.build(equity_payload(), "AAPL", period="2024-09-30", now=NOW)
        self.assertEqual(report["period"], "2024-09-30")
        self.assertEqual(report["quality"]["freshness"], "historical")
        self.assertEqual(cards(report)["revenue"]["value"], 100)
        self.assertIsNone(cards(report)["revenue"]["comparison"]["value"])
        self.assertTrue(
            all(ev["period"] == "2024-09-30" for c in report["cards"] for ev in c["evidence"])
        )

    def test_unknown_period_rejected(self):
        with self.assertRaises(ValueError):
            i.build(equity_payload(), "AAPL", period="1999-01-01", now=NOW)

    def test_zero_negative_and_missing_income_no_cash_conversion(self):
        for value in (0, -4, None):
            payload = equity_payload()
            payload["analysis"]["years"][0]["metrics"]["net_income"]["value"] = value
            c = cards(i.build(payload, "AAPL", now=NOW))
            self.assertIsNone(c["cash_conversion"]["value"])

    def test_missing_cash_flow_not_zero(self):
        payload = equity_payload()
        payload["analysis"]["years"][0]["metrics"]["capex"]["value"] = None
        self.assertIsNone(cards(i.build(payload, "AAPL", now=NOW))["free_cash_flow"]["value"])

    def test_gap_suppresses_comparison(self):
        payload = equity_payload()
        payload["analysis"]["years"][0]["start"] = "2024-11-01"
        c = cards(i.build(payload, "AAPL", now=NOW))
        self.assertIsNone(c["revenue"]["comparison"]["value"])
        self.assertIsNone(c["net_margin"]["comparison"]["value"])

    def test_margin_change_is_percentage_points(self):
        payload = equity_payload()
        payload["analysis"]["years"][0]["metrics"]["net_income"]["value"] = 12
        report = i.build(payload, "AAPL", now=NOW)
        change = cards(report)["net_margin"]["comparison"]
        self.assertEqual(change["value"], -10)
        self.assertEqual(change["unit"], "percentage points")
        self.assertTrue(any("margin turun" in w for w in report["warnings"]))

    def test_annual_age_and_future_filing_guards(self):
        payload = equity_payload()
        report = i.build(payload, "AAPL", now=NOW + dt.timedelta(days=800))
        self.assertEqual(report["quality"]["freshness"], "stale")
        payload["analysis"]["annual_filing"]["filed"] = "2099-01-01"
        report = i.build(payload, "AAPL", now=NOW)
        self.assertEqual(report["cards"], [])
        self.assertEqual(report["quality"]["freshness"], "blocked")

    def test_stale_btc_uses_observation_not_fetch_time(self):
        payload = cross_payload("BTCUSD")
        payload["fetched_at"] = (NOW + dt.timedelta(days=10)).isoformat()
        report = i.build(payload, "BTCUSD", now=NOW + dt.timedelta(days=10))
        self.assertEqual(report["quality"]["freshness"], "stale")
        self.assertTrue(all(c["stale"] for c in report["cards"]))

    def test_btc_exact_seven_day_comparison(self):
        payload = cross_payload("BTCUSD")
        payload["analysis"]["metrics"]["hash-rate"]["change_7d_pct"] = 999
        c = cards(i.build(payload, "BTCUSD", now=NOW))
        self.assertAlmostEqual(c["hash-rate"]["comparison"]["value"], 10)
        payload["analysis"]["metrics"]["hash-rate"]["history"] = []
        self.assertIsNone(
            cards(i.build(payload, "BTCUSD", now=NOW))["hash-rate"]["comparison"]["value"]
        )

    def test_tiny_numeric_change_displayed_as_zero(self):
        payload = cross_payload("BTCUSD")
        metric = payload["analysis"]["metrics"]["difficulty"]
        metric["value"] = 100.00000000000001
        self.assertEqual(
            cards(i.build(payload, "BTCUSD", now=NOW))["difficulty"]["comparison"]["value"], 0
        )

    def test_macro_sources_include_both_rate_components(self):
        report = i.build(cross_payload("EURUSD"), "EURUSD", now=NOW)
        c = cards(report)
        self.assertEqual(c["rate_spread"]["value"], 2)
        self.assertTrue(
            {"us_rate", "ea_rate"} <= {ev["metric"] for ev in c["rate_spread"]["evidence"]}
        )
        self.assertIn("bukan pure policy differential", c["rate_spread"]["readings"]["expert"])

    def test_future_cross_observation_has_no_numeric_insight(self):
        payload = cross_payload("BTCUSD")
        payload["analysis"]["metrics"]["hash-rate"]["observation_date"] = "2099-01-01"
        item = cards(i.build(payload, "BTCUSD", now=NOW))["hash-rate"]
        self.assertIsNone(item["value"])
        self.assertIsNone(item["comparison"]["value"])

    def test_no_data_does_not_fabricate_summary(self):
        report = i.build({"has_data": False}, "EURUSD", now=NOW)
        self.assertFalse(report["has_data"])
        self.assertEqual(report["cards"], [])
        self.assertEqual(report["quality"]["freshness"], "no_data")

    def test_missing_values_never_labeled_current(self):
        payload = cross_payload("EURUSD")
        for metric in payload["analysis"]["metrics"].values():
            metric["value"] = None
        self.assertEqual(i.build(payload, "EURUSD", now=NOW)["quality"]["freshness"], "incomplete")

    def test_saved_payload_not_mutated_and_result_finite(self):
        payload = cross_payload("BTCUSD")
        old = copy.deepcopy(payload)
        json.dumps(i.build(payload, "BTCUSD", now=NOW), allow_nan=False)
        self.assertEqual(payload, old)
        for value in (float("nan"), float("inf"), True, "2"):
            self.assertIsNone(i.number(value))

    def test_failed_sync_warns_without_discarding_insight(self):
        payload = cross_payload("BTCUSD")
        payload["last_job"] = {"status": "failed"}
        report = i.build(payload, "BTCUSD", now=NOW)
        self.assertTrue(report["cards"])
        self.assertTrue(any("terakhir gagal" in w for w in report["warnings"]))

    def test_scopes_and_invalid_symbols(self):
        for symbol in ("UNKNOWN", "TSLA"):
            with self.assertRaises(ValueError):
                i.build({}, symbol, now=NOW)
        with self.assertRaises(ValueError):
            i.build(cross_payload("EURUSD"), "EURUSD", period="2025-01-01", now=NOW)


class InsightHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_db = server.DB
        server.DB = Path(self.temp.name) / "test.db"
        server.init()
        first = equity_payload()["analysis"]
        second = copy.deepcopy(first)
        second["years"][0]["metrics"]["revenue"]["value"] = 500
        with server.conn() as c:
            for identity, analysis in (("old-snapshot", first), ("new-snapshot", second)):
                c.execute(
                    "INSERT INTO fundamental_snapshots VALUES(?,?,?,?)",
                    (identity, "AAPL", NOW.isoformat(), json.dumps(analysis)),
                )
            c.execute(
                "INSERT INTO fundamental_current VALUES(?,?,?,?)",
                ("AAPL", "new-snapshot", None, NOW.isoformat()),
            )
        self.http = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join(timeout=2)
        server.DB = self.old_db
        self.temp.cleanup()

    def get(self, path):
        client = HTTPConnection("127.0.0.1", self.http.server_port, timeout=5)
        client.request("GET", path)
        response = client.getresponse()
        status, data = response.status, json.loads(response.read())
        client.close()
        return status, data

    def test_pinned_snapshot_and_period_do_not_follow_current(self):
        with (
            patch.object(f, "fetch_json", side_effect=AssertionError("No network allowed")),
            patch.object(x, "fetch", side_effect=AssertionError("No network allowed")),
        ):
            status, data = self.get(
                "/api/fundamentals/insights?symbol=AAPL&snapshot_id=old-snapshot&period=2024-09-30"
            )
        self.assertEqual(status, 200)
        self.assertEqual(data["snapshot_id"], "old-snapshot")
        self.assertEqual(cards(data)["revenue"]["value"], 100)
        self.assertEqual(data["period"], "2024-09-30")

    def test_snapshot_cannot_be_used_for_another_symbol(self):
        status, data = self.get("/api/fundamentals/insights?symbol=MSFT&snapshot_id=old-snapshot")
        self.assertEqual(status, 400)

    def test_no_snapshot_and_latest_snapshot(self):
        self.assertEqual(self.get("/api/fundamentals/insights?symbol=BTCUSD")[1]["cards"], [])
        status, data = self.get("/api/fundamentals/insights?symbol=AAPL")
        self.assertEqual(status, 200)
        self.assertEqual(cards(data)["revenue"]["value"], 500)
