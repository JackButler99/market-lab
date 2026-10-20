"""Regenerate deterministic Python reference outputs for browser parity tests (offline)."""
import datetime as dt
import json
import math
from pathlib import Path
import sys
import tempfile

import datasets
import market_data
import server


def main():
    cases = []
    old = server.DB
    with tempfile.TemporaryDirectory() as directory:
        server.DB = Path(directory) / 'fixture.sqlite3'
        try:
            server.init()
            for index, (symbol, calendar, length) in enumerate([
                ('AAPL', 'XNYS', 100), ('MSFT', 'calendar-days', 180),
                ('EURUSD', market_data.FX_CALENDAR, 130), ('BTCUSD', market_data.CRYPTO_CALENDAR, 150),
            ]):
                dates = market_data.future_dates('2024-01-01', length, calendar)
                rows = [{'date': date, 'close': 100.0 if index == 0 else (1.1 if symbol == 'EURUSD' else 30000.0) * math.exp(0.0004 * i + 0.025 * math.sin(i * 0.7) + (0.1 if i == 90 else 0))} for i, date in enumerate(dates)]
                metadata = {**datasets.metadata_for('csv-import'), 'calendar': calendar}
                with server.conn() as c:
                    identity = datasets.snapshot(c, symbol, rows, metadata)
                    ds = datasets.load(c, identity)
                detail = {**datasets.summary(ds), 'prices': rows}
                outputs = [server.experiment(symbol, model, h, identity) for model in ('trend', 'naive') for h in (1, 7, 14, 30)]
                cases.append({'dataset': detail, 'dates': market_data.future_dates(rows[-1]['date'], 30, calendar), 'expected': outputs})
        finally:
            server.DB = old
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parents[1] / 'frontend/scripts/fixtures/browser-parity.json'
    output.write_text(json.dumps({'generator': 'backend/server.py experiment', 'cases': cases}, separators=(',', ':'), allow_nan=False) + '\n')
    print('Generated', len(cases) * 8, 'Python experiment reference cases')


if __name__ == '__main__':
    main()
