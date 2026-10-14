// Layout-only validation: uses the real catalog and never runs or edits a model.
import assert from "node:assert/strict";
import { mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { chromium, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const [url, outputPath] = process.argv.slice(2);
if (!url || !outputPath) throw new Error("Pass a viewer URL and an evidence directory.");
const output = resolve(outputPath);
mkdirSync(output, { recursive: true });
const browser = await chromium.launch({ headless: true });
const errors = [], evidence = [], failures = [];

async function open(page) {
  await page.locator("[data-profiles-open]:visible").click();
  const dialog = page.locator("[data-profile-library]");
  await expect(dialog).toBeVisible();
  await expect(dialog.locator("[data-profiles-status]")).toHaveText("400 profiles");
  await expect(dialog.locator("[data-profiles-search]")).toBeFocused();
  return dialog;
}

async function measure(dialog) {
  return dialog.evaluate(node => {
    const bounds = element => {
      const rect = element.getBoundingClientRect();
      return { left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom, width: rect.width, height: rect.height };
    };
    const preview = node.querySelector("[data-profiles-preview]");
    return {
      viewport: { width: innerWidth, height: innerHeight }, dialog: bounds(node),
      outerOverflow: node.scrollHeight - node.clientHeight,
      horizontalOverflow: node.scrollWidth - node.clientWidth,
      detailOverflow: preview.scrollHeight - preview.clientHeight,
      contentOverflow: node.querySelector(".profile-library-content").scrollHeight - node.querySelector(".profile-library-content").clientHeight,
      figure: bounds(node.querySelector("[data-profiles-figure] svg")),
      properties: bounds(node.querySelector(".profile-library-properties")),
      close: bounds(node.querySelector("[data-profiles-close]"))
    };
  });
}

function assertDesktopDetail(metrics) {
  assert.ok(metrics.dialog.width >= metrics.viewport.width * .9, "Profiles should use the available desktop width.");
  assert.ok(metrics.dialog.height >= metrics.viewport.height * .9, "Profiles should use the available desktop height.");
  assert.ok(metrics.detailOverflow <= 1, `The selected profile should fit without desktop scrolling: ${JSON.stringify(metrics)}`);
  assert.ok(metrics.figure.right <= metrics.properties.left, "The diagram should sit beside the properties.");
  assert.ok(metrics.properties.bottom < metrics.dialog.bottom, "All property rows and source notes should be visible.");
}

try {
  const context = await browser.newContext();
  const page = await context.newPage();
  page.on("pageerror", error => errors.push(error.message));
  await page.goto(url);
  const sizes = [
    { name: "desktop", width: 1440, height: 1040 },
    { name: "laptop", width: 1366, height: 768 },
    { name: "tablet", width: 1024, height: 768 },
    { name: "mobile", width: 390, height: 844 },
    { name: "zoom-equivalent", width: 720, height: 520 },
    { name: "landscape", width: 844, height: 390 }
  ];
  for (const size of sizes) {
    await page.setViewportSize(size);
    const dialog = await open(page);
    const list = dialog.locator("[data-profiles-list]");
    assert.ok(await list.evaluate(node => node.scrollHeight > node.clientHeight), "The full catalog remains scrollable.");
    await list.locator('[data-profile-name="IPEAA100"]').click();
    await expect(dialog.locator("[data-profiles-name]")).toHaveText("IPEAA100");
    await expect(dialog.locator("[data-profiles-properties]")).toContainText("Polar moment");
    const metrics = await measure(dialog);
    assert.ok(metrics.horizontalOverflow <= 1, `${size.name}: no horizontal clipping.`);
    assert.ok(metrics.outerOverflow <= 1, `${size.name}: header and Close stay outside the content scroll.`);
    assert.ok(metrics.close.top >= 0 && metrics.close.bottom <= size.height, `${size.name}: Close remains visible.`);
    await page.screenshot({ path: resolve(output, `profiles-${size.name}.png`) });
    evidence.push({ state: "catalog", ...size, ...metrics });
    if (size.width > 1100) {
      try { assertDesktopDetail(metrics); } catch (error) { failures.push(`${size.name}: ${error.message}`); }
    }
    // A search input consumes its first Escape to clear text in Chromium.
    await dialog.locator("[data-profiles-family]").focus();
    await page.keyboard.press("Escape");
    await expect(dialog).not.toBeVisible();
    await expect(page.locator("[data-profiles-open]:visible")).toBeFocused();
  }

  // Exercise the same markup/controller in Build mode without a model or solver.
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.evaluate(async () => {
    const original = document.querySelector("[data-profile-library]");
    const dialog = original.cloneNode(true);
    original.replaceWith(dialog);
    const { initProfileLibrary, loadProfileCatalog } = await import("/src/profileLibrary.js");
    const load = async () => {
      const payload = await loadProfileCatalog();
      return { ...payload, used: [{ ...payload.catalog.find(row => row.name === "IPEAA100"), name: "FrameBeam", profile_name: "IPEAA100", source_line: 12 }] };
    };
    window.openLayoutProfiles = initProfileLibrary(dialog, {
      load, canInsert: () => true, sourceCurrent: () => true,
      insert: definition => { window.layoutInsertion = definition; },
      reveal: line => { window.layoutSourceLine = line; }
    });
    await window.openLayoutProfiles();
  });
  const dialog = page.locator("[data-profile-library]");
  await dialog.locator("[data-profiles-search]").fill("IPEAA100");
  await expect(dialog.locator("[data-profiles-insert-form]")).toBeVisible();
  let metrics = await measure(dialog);
  try { assertDesktopDetail(metrics); } catch (error) { failures.push(`build: ${error.message}`); }
  assert.deepEqual((await new AxeBuilder({ page }).include("[data-profile-library]").analyze()).violations.map(row => row.id), []);
  await page.screenshot({ path: resolve(output, "profiles-build.png") });
  evidence.push({ state: "build", ...metrics });
  await dialog.locator("[data-profiles-section-name]").fill("NewBeam");
  await dialog.getByRole("button", { name: "Insert into model.py", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  assert.equal((await page.evaluate(() => window.layoutInsertion)).trim(), 'model.add_ibeam_section("NewBeam", profile_name="IPEAA100")');

  await page.evaluate(() => window.openLayoutProfiles("FrameBeam"));
  await expect(dialog.locator("[data-profiles-name]")).toHaveText("FrameBeam · IPEAA100");
  await expect(dialog.locator("[data-profiles-reveal]")).toBeEnabled();
  metrics = await measure(dialog);
  try { assertDesktopDetail(metrics); } catch (error) { failures.push(`used: ${error.message}`); }
  await page.screenshot({ path: resolve(output, "profiles-used.png") });
  evidence.push({ state: "used", ...metrics });
  await dialog.locator("[data-profiles-reveal]").click();
  assert.equal(await page.evaluate(() => window.layoutSourceLine), 12);

  await page.evaluate(() => window.openLayoutProfiles());
  await dialog.locator("[data-profiles-family]").selectOption("Pipe");
  await expect(dialog.locator("[data-profiles-list] button")).toHaveCount(226);
  await dialog.locator("[data-profiles-search]").fill("DN150_SCH40");
  await expect(dialog.locator("[data-profiles-name]")).toHaveText("DN150_SCH40");
  await expect(dialog.locator("[data-profiles-properties]")).toContainText("7.11 mm");
  metrics = await measure(dialog);
  try { assertDesktopDetail(metrics); } catch (error) { failures.push(`pipe: ${error.message}`); }
  await page.screenshot({ path: resolve(output, "profiles-pipe.png") });
  evidence.push({ state: "pipe", ...metrics });
  await dialog.locator("[data-profiles-search]").fill("no matching section");
  await expect(dialog.locator("[data-profiles-status]")).toContainText("no matches");
  await expect(dialog.locator("[data-profiles-preview]")).toBeHidden();
  await dialog.locator("[data-profiles-close]").click();
  assert.deepEqual(errors, []);
  writeFileSync(resolve(output, "evidence.json"), JSON.stringify({ evidence, failures, pageErrors: errors, axeViolations: 0, solverRun: false }, null, 2));
  assert.deepEqual(failures, []);
  console.log("Profiles layout: desktop, laptop, tablet, phone, zoom, landscape, Build, used sections, pipes, insertion, Escape/focus and Axe passed.");
} finally {
  await browser.close();
}
