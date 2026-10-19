"""Deterministic scheduler tests; no provider requests or real-time waits."""

import datetime as dt
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import automation
import datasets
import market_data
import server
from test_pipeline import fixture_rows


class AutomationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_db = server.DB
        server.DB = Path(self.temp.name) / "test.sqlite3"
        server.init()
        self.config = {**automation.settings(), "symbols": ["AAPL"]}
        self.key = patch.dict(os.environ, {"ALPHAVANTAGE_API_KEY": "test-key"})
        self.key.start()
        self.now = dt.datetime(2025, 7, 7, 22, tzinfo=dt.timezone.utc)

    def tearDown(self):
        self.key.stop()
        server.DB = self.old_db
        self.temp.cleanup()

    def put(self, rows=None, source="alphavantage"):
        rows = rows or fixture_rows()
        meta = datasets.metadata_for(source)
        if source == "alphavantage":
            meta.update(
                provider="Alpha Vantage",
                calendar="XNYS",
                price_basis="unadjusted",
                frequency="daily",
            )
        with server.conn() as c:
            c.execute("DELETE FROM prices WHERE symbol='AAPL'")
            c.executemany(
                "INSERT INTO prices VALUES(?,?,?,?)",
                [("AAPL", r["date"], r["close"], source) for r in rows],
            )
            return datasets.snapshot(c, "AAPL", rows, meta)

    def runner(self, sync=None, **config):
        return automation.Runner(
            server.conn,
            sync or Mock(),
            server.experiment,
            server.save_experiment,
            {**self.config, **config},
            clock=lambda: self.now,
        )

    def count(self, table):
        with server.conn() as c:
            return c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def test_no_key_sends_no_request_and_no_synthetic_forecast(self):
        sync = Mock()
        with patch.dict(os.environ, {"ALPHAVANTAGE_API_KEY": ""}):
            runner = self.runner(sync)
            runner.tick(self.now)
        sync.assert_not_called()
        self.assertEqual(self.count("automation_attempts"), 0)
        self.assertEqual(self.count("runs"), 0)
        self.assertEqual(runner.status()["states"][0]["sync_status"], "missing_key")

    def test_retry_budget_and_restart_persistence(self):
        sync = Mock(side_effect=ValueError("provider unavailable"))
        runner = self.runner(sync)
        for minutes in (0, 1, 31, 62, 93):
            runner.tick(self.now + dt.timedelta(minutes=minutes))
        self.assertEqual(sync.call_count, 3)
        self.assertEqual(self.count("automation_attempts"), 3)
        restarted = self.runner(sync)
        restarted.tick(self.now + dt.timedelta(minutes=100))
        self.assertEqual(sync.call_count, 3)
        self.assertEqual(restarted.status()["states"][0]["sync_status"], "daily_limit")
        restarted.tick(self.now + dt.timedelta(days=1))
        self.assertEqual(sync.call_count, 4)

    def test_csv_preserved_and_forecast_deduplicated_across_restart(self):
        identity = self.put(source="csv-import")
        sync = Mock()
        runner = self.runner(sync)
        runner.tick(self.now)
        self.runner(sync).tick(self.now + dt.timedelta(minutes=1))
        sync.assert_not_called()
        self.assertEqual(self.count("runs"), 1)
        with server.conn() as c:
            row = c.execute("SELECT dataset_id,origin FROM runs").fetchone()
            self.assertEqual(tuple(row), (identity, "automatic"))
            self.assertEqual(datasets.current(c, "AAPL")["id"], identity)

    def test_new_snapshot_produces_one_additional_forecast(self):
        self.put(source="csv-import")
        runner = self.runner()
        runner.tick(self.now)
        self.put(fixture_rows(1), source="csv-import")
        runner.tick(self.now + dt.timedelta(minutes=1))
        runner.tick(self.now + dt.timedelta(minutes=2))
        self.assertEqual(self.count("runs"), 2)

    def test_current_session_data_does_not_trigger_provider_request(self):
        rows = fixture_rows()
        self.put(rows)
        cal = market_data.calendar(rows[-1]["date"], rows[-1]["date"])
        now = cal.session_close(rows[-1]["date"]).to_pydatetime() + dt.timedelta(minutes=61)
        sync = Mock()
        runner = self.runner(sync)
        runner.tick(now)
        sync.assert_not_called()
        self.assertEqual(runner.status()["states"][0]["sync_status"], "up_to_date")
        self.assertEqual(self.count("runs"), 1)

    def test_close_delay_holidays_and_early_close(self):
        target, upcoming = automation.release_window(
            dt.datetime(2025, 7, 4, 12, tzinfo=dt.timezone.utc), 60
        )
        self.assertEqual(target, "2025-07-03")
        self.assertEqual(upcoming, "2025-07-07T21:00:00+00:00")
        before, _ = automation.release_window(
            dt.datetime(2025, 7, 7, 20, 30, tzinfo=dt.timezone.utc), 60
        )
        after, _ = automation.release_window(
            dt.datetime(2025, 7, 7, 21, 1, tzinfo=dt.timezone.utc), 60
        )
        self.assertEqual(before, "2025-07-03")
        self.assertEqual(after, "2025-07-07")

    def test_successful_sync_generates_once_per_dataset(self):
        responses = [fixture_rows(), fixture_rows(), fixture_rows(1)]

        def sync(symbol):
            rows = responses.pop(0)
            identity = self.put(rows)
            return {"dataset_id": identity, "message": "Dataset checked"}

        runner = self.runner(sync)
        runner.tick(self.now)
        runner.tick(self.now + dt.timedelta(minutes=31))
        self.assertEqual(self.count("runs"), 1)
        runner.tick(self.now + dt.timedelta(minutes=62))
        self.assertEqual(self.count("runs"), 2)

    def test_forecast_failure_retries_without_provider_requests(self):
        self.put(source="csv-import")
        failed = Mock(side_effect=ValueError("model failure"))
        runner = self.runner(sync_enabled=False)
        runner.experiment = failed
        runner.tick(self.now)
        runner.tick(self.now + dt.timedelta(minutes=1))
        self.assertEqual(failed.call_count, 1)
        self.assertEqual(self.count("automation_attempts"), 0)
        restarted = self.runner(sync_enabled=False)
        restarted.tick(self.now + dt.timedelta(minutes=11))
        self.assertEqual(self.count("runs"), 1)

    def test_worker_runs_and_stops_without_browser(self):
        import threading

        event = threading.Event()
        runner = self.runner()
        runner.tick = Mock(side_effect=lambda: event.set())
        runner.start()
        try:
            self.assertTrue(event.wait(2))
            self.assertTrue(runner.thread.is_alive())
        finally:
            runner.stop()
        self.assertFalse(runner.thread.is_alive())

    def test_disabled_switches(self):
        sync = Mock()
        runner = self.runner(sync, sync_enabled=False, forecast_enabled=False)
        runner.start()
        self.assertIsNone(runner.thread)
        runner.tick(self.now)
        sync.assert_not_called()
        self.assertEqual(self.count("runs"), 0)


if __name__ == "__main__":
    unittest.main()
