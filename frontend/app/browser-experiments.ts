// Pure calculations shared by the interactive browser demo and Python parity checks.
export type Observation = { date: string; close: number };
export type DemoDataset = {
  dataset_id: string; symbol: string; created: string; source: string;
  calendar: string; price_basis: string; prices: Observation[];
  start_date: string; end_date: string; observations: number;
  provider?: string; frequency?: string; currency?: string; forecast_dates?: string[];
};
export type DemoResult = {
  id?: number; created?: string; symbol: string; model: string; horizon: number;
  dataset_id: string; dataset: Omit<DemoDataset, "prices">; origin: "manual";
  source: string; model_version: string; mae: number; baseline_mae: number; samples: number;
  train_end: string; band_note: string; execution: string;
  config: { model: string; horizon: number; window: number; validation: string;
    evaluation_start_index: number; calendar: string; calendar_library: string };
  backtest: { date: string; actual: number; predicted: number }[];
  forecast: { date: string; predicted: number; lower: number; upper: number }[];
};
export const MAX_ROWS = 10000;
export function validDate(value: string) {
  return Number(value.slice(0, 4)) >= 1 && /^\d{4}-\d{2}-\d{2}$/.test(value) && Number.isFinite(Date.parse(value + 'T00:00:00Z')) &&
    new Date(value + 'T00:00:00Z').toISOString().slice(0, 10) === value;
}
export function validateRows(rows: Observation[]) {
  if (!Array.isArray(rows) || rows.length < 100 || rows.length > MAX_ROWS)
    throw Error(`Use 100–${MAX_ROWS} observations per experiment.`);
  for (let i = 0; i < rows.length; i++) {
    const row = rows[i];
    if (!row || !validDate(row.date) || !Number.isFinite(row.close) || row.close <= 0)
      throw Error('Each observation needs an ISO date and a finite positive close.');
    if (i && rows[i - 1].date >= row.date) throw Error('Dates must be unique and sorted.');
  }
}
// RFC-style quoted fields, escaped quotes and CRLF; no spreadsheet formula evaluation.
export function parseCSV(text: string): Observation[] {
  if (new TextEncoder().encode(text).byteLength > 2_000_000) throw Error('CSV exceeds 2 MB.');
  const records: string[][] = []; let record: string[] = [], field = '', quoted = false, closed = false;
  const input = text.replace(/^\uFEFF/, '');
  const finishField = () => { record.push(field); field = ''; closed = false; };
  const finishRow = () => {
    finishField(); if (record.some(v => v.trim())) records.push(record); record = [];
    if (records.length > MAX_ROWS + 1) throw Error(`CSV exceeds ${MAX_ROWS} input rows.`);
  };
  for (let i = 0; i < input.length; i++) {
    const c = input[i];
    if (quoted) {
      if (c === '"') { if (input[i + 1] === '"') { field += '"'; i++; } else { quoted = false; closed = true; } }
      else field += c;
    } else if (c === ',') finishField();
    else if (c === '\r' || c === '\n') { if (c === '\r' && input[i + 1] === '\n') i++; finishRow(); }
    else if (c === '"' && !field && !closed) quoted = true;
    else { if (closed || c === '"') throw Error('Malformed quoted CSV field.'); field += c; }
  }
  if (quoted) throw Error('Unclosed CSV quote.');
  if (field || record.length || closed) finishRow();
  const headers = records.shift() || [];
  if (headers.filter(v => v === 'date').length !== 1 || headers.filter(v => v === 'close').length !== 1)
    throw Error('CSV requires unique lowercase date,close headers.');
  const di = headers.indexOf('date'), ci = headers.indexOf('close'), unique = new Map<string, number>();
  for (const row of records) {
    const date = row[di]?.trim(), value = row[ci]?.trim();
    if (!date || !validDate(date) || !value || !/^[+]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?$/i.test(value))
      throw Error('Invalid CSV date or close; previous dataset retained.');
    const close = Number(value);
    if (!Number.isFinite(close) || close <= 0) throw Error('Closes must be finite and positive.');
    unique.set(date, close); // Same last-row-wins rule as the Python importer.
  }
  const rows = [...unique].sort(([a], [b]) => a.localeCompare(b)).map(([date, close]) => ({ date, close }));
  validateRows(rows); return rows;
}
function predict(y: number[], model: string, h: number, end = y.length) {
  if (model === 'naive') return y[end - 1];
  const start = Math.max(0, end - 30), n = end - start;
  const logs = y.slice(start, end).map(Math.log), xm = (n - 1) / 2;
  const ym = logs.reduce((sum, v) => sum + v, 0) / n;
  let top = 0, bottom = 0;
  logs.forEach((v, i) => { top += (i - xm) * (v - ym); bottom += (i - xm) ** 2; });
  return Math.exp(ym + top / bottom * (n - 1 + h - xm));
}
export function futureDates(last: string, horizon: number, calendar: string): string[] {
  if (calendar === 'XNYS') throw Error('Exchange-session dates must come from the published snapshot.');
  const result: string[] = [], date = new Date(last + 'T00:00:00Z');
  while (result.length < horizon) {
    date.setUTCDate(date.getUTCDate() + 1);
    if (calendar !== 'FX_WEEKDAYS_UTC' || ![0, 6].includes(date.getUTCDay())) result.push(date.toISOString().slice(0, 10));
  }
  return result;
}
export function runBrowserExperiment(dataset: DemoDataset, model: string, horizon: number, suppliedDates?: string[]): DemoResult {
  if (!['trend', 'naive'].includes(model) || ![1, 7, 14, 30].includes(horizon)) throw Error('Unsupported model or horizon.');
  validateRows(dataset.prices);
  const rows = dataset.prices, y = rows.map(r => r.close);
  const dates = suppliedDates?.slice(0, horizon) || futureDates(rows.at(-1)!.date, horizon, dataset.calendar);
  if (dates.length !== horizon || dates.some((d, i) => !validDate(d) || d <= (i ? dates[i - 1] : rows.at(-1)!.date)))
    throw Error('Forecast calendar dates are missing or invalid. Refresh the published snapshot.');
  const start = Math.min(Math.max(60, Math.floor(y.length * 0.8)), y.length - horizon - 9);
  const errors: number[] = [], baseline: number[] = [], residuals: number[] = [];
  const backtest: DemoResult['backtest'] = [];
  for (let t = start; t <= y.length - horizon; t++) {
    const guess = predict(y, model, horizon, t), actual = y[t + horizon - 1];
    if (!Number.isFinite(guess) || guess <= 0) throw Error('This dataset produces a non-finite or nonpositive prediction.');
    errors.push(Math.abs(guess - actual)); baseline.push(Math.abs(y[t - 1] - actual)); residuals.push(actual - guess);
    backtest.push({ date: rows[t + horizon - 1].date, actual, predicted: guess });
  }
  residuals.sort((a, b) => a - b);
  const lo = residuals[Math.floor(0.1 * (residuals.length - 1))], hi = residuals[Math.floor(0.9 * (residuals.length - 1))];
  const forecast = dates.map((date, i) => {
    const predicted = predict(y, model, i + 1), lower = Math.max(0, predicted + lo), upper = predicted + hi;
    if (![predicted, lower, upper].every(Number.isFinite) || predicted <= 0) throw Error('Forecast exceeds numeric limits.');
    return { date, predicted, lower, upper };
  });
  const mean = (v: number[]) => v.reduce((a, b) => a + b, 0) / v.length;
  const { prices: _prices, ...summary } = dataset;
  const mae = mean(errors), baseline_mae = mean(baseline);
  if (![mae, baseline_mae].every(Number.isFinite)) throw Error('Evaluation exceeds numeric limits.');
  return { symbol: dataset.symbol, model, horizon, dataset_id: dataset.dataset_id, dataset: summary,
    origin: 'manual', execution: 'browser', source: dataset.source, model_version: model === 'trend' ? 'trend-v1' : 'naive-v1',
    mae, baseline_mae, samples: errors.length, train_end: rows[start - 1].date, backtest, forecast,
    band_note: 'Exploratory 10–90% historical residual band; not calibrated.',
    config: { model, horizon, window: model === 'trend' ? 30 : 1, validation: 'walk-forward',
      evaluation_start_index: start, calendar: dataset.calendar,
      calendar_library: dataset.calendar === 'XNYS' ? 'published exchange_calendars dates' : 'UTC browser date arithmetic' },
  };
}
