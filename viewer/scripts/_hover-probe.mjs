import { createServer } from "vite";
import { chromium } from "@playwright/test";

const viewerRoot = "D:\\Gitprojects\\Tuba_v4\\viewer";

const server = await createServer({
  root: viewerRoot,
  logLevel: "error",
  server: { host: "127.0.0.1", port: 15998, strictPort: false }
});
await server.listen();
const baseUrl = server.resolvedUrls.local[0];
const browser = await chromium.launch({ headless: true });

async function pixelAt(page, x, y) {
  return page.evaluate(([px, py]) => {
    const canvas = document.querySelector("[data-canvas]");
    const gl = canvas.getContext("webgl2") || canvas.getContext("webgl");
    const rect = canvas.getBoundingClientRect();
    const dpr = gl.drawingBufferWidth / rect.width;
    const sx = Math.round((px - rect.left) * dpr);
    const sy = Math.round((rect.height - (py - rect.top)) * dpr);
    const out = new Uint8Array(4);
    gl.readPixels(sx, sy, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, out);
    return [out[0], out[1], out[2], out[3]];
  }, [x, y]);
}

async function probe(label, bundle) {
  const page = await browser.newPage({ viewport: { height: 800, width: 1280 } });
  await page.goto(`${baseUrl}?bundle=${bundle}`, { waitUntil: "domcontentloaded" });
  await page.waitForFunction(() => /Ready/.test(document.querySelector("[data-runtime-status]")?.textContent ?? ""), null, { timeout: 20000 });
  await page.waitForFunction(() => document.querySelector("[data-canvas]")?.dataset.renderer === "three", null, { timeout: 20000 });
  await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
  const canvas = page.locator("[data-canvas]");
  const box = await canvas.boundingBox();
  const rendered = await page.evaluate(() => Number(document.querySelector("[data-canvas]")?.dataset.renderedObjects ?? 0));
  console.log(`\n[${label}] renderedObjects=${rendered}`);
  for (const [fx, fy] of [[0.5, 0.5], [0.35, 0.45], [0.6, 0.55], [0.45, 0.4], [0.55, 0.6], [0.4, 0.6], [0.65, 0.4]]) {
    const x = box.x + box.width * fx;
    const y = box.y + box.height * fy;
    await page.mouse.move(box.x + 5, box.y + 5);
    await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
    const before = await pixelAt(page, x, y);
    await page.mouse.move(x, y);
    await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
    const hovered = await page.evaluate(() => document.querySelector("[data-canvas]")?.dataset.hoverObjectId ?? "");
    const after = await pixelAt(page, x, y);
    const changed = before.join(",") !== after.join(",");
    console.log(`  ${fx},${fy} ${hovered || "(none)"} before=${before} after=${after} ${changed ? "CHANGED" : "same"}`);
  }
  await page.close();
}

await probe("code_aster_results (review fixture)", "/test/fixtures/code_aster_results");
await probe("smoke_scene (model fixture)", "/test/fixtures/smoke_scene");

await browser.close();
await server.close();
