import { expect, test } from "@playwright/test";
import { formatQuantity } from "../src/units.js";

// Run against the assembled official gallery with real Code_Aster artifacts.
//
// The review's tables live in the "Tables & issues" drawer below the viewport,
// and selecting a shoe hands its solved history to the inspector, so both are
// opened here the way a reviewer reaches them.
const CONTACT_TABLE = "[data-contact-table]";

// The attested 51-state contact history is a 43 MB scene. Use the same
// readiness budget as its gallery test, then retain all engineering assertions.
test.setTimeout(120_000);

async function openReviewDrawer(page) {
  const drawer = page.locator("[data-review-drawer]");
  if (!(await drawer.evaluate((details) => details.open))) {
    await page.locator("[data-review-drawer] > summary").click();
  }
  await expect(drawer).toHaveJSProperty("open", true);
}

async function openDisplaySection(page) {
  const section = page.locator('details.review-section:has(> summary:text-is("Display"))');
  if (!(await section.evaluate((details) => details.open))) {
    await section.locator("> summary").click();
  }
  await expect(section).toHaveJSProperty("open", true);
}

// A staged contact review navigates by load-path stage, not by a menu of every
// converged increment, so a reviewer lands on an increment by choosing its stage
// and then stepping inside it.
async function openStage(page, stageIndex) {
  const chip = page.locator(".contact-step-nav button").nth(stageIndex);
  await expect(chip).toBeVisible();
  await chip.click();
  await expect(chip).toHaveAttribute("aria-pressed", "true");
  return chip;
}

async function incrementScrubber(page) {
  const scrubber = page.getByRole("slider", { name: /Converged increment within/ });
  await expect(scrubber).toBeVisible();
  return scrubber;
}

// Move to one specific increment: its stage, then its position inside that stage.
// The position comes from the stage record the bundle publishes, so this also
// checks that the increment order the scrubber steps through is the solved order.
async function openIncrement(page, state) {
  await openStage(page, state.metadata.stage_index);
  const scrubber = await incrementScrubber(page);
  const withinStage = await page.evaluate(
    ({ runId, stageIndex, stateId }) => {
      const findings = window.__tubaViewer.state.contactFindings;
      const run = findings?.runs?.find(candidate => candidate.run_id === runId) ?? findings?.primary;
      const stage = run?.stages?.find(candidate => candidate.index === stageIndex);
      return stage ? stage.result_state_ids.indexOf(stateId) : -1;
    },
    { runId: state.metadata.run_id, stageIndex: state.metadata.stage_index, stateId: state.id }
  );
  expect(withinStage, `position of ${state.id} inside stage ${state.metadata.stage_index}`).toBeGreaterThanOrEqual(0);
  await scrubber.fill(String(withinStage));
  await scrubber.dispatchEvent("input");
  await expect.poll(() => page.evaluate(() => window.__tubaViewer.state.activeResultStateId)).toBe(state.id);
}

