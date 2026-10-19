"""Regression for the labeled CSV response supplied by the user."""

import copy
import csv
import io
import unittest
from unittest.mock import MagicMock, patch

import cross_fundamentals as x
from test_cross_fundamentals import NOW, macro_fixture


def labeled_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Key",
            "Frequency",
            "Reference area",
            "Time period or range",
            "Observation value",
            "Title complement",
            "Unit",
            "Unit multiplier",
        ]
    )
    for date in ("2026-10-18", "2026-10-19"):
        writer.writerow(
            [
                x.ECB_KEY,
                "D (Daily)",
                "U2 (Euro area (changing composition))",
                date,
                "2.5",
                "Euro area - Key interest rate, provided by ECB",
                "PCPA (Percent per annum)",
                "0 (Units)",
            ]
        )
    return output.getvalue()


class ECBLabelsTests(unittest.TestCase):
    def test_user_header_labels_and_quoted_commas(self):
        rows = x.parse_ecb_csv(labeled_csv())
        self.assertEqual(
            rows[-1], {"KEY": x.ECB_KEY, "TIME_PERIOD": "2026-10-19", "OBS_VALUE": "2.5"}
        )

    def test_code_headers_still_supported(self):
        text = "KEY,TIME_PERIOD,OBS_VALUE,UNIT_MULT\n" + x.ECB_KEY + ",2026-10-19,2.5,0\n"
        self.assertEqual(x.parse_ecb_csv(text)[0]["OBS_VALUE"], "2.5")

    def test_macro_uses_same_normalizer(self):
        raw = macro_fixture()
        raw["ecb"] = labeled_csv()
        raw["us_rate"]["observations"] = [{"date": "2026-10-19", "value": "4"}]
        data = x.macro(raw, NOW)["metrics"]
        self.assertEqual(data["ea_rate"]["value"], 2.5)
        self.assertEqual(data["rate_spread"]["value"], 1.5)
        self.assertEqual(data["rate_spread"]["observation_date"], "2026-10-19")

    def test_transport_accepts_labeled_response_without_rewriting_raw(self):
        text = labeled_csv()
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = text.encode()
        response.headers = {}
        with patch.object(x.urllib.request, "urlopen", return_value=response):
            self.assertEqual(x.fetch("ecb", NOW), text)

    def test_bom_whitespace_case(self):
        text = (
            "\ufeff key , time period or range , OBSERVATION VALUE \n"
            + x.ECB_KEY
            + ",2026-10-19,2.5\n"
        )
        self.assertEqual(len(x.parse_ecb_csv(text)), 1)

    def test_unknown_or_ambiguous_headers_rejected(self):
        for text in (
            "Key,Date,Price\nwrong,2026-10-19,2.5\n",
            "KEY,TIME_PERIOD,Time period or range,OBS_VALUE\n"
            + x.ECB_KEY
            + ",2026-10-19,2026-10-19,2.5\n",
            "KEY,KEY,TIME_PERIOD,OBS_VALUE\nx,x,2026-10-19,2.5\n",
        ):
            with self.assertRaises(x.ProviderError):
                x.parse_ecb_csv(text)

    def test_wrong_series_rejected_in_labeled_csv(self):
        with self.assertRaisesRegex(x.ProviderError, "identity"):
            x.parse_ecb_csv(labeled_csv().replace(x.ECB_KEY, "OTHER"))

    def test_nonzero_multiplier_rejected(self):
        with self.assertRaisesRegex(x.ProviderError, "multiplier"):
            x.parse_ecb_csv(labeled_csv().replace("0 (Units)", "3 (Thousands)"))

    def test_empty_or_truncated_csv_rejected(self):
        for text in (
            "Key,Time period or range,Observation value\n",
            "Key,Time period or range,Observation value\n" + x.ECB_KEY + ",2026-10-19\n",
        ):
            with self.assertRaises(x.ProviderError):
                x.parse_ecb_csv(text)
