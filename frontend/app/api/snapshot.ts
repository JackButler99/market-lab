// Server-side reader for a public normalized snapshot. No provider credentials needed.
type RecordData = {
  asset?: { symbol: string; dataset_id: string };
  dataset?: { dataset_id: string };
  prices?: unknown[];
  forecasts?: Record<string, unknown>;
  fundamentals: {
    saved: { snapshot_id?: string; has_data: boolean };
    insights: Record<string, unknown>;
  };
};
type Bundle = {
  schema: number;
  generated_at: string;
  symbols: Record<string, RecordData>;
  dashboard: unknown;
  automation: unknown;
  fundamental_automation: unknown;
};
const reply = (body: unknown, status = 200) => Response.json(body, {
  status, headers: { "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff" },
});
export function selectSnapshot(bundle: Bundle, route: string, params: URLSearchParams): Response {
  const generated = Date.parse(bundle.generated_at);
  const age = Date.now() - generated;
  const meta = { generated_at: bundle.generated_at, snapshot_stale: age > 12 * 3600000 };
  if (route === "snapshot-status") return reply(meta);
  if (route === "dashboard") return reply(bundle.dashboard);
  if (route === "automation") return reply({ ...(bundle.automation as object), ...meta });
  if (route === "fundamentals/automation") return reply({ ...(bundle.fundamental_automation as object), ...meta });
  const symbol = params.get("symbol") || "AAPL";
  const record = bundle.symbols[symbol];
  if (route === "datasets" && params.has("id")) {
    const dataset = Object.values(bundle.symbols).find(r => r.dataset?.dataset_id === params.get("id"))?.dataset;
    return dataset ? reply(dataset) : reply({ error: "Dataset not included in current snapshot" }, 404);
  }
  if (!["prices", "datasets", "forecast", "fundamentals", "fundamentals/insights"].includes(route))
    return reply({ error: "API route not available" }, 404);
  if (!record) return reply({ error: "No published data for this asset yet" }, 404);
  if (route === "prices") return reply(record.prices || []);
  if (route === "datasets") {
    const detail = record.dataset;
    if (!detail) return reply([]);
    const { prices: _prices, ...summary } = detail as typeof detail & { prices?: unknown };
    return reply([summary]);
  }
  if (route === "forecast") {
    if (params.get("dataset_id") !== record.dataset?.dataset_id) return reply(null);
    return reply(record.forecasts?.[(params.get("model") || "trend") + ":" + (params.get("horizon") || "7")] || null);
  }
  if (route === "fundamentals") return reply(record.fundamentals.saved);
  if (params.has("snapshot_id") && params.get("snapshot_id") !== record.fundamentals.saved.snapshot_id)
    return reply({ error: "Snapshot changed; reload the Fundamentals tab" }, 409);
  if (params.has("period") && ["BTCUSD", "EURUSD"].includes(symbol))
    return reply({ error: "Annual periods apply to equities only" }, 400);
  const insight = record.fundamentals.insights[params.get("period") || "latest"];
  return insight ? reply(insight) : reply({ error: "Annual period unavailable" }, 404);
}
export async function snapshotRead(request: Request, segments: string[]): Promise<Response> {
  const repository = process.env.SNAPSHOT_REPOSITORY || "";
  if (!/^[a-zA-Z0-9_.-]+\/[a-zA-Z0-9_.-]+$/.test(repository))
    return reply({ error: "Set SNAPSHOT_REPOSITORY=owner/repository in Vercel and redeploy." }, 503);
  try {
    const options: RequestInit & { next: { revalidate: number } } = {
      next: { revalidate: 300 }, redirect: "error", signal: AbortSignal.timeout(15000),
    };
    const response = await fetch(`https://raw.githubusercontent.com/${repository}/market-data/bundle.json`, options);
    if (!response.ok) throw new Error();
    const text = await response.text();
    if (text.length > 15000000) throw new Error();
    const bundle = JSON.parse(text) as Bundle;
    if (bundle.schema !== 1 || !bundle.symbols || !Number.isFinite(Date.parse(bundle.generated_at))) throw new Error();
    return selectSnapshot(bundle, segments.join("/"), new URL(request.url).searchParams);
  } catch {
    return reply({ error: "Public snapshot unavailable. Run Refresh public market snapshots in GitHub Actions; check repository visibility and workflow logs." }, 503);
  }
}
