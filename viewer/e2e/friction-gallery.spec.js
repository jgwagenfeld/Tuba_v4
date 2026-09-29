import { expect, test } from "@playwright/test";

test("hot-line gallery glyphs preserve relative reaction magnitudes", async ({ page }) => {
  await page.goto("/viewer/?bundle=autorouted-expansion-loop");
  await expect(page.locator("[data-runtime-status]")).toContainText("Ready", { timeout: 45_000 });
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
  await expect(page.locator("[data-task-rail]")).toBeVisible();
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
  // The card states the review is solved by naming what Code_Aster did for it.
  // It used to assert the literal word "Results", which four of the twelve cards
  // also carried and which told a reader nothing the facts do not.
  await expect(card).toContainText("1 load case");
  await expect(card).toContainText("2 element types");
  await expect(card).not.toContainText("Model only");
  await card.click();
  await expect(page.locator("[data-runtime-status]")).toContainText("Ready", { timeout: 45_000 });
  expect(await page.evaluate(() => window.__tubaViewer.state.sceneId)).toBe("scene:native-friction:comparison");
  expect(await page.evaluate(() => window.__tubaViewer.state.resultStates.length)).toBe(51);
  await expect(page.locator("[data-task-rail]")).toBeVisible();
  // The load path is navigated by stage; a stage lands on the converged
  // increment it ended on, which is what "Hot / 2" used to select by hand.
  const stage = (index) => page.locator(".contact-step-nav button").nth(index);
  await stage(2).click();
  await expect(stage(2)).toHaveAttribute("aria-pressed", "true");
  // The contact tables are in the "Tables & issues" drawer below the viewport.
  await page.locator("[data-review-drawer] > summary").click();
  const panel = page.locator("[data-contact-table]").getByRole("region", { name: "Contact review", exact: true });
  await expect(panel).toContainText("sliding");
  await expect(panel).toContainText("closed (frictionless)");
  expect(await page.evaluate(() => window.__tubaViewer.state.objects.filter(o => o.kind === "scene_label").map(o => o.metadata.text))).toEqual([
    "Without friction · μ = 0", "With friction · μ = 0.3",
  ]);
  await stage(4).click();
  await expect(stage(4)).toHaveAttribute("aria-pressed", "true");
  await expect(panel).toContainText("open");
  await page.screenshot({ path: "../.build/gallery-friction-comparison.png" });
  expect(errors).toEqual([]);
});
