import { expect, test } from "@playwright/test";
import { formatQuantity } from "../src/units.js";

// Run against the assembled official gallery with real Code_Aster artifacts.
test("real contact history preserves forces through selection and display scaling", async ({ page }) => {
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/viewer/?bundle=native-friction-review");
  await expect(page.getByRole("status")).toContainText("Ready");
  await page.getByRole("button", { name: "Controls", exact: true }).click();
  await page.getByRole("navigation", { name: "Engineering review tasks" }).getByRole("button", { name: "Results", exact: true }).click();
  const panel = page.getByRole("region", { name: "Contact review", exact: true });
  await expect(panel).toBeVisible();
  const states = await page.evaluate(() => window.__tubaViewer.state.resultStates.map(s => s.data));
  expect(states.length).toBeGreaterThan(20);
  for (const status of ["sticking", "sliding", "open"]) {
    const state = states.find(s => s.metadata.pseudo_time > 0 && Object.values(s.contact_results).some(c => c.status === status));
    expect(state, `Real ${status} increment`).toBeTruthy();
    const contact = Object.values(state.contact_results).find(c => c.status === status);
    await page.getByRole("combobox", { name: "Result state", exact: true }).selectOption(state.id);
    await panel.getByRole("button", { name: contact.support_id, exact: true }).click();
    await expect(panel.getByRole("heading", { name: `Selected shoe ${contact.support_id}`, exact: true })).toBeVisible();
    const row = panel.locator("tbody tr").filter({ has: page.getByRole("button", { name: contact.support_id, exact: true }) });
    await expect(row).toContainText(`${status} (solver)`);
    const system = await page.evaluate(() => window.__tubaViewer.state.unitSystem);
    await expect(row).toContainText(formatQuantity(contact.normal_force, "N", system));
    await expect(row).toContainText(formatQuantity(contact.gap, "m", system));
    await expect(panel.locator("svg circle[r='5']")).toHaveCount(1);
    await expect(page.locator("[data-inspector]")).toBeHidden();
    const before = await row.textContent();
    const scale = page.getByRole("slider", { name: "Visual deformation scale (display only)" });
    await scale.fill("10");
    await scale.dispatchEvent("change");
    await expect(row).toHaveText(before);
    expect(await page.evaluate(() => window.__tubaViewer.state.activeResultStateId)).toBe(state.id);
    const wrongFrames = await page.evaluate(() => {
      const { state, lastRender } = window.__tubaViewer;
      return state.objects.filter(o => lastRender.objectIds.includes(o.id) &&
        o.metadata?.result_state_id && o.metadata.result_state_id !== state.activeResultStateId).map(o => o.id);
    });
    expect(wrongFrames).toEqual([]);
    await panel.scrollIntoViewIfNeeded();
    await page.screenshot({ path: `../.build/friction-${status}.png`, fullPage: true });
  }
  await panel.getByLabel("Normal-force arrows", { exact: true }).uncheck();
  expect(await page.evaluate(() => window.__tubaViewer.state.contactArrows.normal)).toBe(false);
  await panel.getByLabel("Normal-force arrows", { exact: true }).check();
  await panel.getByRole("button", { name: "Next converged step", exact: true }).focus();
  await page.keyboard.press("Enter");
  await page.setViewportSize({ width: 800, height: 900 });
  await expect(panel).toBeVisible();
  await page.screenshot({ path: "../.build/friction-narrow.png", fullPage: true });
  expect(errors).toEqual([]);
});

test("a missing contact increment displays unavailable, never an invented state", async ({ page }) => {
  // Deliberately remove data only in this test response, leaving real artifacts intact.
  await page.route("**/scene.json", async route => {
    const response = await route.fetch();
    const scene = await response.json();
    const reference = scene.overlays.find(o => o.kind === "result_state" && o.data.metadata.pseudo_time === 0);
    delete reference.data.contact_results;
    await route.fulfill({ response, json: scene });
  });
  await page.goto("/viewer/?bundle=native-friction-review");
  await expect(page.getByRole("status")).toContainText("Ready");
  await page.getByRole("button", { name: "Controls", exact: true }).click();
  await page.getByRole("navigation", { name: "Engineering review tasks" }).getByRole("button", { name: "Results", exact: true }).click();
  const panel = page.getByRole("region", { name: "Contact review", exact: true });
  await expect(panel).toContainText("Contact results unavailable for this state.");
  await expect(panel.locator("tbody tr")).toHaveCount(0);
});

test("frictionless copy displays zero force and no utilization in the shared solve", async ({ page }) => {
  await page.goto("/viewer/?bundle=native-friction-review");
  await expect(page.getByRole("status")).toContainText("Ready");
  await page.getByRole("button", { name: "Controls", exact: true }).click();
  await page.getByRole("navigation", { name: "Engineering review tasks" }).getByRole("button", { name: "Results", exact: true }).click();
  const panel = page.getByRole("region", { name: "Contact review", exact: true });
  await expect(panel.locator("tbody tr").first()).toContainText("n/a");
  const contacts = await page.evaluate(() => window.__tubaViewer.state.resultStates.flatMap(s => Object.entries(s.data.contact_results).filter(([id]) => id.startsWith("NF_")).map(([, contact]) => contact)));
  expect(contacts.length).toBeGreaterThan(20);
  expect(contacts.every(c => c.utilization === null && Math.hypot(...c.tangential_force) < 1e-6)).toBe(true);
});
