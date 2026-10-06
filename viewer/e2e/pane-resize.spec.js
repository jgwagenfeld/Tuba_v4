import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const viewerPath = process.env.TUBA_PANE_TEST_PATH || "/viewer/";
const reviewUrl = `${viewerPath}?bundle=code-aster-review`;
const paneWidth = async (page, selector) => (await page.locator(selector).boundingBox()).width;

async function openReview(page) {
  await page.goto(reviewUrl);
  await expect(page.locator("[data-runtime-status]")).toHaveText("Ready");
  await expect(page.locator("[data-canvas]")).toHaveAttribute("data-renderer", "three");
}

async function selectPipe(page) {
  const section = page.locator("[data-objects-section]");
  if (await section.getAttribute("open") === null) {
    await section.locator("summary").first().click();
  }
  await page.getByRole("searchbox", { name: "Search objects" }).fill("pipe_str_0");
  await page.locator('[data-object-id="object:element:pipe_str_0"]').click();
  await expect(page.getByRole("separator", { name: "Resize selection pane" })).toBeVisible();
}

async function dragHandle(page, name, delta) {
  const handle = page.getByRole("separator", { name });
  const box = await handle.boundingBox();
  const x = box.x + box.width / 2;
  const y = box.y + box.height / 2;
  await page.mouse.move(x, y);
  await page.mouse.down();
  await page.mouse.move(x + delta, y, { steps: 5 });
  await page.mouse.up();
  await expect(page.locator("[data-pane-resizing]")).toHaveCount(0);
}

test("all side panes resize independently, retain widths, and reset", async ({ page }, testInfo) => {
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await openReview(page);
  await expect(page.getByRole("separator", { name: "Resize selection pane" })).toBeHidden();
  const initialControls = await paneWidth(page, "[data-task-rail]");
  await dragHandle(page, "Resize review controls", 80);
  await expect.poll(() => paneWidth(page, "[data-task-rail]")).toBeCloseTo(initialControls + 80, 0);
  await expect.poll(() => page.locator("[data-canvas]").evaluate(canvas => canvas.width))
    .toBeCloseTo(1440 - initialControls - 80, 0);
  await selectPipe(page);
  const initialInspector = await paneWidth(page, "[data-inspector]");
  await dragHandle(page, "Resize selection pane", -100);
  await expect.poll(() => paneWidth(page, "[data-inspector]")).toBeCloseTo(initialInspector + 100, 0);

  // The edge remains in the same place while the contextual contents scroll.
  const handleBox = await page.locator("[data-inspector-resize]").boundingBox();
  await page.locator("[data-inspector]").evaluate(pane => { pane.scrollTop = pane.scrollHeight; });
  expect(await page.locator("[data-inspector-resize]").boundingBox()).toEqual(handleBox);
  const inspectorHandle = page.getByRole("separator", { name: "Resize selection pane" });
  await inspectorHandle.focus();
  await inspectorHandle.press("ArrowLeft");
  await expect.poll(() => paneWidth(page, "[data-inspector]")).toBeCloseTo(initialInspector + 110, 0);
  await expect(inspectorHandle).toHaveAttribute("aria-valuetext", `${initialInspector + 110} pixels wide`);
  await page.screenshot({ path: testInfo.outputPath("resized-review.png") });

  await page.getByRole("button", { name: "Build", exact: true }).click();
  await expect(page.getByRole("separator", { name: "Resize review controls" })).toBeHidden();
  const initialScript = await paneWidth(page, "[data-code-pane]");
  await dragHandle(page, "Resize script pane", -80);
  await expect.poll(() => paneWidth(page, "[data-code-pane]")).toBeCloseTo(initialScript - 80, 0);
  await page.screenshot({ path: testInfo.outputPath("resized-build.png") });
  await page.getByRole("button", { name: "Review", exact: true }).click();
  await expect.poll(() => paneWidth(page, "[data-task-rail]")).toBeCloseTo(initialControls + 80, 0);
  await page.reload();
  await expect(page.locator("[data-runtime-status]")).toHaveText("Ready");
  await expect.poll(() => paneWidth(page, "[data-task-rail]")).toBeCloseTo(initialControls + 80, 0);
  await selectPipe(page);
  await expect.poll(() => paneWidth(page, "[data-inspector]")).toBeCloseTo(initialInspector + 110, 0);
  await page.getByRole("searchbox", { name: "Search objects" }).fill("support_0");
  await page.locator('[data-object-id="object:support:support_0"]').click();
  await expect.poll(() => paneWidth(page, "[data-inspector]")).toBeCloseTo(initialInspector + 110, 0);
  await page.locator("[data-property-actions]").getByRole("button", { name: "Clear selection", exact: true }).click();
  await expect(page.getByRole("separator", { name: "Resize selection pane" })).toBeHidden();
  await selectPipe(page);
  await expect.poll(() => paneWidth(page, "[data-inspector]")).toBeCloseTo(initialInspector + 110, 0);
  await page.getByRole("button", { name: "Build", exact: true }).click();
  await expect.poll(() => paneWidth(page, "[data-code-pane]")).toBeCloseTo(initialScript - 80, 0);
  await page.getByRole("separator", { name: "Resize script pane" }).press("Enter");
  await expect.poll(() => paneWidth(page, "[data-code-pane]")).toBeCloseTo(initialScript, 0);
  await page.getByRole("button", { name: "Review", exact: true }).click();
  await page.getByRole("separator", { name: "Resize selection pane" }).dblclick();
  await expect.poll(() => paneWidth(page, "[data-inspector]")).toBeCloseTo(initialInspector, 0);
  await page.getByRole("separator", { name: "Resize review controls" }).dblclick();
  await expect.poll(() => paneWidth(page, "[data-task-rail]")).toBeCloseTo(initialControls, 0);
  const a11y = await new AxeBuilder({ page }).include(".pane-resize:not([hidden])").analyze();
  expect(a11y.violations).toEqual([]);
  expect(errors).toEqual([]);
});

