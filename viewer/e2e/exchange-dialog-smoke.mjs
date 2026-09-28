// UI-only check; no solver or IFC processing is simulated.
// Run from viewer/: node e2e/exchange-dialog-smoke.mjs
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { chromium, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const html = await readFile(new URL("../index.html", import.meta.url), "utf8");
const css = await readFile(new URL("../src/styles.css", import.meta.url), "utf8");
const source = await readFile(new URL("../src/exchange.js", import.meta.url), "utf8");
const browser = await chromium.launch({ headless: true });
try {
  const context = await browser.newContext({ viewport: { width: 1210, height: 585 } });
  const page = await context.newPage();
  async function open(project = null, downloads = { project: "downloads/pipe.zip", ifc: "downloads/pipe.ifc" }) {
    await page.setContent(`<html lang="en"><head><title>Exchange check</title></head><body>${html.match(/<dialog\b[\s\S]*?<\/dialog>/)[0]}</body></html>`);
    await page.addStyleTag({ content: css });
    await page.addScriptTag({ content: source.replace(/^export /gm, "") });
    await page.evaluate(({ project, downloads }) => {
      const dialog = document.querySelector("dialog");
      initExchange(dialog, { project, catalogEntry: { id: "pipe", downloads }, reload: async () => {} });
      dialog.showModal();
    }, { project, downloads });
  }
  await open();
  const dialog = page.getByRole("dialog", { name: "Downloads & IFC" });
  await expect(dialog.getByRole("link", { name: "Download project ZIP" })).toHaveAttribute("href", "downloads/pipe.zip");
  await expect(dialog.getByRole("link", { name: "Download IFC geometry" })).toHaveAttribute("href", "downloads/pipe.ifc");
  await expect(dialog.locator("[data-ifc-studio-controls]")).toBeHidden();
  await expect(dialog).toContainText("Solver results are not included");
  const close = dialog.getByRole("button", { name: "Close exchange" });
  assert.ok((await close.boundingBox()).width < 100, "Close stays compact");
  assert.deepEqual((await new AxeBuilder({ page }).include(".exchange-dialog").analyze()).violations, []);
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();

  await page.setViewportSize({ width: 390, height: 700 });
  await open();
  assert.ok(await dialog.evaluate(el => el.scrollWidth <= el.clientWidth), "No horizontal overflow on narrow screens");
  await close.click();
  await expect(dialog).not.toBeVisible();

  await open(null, {});
  await expect(dialog).toContainText("No downloads were published for this review.");
  await expect(dialog.getByRole("link")).toHaveCount(0);

  await open({ ifc: { available: true, export_available: true, references: [] } });
  await expect(dialog.locator("[data-exchange-published]")).toBeHidden();
  await expect(dialog.getByLabel("IFC file", { exact: true })).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Preview IFC" })).toBeEnabled();
  await expect(dialog.getByRole("button", { name: "Attach reference" })).toBeDisabled();
  await expect(dialog.locator("[data-ifc-assignments]")).toBeHidden();
  await expect(dialog.locator("[data-ifc-export]")).toBeVisible();

  await open({ ifc: { available: false, export_available: false, reason: "IFC support unavailable", references: [] } });
  await expect(dialog.getByRole("button", { name: "Preview IFC" })).toBeDisabled();
  await expect(dialog.locator("[data-ifc-status]")).toHaveText("IFC support unavailable");
  await expect(dialog.locator("[data-ifc-export]")).toBeHidden();
  console.log("Exchange dialog passed: downloads, empty state, Studio capability, responsive layout, accessibility, close/Escape.");
} finally {
  await browser.close();
}
