// Offline server proxy checks. Never calls real Vercel, Render or market providers.
const assert = require("node:assert/strict"),
  fs = require("node:fs"),
  path = require("node:path"),
  Module = require("node:module"),
  ts = require("typescript");
const filename = path.resolve(__dirname, "../app/api/proxy.ts");
const m = new Module(filename, module);
m.filename = filename;
m.paths = Module._nodeModulePaths(path.dirname(filename));
m._compile(
  ts.transpileModule(fs.readFileSync(filename, "utf8"), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
  }).outputText,
  filename,
);
const { proxyRead, denyWrite } = m.exports;
const previous = {
  url: process.env.BACKEND_URL,
  token: process.env.BACKEND_API_TOKEN,
  node: process.env.NODE_ENV,
  fetch: global.fetch,
};
(async () => {
  try {
    process.env.NODE_ENV = "production";
    process.env.BACKEND_API_TOKEN = "t".repeat(48);
    delete process.env.BACKEND_URL;
    assert.equal(
      (await proxyRead(new Request("https://site.example/api/dashboard"), ["dashboard"])).status,
      503,
    );
    process.env.BACKEND_URL = "https://backend.example";
    assert.equal(
      (await proxyRead(new Request("https://site.example/api/x"), ["..", "health"])).status,
      404,
    );
    assert.equal(denyWrite().status, 403);
    let called = 0;
    global.fetch = async (url, options) => {
      called++;
      assert.equal(url.origin, "https://backend.example");
      assert.equal(url.pathname, "/api/fundamentals/insights");
      assert.equal(url.searchParams.get("symbol"), "BTCUSD");
      assert.equal(url.searchParams.get("api_key"), null);
      assert.equal(options.headers.Authorization, "Bearer " + "t".repeat(48));
      assert.equal(options.headers.Cookie, undefined);
      assert.equal(options.redirect, "error");
      return Response.json({ has_data: true });
    };
    let response = await proxyRead(
      new Request("https://site.example/api/fundamentals/insights?symbol=BTCUSD&api_key=secret", {
        headers: { Authorization: "Bearer attacker", Cookie: "admin=true" },
      }),
      ["fundamentals", "insights"],
    );
    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), { has_data: true });
    assert.equal(called, 1);
    global.fetch = async () => Response.json({ error: "private token detail" }, { status: 401 });
    response = await proxyRead(new Request("https://site.example/api/dashboard"), ["dashboard"]);
    assert.equal(response.status, 502);
    assert.doesNotMatch(await response.text(), /private token detail|tttttttt/);
    process.env.BACKEND_URL = "http://backend.example";
    assert.equal(
      (await proxyRead(new Request("https://site.example/api/dashboard"), ["dashboard"])).status,
      503,
    );
    process.env.BACKEND_URL = "https://user:password@backend.example";
    assert.equal(
      (await proxyRead(new Request("https://site.example/api/dashboard"), ["dashboard"])).status,
      503,
    );
    process.env.BACKEND_URL = "https://backend.example/path";
    assert.equal(
      (await proxyRead(new Request("https://site.example/api/dashboard"), ["dashboard"])).status,
      503,
    );
    process.env.BACKEND_URL = "https://backend.example";
    global.fetch = async () => {
      throw new Error("secret-url-and-token");
    };
    response = await proxyRead(new Request("https://site.example/api/dashboard"), ["dashboard"]);
    assert.equal(response.status, 502);
    assert.doesNotMatch(await response.text(), /secret-url-and-token/);
    console.log(
      "PASS: proxy allowlist, write denial, server credential forwarding, query filtering, redirect policy and safe errors.",
    );
  } finally {
    for (const [key, value] of [
      ["BACKEND_URL", previous.url],
      ["BACKEND_API_TOKEN", previous.token],
      ["NODE_ENV", previous.node],
    ]) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
    global.fetch = previous.fetch;
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
