# Daily market data and reproducible experiments

This update follows the Tailwind and formatting patches. It adds on-demand AAPL/MSFT daily-close sync, validated ingestion, raw response storage, immutable datasets and snapshot replay. This document supersedes earlier README statements about no Python dependencies, no API connector and no dataset versioning.

## 1. Apply the patch

Stop both frontend and backend first. From Windows Command Prompt:

```bat
cd /d "G:\React porject\market-lab"
if exist backend\data\research.sqlite3 copy backend\data\research.sqlite3 backend\data\research-before-pipeline.sqlite3
git apply --check signal-data-pipeline.patch
git apply signal-data-pipeline.patch
```

Retain the backup until you verify the update. Existing prices and runs are preserved by additive SQLite migrations. Existing prices receive an initial snapshot. Old runs are labeled legacy because their original datasets cannot be reliably reconstructed.

## 2. Install Python dependencies

From market-lab:

```bat
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

If python is not recognized, use py for the first command. If you already have a development environment, install the requirements there instead. exchange-calendars supplies exchange-session dates; python-dotenv reads backend/.env. The frontend needs no new npm packages for this patch.

## 3. Configure the provider

Obtain your own API key from https://www.alphavantage.co/support/#api-key.

```bat
if not exist backend\.env copy backend\.env.example backend\.env
notepad backend\.env
```

Set:

```dotenv
ALPHAVANTAGE_API_KEY=your_actual_key
```

Keep this in backend/.env only, never in a NEXT_PUBLIC variable or Git. The backend loads the file on startup; restart it after editing. An existing shell environment variable takes precedence over the file. API keys, quotas and endpoint availability are controlled by the provider.

The connector requests TIME_SERIES_DAILY with outputsize=compact. The documented compact response contains the most recent 100 daily observations. It is unadjusted, not split/dividend-adjusted. This is daily historical data, not streaming prices. See https://www.alphavantage.co/documentation/#daily.

## 4. Start the application

Terminal 1, from market-lab:

```bat
.venv\Scripts\python.exe backend\server.py
```

Terminal 2:

```bat
cd /d "G:\React porject\market-lab\frontend"
npx tsc --noEmit
npm run dev
```

Open http://localhost:3000.

## 5. First sync and experiment

1. Select AAPL in Overview.
2. Click Sync market data in the Daily market data panel.
3. Confirm source alphavantage, price basis unadjusted, as-of date and dataset version.
4. Run a 7-observation experiment.
5. Open Experiments and find its dataset ID and model version.
6. Click Replay to evaluate the same immutable snapshot again.
7. Compare the replay MAE with the original. With this model version and environment, it should match even after another dataset becomes current.

Replay creates a new registry entry and reports its MAE; it does not reopen a historical chart. Legacy runs without snapshot IDs cannot be replayed. CSV imports now also create snapshots, but their original provider, frequency and price adjustments remain unspecified.

## Ingestion behavior

- First API sync replaces the selected asset's synthetic or CSV series. Other assets are unchanged.
- Later API syncs merge by date, apply corrections in the returned window and retain older stored API rows.
- Identical prices and metadata reuse the same SHA-256 dataset ID. Raw successful responses and ingestion attempts are still recorded.
- Changed prices produce a new immutable snapshot. Earlier snapshots and experiment results remain available.
- Dates, symbol, positive finite closes, session continuity and completed exchange sessions are validated before replacement.
- Provider failures, invalid data and unbridgeable gaps preserve the previous active dataset.
- Wait at least 15 seconds between provider attempts. Requests are manual; no scheduler or automatic retry loop consumes your quota.
- If more history is missing than the compact window can bridge, the merge is rejected. Import a complete CSV to reset that asset, then the next API sync deliberately starts a fresh API-only series. It will not preserve CSV history.
- A provider row for a session that has not closed causes rejection; retry after market close.

Unadjusted close series can jump at corporate actions. Do not interpret those jumps as investment returns or claim model quality without adjustment-aware evaluation. The compact window is a pipeline starting point, not a sufficient history for serious model selection.

## Stored evidence and provenance

The existing backend/data/research.sqlite3 database gains:

| Table / field      | Content                                                                      |
| ------------------ | ---------------------------------------------------------------------------- |
| datasets           | Immutable observations, source metadata, creation time and SHA-256 identity  |
| current_dataset    | Active snapshot per asset                                                    |
| raw_responses      | Successful validated provider JSON, endpoint without credentials, fetch time |
| ingestion_jobs     | Attempt status, timestamps and related snapshot/raw-response IDs             |
| runs.dataset_id    | Exact snapshot used by a new experiment                                      |
| runs.model_version | Baseline/trend version label                                                 |
| runs.config_json   | Horizon, model window, validation boundary and calendar library version      |

The full validated provider JSON is stored even though the current model consumes only close prices. API keys are redacted from stored response text and never included in public provider error messages. Failed provider bodies are not retained. The UI shows latest sync status and the last successful fetch time for the active snapshot.

Dataset identity includes symbol, normalized dates/closes and source metadata. Fetch time is excluded so an unchanged sync reuses the snapshot. A snapshot is a normalized research dataset; the raw-response table preserves provider evidence separately.

## Calendars

API equity forecasts use XNYS sessions as the US-equity calendar convention, excluding known weekends and exchange holidays. Session dates are supplied by exchange-calendars; future unexpected closures can still change schedules. Synthetic and CSV forecasts keep calendar-day labels explicitly marked illustrative because CSV frequency is not declared.

## API additions

- POST /api/sync with {"symbol":"AAPL"}.
- GET /api/datasets?symbol=AAPL for up to 100 snapshot summaries.
- GET /api/datasets?id=FULL_DATASET_ID for snapshot metadata and observations.
- POST /api/experiments accepts an optional dataset_id to evaluate that snapshot instead of the active series.

## Verify locally

From market-lab:

```bat
.venv\Scripts\python.exe -m unittest discover -s backend -p "test_*.py" -v
```

The nine offline tests exercise legacy migration, idempotent sync, merging/revisions, history-gap rejection, failure preservation, provider validation, secret redaction, exchange holidays, CSV ingestion and replay after dataset replacement. They use mocked provider responses; no live credentials or requests are used.

TypeScript and Tailwind/PostCSS checks also passed in the authoring environment. Live-provider acceptance must be verified with your own key. Browser QA and a successful production Next.js build were unavailable in the authoring environment.

## Remaining work

Fundamental extraction, report scraping, scheduled ingestion, ML model selection and model-artifact/environment packaging remain future stages. Current snapshots make data reproducible within the implemented model version; the project does not yet archive executable model code or a full environment per run. This remains a localhost app without authentication.
