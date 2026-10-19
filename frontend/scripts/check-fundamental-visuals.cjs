// Offline geometry, accessible SVG markup and native equation rendering checks.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const ts = require("typescript");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");
const cache = new Map();
function load(file) {
  file = path.resolve(file);
  if (cache.has(file)) return cache.get(file).exports;
  const m = new Module(file, module);
  cache.set(file, m);
  m.filename = file;
  m.paths = Module._nodeModulePaths(path.dirname(file));
  m.require = function (id) {
    if (id.startsWith(".")) {
      for (const suffix of [".tsx", ".ts"]) {
        const candidate = path.resolve(path.dirname(file), id + suffix);
        if (fs.existsSync(candidate)) return load(candidate);
      }
    }
    return Module.prototype.require.call(m, id);
  };
  m._compile(
    ts.transpileModule(fs.readFileSync(file, "utf8"), {
      compilerOptions: {
        target: ts.ScriptTarget.ES2022,
        module: ts.ModuleKind.CommonJS,
        jsx: ts.JsxEmit.ReactJSX,
      },
    }).outputText,
    file,
  );
  return m.exports;
}
const app = path.resolve(__dirname, "../app");
const { chartDomain, lineSegments } = load(path.join(app, "fundamental-chart-utils.ts"));
assert.deepEqual(chartDomain([0, 0], true), [0, 1]);
assert.equal(chartDomain([100, 200], true)[0], 0);
assert.ok(chartDomain([-50, 100], true)[0] < -50);
assert.ok(
  chartDomain([100, 100.00000000000001], false)[1] -
    chartDomain([100, 100.00000000000001], false)[0] >
    0.9,
);
assert.equal(
  lineSegments(
    [
      { date: "2026-10-01", value: 1 },
      { date: "2026-10-03", value: 2 },
    ],
    1,
  ).length,
  2,
);
assert.equal(
  lineSegments(
    [
      { date: "2026-10-01", value: 1 },
      { date: "2026-10-02", value: null },
      { date: "2026-10-03", value: 2 },
    ],
    4,
  ).length,
  2,
);
const Formula = load(path.join(app, "fundamental-formula.tsx")).default;
for (const [metric, symbol] of [
  ["net_margin", "AAPL"],
  ["revenue", "AAPL"],
  ["free_cash_flow", "MSFT"],
  ["rate_spread", "EURUSD"],
  ["us_inflation", "EURUSD"],
  ["hash-rate", "BTCUSD"],
]) {
  const html = renderToStaticMarkup(React.createElement(Formula, { metric, symbol, expert: true }));
  assert.match(html, /<math/);
  assert.match(html, /application\/x-tex/);
  assert.match(html, /Dalam kata-kata/);
  if (["net_margin", "revenue", "us_inflation", "hash-rate"].includes(metric))
    assert.match(html, /<mfrac>/);
}
const Chart = load(path.join(app, "fundamental-chart.tsx")).default;
function render(values) {
  return renderToStaticMarkup(
    React.createElement(Chart, {
      visual: {
        card_id: "cash",
        title: "Kas operasi",
        unit: "USD",
        kind: "bar",
        frequency: "annual",
        max_gap_days: 4,
        zero_baseline: true,
        note: "Periode yang dilaporkan",
        series: [
          {
            id: "cfo",
            label: "CFO",
            points: values.map((value, index) => ({ date: `202${index + 3}-09-30`, value })),
          },
        ],
      },
    }),
  );
}
for (const values of [
  [0, 0],
  [-20, 30],
  [null, 20],
]) {
  const html = render(values);
  assert.doesNotMatch(html, /NaN|Infinity/);
  assert.match(html, /Lihat tabel angka grafik/);
  assert.match(html, /scope="col"/);
  assert.match(html, /tabindex="0"/);
}
assert.match(render([null, null]), /Belum cukup observasi/);
console.log(
  "PASS: chart domains, missing-data gaps, MathML/LaTeX markup, zero/negative bars, keyboard targets and data tables.",
);

assert.match(render([20, null]), /2024-09-30/); // Missing latest annual period stays in the table.
if (process.argv.includes("--svg-preview")) {
  const directory = path.resolve(__dirname, "../../../.chart-qa");
  fs.mkdirSync(directory, { recursive: true });
  const html = render([-20, 30]);
  const svg = html
    .match(/<svg[\s\S]*?<\/svg>/)[0]
    .replace("<svg ", '<svg xmlns="http://www.w3.org/2000/svg" ');
  fs.writeFileSync(path.join(directory, "chart.svg"), svg.replace('width="100%"', 'width="480"'));
}
