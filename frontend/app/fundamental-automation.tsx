"use client";

import { useEffect, useState } from "react";
import { Pill } from "./ui";

type Status = {
  enabled: boolean;
  worker_running: boolean;
  next_check: string | null;
  last_error: string | null;
  states: { symbol: string; status: string; message: string; next_attempt: string | null }[];
};
const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export default function FundamentalAutomation({ symbol }: { symbol: string }) {
  const [status, setStatus] = useState<Status | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    async function poll() {
      try {
        const response = await fetch(`${API}/api/fundamentals/automation`, { cache: "no-store" });
        if (!response.ok)
          throw new Error("Fundamental scheduler unavailable. Restart the updated backend.");
        const result = await response.json();
        if (!Array.isArray(result.states))
          throw new Error("Fundamental scheduler response is invalid.");
        if (active) {
          setStatus(result);
          setError("");
        }
      } catch (e) {
        if (active)
          setError(e instanceof Error ? e.message : "Could not load Fundamental scheduler");
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
      aria-label="Fundamental evidence automation"
      className="mt-5 rounded-lg border border-line bg-canvas p-4"
    >
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="mr-auto text-sm font-medium">Fundamental evidence automation</h3>
        <Pill>{status?.worker_running ? "Worker running" : "Worker stopped"}</Pill>
        <Pill>Reports {status?.enabled ? "ON" : "OFF"}</Pill>
      </div>
      {error && (
        <p role="status" className="mt-3 text-xs text-orange-200">
          {error}
        </p>
      )}
      {state && (
        <>
          <p className="mt-3 text-xs leading-6 text-muted">
            <span className="text-accent">{state.status.replaceAll("_", " ")}</span> ·{" "}
            {state.message}
          </p>
          <p className="mt-2 text-xs text-muted">
            Next permitted evidence check:{" "}
            {state.next_attempt
              ? new Date(state.next_attempt).toLocaleString()
              : "Next worker cycle"}
          </p>
        </>
      )}
      {status?.last_error && <p className="mt-2 text-xs text-orange-200">{status.last_error}</p>}
      <p className="mt-3 text-xs leading-6 text-muted">
        Independent of the price worker. Six-hour cache · 30-minute retries · up to six automatic
        attempts per asset per UTC day. Configure AUTO_FUNDAMENTALS_ENABLED in backend/.env and
        restart. Keep the backend running; browser polling only reads local data.
      </p>
    </section>
  );
}
