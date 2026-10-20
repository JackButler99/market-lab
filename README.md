# Signal — Forecast Research Lab

## Free scheduled deployment

For GitHub Actions + Vercel without a continuously running backend, follow
[FREE-DEPLOYMENT.md](FREE-DEPLOYMENT.md). The public site reads normalized snapshots
updated every six hours; provider secrets stay in GitHub Actions. Snapshot mode
requires a public repository and preserves the last successful data on provider failures.
Local development still uses the Python server and SQLite.

Changes are developed on `feature/v2`; merge into the default branch before enabling
the scheduled workflow. `backup/v1` preserves the previous version.

A local research workspace for exploring financial time series, running forecasting experiments, and comparing models against a simple baseline.

The frontend uses Next.js, React and TypeScript. The Python backend handles CSV ingestion, validation, forecasting, backtesting and SQLite persistence. This MVP establishes a workflow for developing forecasting AI; its current models are a naive baseline and log-linear regression, not deep-learning models.

## Current capabilities

| Area | Available now |
| --- | --- |
| Overview | Asset selection, historical price chart, forecasts and evaluation metrics |
| Experiments | Persisted registry of the latest 20 runs |
| Data pipeline | CSV import, validation, deduplication and dataset inventory |
| Storage | Local SQLite database |
| Fundamentals | SEC annuals for AAPL/MSFT, EURUSD macro, BTC network evidence; three-level educational insights with asset-specific charts |
| Market coverage | AAPL, MSFT, EURUSD and BTCUSD dataset slots |

Initial datasets are **synthetic**, reproducible examples. They are not live quotes or actual historical market prices. Synthetic experiments work without provider keys. Connected fundamentals require the appropriate backend configuration; see the guides below.

## Requirements

- Node.js 20.9 or newer; the user's v22.15.0 meets this minimum.
- npm.
- Python 3.10 or newer.
- Two terminals: one for Python and one for Next.js.

The original archive was authored with Next.js 15. If you have followed the subsequent upgrade instructions, your local package.json and package-lock.json reflect that upgrade. This README does not change dependency versions. Verify your installed version with `npm ls next react react-dom` from frontend.

## Start on Windows

### 1. Start the Python backend

Open Command Prompt:

```bat
cd /d "G:\React porject\market-lab"
python backend\server.py
```

If Windows does not recognize `python`, try:

```bat
py backend\server.py
```

Expected startup message:

```text
Research API: http://localhost:8000
```

Install backend dependencies with `python -m pip install -r backend/requirements.txt`. On first startup it creates the SQLite database and seed data.

### 2. Start the frontend

Open a second Command Prompt:

```bat
cd /d "G:\React porject\market-lab\frontend"
npm install
npm run dev
```

Skip npm install on subsequent launches unless dependencies have changed. Open:

**http://localhost:3000**

Keep both terminals running. Stop each service with Ctrl+C. Use the exact frontend origin above: backend CORS currently allows http://localhost:3000, not other ports or 127.0.0.1 origins.

### 3. Optional configuration

The frontend defaults to http://localhost:8000. To override its API address, create frontend/.env.local:

