"""Visual evidence transformations: units, periods, missing values and exact comparisons."""

import copy
import json
import unittest

import fundamental_visuals as v
import insights
from test_insights import equity_payload, cross_payload
from test_cross_fundamentals import NOW


class FundamentalVisualTests(unittest.TestCase):
    def test_selected_period_excludes_later_years(self):
        data = equity_payload()["analysis"]
        charts = v.build(data, "AAPL", "2024-09-30", NOW.date())
        self.assertTrue(
            all(p["date"] == "2024-09-30" for c in charts for s in c["series"] for p in s["points"])
        )

    def test_annual_bar_baseline_and_separate_units(self):
        charts = v.build(equity_payload()["analysis"], "AAPL", "2025-09-30", NOW.date())
        self.assertTrue(all(c["zero_baseline"] for c in charts))
        self.assertEqual(next(c for c in charts if c["card_id"] == "net_margin")["unit"], "%")
        self.assertEqual(
            next(c for c in charts if c["card_id"] == "cash_conversion")["unit"], "USD"
        )

    def test_missing_annual_value_is_not_zero(self):
        data = equity_payload()["analysis"]
        data["years"][0]["metrics"]["revenue"]["value"] = None
        chart = v.build(data, "AAPL", "2025-09-30", NOW.date())[0]
        self.assertIsNone(chart["series"][0]["points"][-1]["value"])

    def test_negative_free_cash_flow_preserved(self):
        data = equity_payload()["analysis"]
        data["years"][0]["metrics"]["capex"]["value"] = 60
        chart = next(
            c
            for c in v.build(data, "AAPL", "2025-09-30", NOW.date())
            if c["card_id"] == "free_cash_flow"
        )
        self.assertEqual(chart["series"][-1]["points"][-1]["value"], -20)

    def test_exact_margin_recomputed_from_snapshot_facts(self):
        data = equity_payload()["analysis"]
        data["years"][0]["derived"]["net_margin"] = 999
        chart = next(
            c
            for c in v.build(data, "AAPL", "2025-09-30", NOW.date())
            if c["card_id"] == "net_margin"
        )
        self.assertEqual(chart["series"][0]["points"][-1]["value"], 20)

    def test_rate_overlay_contains_only_shared_dates(self):
        data = cross_payload("EURUSD")["analysis"]
        data["metrics"]["us_rate"]["history"].append({"date": "2026-10-17", "value": 4})
        chart = next(
            c for c in v.build(data, "EURUSD", None, NOW.date()) if c["card_id"] == "rate_spread"
        )
        dates = [[p["date"] for p in s["points"]] for s in chart["series"]]
        self.assertEqual(dates, [["2026-10-16"], ["2026-10-16"]])
        self.assertEqual(chart["unit"], "%")

    def test_no_rate_overlap_stays_empty(self):
        data = cross_payload("EURUSD")["analysis"]
        data["metrics"]["ea_rate"]["history"][0]["date"] = "2026-10-01"
        chart = next(
            c for c in v.build(data, "EURUSD", None, NOW.date()) if c["card_id"] == "rate_spread"
        )
        self.assertTrue(all(not s["points"] for s in chart["series"]))

    def test_monthly_yoy_uses_exact_prior_calendar_month(self):
        data = cross_payload("EURUSD")["analysis"]
        chart = next(
            c for c in v.build(data, "EURUSD", None, NOW.date()) if c["card_id"] == "us_inflation"
        )
        points = chart["series"][0]["points"]
        self.assertIsNone(points[0]["value"])
        self.assertAlmostEqual(points[-1]["value"], 3)
        data["metrics"]["us_cpi"]["history"][0]["date"] = "2025-08-01"
        chart = next(
            c for c in v.build(data, "EURUSD", None, NOW.date()) if c["card_id"] == "us_inflation"
        )
        self.assertIsNone(chart["series"][0]["points"][-1]["value"])

    def test_btc_axes_not_mixed_and_future_today_excluded(self):
        data = cross_payload("BTCUSD")["analysis"]
        data["metrics"]["hash-rate"]["history"] += [
            {"date": NOW.date().isoformat(), "value": 999},
            {"date": "2099-01-01", "value": 999},
        ]
        charts = v.build(data, "BTCUSD", None, NOW.date())
        self.assertEqual(len(charts), 4)
        self.assertEqual(len({c["unit"] for c in charts}), 4)
        self.assertTrue(all(c["max_gap_days"] == 1 for c in charts))
        self.assertTrue(
            all(
                p["date"] < NOW.date().isoformat()
                for c in charts
                for s in c["series"]
                for p in s["points"]
            )
        )

    def test_gaps_and_null_values_are_not_filled(self):
        data = cross_payload("BTCUSD")["analysis"]
        data["metrics"]["hash-rate"]["history"] = [
            {"date": "2026-10-01", "value": 100},
            {"date": "2026-10-05", "value": None},
            {"date": "2026-10-10", "value": 110},
        ]
        chart = v.build(data, "BTCUSD", None, NOW.date())[0]
        self.assertEqual(len(chart["series"][0]["points"]), 3)
        self.assertIsNone(chart["series"][0]["points"][1]["value"])

    def test_no_mutation_and_valid_json(self):
        data = cross_payload("BTCUSD")["analysis"]
        old = copy.deepcopy(data)
        json.dumps(v.build(data, "BTCUSD", None, NOW.date()), allow_nan=False)
        self.assertEqual(data, old)

    def test_blocked_or_no_data_has_no_visuals(self):
        self.assertEqual(insights.build({"has_data": False}, "BTCUSD", now=NOW)["visuals"], [])
        payload = equity_payload()
        payload["analysis"]["annual_filing"]["filed"] = "2099-01-01"
        self.assertEqual(insights.build(payload, "AAPL", now=NOW)["visuals"], [])

    def test_visuals_follow_report_snapshot_and_period(self):
        report = insights.build(equity_payload(), "AAPL", period="2024-09-30", now=NOW)
        self.assertEqual(report["snapshot_id"], "fixture-equity")
        self.assertTrue(
            all(
                p["date"] <= report["period"]
                for c in report["visuals"]
                for s in c["series"]
                for p in s["points"]
            )
        )
