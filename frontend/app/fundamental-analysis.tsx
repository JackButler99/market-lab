"use client";
import { API_BASE, PUBLIC_READ_ONLY } from "./api-base";

import FundamentalInsights from "./fundamental-insights";
import { MetricHelp } from "./fundamental-glossary";
import FundamentalAutomation from "./fundamental-automation";
import { useEffect, useState } from "react";
import { Button, Panel, Eyebrow, Pill, selectClass, tableClass } from "./ui";

type Metric = {
  value: number | null;
  unit: string;
  issue: string | null;
  evidence: null | {
    tag: string;
    start: string | null;
    end: string;
    filed: string;
    accn: string;
    url: string;
  };
};
type Year = {
  start: string;
  end: string;
  metrics: Record<string, Metric>;
  derived: Record<string, number | null>;
};
type Filing = { form: string; filed: string; accn: string; url: string };
type Payload = {
  has_data: boolean;
  snapshot_id?: string;
  fetched_at?: string;
  cached?: boolean;
  analysis?: {
    company: string;
    source: string;
    annual_filing: Filing;
    years: Year[];
    reports: Filing[];
    limitations: string[];
    formulas: Record<string, string>;
  };
};
const API = API_BASE;
const labels: Record<string, string> = {
  revenue: "Revenue",
  net_income: "Net income",
  operating_income: "Operating income",
  operating_cash_flow: "Operating cash flow",
  capex: "Capital expenditure",
  cash: "Cash & cash equivalents",
  assets: "Total assets",
  liabilities: "Total liabilities",
  equity: "Stockholders’ equity",
  diluted_eps: "Diluted EPS",
  free_cash_flow: "Free cash flow",
  net_margin: "Net margin",
  operating_margin: "Operating margin",
  revenue_yoy: "Revenue growth YoY",
};
function format(value: number | null | undefined, key: string) {
  if (value == null) return "Unavailable";
  if (["net_margin", "operating_margin", "revenue_yoy"].includes(key))
    return `${value.toFixed(2)}%`;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    notation: key === "diluted_eps" ? "standard" : "compact",
    maximumFractionDigits: 2,
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
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Fundamentals request failed");
  if (typeof data.has_data !== "boolean")
    throw new Error("Restart the updated Python backend: fundamentals endpoint unavailable.");
  return data;
}
export default function FundamentalAnalysis() {
  const [symbol, setSymbol] = useState("AAPL");
  const [data, setData] = useState<Payload | null>(null);
  const [period, setPeriod] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  useEffect(() => {
    let active = true;
    setData(null);
    setPeriod("");
    setError("");
    setNotice("");
    setLoading(true);
    request(symbol)
      .then((d) => {
        if (active) setData(d);
      })
      .catch((e) => {
        if (active) setError(e.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [symbol]);
  useEffect(() => {
    let active = true;
    const timer = setInterval(() => {
      if (busy) return;
      request(symbol)
        .then((result) => {
          if (active) setData(result);
        })
        .catch(() => {});
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
          ? "Using stored SEC data: six-hour cache is still valid."
          : "SEC reports synced. Annual metrics and source evidence updated.",
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "SEC sync failed");
    } finally {
      setBusy(false);
    }
  }
  const analysis = data?.analysis;
  const year = analysis?.years.find((y) => y.end === period) || analysis?.years[0];
  return (
    <div data-tour="fundamentals" className="space-y-5">
      <FundamentalAutomation symbol={symbol} />
      <Panel>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <Eyebrow>OFFICIAL FILINGS / EQUITY RESEARCH</Eyebrow>
            <h2 className="mt-3 text-xl">Evidence before interpretation.</h2>
            <p className="mt-2 text-xs leading-6 text-muted">
              Annual SEC fundamentals for AAPL and MSFT. Use the Macro and Network tabs for EURUSD
              and BTCUSD.
            </p>
          </div>
          <Pill>{data?.has_data ? "SEC data stored" : "Not synced"}</Pill>
        </div>
        <div className="mt-5 flex flex-wrap items-end gap-4">
          <label className="text-xs text-muted">
            Company
            <select
              aria-label="Fundamental company"
              className={selectClass}
              value={symbol}
              disabled={busy}
              onChange={(e) => setSymbol(e.target.value)}
            >
              <option>AAPL</option>
              <option>MSFT</option>
            </select>
          </label>
          <Button onClick={sync} disabled={PUBLIC_READ_ONLY || busy || loading}>
            {PUBLIC_READ_ONLY
              ? "Auto-update / read-only demo"
              : busy
                ? "Fetching SEC reports…"
                : "Sync SEC reports"}
          </Button>
        </div>
        <p className="mt-4 text-xs leading-6 text-muted">
          Requires SEC_USER_AGENT in backend/.env. Sync checks SEC at most once every six hours per
          company. The independent SEC worker refreshes expired reports when configured.
        </p>
        {loading && (
          <p className="mt-4 text-xs text-muted" role="status">
            Loading stored fundamentals…
          </p>
        )}
        {error && (
          <p
            role="alert"
            className="mt-4 rounded border border-red-400/30 bg-red-400/10 p-3 text-xs text-red-200"
          >
            {error}
          </p>
        )}
        {notice && (
          <p role="status" className="mt-4 text-xs text-accent">
            {notice}
          </p>
        )}
        {!loading && !data?.has_data && (
          <p className="mt-5 text-sm text-muted">
            No official data stored yet. Configure your SEC contact, then sync reports.
          </p>
        )}
      </Panel>
      <FundamentalInsights symbol={symbol} snapshotId={data?.snapshot_id} period={year?.end} />
      {analysis && year && (
        <>
          <Panel>
            <div className="flex flex-wrap justify-between gap-4">
              <div>
                <h2 className="text-lg">{analysis.company}</h2>
                <p className="mt-2 text-xs text-muted">
                  {analysis.source} · {analysis.annual_filing.form} filed{" "}
                  {analysis.annual_filing.filed}
                </p>
                <a
                  className="mt-2 inline-block text-xs text-accent hover:underline"
                  href={analysis.annual_filing.url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open annual filing ↗
                </a>
              </div>
              <label className="text-xs text-muted">
                Annual period ending
                <select
                  className={selectClass}
                  value={year.end}
                  onChange={(e) => setPeriod(e.target.value)}
                >
                  {analysis.years.map((y) => (
                    <option key={y.end}>{y.end}</option>
                  ))}
                </select>
              </label>
            </div>
            <p className="mt-4 break-all text-xs leading-6 text-muted">
              Period {year.start} — {year.end} · Fetched{" "}
              {data?.fetched_at ? new Date(data.fetched_at).toLocaleString() : "—"}
              <br />
              Snapshot {data?.snapshot_id}
            </p>
            <div className="mt-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
              {[
                "revenue",
                "net_income",
                "operating_cash_flow",
                "free_cash_flow",
                "net_margin",
                "operating_margin",
                "revenue_yoy",
                "diluted_eps",
              ].map((key) => (
                <article key={key} className="rounded-lg border border-line bg-elevated p-4">
                  <p className="text-xs text-muted">{labels[key]}</p>
                  <strong className="mt-3 block text-xl font-medium">
                    {format(
                      key in year.derived ? year.derived[key] : year.metrics[key]?.value,
                      key,
                    )}
                  </strong>
                  <MetricHelp metric={key} />
                </article>
              ))}
            </div>
          </Panel>
          <Panel>
            <h2 className="text-base">Annual comparison</h2>
            <p className="mt-2 text-xs text-muted">
              Up to three comparative periods from the same annual filing. Missing facts stay
              unavailable.
            </p>
            <div className="overflow-x-auto">
              <table className={tableClass}>
                <thead>
                  <tr>
                    <th>Metric</th>
                    {analysis.years.map((y) => (
                      <th key={y.end}>{y.end}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {Object.keys(labels).map((key) => (
                    <tr key={key}>
                      <td>{labels[key]}</td>
                      {analysis.years.map((y) => (
                        <td key={y.end}>
                          {format(key in y.derived ? y.derived[key] : y.metrics[key]?.value, key)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
          <Panel>
            <details>
              <summary className="cursor-pointer text-sm text-accent">
                Inspect source evidence · {year.end}
              </summary>
              <div className="overflow-x-auto">
                <table className={tableClass}>
                  <thead>
                    <tr>
                      <th>Metric</th>
                      <th>Value / unit</th>
                      <th>Tag / period</th>
                      <th>Filing evidence</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(year.metrics).map(([key, metric]) => (
                      <tr key={key}>
                        <td>{labels[key]}</td>
                        <td>
                          {metric.value?.toLocaleString("en-US") ?? "Unavailable"} {metric.unit}
                        </td>
                        <td>
                          {metric.evidence ? (
                            <>
                              {metric.evidence.tag}
                              <br />
                              {metric.evidence.start || "Instant"} — {metric.evidence.end}
                            </>
                          ) : (
                            metric.issue
                          )}
                        </td>
                        <td>
                          {metric.evidence && (
                            <a
                              className="text-accent hover:underline"
                              href={metric.evidence.url}
                              target="_blank"
                              rel="noreferrer"
                            >
                              {metric.evidence.accn}
                              <br />
                              Filed {metric.evidence.filed} ↗
                            </a>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
            <div className="mt-5 space-y-2 text-xs text-muted">
              {Object.entries(analysis.formulas).map(([key, formula]) => (
                <p key={key}>
                  {labels[key]} = {formula}
                </p>
              ))}
            </div>
          </Panel>
          <div className="grid gap-5 lg:grid-cols-2">
            <Panel>
              <h2 className="text-base">Recent official reports</h2>
              <ul className="mt-4 space-y-3">
                {analysis.reports.map((r) => (
                  <li key={r.accn}>
                    <a
                      className="text-xs text-accent hover:underline"
                      href={r.url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {r.form} · {r.filed} · {r.accn} ↗
                    </a>
                  </li>
                ))}
              </ul>
            </Panel>
            <Panel>
              <h2 className="text-base">Research boundaries</h2>
              <ul className="mt-4 list-disc space-y-3 pl-4 text-xs leading-6 text-muted">
                {analysis.limitations.map((x) => (
                  <li key={x}>{x}</li>
                ))}
              </ul>
            </Panel>
          </div>
        </>
      )}
    </div>
  );
}
