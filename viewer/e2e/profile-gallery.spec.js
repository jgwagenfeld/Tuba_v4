import { test, expect } from "@playwright/test";

test("profile comparison keeps labels and solved local frames through load and deformation changes", async ({ page }) => {
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/viewer/?bundle=profile-orientation-review");
  await expect(page.getByRole("status")).toHaveText("Ready", { timeout: 45_000 });
  const labels = ["label:roll-0", "label:roll-45", "label:roll-90"];
  const rendered = () => page.evaluate(() => window.__tubaViewer.lastRender.objectIds);
  expect(await rendered()).toEqual(expect.arrayContaining(labels));
  await expect(page.locator("[data-task-rail]")).toBeVisible();
  await page.getByRole("navigation", { name: "Engineering review tasks" }).getByRole("button", { name: "Results", exact: true }).click();
  await page.getByRole("button", { name: "Reset 3D view", exact: true }).click();
  const canvas = page.locator("[data-canvas]");
  const slider = page.getByRole("slider", { name: "Visual deformation scale (display only)", exact: true });
  await slider.focus();
  await slider.press("Home");
  const trueShape = await canvas.screenshot();
  for (let i = 0; i < 11; i++) await slider.press("ArrowRight");
  await expect.poll(() => page.evaluate(() => window.__tubaViewer.state.visualDeformationScale)).toBe(12);
  expect((await canvas.screenshot()).equals(trueShape)).toBe(false);
  await page.screenshot({ path: "../.build/profile-global.png" });
  const selectedFrames = (await rendered()).filter(id => id.startsWith("profile:deformed:"));
  expect(selectedFrames).toHaveLength(27);
  expect(selectedFrames.every(id => id.includes(":global:"))).toBe(true);
  expect(await page.evaluate(() => {
    const visible = new Set(window.__tubaViewer.lastRender.objectIds);
    return window.__tubaViewer.state.objects.filter(object =>
      object.kind === "deformed_analysis_mesh_element" && visible.has(object.id)).length;
  })).toBe(36);
  await page.getByRole("button", { name: /Animate/ }).click();
  await expect.poll(() => page.evaluate(() => window.__tubaViewer.state.visualDeformationScale)).toBeLessThan(12);
  expect(await canvas.locator("xpath=following-sibling::canvas[@data-deformation-preview]").isVisible()).toBe(false);
  expect(await rendered()).toEqual(expect.arrayContaining(labels));
  await page.getByRole("button", { name: /Pause/ }).click();
  await page.getByRole("combobox", { name: "Case", exact: true }).selectOption("local");
  await expect.poll(() => page.evaluate(() => window.__tubaViewer.state.activeLoadCase)).toBe("local");
  const localFrames = (await rendered()).filter(id => id.startsWith("profile:deformed:"));
  expect(localFrames).toHaveLength(27);
  expect(localFrames.every(id => id.includes(":local:"))).toBe(true);
  expect(await rendered()).toEqual(expect.arrayContaining(labels));
  await page.screenshot({ path: "../.build/profile-local.png" });
  // One click, not two: the tree is the last row of the Display strip now
  // rather than a popover the rail foot had to open first.
  await page.locator("summary").filter({ hasText: /All layers/ }).click();
  const labelToggle = page.getByRole("checkbox", { name: /^Labels/i });
  await labelToggle.uncheck();
  expect((await rendered()).some(id => labels.includes(id))).toBe(false);
  await labelToggle.focus();
  await labelToggle.press("Space");
  expect(await rendered()).toEqual(expect.arrayContaining(labels));
  await page.setViewportSize({ width: 800, height: 900 });
  await page.screenshot({ path: "../.build/profile-narrow.png" });
  expect(errors).toEqual([]);
});
