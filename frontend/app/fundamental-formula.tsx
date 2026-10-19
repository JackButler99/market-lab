import { createElement as el, type ReactNode } from "react";
// Only author-defined MathML trees are rendered; no HTML/LaTeX from provider payloads.
const node = (tag: string, ...children: ReactNode[]) => el(tag, null, ...children);
const text = (s: string) => node("mtext", s);
const op = (s: string) => node("mo", s);
const num = (s: string) => node("mn", s);
const variable = (name: string, sub?: string) =>
  sub ? node("msub", node("mi", name), text(sub)) : node("mi", name);
const fraction = (a: ReactNode, b: ReactNode) => node("mfrac", a, b);
const row = (...nodes: ReactNode[]) => node("mrow", ...nodes);
function formula(
  metric: string,
  symbol: string,
): { title: string; spoken: string; tex: string; math: ReactNode; definitions: string } | null {
  const growth = (label: string, v: string, prior: string) =>
    row(
      text(label),
      op("="),
      op("("),
      fraction(variable(v, "t"), variable(v, prior)),
      op("−"),
      num("1"),
      op(")"),
      op("×"),
      num("100"),
      op("%"),
    );
  switch (metric) {
    case "revenue":
      return {
        title: "Pertumbuhan pendapatan tahunan",
        spoken:
          "Pendapatan kini dibagi pendapatan periode tahunan sebelumnya, dikurangi satu, dikali seratus persen.",
        tex: String.raw`g_R=\left(\frac{R_t}{R_{t-1}}-1\right)\times100\%`,
        math: growth("Pertumbuhan", "R", "t−1"),
        definitions:
          "R = pendapatan. t−1 harus periode tahunan sebelumnya yang berurutan, dengan pendapatan pembanding positif.",
      };
    case "net_margin":
      return {
        title: "Margin laba bersih",
        spoken: "Laba bersih dibagi pendapatan, dikali seratus persen.",
        tex: String.raw`m=\frac{NI}{R}\times100\%`,
        math: row(
          text("Margin"),
          op("="),
          fraction(text("Laba bersih"), text("Pendapatan")),
          op("×"),
          num("100"),
          op("%"),
        ),
        definitions:
          "Pendapatan harus positif. Perubahan margin = margin kini − margin sebelumnya, dalam poin persentase.",
      };
    case "cash_conversion":
      return {
        title: "Kas operasi relatif terhadap laba",
        spoken: "Kas operasi dibagi laba bersih, hanya jika laba bersih positif.",
        tex: String.raw`C=\frac{CFO}{NI},\quad NI>0`,
        math: row(text("Rasio"), op("="), fraction(text("Kas operasi"), text("Laba bersih"))),
        definitions: "Hanya dihitung jika laba bersih positif; satuannya kali (×), bukan persen.",
      };
    case "free_cash_flow":
      return {
        title: "Free cash flow versi aplikasi",
        spoken: "Kas operasi dikurangi belanja properti, pabrik dan peralatan.",
        tex: String.raw`FCF=CFO-\mathrm{Capex}`,
        math: row(variable("FCF"), op("="), text("Kas operasi"), op("−"), text("Capex")),
        definitions:
          "Capex di sini adalah pembelian properti, pabrik dan peralatan. Ini ukuran turunan, bukan subtotal GAAP.",
      };
    case "liabilities_assets":
      return {
        title: "Liabilitas terhadap aset",
        spoken: "Total liabilitas dibagi total aset, dikali seratus persen.",
        tex: String.raw`L_A=\frac{L}{A}\times100\%`,
        math: row(
          text("Rasio"),
          op("="),
          fraction(text("Liabilitas"), text("Aset")),
          op("×"),
          num("100"),
          op("%"),
        ),
        definitions:
          "Aset harus positif. Liabilitas bukan hanya utang berbunga; angka ini tidak memakai threshold sektoral.",
      };
    case "rate_spread":
      return {
        title: "Selisih dua jenis rate",
        spoken: "Bunga efektif AS dikurangi bunga fasilitas deposito ECB pada tanggal yang sama.",
        tex: String.raw`\Delta r=r_{\mathrm{US}}-r_{\mathrm{ECB}}`,
        math: row(variable("Δr"), op("="), variable("r", "US"), op("−"), variable("r", "ECB")),
        definitions:
          "Rate AS dan ECB memakai konsep berbeda. Selisihnya dalam poin persentase; grafik menampilkan kedua komponennya dalam persen.",
      };
    case "us_inflation":
    case "ea_inflation":
      return {
        title: "Inflasi year over year",
        spoken:
          "Indeks harga bulan kini dibagi indeks bulan sama satu tahun sebelumnya, dikurangi satu, dikali seratus persen.",
        tex: String.raw`\pi_t=\left(\frac{I_t}{I_{t-12}}-1\right)\times100\%`,
        math: growth("Inflasi YoY", "I", "t−12 bulan"),
        definitions:
          "I = indeks CPI AS atau HICP zona euro. Gunakan bulan yang tepat dan indeks pembanding positif; kedua keranjang tidak identik.",
      };
    default:
      if (symbol === "BTCUSD")
        return {
          title: "Perubahan tujuh hari",
          spoken:
            "Nilai metrik kini dibagi nilai tepat tujuh hari sebelumnya, dikurangi satu, dikali seratus persen.",
          tex: String.raw`g_7=\left(\frac{X_t}{X_{t-7\mathrm{d}}}-1\right)\times100\%`,
          math: growth("Perubahan 7 hari", "X", "t−7 hari"),
          definitions:
            "X adalah metrik jaringan yang sama. Pembanding harus tersedia tepat tujuh hari sebelumnya dan positif; tidak ada interpolasi.",
        };
      return null;
  }
}
export default function FundamentalFormula({
  metric,
  symbol,
  expert,
}: {
  metric: string;
  symbol: string;
  expert: boolean;
}) {
  const f = formula(metric, symbol);
  if (!f) return null;
  return (
    <details className="mt-4 rounded-lg border border-line bg-canvas p-4">
      <summary className="cursor-pointer text-xs text-accent hover:underline">
        Cara menghitung · {f.title}
      </summary>
      <div className="mt-4 overflow-x-auto py-3 text-lg text-ink">
        {el(
          "math",
          { xmlns: "http://www.w3.org/1998/Math/MathML", display: "block", "aria-label": f.spoken },
          node("semantics", f.math, el("annotation", { encoding: "application/x-tex" }, f.tex)),
        )}
      </div>
      <p className="mt-3 text-xs leading-6 text-muted">{f.definitions}</p>
      <p className="mt-2 text-xs leading-6 text-muted">Dalam kata-kata: {f.spoken}</p>
      {expert && (
        <details className="mt-3">
          <summary className="cursor-pointer text-xs text-muted">Sumber LaTeX</summary>
          <pre className="mt-2 overflow-x-auto rounded bg-surface p-3 text-xs text-muted">
            <code>{f.tex}</code>
          </pre>
        </details>
      )}
    </details>
  );
}
