"use client";
import { useEffect, useRef, useState } from "react";
import { Button } from "./ui";
type Price = { date: string; close: number };
type Forecast = { date: string; predicted: number; lower: number; upper: number };
type Row = { date: string; actual?: number; predicted?: number; lower?: number; upper?: number };
const fmt = (v: number) => v.toLocaleString("en-US", { maximumFractionDigits: v < 10 ? 5 : 2 });
export default function InteractiveChart({
  points,
  result,
}: {
  points: Price[];
  result: { forecast: Forecast[] } | null;
}) {
  const rows: Row[] = [
    ...points.map((p) => ({ date: p.date, actual: p.close })),
    ...(result?.forecast || []),
  ];
  const n = rows.length;
  const [view, setView] = useState({ start: Math.max(0, n - 100), size: Math.min(100, n) });
  const [hover, setHover] = useState<number | null>(null);
  const [dragging, setDragging] = useState(false);
  const drag = useRef<{ x: number; start: number; width: number; size: number } | null>(null);
  const svg = useRef<SVGSVGElement>(null);
  useEffect(() => {
    setView({
      start: Math.max(0, n - 100 - (result?.forecast.length || 0)),
      size: Math.min(n, 100 + (result?.forecast.length || 0)),
    });
    setHover(null);
  }, [points, result, n]);
  const size = Math.min(n, Math.max(Math.min(8, n), view.size));
  const start = Math.max(0, Math.min(view.start, n - size));
  const end = start + size - 1;
  const visible = rows
    .map((r, i) => ({ ...r, i }))
    .filter((r) => r.i >= Math.floor(start) && r.i <= Math.ceil(end));
  const vals = visible.flatMap((r) =>
    [r.actual, r.predicted, r.lower, r.upper].filter(
      (v): v is number => v !== undefined && Number.isFinite(v),
    ),
  );
  const low = vals.length ? Math.min(...vals) : 0,
    high = vals.length ? Math.max(...vals) : 1,
    pad = Math.max((high - low) * 0.12, Math.abs(high) * 0.001, 0.00001);
  const min = low - pad,
    max = high + pad;
  const x = (i: number) => 70 + ((i - start) / Math.max(1, size - 1)) * 830;
  const y = (v: number) => 265 - ((v - min) / (max - min)) * 235;
  function reset() {
    setView({
      start: Math.max(0, n - 100 - (result?.forecast.length || 0)),
      size: Math.min(n, 100 + (result?.forecast.length || 0)),
    });
    setHover(null);
  }
  function zoom(factor: number, anchor = 0.5) {
    setView((v) => {
      const current = Math.min(n, Math.max(Math.min(8, n), v.size));
      const next = Math.min(n, Math.max(Math.min(8, n), Math.round(current * factor)));
      return {
        size: next,
        start: Math.max(0, Math.min(n - next, v.start + (current - next) * anchor)),
      };
    });
    setHover(null);
  }
  const actual = rows
    .map((r, i) => (r.actual !== undefined ? `${x(i)},${y(r.actual)}` : null))
    .filter(Boolean)
    .join(" ");
  const forecastRows = rows.map((r, i) => ({ ...r, i })).filter((r) => r.predicted !== undefined);
  const bridge = points.length
    ? `${x(points.length - 1)},${y(points[points.length - 1].close)} `
    : "";
  const forecast = bridge + forecastRows.map((r) => `${x(r.i)},${y(r.predicted!)}`).join(" ");
  const band = [
    ...forecastRows.map((r) => `${x(r.i)},${y(r.upper!)}`),
    ...forecastRows.map((r) => `${x(r.i)},${y(r.lower!)}`).reverse(),
  ].join(" ");
  const selected = hover !== null ? rows[hover] : null;
  if (n < 2)
    return (
      <div className="px-5 py-20 text-center text-muted">
        Waiting for at least two observations…
      </div>
    );
  return (
    <div className="w-full">
      <div
        className="
          mt-[18px] flex items-center justify-between gap-2.5 max-[650px]:flex-col
          max-[650px]:items-start [&>span]:text-[11px] [&>span]:text-muted [&>div]:flex
          [&>div]:gap-1.5
        "
      >
        <span>Hover to inspect · drag to pan</span>
        <div>
          <Button
            compact
            aria-label="Zoom in"
            disabled={size <= Math.min(8, n)}
            onClick={() => zoom(0.7)}
          >
            +
          </Button>
          <Button compact aria-label="Zoom out" disabled={size >= n} onClick={() => zoom(1.4)}>
            −
          </Button>
          <Button compact onClick={reset}>
            Reset
          </Button>
          <Button
            compact
            onClick={() => {
              setView({ start: 0, size: n });
              setHover(null);
            }}
          >
            All
          </Button>
        </div>
      </div>
      <div className="relative">
        <svg
          className="
            mt-2 block w-full select-none rounded focus-visible:outline-2
            focus-visible:outline-accent focus-visible:outline-offset-4
          "
          ref={svg}
          viewBox="0 0 950 320"
          role="img"
          tabIndex={0}
          aria-label="Interactive price chart. Left and right arrows pan. Plus and minus zoom. Home resets."
          style={{ touchAction: "pan-y", cursor: dragging ? "grabbing" : "crosshair" }}
          onKeyDown={(e) => {
            if (["ArrowLeft", "ArrowRight", "+", "=", "-", "Home"].includes(e.key))
              e.preventDefault();
            if (e.key === "+" || e.key === "=") zoom(0.7);
            if (e.key === "-") zoom(1.4);
            if (e.key === "Home") reset();
            if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
              const direction = e.key === "ArrowLeft" ? -1 : 1;
              setView((v) => ({
                ...v,
                start: Math.max(
                  0,
                  Math.min(n - size, start + direction * Math.max(1, Math.round(size * 0.15))),
                ),
              }));
              setHover(null);
            }
          }}
          onPointerDown={(e) => {
            if (e.button !== 0) return;
            const rect = e.currentTarget.getBoundingClientRect();
            drag.current = { x: e.clientX, start, width: (rect.width * 830) / 950, size };
            setDragging(true);
            e.currentTarget.setPointerCapture(e.pointerId);
          }}
          onPointerMove={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            if (drag.current) {
              const d = drag.current;
              setView({
                size: d.size,
                start: Math.max(
                  0,
                  Math.min(n - d.size, d.start - ((e.clientX - d.x) / d.width) * (d.size - 1)),
                ),
              });
              setHover(null);
              return;
            }
            const local = ((e.clientX - rect.left) / rect.width) * 950;
            if (local < 70 || local > 900) {
              setHover(null);
              return;
            }
            setHover(
              Math.max(0, Math.min(n - 1, Math.round(start + ((local - 70) / 830) * (size - 1)))),
            );
          }}
          onPointerUp={(e) => {
            drag.current = null;
            setDragging(false);
            if (e.currentTarget.hasPointerCapture(e.pointerId))
              e.currentTarget.releasePointerCapture(e.pointerId);
          }}
          onPointerCancel={() => {
            drag.current = null;
            setDragging(false);
          }}
          onLostPointerCapture={() => {
            drag.current = null;
            setDragging(false);
          }}
          onPointerLeave={() => {
            if (!drag.current) setHover(null);
          }}
        >
          <defs>
            <clipPath id="signal-price-clip">
              <rect x="70" y="20" width="830" height="255" />
            </clipPath>
          </defs>
          {[0, 1, 2, 3, 4].map((i) => {
            const v = min + ((max - min) * i) / 4;
            return (
              <g key={i}>
                <line x1="70" x2="900" y1={y(v)} y2={y(v)} stroke="#2b3942" strokeDasharray="3 6" />
                <text x="3" y={y(v) + 4} fill="#9babb7" fontSize="11">
                  {fmt(v)}
                </text>
              </g>
            );
          })}
          <g clipPath="url(#signal-price-clip)">
            <polyline points={actual} fill="none" stroke="#b9f275" strokeWidth="2.5" />
            {forecastRows.length > 0 && (
              <>
                <polygon points={band} fill="#a8b6ff" opacity=".16" />
                <polyline
                  points={forecast}
                  fill="none"
                  stroke="#a8b6ff"
                  strokeWidth="2"
                  strokeDasharray="6 4"
                />
              </>
            )}
            {selected && hover !== null && (
              <>
                <line
                  x1={x(hover)}
                  x2={x(hover)}
                  y1="20"
                  y2="275"
                  stroke="#a5b6c4"
                  strokeDasharray="4 4"
                />
                <circle
                  cx={x(hover)}
                  cy={y(selected.actual ?? selected.predicted!)}
                  r="4"
                  fill={selected.actual !== undefined ? "#b9f275" : "#a8b6ff"}
                  stroke="#10161c"
                  strokeWidth="2"
                />
              </>
            )}
          </g>
          {[0, 0.5, 1].map((f) => {
            const i = Math.min(n - 1, Math.max(0, Math.round(start + (size - 1) * f)));
            return (
              <text
                key={f}
                x={70 + 830 * f}
                y="305"
                textAnchor={f === 0 ? "start" : f === 1 ? "end" : "middle"}
                fill="#9babb7"
                fontSize="11"
              >
                {rows[i].date}
              </text>
            );
          })}
        </svg>
        {selected && hover !== null && (
          <div
            className="
              pointer-events-none absolute top-3 z-10 min-w-[155px] max-w-[94%] rounded-lg border
              border-[#536850] bg-[#111b22]/95 p-3 text-xs text-[#e7eee9] shadow-xl
              [&>strong]:mb-2 [&>strong]:block [&>strong]:text-[#c5e7ab] [&>span]:my-1
              [&>span]:flex [&>span]:justify-between [&>span]:gap-4 [&>span]:text-[#a9bac5]
              [&_b]:font-medium [&_b]:text-[#eef3f6] [&>small]:mt-2 [&>small]:block
              [&>small]:text-[10px] [&>small]:text-muted max-[650px]:min-w-[125px] max-[650px]:p-2
              max-[650px]:text-[11px]
            "
            style={{ left: `${Math.max(2, Math.min(70, (x(hover) / 950) * 100))}%` }}
          >
            <strong>{selected.date}</strong>
            {selected.actual !== undefined ? (
              <span>
                Close <b>{fmt(selected.actual)}</b>
              </span>
            ) : (
              <>
                <span>
                  Forecast <b>{fmt(selected.predicted!)}</b>
                </span>
                <span>
                  Lower <b>{fmt(selected.lower!)}</b>
                </span>
                <span>
                  Upper <b>{fmt(selected.upper!)}</b>
                </span>
                <small>Exploratory residual band</small>
              </>
            )}
          </div>
        )}
      </div>
      <div className="mt-1 mb-3 text-center text-[10px] text-muted" aria-live="polite">
        {Math.round(size)} of {n} observations · {rows[Math.floor(start)].date} to{" "}
        {rows[Math.min(n - 1, Math.ceil(end))].date}
      </div>
    </div>
  );
}
