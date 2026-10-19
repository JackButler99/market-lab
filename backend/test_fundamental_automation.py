"""Persisted SEC scheduling decisions without upstream requests or real-time waits."""

import datetime as dt
import os
import unittest
from unittest.mock import Mock, patch

import fundamentals as f
import test_fundamentals as fixtures


class FundamentalAutomationTests(unittest.TestCase):
    setUp = fixtures.StorageTests.setUp
    tearDown = fixtures.StorageTests.tearDown
    connect = fixtures.StorageTests.connect
    fetch = fixtures.StorageTests.fetch

    # Reuse the database fixture, not the parent test methods.
    def runner(self, syncer=None, enabled=True):
        return f.Runner(
            self.connect, syncer=syncer or Mock(), clock=lambda: self.now, enabled=enabled
        )

    def state(self, symbol):
        with self.connect() as c:
            return dict(
                c.execute(
                    "SELECT * FROM fundamental_automation WHERE symbol=?", (symbol,)
                ).fetchone()
            )

    def test_one_company_each_cycle(self):
        syncer = Mock()
        worker = self.runner(syncer)
        worker.tick(self.now)
        self.assertEqual(syncer.call_count, 1)
        self.assertEqual(syncer.call_args.args[0], "AAPL")
        self.assertEqual(self.state("MSFT")["status"], "queued")
        worker.tick(self.now + dt.timedelta(minutes=1))
        self.assertEqual(syncer.call_count, 2)
        self.assertEqual(syncer.call_args.args[0], "MSFT")

    def test_disabled_does_not_request(self):
        syncer = Mock()
        worker = self.runner(syncer, enabled=False)
        worker.tick(self.now)
        syncer.assert_not_called()
        self.assertEqual(self.state("AAPL")["status"], "disabled")

    def test_missing_contact_does_not_request(self):
        syncer = Mock()
        with patch.dict(os.environ, {"SEC_USER_AGENT": ""}):
            self.runner(syncer).tick(self.now)
        syncer.assert_not_called()
        self.assertEqual(self.state("AAPL")["status"], "missing_contact")

    def test_fresh_manual_cache_is_respected(self):
        f.sync(self.connect, "AAPL", self.fetch, self.now)
        syncer = Mock()
        self.runner(syncer).tick(self.now + dt.timedelta(minutes=1))
        self.assertEqual(self.state("AAPL")["status"], "up_to_date")
        self.assertNotIn("AAPL", [c.args[0] for c in syncer.call_args_list])

    def test_global_manual_cooldown_is_respected(self):
        f.sync(self.connect, "AAPL", self.fetch, self.now)
        syncer = Mock()
        self.runner(syncer).tick(self.now + dt.timedelta(seconds=10))
        syncer.assert_not_called()
        self.assertEqual(self.state("MSFT")["status"], "queued")

    def test_retry_survives_worker_restart(self):
        syncer = Mock(side_effect=ValueError("upstream failed"))
        self.runner(syncer).tick(self.now)
        self.assertEqual(self.state("AAPL")["status"], "retry_scheduled")
        other = self.runner(syncer)
        other.tick(self.now + dt.timedelta(minutes=1))
        self.assertEqual([c.args[0] for c in syncer.call_args_list].count("AAPL"), 1)
        other.tick(self.now + dt.timedelta(minutes=31))
        self.assertEqual([c.args[0] for c in syncer.call_args_list].count("AAPL"), 2)

    def test_daily_budget_persists_across_restart(self):
        with self.connect() as c:
            for _ in range(6):
                c.execute(
                    "INSERT INTO fundamental_auto_attempts(symbol,day,started) VALUES(?,?,?)",
                    ("AAPL", self.now.date().isoformat(), self.now.isoformat()),
                )
        syncer = Mock()
        self.runner(syncer).tick(self.now)
        self.assertEqual(self.state("AAPL")["status"], "daily_limit")
        self.assertNotIn("AAPL", [c.args[0] for c in syncer.call_args_list])

    def test_manual_inflight_sync_defers_worker(self):
        syncer = Mock()
        with f.LOCK:
            self.runner(syncer).tick(self.now)
        syncer.assert_not_called()
        self.assertEqual(self.state("AAPL")["status"], "queued")

    def test_status_is_read_only(self):
        syncer = Mock()
        worker = self.runner(syncer)
        worker.status()
        worker.status()
        syncer.assert_not_called()

    def test_cache_expiry_allows_next_request(self):
        f.sync(self.connect, "AAPL", self.fetch, self.now)
        syncer = Mock()
        worker = self.runner(syncer)
        worker.tick(self.now + dt.timedelta(hours=5))
        worker.tick(self.now + dt.timedelta(hours=6, minutes=1))
        self.assertIn("AAPL", [c.args[0] for c in syncer.call_args_list])
