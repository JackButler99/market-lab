"""ECB HTTP negotiation and safe transport diagnostics. No network calls."""

import datetime as dt
import gzip
import socket
import ssl
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

import cross_fundamentals as x

NOW = dt.datetime(2026, 10, 19, tzinfo=dt.timezone.utc)
CSV = b"KEY,TIME_PERIOD,OBS_VALUE\nFM.D.U2.EUR.4F.KR.DFR.LEV,2026-10-16,2\n"


class ECBTransportTests(unittest.TestCase):
    def response(self, body, encoding=""):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = body
        response.headers = {"Content-Encoding": encoding}
        return response

    def test_official_csv_accept_and_longer_timeout(self):
        with patch.object(x.urllib.request, "urlopen", return_value=self.response(CSV)) as call:
            self.assertEqual(x.fetch("ecb", NOW), CSV.decode())
        req = call.call_args.args[0]
        self.assertEqual(req.get_header("Accept"), "application/vnd.ecb.data+csv;version=1.0.0")
        self.assertEqual(call.call_args.kwargs["timeout"], 60)
        self.assertIn("startPeriod=", req.full_url)

    def test_gzip_with_and_without_header(self):
        for encoding in ("gzip", ""):
            with patch.object(
                x.urllib.request,
                "urlopen",
                return_value=self.response(gzip.compress(CSV), encoding),
            ):
                self.assertEqual(x.fetch("ecb", NOW), CSV.decode())

    def test_bom_csv(self):
        with patch.object(
            x.urllib.request, "urlopen", return_value=self.response(b"\xef\xbb\xbf" + CSV)
        ):
            self.assertTrue(x.fetch("ecb", NOW).startswith("KEY"))

    def test_html_response_detected(self):
        with patch.object(
            x.urllib.request,
            "urlopen",
            return_value=self.response(b"<html>secret proxy page</html>"),
        ):
            with self.assertRaisesRegex(x.ProviderError, "expected ECB CSV") as error:
                x.fetch("ecb", NOW)
        self.assertNotIn("secret", str(error.exception))

    def test_safe_network_error_categories(self):
        cases = [
            (ssl.SSLCertVerificationError(1, "secret"), "certificate verification"),
            (ssl.SSLError(1, "secret"), "TLS handshake"),
            (TimeoutError("secret"), "timed out"),
            (socket.gaierror(11001, "secret"), "DNS lookup"),
            (ConnectionResetError("secret"), "Network connection"),
        ]
        for reason, expected in cases:
            with self.subTest(expected=expected):
                with patch.object(
                    x.urllib.request, "urlopen", side_effect=urllib.error.URLError(reason)
                ):
                    with self.assertRaisesRegex(x.ProviderError, expected) as error:
                        x.fetch("ecb", NOW)
                self.assertNotIn("secret", str(error.exception))

    def test_decompressed_body_limit(self):
        with patch.object(
            x.urllib.request,
            "urlopen",
            return_value=self.response(gzip.compress(b"A" * 8_000_001), "gzip"),
        ):
            with self.assertRaisesRegex(x.ProviderError, "8 MB"):
                x.fetch("ecb", NOW)
