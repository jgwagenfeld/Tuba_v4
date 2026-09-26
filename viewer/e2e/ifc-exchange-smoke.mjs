import assert from "node:assert/strict";
import { chromium, expect } from "@playwright/test";

const [url, fixture, pipeGuid, fittingGuid, output] = process.argv.slice(2);
if (![url, fixture, pipeGuid, fittingGuid, output].every(Boolean)) {
  throw new Error("Usage: node ifc-exchange-smoke.mjs <studio-url> <fixture.ifc> <pipe-guid> <fitting-guid> <output-dir>");
}

const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto(url, { waitUntil: "domcontentloaded" });
  await expect(page.locator("[data-runtime-status]")).toHaveText("Ready", { timeout: 60_000 });
  await page.getByRole("button", { name: "Exchange" }).click();
  const dialog = page.getByRole("dialog", { name: "Project exchange" });
  await dialog.waitFor();
  await dialog.locator("[data-ifc-file]").setInputFiles(fixture);
  await dialog.getByRole("button", { name: "Preview IFC" }).click();
  const supported = dialog.locator(`[data-ifc-products] input[value="${pipeGuid}"]`);
  const fitting = dialog.locator(`[data-ifc-products] input[value="${fittingGuid}"]`);
  await supported.waitFor();
  assert.equal(await supported.isEnabled(), true);
  assert.equal(await fitting.isDisabled(), true);
  await supported.check();
  await dialog.locator("[data-ifc-products] p").filter({ hasText: "Warning" }).first().waitFor();
  await dialog.getByRole("button", { name: "Attach reference" }).click();
  await dialog.getByRole("button", { name: "Remove plant.ifc" }).waitFor();

  const converted = page.waitForEvent("download");
  await dialog.getByRole("button", { name: "Download new project ZIP" }).click();
  await (await converted).saveAs(`${output}/converted.zip`);
  const exported = page.waitForEvent("download");
  await dialog.getByRole("button", { name: "Download model IFC (geometry only)" }).click();
  await (await exported).saveAs(`${output}/export.ifc`);

  await dialog.getByRole("button", { name: "Remove plant.ifc" }).click();
  await dialog.getByRole("button", { name: "Remove plant.ifc" }).waitFor({ state: "detached" });
  console.log("IFC browser exchange passed: preview, supported selection, attach, convert, export, remove");
} finally {
  await browser.close();
}
