# SEC fundamentals

This patch extends the existing BTCUSD-enabled Market Lab project. Apply it from the repository root, not from `frontend`.

## Windows installation

For the automation add-on, first apply the earlier `signal-fundamentals.patch`, then stop both servers and apply `signal-fundamentals-auto.patch` using the same check/apply workflow below. This add-on does not replace the first patch.

Stop the frontend and the one active Python backend with Ctrl+C. Keep a backup or commit of your current changes.

```bat
cd /d "G:\React porject\market-lab"
git apply --check signal-fundamentals.patch
git apply signal-fundamentals.patch
```

If the check fails, do not force it: the patch expects the accumulated project including the earlier BTCUSD patch. No dependency or package.json changes are required.

Add this setting to `backend\.env`, replacing the placeholder with your genuine contact email:

```dotenv
SEC_USER_AGENT=MarketLab your-name@your-domain.com
```

SEC does not require an API key. It requires an identifying User-Agent. Your contact is sent to SEC in the request header; it is not returned to the frontend or stored in raw responses. Never commit your `.env`.

Start one backend process from the repository root:

```bat
.venv-market\Scripts\python.exe backend\server.py
```

In a second terminal:

```bat
cd /d "G:\React porject\market-lab\frontend"
npm run dev
```

Open the app, select **Fundamentals**, choose **AAPL** or **MSFT**, then click **Sync SEC reports**. Subsequent page visits load saved SQLite data without requesting SEC. The SEC sync button reuses a six-hour cache per company. There is a global 45-second cooldown between actual sync attempts. To sync the second company immediately after the first, wait 45 seconds. A separate SEC worker now refreshes AAPL and MSFT automatically when their six-hour cache expires. It checks local eligibility every 60 seconds and processes at most one company per cycle, independently of the price worker.

Add `AUTO_FUNDAMENTALS_ENABLED=true` to `backend\.env` (this is also the default). To disable automatic SEC fetching, set it to `false` and restart. Manual sync remains available. No new Python or npm dependencies are required.

Failed automatic syncs retry after 30 minutes, up to six automatic attempts per company per UTC day. The attempt budget and retry timestamps are stored in SQLite, so restarting does not reset them. A missing SEC contact sends no request. Existing manual syncs and their global cooldown are respected.

The Overview and Fundamentals tabs display SEC worker status and the next permitted report check. These times are eligibility, not a promise that SEC has published a new report. The Fundamentals tab refreshes saved data every 15 seconds without fetching SEC. Keep the backend running; browser tabs are not required for synchronization.

## What is included

- Annual revenue, net income, operating income, operating cash flow, capex, cash, assets, liabilities, equity and diluted EPS where standard facts exist.
- Net margin, operating margin, free cash flow (operating cash flow minus property/plant/equipment purchases), and contiguous annual revenue growth.
- Up to three comparative annual periods from the same filing, selected by actual start/end dates rather than the XBRL `fy` field.
- Per-metric XBRL tag, unit, period, filing date, accession and official SEC link; recent 10-K and 10-Q report links.
- Stored raw responses, content-addressed analysis snapshots, cached current analysis and sync job history. Failed syncs preserve previous data.
- A guided tutorial updated for the new connector. All new frontend styling uses Tailwind utilities.

Missing, mismatched and conflicting facts are unavailable, never silently zero. Cash is cash equivalents only, not cash plus all investments; liabilities are not equivalent to interest-bearing debt. Amounts are USD. EPS is USD per share. Free cash flow is a derived research measure, not an official GAAP subtotal.

## Research scope

This is a latest/as-restated annual view, not a historical point-in-time fundamentals dataset. Quarterly reports are linked but quarterly/TTM metrics are not computed. The metric extractor uses standard US-GAAP entity-wide concepts; custom concepts are not mapped. Balance-sheet values for older comparative periods may be missing in the selected annual filing.

No valuation target, investment rating, LLM interpretation or fundamental price-model input is added. Adding these facts to historical forecasts requires publication-time alignment first. Forex macroeconomic and crypto on-chain fundamentals need separate connectors.

## Endpoints

- `GET /api/fundamentals/automation`: local worker status only; no upstream requests.
- `GET /api/fundamentals?symbol=AAPL`: saved analysis only, no upstream requests.
- `POST /api/fundamentals/sync` with JSON `{"symbol":"AAPL"}`: cached response or a fresh SEC sync.

Data comes from `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json` and `https://data.sec.gov/submissions/CIK##########.json` (Apple CIK 320193; Microsoft CIK 789019). Errors such as 403/429 are displayed without deleting previous results.

Official documentation:
- https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- https://www.sec.gov/about/developer-resources

## Validation

54 backend tests passed, including 11 SEC fixture tests and 10 SEC scheduler tests covering matching periods/accessions, formulas, missing/conflicting facts, company identity, currencies, publication cutoff, raw persistence, cache, failed-sync preservation and required contact configuration. TypeScript checking and Tailwind compilation passed. SEC network access with a real user contact and browser rendering were not verified in the patch environment.

```bat
.venv-market\Scripts\python.exe -m unittest discover -s backend -p "test_*.py"
cd frontend
npx tsc --noEmit
```
