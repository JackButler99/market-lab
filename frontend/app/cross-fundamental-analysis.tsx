"use client";
import { API_BASE, PUBLIC_READ_ONLY } from "./api-base";
import { useEffect, useState } from "react";
import FundamentalInsights from "./fundamental-insights";
import { MetricHelp } from "./fundamental-glossary";
import FundamentalAutomation from "./fundamental-automation";
import { Button, Eyebrow, Panel, Pill, tableClass } from "./ui";

type Observation = { date: string; value: number };
type Metric = {
  label: string;
  value: number | null;
  unit: string;
  observation_date: string | null;
  source: string;
  series_id: string;
  url: string;
  stale: boolean;
  issue: string | null;
  history: Observation[];
  formula?: string;
  change_7d_pct?: number | null;
};
type Payload = {
  has_data: boolean;
  cached?: boolean;
  fetched_at: string | null;
  snapshot_id: string | null;
  analysis: null | { title: string; metrics: Record<string, Metric>; limitations: string[] };
  last_job?: { status: string; message: string } | null;
};
const API = API_BASE;
function number(value: number | null) {
  return value == null
    ? "Unavailable"
    : new Intl.NumberFormat("en-US", {
        maximumFractionDigits: 3,
        notation: Math.abs(value) >= 1e6 ? "compact" : "standard",
      }).format(value);
}
async function request(symbol: string, sync = false): Promise<Payload> {
  const response = await fetch(
    `${API}/api/fundamentals${sync ? "/sync" : `?symbol=${symbol}`}`,
    sync
      ? {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ symbol }),
        }
      : { cache: "no-store" },
  );
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "Could not load fundamentals");
  if (typeof result.has_data !== "boolean" || result.supported !== true)
    throw new Error("Restart the updated backend: this fundamental connector is unavailable.");
  return result;
}
export default function CrossFundamentalAnalysis({ symbol }: { symbol: "EURUSD" | "BTCUSD" }) {
  const [data, setData] = useState<Payload | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  useEffect(() => {
    let active = true;
    async function load(first = false) {
      try {
        const result = await request(symbol);
        if (active) {
          setData(result);
          if (first) setError("");
        }
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : "Could not load data");
      } finally {
        if (active) setLoading(false);
      }
    }
    load(true);
    const timer = setInterval(() => {
      if (!busy) load();
    }, 15000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [symbol, busy]);
  async function sync() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await request(symbol, true);
      setData(result);
      setNotice(
        result.cached
          ? "Six-hour cache is valid. No provider request was sent."
          : "Fundamental evidence updated.",
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sync failed");
    } finally {
      setBusy(false);
    }
  }
  const analysis = data?.analysis;
  return (
    <div className="space-y-5">
      <FundamentalAutomation symbol={symbol} />
      <Panel>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <Eyebrow>
              {symbol === "EURUSD" ? "FOREX / MACROECONOMIC CONTEXT" : "BITCOIN / NETWORK EVIDENCE"}
            </Eyebrow>
            <h2 className="mt-3 text-xl">
              {symbol === "EURUSD"
                ? "Rates, inflation and source dates."
                : "Observe the network behind BTC."}
            </h2>
            <p className="mt-3 max-w-3xl text-xs leading-6 text-muted">
              {symbol === "EURUSD"
                ? "Federal Reserve and BLS observations via FRED, Eurostat HICP via FRED, and ECB deposit facility data. Provider credentials are configured by the administrator."
                : "Hash rate, mining difficulty, confirmed transactions and issued supply from Blockchain.com. No API key is required by this connector. Current incomplete UTC day is excluded."}
            </p>
          </div>
          <Pill>{data?.has_data ? "Evidence stored" : "Not synced"}</Pill>
        </div>
        <Button className="mt-5" disabled={PUBLIC_READ_ONLY || busy || loading} onClick={sync}>
          {PUBLIC_READ_ONLY
            ? "Auto-update / read-only demo"
            : busy
              ? "Fetching evidence…"
              : "Sync fundamentals"}
        </Button>
        <p className="mt-3 text-xs leading-6 text-muted">
          {PUBLIC_READ_ONLY
            ? "Scheduled updates are managed by the administrator. Observation dates show provider freshness; publication time can differ."
            : "Six-hour cache · shared 45-second sync cooldown · automatic refresh while the Python backend runs."}
          {" "}This is research context; it does not change the forecasting model.
        </p>
        {loading && (
          <p role="status" className="mt-4 text-xs text-muted">
            Loading stored evidence…
          </p>
        )}
        {error && (
          <p role="alert" className="mt-4 rounded bg-red-400/10 p-3 text-xs text-red-200">
            {error}
          </p>
        )}
        {notice && (
          <p role="status" className="mt-4 text-xs text-accent">
            {notice}
          </p>
        )}
        {!loading && !data?.has_data && (
          <p className="mt-4 text-xs text-muted">
            {PUBLIC_READ_ONLY ? "No published observations yet. The administrator should check the latest refresh workflow and provider diagnostics." : "No observations stored yet. Sync now or wait for the configured worker."}
          </p>
        )}
        {data?.last_job?.status === "failed" && (
          <p className="mt-4 text-xs text-orange-200">
            Last sync failed; any analysis below is the last successful snapshot. {data?.last_job?.message}
          </p>
        )}
      </Panel>
      <FundamentalInsights symbol={symbol} snapshotId={data?.snapshot_id} />
      {analysis && (
        <>
          <Panel>
            <h2 className="text-lg">{analysis.title}</h2>
            <p className="mt-3 break-all text-xs leading-6 text-muted">
              Fetched {data?.fetched_at ? new Date(data.fetched_at).toLocaleString() : "—"}
              <br />
              Snapshot {data?.snapshot_id}
            </p>
            <div className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {Object.entries(analysis.metrics).map(([key, m]) => (
                <article key={key} className="rounded-lg border border-line bg-elevated p-4">
                  <div className="flex justify-between gap-3">
                    <h3 className="text-xs leading-5 text-muted">{m.label}</h3>
                    {m.stale && <Pill>Stale</Pill>}
                  </div>
                  <strong className="mt-3 block text-2xl font-medium">{number(m.value)}</strong>
                  <MetricHelp metric={key} />
                  <p className="mt-1 text-xs text-muted">{m.unit}</p>
                  <p className="mt-3 text-xs text-muted">
                    Observation: {m.observation_date || "Unavailable"}
                  </p>
                  {m.change_7d_pct != null && (
                    <p className="mt-2 text-xs text-accent">
                      7-day change {m.change_7d_pct.toFixed(2)}%
                    </p>
                  )}
                  {m.issue && <p className="mt-2 text-xs text-orange-200">{m.issue}</p>}
                  <a
                    className="mt-3 inline-block text-xs text-accent hover:underline"
                    href={m.url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {m.source} ↗
                  </a>
                </article>
              ))}
            </div>
          </Panel>
          <Panel>
            <h2 className="text-base">Source evidence and observations</h2>
            <p className="mt-2 text-xs leading-6 text-muted">
              Observation dates describe the measured period, not when the information first became
              public. Fetch time is when this app received the data.
            </p>
            <div className="mt-4 space-y-3">
              {Object.entries(analysis.metrics).map(([key, m]) => (
                <details key={key} className="rounded border border-line p-4">
                  <summary className="cursor-pointer text-sm text-accent">{m.label}</summary>
                  <p className="mt-3 break-all text-xs leading-6 text-muted">
                    Series {m.series_id} · {m.source}
                    {m.formula && (
                      <>
                        <br />
                        Formula: {m.formula}
                      </>
                    )}
                  </p>
                  {m.history.length > 0 ? (
                    <div className="overflow-x-auto">
                      <table className={tableClass}>
                        <thead>
                          <tr>
                            <th>Observation date</th>
                            <th>Value</th>
                            <th>Unit</th>
                          </tr>
                        </thead>
                        <tbody>
                          {m.history
                            .slice(-15)
                            .reverse()
                            .map((p) => (
                              <tr key={p.date}>
                                <td>{p.date}</td>
                                <td>
                                  {p.value.toLocaleString("en-US", { maximumFractionDigits: 8 })}
                                </td>
                                <td>{m.unit}</td>
                              </tr>
                            ))}
                        </tbody>
                      </table>
                      <p className="mt-2 text-xs text-muted">
                        Latest 15 observations shown; {m.history.length} stored in this snapshot.
                      </p>
                    </div>
                  ) : (
                    <p className="mt-3 text-xs text-muted">
                      Derived from the cited source metrics; no standalone history.
                    </p>
                  )}
                </details>
              ))}
            </div>
          </Panel>
          <Panel>
            <h2 className="text-base">Research boundaries</h2>
            <ul className="mt-4 list-disc space-y-3 pl-5 text-xs leading-6 text-muted">
              {analysis.limitations.map((x) => (
                <li key={x}>{x}</li>
              ))}
            </ul>
          </Panel>
        </>
      )}
    </div>
  );
}
