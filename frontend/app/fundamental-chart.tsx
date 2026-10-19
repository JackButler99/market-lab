"use client";
import { useEffect, useId, useRef, useState } from "react";
import { Button, tableClass } from "./ui";
import { chartDomain, lineSegments, utcTime, type ChartPoint } from "./fundamental-chart-utils";
export type FundamentalVisual = {
  card_id: string;
  title: string;
  unit: string;
  kind: "bar" | "line" | "step";
  frequency: "annual" | "monthly" | "daily";
  series: { id: string; label: string; points: ChartPoint[] }[];
  max_gap_days: number;
  note: string;
  zero_baseline: boolean;
};
const COLORS = ["#b9f275", "#b5a5ff", "#67d5e3"];
const short = (v: number) =>
  new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 2 }).format(v);
const exact = (v: number | null) =>
  v == null ? "Tidak tersedia" : v.toLocaleString("en-US", { maximumFractionDigits: 8 });
export default function FundamentalChart({
  visual,
  stale = false,
}: {
  visual: FundamentalVisual;
  stale?: boolean;
}) {
  const id = useId();
  const box = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(480);
  const defaultWindow =
    visual.frequency === "daily" ? "90" : visual.frequency === "monthly" ? "12" : "all";
  const [window, setWindow] = useState(defaultWindow);
  const [zero, setZero] = useState(false);
  const [hover, setHover] = useState<string | null>(null);
  useEffect(() => {
    setHover(null);
    setWindow(defaultWindow);
    setZero(false);
  }, [visual.card_id, defaultWindow]);
  const allDates = [...new Set(visual.series.flatMap((s) => s.points.map((p) => p.date)))].sort();
  const goodDates = visual.series
    .flatMap((s) =>
      s.points.filter((p) => p.value != null && Number.isFinite(p.value)).map((p) => p.date),
    )
    .sort();
  const latest = goodDates.at(-1);
  let cutoff = -Infinity;
  if (latest && window !== "all") {
    if (visual.frequency === "monthly") {
      const date = new Date(utcTime(latest));
      date.setUTCMonth(date.getUTCMonth() - Number(window) + 1, 1);
      cutoff = date.getTime();
    } else cutoff = utcTime(latest) - (Number(window) - 1) * 86400000;
  }
  const dates = allDates.filter(
    (d) =>
      (visual.kind === "bar" || (goodDates.length > 0 && d >= goodDates[0] && d <= latest!)) &&
      utcTime(d) >= cutoff,
  );
  const displayed = visual.series.map((s) => ({
    ...s,
    points: s.points.filter((p) => dates.includes(p.date)),
  }));
  const values = displayed.flatMap((s) =>
    s.points.flatMap((p) => (p.value != null && Number.isFinite(p.value) ? [p.value] : [])),
  );
  useEffect(() => {
    if (!box.current) return;
    const measure = new ResizeObserver(([entry]) =>
      setWidth(Math.max(280, Math.floor(entry.contentRect.width))),
    );
    measure.observe(box.current);
    return () => measure.disconnect();
  }, [values.length > 0]);
  const isBar = visual.kind === "bar";
  const [min, max] = chartDomain(values, isBar || zero);
  const left = 76,
    right = 16,
    top = 18,
    bottom = 42,
    height = 260;
  const pw = width - left - right,
    ph = height - top - bottom;
  const y = (v: number) => top + ((max - v) / (max - min)) * ph;
  const x = (date: string) =>
    isBar
      ? left + ((dates.indexOf(date) + 0.5) * pw) / Math.max(1, dates.length)
      : left +
        (dates.length === 1
          ? pw / 2
          : ((utcTime(date) - utcTime(dates[0])) /
              Math.max(1, utcTime(dates[dates.length - 1]) - utcTime(dates[0]))) *
            pw);
  const selected =
    hover && dates.includes(hover)
      ? hover
      : isBar
        ? dates.at(-1)
        : latest && dates.includes(latest)
          ? latest
          : dates.at(-1);
  const selectedValues = displayed.map((s) => ({
    label: s.label,
    value: s.points.find((p) => p.date === selected)?.value ?? null,
  }));
  const tickDates = [
    ...new Set(
      [dates[0], dates[Math.floor((dates.length - 1) / 2)], dates.at(-1)].filter((d): d is string =>
        Boolean(d),
      ),
    ),
  ];
  function choose(clientX: number, element: SVGSVGElement) {
    const rect = element.getBoundingClientRect();
    const px = ((clientX - rect.left) / rect.width) * width;
    if (dates.length)
      setHover(dates.reduce((a, b) => (Math.abs(x(a) - px) < Math.abs(x(b) - px) ? a : b)));
  }
  function keyboard(e: React.KeyboardEvent<SVGSVGElement>) {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key) || !dates.length) return;
    e.preventDefault();
    const index = dates.indexOf(selected || "");
    setHover(
      dates[
        e.key === "Home"
          ? 0
          : e.key === "End"
            ? dates.length - 1
            : Math.max(0, Math.min(dates.length - 1, index + (e.key === "ArrowLeft" ? -1 : 1)))
      ],
    );
  }
  const barWidth = Math.min(
    30,
    ((pw / Math.max(1, dates.length)) * 0.72) / Math.max(1, displayed.length),
  );
  return (
    <figure
      className="mt-4 rounded-lg border border-line bg-canvas p-3"
      aria-labelledby={`${id}-title`}
      aria-describedby={`${id}-note`}
    >
      <figcaption id={`${id}-title`} className="text-sm font-medium leading-6">
        {visual.title}
        <span className="ml-2 text-xs font-normal text-muted">({visual.unit})</span>
      </figcaption>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {visual.frequency !== "annual" && (
          <div className="flex gap-1" role="group" aria-label="Rentang grafik">
            {(visual.frequency === "monthly"
              ? [
                  ["6", "6 bln"],
                  ["12", "12 bln"],
                  ["all", "Snapshot"],
                ]
              : [
                  ["30", "30 hari"],
                  ["90", "90 hari"],
                  ["all", "Snapshot"],
                ]
            ).map(([value, label]) => (
              <Button
                key={value}
                compact
                variant={window === value ? "primary" : "ghost"}
                onClick={() => {
                  setWindow(value);
                  setHover(null);
                }}
                aria-pressed={window === value}
              >
                {label}
              </Button>
            ))}
          </div>
        )}
        {!isBar && (
          <label className="ml-auto flex cursor-pointer items-center gap-2 text-xs text-muted">
            <input
              type="checkbox"
              checked={zero}
              onChange={(e) => setZero(e.target.checked)}
              className="accent-[#b9f275]"
            />
            Sumbu Y mencakup nol
          </label>
        )}
      </div>
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2">
        {displayed.map((s, i) => (
          <span key={s.id} className="flex items-center gap-2 text-xs text-muted">
            <span
              className="inline-block h-2 w-4 rounded-sm"
              style={{ background: COLORS[i % COLORS.length] }}
            />
            {s.label}
          </span>
        ))}
      </div>
      {!values.length ? (
        <p className="my-8 text-sm leading-7 text-muted">
          Belum cukup observasi yang valid untuk grafik ini. Data yang hilang tidak diganti dengan
          nol.
        </p>
      ) : (
        <>
          <div ref={box} className="mt-2 overflow-x-auto">
            <svg
              role="group"
              tabIndex={0}
              aria-label={`${visual.title}. Gunakan panah kiri dan kanan untuk membaca observasi; Home dan End untuk awal dan akhir.`}
              width="100%"
              height={height}
              viewBox={`0 0 ${width} ${height}`}
              className="block min-w-[280px] focus-visible:outline-2 focus-visible:outline-accent"
              onKeyDown={keyboard}
              onFocus={() => setHover(dates.at(-1) || null)}
              onPointerMove={(e) => choose(e.clientX, e.currentTarget)}
              onPointerDown={(e) => choose(e.clientX, e.currentTarget)}
              onPointerLeave={() => setHover(null)}
            >
              <title>{visual.title}</title>
              <desc>
                Satuan {visual.unit}. {dates[0]} sampai {dates.at(-1)}. {visual.note} Nilai juga
                tersedia dalam tabel.
              </desc>
              {[0, 1, 2, 3, 4].map((i) => {
                const value = max - ((max - min) * i) / 4;
                return (
                  <g key={i}>
                    <line
                      x1={left}
                      x2={width - right}
                      y1={y(value)}
                      y2={y(value)}
                      stroke="#34414b"
                      strokeDasharray="3 5"
                    />
                    <text
                      x={left - 10}
                      y={y(value) + 4}
                      textAnchor="end"
                      fill="#9baab5"
                      fontSize="12"
                    >
                      {short(value)}
                    </text>
                  </g>
                );
              })}
              {min <= 0 && max >= 0 && (
                <line x1={left} x2={width - right} y1={y(0)} y2={y(0)} stroke="#899aa4" />
              )}
              {tickDates.map((date, j) => (
                <text
                  key={date}
                  x={x(date)}
                  y={height - 13}
                  textAnchor={
                    isBar
                      ? "middle"
                      : j === 0
                        ? "start"
                        : j === tickDates.length - 1
                          ? "end"
                          : "middle"
                  }
                  fill="#9baab5"
                  fontSize="12"
                >
                  {visual.frequency === "annual"
                    ? date.slice(0, 4)
                    : visual.frequency === "monthly"
                      ? date.slice(0, 7)
                      : date.slice(5)}
                </text>
              ))}
              {displayed.map((s, si) => (
                <g key={s.id}>
                  {isBar
                    ? s.points
                        .filter((p) => p.value != null)
                        .map((p) => (
                          <rect
                            key={p.date}
                            x={x(p.date) + (si - displayed.length / 2) * barWidth}
                            y={Math.min(y(0), y(p.value!))}
                            width={Math.max(1, barWidth - 2)}
                            height={Math.max(1, Math.abs(y(p.value!) - y(0)))}
                            rx="2"
                            fill={COLORS[si % COLORS.length]}
                            opacity={hover && p.date !== hover ? 0.5 : 0.9}
                          >
                            <title>{`${s.label} · ${p.date}: ${exact(p.value)} ${visual.unit}`}</title>
                          </rect>
                        ))
                    : lineSegments(s.points, visual.max_gap_days).map((segment, j) => (
                        <g key={j}>
                          {segment.length > 1 && (
                            <path
                              d={segment
                                .map((p, k) =>
                                  k === 0
                                    ? `M ${x(p.date)} ${y(p.value!)}`
                                    : visual.kind === "step"
                                      ? `H ${x(p.date)} V ${y(p.value!)}`
                                      : `L ${x(p.date)} ${y(p.value!)}`,
                                )
                                .join(" ")}
                              fill="none"
                              stroke={COLORS[si % COLORS.length]}
                              strokeWidth="2.5"
                              strokeDasharray={si === 1 ? "7 4" : undefined}
                            />
                          )}{" "}
                          {segment.map((p) => (
                            <circle
                              key={p.date}
                              cx={x(p.date)}
                              cy={y(p.value!)}
                              r={segment.length === 1 ? 3 : 1.8}
                              fill={COLORS[si % COLORS.length]}
                            />
                          ))}
                        </g>
                      ))}
                </g>
              ))}
              {hover && dates.includes(hover) && (
                <line
                  x1={x(hover)}
                  x2={x(hover)}
                  y1={top}
                  y2={height - bottom}
                  stroke="#e7edf1"
                  strokeDasharray="4 4"
                  opacity=".65"
                />
              )}
            </svg>
          </div>
          <div
            role="status"
            aria-live="polite"
            aria-atomic="true"
            className="mt-2 rounded border border-line bg-surface p-3 text-xs leading-6"
          >
            <p className="text-muted">
              {selected} · {hover ? "Observasi dipilih" : "Observasi terakhir"}
            </p>
            <div className="mt-1 grid gap-1">
              {selectedValues.map((s, si) => (
                <p key={s.label} className="break-words">
                  <span style={{ color: COLORS[si % COLORS.length] }}>{s.label}</span>:{" "}
                  {exact(s.value)} {visual.unit}
                </p>
              ))}
            </div>
          </div>
        </>
      )}
      <p id={`${id}-note`} className="mt-3 text-xs leading-6 text-muted">
        {stale
          ? "Data stale: grafik menggambarkan periode observasi, bukan kondisi saat ini. "
          : ""}
        {isBar
          ? "Skala batang mencakup nol. "
          : zero
            ? "Skala Y mencakup nol. "
            : "Skala Y fokus pada rentang data dan tidak selalu dimulai dari nol. "}
        {visual.note}
      </p>
      <details className="mt-3">
        <summary className="cursor-pointer text-xs text-accent hover:underline">
          Lihat tabel angka grafik
        </summary>
        <div className="max-h-64 overflow-auto">
          <table className={tableClass}>
            <caption className="pt-3 text-left text-xs text-muted">
              {visual.title} · {visual.unit}
            </caption>
            <thead>
              <tr>
                <th scope="col">Periode / tanggal</th>
                {displayed.map((s) => (
                  <th scope="col" key={s.id}>
                    {s.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {dates.map((date) => (
                <tr key={date}>
                  <th scope="row">{date}</th>
                  {displayed.map((s) => (
                    <td key={s.id}>
                      {exact(s.points.find((p) => p.date === date)?.value ?? null)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  );
}
