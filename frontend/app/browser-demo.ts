import { DemoDataset, DemoResult, parseCSV, runBrowserExperiment, validateRows } from './browser-experiments';
const KEY = 'signal-browser-demo-v1';
const SYMBOLS = ['AAPL', 'MSFT', 'EURUSD', 'BTCUSD'];
type State = { version: 1; current: Record<string, string>; datasets: Record<string, DemoDataset>; runs: DemoResult[] };
const empty = (): State => ({ version: 1, current: {}, datasets: {}, runs: [] });
function load(): State {
  if (typeof window === 'undefined') return empty();
  const raw = localStorage.getItem(KEY);
  if (!raw) return empty();
  try {
    const state = JSON.parse(raw) as State;
    if (state.version !== 1 || !Array.isArray(state.runs) || !state.datasets || !state.current) throw Error();
    // Storage is untrusted: ignore corrupted state, never execute stored text.
    for (const [id, ds] of Object.entries(state.datasets)) {
      if (!ds || ds.dataset_id !== id || !SYMBOLS.includes(ds.symbol)) throw Error();
      validateRows(ds.prices);
    }
    if (state.runs.length > 20 || Object.keys(state.datasets).length > 24) throw Error();
    for (const run of state.runs) {
      if (!run || !state.datasets[run.dataset_id] || !Number.isFinite(run.mae) || !Number.isFinite(run.baseline_mae)) throw Error();
    }
    return state;
  } catch { throw Error('Saved demo data is invalid. Use “Clear browser demo data” to reset it.'); }
}
function save(state: State) {
  state.runs = state.runs.slice(0, 20);
  const used = new Set([...Object.values(state.current), ...state.runs.map(r => r.dataset_id)]);
  for (const id of Object.keys(state.datasets)) if (!used.has(id)) delete state.datasets[id];
  try { localStorage.setItem(KEY, JSON.stringify(state)); }
  catch { throw Error('Browser storage unavailable or full. No changes saved; clear old demo data or enable site storage.'); }
}
async function published(path: string) {
  const response = await fetch(path, { cache: 'no-store' }), data = await response.json();
  if (!response.ok) throw Error(data.error || 'Published snapshot unavailable.');
  return data;
}
function summary(ds: DemoDataset) { const { prices: _prices, ...detail } = ds; return detail; }
async function dataset(state: State, id: string): Promise<DemoDataset> {
  return state.datasets[id] || await published('/api/datasets?id=' + encodeURIComponent(id));
}
function localAsset(ds: DemoDataset) {
  const last = ds.prices.at(-1)!, prior = ds.prices.at(-2)!;
  return { ...summary(ds), name: ds.symbol + ' · private CSV', kind: 'Browser dataset', as_of: last.date,
    price: last.close, change: (last.close / prior.close - 1) * 100, fetched_at: null, last_sync: null };
}
export async function browserDemoRequest(path: string, body?: Record<string, unknown>): Promise<any> {
  // This facade is client-only. Mutations below never issue HTTP POST requests.
  if (typeof window === 'undefined') throw Error('Browser demo requires a browser.');
  const url = new URL(path, window.location.origin), route = url.pathname;
  if (route === '/api/demo/clear' && body) { localStorage.removeItem(KEY); return { cleared: true }; }
  let state = load();
  if (body) {
    const symbol = String(body.symbol || '');
    if (!SYMBOLS.includes(symbol)) throw Error('Unsupported asset.');
    if (route === '/api/demo/restore') { delete state.current[symbol]; save(state); return { restored: true }; }
    if (route === '/api/import') {
      const prices = parseCSV(String(body.csv || '')), created = new Date().toISOString();
      const bytes = new TextEncoder().encode(JSON.stringify({ symbol, prices, source: 'browser-csv-v1' }));
      const hash = await crypto.subtle.digest('SHA-256', bytes);
      const id = 'browser-' + [...new Uint8Array(hash)].map(b => b.toString(16).padStart(2, '0')).join('');
      const ds: DemoDataset = { dataset_id: id, symbol, created, source: 'csv-import', provider: 'user/browser',
        calendar: 'calendar-days', price_basis: 'unspecified', currency: 'USD (assumed for imported CSV)',
        frequency: 'observations-unspecified', prices, observations: prices.length,
        start_date: prices[0].date, end_date: prices.at(-1)!.date };
      state.datasets[id] = ds; state.current[symbol] = id; save(state);
      return { rows: prices.length, dataset_id: id };
    }
    if (route === '/api/experiments') {
      let id = String(body.dataset_id || state.current[symbol] || '');
      if (!id) { const dashboard = await published('/api/dashboard'); id = dashboard.assets.find((a: {symbol:string}) => a.symbol === symbol)?.dataset_id; }
      if (!id) throw Error('Select an available published dataset or import a CSV first.');
      const ds = await dataset(state, id);
      if (ds.symbol !== symbol) throw Error('Dataset does not belong to this asset.');
      let dates: string[] | undefined;
      if (ds.calendar === 'XNYS' && ds.forecast_dates?.length === 30) dates = ds.forecast_dates;
      else if (ds.calendar === 'XNYS') {
        const saved = await published(`/api/forecast?symbol=${symbol}&dataset_id=${encodeURIComponent(id)}&model=naive&horizon=30`);
        dates = saved?.forecast?.map((v: {date:string}) => v.date);
        if (!dates) throw Error('Published exchange calendar missing. Refresh snapshot or import CSV.');
        ds.forecast_dates = dates;
      }
      await new Promise(resolve => setTimeout(resolve, 0));
      const result = runBrowserExperiment(ds, String(body.model), Number(body.horizon), dates);
      // Reload before saving so another completed action in this tab is not overwritten.
      const latest = load();
      result.id = -Math.max(Date.now(), ...latest.runs.map(r => Math.abs(r.id || 0) + 1));
      result.created = new Date().toISOString();
      latest.datasets[id] = ds; latest.runs.unshift(result); save(latest);
      return result;
    }
    throw Error('Provider sync is administrator-managed. Visitor experiments run on this device.');
  }
  if (route === '/api/dashboard') {
    let remote: any;
    try { remote = await published(path); }
    catch (error) { if (!Object.keys(state.current).length) throw error; remote = { assets: [], runs: [], pipeline: {} }; }
    state = load();
    const assets = remote.assets.filter((a: {symbol:string}) => !state.current[a.symbol]);
    for (const [symbol, id] of Object.entries(state.current)) {
      if (state.datasets[id]?.symbol === symbol) assets.push(localAsset(state.datasets[id]));
    }
    return { ...remote, assets, runs: [...state.runs, ...remote.runs], pipeline: { ...remote.pipeline, visitor_storage: 'This browser only' } };
  }
  const symbol = url.searchParams.get('symbol') || 'AAPL';
  if (route === '/api/prices' && state.current[symbol]) return state.datasets[state.current[symbol]].prices;
  if (route === '/api/datasets') {
    const id = url.searchParams.get('id');
    if (id && state.datasets[id]) return state.datasets[id];
    if (!id && state.current[symbol]) return [summary(state.datasets[state.current[symbol]])];
  }
  if (route === '/api/forecast') {
    const id = url.searchParams.get('dataset_id');
    const match = (s: State) => s.runs.find(r => r.dataset_id === id && r.symbol === symbol && r.model === url.searchParams.get('model') && r.horizon === Number(url.searchParams.get('horizon')));
    const local = match(state); if (local) return local;
    if (id?.startsWith('browser-')) return null;
    const remote = await published(path);
    return match(load()) || remote;
  }
  return published(path);
}
