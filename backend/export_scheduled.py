"""Finite scheduled build. Publishes normalized read responses, never SQLite/raw provider data."""
import argparse
import copy
import datetime as dt
import json
import hashlib
import os
import re
from pathlib import Path
import tempfile
import time

import fundamentals
import insights
import server
from wsgi_app import APIRequest
from email.message import Message

UTC = dt.timezone.utc
SYMBOLS = tuple(server.ASSETS)


def diagnostic(error):
    """Classify into fixed public labels; never return exception text or URLs."""
    text = str(error).lower()
    sources = ('ecb', 'us_rate', 'us_cpi', 'ea_hicp', 'hash-rate', 'difficulty', 'n-transactions', 'total-bitcoins')
    source = next((name for name in sources if text.startswith(name + ':')), 'fundamentals')
    if 'fred_api_key' in text:
        return 'FRED configuration: repository secret FRED_API_KEY must be a valid 32-character key.'
    status = re.search(r'provider returned http ([1-5][0-9]{2})\b', text)
    if status:
        return source + ': provider HTTP ' + status.group(1) + '; check access, key and provider limits.'
    categories = (
        ('certificate verification', 'TLS certificate verification failed'),
        ('tls handshake', 'TLS handshake failed'),
        ('timed out', 'connection/read timeout'),
        ('dns lookup', 'DNS lookup failed'),
        ('network connection', 'network connection failed'),
        ('csv', 'ECB CSV schema/format mismatch'),
        ('series identity', 'provider series identity mismatch'),
        ('unit multiplier', 'provider unit multiplier mismatch'),
        ('encoding or format', 'response encoding/format invalid'),
        ('45 seconds', 'shared provider cooldown active'),
        ('no observations', 'no stored observations'),
    )
    for fragment, label in categories:
        if fragment in text:
            return source + ': ' + label + '.'
    return source + ': fetch or normalization failed; no raw exception published.'


def read(route, **query):
    from urllib.parse import urlencode
    request = APIRequest('/api/' + route + ('?' + urlencode(query) if query else ''), Message(), b'')
    request.do_GET()
    if request.status != 200:
        raise ValueError('Unable to export normalized route')
    return request.payload


