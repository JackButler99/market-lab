# Fundamental Insight: one reading experience, three analytical engines

This incremental patch requires the accumulated project through `signal-btc-schema-fix.patch`, including the earlier ECB transport and labeled CSV fixes. The scope remains AAPL/MSFT, EURUSD and BTCUSD. No new provider, model, database migration, package or API key is introduced.

## Install on Windows

Stop frontend and backend with Ctrl+C. Commit or back up your current changes. Save `signal-fundamental-insights.patch` in the project root, then:

```bat
cd /d "G:\React porject\market-lab"
git apply --check signal-fundamental-insights.patch
git apply signal-fundamental-insights.patch
.venv-market\Scripts\python.exe backend\server.py
```

In another terminal:

```bat
cd /d "G:\React porject\market-lab\frontend"
npm run dev
```

Do not force the patch if its check fails: it expects the project after the previously delivered fixes. Existing SEC_USER_AGENT, FRED_API_KEY, SSL_CERT_FILE and automation settings remain in place. If certificates were configured only in a terminal, restart the backend from that terminal or retain the working path in backend/.env.

## Guided use

1. Open **Fundamentals** and choose **Stocks · SEC**, **EURUSD · Macro** or **BTCUSD · Network**.
2. Sync the source panel if there is no saved evidence. Existing automatic workers and cache rules continue to apply.
3. Use the new **Fundamental Insight** panel. Explanations are in Bahasa Indonesia; the existing source-data UI remains in English.
4. Select Beginner, Intermediate or Expert. The preference stays in this browser and carries across asset tabs; unavailable localStorage does not prevent the UI from working.
5. Read the observed facts, then the explanation and limits. Open **Bukti & sumber** for the relevant filing or series.
6. In Stocks, change the annual period. The insight panel follows that same period, using only an older contiguous annual period as its comparison. If none exists, the change remains unavailable.
7. Open **Apa arti metrik ini?** on source metric cards for a short definition. Use the searchable glossary for the selected asset class.
8. Review the conditional learning scenarios as investigative questions, not as descriptions of what is currently happening or forecasts.

### Beginner

Plain-language meaning, dated observed facts, explicit limits and source links. Concepts remain available even if a numeric ratio cannot be computed. For example, a missing capex fact does not become zero free cash flow.

### Intermediate

Adds relationships to companion metrics and a follow-up checklist. Potential drivers are presented as things to investigate, never as established causes extracted from management commentary.

### Expert

Adds formula/context, values without compact abbreviations, comparison periods, source tags/series/accessions and available filing/sample timestamps. This is an audit view of the same evidence, not a claim of sector-complete institutional research.

## Class-specific behavior

| Module | Insights | Important limits |
| --- | --- | --- |
| AAPL/MSFT equity | Revenue growth, net margin changes, CFO/net income, CFO minus capex, liabilities/assets | General corporate template only. No peer benchmarks, sector models, valuation, debt maturity or management narrative extraction. Liabilities are not interest-bearing debt. |
| EURUSD macro | Effective US rate, ECB deposit facility, same-date rate difference, US CPI and EA HICP YoY context | Different rate concepts and inflation baskets. No GDP, employment, consensus surprise or policy-expectation dataset. No automatic FX-direction signal. |
| BTCUSD network | Estimated hash rate, difficulty, confirmed transactions, issued supply and exact seven-day comparisons | No entity adjustment, exchange flows, miner profitability, MVRV or liquid-supply estimate. Last available supply timestamp is not guaranteed midnight close. |

CFO/net income is computed only for positive net income; negative/zero earnings do not yield a misleading cash-conversion ratio. Net-margin comparisons use percentage points. Revenue comparison requires contiguous annual periods and a positive prior revenue denominator. Issued-supply snapshots retain the parser fix. BTC seven-day changes are recomputed from exact-date snapshot history, not inferred from rounded labels. Tiny near-zero changes below 1e-9 percentage points are displayed as zero for interpretation.

## Data quality versus interpretation

The quality panel describes availability and freshness, not confidence in an investment thesis. There is no universal positive/negative rating, price-rise probability or asset-health score.

