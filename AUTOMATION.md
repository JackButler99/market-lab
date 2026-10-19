# Backend auto-sync and automatic forecasting

This update follows the data-pipeline and dataset-guard patches. It adds a backend-local worker; it does not create a cloud service or a ChatGPT scheduled task. It supersedes earlier descriptions of manual-only updates.

## Apply

Stop frontend and backend. Back up the SQLite database while the backend is stopped. Save signal-auto-sync.patch in market-lab, then run:

```bat
cd /d "G:\React porject\market-lab"
git apply --check signal-auto-sync.patch
git apply signal-auto-sync.patch
```

No new runtime dependencies are required beyond backend/requirements.txt from the data-pipeline patch.

Your existing backend/.env key is retained. These options default to true; you can add them explicitly:

```dotenv
ALPHAVANTAGE_API_KEY=your_existing_key
AUTO_SYNC_ENABLED=true
AUTO_FORECAST_ENABLED=true
```

Restart the backend after editing the file. False disables the corresponding feature. Do not replace your existing key with the placeholder above.

Run from the root:

```bat
.venv-market\Scripts\python.exe backend\server.py
```

In another terminal:

```bat
cd /d "G:\React porject\market-lab\frontend"
npx tsc --noEmit
npm run dev
```

Use the virtual-environment interpreter, not Python bundled with Inkscape. Start only one backend instance. The updated entrypoint binds the port before starting the worker, so a second process cannot start another scheduled worker on the same port.

## What happens automatically

| Task                  | Behavior                                                                              |
| --------------------- | ------------------------------------------------------------------------------------- |
| Local scheduler check | At startup, then every 60 seconds after each check completes                          |
| Eligible daily data   | Latest exchange session whose close was at least 60 minutes ago                       |
| Provider request      | Only if selected configured API/seed data is behind the eligible session              |
| Retry                 | At least 30 minutes between automatic attempts for an asset                           |
| Request budget        | At most 3 automatic attempts per asset per UTC day, persisted across restarts         |
| Automatic forecast    | Rolling log-linear trend, horizon 7 observations                                      |
| Forecast frequency    | Once per dataset ID, model version and horizon; unique constraint prevents duplicates |
| Browser updates       | Local API polling every 15 seconds; does not call the market-data provider            |

AAPL and MSFT are configured initially. Parameters other than the two enable/disable flags are defined centrally in backend/automation.py. Automatic forecasts for different models/horizons are not configured yet; those combinations remain available manually.

The worker checks missed data when the backend starts, so you do not have to leave a browser open. The computer and Python process must stay running for background work. Work pauses while the machine sleeps or the backend is stopped. Time spent fetching data makes the next check slightly later than exactly 60 seconds.

The calendar accounts for known exchange holidays, early closes and daylight saving changes. A one-hour delay does not guarantee provider availability: a lagging provider triggers bounded retries. It is still daily data, not live intraday quotes. Provider quotas also apply to manual requests; the automatic budget is not a guarantee about total account usage.

## Data protection and forecasts

- Synthetic AAPL/MSFT data is eligible for automatic replacement with API data when a valid key is configured.
- CSV data is preserved. Automatic API sync skips CSV datasets; click manual Sync if you deliberately want to switch that asset back to API data.
- Automatic forecasts may be generated for API and CSV datasets. Seed synthetic data is not automatically forecast.
- Each new eligible dataset gets an automatic forecast; restarting the backend does not duplicate it.
- Failed forecasts retry after 10 minutes without fetching more provider data.
- Forecast generation uses a saved immutable snapshot. It does not train a shared neural network or perform automatic ML retraining.
- Provider failures retain stored data and results. Large gaps outside the compact provider window still require the manual recovery described in DATA-PIPELINE.md.
- Existing runs are retained and labeled manual. New scheduler-generated runs are labeled automatic.

Automatic forecasts can backfill the currently stored API/CSV dataset at startup, even if no new provider request is needed. Reverting to a previously forecast snapshot reuses its existing automatic forecast.

## Dashboard

The Daily market data panel now includes Backend automation:

- Worker state and feature switches.
- Next local check and next market-close eligibility in your browser timezone.
- Per-asset sync status, retry timing and automatic forecast run ID.

The Overview price series reloads when its dataset ID changes. A saved automatic forecast is displayed when it matches the selected asset, dataset, model and horizon. Select trend and 7 observations to see the configured automatic output. The forecast footnote identifies automatic versus manual output.

Experiments shows an Origin column. Replay remains a manual action that reruns the saved snapshot. Existing UI controls and manual Sync are retained.

## Persistence and API

SQLite migrations add automation_state, automation_attempts and runs.origin, plus a unique partial index for automatic forecast deduplication. Attempts and forecasts survive server restarts. No database reset is needed.

- GET /api/automation: effective configuration, worker state, check/release times and per-asset status.
- GET /api/forecast?symbol=AAPL&dataset_id=FULL_ID&model=trend&horizon=7: the latest matching automatic result or null.
- GET /api/dashboard: registry rows now include origin.

Forecast payloads, snapshot IDs and model configurations continue to use the existing versioned pipeline.

## Validation

From the root:

```bat
.venv-market\Scripts\python.exe -m unittest discover -s backend -p "test_*.py" -v
```

The suite covers calendar eligibility, restart-persistent retry limits, unchanged-data request avoidance, CSV protection, one forecast per dataset, forecast retries without provider requests, enable/disable switches and worker shutdown, alongside previous ingestion/replay tests. Tests use fixed clocks and mocked providers; a live API key is not required.

TypeScript, Tailwind compilation, formatting and patch checks were also run. Live provider execution and browser visual QA remain unverified in the authoring environment. Check the worker status with your own configured key after startup.

## Troubleshooting

| Status                         | Action                                                                      |
| ------------------------------ | --------------------------------------------------------------------------- |
| missing key                    | Set backend/.env and restart the backend                                    |
| CSV protected                  | Expected; use manual Sync to replace CSV with API data                      |
| provider lag / retry scheduled | Wait for the displayed retry time; use manual Sync for detailed diagnostics |
| daily limit                    | Automatic attempts resume on the next UTC day                               |
| worker stopped                 | Start the updated backend; check enable/disable flags                       |
| waiting for data               | Synthetic data is not auto-forecast; sync API data or import CSV            |

This remains a local development server. It must be supervised or hosted appropriately before any unattended production use.
