import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { createServer as createNetServer } from "node:net";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";
import { createServer } from "vite";

const viewerRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const scenario = process.argv[2] ?? "smoke";

async function rememberCanvas(page) {
  await page.locator("[data-canvas]").evaluate((canvas) => {
    window.__tubaE2eCanvas = canvas;
    canvas.dataset.e2ePersistent = "true";
  });
}

async function assertSameCanvas(page) {
  assert.equal(
    await page.evaluate(() => document.querySelector('[data-canvas][data-e2e-persistent="true"]') === window.__tubaE2eCanvas),
    true
  );
  assert.equal(await page.locator('[data-canvas][data-e2e-persistent="true"]').isVisible(), true);
}

async function assertInspectorIdentity(page, objectId, entityRef) {
  const identity = page.locator("[data-properties] .property-section").filter({
    has: page.getByRole("heading", { level: 3, name: "Identity", exact: true })
  });
  assert.equal(await identity.isVisible(), true);
  const text = await identity.textContent();
  assert.ok(text.includes(objectId), `inspector identity must include ${objectId}: ${text}`);
  assert.ok(text.includes(entityRef), `inspector identity must include ${entityRef}: ${text}`);
}

const scenarios = {
  smoke: {
    bundle: "/smoke-scene",
    minimumObjects: 3
  },
  "layer-state": {
    bundle: "/test/fixtures/layer_state_scene",
    minimumObjects: 3,
    async run(page) {
      const layers = page.locator("[data-display-tools-home] details").filter({ hasText: "Layers" });
      await layers.evaluate((details) => {
        details.open = true;
      });
      assert.equal(await layers.evaluate((details) => details.open), true);
      await page.getByLabel(/Deformed Visual Centerline/).uncheck();
      await page.waitForFunction(() => {
        const ids = window.__tubaViewer?.lastRender?.objectIds ?? [];
        return ids.length === 2 && ids.includes("object:cold") && ids.includes("object:clash") && !ids.includes("object:deformed");
      });

      await page.getByLabel(/Overlay Clash/).uncheck();
      await page.waitForFunction(() => {
        const ids = window.__tubaViewer?.lastRender?.objectIds ?? [];
        return ids.length === 1 && ids[0] === "object:cold";
      });
    }
  },
  "scene-inspection": {
    bundle: "/test/fixtures/inspection_scene",
    minimumObjects: 3,
    async run(page) {
      await page.getByRole("button", { name: /Insulated pipe/ }).click();
      let properties = await page.locator("[data-properties]").textContent();
      assert.match(properties, /mineral_wool/);
      assert.match(properties, /effective_radius_m/);
      assert.match(properties, /57000000/);

      await page.getByRole("button", { name: /Copy Entity Ref/ }).click();
      await page.waitForFunction(() => /Copied element:pipe_insulated/.test(document.querySelector("[data-status]")?.textContent ?? ""));

      await page.getByRole("button", { name: /Clash marker/ }).click();
      properties = await page.locator("[data-properties]").textContent();
      assert.match(properties, /element:pipe_insulated/);
      assert.match(properties, /distance_m/);
      assert.match(properties, /0\.04/);

      await page.getByRole("button", { name: /Analysis mesh element/ }).click();
      properties = await page.locator("[data-properties]").textContent();
      assert.match(properties, /source_ref/);
      assert.match(properties, /native_element/);
    }
  },
  "review-workflow": {
    bundle: "/test/fixtures/code_aster_results",
    minimumObjects: 7,
    async run(page) {
      const reviewTask = page.getByRole("button", { name: "Review", exact: true });
      await reviewTask.waitFor();
      assert.equal(await reviewTask.getAttribute("aria-current"), "page");
      assert.equal(await page.locator("[data-viewer-workspace]").isVisible(), true);
      assert.equal(await page.locator("[data-cockpit-status]").isVisible(), true);
      assert.equal(await page.locator("[data-inspector]").isHidden(), true);
      assert.equal(
        await page.getByRole("tab", { name: "Governing Results", exact: true }).getAttribute("aria-selected"),
        "true"
      );
      await rememberCanvas(page);

      await page.getByRole("button", { name: "Model", exact: true }).click();
      await page.getByRole("heading", { level: 1, name: "Model", exact: true }).waitFor();
      await assertSameCanvas(page);
      await page.getByRole("button", { name: "Load Cases", exact: true }).click();
      await page.getByRole("heading", { level: 1, name: "Load Cases", exact: true }).waitFor();
      await assertSameCanvas(page);
      await page.getByRole("button", { name: "Results", exact: true }).click();
      await page.getByRole("heading", { level: 1, name: "Results", exact: true }).waitFor();
      await assertSameCanvas(page);

      assert.equal(await page.getByRole("combobox", { name: /^Load case/ }).inputValue(), "Hot");
      assert.equal(await page.getByRole("combobox", { name: /^Result state/ }).inputValue(), "result_state:Hot");
      await page.setViewportSize({ width: 800, height: 900 });
      await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      const compactLayout = await page.evaluate(() => {
        const workspace = document.querySelector("[data-viewer-workspace]").getBoundingClientRect();
        const launcher = document.querySelector("[data-task-rail]");
        const rail = launcher.getBoundingClientRect();
        const canvas = document.querySelector("[data-canvas]").getBoundingClientRect();
        const style = getComputedStyle(launcher);
        return {
          workspace: { left: workspace.left, right: workspace.right },
          rail: { top: rail.top, bottom: rail.bottom },
          canvas: { left: canvas.left, right: canvas.right, top: canvas.top, width: canvas.width, height: canvas.height },
          display: style.display,
          overflowX: style.overflowX,
          overflowY: style.overflowY
        };
      });
      assert.equal(compactLayout.display, "flex");
      assert.equal(compactLayout.overflowX, "auto");
      assert.equal(compactLayout.overflowY, "hidden");
      assert.ok(compactLayout.rail.bottom <= compactLayout.canvas.top + 1, JSON.stringify(compactLayout));
      assert.ok(Math.abs(compactLayout.canvas.left - compactLayout.workspace.left) <= 1, JSON.stringify(compactLayout));
      assert.ok(Math.abs(compactLayout.canvas.right - compactLayout.workspace.right) <= 1, JSON.stringify(compactLayout));
      assert.ok(compactLayout.canvas.width >= 480, `compact canvas width is too small: ${JSON.stringify(compactLayout)}`);
      assert.ok(compactLayout.canvas.height >= 240, `compact canvas height is too small: ${JSON.stringify(compactLayout)}`);
      const compactStatus = await page.locator("[data-cockpit-status]").textContent();
      assert.match(compactStatus, /Analysis\s*solved/i);
      assert.match(compactStatus, /Governing case\s*Not available/i);
      await page.getByRole("tab", { name: "Warnings", exact: true }).click();
      await page.getByRole("heading", { level: 1, name: "Issues", exact: true }).waitFor();
      await assertSameCanvas(page);
      await page.getByRole("button", { name: "Results", exact: true }).click();
      await page.getByRole("heading", { level: 1, name: "Results", exact: true }).waitFor();
      assert.equal(await page.getByRole("button", { name: "Results", exact: true }).getAttribute("aria-current"), "page");
      await assertSameCanvas(page);
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      assert.equal(await page.evaluate(() => window.innerWidth), 1440);
      await assertSameCanvas(page);
      await page.setViewportSize({ width: 1024, height: 768 });
      await page.getByRole("button", { name: "Show element:pipe_hot in 3D", exact: true }).first().click();
      await page.waitForFunction(() => {
        const state = window.__tubaViewer?.state;
        return (
          state?.activeTab === "results" &&
          state?.selectedObjectIds?.includes("object:pipe:hot") &&
          state?.activeLoadCase === "Hot" &&
          state?.activeResultStateId === "result_state:Hot"
        );
      });
      assert.equal(await page.locator("[data-canvas]").isVisible(), true);
      assert.equal(await page.locator("[data-inspector]").isVisible(), true);
      await assertInspectorIdentity(page, "object:pipe:hot", "element:pipe_hot");
      assert.equal(
        await page.locator('[data-workflow-panel] tr[data-entity-ref="element:pipe_hot"][data-selected="true"]').first().isVisible(),
        true
      );
      const narrowLayout = await page.evaluate(() => {
        const canvas = document.querySelector("[data-canvas]").getBoundingClientRect();
        const inspector = document.querySelector("[data-inspector]");
        const drawer = inspector.getBoundingClientRect();
        return {
          canvas: { left: canvas.left, right: canvas.right, top: canvas.top, bottom: canvas.bottom, width: canvas.width },
          drawer: { left: drawer.left, right: drawer.right, top: drawer.top, bottom: drawer.bottom },
          drawerPosition: getComputedStyle(inspector).position
        };
      });
      assert.equal(narrowLayout.drawerPosition, "absolute");
      assert.ok(
        narrowLayout.drawer.left < narrowLayout.canvas.right &&
          narrowLayout.drawer.right > narrowLayout.canvas.left &&
          narrowLayout.drawer.top < narrowLayout.canvas.bottom &&
          narrowLayout.drawer.bottom > narrowLayout.canvas.top,
        `inspector must overlap the canvas as a drawer: ${JSON.stringify(narrowLayout)}`
      );
      assert.ok(narrowLayout.canvas.width >= 480, `canvas width is too small: ${JSON.stringify(narrowLayout)}`);
      await page.setViewportSize({ width: 1440, height: 900 });

      const reviewContext = await page.evaluate(() => ({
        activeTab: window.__tubaViewer?.state?.activeTab,
        activeLoadCase: window.__tubaViewer?.state?.activeLoadCase,
        activeResultStateId: window.__tubaViewer?.state?.activeResultStateId,
        selectedObjectIds: window.__tubaViewer?.state?.selectedObjectIds
      }));
      assert.deepEqual(reviewContext, {
        activeTab: "results",
        activeLoadCase: "Hot",
        activeResultStateId: "result_state:Hot",
        selectedObjectIds: ["object:pipe:hot"]
      });
    }
  },
  "public-code-aster-review": {
    bundle: "/code-aster-review",
    minimumObjects: 1,
    async beforeNavigate(page) {
      page.__tubaUnexpectedBrowserEvents = [];
      page.on("pageerror", (error) => page.__tubaUnexpectedBrowserEvents.push(`pageerror: ${error.message}`));
      page.on("console", (message) => {
        if (message.type() === "error") {
          page.__tubaUnexpectedBrowserEvents.push(`console: ${message.text()}`);
        }
      });
      page.on("requestfailed", (request) => {
        page.__tubaUnexpectedBrowserEvents.push(
          `requestfailed: ${request.url()} ${request.failure()?.errorText ?? "unknown"}`
        );
      });
    },
    async run(page) {
      await page.waitForFunction(
        () => window.__tubaViewer?.state?.review?.schema_version === "engineering_review.v1"
      );
      const reviewTask = page.getByRole("button", { name: "Review", exact: true });
      await reviewTask.waitFor();
      assert.equal(await reviewTask.getAttribute("aria-current"), "page");
      assert.equal(await page.locator("[data-viewer-workspace]").isVisible(), true);
      assert.equal(await page.locator("[data-cockpit-status]").isVisible(), true);
      assert.equal(await page.locator("[data-inspector]").isHidden(), true);
      await rememberCanvas(page);

      const loaded = await page.evaluate(() => {
        const viewer = window.__tubaViewer;
        const state = viewer.state;
        const reviewDiagnostics = state.review?.tables?.diagnostics?.rows ?? [];
        return {
          objects: state.objects.length,
          geometryPayloads: state.geometryPayloads.length,
          overlays: state.overlays.length,
          reviewLoadDiagnostics: state.reviewDiagnostics,
          missingNodeGeometry: state.diagnostics.filter(
            (diagnostic) => diagnostic.code === "result_state.missing_node_geometry"
          ),
          solverParserDiagnostics: reviewDiagnostics.filter(
            (diagnostic) => diagnostic.code === "SOLVER_PARSER_DIAGNOSTIC"
          ),
          parserDiagnosticOverlays: state.overlays.filter(
            (overlay) => overlay.data?.result_type === "parser_diagnostics"
          ),
          renderDiagnostics: viewer.lastRender.diagnostics
        };
      });
      assert.equal(loaded.objects, 216);
      assert.equal(loaded.geometryPayloads, 213);
      assert.equal(loaded.overlays, 7);
      assert.deepEqual(loaded.reviewLoadDiagnostics, []);
      assert.deepEqual(loaded.missingNodeGeometry, []);
      assert.deepEqual(loaded.solverParserDiagnostics, []);
      assert.deepEqual(loaded.parserDiagnosticOverlays, []);
      assert.deepEqual(loaded.renderDiagnostics, []);

      await page.getByRole("button", { name: "Results", exact: true }).click();
      await page.getByRole("heading", { level: 1, name: "Results", exact: true }).waitFor();
      await assertSameCanvas(page);
      assert.equal(await page.getByRole("combobox", { name: /^Load case/ }).inputValue(), "Operating");
      assert.equal(
        await page.getByRole("combobox", { name: /^Result state/ }).inputValue(),
        "result_state:Operating"
      );
      await page.getByRole("button", { name: "Show element:pipe_str_0 in 3D", exact: true }).first().click();
      await page.waitForFunction(() => {
        const state = window.__tubaViewer?.state;
        return (
          state?.activeTab === "results" &&
          state?.selectedObjectIds?.includes("object:element:pipe_str_0") &&
          state?.activeLoadCase === "Operating" &&
          state?.activeResultStateId === "result_state:Operating"
        );
      });
      assert.equal(await page.locator("[data-canvas]").isVisible(), true);
      assert.equal(await page.locator("[data-inspector]").isVisible(), true);
      await assertInspectorIdentity(page, "object:element:pipe_str_0", "element:pipe_str_0");
      assert.equal(
        await page.locator('[data-workflow-panel] tr[data-entity-ref="element:pipe_str_0"][data-selected="true"]').first().isVisible(),
        true
      );

      assert.deepEqual(page.__tubaUnexpectedBrowserEvents, []);
    }
  },
  "default-public-review": {
    bundle: null,
    minimumObjects: 1,
    async run(page) {
      const loaded = await page.evaluate(() => ({
        sceneId: window.__tubaViewer?.state?.sceneId,
        analysisStatus: window.__tubaViewer?.state?.review?.analysis_status
      }));
      assert.equal(loaded.sceneId, "scene:code_aster_artifact_review");
      assert.equal(loaded.analysisStatus, "solved");
    }
  },
  "legacy-workflow": {
    bundle: "/smoke-scene",
    minimumObjects: 3,
    async beforeNavigate(page) {
      await page.route("**/smoke-scene/review.json", (route) =>
        route.fulfill({ status: 404, contentType: "application/json", body: "" })
      );
    },
    async run(page) {
      const displayTask = page.getByRole("button", { name: "Display", exact: true });
      await displayTask.waitFor();
      assert.equal(await displayTask.getAttribute("aria-current"), "page");
      assert.equal(await page.getByRole("button", { name: "Issues", exact: true }).count(), 1);
      assert.equal(await page.getByRole("button", { name: "Review", exact: true }).count(), 0);
      assert.equal(await page.getByRole("tab", { name: "Warnings", exact: true }).count(), 1);
      assert.equal(await page.getByRole("tab", { name: "Governing Results", exact: true }).count(), 0);
      assert.equal(await page.locator("[data-viewer-workspace]").isVisible(), true);
      assert.equal(await page.locator("[data-canvas]").isVisible(), true);
      assert.equal(await page.locator("[data-inspector]").isHidden(), true);
      assert.equal(await page.getByRole("status").getAttribute("data-error"), "false");
      const legacyState = await page.evaluate(() => ({
        activeTab: window.__tubaViewer?.state?.activeTab,
        legacyReview: window.__tubaViewer?.state?.legacyReview,
        review: window.__tubaViewer?.state?.review,
        reviewDiagnostics: window.__tubaViewer?.state?.reviewDiagnostics
      }));
      assert.deepEqual(legacyState, {
        activeTab: "3d",
        legacyReview: true,
        review: null,
        reviewDiagnostics: []
      });
    }
  },
  "embedded-review": {
    bundle: "/test/fixtures/code_aster_results",
    minimumObjects: 7,
    query() {
      return { embed: "1" };
    },
    async run(page) {
      await page.waitForFunction(() => window.__tubaViewer?.state?.activeTab === "3d");
      assert.equal(await page.getByRole("banner").isVisible(), false);
      assert.equal(await page.locator("[data-task-rail]").isVisible(), false);
      assert.equal(await page.locator("[data-cockpit-status]").isVisible(), false);
      assert.equal(await page.locator("[data-evidence-dock]").isVisible(), false);
      assert.equal(await page.locator("[data-inspector]").isVisible(), false);
      assert.equal(await page.getByLabel("Interactive 3D engineering review viewport").isVisible(), true);
      assert.equal(await page.evaluate(() => window.__tubaViewer?.state?.embed), true);
    }
  },
  "code-aster-results": {
    bundle: "/test/fixtures/code_aster_results",
    minimumObjects: 7,
    async run(page) {
      const shellLayout = await page.evaluate(() => {
        const rect = (selector) => document.querySelector(selector)?.getBoundingClientRect();
        const shell = rect("[data-embed]");
        const header = rect("[data-app-header]");
        const panel = rect("[data-workflow-panel]");
        return { shell, header, panel };
      });
      assert.ok(shellLayout.header.width >= shellLayout.shell.width - 1, `header must span shell: ${JSON.stringify(shellLayout)}`);
      assert.ok(shellLayout.panel.width >= shellLayout.shell.width - 1, `review panel must span shell: ${JSON.stringify(shellLayout)}`);
      assert.ok(shellLayout.panel.height >= 500, `review panel must fill remaining viewport: ${JSON.stringify(shellLayout)}`);

      const workflowPanel = page.locator("[data-workflow-panel]");
      await workflowPanel.focus();
      const lightFocus = await workflowPanel.evaluate((element) => {
        const style = getComputedStyle(element);
        return { backgroundColor: style.backgroundColor, outlineColor: style.outlineColor, outlineWidth: style.outlineWidth };
      });
      assert.deepEqual(lightFocus, {
        backgroundColor: "rgb(243, 244, 242)",
        outlineColor: "rgb(11, 118, 132)",
        outlineWidth: "3px"
      });

      const summaryTab = page.getByRole("tab", { name: "Summary", exact: true });
      assert.equal(await summaryTab.getAttribute("aria-selected"), "true");
      assert.equal(await summaryTab.getAttribute("aria-controls"), "engineering-workflow-panel");
      await summaryTab.focus();
      await summaryTab.press("ArrowRight");
      const modelTab = page.getByRole("tab", { name: "Model", exact: true });
      assert.equal(await modelTab.getAttribute("aria-selected"), "true");
      assert.equal(await modelTab.evaluate((element) => element === document.activeElement), true);
      const darkChromeFocus = await modelTab.evaluate((element) => {
        const style = getComputedStyle(element);
        return {
          backgroundColor: getComputedStyle(element.parentElement).backgroundColor,
          outlineColor: style.outlineColor,
          outlineWidth: style.outlineWidth
        };
      });
      assert.deepEqual(darkChromeFocus, {
        backgroundColor: "rgb(32, 42, 49)",
        outlineColor: "rgb(94, 216, 229)",
        outlineWidth: "3px"
      });
      await modelTab.press("Home");
      assert.equal(await summaryTab.getAttribute("aria-selected"), "true");
      await summaryTab.press("End");
      const diagnosticsTab = page.getByRole("tab", { name: "Diagnostics", exact: true });
      assert.equal(await diagnosticsTab.getAttribute("aria-selected"), "true");
      await diagnosticsTab.press("Home");
      assert.equal(await summaryTab.getAttribute("aria-selected"), "true");

      assert.equal(await page.locator("[data-result-tools]").count(), 1);
      await page.getByRole("tab", { name: "Results", exact: true }).click();
      assert.equal(await page.locator("[data-workflow-panel] > [data-result-tools]").count(), 1);
      let legend = await page.locator("[data-result-legend]").textContent();
      assert.match(legend, /max_von_mises/);
      assert.match(legend, /Pa/);

      let hotspots = await page.locator("[data-hotspot-list]").textContent();
      assert.match(hotspots, /Hot pipe/);
      assert.match(hotspots, /Warm pipe/);

      await page.getByLabel(/Stress threshold/i).evaluate((input) => {
        input.value = "50000000";
        input.dispatchEvent(new Event("change", { bubbles: true }));
      });
      hotspots = await page.locator("[data-hotspot-list]").textContent();
      assert.match(hotspots, /Hot pipe/);
      assert.doesNotMatch(hotspots, /Warm pipe/);

      await page.locator("[data-hotspot-list]").getByRole("button", { name: /Hot pipe/ }).click();
      await page.getByRole("tab", { name: "Load Cases", exact: true }).click();
      assert.equal(await page.locator("[data-workflow-panel] > [data-result-tools]").count(), 1);
      await page.getByRole("tab", { name: "Results", exact: true }).click();

      await page.getByLabel(/Displacement vector scale/i).evaluate((input) => {
        input.value = "10";
        input.dispatchEvent(new Event("input", { bubbles: true }));
      });
      await page.waitForFunction(() => window.__tubaViewer?.state?.resultVectorScales?.displacement === 10);

      const threeDimensionalTab = page.getByRole("tab", { name: "3D", exact: true });
      assert.equal(await threeDimensionalTab.getAttribute("aria-controls"), "engineering-3d-panel");
      await threeDimensionalTab.click();
      const threeDimensionalHeading = page.getByRole("heading", { level: 1, name: "3D Engineering Review" });
      assert.equal(await threeDimensionalHeading.count(), 1);
      const objectButton = page.locator("[data-object-list] button").first();
      await objectButton.focus();
      await page.keyboard.press("Tab");
      await page.keyboard.press("Shift+Tab");
      const darkControlFocus = await objectButton.evaluate((element) => {
        const style = getComputedStyle(element);
        return { backgroundColor: style.backgroundColor, outlineColor: style.outlineColor, outlineWidth: style.outlineWidth };
      });
      assert.deepEqual(darkControlFocus, {
        backgroundColor: "rgb(38, 50, 58)",
        outlineColor: "rgb(94, 216, 229)",
        outlineWidth: "3px"
      });
      assert.equal(await page.locator("[data-result-tools-home] > [data-result-tools]").count(), 1);
      assert.equal(await page.locator("[data-viewer-workspace]").getAttribute("aria-labelledby"), "workflow-tab-3d");
      const workspaceLayout = await page.evaluate(() => {
        const workspace = document.querySelector("[data-viewer-workspace]").getBoundingClientRect();
        const canvas = document.querySelector("[data-canvas]").getBoundingClientRect();
        return {
          workspace: { width: workspace.width, height: workspace.height },
          canvas: { width: canvas.width, height: canvas.height }
        };
      });
      assert.ok(workspaceLayout.workspace.width >= 1000, `3D workspace width is too small: ${JSON.stringify(workspaceLayout)}`);
      assert.ok(workspaceLayout.workspace.height >= 500, `3D workspace height is too small: ${JSON.stringify(workspaceLayout)}`);
      assert.ok(workspaceLayout.canvas.width >= 400, `3D canvas width is too small: ${JSON.stringify(workspaceLayout)}`);
      assert.ok(workspaceLayout.canvas.height >= 500, `3D canvas height is too small: ${JSON.stringify(workspaceLayout)}`);
      let properties = await page.locator("[data-properties]").textContent();
      assert.match(properties, /max_von_mises/);
      assert.match(properties, /57000000/);

      await page.getByLabel(/Deformed Visual Centerline/).uncheck();
      await page.waitForFunction(() => {
        const ids = window.__tubaViewer?.lastRender?.objectIds ?? [];
        return ids.includes("object:deformed_physical") && !ids.includes("object:deformed_visual");
      });
      await page.getByLabel(/Deformed Physical Centerline/).uncheck();
      await page.waitForFunction(() => {
        const ids = window.__tubaViewer?.lastRender?.objectIds ?? [];
        return !ids.includes("object:deformed_physical") && !ids.includes("object:deformed_visual");
      });

      await page.getByRole("button", { name: /Operating clash marker/ }).click();
      properties = await page.locator("[data-properties]").textContent();
      assert.match(properties, /operating_distance_m/);
      assert.match(properties, /0\.04/);

      await page.getByLabel(/Visual deformation scale/i).evaluate((input) => {
        input.value = "80";
        input.dispatchEvent(new Event("input", { bubbles: true }));
      });
      await page.waitForFunction(() => window.__tubaViewer?.state?.visualDeformationScale === 80);
      properties = await page.locator("[data-properties]").textContent();
      assert.match(properties, /operating_distance_m/);
      assert.match(properties, /0\.04/);

      const embedUrl = new URL(page.url());
      embedUrl.searchParams.set("embed", "1");
      await page.goto(embedUrl.toString(), { waitUntil: "domcontentloaded" });
      await page.waitForFunction(() => /Ready/.test(document.querySelector("[data-status]")?.textContent ?? ""));
      await page.waitForFunction(() => document.querySelector("[data-canvas]")?.dataset.renderer === "three");
      const embedLayout = await page.evaluate(() => {
        const workspace = document.querySelector("[data-viewer-workspace]").getBoundingClientRect();
        const canvas = document.querySelector("[data-canvas]").getBoundingClientRect();
        return {
          viewport: { width: window.innerWidth, height: window.innerHeight },
          workspace: { width: workspace.width, height: workspace.height },
          canvas: { width: canvas.width, height: canvas.height },
          activeTab: window.__tubaViewer?.state?.activeTab
        };
      });
      assert.equal(embedLayout.activeTab, "3d");
      assert.equal(await page.getByRole("heading", { level: 1, name: "3D Engineering Review" }).count(), 1);
      assert.ok(embedLayout.workspace.width >= embedLayout.viewport.width - 1, `embed workspace must fill viewport width: ${JSON.stringify(embedLayout)}`);
      assert.ok(embedLayout.workspace.height >= embedLayout.viewport.height - 1, `embed workspace must fill viewport height: ${JSON.stringify(embedLayout)}`);
      assert.ok(embedLayout.canvas.width >= embedLayout.viewport.width - 1, `embed canvas must fill viewport width: ${JSON.stringify(embedLayout)}`);
      assert.ok(embedLayout.canvas.height >= embedLayout.viewport.height - 1, `embed canvas must fill viewport height: ${JSON.stringify(embedLayout)}`);

      await page.reload({ waitUntil: "domcontentloaded" });
      await page.waitForFunction(() => window.__tubaViewer?.state?.activeTab === "3d");
      assert.equal(await page.locator("[data-app-header]").isVisible(), false);
      assert.equal(await page.locator("[data-workflow-tabs]").isVisible(), false);
    }
  },
  "clash-review": {
    bundle: "/test/fixtures/code_aster_results",
    minimumObjects: 7,
    async run(page) {
      await page.getByRole("tab", { name: "3D", exact: true }).click();
      await page.getByRole("heading", { level: 1, name: "3D Engineering Review" }).waitFor();
      await page.getByLabel(/Operating-only/).check();
      await page.waitForFunction(() => /ERROR - Hot - open/.test(document.querySelector("[data-issue-list]")?.textContent ?? ""));
      await page.getByRole("button", { name: /^ERROR - Operating pipe\/rack clash$/ }).click();

      let properties = await page.locator("[data-properties]").textContent();
      assert.match(properties, /cold_distance_m/);
      assert.match(properties, /operating_distance_m/);
      assert.match(properties, /penetration_m/);
      assert.match(properties, /envelope_type/);
      assert.match(properties, /load_case/);
      assert.match(properties, /0\.04/);

      await page.getByLabel(/Issue Status/).selectOption("resolved");
      await page.getByLabel(/Issue Comment/).fill("Reviewed in browser");
      await page.getByLabel(/Issue Comment/).dispatchEvent("change");
      await page.getByRole("button", { name: /Export BCF/ }).click();
      await page.waitForFunction(() => /BCF ready issue:operating_clash/.test(document.querySelector("[data-status]")?.textContent ?? ""));

      await page.getByRole("button", { name: /Isolate selected/ }).click();
      await page.waitForFunction(() => {
        const ids = window.__tubaViewer?.lastRender?.objectIds ?? [];
        return ids.includes("object:pipe:hot") && ids.includes("object:clash") && !ids.includes("object:reaction_vector");
      });

      await page.getByRole("button", { name: /Restore view/ }).click();
      await page.waitForFunction(() => (window.__tubaViewer?.lastRender?.objectIds ?? []).includes("object:reaction_vector"));

      const state = await page.evaluate(() => window.__tubaViewer?.state);
      assert.equal(state.activeIssueId, "issue:operating_clash");
      assert.equal(state.issueReviewState["issue:operating_clash"].status, "resolved");
      assert.equal(state.issueReviewState["issue:operating_clash"].comment, "Reviewed in browser");
    }
  },
  "live-preview": {
    bundle: "/smoke-scene",
    minimumObjects: 3,
    async setup() {
      return startTestWebSocketServer();
    },
    query(runtime) {
      return { preview_ws: runtime.url };
    },
    async run(page, runtime) {
      await page.waitForFunction(() => window.__tubaViewer?.state?.sceneId === "viewer_smoke_scene");
      await runtime.waitForClient();
      runtime.send({ type: "run_started", run_id: "run:live-preview" });
      await page.waitForFunction(() => /Preview run started/.test(document.querySelector("[data-status]")?.textContent ?? ""));

      runtime.send({ type: "scene_reloaded", run_id: "run:live-preview", bundle_url: "/test/fixtures/code_aster_results" });
      await page.waitForFunction(() => window.__tubaViewer?.state?.sceneId === "scene:code_aster_results");
      assert.equal(await page.evaluate(() => window.__tubaViewer?.state?.activeTab), "3d");
      const navigationCount = await page.evaluate(() => performance.getEntriesByType("navigation").length);
      assert.equal(navigationCount, 1);

      runtime.send({
        type: "diagnostic",
        run_id: "run:live-preview",
        diagnostic: { severity: "error", code: "visualization.preview.python_error", message: "preview boom" }
      });
      await page.waitForFunction(() => /preview boom/.test(document.querySelector("[data-status]")?.textContent ?? ""));

      const previewEvents = await page.evaluate(() => window.__tubaViewer?.previewEvents ?? []);
      assert.deepEqual(previewEvents.map((event) => event.type), ["run_started", "scene_reloaded", "diagnostic"]);
    }
  },
  "patch-preview": {
    bundle: "/smoke-scene",
    minimumObjects: 3,
    async setup() {
      return startTestWebSocketServer();
    },
    query(runtime) {
      return { preview_ws: runtime.url };
    },
    async run(page, runtime) {
      await page.waitForFunction(() => window.__tubaViewer?.state?.sceneId === "viewer_smoke_scene");
      await runtime.waitForClient();
      runtime.send({ type: "run_started", mode: "json_patch", revision: 12 });
      await page.waitForFunction(() => /Preview run 12 started/.test(document.querySelector("[data-status]")?.textContent ?? ""));

      runtime.send({
        type: "scene_reloaded",
        mode: "json_patch",
        revision: 12,
        bundle_revision: 12,
        bundle_url: "/test/fixtures/patch_preview_scene"
      });
      await page.waitForFunction(() => window.__tubaViewer?.state?.sceneId === "scene:patch_preview");
      await page.waitForFunction(() => (window.__tubaViewer?.lastRender?.objectIds ?? []).includes("object:proposal_pipe"));
      const navigationCount = await page.evaluate(() => performance.getEntriesByType("navigation").length);
      assert.equal(navigationCount, 1);

      const layerText = await page.locator("[data-layer-list]").textContent();
      assert.match(layerText, /Agent Proposal Added/);
      const objectText = await page.locator("[data-object-list]").textContent();
      assert.match(objectText, /Proposed pipe/);

      runtime.send({
        type: "diagnostic",
        mode: "json_patch",
        revision: 13,
        payload: {
          severity: "error",
          code: "visualization.patch_preview.invalid_patch",
          message: "patch schema failed"
        }
      });
      await page.waitForFunction(() => /patch schema failed/.test(document.querySelector("[data-status]")?.textContent ?? ""));
      const diagnostics = await page.locator("[data-diagnostic-list]").textContent();
      assert.match(diagnostics, /visualization.patch_preview.invalid_patch/);

      const previewEvents = await page.evaluate(() => window.__tubaViewer?.previewEvents ?? []);
      assert.deepEqual(previewEvents.map((event) => event.type), ["run_started", "scene_reloaded", "diagnostic"]);
    }
  },
  "scene-diff": {
    bundle: "/smoke-scene",
    minimumObjects: 3,
    async setup() {
      return startTestWebSocketServer();
    },
    query(runtime) {
      return { preview_ws: runtime.url };
    },
    async run(page, runtime) {
      await page.waitForFunction(() => window.__tubaViewer?.state?.sceneId === "viewer_smoke_scene");
      await page.getByRole("button", { name: /Smoke pipe - pipe/ }).click();
      await page.waitForFunction(() => (window.__tubaViewer?.state?.selectedObjectIds ?? []).includes("object:element:pipe_smoke"));
      await runtime.waitForClient();

      runtime.send({
        type: "scene_diff",
        revision: 21,
        payload: {
          diff_id: "diff:add-support",
          base_scene_id: "viewer_smoke_scene",
          added_objects: [
            {
              id: "object:diff_support",
              kind: "support",
              name: "Diff support",
              geometry_asset_id: "asset:diff_support",
              layer_ids: ["supports"]
            }
          ],
          added_geometry_assets: [
            {
              id: "asset:diff_support",
              format: "point",
              bounds: [1, 0.45, 0, 1, 0.45, 0],
              object_ids: ["object:diff_support"],
              generation_config: { point: [1, 0.45, 0], radius_m: 0.08 }
            }
          ],
          diagnostics: [{ severity: "warning", code: "visualization.scene_diff.partial", message: "partial diff applied" }]
        }
      });
      await page.waitForFunction(() => window.__tubaViewer?.state?.lastSceneDiffStatus?.applied === true);
      await page.waitForFunction(() => (window.__tubaViewer?.lastRender?.objectIds ?? []).includes("object:diff_support"));
      let state = await page.evaluate(() => window.__tubaViewer?.state);
      assert.equal(state.sceneId, "viewer_smoke_scene");
      assert.deepEqual(state.selectedObjectIds, ["object:element:pipe_smoke"]);
      assert.match(await page.locator("[data-object-list]").textContent(), /Diff support/);
      assert.match(await page.locator("[data-diagnostic-list]").textContent(), /visualization.scene_diff.partial/);
      assert.equal(await page.evaluate(() => performance.getEntriesByType("navigation").length), 1);

      runtime.send({
        type: "scene_diff",
        revision: 22,
        bundle_url: "/test/fixtures/code_aster_results",
        payload: { diff_id: "diff:fallback", base_scene_id: "scene:other", added_objects: [] }
      });
      await page.waitForFunction(() => window.__tubaViewer?.state?.sceneId === "scene:code_aster_results");
      state = await page.evaluate(() => window.__tubaViewer?.state);
      assert.equal(state.lastSceneDiffStatus?.applied, undefined);
      assert.equal(await page.evaluate(() => performance.getEntriesByType("navigation").length), 1);

      const previewEvents = await page.evaluate(() => window.__tubaViewer?.previewEvents ?? []);
      assert.deepEqual(previewEvents.map((event) => event.type), ["scene_diff", "scene_diff"]);
    }
  }
};
const selected = scenarios[scenario];

