// node scripts/browser-runtime-smoke.mjs ../.build/publication-viewer
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { createServer } from "node:http";
import { readFile, readdir, writeFile } from "node:fs/promises";
import { resolve, sep } from "node:path";
import { chromium } from "@playwright/test";

const root = resolve(process.argv[2] ?? "../tuba/visualization/_viewer");
const manifest = JSON.parse(await readFile(resolve(root, "pyodide/runtime-manifest.json"), "utf8"));
for (const [name, expected] of Object.entries(manifest.sha256)) {
  assert.equal(createHash("sha256").update(await readFile(resolve(root, "pyodide", name))).digest("hex"), expected);
}
const html = await readFile(resolve(root, "index.html"), "utf8");
const csp = html.match(/<meta http-equiv="Content-Security-Policy"[^>]+>/)?.[0];
assert.ok(csp, "Built viewer must restrict main-document scripts to release-owned assets");
const server = createServer(async (request, response) => {
  try {
    const url = new URL(request.url, "http://127.0.0.1");
    if (url.pathname === "/") {
      response.setHeader("content-type", "text/html");
      response.end(`<!doctype html><html><head>${csp}</head><body></body></html>`);
      return;
    }
    const file = resolve(root, "." + decodeURIComponent(url.pathname));
    assert.ok(file.startsWith(root + sep));
    response.setHeader("content-type", /\.(js|mjs)$/.test(file) ? "text/javascript" : file.endsWith(".wasm") ? "application/wasm" : "application/octet-stream");
    response.end(await readFile(file));
  } catch {
    response.statusCode = 404;
    response.end();
  }
});
await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
let browser;
try {
  const origin = `http://127.0.0.1:${server.address().port}`;
  browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const requests = [];
  page.on("request", request => requests.push(request.url()));
  await page.context().route("**/*", route => new URL(route.request().url()).origin === origin ? route.continue() : route.abort());
  await page.goto(origin);
  const worker = (await readdir(resolve(root, "assets"))).find(name => /^browserPython\.worker-[\w-]+\.js$/.test(name));
  assert.ok(worker);
  const code = await readFile(resolve("../examples/code-aster-review/model.py"), "utf8");
  const result = await page.evaluate(({ code, worker }) => new Promise((resolve, reject) => {
    const runtime = new Worker(`/assets/${worker}`, { type: "module" });
    const timer = setTimeout(() => { runtime.terminate(); reject(new Error("Browser Python timed out")); }, 60_000);
    runtime.onerror = error => { clearTimeout(timer); runtime.terminate(); reject(new Error(error.message)); };
    runtime.onmessage = ({ data }) => {
      if (data.status) return;
      clearTimeout(timer);
      runtime.terminate();
      resolve(data.ok ? { ok: true, objects: data.scene.objects.length, result_fields: data.scene.result_fields.length } : data);
    };
    runtime.postMessage({ code, runtimeUrl: new URL("/tuba-browser.zip", location.href).href });
  }), { code, worker });
  assert.equal(result.ok, true, result.error);
  assert.ok(result.objects > 0);
  assert.equal(result.result_fields, 0);
  assert.ok(requests.some(url => url.endsWith("/pyodide/pyodide.mjs")));
  assert.ok(requests.every(url => new URL(url).origin === origin), "Browser runtime must never request CDN assets");
  const evidence = { origin, runtime_version: manifest.version, ...result, requests };
  await writeFile(resolve("../.build/publication-runtime-browser.json"), JSON.stringify(evidence, null, 2) + "\n");
  console.log(JSON.stringify(evidence));
} finally {
  await browser?.close();
  await new Promise(resolve => server.close(resolve));
}
