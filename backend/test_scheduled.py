"""Snapshot publication regressions; no live requests."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import export_scheduled as exporter
import server

class ScheduledTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old = server.DB
        server.DB = Path(self.temp.name) / 'test.sqlite3'
        self.env = patch.dict(os.environ, {'MARKET_ENV': 'development'})
        self.env.start()
        server.init()

    def tearDown(self):
        self.env.stop()
        server.DB = self.old
        self.temp.cleanup()

    def test_export_has_matching_dataset_and_all_forecasts(self):
        bundle = exporter.build(live=False)
        for symbol, record in bundle['symbols'].items():
            self.assertEqual(record['asset']['dataset_id'], record['dataset']['dataset_id'])
            self.assertEqual(len(record['forecasts']), 8)
            for forecast in record['forecasts'].values():
                self.assertEqual(forecast['dataset_id'], record['dataset']['dataset_id'])
                self.assertEqual(forecast['symbol'], symbol)
        self.assertEqual(bundle['automation']['mode'], 'scheduled_snapshot')
        self.assertFalse(bundle['automation']['worker_running'])

    def test_provider_failures_preserve_price_groups_and_refresh_status(self):
        previous = exporter.build(live=False)
        with patch.object(server, 'sync_market', side_effect=ValueError('private-url')), \
             patch.object(exporter.fundamentals, 'sync', side_effect=ValueError('private-secret')):
            result = exporter.build(previous, pause=lambda _: None)
        for symbol in exporter.SYMBOLS:
            self.assertEqual(result['symbols'][symbol]['dataset'], previous['symbols'][symbol]['dataset'])
            self.assertEqual(result['symbols'][symbol]['forecasts'], previous['symbols'][symbol]['forecasts'])
        self.assertTrue(all(s['sync_status'] == 'retained' for s in result['automation']['states']))
        self.assertNotIn('private-secret', json.dumps(result))
        self.assertNotIn('private-url', json.dumps(result))

    def test_publication_rejects_secrets_and_private_fields(self):
        with patch.dict(os.environ, {'FRED_API_KEY': 'secret-fixture-123456'}):
            with self.assertRaises(ValueError): exporter.ensure_public({'message': 'secret-fixture-123456'})
        with self.assertRaises(ValueError): exporter.ensure_public({'nested': [{'api_key': 'value'}]})
        with self.assertRaises(ValueError): exporter.ensure_public({'bad_number': float('nan')})

    def test_failed_initial_fetch_does_not_publish_synthetic_prices(self):
        with patch.object(server, 'sync_market', side_effect=ValueError()), \
             patch.object(exporter.fundamentals, 'sync', side_effect=ValueError()):
            result = exporter.build(pause=lambda _: None)
        self.assertEqual(result['dashboard']['assets'], [])
        self.assertTrue(all('dataset' not in r for r in result['symbols'].values()))

    def test_retained_fundamentals_rebuild_insights_from_saved_payload(self):
        previous = exporter.build(live=False)
        previous['symbols']['BTCUSD']['fundamentals']['saved'] = {'has_data': True, 'snapshot_id': 'known', 'analysis': {'example': 1}}
        with patch.object(server, 'sync_market', side_effect=ValueError()), \
             patch.object(exporter.fundamentals, 'sync', side_effect=ValueError()), \
             patch.object(exporter.insights, 'build', return_value={'freshness': 'recomputed'}):
            result = exporter.build(previous, pause=lambda _: None)
        retained = result['symbols']['BTCUSD']['fundamentals']
        self.assertEqual(retained['saved']['snapshot_id'], 'known')
        self.assertEqual(retained['saved']['last_job']['status'], 'failed')
        self.assertEqual(retained['insights']['latest']['freshness'], 'recomputed')
