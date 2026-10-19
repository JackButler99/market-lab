"use client";
import { useEffect, useState } from "react";
import FundamentalChart, { type FundamentalVisual } from "./fundamental-chart";
import FundamentalFormula from "./fundamental-formula";
import { Button, Eyebrow, Panel, Pill } from "./ui";
import { useInsightPreferences, type ReadingLevel } from "./insight-preferences";
import { FundamentalGlossary } from "./fundamental-glossary";

type Evidence = {
  metric: string;
  source: string;
  period: string;
  url?: string;
  filed?: string;
  tag?: string;
  accn?: string;
  series_id?: string;
  source_timestamp?: string;
};
type Insight = {
  id: string;
  title: string;
  value: number | null;
  unit: string;
  fact: string;
  readings: Record<ReadingLevel, string>;
  caveat: string;
  next_steps: string[];
  evidence: Evidence[];
  formula?: string | null;
  comparison?: { value: number | null; unit: string; prior_period: string | null } | null;
  stale?: boolean;
  issue?: string | null;
};
type Report = {
  version: string;
  symbol: string;
  snapshot_id: string | null;
  fetched_at: string | null;
  as_of: string;
  period: string | null;
  has_data: boolean;
  summary: string;
  highlights?: string[];
  warnings: string[];
  cards: Insight[];
  visuals?: FundamentalVisual[];
  quality: {
    label: string;
    freshness: string;
    available: number;
    expected: number;
    meaning?: string;
  };
  scenarios?: { condition: string; reading: string; check: string }[];
  questions: string[];
};
const displayValue = (value: number | null) =>
  value == null
    ? "Tidak tersedia"
    : new Intl.NumberFormat("id-ID", {
        notation: Math.abs(value) >= 1e6 ? "compact" : "standard",
        maximumFractionDigits: 2,
      }).format(value);
