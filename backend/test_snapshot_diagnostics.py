import unittest
from export_scheduled import diagnostic

class DiagnosticTests(unittest.TestCase):
    def test_classifies_provider_failures_without_raw_text(self):
        self.assertIn('ecb: provider HTTP 403', diagnostic(ValueError('ecb: provider returned HTTP 403. secret-url')))
        self.assertIn('TLS certificate', diagnostic(ValueError('ecb: TLS certificate verification failed')))
        self.assertIn('FRED configuration', diagnostic(ValueError('Set FRED_API_KEY to your 32-character FRED key')))
        self.assertIn('CSV schema', diagnostic(ValueError('ecb: response is not the expected ECB CSV')))

    def test_arbitrary_exception_secrets_are_never_returned(self):
        for text in ('https://example.test?api_key=secret-123', 'ecb: timed out secret-123', 'ecb: provider returned HTTP 403 secret-123'):
            output = diagnostic(ValueError(text))
            self.assertNotIn('secret-123', output)
            self.assertNotIn('https://', output)
