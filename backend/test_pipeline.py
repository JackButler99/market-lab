"""Offline regression tests. No live provider calls or credentials required."""

import datetime as dt
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

import datasets
import market_data
import server


def fixture_rows(offset=0):
    cal = market_data.calendar("2024-01-01", "2025-12-31")
    days = cal.sessions_in_range("2024-01-01", "2025-01-31")[offset : offset + 100]
    return [
        {"date": day.date().isoformat(), "close": 100.0 + i + offset} for i, day in enumerate(days)
    ]


def payload(rows, symbol="AAPL"):
    return {
        "Meta Data": {"2. Symbol": symbol},
        "Time Series (Daily)": {r["date"]: {"4. close": str(r["close"])} for r in rows},
    }


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.previous_db = server.DB
        server.DB = Path(self.temp.name) / "research.sqlite3"
        server.init()

    def tearDown(self):
        server.DB = self.previous_db
        self.temp.cleanup()

    def unblock(self):
        with server.conn() as c:
            c.execute("UPDATE ingestion_jobs SET started='2000-01-01T00:00:00+00:00'")

    def sync(self, rows):
        self.unblock()
        with patch.object(
            market_data, "fetch_daily", return_value=(rows, json.dumps(payload(rows)))
        ):
            return server.sync_market("AAPL")

    def test_additive_migration_preserves_existing_run(self):
        server.DB = Path(self.temp.name) / "legacy.sqlite3"
        with sqlite3.connect(server.DB) as c:
            c.executescript(
                "CREATE TABLE prices(symbol TEXT,date TEXT,close REAL,source TEXT,PRIMARY KEY(symbol,date));"
                "CREATE TABLE runs(id INTEGER PRIMARY KEY,created TEXT,symbol TEXT,model TEXT,horizon INTEGER,mae REAL,baseline_mae REAL,payload TEXT);"
            )
            c.executemany(
                "INSERT INTO prices VALUES(?,?,?,?)",
                [("AAPL", r["date"], r["close"], "csv-import") for r in fixture_rows()],
            )
            c.execute("INSERT INTO runs(symbol,model,payload) VALUES('AAPL','naive','{}')")
        server.init()
        server.init()
        with server.conn() as c:
            self.assertEqual(
                c.execute("SELECT COUNT(*) FROM prices WHERE symbol='AAPL'").fetchone()[0], 100
            )
            self.assertIsNone(c.execute("SELECT dataset_id FROM runs").fetchone()[0])
            self.assertEqual(c.execute("SELECT COUNT(*) FROM datasets").fetchone()[0], 4)
            self.assertEqual(datasets.current(c, "AAPL")["metadata"]["source"], "csv-import")

    def test_gap_rejected_without_replacing_current_dataset(self):
        first = self.sync(fixture_rows())
        with self.assertRaisesRegex(ValueError, "history gap"):
            self.sync(fixture_rows(150))
        with server.conn() as c:
            self.assertEqual(datasets.current(c, "AAPL")["id"], first["dataset_id"])
            self.assertEqual(c.execute("SELECT COUNT(*) FROM raw_responses").fetchone()[0], 1)

    def test_successful_transport_keeps_secret_out_of_raw_storage(self):
        import io

        secret = "private-test-key"
        data = payload(fixture_rows())
        data["echo"] = secret
        with patch.dict(os.environ, {"ALPHAVANTAGE_API_KEY": secret}):
            with patch(
                "urllib.request.urlopen", return_value=io.BytesIO(json.dumps(data).encode())
            ):
                rows, raw = market_data.fetch_daily("AAPL")
        self.assertEqual(len(rows), 100)
        self.assertNotIn(secret, raw)

    def test_replace_deduplicate_merge_revision_and_replay(self):
        original = server.experiment("AAPL", "trend", 7)
        rows = fixture_rows()
        first = self.sync(rows)
        self.assertEqual(len(server.prices("AAPL")), 100)  # Synthetic history removed.
        self.assertTrue(first["changed"])
        second = self.sync(rows)
        self.assertFalse(second["changed"])
        self.assertEqual(first["dataset_id"], second["dataset_id"])
        extended = self.sync(fixture_rows(1))
        self.assertEqual(extended["rows"], 101)
        revised = fixture_rows(1)
        revised[0]["close"] = 999.0
        correction = self.sync(revised)
        self.assertNotEqual(correction["dataset_id"], extended["dataset_id"])
        replay = server.experiment("AAPL", "trend", 7, original["dataset_id"])
        self.assertEqual(original, replay)
        with server.conn() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM raw_responses").fetchone()[0], 4)
            self.assertEqual(len(datasets.load(c, first["dataset_id"])["observations"]), 100)

    def test_provider_failure_preserves_data_and_records_failure(self):
        with server.conn() as c:
            identity = datasets.current(c, "AAPL")["id"]
        before = server.prices("AAPL")
        with patch.object(
            market_data, "fetch_daily", side_effect=market_data.ProviderError("Quota")
        ):
            with self.assertRaises(market_data.ProviderError):
                server.sync_market("AAPL")
        self.assertEqual(before, server.prices("AAPL"))
        with server.conn() as c:
            self.assertEqual(datasets.current(c, "AAPL")["id"], identity)
            self.assertEqual(c.execute("SELECT status FROM ingestion_jobs").fetchone()[0], "failed")
            self.assertEqual(c.execute("SELECT COUNT(*) FROM raw_responses").fetchone()[0], 0)

    def test_validation_and_calendar(self):
        rows = fixture_rows()
        self.assertEqual(market_data.normalize(payload(rows), "AAPL"), rows)
        for invalid in (
            {"Information": "Key or quota problem"},
            payload(rows, "MSFT"),
            payload(rows[:-1]),
        ):
            with self.assertRaises(market_data.ProviderError):
                market_data.normalize(invalid, "AAPL")
        invalid = payload(rows)
        invalid["Time Series (Daily)"][rows[0]["date"]]["4. close"] = "NaN"
        with self.assertRaises(market_data.ProviderError):
            market_data.normalize(invalid, "AAPL")
        self.assertEqual(
            market_data.future_dates("2025-07-03", 2, "XNYS"), ["2025-07-07", "2025-07-08"]
        )
        self.assertEqual(market_data.future_dates("2025-07-03", 1, "calendar-days"), ["2025-07-04"])

    def test_baseline_all_horizons_and_api_snapshots(self):
        self.sync(fixture_rows())
        for horizon in (1, 7, 14, 30):
            r = server.experiment("AAPL", "naive", horizon)
            self.assertEqual(r["mae"], r["baseline_mae"])
            self.assertGreaterEqual(r["samples"], 10)
            self.assertEqual(len(r["forecast"]), horizon)
            self.assertEqual(r["dataset"]["calendar"], "XNYS")

    def test_missing_key_and_transport_failure_do_not_leak_key(self):
        with patch.dict(os.environ, {"ALPHAVANTAGE_API_KEY": ""}):
            with self.assertRaisesRegex(market_data.ProviderError, "Set ALPHAVANTAGE"):
                market_data.fetch_daily("AAPL")
        secret = "private-test-key"
        with patch.dict(os.environ, {"ALPHAVANTAGE_API_KEY": secret}):
            with patch("urllib.request.urlopen", side_effect=urllib.error.URLError(secret)):
                with self.assertRaises(market_data.ProviderError) as error:
                    market_data.fetch_daily("AAPL")
                self.assertNotIn(secret, str(error.exception))

    def test_http_csv_and_snapshot_replay(self):
        http = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{http.server_port}"

        def call(path, body=None):
            req = urllib.request.Request(
                base + path,
                data=json.dumps(body).encode() if body is not None else None,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req) as response:
                return json.load(response)

        try:
            old = call("/api/experiments", {"symbol": "AAPL", "model": "naive", "horizon": 7})
            rows = fixture_rows()
            csv = "date,close\n" + "\n".join(f"{r['date']},{r['close']}" for r in rows)
            imported = call("/api/import", {"symbol": "AAPL", "csv": csv})
            self.assertNotEqual(imported["dataset_id"], old["dataset_id"])
            replay = call(
                "/api/experiments",
                {"symbol": "AAPL", "model": "naive", "horizon": 7, "dataset_id": old["dataset_id"]},
            )
            self.assertEqual(replay["mae"], old["mae"])
            dash = call("/api/dashboard")
            self.assertEqual(dash["assets"][0]["source"], "csv-import")
            self.assertEqual(dash["runs"][0]["dataset_id"], old["dataset_id"])
            snap = call("/api/datasets?id=" + old["dataset_id"])
            self.assertEqual(len(snap["prices"]), 420)
            with self.assertRaises(urllib.error.HTTPError):
                call("/api/import", {"symbol": "AAPL", "csv": "date,close\n2025-01-01,-1"})
            self.assertEqual(
                call("/api/dashboard")["assets"][0]["dataset_id"], imported["dataset_id"]
            )
        finally:
            http.shutdown()
            http.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