test("bounds preserve the scene and preferences survive narrow windows", async ({ page }) => {
  await openReview(page);
  await selectPipe(page);
  const inspector = page.getByRole("separator", { name: "Resize selection pane" });
  await inspector.press("End");
  const wideInspector = await paneWidth(page, "[data-inspector]");
  const canvas = page.locator("[data-canvas]");
  expect((await canvas.boundingBox()).width).toBeGreaterThanOrEqual(320);
  await page.setViewportSize({ width: 1024, height: 768 });
  await expect.poll(() => paneWidth(page, "[data-inspector]")).toBeLessThan(wideInspector);
  const controlsWidth = await paneWidth(page, "[data-task-rail]");
  expect(1024 - controlsWidth - await paneWidth(page, "[data-inspector]")).toBeGreaterThanOrEqual(320);
  await page.setViewportSize({ width: 1440, height: 900 });
  await expect.poll(() => paneWidth(page, "[data-inspector]")).toBeCloseTo(wideInspector, 0);
  await page.setViewportSize({ width: 1024, height: 768 });
  await dragHandle(page, "Resize selection pane", 10000);
  await expect.poll(() => paneWidth(page, "[data-inspector]")).toBe(256);
  await inspector.press("End");
  await page.getByRole("button", { name: "Hide controls", exact: true }).click();
  await expect(page.getByRole("separator", { name: "Resize review controls" })).toBeHidden();
  await page.getByRole("button", { name: "Show controls", exact: true }).click();
  await expect(page.getByRole("separator", { name: "Resize review controls" })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("separator", { name: "Resize review controls" })).toBeHidden();
  expect(await canvas.evaluate(element => element.clientWidth)).toBe(390);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(390);
  await page.goto(`${reviewUrl}&embed=1`);
  await expect(page.locator("[data-runtime-status]")).toHaveText("Ready");
  await expect(page.getByRole("separator")).toHaveCount(0);
});

test("pane resizing still works when local storage is unavailable", async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(window, "localStorage", { get() { throw new Error("Storage unavailable"); } });
  });
  await openReview(page);
  const original = await paneWidth(page, "[data-task-rail]");
  await dragHandle(page, "Resize review controls", 70);
  await expect.poll(() => paneWidth(page, "[data-task-rail]")).toBeCloseTo(original + 70, 0);
  await page.getByRole("separator", { name: "Resize review controls" }).press("Enter");
  await expect.poll(() => paneWidth(page, "[data-task-rail]")).toBeCloseTo(original, 0);
});
