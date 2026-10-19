# Visual fundamental reading

Apply after `signal-fundamental-insights.patch`. This update adds charts and rendered mathematical notation to the existing three reading levels. No npm/Python dependencies, API keys, database migration or provider changes are required. The user's Next.js version and package.json remain unchanged.

## Install

Stop both frontend and backend with Ctrl+C, keep a backup or commit, and save `signal-fundamental-visuals.patch` in the root.

```bat
cd /d "G:\React porject\market-lab"
git apply --check signal-fundamental-visuals.patch
git apply signal-fundamental-visuals.patch
.venv-market\Scripts\python.exe backend\server.py
```

Restart the frontend in another terminal:

```bat
cd /d "G:\React porject\market-lab\frontend"
npm run dev
```

Keep existing .env values, including the working SSL_CERT_FILE path. If the patch check fails, do not force it: it expects the preceding Insight patch and its earlier BTC/ECB fixes.

## Read visually

Open Fundamentals, select a market and reading level. Insight summary values use compact Indonesian formatting. Each numerical insight now includes an appropriate chart. Exact facts are available in **Fakta & angka lengkap** rather than dominating the first view.

| Market | Visual |
| --- | --- |
| AAPL/MSFT | Annual bars for revenue and net margin; grouped bars for income versus operating cash flow, CFO/capex/FCF, and assets/liabilities. All use zero-inclusive axes; negative values remain below zero. |
| EURUSD | Daily US effective-rate line and ECB deposit-rate steps; an overlay restricted to dates shared by both rates; separate monthly CPI/HICP YoY charts. Index levels with different bases are not overlaid. |
| BTCUSD | Separate hash-rate, difficulty, transaction-count and issued-supply charts, each with its own unit. Difficulty uses provider daily steps, not an assertion about exact block retarget times. |

The cash-conversion card intentionally plots the two USD components rather than mixing a multiple with dollar amounts. The rate-spread card plots both rate components in percent while the numeric difference remains in percentage points. FCF components share a USD axis and are grouped, not stacked as if all values were parts of a positive whole.

Stock charts never include a period later than the selected annual period. Missing annual categories stay visible in the table without becoming zero bars. Monthly YoY is recomputed from the exact prior-year month in the pinned index history. First-year months with no comparator are unavailable; gaps inside the valid range remain gaps.

### Interaction and accessibility

- Hover or tap a chart to select the nearest date and inspect exact values in the persistent readout below it.
- Focus a chart, then use Left/Right arrows or Home/End to move through dates.
- Daily charts offer 30-day, 90-day and full-snapshot windows; monthly charts offer 6-month, 12-month and full-snapshot windows. Defaults are 90 days/12 months. Windows end at the last valid observation, not download time.
- Line/step charts disclose their focused Y scale and provide a **Sumbu Y mencakup nol** checkbox. Focus padding prevents tiny floating-point jitter in large, nearly constant values from looking like a large movement.
- Annual bar charts always include zero. Negative values and entirely zero series have valid scales.
- Legends, axis units, dated value readouts, descriptive text and a data table supplement colors. **Lihat tabel angka grafik** exposes exact values and missing observations for keyboard/screen-reader access.
- Chart dimensions track the container so text remains readable at smaller widths; very narrow containers can scroll horizontally.

BTC gaps exceeding one calendar day are not connected. Daily macro plots permit up to four days between recorded observations to accommodate non-observation weekends, and monthly plots permit up to 45 days. Missing numeric observations explicitly break lines. None of these plots creates synthetic observations or interpolated table values. Lines/steps are visual connections between recorded samples, not a continuous data feed.

## Mathematical notation

Open **Cara menghitung** beneath an insight for typeset fractions, subscripts and operators. It is optional at every reading level, with **Sumber LaTeX** additionally available in Expert mode.

The renderer uses author-defined MathML trees with LaTeX source annotations, not an external TeX service. Modern browser MathML support is required for typeset output; the same formula is always explained in ordinary text. Formula/provider strings are not injected as HTML or executed. No KaTeX, MathJax, CDN, fonts or package installation is required.

The growth formula describes the comparison, not the displayed absolute revenue/network value. Revenue growth uses contiguous annual periods; inflation uses the exact prior-year month; BTC comparisons use exactly seven calendar days. Cash conversion requires positive net income. Margin changes remain percentage points.

## Data integrity and scope

Chart specifications are built by `backend/fundamental_visuals.py` using the same pinned payload and selected period as the insight report. `fundamental-insight-v2` responses include a `visuals` array; the existing insight endpoint and snapshot isolation remain in place. A blocked/future-dated annual interpretation has no charts. Current-day/future BTC observations are excluded. Old observations remain stale even if plotted today.

The existing snapshot/period, glossary, reading-level persistence, provider automation and raw source panels remain available. Charts do not add external requests or fundamental inputs to the forecasting model. Changing chart windows/scales is local UI state and consumes no provider calls. This remains AAPL/MSFT, EURUSD and BTCUSD; no universal asset-health or buy/sell score is added.

## Validation

132 backend tests passed, including 13 new tests covering selected periods, units, missing observations, negative cash flow, same-date rate overlays, exact monthly YoY, incomplete BTC days, preserved gaps, immutable inputs and blocked/no-data charts. TypeScript checking, Tailwind compilation and offline React rendering/geometry checks passed. The frontend checks cover zero/negative chart domains, broken line segments, native MathML/LaTeX markup, accessible table/keyboard targets and missing latest annual categories.

Actual browser rendering, pointer/keyboard interaction and production build were not verified in this environment. Offline markup/geometry checks do not substitute for browser QA.

```bat
.venv-market\Scripts\python.exe -m unittest discover -s backend -p "test_*.py"
cd frontend
npx tsc --noEmit
node scripts/check-fundamental-visuals.cjs
```

Recommended browser checks: change a stock annual period, inspect a negative/missing cash-flow observation if available, hover/tap a BTC point, use arrow keys, select different windows, toggle the Y-axis option, open the exact-value table, and inspect a rendered formula in Beginner and Expert modes.

References:
- MathML: https://developer.mozilla.org/en-US/docs/Web/MathML/Reference/Element/math
- Accessible chart descriptions/tables: https://www.w3.org/WAI/tutorials/images/complex/
