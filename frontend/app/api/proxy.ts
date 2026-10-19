// Server-only by import graph: route.ts imports this; client components never do.
const ALLOWED = new Set([
  "dashboard",
  "prices",
  "datasets",
  "forecast",
  "automation",
  "fundamentals",
  "fundamentals/automation",
  "fundamentals/insights",
]);
const PARAMETERS = new Set([
  "symbol",
  "id",
  "dataset_id",
  "model",
  "horizon",
  "snapshot_id",
  "period",
]);
const json = (body: object, status: number) =>
  Response.json(body, {
    status,
    headers: { "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff" },
  });
export function denyWrite() {
  return json(
    {
      error:
        "Demo publik bersifat read-only. Backend automation memperbarui data; jalankan aksi manual dari lingkungan admin/lokal.",
    },
    403,
  );
}
export async function proxyRead(request: Request, segments: string[]) {
  const route = segments.join("/");
  if (!ALLOWED.has(route)) return json({ error: "API route not available" }, 404);
  const configured = process.env.BACKEND_URL || "";
  const token = process.env.BACKEND_API_TOKEN || "";
  if (!configured || token.length < 32)
    return json(
      {
        error:
          "Backend proxy belum dikonfigurasi. Set BACKEND_URL dan BACKEND_API_TOKEN di Vercel, lalu redeploy.",
      },
      503,
    );
  let url: URL;
  try {
    const base = new URL(configured);
    const local =
      process.env.NODE_ENV !== "production" && ["localhost", "127.0.0.1"].includes(base.hostname);
    if (
      (base.protocol !== "https:" && !(base.protocol === "http:" && local)) ||
      base.username ||
      base.password ||
      base.pathname !== "/" ||
      base.search ||
      base.hash
    )
      throw new Error();
    url = new URL(`/api/${route}`, base);
    new URL(request.url).searchParams.forEach((value, key) => {
      if (PARAMETERS.has(key)) url.searchParams.append(key, value);
    });
  } catch {
    return json(
      { error: "BACKEND_URL harus berupa origin HTTPS tanpa path, query atau credentials." },
      503,
    );
  }
  try {
    const response = await fetch(url, {
      method: "GET",
      headers: { Authorization: `Bearer ${token}`, Accept: "application/json" },
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(25000),
    });
    if ([401, 403].includes(response.status))
      return json({ error: "Token koneksi backend tidak cocok. Periksa environment server." }, 502);
    if (!response.headers.get("Content-Type")?.includes("application/json"))
      return json({ error: "Backend mengembalikan format yang tidak diharapkan." }, 502);
    const data = await response.json();
    return json(data, response.status);
  } catch {
    return json(
      { error: "Backend belum dapat dijangkau. Periksa status layanan dan environment Vercel." },
      502,
    );
  }
}