- BTC stale threshold: more than three calendar days since observation.
- Macro rate/spread threshold: more than ten days; monthly inflation threshold: more than 75 days.
- Equity annual threshold: fiscal period end more than 450 days ago. This is an app heuristic, not a regulatory filing-deadline check. Selected older periods are explicitly historical.
- A new fetch timestamp does not make old provider observations current.
- Future-dated annual evidence blocks interpretation. Future-dated cross-asset observations hide their numeric values.
- Failed/interrupted current syncs show a warning while the last successful snapshot remains readable.
- Missing or nonfinite inputs do not silently become zero, and a wholly missing numeric view is labeled incomplete.

Latest/as-restated fundamental observations are not a historical point-in-time feature dataset. No new evidence enters the forecasting model. Publication timestamps, historical vintages and revision handling are prerequisites before using these facts in historical forecasting evaluations.

## Consistency and automatic refresh

The UI sends the displayed source snapshot ID and, for stocks, the selected fiscal period to the insight endpoint. A stored snapshot is loaded by both symbol and ID; an old ID cannot be used for another symbol. If a worker replaces the current data between requests, the explanation stays bound to the snapshot the user is viewing. The UI rejects mismatching response IDs/periods and clears obsolete responses on tab/period changes.

Existing source panels poll saved data every 15 seconds. When their snapshot changes, insights regenerate locally. The insight panel rechecks the pinned report every 60 seconds for freshness and exposes a retry button for errors. Neither reading-level changes nor insight requests contact providers. Keeping the backend running is still necessary for provider automation; a browser tab is not.

## Backend and API

`backend/insights.py` is a pure interpretation layer over saved payloads. It has distinct equity and macro/network rules, versioned as `fundamental-insight-v1`. It does not scrape reports, call an LLM, save forecasts or modify snapshots. Explanations are reproducible for the same snapshot, period, version and as-of date; freshness can change with the as-of date.

```text
GET /api/fundamentals/insights?symbol=AAPL
GET /api/fundamentals/insights?symbol=AAPL&snapshot_id=<saved-id>&period=2025-09-30
GET /api/fundamentals/insights?symbol=EURUSD&snapshot_id=<saved-id>
GET /api/fundamentals/insights?symbol=BTCUSD&snapshot_id=<saved-id>
```

Annual `period` applies only to stocks and must exist in the snapshot. The endpoint returns quality information, observed facts, three explanation depths, comparison metadata, caveats, follow-up checks, source evidence and explicitly hypothetical learning scenarios. The selected equity period is in the response; cross-asset cards carry their individual observation dates.

## Verification

119 backend tests passed, including 22 new tests for ratios, contiguous periods, percentage-point changes, missing/zero/negative earnings, stale/future evidence, exact BTC comparisons, no-data behavior, immutability, safe numeric handling and HTTP snapshot/period isolation. TypeScript and Tailwind compilation passed. Patch check/application reconstructed all changed files against the expected baseline. Browser visual/interactivity QA and a production build were not verified in the authoring environment. Existing provider/network availability remains a separate concern.

```bat
.venv-market\Scripts\python.exe -m unittest discover -s backend -p "test_*.py"
cd frontend
npx tsc --noEmit
```

Recommended local checks: switch reading level in each market tab, select an older stock period, open source evidence, search the glossary, and confirm that stale BTC data explains its observation period rather than claiming to describe the current market. Confirm existing Sync and Automation panels still work.

## Educational references

Explanations are original templates based on financial-statement and source-series definitions, not summaries of unextracted filings:

- SEC guide: https://www.sec.gov/reportspubs/investor-publications/investorpubsbegfinstmtguidehtm.html
- Reading filings: https://www.investor.gov/introduction-investing/getting-started/researching-investments/how-read-10-k
- ECB rate concepts: https://data.ecb.europa.eu/methodology/what-are-interest-rates
- FRED DFF: https://fred.stlouisfed.org/series/DFF
- US CPI: https://fred.stlouisfed.org/series/CPIAUCNS
- EA HICP: https://fred.stlouisfed.org/series/CP0000EZCCM086NEST
- Hash-rate definition: https://www.blockchain.com/explorer/charts/hash-rate

Further coverage requires additional connectors and reviewed asset/sector rules. A glossary entry or a hypothetical follow-up is not evidence that the corresponding dataset has already been ingested.