if (!selected) {
  throw new Error(`Unknown e2e scenario '${scenario}'. Expected one of: ${Object.keys(scenarios).join(", ")}`);
}

let browser;
let server;
let runtime;

try {
  runtime = await selected.setup?.();
  server = await createServer({
    root: viewerRoot,
    logLevel: "error",
    server: {
      host: "127.0.0.1",
      port: 15974,
      strictPort: false
    }
  });
  await server.listen();
  const baseUrl = server.resolvedUrls.local[0];

  browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { height: 800, width: 1280 } });
  page.setDefaultTimeout(15_000);
  await selected.beforeNavigate?.(page, runtime);

  const url = new URL("/", baseUrl);
  if (selected.bundle) {
    url.searchParams.set("bundle", selected.bundle);
  }
  for (const [name, value] of Object.entries(selected.query?.(runtime) ?? {})) {
    url.searchParams.set(name, value);
  }
  await page.goto(url.toString(), { waitUntil: "domcontentloaded" });
  await page.waitForFunction(() => /Ready/.test(document.querySelector("[data-status]")?.textContent ?? ""));
  await page.waitForFunction(() => document.querySelector("[data-canvas]")?.dataset.renderer === "three");
  await page.waitForFunction(
    (minimumObjects) => Number(document.querySelector("[data-canvas]")?.dataset.renderedObjects ?? 0) >= minimumObjects,
    selected.minimumObjects
  );
  await page.waitForFunction(() => {
    const canvas = document.querySelector("[data-canvas]");
    const gl = canvas?.getContext("webgl2") || canvas?.getContext("webgl");
    return Boolean(gl && gl.drawingBufferWidth > 0 && gl.drawingBufferHeight > 0);
  });
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));

  const canvasStats = await page.locator("[data-canvas]").evaluate((canvas) => {
    const gl = canvas.getContext("webgl2") || canvas.getContext("webgl");
    if (!gl) {
      return { hasContext: false };
    }

    const width = gl.drawingBufferWidth;
    const height = gl.drawingBufferHeight;
    const pixels = new Uint8Array(width * height * 4);
    gl.readPixels(0, 0, width, height, gl.RGBA, gl.UNSIGNED_BYTE, pixels);

    const baseline = [pixels[0], pixels[1], pixels[2]];
    let sampled = 0;
    let varied = 0;
    const stepX = Math.max(1, Math.floor(width / 48));
    const stepY = Math.max(1, Math.floor(height / 48));
    for (let y = 0; y < height; y += stepY) {
      for (let x = 0; x < width; x += stepX) {
        const index = (y * width + x) * 4;
        sampled += 1;
        const delta =
          Math.abs(pixels[index] - baseline[0]) +
          Math.abs(pixels[index + 1] - baseline[1]) +
          Math.abs(pixels[index + 2] - baseline[2]);
        if (delta > 8) {
          varied += 1;
        }
      }
    }

    return {
      hasContext: true,
      renderedObjects: Number(canvas.dataset.renderedObjects ?? 0),
      sampled,
      varied
    };
  });

  assert.equal(canvasStats.hasContext, true);
  assert.ok(canvasStats.renderedObjects >= selected.minimumObjects, `expected rendered objects, got ${canvasStats.renderedObjects}`);
  assert.ok(canvasStats.varied > 0, `expected nonblank canvas samples, got ${JSON.stringify(canvasStats)}`);

  await selected.run?.(page, runtime);
  console.log(`${scenario} ok: ${canvasStats.renderedObjects} objects, ${canvasStats.varied}/${canvasStats.sampled} varied samples`);
  await shutdown();
  process.exit(0);
} catch (error) {
  console.error(error);
  await shutdown();
  process.exit(1);
}

