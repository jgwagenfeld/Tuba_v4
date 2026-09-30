// Run against an assembled gallery and a disposable Studio: this edits model.py.
import assert from "node:assert/strict";
import { mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { chromium, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const [galleryUrl, studioUrl, outputPath] = process.argv.slice(2);
if (!galleryUrl || !studioUrl) throw new Error("Pass a gallery viewer URL and a disposable Studio URL.");
const output = resolve(outputPath ?? "../.build/shared-profiles/browser");
mkdirSync(output, { recursive: true });
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const errors = [];

async function newPage(url) {
  const page = await context.newPage();
  page.on("pageerror", error => errors.push(error.message));
  await page.goto(url);
  return page;
}

async function openProfiles(page) {
  await page.locator("[data-profiles-open]:visible").click();
  const drawer = page.locator("[data-profile-library]");
  await expect(drawer).toBeVisible();
  await expect(drawer.locator("[data-profiles-status]")).toHaveText("400 profiles");
  return drawer;
}

async function catalogSnapshot(page, drawer) {
  const names = await drawer.locator("[data-profiles-list] button").evaluateAll(nodes => nodes.map(node => node.dataset.profileName));
  assert.equal(names.length, 400);
  await drawer.locator("[data-profiles-family]").selectOption("IPE");
  await drawer.locator("[data-profiles-min]").fill("150");
  await drawer.locator("[data-profiles-max]").fill("170");
  await drawer.locator("[data-profiles-search]").fill("ipe 160");
  await expect(drawer.locator("[data-profiles-list] button")).toHaveCount(1);
  await expect(drawer.locator("[data-profiles-name]")).toHaveText("IPE160");
  await expect(drawer.locator("[data-profiles-figure] svg")).toBeVisible();
  const beam = await drawer.locator("[data-profiles-properties]").textContent();
  await expect(drawer.locator("[data-profiles-properties]")).toContainText("thin-wall estimate");
  await drawer.locator("[data-profiles-family]").selectOption("Pipe");
  await drawer.locator("[data-profiles-min]").fill("");
  await drawer.locator("[data-profiles-max]").fill("");
  await drawer.locator("[data-profiles-search]").fill("");
  await expect(drawer.locator("[data-profiles-list] button")).toHaveCount(226);
  await drawer.locator("[data-profiles-search]").fill("DN150_SCH40");
  await expect(drawer.locator("[data-profiles-list] button")).toHaveCount(1);
  await expect(drawer.locator("[data-profiles-list]")).toContainText("NPS 6 · Sch 40 · OD 168.3 × WT 7.11 mm");
  await expect(drawer.locator("[data-profiles-figure] svg")).toBeVisible();
  const pipe = await drawer.locator("[data-profiles-properties]").textContent();
  const figure = (await drawer.locator("[data-profiles-figure]").innerHTML()).replace(/profile-material-\d+/g, "profile-material");
  assert.deepEqual((await new AxeBuilder({ page }).include("[data-profile-library]").analyze()).violations.map(row => row.id), []);
  return { names, beam, pipe, figure };
}

async function insertAndRun(page, studio) {
  await page.getByRole("button", { name: "Build", exact: true }).click();
  const editor = page.locator("[data-code-text]");
  await expect(editor).toBeEditable();
  await expect(editor).toHaveValue(/with model\.pipe/);
  const original = await editor.inputValue();
  const at = original.indexOf("with model.pipe");
  assert.ok(at > 0, "The test model needs a procedural pipe definition.");
  await editor.focus();
  await editor.evaluate((node, at) => node.setSelectionRange(at + 3, at + 3), at);
  const drawer = await openProfiles(page);
  await drawer.locator("[data-profiles-search]").fill("IPE160");
  const name = 'Parity"UnusedBeam';
  await drawer.locator("[data-profiles-section-name]").fill(name);
  await drawer.getByRole("button", { name: "Insert into Python" }).click();
  const definition = `model.add_ibeam_section(${JSON.stringify(name)}, profile_name="IPE160")\n`;
  await expect(editor).toHaveValue(original.slice(0, at) + definition + original.slice(at));
  await openProfiles(page);
  await drawer.getByRole("button", { name: "Used in this model" }).click();
  await expect(drawer.locator("[data-profiles-definition-note]")).toContainText("last successful run");
  await expect(drawer.locator("[data-profiles-reveal]")).toBeDisabled();
  await page.keyboard.press("Escape");
  await page.locator("[data-code-run]").click();
  if (studio) await expect(page.locator("[data-code-foot]")).toContainText("Saved to model.py", { timeout: 30_000 });
  else {
    await expect(page.locator("[data-code-state]")).toHaveText("Geometry preview", { timeout: 90_000 });
    assert.deepEqual(await page.evaluate(() => ({ results: window.__tubaViewer.state.resultFields.length, review: window.__tubaViewer.state.review })), { results: 0, review: null });
  }
  await openProfiles(page);
  await drawer.getByRole("button", { name: "Used in this model" }).click();
  await drawer.locator("[data-profiles-list] button").filter({ hasText: name }).click();
  await expect(drawer.locator("[data-profiles-name]")).toHaveText(`${name} · IPE160`);
  await expect(drawer.locator("[data-profiles-reveal]")).toBeEnabled();
  await drawer.locator("[data-profiles-reveal]").click();
  await expect(editor).toBeFocused();
  assert.equal(await editor.evaluate(node => node.selectionStart), at);
  await page.screenshot({ path: resolve(output, studio ? "studio-profile-insertion.png" : "gallery-profile-insertion.png") });
  return name;
}

async function externalStudioReload(page, name) {
  const editor = page.locator("[data-code-text]");
  const code = await editor.inputValue();
  const offset = code.indexOf(`model.add_ibeam_section(${JSON.stringify(name)},`);
  assert.ok(offset > 0);
  const line = code.slice(0, offset).split("\n").length;
  const drawer = await openProfiles(page);
  await drawer.getByRole("button", { name: "Used in this model" }).click();
  await drawer.locator("[data-profiles-list] button").filter({ hasText: name }).click();
  await expect(drawer.locator("[data-profiles-definition-note]")).toHaveText(`Defined at model.py:${line}`);
  // Another client can rebuild the same disposable project while its dialog is open.
  const response = await page.request.post(new URL("/api/script", page.url()).href, { data: { code: `\n${code}` } });
  assert.ok(response.ok(), await response.text());
  assert.equal((await response.json()).ok, true);
  await expect(drawer).not.toBeVisible();
  await expect(editor).toHaveValue(`\n${code}`);
  await openProfiles(page);
  await drawer.getByRole("button", { name: "Used in this model" }).click();
  await drawer.locator("[data-profiles-list] button").filter({ hasText: name }).click();
  await expect(drawer.locator("[data-profiles-definition-note]")).toHaveText(`Defined at model.py:${line + 1}`);
  await expect(drawer.locator("[data-profiles-reveal]")).toBeEnabled();
  await drawer.locator("[data-profiles-reveal]").click();
  await expect(editor).toBeFocused();
  assert.equal(await editor.evaluate(node => node.selectionStart), offset + 1);
}

try {
  const gallery = await newPage(galleryUrl);
  await expect(gallery.locator("[data-gallery-card]").first()).toBeVisible();
  const landingDrawer = await openProfiles(gallery);
  await expect(landingDrawer.locator("[data-profiles-insert-form]")).toBeHidden();
  const landing = await catalogSnapshot(gallery, landingDrawer);
  await gallery.setViewportSize({ width: 390, height: 844 });
  assert.ok(await landingDrawer.evaluate(node => node.scrollWidth <= node.clientWidth + 1));
  await gallery.screenshot({ path: resolve(output, "gallery-profiles-mobile.png") });
  await gallery.keyboard.press("Escape");
  await gallery.setViewportSize({ width: 1440, height: 1000 });
  const reviewUrl = new URL(galleryUrl);
  reviewUrl.searchParams.set("bundle", "code-aster-review");
  await gallery.goto(reviewUrl.href);
  await expect(gallery.locator("[data-runtime-status]")).toHaveText("Ready", { timeout: 60_000 });
  const published = await gallery.evaluate(() => {
    const state = window.__tubaViewer.state;
    return JSON.stringify({ objects: state.objects, resultFields: state.resultFields, resultStates: state.resultStates, overlays: state.overlays, review: state.review });
  });
  assert.ok(await gallery.evaluate(() => window.__tubaViewer.state.resultFields.length > 0), "Use real published Code_Aster results.");
  const reviewDrawer = await openProfiles(gallery);
  await expect(reviewDrawer.locator("[data-profiles-insert-form]")).toBeHidden();
  assert.deepEqual(await catalogSnapshot(gallery, reviewDrawer), landing);
  await gallery.keyboard.press("Escape");
  await insertAndRun(gallery, false);
  await gallery.getByRole("button", { name: "Review", exact: true }).click();
  assert.equal(await gallery.evaluate(() => {
    const state = window.__tubaViewer.state;
    return JSON.stringify({ objects: state.objects, resultFields: state.resultFields, resultStates: state.resultStates, overlays: state.overlays, review: state.review });
  }), published, "Editing and previewing must preserve the published solved snapshot.");
  await expect(gallery.locator("[data-status-chip] [data-status]")).toHaveAttribute("data-status", "stale");

  const studio = await newPage(studioUrl);
  await expect(studio.locator("[data-code-text]")).toBeEditable();
  const studioDrawer = await openProfiles(studio);
  assert.deepEqual(await catalogSnapshot(studio, studioDrawer), landing);
  await studio.keyboard.press("Escape");
  await externalStudioReload(studio, await insertAndRun(studio, true));
  assert.deepEqual(errors, []);
  writeFileSync(resolve(output, "evidence.json"), JSON.stringify({ catalog: 400, pipes: 226, parity: true, landingBrowseOnly: true, mobile: true, axeViolations: 0, galleryInsertion: true, studioInsertion: true, unusedSection: true, sourceNavigation: true, externalStudioReload: true, publishedResultsPreserved: true, previewUnsolved: true, pageErrors: errors }, null, 2));
  console.log("Profiles parity: gallery, published review, Studio, insertion, source navigation, external reload, unsolved preview, preserved results, mobile and Axe passed.");
} finally {
  await browser.close();
}
