"""Regression for observed Blockchain.com units and intraday supply snapshots."""

import datetime as dt
import unittest

import cross_fundamentals as x
from test_cross_fundamentals import NOW, btc_fixture


class BitcoinSchemaTests(unittest.TestCase):
    def test_observed_hash_rate_unit(self):
        raw = btc_fixture()
        raw["hash-rate"]["unit"] = "Hash Rate TH/s"
        self.assertEqual(x.bitcoin(raw, NOW)["metrics"]["hash-rate"]["unit"], "TH/s")

    def test_intraday_supply_uses_latest_timestamp_in_any_order(self):
        raw = btc_fixture()
        base = (NOW - dt.timedelta(days=1)).timestamp()
        raw["total-bitcoins"]["values"] = [
            {"x": base + 80000, "y": 20_098_862.5},
            {"x": base + 100, "y": 20_098_859.375},
            {"x": base + 40000, "y": 20_098_860},
        ]
        metric = x.bitcoin(raw, NOW)["metrics"]["total-bitcoins"]
        self.assertEqual(metric["value"], 20_098_862.5)
        self.assertEqual(len(metric["history"]), 1)
        self.assertEqual(
            metric["observation_timestamp"],
            dt.datetime.fromtimestamp(base + 80000, dt.timezone.utc).isoformat(),
        )

    def test_today_and_future_supply_excluded(self):
        raw = btc_fixture()
        base = (NOW - dt.timedelta(days=1)).timestamp()
        raw["total-bitcoins"]["values"] = [
            {"x": base, "y": 20_000_000},
            {"x": NOW.timestamp(), "y": 20_000_100},
            {"x": NOW.timestamp() + 86400, "y": 20_000_200},
        ]
        self.assertEqual(x.bitcoin(raw, NOW)["metrics"]["total-bitcoins"]["value"], 20_000_000)

    def test_conflicting_same_timestamp_is_not_silently_chosen(self):
        timestamp = (NOW - dt.timedelta(days=1)).timestamp()
        with self.assertRaisesRegex(x.ProviderError, "same timestamp"):
            x.bitcoin_history(
                "total-bitcoins", [{"x": timestamp, "y": 1}, {"x": timestamp, "y": 2}], NOW
            )

    def test_other_metrics_keep_daily_conflict_validation(self):
        base = (NOW - dt.timedelta(days=1)).timestamp()
        with self.assertRaisesRegex(x.ProviderError, "conflicting daily"):
            x.bitcoin_history("hash-rate", [{"x": base, "y": 1}, {"x": base + 1, "y": 2}], NOW)

    def test_invalid_earlier_supply_not_hidden_by_later_valid_value(self):
        base = (NOW - dt.timedelta(days=1)).timestamp()
        with self.assertRaises(x.ProviderError):
            x.bitcoin_history(
                "total-bitcoins",
                [{"x": base, "y": 22_000_000}, {"x": base + 1, "y": 20_000_000}],
                NOW,
            )

    def test_source_timestamps_recorded_per_daily_supply_value(self):
        raw = btc_fixture()
        result = x.bitcoin(raw, NOW)["metrics"]["total-bitcoins"]
        self.assertTrue(all("source_timestamp" in p for p in result["history"]))
        self.assertIn("sampling_policy", result)
        self.assertAlmostEqual(result["change_7d_pct"], 10)

    def test_malformed_observation_has_safe_source_specific_error(self):
        with self.assertRaisesRegex(x.ProviderError, "hash-rate: invalid") as err:
            x.bitcoin_history("hash-rate", [{"x": "secret", "y": 1}], NOW)
        self.assertNotIn("secret", str(err.exception))
