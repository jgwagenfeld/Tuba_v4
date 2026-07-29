import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const VIEWPORTS = {
  desktop: { width: 1440, height: 900 },
  compact: { width: 1024, height: 768 },
  narrow: { width: 800, height: 900 }
};

test("assembled Pages viewer is accessible and visually stable", async ({ page }) => {
  const browserErrors = [];
  page.on("pageerror", (error) => browserErrors.push(`pageerror: ${error.message}`));
  page.on("console", (message) => {
    if (message.type() === "error") browserErrors.push(`console: ${message.text()}`);
  });
  page.on("requestfailed", (request) => {
    browserErrors.push(`requestfailed: ${request.url()} ${request.failure()?.errorText ?? "unknown"}`);
  });

  await page.goto("/viewer/?bundle=code-aster-review", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("status")).toHaveText("Ready");
  await page.waitForFunction(() => {
    const canvas = document.querySelector("[data-canvas]");
    return (
      canvas?.dataset.renderer === "three" &&
      Number(canvas.dataset.renderedObjects ?? 0) > 0 &&
      canvas.dataset.renderDiagnostics === "0"
    );
  });
  await page.evaluate(() => document.fonts.ready);
  const typography = await page.evaluate(() => ({
    loadedFamilies: [...document.fonts].filter((font) => font.status === "loaded").map((font) => font.family),
    ui: getComputedStyle(document.body).fontFamily,
    mono: getComputedStyle(document.querySelector(".runtime-status")).fontFamily
  }));
  expect(typography.loadedFamilies).toContain("Roboto Condensed");
  expect(typography.loadedFamilies).toContain("IBM Plex Mono");
  expect(typography.ui).toBe('"Roboto Condensed", sans-serif');
  expect(typography.mono).toBe('"IBM Plex Mono", monospace');

  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(accessibility.violations).toEqual([]);

  for (const [name, viewport] of Object.entries(VIEWPORTS)) {
    await page.setViewportSize(viewport);
    await page.waitForFunction(() => {
      const canvas = document.querySelector("[data-canvas]");
      const gl = canvas?.getContext("webgl2") || canvas?.getContext("webgl");
      return Boolean(
        gl &&
        canvas.clientWidth > 0 &&
        canvas.clientHeight > 0 &&
        gl.drawingBufferWidth === Math.round(canvas.clientWidth * devicePixelRatio) &&
        gl.drawingBufferHeight === Math.round(canvas.clientHeight * devicePixelRatio)
      );
    });
    await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    await expect(page).toHaveScreenshot(`pages-${name}.png`, {
      animations: "disabled",
      caret: "hide",
      maxDiffPixelRatio: 0.002
    });
  }

  expect(browserErrors).toEqual([]);
});
