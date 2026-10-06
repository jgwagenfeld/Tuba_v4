// Focused native Studio qualification. Usage: node scripts/mesh-review.mjs READY PROJECT EVIDENCE
import assert from "node:assert/strict";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { chromium } from "playwright";

const [readyFile, project, evidence] = process.argv.slice(2);
if (!readyFile || !project || !evidence) throw new Error("Pass viewer ready JSON, authored project and evidence directory.");
const ready = JSON.parse(readFileSync(readyFile, "utf8"));
const sourcePath = join(project, "model.py");
const studyPath = join(project, "study.py");
const source = readFileSync(sourcePath, "utf8");
const study = readFileSync(studyPath, "utf8");
mkdirSync(evidence, { recursive: true });
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
const served = [];
page.on("pageerror", error => errors.push(error.message));
page.on("response", response => {
  if (/\/api\/mesh$|\/build\/scene\.json$|\/src\/meshReview\.js/.test(new URL(response.url()).pathname)) {
    served.push({ url: response.url(), status: response.status(), content_type: response.headers()["content-type"] });
  }
});
const snapshot = async name => {
  await page.screenshot({ path: join(evidence, `${name}.png`), fullPage: true });
  const state = await page.evaluate(() => ({
    objects: window.__tubaViewer?.state.objects.length,
    rendered: window.__tubaViewer?.lastRender.renderableCount,
    renderedIds: window.__tubaViewer?.lastRender.objectIds,
    diagnostics: window.__tubaViewer?.lastRender.diagnostics,
    mesh: document.querySelector("[data-mesh-review]")?.innerText
  }));
  writeFileSync(join(evidence, `${name}.json`), JSON.stringify(state, null, 2));
  console.log(name, state.mesh?.replace(/\n/g, " | "));
};
const panel = page.locator("[data-mesh-review]");
// The panel lives in the dock the status strip's mesh toggle opens.
const openMeshDetail = async () => {
  await page.waitForFunction(() => document.querySelector("[data-analysis-summary]")?.hidden === false);
  if (await page.locator("[data-analysis-summary]").getAttribute("aria-expanded") !== "true") await page.locator("[data-analysis-summary]").click();
};
const current = async () => (await page.request.get(new URL("/api/mesh", ready.base_url).href)).json();
async function waitState(state) {
  await page.waitForFunction(expected => document.querySelector("[data-mesh-status]")?.dataset.meshState === expected, state, { timeout: 120000 });
  const job = await current();
  assert.equal(job.state, state);
  return job;
}
try {
  const response = await page.goto(ready.viewer_url);
  assert.match(response.headers()["content-type"], /text\/html/);
  served.push({ url: ready.viewer_url, status: response.status(), content_type: response.headers()["content-type"] });
  await openMeshDetail();
  await panel.waitFor({ state: "visible" });
  await page.waitForFunction(() => window.__tubaViewer?.lastRender.renderableCount > 0);
  assert.match(await panel.innerText(), /unsolved/);
  assert.match(await panel.innerText(), /outlet_detail/);
  assert.match(await panel.innerText(), /0.0025 m/);
  await page.getByRole("checkbox", { name: "Requested sizing", exact: true }).check();
  // Hide the existing 80 mm minimum support glyph on this deliberately tiny diagnostic fixture.
  await page.getByText("Display", { exact: true }).click();
  await page.getByRole("checkbox", { name: "Supports & BCs", exact: true }).uncheck();
  await page.getByText("Display", { exact: true }).click();
  await panel.getByRole("button", { name: /outlet_detail/ }).click();
  await page.waitForFunction(() => window.__tubaViewer.state.selectedObjectIds.length > 0);
  await page.getByRole("button", { name: "Fit selected", exact: true }).click();
  assert.ok(await page.evaluate(() => window.__tubaViewer.lastRender.objectIds.some(id => id.startsWith("object:mesh_size:"))));
  await snapshot("01-requested-sizing");
  await panel.getByRole("button", { name: "Generate mesh", exact: true }).click();
  const generated = await waitState("succeeded");
  assert.equal(generated.current, true);
  assert.match(await panel.innerText(), /HEXA20/);
  assert.match(await panel.innerText(), /minSJ/);
  await page.locator("[data-code-mesh-toggle]").click();
  await page.waitForFunction(() => window.__tubaViewer.lastRender.objectIds.some(id => id.includes("volume_skin")));
  await snapshot("02-generated-mesh");
  // Cancellation is native and named; no previous mesh remains current during remesh.
  await panel.getByRole("button", { name: "Regenerate mesh", exact: true }).click();
  await panel.getByRole("button", { name: "Cancel mesh job", exact: true }).click();
  assert.equal((await waitState("cancelled")).current, false);
  await page.waitForFunction(() => !window.__tubaViewer.state.objects.some(o => o.kind === "analysis_mesh_surface"));
  await snapshot("03-cancelled");
  await page.waitForFunction(async () => !(await (await fetch("/api/mesh")).json()).busy);
  await panel.getByRole("button", { name: "Generate mesh", exact: true }).click();
  await waitState("succeeded");
  writeFileSync(sourcePath, source.replace(".0025", ".0024"));
  assert.equal((await waitState("stale")).current, false);
  await page.waitForFunction(() => !window.__tubaViewer.state.objects.some(o => o.kind === "analysis_mesh_surface"));
  await snapshot("04-stale-source");
  // Real worker failure, using an authored unsupported element order.
  const priorRevision = (await current()).loaded_source_revision;
  writeFileSync(studyPath, study.replace('"element_order":2', '"element_order":1'));
  await page.waitForFunction(previous => Number(document.querySelector("[data-mesh-review]")?.dataset.sourceRevision) > previous, priorRevision);
  await page.waitForFunction(() => document.querySelector("[data-mesh-review]")?.innerText.includes("0.0024 m"));
  await panel.getByRole("button", { name: "Generate mesh", exact: true }).click();
  assert.equal((await waitState("failed")).current, false);
  assert.match(await panel.innerText(), /element_order=2/);
  await snapshot("05-worker-error");
  writeFileSync(sourcePath, source + "\nraise ValueError('Authored source is invalid for this diagnostic check')\n");
  await page.locator("[data-code-problem]").waitFor({ state: "visible" });
  await page.waitForFunction(() => document.querySelector('[data-focus-key="mesh-generate"]')?.disabled === true);
  assert.equal((await current()).current, false);
  await snapshot("06-source-error");
  assert.deepEqual(errors, []);
  assert.ok(served.some(item => item.url.endsWith("/api/mesh") && item.content_type === "application/json"));
  assert.ok(served.some(item => item.url.endsWith("/build/scene.json") && item.content_type.includes("application/json")));
  writeFileSync(join(evidence, "browser-summary.json"), JSON.stringify({ passed: true, served, errors, generated }, null, 2));
} catch (failure) {
  await snapshot("failure");
  writeFileSync(join(evidence, "failure-summary.json"), JSON.stringify({ error: failure.message, served, errors,
    document: await page.locator("body").innerText() }, null, 2));
  throw failure;
} finally {
  writeFileSync(sourcePath, source);
  writeFileSync(studyPath, study);
  await browser.close();
}
