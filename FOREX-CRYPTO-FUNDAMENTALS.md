# EURUSD macro and Bitcoin network fundamentals

This add-on requires the earlier `signal-fundamentals.patch` and `signal-fundamentals-auto.patch` already applied. It extends the current Next.js/Tailwind frontend and Python/SQLite backend without adding npm or Python dependencies. Apply it from the project root.

## Install on Windows

1. Stop the frontend and the single active Python backend with Ctrl+C. Commit or back up your current changes, including the SQLite database in `backend/data`.
2. Save `signal-forex-crypto-fundamentals.patch` in your project root.
3. Check and apply:

```bat
cd /d "G:\React porject\market-lab"
git apply --check signal-forex-crypto-fundamentals.patch
git apply signal-forex-crypto-fundamentals.patch
```

If the check fails, do not force the patch. Its baseline is the project after both earlier Fundamentals patches. No package.json or dependency lock changes are included.

4. For EURUSD, obtain a FRED API key: https://fred.stlouisfed.org/docs/api/api_key.html
5. Add these settings to `backend\.env` (replace the placeholder with your actual 32-character FRED key):

```dotenv
FRED_API_KEY=your_fred_key_here
AUTO_FUNDAMENTALS_ENABLED=true
```

Keep the existing SEC_USER_AGENT and ALPHAVANTAGE_API_KEY values. FRED_API_KEY is backend-only; never place it in NEXT_PUBLIC variables or commit `.env`. BTC network data and ECB requests do not use this key. Missing FRED or SEC settings do not block the BTC connector.

6. Start one backend process from the root:

```bat
.venv-market\Scripts\python.exe backend\server.py
```

7. In another terminal:

```bat
cd /d "G:\React porject\market-lab\frontend"
npm run dev
```

Open Fundamentals and select **EURUSD · Macro** or **BTCUSD · Network**. Click **Sync fundamentals**, or wait for the automatic worker. The existing Stocks · SEC tab retains AAPL/MSFT.

## What you can inspect

### EURUSD

| Metric | Source and definition |
| --- | --- |
| US effective overnight rate | Federal Reserve, via FRED `DFF`. This is not the Fed target range. |
| ECB deposit facility rate | ECB `FM.D.U2.EUR.4F.KR.DFR.LEV`, daily level in percent. |
| Rate difference | DFF minus ECB deposit rate, in percentage points, only on the newest common observation date in the fetched window. No fill-forward. These are different rate concepts. |
| US all-items CPI | BLS via FRED `CPIAUCNS`, monthly, not seasonally adjusted, index 1982–84=100. |
| Euro-area all-items HICP | Eurostat via FRED `CP0000EZCCM086NEST`, monthly, not seasonally adjusted, index 2025=100, changing euro-area composition. |
| US/EA inflation YoY | Each index relative to the exact same calendar month one year earlier. Missing prior months remain unavailable. |

The two inflation baskets differ; index levels are not comparable. No inflation-gap score or currency trading recommendation is produced. FRED observations cover the latest revised view as retrieved today, not historical vintages. Observation dates are not publication timestamps.

Rates are flagged stale after 10 days; monthly indices and their YoY measures after 75 days. These thresholds are data-quality checks, not expected official publication schedules. A common date may be unavailable if one rate has no overlapping observation in the downloaded ECB window.

### BTCUSD

Blockchain.com provides estimated hash rate (TH/s), mining difficulty, confirmed daily transactions, and issued supply (BTC). Metrics include seven-day percentage changes only when the exact prior date is present. Current incomplete UTC-day observations are excluded. Network metrics are flagged stale after three days.

Hash rate is an estimate. Transactions are not users, and issued supply is not liquid supply. This connector is specific to Bitcoin, not all crypto assets. It does not provide exchange flows, wallet classification, realized cap or MVRV. Blockchain.com is a third-party data provider, not an official company-reporting authority.

### Evidence and storage

Cards show observation date, unit, source link and stale status. Expand the evidence rows to inspect source series and the latest 15 stored observations. The full downloaded history is retained in each analysis snapshot. Raw responses are stored in `cross_fundamental_raw`, linked by snapshot ID, while current and immutable analysis views use the existing fundamentals tables. API credentials and request URLs containing credentials are not persisted. Freshness flags are recomputed when saved data is read, so older cached evidence can become stale even after failed syncs.

Each sync is atomic across its required sources: EURUSD requires all three FRED series plus ECB, and BTC requires all four charts. If a source fails, the previous complete snapshot is retained; partial results do not replace it. Provider HTTP errors include a safe source name/status code where available.

## Automation

The existing AUTO_FUNDAMENTALS_ENABLED worker now covers AAPL, MSFT, EURUSD and BTCUSD. It processes at most one eligible asset per 60-second cycle and is independent of price ingestion/forecasting. It shares the six-hour cache, 45-second manual/automatic sync cooldown and in-flight lock across fundamental connectors. Allow several cycles after startup to populate every configured asset.

Failed automatic attempts retry after 30 minutes, bounded by six attempts per asset per UTC day. Retry timestamps and budgets survive restarts. Successful cache reads do not request providers. Browser polling every 15 seconds reads saved SQLite data only. Keep one backend running; a browser tab is not required for the worker.

Automatic requests can be disabled with AUTO_FUNDAMENTALS_ENABLED=false followed by a restart. Manual sync remains available. These are periodic updates, not tick-level live macro releases or Bitcoin-node streaming.

## API

The existing routes now accept EURUSD and BTCUSD:

- `GET /api/fundamentals?symbol=EURUSD`
- `GET /api/fundamentals?symbol=BTCUSD`
- `POST /api/fundamentals/sync` with JSON `{"symbol":"EURUSD"}` or `{"symbol":"BTCUSD"}`
- `GET /api/fundamentals/automation` for local worker status.

GET routes never fetch provider data. POST sync applies cache/cooldown rules.

## Research limits and validation

No new fundamentals enter the price predictor yet. Before using macro history in backtests, align release timestamps and historical vintages to prevent future information leaking into earlier predictions. BTC histories are also provider observations that can be revised. No buy/sell score or price target is added.

74 backend tests passed, including 20 new tests for macro/BTC parsing, date alignment, exact YoY/seven-day calculations, missing data, unit/identity validation, cache/snapshot persistence, credential handling, worker independence and HTTP sync routes. TypeScript and Tailwind compilation passed. The patch was checked and applied against a clean copy of its baseline. Live provider fetching and browser rendering were not verified in this environment; fixture tests do not guarantee upstream availability or unchanged provider schemas.

```bat
.venv-market\Scripts\python.exe -m unittest discover -s backend -p "test_*.py"
cd frontend
npx tsc --noEmit
```

## Provider references

- FRED observations: https://fred.stlouisfed.org/docs/api/fred/series_observations.html
- DFF: https://fred.stlouisfed.org/series/DFF
- US CPI: https://fred.stlouisfed.org/series/CPIAUCNS
- Eurostat HICP via FRED: https://fred.stlouisfed.org/series/CP0000EZCCM086NEST
- ECB rate: https://data.ecb.europa.eu/data/datasets/FM/FM.D.U2.EUR.4F.KR.DFR.LEV
- ECB API: https://data.ecb.europa.eu/help/api/data-examples
- Blockchain.com: https://www.blockchain.com/explorer/api/charts_api

Providers can change access policies, schemas and availability; no fallback silently substitutes another series.
