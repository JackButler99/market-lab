"""Auth, WSGI routes, durable SQLite ownership and request-boundary regressions."""

import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import deploy_config as config
import process_lock
import server
from wsgi_app import application


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_db = server.DB
        server.DB = Path(self.temp.name) / "research.sqlite3"
        server.init()
        self.token = "test-" + "a" * 48
        self.env = patch.dict(
            os.environ,
            {
                "MARKET_ENV": "production",
                "API_ACCESS_TOKEN": self.token,
                "DATABASE_PATH": str(server.DB),
                "ALLOWED_ORIGINS": "https://demo.example.test",
            },
        )
        self.env.start()

    def tearDown(self):
        self.env.stop()
        server.DB = self.old_db
        self.temp.cleanup()

    def request(self, path, method="GET", body=b"", token=None, origin="", length=None):
        captured = {}
        environ = {
            "PATH_INFO": path.split("?", 1)[0],
            "QUERY_STRING": path.partition("?")[2],
            "REQUEST_METHOD": method,
            "CONTENT_LENGTH": str(len(body) if length is None else length),
            "CONTENT_TYPE": "application/json",
            "wsgi.input": io.BytesIO(body),
        }
        if token is not None:
            environ["HTTP_AUTHORIZATION"] = "Bearer " + token
        if origin:
            environ["HTTP_ORIGIN"] = origin

        def start(status, headers):
            captured.update(status=int(status.split()[0]), headers=dict(headers))

        result = b"".join(application(environ, start))
        return captured["status"], json.loads(result), captured["headers"]

    def test_health_public_but_data_requires_token(self):
        self.assertEqual(self.request("/health")[0], 200)
        self.assertEqual(self.request("/api/dashboard")[0], 401)
        self.assertEqual(self.request("/api/dashboard", token="wrong")[0], 401)
        self.assertEqual(self.request("/api/dashboard", token=self.token)[0], 200)

    def test_unauthorized_write_cannot_reach_route(self):
        with patch.object(server, "sync_market", side_effect=AssertionError("Must not call sync")):
            self.assertEqual(self.request("/api/sync", "POST", b'{"symbol":"AAPL"}')[0], 401)

    def test_authenticated_admin_write_reaches_existing_route(self):
        with patch.object(
            server, "sync_market", return_value={"message": "fixture updated"}
        ) as sync:
            status, data, _ = self.request("/api/sync", "POST", b'{"symbol":"AAPL"}', self.token)
        self.assertEqual(status, 200)
        self.assertEqual(data["message"], "fixture updated")
        sync.assert_called_once_with("AAPL")

    def test_content_length_limit_and_truncation(self):
        self.assertEqual(
            self.request("/api/sync", "POST", b"", self.token, length=2_000_001)[0], 413
        )
        self.assertEqual(self.request("/api/sync", "POST", b"{}", self.token, length=10)[0], 400)
        self.assertEqual(self.request("/api/sync", "POST", b"", self.token, length="bad")[0], 400)

    def test_explicit_origins_only_no_wildcard(self):
        self.assertEqual(
            self.request("/health", origin="https://demo.example.test")[2][
                "Access-Control-Allow-Origin"
            ],
            "https://demo.example.test",
        )
        self.assertNotIn(
            "Access-Control-Allow-Origin",
            self.request("/health", origin="https://untrusted.example")[2],
        )
        self.assertNotIn("Access-Control-Allow-Origin", self.request("/health")[2])

    def test_invalid_json_does_not_expose_internal_secrets(self):
        status, data, _ = self.request("/api/sync", "POST", b"not json", self.token)
        self.assertEqual(status, 400)
        self.assertNotIn(self.token, json.dumps(data))

    def test_missing_token_fails_closed(self):
        with patch.dict(os.environ, {"API_ACCESS_TOKEN": ""}):
            with self.assertRaises(ValueError):
                config.validate()
            self.assertEqual(self.request("/api/dashboard")[0], 401)

    def test_config_persistent_absolute_path_and_port(self):
        with patch.dict(os.environ, {"DATABASE_PATH": "relative.sqlite3"}):
            with self.assertRaises(ValueError):
                config.database_path()
        with patch.dict(
            os.environ, {"DATABASE_PATH": str(Path(self.temp.name) / "missing" / "db.sqlite3")}
        ):
            with self.assertRaises(ValueError):
                config.validate()
        with patch.dict(os.environ, {"HOST": "0.0.0.0", "PORT": "10000"}):
            self.assertEqual(config.validate(), ("0.0.0.0", 10000))

    def test_unicode_bearer_is_safe_rejection(self):
        self.assertEqual(self.request("/api/dashboard", token="☃")[0], 401)

    def test_os_lock_blocks_second_owner_and_releases(self):
        path = Path(self.temp.name) / "process.lock"
        with process_lock.exclusive(path):
            with self.assertRaises(RuntimeError):
                with process_lock.exclusive(path):
                    pass
        with process_lock.exclusive(path):
            pass

    def test_connection_context_closes_and_wal_enabled(self):
        with server.conn() as connection:
            self.assertEqual(connection.execute("PRAGMA journal_mode").fetchone()[0], "wal")
        with self.assertRaises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")

    def test_development_local_behavior_remains_available(self):
        with patch.dict(os.environ, {"MARKET_ENV": "development"}):
            self.assertEqual(self.request("/api/dashboard")[0], 200)

    def test_methods_and_security_headers(self):
        self.assertEqual(self.request("/api/dashboard", "DELETE", token=self.token)[0], 405)
        self.assertEqual(self.request("/api/dashboard", "OPTIONS")[0], 200)
        self.assertEqual(self.request("/health")[2]["Cache-Control"], "no-store")
