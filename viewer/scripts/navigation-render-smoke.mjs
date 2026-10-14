// Count completed 3D draws, including queued frames, against a real Studio.
// node scripts/navigation-render-smoke.mjs <Studio URL> <evidence-directory>
import assert from "node:assert/strict";
import { chromium, expect } from "@playwright/test";
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

const [url, output] = process.argv.slice(2);
if (!url || !output) throw new Error("Pass a running Studio URL and an evidence directory.");
await mkdir(resolve(output), { recursive: true });
const browser = await chromium.launch({ headless: true });
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  const errors = [], writes = [], samples = [];
  page.on("pageerror", error => errors.push(error.message));
  await context.route("**/api/**", async route => {
    if (!["GET", "HEAD"].includes(route.request().method())) {
      writes.push(new URL(route.request().url()).pathname);
      await route.abort();
    } else await route.continue();
  });
  await page.goto(url);
  await expect(page.locator("[data-runtime-status]")).toContainText("Live preview connected", { timeout: 60_000 });
  await page.evaluate(() => {
    window.__drawCount = 0;
    const canvas = document.querySelector("canvas[data-viewport]") ?? document.querySelector("canvas");
    // drawFrame publishes this camera diagnostic once after each complete draw.
    new MutationObserver(records => window.__drawCount += records.length)
      .observe(canvas, { attributes: true, attributeFilter: ["data-camera-direction"] });
  });
  const painted = () => page.evaluate(() => new Promise(resolve =>
    requestAnimationFrame(() => requestAnimationFrame(resolve))));
  const stage = async mode => {
    await page.locator(`button[data-mode=${mode}]`).click();
    await expect(page.locator("body")).toHaveAttribute("data-mode", mode, { timeout: 60_000 });
    await expect(page.locator("[data-mode-switch]")).toHaveAttribute("aria-busy", "false", { timeout: 60_000 });
    await painted();
  };
  await stage("build"); await stage("review");
  for (const mode of ["build", "review", "build", "review"]) {
    await page.evaluate(() => window.__drawCount = 0);
    await stage(mode);
    samples.push({ mode, draws: await page.evaluate(() => window.__drawCount) });
  }
  const canvas = page.locator("canvas[data-renderer=three]");
  await canvas.focus();
  const previousDirection = await canvas.getAttribute("data-camera-direction");
  await page.keyboard.press("ArrowRight");
  await expect(canvas).not.toHaveAttribute("data-camera-direction", previousDirection);
  await page.setViewportSize({ width: 1200, height: 800 });
  await painted();
  const size = await canvas.evaluate(canvas => ({ width: canvas.width, height: canvas.height,
    cssWidth: Math.floor(canvas.clientWidth), cssHeight: Math.floor(canvas.clientHeight) }));
  assert.equal(size.width, size.cssWidth);
  assert.equal(size.height, size.cssHeight);
  const receipt = { samples, cameraResponsive: true, resizeCorrect: true, errors, writes };
  await writeFile(resolve(output, "navigation-render.json"), JSON.stringify(receipt, null, 2));
  console.log(JSON.stringify(receipt));
  assert.deepEqual(errors, []); assert.deepEqual(writes, []);
  for (const sample of samples) assert.equal(sample.draws, 1, `${sample.mode} should draw once after updating the scene`);
} finally { await browser.close(); }