async function shutdown() {
  browser?.process?.()?.kill();
  await boundedClose("browser", () => browser?.close());
  await boundedClose("vite server", () => server?.close());
  await boundedClose("scenario runtime", () => runtime?.close?.());
}

async function boundedClose(label, close) {
  try {
    await Promise.race([
      close(),
      new Promise((resolve) => {
        setTimeout(resolve, 3000);
      })
    ]);
  } catch (error) {
    console.warn(`Failed to close ${label}: ${error.message}`);
  }
}

async function startTestWebSocketServer() {
  const sockets = new Set();
  let clientResolve;
  const clientReady = new Promise((resolve) => {
    clientResolve = resolve;
  });
  const wsServer = createNetServer((socket) => {
    let buffer = "";
    socket.on("data", (chunk) => {
      buffer += chunk.toString("utf8");
      if (!buffer.includes("\r\n\r\n")) {
        return;
      }
      const key = buffer.match(/Sec-WebSocket-Key: (.+)\r\n/i)?.[1]?.trim();
      if (!key) {
        socket.destroy();
        return;
      }
      const accept = createHash("sha1")
        .update(`${key}258EAFA5-E914-47DA-95CA-C5AB0DC85B11`)
        .digest("base64");
      socket.write(
        "HTTP/1.1 101 Switching Protocols\r\n" +
          "Upgrade: websocket\r\n" +
          "Connection: Upgrade\r\n" +
          `Sec-WebSocket-Accept: ${accept}\r\n` +
          "\r\n"
      );
      sockets.add(socket);
      clientResolve();
    });
    socket.on("close", () => sockets.delete(socket));
    socket.on("error", () => sockets.delete(socket));
  });

  await new Promise((resolveListen) => {
    wsServer.listen(0, "127.0.0.1", resolveListen);
  });
  const address = wsServer.address();
  return {
    url: `ws://127.0.0.1:${address.port}`,
    send(event) {
      const frame = websocketTextFrame(JSON.stringify(event));
      for (const socket of sockets) {
        socket.write(frame);
      }
    },
    waitForClient() {
      return Promise.race([
        clientReady,
        new Promise((_resolve, reject) => {
          setTimeout(() => reject(new Error("Timed out waiting for preview websocket client")), 5000);
        })
      ]);
    },
    close() {
      for (const socket of sockets) {
        socket.destroy();
      }
      return new Promise((resolveClose) => wsServer.close(resolveClose));
    }
  };
}

function websocketTextFrame(text) {
  const payload = Buffer.from(text, "utf8");
  if (payload.length < 126) {
    return Buffer.concat([Buffer.from([0x81, payload.length]), payload]);
  }
  if (payload.length < 65536) {
    const header = Buffer.alloc(4);
    header[0] = 0x81;
    header[1] = 126;
    header.writeUInt16BE(payload.length, 2);
    return Buffer.concat([header, payload]);
  }
  const header = Buffer.alloc(10);
  header[0] = 0x81;
  header[1] = 127;
  header.writeBigUInt64BE(BigInt(payload.length), 2);
  return Buffer.concat([header, payload]);
}