def ensure_public(bundle):
    serialized = json.dumps(bundle, allow_nan=False, separators=(',', ':'))
    for name in ('ALPHAVANTAGE_API_KEY', 'FRED_API_KEY', 'API_ACCESS_TOKEN', 'SEC_USER_AGENT'):
        secret = os.getenv(name, '')
        if len(secret) >= 8 and secret in serialized:
            raise ValueError('Public snapshot contains a configured secret; publication blocked')
    def check(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key.lower() in {'api_key', 'apikey', 'authorization', 'companyfacts', 'submissions', 'raw_response'}:
                    raise ValueError('Private field in public snapshot; publication blocked')
                check(item)
        elif isinstance(value, list):
            for item in value: check(item)
    check(bundle)
    if len(serialized.encode()) > 15_000_000:
        raise ValueError('Snapshot exceeds publication size limit')
    return serialized


def fundamental_record(saved, symbol):
    result = {'saved': saved, 'insights': {}}
    result['insights']['latest'] = insights.build(saved, symbol)
    if symbol in ('AAPL', 'MSFT'):
        for year in (saved.get('analysis') or {}).get('years', []):
            result['insights'][year['end']] = insights.build(saved, symbol, year['end'])
    return result


def build(previous=None, live=True, pause=time.sleep):
    now = dt.datetime.now(UTC).isoformat()
    previous = previous or {}
    records = {symbol: copy.deepcopy(previous.get('symbols', {}).get(symbol, {})) for symbol in SYMBOLS}
    price_states, fundamental_states = [], []
    price_requests = fundamental_requests = 0
    for symbol in SYMBOLS:
        record = records.setdefault(symbol, {})
        # Only successful real provider data replaces a previous price group.
        try:
            if live:
                if price_requests: pause(16)
                price_requests += 1
                server.sync_market(symbol)
            ds = read('datasets', symbol=symbol)[0]
            detail = read('datasets', id=ds['dataset_id'])
            if live and detail['source'] == 'synthetic':
                raise ValueError('No provider price data')
            forecasts = {}
            for model in ('trend', 'naive'):
                for horizon in (1, 7, 14, 30):
                    result = server.save_experiment(server.experiment(symbol, model, horizon), origin='automatic')
                    # Stable public run identity, independent of the ephemeral SQLite sequence.
                    identity = symbol + ':' + result['dataset_id'] + ':' + model + ':' + str(horizon)
                    result['id'] = int(hashlib.sha256(identity.encode()).hexdigest()[:12], 16)
                    forecasts[model + ':' + str(horizon)] = result
            asset = next(a for a in read('dashboard')['assets'] if a['symbol'] == symbol)
            record.update(asset=asset, dataset=detail, prices=read('prices', symbol=symbol), forecasts=forecasts)
            price_status = 'updated'
        except Exception:
            price_status = 'retained' if record.get('dataset') else 'unavailable'
        price_states.append({'symbol': symbol, 'sync_status': price_status,
            'sync_message': 'Scheduled fetch completed.' if price_status == 'updated' else 'Provider fetch failed; last successful price snapshot retained if available.',
            'target_session': None, 'sync_retry_at': None,
            'forecast_status': 'ready' if record.get('forecasts') else 'unavailable',
            'forecast_message': 'Precomputed trend/naive forecasts for 1, 7, 14 and 30 observations.', 'forecast_id': None})
        try:
            if live:
                if fundamental_requests: pause(46)
                fundamental_requests += 1
                fundamentals.sync(server.conn, symbol)
            saved = fundamentals.cached(server.conn, symbol)
            if not saved.get('has_data'): raise ValueError('No observations')
            fund_status = 'updated'
        except Exception as error:
            failure = diagnostic(error)
            saved = copy.deepcopy(record.get('fundamentals', {}).get('saved')) or {
                'symbol': symbol, 'supported': True, 'has_data': False,
                'snapshot_id': None, 'fetched_at': None, 'analysis': None}
            saved['last_job'] = {'started': now, 'finished': now, 'status': 'failed',
                'message': failure + ' Saved analysis retained.'}
            fund_status = 'retained' if saved.get('has_data') else 'unavailable'
        record['fundamentals'] = fundamental_record(saved, symbol)
        fundamental_states.append({'symbol': symbol, 'status': fund_status,
            'message': 'Scheduled evidence fetched.' if fund_status == 'updated' else failure + ' Last successful observations retained if available.', 'next_attempt': None})
    runs = []
    for record in records.values():
        for forecast in record.get('forecasts', {}).values():
            runs.append({key: forecast.get(key) for key in ('id', 'symbol', 'model', 'horizon', 'mae', 'baseline_mae', 'dataset_id', 'model_version', 'origin')})
            runs[-1]['created'] = record.get('asset', {}).get('fetched_at') or now
    meta = {'mode': 'scheduled_snapshot', 'generated_at': now,
        'schedule': '17 */6 * * * UTC; best effort', 'states': price_states,
        'worker_running': False, 'sync_enabled': True, 'forecast_enabled': True,
        'next_check': None, 'next_market_release': None, 'last_error': None}
    bundle = {'schema': 1, 'generated_at': now, 'symbols': records,
        'dashboard': {'assets': [r['asset'] for r in records.values() if r.get('asset')],
            'runs': runs, 'pipeline': {'storage': 'Published JSON snapshot', 'mode': 'GitHub Actions every six hours', 'last_checked': now}},
        'automation': meta,
        'fundamental_automation': {**meta, 'enabled': True, 'states': fundamental_states}}
    ensure_public(bundle)
    return bundle


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--previous', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--fixtures', action='store_true', help='Offline synthetic QA only; never used by workflow')
    args = parser.parse_args()
    previous = json.loads(args.previous.read_text()) if args.previous and args.previous.exists() else None
    if previous and (previous.get('schema') != 1 or not isinstance(previous.get('symbols'), dict)):
        raise ValueError('Unsupported previous snapshot')
    # No durable database required: reconstruct publishable responses and retain previous groups on failure.
    with tempfile.TemporaryDirectory() as directory:
        server.DB = Path(directory) / 'build.sqlite3'
        server.init()
        bundle = build(previous, live=not args.fixtures)
        if not args.fixtures and not any(
            record.get('dataset') or record['fundamentals']['saved'].get('has_data')
            for record in bundle['symbols'].values()
        ):
            raise ValueError('No real observations available; publication skipped. Check Actions secrets and provider access.')
        content = ensure_public(bundle)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding='utf-8')
    print('Normalized snapshot prepared. Price status:')
    for state in bundle['automation']['states']:
        print(state['symbol'], state['sync_status'])
    print('Fundamental status:')
    for state in bundle['fundamental_automation']['states']:
        print(state['symbol'], state['status'])
        if state['status'] != 'updated':
            print('  Diagnostic:', state['message'])


if __name__ == '__main__':
    main()
