"use client";
import { useState } from "react";
import { Panel } from "./ui";
const TERMS: Record<string, { name: string; meaning: string; caution: string; group: string }> = {
  revenue: {
    name: "Revenue / pendapatan",
    meaning: "Nilai penjualan yang diakui dalam periode laporan.",
    caution: "Bukan kas yang sudah diterima dan bukan laba.",
    group: "equity",
  },
  net_income: {
    name: "Net income / laba bersih",
    meaning: "Hasil akuntansi setelah beban dan pajak pada periode laporan.",
    caution: "Tidak sama dengan kas operasi; dapat mencakup item nonkas atau satu kali.",
    group: "equity",
  },
  operating_income: {
    name: "Operating income",
    meaning: "Laba dari kegiatan operasi menurut klasifikasi laporan.",
    caution: "Periksa definisi dan item yang dimasukkan perusahaan.",
    group: "equity",
  },
  operating_cash_flow: {
    name: "Operating cash flow",
    meaning: "Arus kas masuk/keluar dari aktivitas operasi.",
    caution: "Perubahan working capital dapat membuatnya berbeda dari laba.",
    group: "equity",
  },
  capex: {
    name: "Capex",
    meaning: "Di aplikasi ini: pembelian properti, pabrik dan peralatan.",
    caution: "Belum tentu mencakup seluruh investasi, akuisisi atau aset takberwujud.",
    group: "equity",
  },
  free_cash_flow: {
    name: "Free cash flow",
    meaning: "Kas operasi dikurangi capex yang dicakup metrik aplikasi.",
    caution: "Ukuran turunan, bukan subtotal GAAP atau seluruh kas bebas dibagikan.",
    group: "equity",
  },
  net_margin: {
    name: "Net margin",
    meaning: "Laba bersih dibagi pendapatan, dikali 100.",
    caution: "Perbandingan antarindustri memerlukan konteks model bisnis.",
    group: "equity",
  },
  operating_margin: {
    name: "Operating margin",
    meaning: "Operating income dibagi pendapatan, dikali 100.",
    caution: "Tidak menunjukkan seluruh beban non-operasional dan pajak.",
    group: "equity",
  },
  revenue_yoy: {
    name: "Revenue growth YoY",
    meaning: "Perubahan pendapatan dibanding periode tahunan sebelumnya yang berurutan.",
    caution: "Perubahan akuisisi, kurs dan komposisi bisnis dapat memengaruhi perbandingan.",
    group: "equity",
  },
  cash: {
    name: "Cash & equivalents",
    meaning: "Kas dan setara kas yang dilaporkan.",
    caution: "Bukan seluruh investasi likuid atau kas yang seluruhnya bebas digunakan.",
    group: "equity",
  },
  assets: {
    name: "Assets / aset",
    meaning: "Sumber daya yang diakui dalam neraca pada tanggal laporan.",
    caution: "Nilai buku bukan nilai pasar perusahaan.",
    group: "equity",
  },
  liabilities: {
    name: "Liabilities / liabilitas",
    meaning: "Seluruh kewajiban yang diakui dalam neraca.",
    caution: "Bukan hanya utang berbunga; tidak dapat langsung dipakai sebagai debt.",
    group: "equity",
  },
  equity: {
    name: "Stockholders’ equity",
    meaning: "Hak residual pemegang saham yang diakui dalam neraca.",
    caution: "Bukan kapitalisasi pasar.",
    group: "equity",
  },
  diluted_eps: {
    name: "Diluted EPS",
    meaning: "Laba per saham setelah mempertimbangkan efek dilusi sesuai laporan.",
    caution: "Perubahan jumlah saham dan item satu kali dapat memengaruhinya.",
    group: "equity",
  },
  us_rate: {
    name: "US effective federal funds rate",
    meaning: "Bunga efektif pasar uang antarbank semalam yang teramati.",
    caution: "Bukan batas target Fed atau prediksi rate mendatang.",
    group: "EURUSD",
  },
  ea_rate: {
    name: "ECB deposit facility rate",
    meaning: "Bunga fasilitas simpanan semalam pada ECB.",
    caution: "Konsep instrumennya berbeda dari bunga efektif pasar AS.",
    group: "EURUSD",
  },
  rate_spread: {
    name: "Rate spread",
    meaning: "Di aplikasi ini: DFF AS dikurangi deposit facility ECB pada tanggal yang sama.",
    caution: "Satuan poin persentase; bukan sinyal arah kurs.",
    group: "EURUSD",
  },
  us_cpi: {
    name: "US CPI (NSA)",
    meaning: "Indeks harga konsumen AS yang tidak disesuaikan musiman.",
    caution: "Indeks bukan persen inflasi; basis indeks berbeda dari HICP.",
    group: "EURUSD",
  },
  ea_hicp: {
    name: "Euro-area HICP (NSA)",
    meaning: "Indeks harga konsumen harmonis zona euro dengan komposisi wilayah berubah.",
    caution: "Keranjang dan basisnya berbeda dari CPI AS.",
    group: "EURUSD",
  },
  us_inflation: {
    name: "US inflation YoY",
    meaning: "Persentase perubahan CPI dari bulan yang sama satu tahun lalu.",
    caution: "Bukan perubahan bulanan, core CPI atau surprise terhadap konsensus.",
    group: "EURUSD",
  },
  ea_inflation: {
    name: "Euro-area inflation YoY",
    meaning: "Persentase perubahan HICP dari bulan yang sama satu tahun lalu.",
    caution: "Base effect, revisi dan komposisi wilayah memerlukan pemeriksaan.",
    group: "EURUSD",
  },
  "hash-rate": {
    name: "Hash rate",
    meaning: "Estimasi daya komputasi penambang Bitcoin, ditampilkan dalam TH/s.",
    caution: "Bukan harga, jumlah pengguna atau ukuran profitabilitas penambang.",
    group: "BTCUSD",
  },
  difficulty: {
    name: "Mining difficulty",
    meaning: "Tingkat kesulitan menemukan blok Bitcoin yang valid.",
    caution: "Angka chart harian dapat mengalami pembulatan/agregasi provider.",
    group: "BTCUSD",
  },
  "n-transactions": {
    name: "Confirmed transactions",
    meaning: "Jumlah transaksi terkonfirmasi pada observasi harian provider.",
    caution:
      "Satu transaksi bukan satu pengguna; batching dan transaksi internal memengaruhi angka.",
    group: "BTCUSD",
  },
  "total-bitcoins": {
    name: "Issued supply",
    meaning: "Jumlah BTC yang diterbitkan; dipilih observasi terakhir per hari UTC selesai.",
    caution:
      "Bukan liquid supply; mencakup koin hilang. Timestamp terakhir tidak menjamin midnight close.",
    group: "BTCUSD",
  },
};
export function MetricHelp({ metric }: { metric: string }) {
  const term = TERMS[metric];
  if (!term) return null;
  return (
    <details className="mt-3 text-xs leading-6 text-muted">
      <summary className="cursor-pointer text-accent hover:underline">Apa arti metrik ini?</summary>
      <p className="mt-2">{term.meaning}</p>
      <p className="mt-2">Perhatikan: {term.caution}</p>
    </details>
  );
}
export function FundamentalGlossary({ symbol }: { symbol: string }) {
  const [search, setSearch] = useState("");
  const group = ["AAPL", "MSFT"].includes(symbol) ? "equity" : symbol;
  const entries = Object.entries(TERMS).filter(
    ([, t]) =>
      t.group === group && `${t.name} ${t.meaning}`.toLowerCase().includes(search.toLowerCase()),
  );
  return (
    <Panel>
      <details>
        <summary className="cursor-pointer text-base text-accent">
          Glosarium · pelajari istilah {group === "equity" ? "saham" : symbol}
        </summary>
        <label className="mt-4 block text-xs text-muted">
          Cari istilah
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            type="search"
            placeholder="Misalnya margin, inflasi, atau suplai"
            className="mt-2 block w-full rounded border border-line bg-canvas p-3 text-sm text-ink focus-visible:outline-2 focus-visible:outline-accent"
          />
        </label>
        <dl className="mt-4 grid gap-4 md:grid-cols-2">
          {entries.map(([key, t]) => (
            <div key={key} className="rounded border border-line p-4">
              <dt className="text-sm text-ink">{t.name}</dt>
              <dd className="mt-2 text-xs leading-6 text-muted">
                {t.meaning}
                <p className="mt-2">Perhatikan: {t.caution}</p>
              </dd>
            </div>
          ))}
        </dl>
        {!entries.length && <p className="mt-4 text-sm text-muted">Istilah tidak ditemukan.</p>}
      </details>
    </Panel>
  );
}
