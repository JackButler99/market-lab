"""Deterministic SEC fixtures; no live requests or contact email required."""

import copy
from contextlib import contextmanager
import datetime as dt
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import fundamentals as f

ACC = "0000320193-25-000001"


def fixtures():
    concepts = {}
    for key, (tags, unit, duration) in f.METRICS.items():
        values = []
        for year, revenue in [(2024, 100), (2025, 120)]:
            value = {
                "revenue": revenue,
                "net_income": revenue / 5,
                "operating_income": revenue / 4,
                "operating_cash_flow": 40,
                "capex": 10,
            }.get(key, 5)
            fact = dict(
                end=f"{year}-09-30",
                filed="2025-11-01",
                val=value,
                form="10-K",
                fp="FY",
                accn=ACC,
                fy=2025,
            )
            if duration:
                fact["start"] = f"{year-1}-10-01"
            values.append(fact)
        concepts[tags[0]] = {"units": {unit: values}}
    return (
        {"cik": 320193, "entityName": "Fixture Apple", "facts": {"us-gaap": concepts}},
        {
            "cik": "0000320193",
            "filings": {
                "recent": {
                    "form": ["10-K"],
                    "filingDate": ["2025-11-01"],
                    "accessionNumber": [ACC],
                    "primaryDocument": ["annual.htm"],
                }
            },
        },
    )


class ExtractionTests(unittest.TestCase):
    def test_comparative_periods_not_fiscal_year_field(self):
        a = f.extract(*fixtures(), "AAPL", dt.date(2026, 1, 1))
        self.assertEqual([y["end"] for y in a["years"]], ["2025-09-30", "2024-09-30"])
        self.assertAlmostEqual(a["years"][0]["derived"]["revenue_yoy"], 20)
        self.assertEqual(a["years"][0]["derived"]["net_margin"], 20)
        self.assertEqual(a["years"][0]["derived"]["free_cash_flow"], 30)
        self.assertIn("annual.htm", a["years"][0]["metrics"]["revenue"]["evidence"]["url"])

    def test_missing_fact_not_zero(self):
        facts, sub = fixtures()
        del facts["facts"]["us-gaap"]["NetIncomeLoss"]
        year = f.extract(facts, sub, "AAPL")["years"][0]
        self.assertIsNone(year["metrics"]["net_income"]["value"])
        self.assertIsNone(year["derived"]["net_margin"])

    def test_mismatched_period_and_accession_excluded(self):
        facts, sub = fixtures()
        facts["facts"]["us-gaap"]["NetIncomeLoss"]["units"]["USD"][1]["start"] = "2025-01-01"
        facts["facts"]["us-gaap"]["OperatingIncomeLoss"]["units"]["USD"][1][
            "accn"
        ] = "0000320193-24-000001"
        metrics = f.extract(facts, sub, "AAPL")["years"][0]["metrics"]
        self.assertIsNone(metrics["net_income"]["value"])
        self.assertIsNone(metrics["operating_income"]["value"])

    def test_conflicting_contexts_unavailable(self):
        facts, sub = fixtures()
        values = facts["facts"]["us-gaap"]["NetIncomeLoss"]["units"]["USD"]
        values.append({**values[-1], "val": 999})
        metric = f.extract(facts, sub, "AAPL")["years"][0]["metrics"]["net_income"]
        self.assertIsNone(metric["value"])
        self.assertIn("Conflicting", metric["issue"])

    def test_wrong_company_rejected(self):
        facts, sub = fixtures()
        facts["cik"] = 789019
        with self.assertRaises(ValueError):
            f.extract(facts, sub, "AAPL")

    def test_future_filings_and_quarterly_facts_excluded(self):
        with self.assertRaises(ValueError):
            f.extract(*fixtures(), "AAPL", dt.date(2025, 1, 1))
        facts, sub = fixtures()
        for concept in facts["facts"]["us-gaap"].values():
            for values in concept["units"].values():
                for fact in values:
                    fact["form"] = "10-Q"
        with self.assertRaises(ValueError):
            f.extract(facts, sub, "AAPL")

    def test_wrong_currency_unavailable(self):
        facts, sub = fixtures()
        concept = facts["facts"]["us-gaap"]["Assets"]
        concept["units"]["EUR"] = concept["units"].pop("USD")
        self.assertIsNone(f.extract(facts, sub, "AAPL")["years"][0]["metrics"]["assets"]["value"])


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = self.tmp.name + "/sec.db"
        self.env = patch.dict(os.environ, {"SEC_USER_AGENT": "MarketLab dev@research.test"})
        self.env.start()
        with self.connect() as c:
            f.init_schema(c)
        self.now = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    @contextmanager
    def connect(self):
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        try:
            with c:
                yield c
        finally:
            c.close()

    def fetch(self, url):
        return copy.deepcopy(fixtures()[0 if "companyfacts" in url else 1])

    def test_sync_raw_snapshot_and_cache(self):
        first = f.sync(self.connect, "AAPL", self.fetch, self.now)

        def fail(url):
            self.fail("Cache hit must not fetch SEC")

        second = f.sync(self.connect, "AAPL", fail, self.now + dt.timedelta(hours=1))
        self.assertTrue(second["cached"])
        self.assertEqual(first["snapshot_id"], second["snapshot_id"])
        with self.connect() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM sec_raw").fetchone()[0], 1)

    def test_failure_preserves_analysis(self):
        first = f.sync(self.connect, "AAPL", self.fetch, self.now)

        def fail(url):
            raise ValueError("SEC unavailable")

        with self.assertRaises(ValueError):
            f.sync(self.connect, "AAPL", fail, self.now + dt.timedelta(hours=7))
        saved = f.cached(self.connect, "AAPL")
        self.assertEqual(first["snapshot_id"], saved["snapshot_id"])
        self.assertEqual(saved["last_job"]["status"], "failed")

    def test_contact_required(self):
        with patch.dict(os.environ, {"SEC_USER_AGENT": ""}):
            with self.assertRaisesRegex(ValueError, "SEC_USER_AGENT"):
                f.sync(self.connect, "AAPL", self.fetch, self.now)

    def test_cross_asset_cache_routes_to_connector(self):
        self.assertTrue(f.cached(self.connect, "EURUSD")["supported"])
        with self.assertRaises(ValueError):
            f.sync(self.connect, "BTCUSD", self.fetch, self.now)
