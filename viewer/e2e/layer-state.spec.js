import { expect, test } from "@playwright/test";

test("layer-state toggles deformed and clash layers independently", async ({ page }) => {
  await page.goto("/?bundle=/test/fixtures/layer_state_scene");
  await expect(page.locator("[data-status]")).toContainText("Ready");
  await page.waitForFunction(() => window.__tubaViewer?.lastRender?.renderableCount === 3);

  await page.getByLabel(/Deformed Visual Centerline/).uncheck();
  await expect.poll(() => page.evaluate(() => window.__tubaViewer.lastRender.objectIds)).toEqual([
    "object:cold",
    "object:clash",
  ]);

  await page.getByLabel(/Overlay Clash/).uncheck();
  await expect.poll(() => page.evaluate(() => window.__tubaViewer.lastRender.objectIds)).toEqual(["object:cold"]);
});
