# EUR/USD daily API and automation

This patch follows signal-auto-sync.patch. It enables the existing EURUSD dataset slot for Alpha Vantage FX_DAILY, the backend scheduler and automatic trend forecasts. It uses the API key already configured in backend/.env. No extra dependencies or key are required by the implementation; endpoint access and quotas depend on the provider account.

## Install

Stop backend and frontend. Back up the database while the backend is stopped. Save signal-forex.patch in market-lab:

```bat
cd /d "G:\React porject\market-lab"
git apply --check signal-forex.patch
git apply signal-forex.patch
.venv-market\Scripts\python.exe backend\server.py
```

In another terminal:

```bat
cd /d "G:\React porject\market-lab\frontend"
npx tsc --noEmit
npm run dev
```

Run only one backend instance on port 8000. If the API still reports the old symbols, stop the old process before restarting the updated backend.

## Use

1. Select EURUSD in Overview.
2. Inspect Daily market data and Backend automation.
3. API sync can run automatically when the stored series is behind the eligible UTC weekday.
4. Use Sync market data for an immediate request or provider diagnostics.
5. After new API data arrives, the worker generates a trend forecast with horizon 7.
6. Select that model/horizon to display the automatic result. Other combinations remain available manually.
7. Check the dataset ID and Origin in Experiments; Replay uses the saved snapshot.

If EURUSD currently contains imported CSV data, automatic API replacement is skipped. Click manual Sync once to deliberately switch that asset to API data. Subsequent API updates are automatic when the backend remains active and both AUTO_SYNC_ENABLED and AUTO_FORECAST_ENABLED are true.

Synthetic EURUSD seed prices can be replaced automatically. AAPL and MSFT keep their existing exchange-calendar behavior. Crypto is still CSV/manual only.

## Date and quote policy

The provider's public EUR/USD demo response reports UTC metadata and uses Time Series FX (Daily). This connector checks the EUR/USD pair and accepts UTC/GMT timezone metadata only.

For this MVP, the normalized dataset policy is explicitly **completed UTC dates, weekdays only**:

- A row dated today UTC is excluded because the daily endpoint may still update it.
- Saturday and Sunday rows are excluded. Their raw response remains stored for evidence.
- A weekday labeled D becomes eligible for scheduled fetching at 01:00 UTC on D+1: UTC midnight plus the existing one-hour delay.
- Friday becomes eligible Saturday at 01:00 UTC. The next weekday bar after Friday is Monday, eligible Tuesday at 01:00 UTC.
- Forecast date labels advance across weekdays. They do not use XNYS or claim New York 5pm session boundaries.
- Forex is decentralized. This weekday grid is a modeling convention, not an authoritative holiday/session calendar. A projected weekday may have no provider quote.

Horizon remains a number of observations for backtesting. Forecast dates use the weekday grid, so dates are approximate when provider weekdays are absent.

Prices are USD per EUR and labeled spot. They are not equity adjusted closes.

## Validation and missing data

FX compact fetch requests 100 raw daily rows. At least 70 completed weekday rows must remain after filtering, enough for the current 30-observation model window and supported evaluation horizons. The retained row count may be below 100. CSV imports keep their existing 100-unique-date minimum.

Dates and closes must be valid, finite and positive. Future-dated rows, wrong pairs, unsupported/missing timezone metadata and provider errors are rejected without changing current data.

Missing weekdays inside the stored range are recorded in dataset metadata and shown as a count in the UI. They are not forward-filled. Gaps longer than seven calendar days are rejected as a conservative data-quality policy. This threshold is not a universal FX market rule.

Subsequent API syncs merge overlapping dates and preserve old history. A disconnected compact response is rejected rather than silently joining non-overlapping periods. Raw evidence, immutable snapshot IDs and replay behavior are retained.

## Scheduler

EURUSD joins AAPL and MSFT in the configured symbol list. Equity eligibility still follows XNYS session closes, including known holidays and early closes. FX eligibility uses the separate UTC weekday convention above.

The scheduler checks local state every 60 seconds, sends at most one provider request per check, waits 30 minutes before automatic retries, and limits automatic requests to three attempts per asset per UTC day. Across the three assets this is at most nine automatic attempts per UTC day, plus any manual requests. Provider quotas may impose stricter limits.

The automation API now returns next_market_releases keyed by symbol. The selected asset's panel displays its own next eligibility time in the browser timezone.

## Verification

```bat
cd /d "G:\React porject\market-lab"
.venv-market\Scripts\python.exe -m unittest discover -s backend -p "test_*.py" -v
```

The combined 26-test suite passed. New tests cover EUR/USD request parameters, pair/timezone validation, incomplete/weekend exclusion, missing-weekday reporting, separate FX/equity dates, snapshots, merging and automatic forecast deduplication. TypeScript, Tailwind compilation and formatting checks also passed.

The provider's public demo was inspected to confirm the response schema; authenticated requests using the user's key and browser visual behavior have not been exercised in the authoring environment. Quota or entitlement errors must be checked with the configured account.

## References

- https://www.alphavantage.co/documentation/#fx-daily
- https://www.alphavantage.co/query?function=FX_DAILY&from_symbol=EUR&to_symbol=USD&apikey=demo
