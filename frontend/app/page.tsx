"use client";
import { API_BASE, PUBLIC_READ_ONLY } from "./api-base";
import { useEffect, useState } from "react";
import FundamentalAnalysis from "./research-fundamentals";
import ResearchTutorial from "./research-tutorial";
import InteractiveChart from "./interactive-chart";
import MarketSync, { type DatasetAsset } from "./market-sync";
import { Button, Panel, Eyebrow, Pill, selectClass, labelClass, hintClass, tableClass } from "./ui";

type Asset = DatasetAsset & {
  symbol: string;
  name: string;
  kind: string;
  price: number;
  change: number;
  source: string;
  as_of: string;
  observations: number;
};
type Run = {
  origin: "manual" | "automatic";
  dataset_id: string | null;
  model_version: string | null;
  id: number;
  created: string;
  symbol: string;
  model: string;
  horizon: number;
  mae: number;
  baseline_mae: number;
};
type Point = { date: string; close: number };
type Result = {
  origin?: "manual" | "automatic";
  dataset_id: string;
  model_version: string;
  dataset: { calendar: string; source: string; price_basis: string };
  mae: number;
  baseline_mae: number;
  samples: number;
  train_end: string;
  band_note: string;
  forecast: { date: string; predicted: number; lower: number; upper: number }[];
  backtest: { date: string; actual: number; predicted: number }[];
};
const API = API_BASE;
const money = (v: number) => v.toLocaleString("en-US", { maximumFractionDigits: v < 10 ? 5 : 2 });
async function request(path: string, body?: object) {
  if (body && PUBLIC_READ_ONLY)
    throw Error("Demo publik read-only; backend automation memperbarui data.");
  const r = await fetch(
    API + path,
    body
      ? {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      : {},
  );
  const d = await r.json();
  if (!r.ok) throw Error(d.error || "Request failed");
  return d;
}
function AssetCard({
  asset: a,
  selected,
  disabled,
  onSelect,
}: {
  asset: Asset;
  selected: boolean;
  disabled: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      disabled={disabled}
      onClick={onSelect}
      className={`
        rounded-[9px] border p-4 text-left
        transition-[transform,background-color,border-color,box-shadow] duration-200
        cursor-pointer enabled:hover:-translate-y-[3px] enabled:hover:border-[#c6f68d]
        enabled:hover:bg-[#293a30] enabled:hover:shadow-xl focus-visible:outline-2
        focus-visible:outline-accent focus-visible:outline-offset-4 disabled:opacity-50
        disabled:cursor-not-allowed motion-reduce:transition-none motion-reduce:transform-none
        ${selected ? "border-[#a4c87c] bg-[#1d2828]" : "border-line bg-[#171f27]"}`}
    >
      <div className="flex items-center gap-2 text-xs">
        <span className="grid size-8 shrink-0 place-items-center rounded-full bg-[#303c41] text-lg text-[#d1e3c1]">
          {a.symbol === "BTCUSD" ? "₿" : a.symbol === "EURUSD" ? "€" : a.symbol[0]}
        </span>
        <span>
          {a.symbol}
          <small className="mt-1 block text-[10px] text-muted">{a.name}</small>
        </span>
        <span className="ml-auto text-[9px] text-muted max-[650px]:hidden">{a.kind}</span>
      </div>
      <div className="mt-5 mb-3 flex items-center justify-between gap-2 text-[25px] tracking-tight max-[650px]:text-xl">
        {money(a.price)}
        <span
          className={`text-[10px] tracking-normal ${a.change >= 0 ? "text-accent" : "text-[#e89292]"}`}
        >
          {a.change >= 0 ? "+" : ""}
          {a.change.toFixed(2)}%
        </span>
      </div>
      <small className="block text-[9px] text-muted">
        {a.source} · {a.as_of}
      </small>
    </button>
  );
}
function Metric({
  label,
  value,
  description,
  positive = false,
}: {
  label: string;
  value: string | number;
  description: string;
  positive?: boolean;
}) {
  return (
    <Panel>
      <span className="text-[9px] tracking-widest text-muted">{label}</span>
      <strong
        className={`mt-4 block text-[28px] font-normal ${positive ? "text-accent" : "text-ink"}`}
      >
        {value}
      </strong>
      <p className="mt-2.5 text-[10px] leading-5 text-muted">{description}</p>
    </Panel>
  );
}
export default function Page() {
  const [tab, setTab] = useState("Overview");
  const [assets, setAssets] = useState<Asset[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [symbol, setSymbol] = useState("AAPL");
  const [points, setPoints] = useState<Point[]>([]);
  const [result, setResult] = useState<Result | null>(null);
  const [model, setModel] = useState("trend");
  const [horizon, setHorizon] = useState(7);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [online, setOnline] = useState(false);
  const asset = assets.find((a) => a.symbol === symbol);
  const datasetId = asset?.dataset_id;
  const autoRunId = runs.find(
    (r) =>
      r.origin === "automatic" &&
      r.symbol === symbol &&
      r.dataset_id === datasetId &&
      r.model === model &&
      r.horizon === horizon,
  )?.id;
  async function refresh() {
    try {
      const d = await request("/api/dashboard");
      if (
        !Array.isArray(d.assets) ||
        !Array.isArray(d.runs) ||
        !d.assets.every(
          (a: DatasetAsset | null) =>
            a && typeof a.dataset_id === "string" && a.dataset_id.trim().length > 0,
        )
      ) {
        throw new Error(
          "Backend version mismatch: dataset metadata is missing. Stop the old Python server, " +
            "start the updated backend using .venv-market\\Scripts\\python.exe backend\\server.py, then refresh.",
        );
      }
      setAssets(d.assets);
      setRuns(d.runs);
      setOnline(true);
    } catch (e) {
      setOnline(false);
      throw e;
    }
  }
  useEffect(() => {
    let active = true;
    const poll = () => {
      if (active)
        refresh().catch((e) => {
          if (active) setError((e as Error).message);
        });
    };
    poll();
    const timer = setInterval(poll, 15000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);
  useEffect(() => {
    let active = true;
    setResult(null);
    setPoints([]);
    if (datasetId)
      request("/api/datasets?id=" + encodeURIComponent(datasetId))
        .then((d) => {
          if (active) setPoints(d.prices);
        })
        .catch((e) => {
          if (active) setError((e as Error).message);
        });
    return () => {
      active = false;
    };
  }, [symbol, datasetId]);
  useEffect(() => {
    let active = true;
    if (datasetId)
      request(
        `/api/forecast?symbol=${symbol}&dataset_id=${datasetId}&model=${model}&horizon=${horizon}`,
      )
        .then((d) => {
          if (active && d) setResult(d);
        })
        .catch(() => {});
    return () => {
      active = false;
    };
  }, [symbol, datasetId, model, horizon, autoRunId]);
  async function run() {
    setBusy(true);
    setError("");
    try {
      setResult(await request("/api/experiments", { symbol, model, horizon }));
      await refresh();
      setNotice("Experiment saved. Compare out-of-sample performance below.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function syncMarket() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const d = await request("/api/sync", { symbol });
      await refresh();
      setPoints(await request("/api/prices?symbol=" + symbol));
      setResult(null);
      setNotice(`${d.message}. ${d.rows} rows · dataset ${d.dataset_id.slice(0, 12)}`);
    } catch (e) {
      setError((e as Error).message);
      await refresh().catch(() => {});
    } finally {
      setBusy(false);
    }
  }
  async function replay(saved: Run) {
    if (!saved.dataset_id) return;
    setBusy(true);
    setError("");
    try {
      const d = await request("/api/experiments", {
        symbol: saved.symbol,
        model: saved.model,
        horizon: saved.horizon,
        dataset_id: saved.dataset_id,
      });
      await refresh();
      setNotice(
        `Replay saved as EXP-${d.id}. MAE ${money(d.mae)} · original ${money(saved.mae)}. Dataset ${d.dataset_id.slice(0, 12)}.`,
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function upload(file: File) {
    setBusy(true);
    setError("");
    try {
      const d = await request("/api/import", { symbol, csv: await file.text() });
      await refresh();
      setPoints(await request("/api/prices?symbol=" + symbol));
      setResult(null);
      setNotice(`${d.rows} observations imported for ${symbol}. Previous series replaced.`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div
      className="
        flex min-h-screen max-[650px]:block [&_[data-tour-active=true]]:outline-2
        [&_[data-tour-active=true]]:outline-accent
        [&_[data-tour-active=true]]:outline-offset-[5px] [&_[data-tour-active=true]]:scroll-mt-24
        [&_[data-tour-active=true]]:scroll-mb-60
      "
    >
      <aside
        className="
          fixed flex h-screen w-56 flex-col border-r border-line bg-[#11181f] px-5 py-8
          max-[1150px]:w-[185px] max-[650px]:static max-[650px]:h-auto max-[650px]:w-full
          max-[650px]:p-[17px]
        "
      >
        <a
          href="/"
          className="flex items-center gap-3 text-[35px] font-bold tracking-[-1.5px] text-accent max-[650px]:text-[26px]"
        >
          ◈{" "}
          <span className="text-white">
            signal<span className="text-accent">.</span>
          </span>
        </a>
        <div className="mx-3 mt-12 mb-[18px] text-[9px] tracking-[1.8px] text-[#73818d] max-[650px]:hidden">
          RESEARCH WORKSPACE
        </div>
        <nav
          aria-label="Workspace"
          className="max-[650px]:mt-2.5 max-[650px]:flex max-[650px]:overflow-auto"
        >
          {["Overview", "Experiments", "Fundamentals", "Data pipeline"].map((t, i) => (
            <button
              type="button"
              key={t}
              aria-current={tab === t ? "page" : undefined}
              onClick={() => setTab(t)}
              className={`
                my-1 flex w-full cursor-pointer items-center gap-3 rounded-md px-3 py-3.5
                text-left text-[13px] transition-[transform,background-color,color] duration-200
                hover:translate-x-[3px] hover:bg-[#334637] hover:text-accent
                focus-visible:outline-2 focus-visible:outline-accent
                focus-visible:outline-offset-2 motion-reduce:transition-none
                motion-reduce:transform-none max-[650px]:gap-1 max-[650px]:p-2.5
                max-[650px]:text-[10px] max-[650px]:whitespace-nowrap
                ${tab === t ? "bg-[#26332b] text-accent" : "bg-transparent text-muted"}`}
            >
              <span className="text-xl max-[650px]:text-sm">{["▦", "⌁", "▤", "⇄"][i]}</span>
              {t}
              {t === "Experiments" && <small className="ml-auto">{runs.length}</small>}
            </button>
          ))}
        </nav>
        <div className="mt-auto text-xs text-[#c0c9d0] max-[650px]:hidden">
          <span className="mr-2 inline-block size-[7px] rounded-full bg-accent" />
          Local environment
          <p className="my-3 text-[11px] text-[#75838e]">Python pipeline · SQLite</p>
          <div className="mt-6 flex gap-3 border-t border-line pt-[22px]">
            JB{" "}
            <span className="text-[11px]">
              Research workspace
              <small className="mt-1.5 block text-[#73818d]">Personal / development</small>
            </span>
          </div>
        </div>
      </aside>
      <main
        className="
          ml-56 w-[calc(100%_-_224px)] max-[1150px]:ml-[185px] max-[1150px]:w-[calc(100%_-_185px)]
          max-[650px]:m-0 max-[650px]:w-full
        "
      >
        <header
          className="
            flex h-[76px] items-center justify-between border-b border-line px-[38px] text-xs
            text-muted max-[650px]:h-14 max-[650px]:px-[18px]
          "
        >
          <span>
            Workspace <b className="mx-3.5 text-[#4c5c69]">/</b>
            {tab}
          </span>
          <div className="flex items-center gap-[22px]">
            <span
              className={`text-[11px] max-[650px]:text-[9px] ${online ? "text-[#b8e495]" : "text-[#f0b47a]"}`}
            >
              {online ? "● API connected" : "○ API offline"}
            </span>
            <span className="rounded-full border border-[#3b4751] p-2.5 text-[#d5dce2]">JB</span>
          </div>
        </header>
        <div
          className="
            mx-auto max-w-[1530px] px-[38px] pt-[35px] pb-24 min-[1600px]:pt-[50px]
            max-[1150px]:px-[22px] max-[1150px]:pt-[25px] max-[650px]:px-4
          "
        >
          <div className="mb-6 flex items-center justify-between gap-3 max-[650px]:items-start">
            <div>
              <Eyebrow>MARKET INTELLIGENCE / MODEL RESEARCH</Eyebrow>
              <h1 className="my-3 text-[32px] font-medium tracking-[-1.1px] max-[650px]:text-[26px]">
                {tab === "Overview" ? "A clearer view of what’s next." : tab}
              </h1>
              <p className={hintClass}>
                Explore market data. Test your assumptions. Measure every forecast.
              </p>
            </div>
            <Button
              onClick={() => {
                refresh()
                  .then(() => setNotice("Pipeline status refreshed."))
                  .catch((e) => setError((e as Error).message));
              }}
            >
              ↻ Refresh
            </Button>
          </div>
          {error && (
            <div
              className="mb-4 rounded-md bg-[#422d2e] px-4 py-3 text-xs text-[#ffb8b8]"
              role="alert"
            >
              {error}
            </div>
          )}
          {PUBLIC_READ_ONLY && (
            <div
              role="status"
              className="mb-4 rounded-lg border border-accent/30 bg-accent/5 p-4 text-xs leading-6 text-muted"
            >
              Demo publik read-only. Grafik, sumber, insight dan hasil tersimpan dapat dibaca.
              Sinkronisasi berjalan otomatis sesuai konfigurasi deployment; import, sync manual dan eksperimen baru
              tersedia di lingkungan admin/lokal.
            </div>
          )}
          {notice && (
            <div
              className="mb-4 rounded-md bg-[#25362b] px-4 py-3 text-xs text-[#c3e5bd]"
              role="status"
            >
              {notice}
            </div>
          )}
          <div
            data-tour="research-mode"
            className="
              mb-[23px] flex items-center gap-4 rounded-md border border-[#354138] bg-[#1d2528]
              px-4 py-3 text-[11px] leading-5 text-[#a7b3b9] max-[650px]:block
            "
          >
            <span className="shrink-0 text-[9px] tracking-widest text-[#c1e996] max-[650px]:mb-2 max-[650px]:block">
              ◎ RESEARCH MODE
            </span>
            {asset?.source === "alphavantage"
              ? "Stored API daily closes selected. Check the as-of date; backend automation checks for updates while Python is running."
              : asset?.source === "csv-import"
                ? "User-imported CSV selected. Provider, adjustment and frequency are unspecified."
                : "Synthetic examples selected. Sync AAPL/MSFT/EURUSD/BTCUSD or import CSV for real observations."}
          </div>
          {tab === "Overview" && (
            <>
              <MarketSync asset={asset} busy={busy} onSync={syncMarket} />
              <div
                data-tour="assets"
                className="mb-[23px] grid grid-cols-4 gap-3.5 max-[1150px]:grid-cols-2"
              >
                {assets.map((a) => (
                  <AssetCard
                    key={a.symbol}
                    asset={a}
                    selected={symbol === a.symbol}
                    disabled={busy}
                    onSelect={() => setSymbol(a.symbol)}
                  />
                ))}
              </div>
              <div
                className="
                  grid grid-cols-[minmax(0,1fr)_290px] gap-5
                  min-[1600px]:grid-cols-[minmax(0,1fr)_320px] max-[1150px]:grid-cols-1
                "
              >
                <Panel data-tour="chart">
                  <div className="flex items-start justify-between gap-2.5">
                    <div>
                      <h2 className="mb-2 text-[15px] font-medium">
                        {symbol} <span className="text-xs text-muted">/ Price & forecast</span>
                      </h2>
                      <p className="text-[10px] text-muted">
                        Initial view: latest observations ·{" "}
                        {symbol === "EURUSD"
                          ? "USD per EUR"
                          : symbol === "BTCUSD"
                            ? "USD per BTC"
                            : "USD quote"}
                      </p>
                    </div>
                    <Pill>{asset?.source || "Waiting"}</Pill>
                  </div>
                  <div className="mt-6 text-[29px] tracking-tight">
                    {asset ? money(asset.price) : "—"}{" "}
                    <span className="ml-2.5 text-[10px] tracking-normal text-muted max-[650px]:ml-0 max-[650px]:block">
                      As of {asset?.as_of || "—"}
                    </span>
                  </div>
                  <InteractiveChart points={points} result={result} />
                  <div className="mt-1.5 flex flex-wrap items-center justify-center gap-2 text-[9px] text-muted">
                    <span className="ml-3.5 size-1.5 rounded-full bg-accent" />
                    Historical close
                    <span className="ml-3.5 size-1.5 rounded-full bg-forecast" />
                    Model forecast
                    <span className="ml-3.5 size-[9px] bg-[#434b6d]" />
                    Residual band
                  </div>
                </Panel>
                <Panel data-tour="builder">
                  <Eyebrow>EXPERIMENT BUILDER</Eyebrow>
                  <h2 className="mt-4 mb-2 text-[22px] font-medium tracking-tight">
                    Test the next move.
                  </h2>
                  <p className="mb-[22px] text-[11px] leading-5 text-muted">
                    A reproducible starting point for your forecasting research.
                  </p>
                  <label className={labelClass}>
                    MODEL
                    <select
                      className={selectClass}
                      disabled={busy}
                      value={model}
                      onChange={(e) => {
                        setModel(e.target.value);
                        setResult(null);
                      }}
                    >
                      <option value="trend">Rolling log-linear trend</option>
                      <option value="naive">Naive / last observed price</option>
                    </select>
                  </label>
                  <label className={labelClass}>
                    FORECAST HORIZON
                    <select
                      className={selectClass}
                      disabled={busy}
                      value={horizon}
                      onChange={(e) => {
                        setHorizon(+e.target.value);
                        setResult(null);
                      }}
                    >
                      {[1, 7, 14, 30].map((n) => (
                        <option key={n} value={n}>
                          {n} observations
                        </option>
                      ))}
                    </select>
                  </label>
                  <div
                    className="
                      mt-[23px] grid grid-cols-[1fr_auto] gap-3 border-t border-line pt-5
                      text-[10px] text-muted [&_b]:font-normal [&_b]:text-[#c2ccd2]
                    "
                  >
                    <span>Validation</span>
                    <b>Walk-forward</b>
                    <span>Holdout</span>
                    <b>20% / min. 10 origins</b>
                    <span>Training window</span>
                    <b>{model === "trend" ? "30 observations" : "1 observation"}</b>
                  </div>
                  <Button
                    data-tour="run"
                    variant="primary"
                    className="group mt-6 w-full justify-between py-3"
                    disabled={PUBLIC_READ_ONLY || busy || !online || !points.length}
                    onClick={run}
                  >
                    {busy ? "Processing…" : "Run experiment"}
                    <span
                      className="
                        transition-transform group-hover:translate-x-0.5
                        group-hover:-translate-y-0.5 motion-reduce:transform-none
                        motion-reduce:transition-none
                      "
                    >
                      ↗
                    </span>
                  </Button>
                  <small className="mt-3 block text-center text-[9px] text-muted">
                    CPU only · Results saved locally
                  </small>
                </Panel>
              </div>
              <div
                data-tour="metrics"
                className="mt-5 grid grid-cols-4 gap-[15px] max-[1150px]:grid-cols-2"
              >
                <Metric
                  label="MODEL MAE"
                  value={result ? money(result.mae) : "—"}
                  description="Out-of-sample absolute error"
                />
                <Metric
                  label="BASELINE MAE"
                  value={result ? money(result.baseline_mae) : "—"}
                  description="Same horizon · last-price baseline"
                />
                <Metric
                  label="VS. BASELINE"
                  value={
                    result
                      ? result.baseline_mae
                        ? ((1 - result.mae / result.baseline_mae) * 100).toFixed(1) + "%"
                        : "N/A"
                      : "—"
                  }
                  positive={!!result && result.mae < result.baseline_mae}
                  description="Positive means lower model error"
                />
                <Metric
                  label="EVALUATION SAMPLES"
                  value={result?.samples || "—"}
                  description="Overlapping forecast windows"
                />
              </div>
              {result && (
                <p className="mt-3 text-[10px] leading-5 text-muted">
                  {result.origin === "automatic" ? "Automatic forecast" : "Manual experiment"} ·
                  Dataset {result.dataset_id.slice(0, 12)} · {result.model_version} ·{" "}
                  {result.dataset.price_basis}. {result.band_note} Imported dates retain their
                  original calendar. API equity forecasts use XNYS sessions, forex uses a weekday
                  UTC grid, and crypto includes all UTC calendar days; synthetic and CSV forecasts
                  use illustrative calendar days.
                </p>
              )}
            </>
          )}
          {tab === "Experiments" && (
            <Panel>
              <h2 className="mb-2 text-[15px] font-medium">Experiment registry</h2>
              <p className={hintClass}>
                Persisted runs · most recent 20 · use Overview to run a model
              </p>
              <div data-tour="registry" className="overflow-auto">
                <table className={tableClass}>
                  <thead>
                    <tr>
                      {[
                        "RUN",
                        "ASSET",
                        "MODEL",
                        "HORIZON",
                        "MAE",
                        "BASELINE",
                        "CREATED",
                        "DATASET",
                        "ORIGIN",
                        "REPLAY",
                      ].map((x) => (
                        <th key={x}>{x}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {runs.map((r) => (
                      <tr key={r.id}>
                        <td>EXP-{String(r.id).padStart(3, "0")}</td>
                        <td>{r.symbol}</td>
                        <td>{r.model}</td>
                        <td>{r.horizon}</td>
                        <td>{money(r.mae)}</td>
                        <td>{money(r.baseline_mae)}</td>
                        <td>{r.created.slice(0, 16).replace("T", " ")}</td>
                        <td title={r.dataset_id || "Dataset unavailable for legacy run"}>
                          {r.dataset_id?.slice(0, 12) || "Legacy / unknown"}
                          <small className="mt-1 block text-muted">
                            {r.model_version || "unversioned"}
                          </small>
                        </td>
                        <td>
                          <Pill>{r.origin || "manual"}</Pill>
                        </td>
                        <td>
                          <Button
                            compact
                            disabled={PUBLIC_READ_ONLY || busy || !r.dataset_id}
                            onClick={() => replay(r)}
                          >
                            Replay
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!runs.length && (
                  <div className="px-5 py-20 text-center text-muted">
                    No experiments yet. Run your first model in Overview.
                  </div>
                )}
              </div>
              <p className="mt-4 text-[10px] leading-5 text-muted">
                Replay uses the saved immutable dataset, model and horizon. Legacy runs predate
                dataset tracking. These baseline models are scaffolding for future ML research.
              </p>
            </Panel>
          )}
          {tab === "Fundamentals" && <FundamentalAnalysis />}
          {tab === "Data pipeline" && (
            <>
              <MarketSync asset={asset} busy={busy} onSync={syncMarket} />
              <Panel>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h2 className="mb-2 text-[15px] font-medium">
                      From observations to experiments.
                    </h2>
                    <p className={hintClass}>
                      Local, manual ingestion · validated before replacement
                    </p>
                  </div>
                  <Pill>SQLite persistence</Pill>
                </div>
                <div className="my-8 grid grid-cols-4 gap-[15px] max-[1150px]:grid-cols-2 max-[650px]:grid-cols-1">
                  {[
                    "01 / Ingest CSV",
                    "02 / Validate & deduplicate",
                    "03 / Store observations",
                    "04 / Backtest & forecast",
                  ].map((s) => (
                    <div
                      key={s}
                      className="rounded-md border border-[#3a4d3d] bg-[#25312d] p-[18px] text-[11px]"
                    >
                      {s}
                      <small className="mt-[15px] block text-[9px] text-[#9dc380]">
                        Implemented
                      </small>
                    </div>
                  ))}
                </div>
                <label className={labelClass}>
                  DESTINATION ASSET
                  <select
                    className={selectClass}
                    disabled={busy}
                    value={symbol}
                    onChange={(e) => setSymbol(e.target.value)}
                  >
                    {["AAPL", "MSFT", "EURUSD", "BTCUSD"].map((s) => (
                      <option key={s}>{s}</option>
                    ))}
                  </select>
                </label>
                <label
                  data-tour="import"
                  className="
                    my-[18px] flex flex-col items-center gap-3.5 rounded-lg border border-dashed
                    border-[#52684a] p-[35px] text-sm text-accent
                  "
                >
                  ↑ <b>Import a price series for {symbol}</b>
                  <span className="text-center text-[11px] text-muted">
                    CSV with date,close · at least 100 unique dates · max 2 MB
                  </span>
                  <input
                    className="
                      max-w-full text-xs text-[#b9c7ce] file:mr-3 file:cursor-pointer file:rounded
                      file:border file:border-line file:bg-elevated file:px-3 file:py-2
                      file:text-ink focus-visible:outline-2 focus-visible:outline-accent
                    "
                    aria-label="Import CSV"
                    disabled={PUBLIC_READ_ONLY || busy}
                    type="file"
                    accept=".csv,text/csv"
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (f) upload(f);
                      e.target.value = "";
                    }}
                  />
                </label>
                <p className="text-[10px] leading-5 text-muted">
                  Import replaces the selected asset’s entire series after validation. Use ISO dates
                  (YYYY-MM-DD), positive closes, and a consistent observation frequency.
                  AAPL/MSFT/EURUSD/BTCUSD support API sync and backend automation. Report scraping
                  remains planned.
                </p>
              </Panel>
              <Panel className="mt-5">
                <h2 className="text-[15px] font-medium">Dataset inventory</h2>
                <div className="overflow-auto">
                  <table className={tableClass}>
                    <thead>
                      <tr>
                        <th>ASSET</th>
                        <th>SOURCE</th>
                        <th>ROWS</th>
                        <th>AS OF</th>
                      </tr>
                    </thead>
                    <tbody>
                      {assets.map((a) => (
                        <tr key={a.symbol}>
                          <td>{a.symbol}</td>
                          <td>{a.source}</td>
                          <td>{a.observations}</td>
                          <td>{a.as_of}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Panel>
            </>
          )}
          <ResearchTutorial onNavigate={setTab} />
          <footer
            className="
              mt-[30px] flex justify-between gap-5 border-t border-line pt-5 text-[9px] leading-5
              tracking-wide text-[#637481]
            "
          >
            <span>◈ SIGNAL RESEARCH LAB</span>
            <span>Local MVP · Experimental forecasts · No trading execution</span>
          </footer>
        </div>
      </main>
    </div>
  );
}
