"use client";
import { API_BASE } from "./api-base";
import { useEffect, useState } from "react";
import FundamentalAutomation from "./fundamental-automation";
import { Pill } from "./ui";
type State = {
  symbol: string;
  target_session: string | null;
  sync_status: string;
  sync_message: string;
  sync_retry_at: string | null;
  forecast_status: string;
  forecast_message: string;
  forecast_id: number | null;
};
type Status = {
  sync_enabled: boolean;
  forecast_enabled: boolean;
  worker_running: boolean;
  next_check: string | null;
  next_market_release: string | null;
  next_market_releases?: Record<string, string | null>;
  last_error: string | null;
  states: State[];
};
const API = API_BASE;
const date = (value: string | null) => (value ? new Date(value).toLocaleString() : "—");
export default function AutomationStatus({ symbol }: { symbol: string }) {
  const [status, setStatus] = useState<Status | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    async function poll() {
      try {
        const response = await fetch(API + "/api/automation");
        if (!response.ok) throw Error("Scheduler unavailable. Restart the updated backend.");
        const data = await response.json();
        if (active) {
          setStatus(data);
          setError("");
        }
      } catch (e) {
        if (active) setError((e as Error).message);
      }
    }
    poll();
    const timer = setInterval(poll, 15000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);
  const state = status?.states.find((s) => s.symbol === symbol);
  return (
    <section
      className="mt-5 rounded-lg border border-line bg-canvas p-4"
      aria-label="Backend automation"
    >
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="mr-auto text-sm font-medium">Backend automation</h3>
        <Pill>{status?.worker_running ? "Worker running" : "Worker stopped"}</Pill>
        <Pill>Sync {status?.sync_enabled ? "ON" : "OFF"}</Pill>
        <Pill>Forecast {status?.forecast_enabled ? "ON" : "OFF"}</Pill>
      </div>
      {error && (
        <p role="status" className="mt-2 text-xs text-[#f0b47a]">
          {error}
        </p>
      )}
      {status && (
        <>
          <dl className="mt-3 grid grid-cols-2 gap-3 text-[11px] max-[650px]:grid-cols-1">
            <div>
              <dt className="text-muted">Next local check</dt>
              <dd className="mt-1">{date(status.next_check)}</dd>
            </div>
            <div>
              <dt className="text-muted">Next daily-data eligibility</dt>
              <dd className="mt-1">
                {date(status.next_market_releases?.[symbol] ?? status.next_market_release)}
              </dd>
            </div>
          </dl>
          {state && (
            <div className="mt-3 space-y-2 text-xs leading-6">
              <p>
                <span className="text-accent">{state.sync_status?.replaceAll("_", " ")}</span> ·{" "}
                {state.sync_message}
              </p>
              {state.sync_retry_at && (
                <p className="text-muted">Next permitted attempt: {date(state.sync_retry_at)}</p>
              )}
              <p>
                <span className="text-forecast">
                  Forecast {state.forecast_status?.replaceAll("_", " ")}
                </span>{" "}
                · {state.forecast_message}
                {state.forecast_id ? ` · EXP-${state.forecast_id}` : ""}
              </p>
            </div>
          )}
          {status.last_error && <p className="mt-2 text-xs text-[#f0b47a]">{status.last_error}</p>}
        </>
      )}
      {["AAPL", "MSFT", "EURUSD", "BTCUSD"].includes(symbol) && (
        <FundamentalAutomation symbol={symbol} />
      )}
      <p className="mt-3 text-[11px] leading-6 text-muted">
        Requires the Python backend to stay running. Browser polling reads local status only; it
        does not consume provider requests. Times use your browser timezone.
      </p>
    </section>
  );
}
