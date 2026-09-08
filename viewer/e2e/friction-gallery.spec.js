import { expect, test } from "@playwright/test";

test("hot-line gallery glyphs preserve relative reaction magnitudes", async ({ page }) => {
  await page.goto("/viewer/?bundle=autorouted-expansion-loop");
  await expect(page.getByRole("status")).toContainText("Ready", { timeout: 45_000 });
  const vectors = await page.evaluate(() => window.__tubaViewer.state.geometryPayloads
    .filter(p => p.format === "vector").map(p => p.generation_config)
    .filter(c => c.result_type === "reaction_force"));
  const lengths = vectors.map(c => Math.hypot(...c.end.map((x, i) => x - c.start[i])));
  const magnitudes = vectors.map(c => Math.hypot(...c.reaction_force_n));
  expect(vectors.length).toBeGreaterThan(1);
  for (let i = 1; i < vectors.length; i++) {
    expect(lengths[i] / lengths[0]).toBeCloseTo(magnitudes[i] / magnitudes[0], 8);
  }
  await page.screenshot({ path: "../.build/hot-line-fixed.png" });
  await page.getByRole("button", { name: "Controls", exact: true }).click();
  await page.getByRole("navigation", { name: "Engineering review tasks" }).getByRole("button", { name: "Results", exact: true }).click();
  await page.locator("summary").filter({ hasText: "Filters & vectors" }).click();
  const moment = page.getByRole("slider", { name: /^Moment vector scale/ });
  await moment.fill("0.25");
  await moment.dispatchEvent("change");
  expect(await page.evaluate(() => window.__tubaViewer.state.resultVectorScales)).toMatchObject({ moment: 0.25, reaction: 1 });
});

test("gallery opens the combined attested pipe-shoe comparison", async ({ page }) => {
  test.setTimeout(120_000);
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/viewer/");
  const card = page.locator('[data-gallery-card="native-friction-review"]');
  await expect(card).toContainText("Results");
  await card.click();
  await expect(page.getByRole("status")).toContainText("Ready", { timeout: 45_000 });
  expect(await page.evaluate(() => window.__tubaViewer.state.sceneId)).toBe("scene:native-friction:comparison");
  expect(await page.evaluate(() => window.__tubaViewer.state.resultStates.length)).toBe(51);
  await page.getByRole("button", { name: "Controls", exact: true }).click();
  await page.getByRole("navigation", { name: "Engineering review tasks" }).getByRole("button", { name: "Results", exact: true }).click();
  await page.getByRole("combobox", { name: "Result state", exact: true }).selectOption({ label: "Hot / 2" });
  const panel = page.getByRole("region", { name: "Contact review", exact: true });
  await expect(panel).toContainText("sliding");
  await expect(panel).toContainText("closed (frictionless)");
  expect(await page.evaluate(() => window.__tubaViewer.state.objects.filter(o => o.kind === "scene_label").map(o => o.metadata.text))).toEqual([
    "Without friction · μ = 0", "With friction · μ = 0.3",
  ]);
  await page.getByRole("combobox", { name: "Result state", exact: true }).selectOption({ label: "Lift / 4" });
  await expect(panel).toContainText("open");
  await page.screenshot({ path: "../.build/gallery-friction-comparison.png" });
  expect(errors).toEqual([]);
});
