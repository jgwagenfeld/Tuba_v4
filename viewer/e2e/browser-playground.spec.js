import { test, expect } from "@playwright/test";
import { readFile, readdir } from "node:fs/promises";
import { resolve } from "node:path";

test("gallery scripts build in the browser or explicitly require a native package", async ({ page, request }) => {
  test.setTimeout(300_000);
  await page.goto("/viewer/");
  const catalog = await (await request.get("/viewer/bundles.json")).json();
  const siteRoot = resolve(process.env.TUBA_PAGES_SITE_ROOT?.trim() || "../.build/pages-check");
  const workers = (await readdir(resolve(siteRoot, "viewer/assets")))
    .filter(name => /^browserPython\.worker-[\w-]+\.js$/.test(name));
  expect(workers).toHaveLength(1);
  const [workerFile] = workers;
  for (const entry of catalog) {
    const code = await (await request.get(`/viewer/${entry.id}/source.py`)).text();
    const result = await page.evaluate(({ code, workerFile }) => new Promise((resolve, reject) => {
      const worker = window.previewWorker ??= new Worker(new URL(`assets/${workerFile}`, location.href), { type: "module" });
      const timer = setTimeout(() => { worker.terminate(); reject(new Error("Timed out")); }, 60_000);
      worker.onmessage = ({ data }) => {
        if (data.status) return;
        clearTimeout(timer);
        if (!data.ok) { worker.terminate(); window.previewWorker = null; }
        resolve(data.ok ? { ok: true, objects: data.scene.objects.length, results: data.scene.result_fields.length } : data);
      };
      worker.onerror = event => { clearTimeout(timer); worker.terminate(); reject(new Error(event.message)); };
      worker.postMessage({ code, runtimeUrl: new URL("tuba-browser.zip", location.href).href });
    }), { code, workerFile });
    console.log(entry.id, result);
    if (!result.ok) {
      expect(entry.id).toBe("imported_component_mixed_demo");
      expect(result.error).toContain("native package unavailable in the browser");
    } else {
      expect(result.objects).toBeGreaterThan(0);
      expect(result.results).toBe(0);
    }
  }
});

test("public gallery runs Python geometry, keeps solved review separate, and recovers from errors", async ({ page }) => {
  test.setTimeout(180_000);
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/viewer/?bundle=code-aster-review");
  await expect(page.locator("[data-runtime-status]")).toHaveText("Ready");
  const workers = [];
  page.on("worker", worker => workers.push(worker));
  const originalObjects = await page.evaluate(() => JSON.stringify(window.__tubaViewer.state.objects));
  await page.getByRole("button", { name: "Build", exact: true }).click();
  const editor = page.locator("[data-code-text]");
  const run = page.locator("[data-code-run]");
  const original = await editor.inputValue();
  const edited = original.replace("builder.run(3.0)", "builder.run(5.0)")
    .replace('builder.end(support="anchor")', 'builder.end(support="guide")');
  await editor.fill(edited + '\nimport tuba\ntuba._preview_marker = True\n_preview_global = True\nfrom pathlib import Path\nPath("run-only.txt").write_text("temporary")\n');
  const coldStart = Date.now();
  await run.click();
  await expect(page.locator("[data-code-state]")).toHaveText("Geometry preview", { timeout: 90_000 });
  const coldMs = Date.now() - coldStart;
  await editor.fill(edited + '\nimport tuba\nassert not hasattr(tuba, "_preview_marker")\nassert "_preview_global" not in globals()\nfrom pathlib import Path\nassert not Path("run-only.txt").exists()\n');
  const warmStart = Date.now();
  await run.click();
  await expect(page.locator("[data-code-state]")).toHaveText("Geometry preview", { timeout: 90_000 });
  console.log(`Geometry update: cold ${coldMs} ms, warm ${Date.now() - warmStart} ms`);
  expect(workers).toHaveLength(1);
  await editor.fill(edited);
  await run.click();
  await expect(page.locator("[data-code-state]")).toHaveText("Geometry preview");
  const preview = await page.evaluate(() => {
    const state = window.__tubaViewer.state;
    return { length: state.objects.find(o => o.name === "pipe_str_0").quantities.length_m,
      support: state.objects.find(o => o.name === "support_3").metadata.support_type,
      results: state.resultFields.length, review: state.review };
  });
  expect(preview).toEqual({ length: 5, support: "guide", results: 0, review: null });
  await expect(page.locator("[data-status-chip] [data-status]")).toHaveAttribute("data-status", "not_solved");
  await expect(page.locator("[data-viewport-legend]")).not.toContainText("Von Mises");
  const previewObjects = await page.evaluate(() => JSON.stringify(window.__tubaViewer.state.objects));
  await page.screenshot({ path: "../.build/browser-geometry-preview.png" });

  await page.getByRole("button", { name: "Review", exact: true }).click();
  expect(await page.evaluate(() => JSON.stringify(window.__tubaViewer.state.objects))).toBe(originalObjects);
  expect(await page.evaluate(() => window.__tubaViewer.state.resultFields.length)).toBeGreaterThan(0);
  await expect(page.locator("[data-status-chip] [data-status]")).toHaveAttribute("data-status", "stale");
  await page.getByRole("button", { name: "Build", exact: true }).click();
  expect(await page.evaluate(() => JSON.stringify(window.__tubaViewer.state.objects))).toBe(previewObjects);
  const downloading = page.waitForEvent("download");
  await page.getByRole("button", { name: "Exchange", exact: true }).click();
  await page.getByRole("button", { name: "Download model.py", exact: true }).click();
  await page.getByRole("button", { name: "Close exchange", exact: true }).click();
  expect(await readFile(await (await downloading).path(), "utf8")).toBe(edited);

  await editor.fill("def broken(:\n");
  await run.click();
  await expect(page.locator("[data-code-problem]")).toContainText("Line 1", { timeout: 90_000 });
  expect(await page.evaluate(() => JSON.stringify(window.__tubaViewer.state.objects))).toBe(previewObjects);

  await editor.fill("import gmsh\n" + edited);
  await run.click();
  await expect(page.locator("[data-code-problem]")).toContainText("gmsh", { timeout: 90_000 });
  expect(await page.evaluate(() => JSON.stringify(window.__tubaViewer.state.objects))).toBe(previewObjects);

  await editor.fill("while True:\n    pass\n");
  await run.click();
  await expect(page.locator("[data-code-state]")).toHaveText("Building geometry…", { timeout: 90_000 });
  await run.click();
  await expect(run).toHaveText("Update geometry");
  expect(await page.evaluate(() => JSON.stringify(window.__tubaViewer.state.objects))).toBe(previewObjects);
  await page.getByRole("button", { name: "Exchange", exact: true }).click();
  await page.getByText("Example actions", { exact: true }).click();
  await page.getByRole("button", { name: "Reset example", exact: true }).click();
  await expect(editor).toHaveValue(original);
  expect(await page.evaluate(() => JSON.stringify(window.__tubaViewer.state.objects))).toBe(originalObjects);
  await expect(page.locator("[data-status-chip] [data-status]")).not.toHaveAttribute("data-status", "stale");
  expect(errors).toEqual([]);
});

