// Read-only UI check against a Studio with a current, real Code_Aster review.
// Pass a source preview URL and an output directory outside tracked source.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { chromium, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const [url, output, mode] = process.argv.slice(2);
const navigationOnly = mode === "--navigation-only";
if (!url || !output) throw new Error("Pass a Studio review URL and an external evidence directory.");
const directory = resolve(output);
await mkdir(directory, { recursive: true });
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: "reduce" });
const page = await context.newPage();
const errors = [], blockedWrites = [], checks = [];
page.on("pageerror", error => errors.push(error.message));
await context.route("**/api/**", async route => {
  if (!["GET", "HEAD"].includes(route.request().method())) {
    blockedWrites.push(route.request().url());
    await route.abort();
  } else await route.continue();
});
const sourceHash = async () => {
  const response = await context.request.get(new URL("/api/script", url).href);
  assert.equal(response.status(), 200);
  return createHash("sha256").update((await response.json()).code).digest("hex");
};
const accessible = async selector => {
  const audit = await new AxeBuilder({ page }).include(selector).analyze();
  assert.deepEqual(audit.violations.map(item => ({ id: item.id, targets: item.nodes.map(node => node.target) })), []);
};
const openTools = async () => {
  const tools = page.locator("[data-header-tools]");
  if (await tools.getAttribute("open") === null) await tools.locator(":scope > summary").click();
};

try {
  const originalSourceHash = await sourceHash();
  await page.goto(url);
  await expect(page.locator("[data-runtime-status]")).toContainText("Live preview connected", { timeout: 45_000 });
  await expect(page.locator("body")).toHaveAttribute("data-studio", "true");
  await expect(page.locator("[data-solver-fact]")).toContainText("Code_Aster");
  await expect(page.locator("[data-report-link]")).toBeVisible();
  await accessible("[data-app-header]");
  await page.screenshot({ path: resolve(directory, "review-desktop.png") });
  checks.push("Current retained Code_Aster review opens with result fields and Report");
  console.log("Review ready; checking Build");

  await page.locator("button[data-mode=build]").click();
  await expect(page.locator("body")).toHaveAttribute("data-mode", "build", { timeout: 15_000 });
  await expect(page.locator("[data-code-run-label]")).toHaveText("Update geometry");
  await page.screenshot({ path: resolve(directory, "build-desktop.png") });
  if (!navigationOnly) {
    await page.getByRole("button", { name: "Solver .comm", exact: true }).click();
    await expect(page.locator("[data-comm-text]")).toHaveAttribute("data-state", "ready", { timeout: 60_000 });
    await expect(page.locator("[data-comm-text]")).toContainText("DEBUT");
    await page.getByRole("button", { name: "model.py", exact: true }).click();
    checks.push("Build, model.py and read-only solver input remain reachable");
  } else checks.push("Build and model.py reachable; generated input excluded from this navigation check");
  console.log(navigationOnly ? "Build ready; checking responsive controls" : "Build and solver input ready; checking responsive controls");

  for (const [width, height] of [[1440, 900], [900, 650], [390, 844]]) {
    await page.setViewportSize({ width, height });
    await openTools();
    await expect(page.getByRole("button", { name: "Section profiles", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Import geometry", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Files & export", exact: true })).toBeVisible();
    const technicalDetails = page.locator("[data-header-tools] .meta");
    if (await technicalDetails.getAttribute("open") === null) await technicalDetails.locator(":scope > summary").click();
    await expect(page.locator("[data-viewer-identity]")).toBeVisible();
    await accessible("[data-app-header]");
    const menu = await page.locator(".header-tools-content").boundingBox();
    assert.ok(menu.x >= 0 && menu.x + menu.width <= width, "Tools fits the viewport");
    await page.getByRole("button", { name: "Section profiles", exact: true }).focus();
    await page.keyboard.press("Escape");
    await expect(page.locator("[data-header-tools]")).not.toHaveAttribute("open");
    await expect(page.locator("[data-header-tools] > summary")).toBeFocused();

    const help = page.getByRole("button", { name: "Help", exact: true });
    await help.click();
    const dialog = page.getByRole("dialog", { name: "Using Tuba" });
    await expect(dialog).toBeVisible();
    await expect(dialog).toContainText("Geometry previews and exported inputs are not solved results");
    await accessible("#workspace-help");
    await page.keyboard.press("R");
    await expect(page.locator("body")).toHaveAttribute("data-mode", "build", { timeout: 15_000 });
    if (width === 390) await page.screenshot({ path: resolve(directory, "help-mobile.png") });
    await page.keyboard.press("Escape");
    await expect(dialog).not.toBeVisible();
    await expect(help).toBeFocused();
    await page.screenshot({ path: resolve(directory, `build-${width}.png`) });
    const overflow = await page.locator("[data-app-header]").evaluate(element => element.scrollWidth > element.clientWidth);
    assert.equal(overflow, false, "Header stays within the viewport");
    checks.push(`${width}px: tools, technical details, Help, modal keyboard behavior and accessibility`);
  }

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.locator("button[data-mode=review]").click();
  await expect(page.locator("body")).toHaveAttribute("data-mode", "review", { timeout: 15_000 });
  await page.locator("[data-review-drawer] > summary").click();
  await expect(page.locator("[data-issue-list]")).toBeVisible();
  checks.push("Review tables and issues are reachable after returning from Build");
  assert.deepEqual(errors, []);
  assert.deepEqual(blockedWrites, []);
  assert.equal(await sourceHash(), originalSourceHash, "The live authored source remains unchanged");
  const receipt = { checks, pageErrors: errors, blockedWrites, sourceUnchanged: true, generatedInputChecked: !navigationOnly,
    solverExecution: "Existing retained Code_Aster review; no fresh solve requested" };
  await writeFile(resolve(directory, "browser-validation.json"), JSON.stringify(receipt, null, 2));
  console.log(JSON.stringify(receipt, null, 2));
} catch (error) {
  await writeFile(resolve(directory, "browser-failure.json"), JSON.stringify({ error: error.message, pageErrors: errors, blockedWrites,
    body: await page.locator("body").evaluate(element => ({ ...element.dataset })), status: await page.locator("[data-runtime-status]").textContent() }, null, 2));
  throw error;
} finally {
  await browser.close();
}
