// Read-only timing against a running Studio and its real retained review.
// node scripts/navigation-perf.mjs <Studio URL> <output-directory>
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { chromium, expect } from "@playwright/test";

const [url, output] = process.argv.slice(2);
if (!url || !output) throw new Error("Pass a running Studio URL and an evidence directory.");
const directory = resolve(output);
await mkdir(directory, { recursive: true });
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await context.newPage();
const errors = [], writes = [], requests = [];
page.on("pageerror", error => errors.push(error.message));
await context.route("**/api/**", async route => {
  if (!["GET", "HEAD"].includes(route.request().method())) {
    writes.push(new URL(route.request().url()).pathname);
    await route.abort();
  } else await route.continue();
});
page.on("request", request => {
  if (new URL(request.url()).pathname.endsWith("/scene.json")) requests.push(new URL(request.url()).pathname);
});
await page.addInitScript(() => {
  window.__navigationTasks = [];
  new PerformanceObserver(list => window.__navigationTasks.push(...list.getEntries().map(entry =>
    ({ start: entry.startTime, duration: entry.duration })))).observe({ type: "longtask", buffered: true });
});
const sourceHash = async () => {
  const response = await context.request.get(new URL("/api/script", url).href);
  assert.equal(response.status(), 200);
  return createHash("sha256").update((await response.json()).code).digest("hex");
};

try {
  const originalSource = await sourceHash();
  await page.goto(url);
  await expect(page.locator("[data-runtime-status]")).toContainText("Live preview connected", { timeout: 60_000 });
  await expect(page.locator("body")).toHaveAttribute("data-studio", "true");
  const samples = [];
  for (const [index, stage] of ["build", "review", "build", "review", "build", "review", "build", "review"].entries()) {
    const requestCount = requests.length;
    const started = performance.now();
    await page.locator(`button[data-mode=${stage}]`).click({ timeout: 60_000 });
    await expect(page.locator("body")).toHaveAttribute("data-mode", stage, { timeout: 60_000 });
    await expect(page.locator("[data-mode-switch]")).toHaveAttribute("aria-busy", "false", { timeout: 60_000 });
    // Include the next painted frame, rather than just the DOM attribute flip.
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    const ms = performance.now() - started;
    const state = await page.evaluate(() => ({
      scene: window.__tubaViewer.state.sceneId,
      objects: window.__tubaViewer.state.objects.length,
      fields: window.__tubaViewer.state.resultFields.length,
      rendered: window.__tubaViewer.lastRender.renderableCount,
      loadCase: window.__tubaViewer.state.activeLoadCase,
      resultState: window.__tubaViewer.state.activeResultStateId
    }));
    const sample = { stage, warm: index >= 2, ms: Math.round(ms), sceneRequests: requests.length - requestCount, state };
    samples.push(sample);
    console.log(`${sample.warm ? "warm" : "first"} ${stage}: ${sample.ms} ms, ${sample.sceneRequests} scene requests`);
  }
  assert.deepEqual(errors, []);
  assert.deepEqual(writes, []);
  assert.equal(await sourceHash(), originalSource, "authored source remains unchanged");
  for (const stage of ["build", "review"]) {
    const states = samples.filter(sample => sample.stage === stage).map(sample => sample.state);
    for (const state of states.slice(1)) assert.deepEqual(state, states[0], "stage retains the same model and result identity");
  }
  const warm = samples.filter(sample => sample.warm);
  const report = {
    page: new URL(url).origin, viewport: { width: 1440, height: 900 }, samples,
    warmMedianMs: [...warm.map(sample => sample.ms)].sort((a, b) => a - b)[Math.floor(warm.length / 2)],
    warmSceneRequests: warm.reduce((count, sample) => count + sample.sceneRequests, 0),
    longTasks: await page.evaluate(() => window.__navigationTasks), errors, writes, sourceUnchanged: true
  };
  await writeFile(resolve(directory, "navigation-perf.json"), JSON.stringify(report, null, 2));
  await page.screenshot({ path: resolve(directory, "review.png") });
  console.log(`Warm median: ${report.warmMedianMs} ms; scene requests: ${report.warmSceneRequests}`);
} finally {
  await browser.close();
}