test("switching examples cancels a running browser script and failed runtime loading can be retried", async ({ page }) => {
  test.setTimeout(120_000);
  await page.goto("/viewer/?bundle=code-aster-review");
  await expect(page.locator("[data-runtime-status]")).toHaveText("Ready");
  await page.getByRole("button", { name: "Build", exact: true }).click();
  await page.evaluate(() => {
    window.originalWorker = window.Worker;
    window.Worker = class { constructor() { throw new Error("Worker blocked by browser policy"); } };
  });
  await page.locator("[data-code-run]").click();
  await expect(page.locator("[data-code-problem]")).toContainText("Worker blocked by browser policy");
  await expect(page.locator("[data-code-run]")).toHaveText("Update geometry");
  await page.evaluate(() => { window.Worker = window.originalWorker; delete window.originalWorker; });
  await page.route("**/pyodide.mjs", route => route.abort());
  await page.locator("[data-code-run]").click();
  await expect(page.locator("[data-code-problem]")).toBeVisible({ timeout: 30_000 });
  await expect(page.locator("[data-code-run]")).toHaveText("Update geometry");
  await page.unroute("**/pyodide.mjs");
  await page.locator("[data-code-text]").fill("while True:\n    pass\n");
  await page.locator("[data-code-run]").click();
  await expect(page.locator("[data-code-state]")).toHaveText("Building geometry…", { timeout: 90_000 });
  await page.getByRole("button", { name: "Review", exact: true }).click();
  await page.locator("[data-bundle-picker]").selectOption("guyed-mast-review");
  await expect(page.locator("[data-runtime-status]")).toHaveText("Ready");
  await page.getByRole("button", { name: "Build", exact: true }).click();
  await expect(page.locator("[data-code-text]")).not.toHaveValue("while True:\n    pass\n");
  await expect(page.locator("[data-code-run]")).toHaveText("Update geometry");
  await expect(page.locator("[data-code-problem]")).toBeHidden();
  await page.locator("[data-code-run]").click();
  await expect(page.locator("[data-code-state]")).toHaveText("Geometry preview", { timeout: 90_000 });
  expect(await page.evaluate(() => window.__tubaViewer.state.sceneId)).toBe("scene:Guyed_Mast_Review");
});
