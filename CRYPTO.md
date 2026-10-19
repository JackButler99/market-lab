# BTC/USD daily API and automation

This patch follows signal-forex.patch. It enables BTCUSD for API sync, backend auto-sync, versioned datasets and automatic trend forecasts. Existing stocks and EURUSD behavior is retained.

## Install

Stop both servers and back up the database while Python is stopped. Save signal-btcusd.patch in market-lab:

```bat
cd /d "G:\React porject\market-lab"
git apply --check signal-btcusd.patch
git apply signal-btcusd.patch
.venv-market\Scripts\python.exe backend\server.py
```

Frontend, in another terminal:

```bat
cd /d "G:\React porject\market-lab\frontend"
npx tsc --noEmit
npm run dev
```

No additional dependency or credential is required by the code. The existing ALPHAVANTAGE_API_KEY is used; endpoint entitlement and provider quota still depend on your account. Keep only one backend process on port 8000.

## Use

1. Select BTCUSD in Overview.
2. Check Daily market data and Backend automation.
3. Seed synthetic BTC data is eligible for automatic API replacement.
4. If BTCUSD contains imported CSV data, automatic replacement is skipped. Click manual Sync once to deliberately switch that asset to API data.
5. After API data arrives, the worker generates a trend forecast with a 7-observation horizon.
6. Select trend and horizon 7 to display the automatic result. Other model/horizon combinations can still be run manually.
7. Inspect source, as-of date, CRYPTO_DAILY_UTC calendar, dataset version and automatic Origin.

If the backend status still lists only three symbols, the old process is serving requests. Restart the updated backend and inspect http://localhost:8000/api/automation; its symbols list should now include BTCUSD.

## Source

The request is:

```text
https://www.alphavantage.co/query?function=DIGITAL_CURRENCY_DAILY&symbol=BTC&market=USD&apikey=YOUR_KEY
```

The documented endpoint is refreshed daily at midnight UTC. Unlike the stock and FX daily requests, this request does not send outputsize=compact. History length is determined by the provider response.

The connector checks BTC identity, USD market currency and UTC/GMT metadata. It accepts plain USD-close fields and currency-qualified USD-close fields, rejects conflicting values, and does not reinterpret BTC/USDT as BTC/USD. The model currently consumes date and close; validated raw JSON remains stored for evidence.

This is a provider daily reference series. The app does not offer an executable exchange quote, venue selection or order execution.

## Date policy and validation

- Crypto history and forecasts include all calendar days, including Saturday and Sunday.
- The current UTC date is excluded as potentially incomplete; future-dated rows are rejected.
- Each stored date represents the declared UTC-date modeling convention.
- At least 70 completed observations must remain, enough for the current model/evaluation windows.
- Prices must be finite and positive; invalid identities, unsupported timezone metadata and conflicting close fields are rejected.
- Missing calendar dates are rejected rather than filled. A merge that leaves a gap preserves the previous active dataset.
- Identical normalized prices and metadata reuse the existing snapshot. Changed data produces a new snapshot and one new automatic forecast.

## Scheduling

BTCUSD joins the three existing assets in the worker configuration. For a BTC bar labeled D, the automatic request becomes eligible at 01:00 UTC on D+1, including weekends: midnight plus the existing one-hour delay. Provider publishing delays can still require retries.

The worker checks local state every 60 seconds, performs at most one provider request per check, waits 30 minutes between automatic retries for an asset and allows at most three automatic attempts per asset per UTC day. Four configured assets can therefore generate at most 12 automatic attempts per UTC day, in addition to manual requests. The provider's account limits may be stricter.

The Python backend must remain running. The browser may be closed. CSV protection, snapshots, Replay, retry persistence and automatic-forecast deduplication are retained.

## Verification

```bat
cd /d "G:\React porject\market-lab"
.venv-market\Scripts\python.exe -m unittest discover -s backend -p "test_*.py" -v
```

All 33 offline tests passed. Crypto coverage includes weekend bars, current-day exclusion, quote identity, close-field variants, invalid/gapped data, request parameters, calendar eligibility, snapshots, auto-forecast deduplication and minimum history across all horizons. Existing stock, FX and scheduler tests also passed. TypeScript, Tailwind compilation, formatting and patch application were checked.

The public demo requests attempted for this crypto endpoint returned an Information response instead of price data. Tests use fixtures; authenticated BTC/USD execution and browser visual behavior remain unverified in the authoring environment. Use manual Sync to surface any account-entitlement or schema error with your own key. Never share the key in logs or screenshots.

Reference: https://www.alphavantage.co/documentation/#digital-currency-daily