```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Restart the frontend after changing this variable. This variable is public browser configuration; never put secrets in NEXT_PUBLIC variables. The backend host, port and CORS origin are configured directly in backend/server.py.

## First experiment: use the synthetic dataset

1. Confirm the header shows **API connected**.
2. Open **Overview** and select the AAPL card.
3. Choose **Rolling log-linear trend** in Experiment Builder.
4. Set the horizon to **7 observations**.
5. Click **Run experiment** and wait for completion.
6. Inspect the forecast line and evaluation cards.
7. Open **Experiments** to see the saved run.
8. Return to Overview, select the naive model, keep the same asset and horizon, and run it again.

Changing the selected asset, model or horizon clears the current forecast display. It does not delete saved experiments. The UI does not currently reload a saved run into the chart.

### Understand the chart

| Element | Meaning |
| --- | --- |
| Green line | Last 100 historical close observations |
| Dashed purple line | Future predictions from the selected model |
| Shaded purple region | Exploratory historical residual band |
| As of | Date of the latest stored observation |

The shaded band is based on historical evaluation residuals. It is **not a calibrated confidence interval**, and the same horizon's endpoint residual distribution is applied across the displayed forecast path.

### Understand the metrics

| Metric | Interpretation |
| --- | --- |
| Model MAE | Mean absolute forecast error on evaluation observations; lower is better |
| Baseline MAE | Error from predicting the last known price at the same horizon |
| Vs. baseline | Percentage reduction in MAE relative to the baseline |
| Evaluation samples | Number of evaluated prediction origins |

The improvement formula is `(1 - model_mae / baseline_mae) * 100`. Positive values mean lower error; negative values mean the model performed worse. A zero baseline error displays N/A. A naive-model run should have identical model and baseline MAE.

MAE is measured in the price series' units. Do not compare raw MAE between Bitcoin and EURUSD, or compare runs with different datasets or horizons as if they were equivalent. Lower historical error does not guarantee future accuracy or profitable trading.

## Import your own data

### Prepare the CSV

Required headers are lowercase `date,close`. Example format:

```csv
date,close
2025-01-02,243.85
2025-01-03,243.36
2025-01-06,245.00
```

This short example demonstrates formatting only. An actual import requires:

- At least **100 unique dates**.
- Dates in YYYY-MM-DD format.
- Finite, positive numeric close values; use a dot as the decimal separator.
- A request below 2 MB, including the JSON wrapper.
- Consistent observation frequency and quote units.

Extra columns are ignored. Rows are sorted by date. For duplicate dates, the last row wins. Missing dates are not filled and observation frequency is not automatically checked. The chart assumes USD quotes: supply data with matching units. Use appropriately adjusted historical equity data when evaluating across splits, and document dividend treatment externally.

### Import and run

1. Open **Data pipeline**.
2. Select the destination asset that matches your CSV.
3. Choose the CSV under **Import a price series**.
4. Check the success message and Dataset inventory.
5. Return to Overview, select the asset and run an experiment.

**A successful import replaces the selected asset's entire stored price series.** Validation happens before replacement. An invalid import leaves that series unchanged. The source label becomes csv-import; this label does not verify the original provider or data quality.

Old experiment results remain in SQLite, but dataset version tracking is not implemented. Record the CSV filename, provider, adjustment method and date range externally so you can interpret your experiments later.

## How the forecasting pipeline works

1. Read the selected series from SQLite in date order.
2. Reserve the final approximately 20% for chronological evaluation. For short series and long horizons, expand the evaluation region to retain at least 10 prediction origins.
3. At each origin, use only earlier prices to calculate a prediction.
4. Compare the prediction at the selected horizon's endpoint with the actual observed close.
5. Evaluate the last-price baseline using identical origins and horizon.
6. Aggregate absolute errors into MAE.
7. Generate a future prediction path using all available observations.
8. Save the run, metrics, backtest points and forecast payload in SQLite.

The trend model fits a straight line to log prices over the latest 30 observations at each origin. The naive model repeats the most recent close. Neither model automatically tunes hyperparameters or learns from previous runs. Running experiments adds results to the registry; it does not train a shared AI model.

Evaluation windows overlap and are statistically dependent. There is no separate untouched final test set or trading-strategy evaluation yet.

### Observation horizons and dates

Horizon choices are 1, 7, 14 or 30 **observations**. For a series containing only exchange sessions, seven observations means seven sessions, not seven calendar days.

Forecast date labels follow the calendar policy saved with each dataset. Synthetic seeds are examples and do not update themselves; provider connectors fetch eligible daily observations through the backend worker.

## Fundamentals and live updates

The Fundamentals tab now includes Stocks · SEC (AAPL/MSFT), EURUSD · Macro and BTCUSD · Network. Saved facts include source links, observation/filing dates and snapshots. Backend automation refreshes eligible fundamental data with a six-hour cache; the backend must remain running.

**Fundamental Insight** adds asset-specific charts, native mathematical notation, Beginner / Intermediate / Expert reading modes, Indonesian explanations, glossary search, help on metric cards, conditional learning scenarios, and source evidence. Stocks use corporate financial-statement rules; forex uses two-economy macro context; Bitcoin uses network-specific rules. No universal asset-health score is inferred. The selected annual period and snapshot are preserved throughout the explanation.

Insights are deterministic templates, not an LLM service. They do not explain management motivations from unextracted reports, recommend trades or enter the price predictor. No extra API key or dependency is required for the insight layer. Changing reading level never requests provider data.

Guides: [Visual reading and formulas](FUNDAMENTAL-VISUALS.md), [Fundamental Insight](FUNDAMENTAL-INSIGHTS.md), [SEC fundamentals](FUNDAMENTALS.md), [Forex and crypto fundamentals](FOREX-CRYPTO-FUNDAMENTALS.md), [automation](AUTOMATION.md). Provider transport/parser compatibility fixes and existing credential settings remain in place.

## Storage and project structure

| Path | Purpose |
| --- | --- |
| frontend/app/page.tsx | Dashboard, navigation, API requests and SVG chart |
| frontend/app/tailwind.css | Tailwind theme and global entry point |
| frontend/app/fundamental-insights.tsx | Reading modes, educational insight cards and evidence |
| backend/insights.py | Pure snapshot-based equity/macro/network interpretation rules |
| frontend/app/layout.tsx | Root layout and metadata |
| frontend/package.json | Frontend scripts and dependencies |
| frontend/package-lock.json | Resolved dependency versions |
| backend/server.py | HTTP API, ingestion, models and persistence |
| backend/data/research.sqlite3 | Generated local database |

SQLite stores prices in `prices` and experiments in `runs`. Restarting the backend preserves both. To back up research, stop the backend and copy the SQLite file to a safe location. Data and generated dependencies are excluded from the source archive and gitignore.

## API reference

| Method | Route | Purpose |
| --- | --- | --- |
| GET | /health | Backend health |
| GET | /api/dashboard | Asset inventory, latest runs and pipeline metadata |
| GET | /api/prices?symbol=AAPL | Stored price series |
| GET | /api/fundamentals?symbol=AAPL | Saved fundamental facts |
| GET | /api/fundamentals/insights?symbol=AAPL | Explanations of saved facts; optional snapshot_id and annual period |
| POST | /api/fundamentals/sync | Provider fundamental sync with cache/cooldown |
| POST | /api/experiments | Run and save an experiment |
| POST | /api/import | Validate CSV and replace an asset's prices |

Example experiment request body:

```json
{"symbol":"AAPL","model":"trend","horizon":7}
```

Supported model IDs: trend and naive. Supported symbols: AAPL, MSFT, EURUSD, BTCUSD.

Example import request structure:

```json
{"symbol":"AAPL","csv":"date,close\n2025-01-02,243.85\n..."}
```

The example above is structural only; replace it with at least 100 valid unique rows.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| API offline / Failed to fetch | Start the Python backend and check http://localhost:8000/health; reload the page |
| Frontend starts on port 3001 | Free port 3000 and restart, or deliberately update backend CORS |
| python is not recognized | Try py; verify a compatible Python installation |
| CSV import rejected | Check exact headers, ISO dates, positive closes, unique-date count and request size |
| Forecast disappears | Selecting a different asset, model or horizon clears the current forecast |
| Experiments stay after import | Runs persist independently; dataset versioning is not implemented |
| Refresh does not update market quotes | No external market-data connector is connected |
| npm audit reports vulnerabilities | Inspect the report and update affected dependencies deliberately; validate with audit and build |

Frontend checks, from frontend:

```sh
npm audit
npx tsc --noEmit
npm run build
```

For a local production-mode frontend, after a successful build:

```sh
npm run start
```

The Python backend must still run separately. During initial authoring, TypeScript and Python model checks passed; the production build was blocked by an authoring-environment runtime error and browser visual QA was unavailable. The later Next.js upgrade has not been verified on the user's machine in this conversation.

## Development roadmap

1. Sector-specific equity rules and verified peer benchmarks beyond AAPL/MSFT.
2. GDP, employment, policy expectations and broader forex-pair coverage.
3. Additional Bitcoin network and entity-adjusted metrics with explicit source coverage.
4. Filing narrative extraction and grounded question answering with document citations.
5. Publication-time-aware fundamental feature joins and historical vintage alignment.
6. ML adapters, temporal model evaluation, calibrated intervals and deployment hardening.

This is a localhost research MVP without authentication. Its backend binds to loopback. Do not expose it publicly without adding access controls and reviewing the deployment architecture. Forecasts are experimental research outputs; no trading execution is implemented.
