import { test, expect } from "@playwright/test";

test("profile comparison keeps labels and solved local frames through deformation changes", async ({ page }) => {
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/viewer/?bundle=profile-orientation-review");
  await expect(page.getByRole("status")).toHaveText("Ready", { timeout: 45_000 });
  const labels = ["label:roll-0", "label:roll-45", "label:roll-90"];
  const rendered = () => page.evaluate(() => window.__tubaViewer.lastRender.objectIds);
  expect(await rendered()).toEqual(expect.arrayContaining(labels));
  await expect(page.locator("[data-task-rail]")).toBeVisible();
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
  // Every deformed mesh element is on screen. A count was pinned here once and
  // went stale the moment the mesh sampled each beam element into sub-elements;
  // what the review needs is that none of them drop out.
  expect(await page.evaluate(() => {
    const visible = new Set(window.__tubaViewer.lastRender.objectIds);
    const deformed = window.__tubaViewer.state.objects.filter(object =>
      object.kind === "deformed_analysis_mesh_element");
    return deformed.length > 0 && deformed.every(object => visible.has(object.id));
  })).toBe(true);
  await page.getByRole("button", { name: /Animate/ }).click();
  await expect.poll(() => page.evaluate(() => window.__tubaViewer.state.visualDeformationScale)).toBeLessThan(12);
  expect(await canvas.locator("xpath=following-sibling::canvas[@data-deformation-preview]").isVisible()).toBe(false);
  expect(await rendered()).toEqual(expect.arrayContaining(labels));
  await page.getByRole("button", { name: /Pause/ }).click();
  // The tree is the last row of the Display section now, and the sections are
  // disclosures, so it is two clicks from the rail rather than one.
  const display = page.locator('details.review-section:has(> summary:text-is("Display"))');
  if (!(await display.evaluate((details) => details.open))) {
    await display.locator("> summary").click();
  }
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