const displayUnit = (unit: string) => (unit === "percentage points" ? "poin persentase" : unit);
const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const LEVELS: [ReadingLevel, string, string][] = [
  ["beginner", "Beginner", "Arti angka dengan bahasa sederhana"],
  ["intermediate", "Intermediate", "Hubungan metrik dan pertanyaan lanjutan"],
  ["expert", "Expert", "Rumus, sumber dan batas interpretasi"],
];
export default function FundamentalInsights({
  symbol,
  snapshotId,
  period,
}: {
  symbol: string;
  snapshotId?: string | null;
  period?: string;
}) {
  const { level, setLevel } = useInsightPreferences();
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    let active = true;
    setReport(null);
    setError("");
    if (!snapshotId) {
      setLoading(false);
      return () => {
        active = false;
      };
    }
    setLoading(true);
    async function load() {
      try {
        const params = new URLSearchParams({ symbol, snapshot_id: snapshotId! });
        if (period) params.set("period", period);
        const response = await fetch(`${API}/api/fundamentals/insights?${params}`, {
          cache: "no-store",
        });
        const result = await response.json();
        if (!response.ok)
          throw new Error(
            result.error || "Insight tidak dapat dimuat. Restart backend yang sudah diperbarui.",
          );
        if (
          result.symbol !== symbol ||
          result.snapshot_id !== snapshotId ||
          (period && result.period !== period) ||
          !Array.isArray(result.cards)
        )
          throw new Error("Snapshot/periode insight tidak cocok dengan data yang ditampilkan.");
        if (active) {
          setReport(result);
          setError("");
        }
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : "Insight tidak tersedia.");
      } finally {
        if (active) setLoading(false);
      }
    }
    load();
    const timer = setInterval(load, 60000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [symbol, snapshotId, period, refresh]);
  const current =
    report?.symbol === symbol &&
    report.snapshot_id === snapshotId &&
    (!period || report.period === period)
      ? report
      : null;
  return (
    <div className="space-y-5" data-tour="fundamental-insights">
      <Panel className="border-accent/30 bg-gradient-to-br from-accent/5 to-surface">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <Eyebrow>FUNDAMENTAL INSIGHT / {symbol}</Eyebrow>
            <h2 className="mt-3 text-xl font-medium">Pahami angka, lalu periksa buktinya.</h2>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-muted">
              Penjelasan Bahasa Indonesia untuk{" "}
              {symbol === "EURUSD"
                ? "konteks dua ekonomi dan kebijakan mata uang"
                : symbol === "BTCUSD"
                  ? "aktivitas serta kondisi jaringan Bitcoin"
                  : "kinerja bisnis dan laporan keuangan perusahaan"}
              . Pilih kedalaman bacaan; fakta sumber tetap sama.
            </p>
          </div>
          <Pill>Data & interpretasi dipisahkan</Pill>
        </div>
        <div
          className="mt-5 flex flex-wrap gap-2"
          role="group"
          aria-label="Tingkat penjelasan fundamental"
        >
          {LEVELS.map(([id, label, hint]) => (
            <Button
              key={id}
              variant={level === id ? "primary" : "secondary"}
              aria-pressed={level === id}
              title={hint}
              onClick={() => setLevel(id)}
            >
              {label}
            </Button>
          ))}
        </div>
        <p className="mt-3 text-xs leading-6 text-muted">
          {LEVELS.find(([id]) => id === level)?.[2]}. Pilihan disimpan di browser dan dipakai di
          semua tab aset.
        </p>
        {!snapshotId && (
          <p className="mt-5 rounded border border-line bg-canvas p-4 text-sm leading-7 text-muted">
            Belum ada snapshot tersimpan. Sinkronkan fundamental di panel sumber; glosarium di bawah
            tetap dapat dipelajari.
          </p>
        )}
        {loading && (
          <p role="status" className="mt-5 text-sm text-muted">
            Menyusun penjelasan dari snapshot dan periode yang dipilih…
          </p>
        )}
        {error && (
          <div
            role="alert"
            className="mt-5 rounded bg-red-400/10 p-4 text-sm leading-7 text-red-200"
          >
            <p>{error}</p>
            <Button className="mt-3" onClick={() => setRefresh((v) => v + 1)}>
              Muat ulang insight
            </Button>
          </div>
        )}
        {current && (
          <>
            <div className="mt-5 rounded-lg border border-line bg-canvas p-4">
              <div className="flex flex-wrap gap-2">
                <Pill>{current.quality.label}</Pill>
                <Pill>
                  {current.quality.available}/{current.quality.expected} metrik inti tersedia
                </Pill>
                {current.period && <Pill>Periode {current.period}</Pill>}
              </div>
              <p className="mt-3 text-sm leading-7">{current.summary}</p>
              <p className="mt-2 text-xs leading-6 text-muted">
                Kesegaran dan cakupan data bukan skor keyakinan, kesehatan aset, atau probabilitas
                harga naik.
              </p>
              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                {current.cards
                  .filter((c) => c.value != null)
                  .slice(0, 3)
                  .map((c) => (
                    <div key={c.id} className="rounded-lg border border-line bg-surface p-4">
                      <p className="text-xs leading-6 text-muted">{c.title}</p>
                      <strong className="mt-2 block text-2xl font-medium tracking-tight">
                        {displayValue(c.value)}
                      </strong>
                      <p className="mt-1 text-xs text-muted">
                        {displayUnit(c.unit)} ·{" "}
                        {current.period || c.evidence[0]?.period || "Tanggal tidak tersedia"}
                      </p>
                    </div>
                  ))}
              </div>
            </div>
            <div className="mt-4 space-y-2 rounded border border-amber-300/20 bg-amber-300/5 p-4">
              <h3 className="text-sm text-amber-100">Konteks sebelum menyimpulkan</h3>
              <ul className="mt-2 list-disc space-y-2 pl-4 text-xs leading-6 text-muted">
                {current.warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            </div>
          </>
        )}
      </Panel>
      {current && (
        <>
          <div className="grid items-start gap-4 lg:grid-cols-2">
            {current.cards.map((c) => (
              <Panel key={c.id} className="h-full">
                <div className="flex items-start justify-between gap-3">
                  <h3 className="text-base font-medium">{c.title}</h3>
                  <Pill>
                    {c.value == null
                      ? "Nilai tidak tersedia"
                      : c.stale
                        ? "Data stale"
                        : "Bukti tersimpan"}
                  </Pill>
                </div>
                {current.visuals?.find((v) => v.card_id === c.id) && (
                  <FundamentalChart
                    visual={current.visuals.find((v) => v.card_id === c.id)!}
                    stale={c.stale || current.quality.freshness === "stale"}
                  />
                )}
                <div className="mt-4 rounded border border-line bg-canvas p-4">
                  <h4 className="text-[10px] uppercase tracking-widest text-accent">Angka utama</h4>
                  <p className="mt-2">
                    <strong className="text-3xl font-medium tracking-tight">
                      {displayValue(c.value)}
                    </strong>
                    <span className="ml-2 text-xs text-muted">{displayUnit(c.unit)}</span>
                  </p>
                  <p className="mt-2 text-xs text-muted">
                    Periode observasi: {current.period || c.evidence[0]?.period || "Tidak tersedia"}
                  </p>
                  {c.comparison?.value != null && (
                    <p className="mt-2 text-xs text-muted">
                      Perubahan terhadap {c.comparison.prior_period}:{" "}
                      {c.comparison.value > 0 ? "+" : ""}
                      {displayValue(c.comparison.value)} {displayUnit(c.comparison.unit)}
                    </p>
                  )}
                  <details className="mt-3">
                    <summary className="cursor-pointer text-xs text-accent hover:underline">
                      Fakta & angka lengkap
                    </summary>
                    <p className="mt-2 text-sm leading-7">{c.fact}</p>
                  </details>
                  {c.issue && <p className="mt-2 text-xs text-amber-200">{c.issue}</p>}
                </div>
                <h4 className="mt-5 text-xs text-accent">
                  Cara membacanya · {LEVELS.find(([id]) => id === level)?.[1]}
                </h4>
                <p className="mt-2 text-sm leading-7 text-muted">{c.readings[level]}</p>
                <p className="mt-4 border-l-2 border-amber-300/40 pl-3 text-xs leading-6 text-muted">
                  Batas kesimpulan: {c.caveat}
                </p>
                {level !== "beginner" && (
                  <>
                    <h4 className="mt-5 text-xs text-accent">Periksa berikutnya</h4>
                    <ul className="mt-2 list-disc space-y-2 pl-4 text-xs leading-6 text-muted">
                      {c.next_steps.map((step) => (
                        <li key={step}>{step}</li>
                      ))}
                    </ul>
                  </>
                )}
                {level === "expert" && (
                  <div className="mt-4 rounded border border-line p-3 text-xs leading-6 text-muted">
                    <p>
                      Nilai tanpa singkatan:{" "}
                      {c.value == null
                        ? "Tidak tersedia"
                        : c.value.toLocaleString("en-US", { maximumFractionDigits: 10 })}{" "}
                      {c.unit}
                    </p>
                    {c.comparison && (
                      <p className="mt-2">
                        Pembanding: {c.comparison.prior_period || "Tidak tersedia"} · perubahan{" "}
                        {c.comparison.value == null
                          ? "Tidak tersedia"
                          : c.comparison.value.toLocaleString("en-US", {
                              maximumFractionDigits: 6,
                            })}{" "}
                        {c.comparison.unit}
                      </p>
                    )}
                  </div>
                )}
                <FundamentalFormula metric={c.id} symbol={symbol} expert={level === "expert"} />
                <details className="mt-5">
                  <summary className="cursor-pointer text-xs text-accent hover:underline">
                    Bukti & sumber ({c.evidence.length})
                  </summary>
                  <ul className="mt-3 space-y-3 text-xs leading-6 text-muted">
                    {c.evidence.map((ev, i) => (
                      <li
                        key={`${ev.metric}-${ev.period}-${i}`}
                        className="rounded border border-line p-3"
                      >
                        <p>
                          {ev.metric} · {ev.source} · periode {ev.period}
                        </p>
                        {level === "expert" && (
                          <p className="mt-1 break-all">
                            {ev.tag || ev.series_id}
                            {ev.accn ? ` · ${ev.accn}` : ""}
                            {ev.filed ? ` · filed ${ev.filed}` : ""}
                            {ev.source_timestamp ? ` · timestamp ${ev.source_timestamp}` : ""}
                          </p>
                        )}
                        {ev.url && (
                          <a
                            href={ev.url}
                            target="_blank"
                            rel="noreferrer"
                            className="mt-1 inline-block text-accent hover:underline"
                          >
                            Buka sumber ↗
                          </a>
                        )}
                      </li>
                    ))}
                  </ul>
                  {!c.evidence.length && (
                    <p className="mt-2 text-xs text-muted">
                      Bukti untuk angka ini belum tersedia; penjelasan konsep tidak menggantikannya.
                    </p>
                  )}
                </details>
              </Panel>
            ))}
          </div>
          {current.scenarios && (
            <Panel>
              <h3 className="text-base">Skenario belajar · bersyarat, bukan prediksi</h3>
              <p className="mt-2 text-xs leading-6 text-muted">
                Contoh pertanyaan untuk investigasi. Bukan klaim bahwa kondisi berikut sedang
                terjadi.
              </p>
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                {current.scenarios.map((s) => (
                  <article key={s.condition} className="rounded border border-line p-4">
                    <h4 className="text-sm text-accent">{s.condition}</h4>
                    <p className="mt-2 text-sm leading-7 text-muted">{s.reading}</p>
                    <p className="mt-3 text-xs leading-6 text-muted">Bukti tambahan: {s.check}</p>
                  </article>
                ))}
              </div>
            </Panel>
          )}
          <Panel>
            <details>
              <summary className="cursor-pointer text-sm text-accent">
                Metode dan jejak audit
              </summary>
              <p className="mt-3 text-xs leading-6 text-muted">
                Penjelasan dihasilkan oleh aturan dan template yang dapat diuji, tanpa panggilan AI
                eksternal. Tidak membaca narasi manajemen, berita atau dokumen yang belum diekstrak.
                Insight ini tidak masuk ke model harga.
              </p>
              <p className="mt-3 break-all font-mono text-xs leading-6 text-muted">
                Versi {current.version}
                <br />
                Snapshot {current.snapshot_id}
                <br />
                Periode {current.period || "Masing-masing tanggal observasi"}
                <br />
                Pemeriksaan kesegaran {current.as_of}
              </p>
            </details>
          </Panel>
        </>
      )}
      <FundamentalGlossary symbol={symbol} />
    </div>
  );
}