test("real contact history preserves forces through selection and display scaling", async ({ page }) => {
  // Three complete regime checks rebuild and trace the large scene repeatedly.
  // Keep full failure traces; Linux recording exceeded the shared 120s budget.
  test.setTimeout(180_000);
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/viewer/?bundle=native-friction-review");
  await expect(page.locator("[data-runtime-status]")).toContainText("Ready", { timeout: 45_000 });
  await expect(page.locator("[data-task-rail]")).toBeVisible();
  await openReviewDrawer(page);
  const panel = page.locator(CONTACT_TABLE).getByRole("region", { name: "Contact review", exact: true });
  await expect(panel).toBeVisible();
  const states = await page.evaluate(() => window.__tubaViewer.state.resultStates.map(s => s.data));
  expect(states.length).toBeGreaterThan(20);
  // The load path is the navigation a reviewer uses, and it is the five stages
  // of the cycle rather than the fifty-one increments inside them.
  const chips = page.locator(".contact-step-nav button");
  await expect(chips).toHaveCount(6);
  await expect(chips).toHaveText(["Reference", "Cold", "Hot", "Cold", "Lift", "Reseat"]);
  for (const status of ["sticking", "sliding", "open"]) {
    const state = states.find(s => s.metadata.pseudo_time > 0 && Object.values(s.contact_results).some(c => c.status === status));
    expect(state, `Real ${status} increment`).toBeTruthy();
    const contact = Object.values(state.contact_results).find(c => c.status === status);
    await openIncrement(page, state);
    await panel.getByRole("button", { name: contact.support_id, exact: true }).click();
    // The solved history for the shoe that was just selected.
    const inspector = page.locator("[data-inspector]");
    await expect(inspector.getByRole("heading", { name: `Selected shoe ${contact.support_id}`, exact: true })).toBeVisible();
    const row = panel.locator("tbody tr").filter({ has: page.getByRole("button", { name: contact.support_id, exact: true }) });
    await expect(row).toContainText(`${status} (solver)`);
    const system = await page.evaluate(() => window.__tubaViewer.state.unitSystem);
    await expect(row).toContainText(formatQuantity(contact.normal_force, "N", system));
    await expect(row).toContainText(formatQuantity(contact.gap, "m", system));
    await expect(inspector.locator("svg circle[r='5']")).toHaveCount(1);
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
  await openDisplaySection(page);
  const arrows = page.getByLabel("Normal-force arrows", { exact: true });
  await arrows.uncheck();
  expect(await page.evaluate(() => window.__tubaViewer.state.contactArrows.normal)).toBe(false);
  await arrows.check();
  // Stepping stays keyboard-operable from the rail's own control.
  const activeBefore = await page.evaluate(() => window.__tubaViewer.state.activeResultStateId);
  const scrubber = await incrementScrubber(page);
  await scrubber.focus();
  await page.keyboard.press("ArrowDown");
  await expect.poll(() => page.evaluate(() => window.__tubaViewer.state.activeResultStateId)).not.toBe(activeBefore);
  await page.setViewportSize({ width: 800, height: 900 });
  await expect(panel).toBeVisible();
  await page.screenshot({ path: "../.build/friction-narrow.png", fullPage: true });
  expect(errors).toEqual([]);
});

test("every shoe is drawn on one force-against-travel plot, from the real history", async ({ page }) => {
  // The per-shoe chart in the inspector only ever draws one shoe, so this plot is
  // the only place two shoes can be compared without reading one and then the
  // other. It is checked against the real 51-state history, not a fixture.
  test.setTimeout(180_000);
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/viewer/?bundle=native-friction-review");
  await expect(page.locator("[data-runtime-status]")).toContainText("Ready", { timeout: 45_000 });
  await openReviewDrawer(page);
  // Hot is where the friction copy is on its cone and the frictionless copy is not.
  await openStage(page, 2);
  const plot = page.locator(".contact-review svg").last();
  await expect(plot).toBeVisible();
  for (const id of ["F_S1", "F_S2", "NF_S1", "NF_S2"]) {
    await expect(plot).toContainText(id);
  }
  // One solid force line per shoe, its cone bounds dashed.
  await expect(plot.locator('path[stroke]:not([stroke="#64748b"]):not([stroke-dasharray])')).toHaveCount(4);
  // The legend must not tell a frictionless shoe it used a fraction of a cone.
  await expect(plot).toContainText("no cone (μ = 0)");
  await expect(plot).toContainText("100% of cone");
  // Every shoe carries a point per converged increment, so 51 each.
  await expect(plot.locator("circle")).toHaveCount(51 * 4 + 4);
  // The travel axis is not pinned to a float artifact at the origin.
  await expect(plot).toContainText("travel [mm]: 0 …");
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
  await expect(page.locator("[data-runtime-status]")).toContainText("Ready", { timeout: 45_000 });
  await expect(page.locator("[data-task-rail]")).toBeVisible();
  await openReviewDrawer(page);
  const panel = page.locator(CONTACT_TABLE).getByRole("region", { name: "Contact review", exact: true });
  await expect(panel).toContainText("Contact results unavailable for this state.");
  await expect(panel.locator("tbody tr")).toHaveCount(0);
});

test("frictionless copy displays zero force and no utilization in the shared solve", async ({ page }) => {
  await page.goto("/viewer/?bundle=native-friction-review");
  await expect(page.locator("[data-runtime-status]")).toContainText("Ready", { timeout: 45_000 });
  await expect(page.locator("[data-task-rail]")).toBeVisible();
  await openReviewDrawer(page);
  const panel = page.locator(CONTACT_TABLE).getByRole("region", { name: "Contact review", exact: true });
  await expect(panel.locator("tbody tr").first()).toContainText("n/a");
  const contacts = await page.evaluate(() => window.__tubaViewer.state.resultStates.flatMap(s => Object.entries(s.data.contact_results).filter(([id]) => id.startsWith("NF_")).map(([, contact]) => contact)));
  expect(contacts.length).toBeGreaterThan(20);
  expect(contacts.every(c => c.utilization === null && Math.hypot(...c.tangential_force) < 1e-6)).toBe(true);
});
