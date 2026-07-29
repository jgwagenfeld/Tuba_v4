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

async function assertSelectedEvidenceTab(page, label) {
  const selected = page.locator('[data-evidence-tabs] [role="tab"][aria-selected="true"]');
  const focusable = page.locator('[data-evidence-tabs] [role="tab"][tabindex="0"]');
  assert.equal(await selected.count(), 1);
  assert.equal(await focusable.count(), 1);
  assert.equal(await selected.textContent(), label);
  assert.equal(await focusable.textContent(), label);
}

async function framebufferFingerprint(canvas) {
  return canvas.evaluate((target) => {
    const gl = target.getContext("webgl2") || target.getContext("webgl");
    const pixels = new Uint8Array(gl.drawingBufferWidth * gl.drawingBufferHeight * 4);
    gl.readPixels(0, 0, gl.drawingBufferWidth, gl.drawingBufferHeight, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
    let hash = 2166136261;
    const step = Math.max(4, Math.floor(pixels.length / 4096 / 4) * 4);
    for (let index = 0; index < pixels.length; index += step) hash = Math.imul(hash ^ pixels[index], 16777619);
    return hash >>> 0;
  });
}

async function framebufferSnapshot(canvas) {
  return canvas.evaluate((target) => {
    const gl = target.getContext("webgl2") || target.getContext("webgl");
    const pixels = new Uint8Array(gl.drawingBufferWidth * gl.drawingBufferHeight * 4);
    gl.readPixels(0, 0, gl.drawingBufferWidth, gl.drawingBufferHeight, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
    let hash = 2166136261;
    const samples = [];
    const step = Math.max(4, Math.floor(pixels.length / 4096 / 4) * 4);
    for (let index = 0; index < pixels.length; index += step) {
      hash = Math.imul(hash ^ pixels[index], 16777619);
      samples.push(pixels[index], pixels[index + 1], pixels[index + 2], pixels[index + 3]);
    }
    return { hash: hash >>> 0, samples };
  });
}

const scenarios = {
  smoke: {
    bundle: "/smoke-scene",
    minimumObjects: 3
  },
  "section-camera": {
    bundle: "/smoke-scene",
    minimumObjects: 3,
    async run(page) {
      const canvas = page.locator("[data-canvas]");
      const baseline = await framebufferFingerprint(canvas);
      const baselineSnapshot = await framebufferSnapshot(canvas);
      const positiveZ = page.getByRole("button", { name: "+Z", exact: true });
      await positiveZ.focus();
      await page.keyboard.press("Enter");
      await page.waitForFunction(() => {
        const [x, y, z] = (document.querySelector("[data-canvas]")?.dataset.cameraDirection ?? "").split(",").map(Number);
        return Math.abs(x) < 0.01 && Math.abs(y) < 0.01 && z < -0.99;
      });
      await page.getByRole("button", { name: "Reset 3D view", exact: true }).click();
      await page.waitForFunction(() => {
        const [x, y, z] = (document.querySelector("[data-canvas]")?.dataset.cameraDirection ?? "").split(",").map(Number);
        return x < -0.6 && y > 0.6 && z < -0.4 && z > -0.5;
      });
      await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      const resetViewSnapshot = await framebufferSnapshot(canvas);
      const resetViewMaxDifference = Math.max(
        ...resetViewSnapshot.samples.map((value, index) => Math.abs(value - baselineSnapshot.samples[index]))
      );
      assert.ok(
        resetViewMaxDifference <= 1,
        `reset view after +Z should restore the canonical rendered orientation (max channel difference ${resetViewMaxDifference})`
      );

      await positiveZ.click();
      await page.waitForFunction(() => {
        const [x, y, z] = (document.querySelector("[data-canvas]")?.dataset.cameraDirection ?? "").split(",").map(Number);
        return Math.abs(x) < 0.01 && Math.abs(y) < 0.01 && z < -0.99;
      });
      const viewFingerprint = await framebufferFingerprint(canvas);
      await page.getByRole("button", { name: "Zoom in", exact: true }).click();
      await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      const zoomSnapshot = await framebufferSnapshot(canvas);
      assert.notEqual(zoomSnapshot.hash, viewFingerprint, "zoom must redraw the framebuffer");

      const sectionEnabled = page.getByLabel("Enable section");
      await sectionEnabled.focus();
      await page.keyboard.press("Space");
      await page.waitForFunction(() => Boolean(window.__tubaViewer?.state?.sectionBox));
      assert.equal(await sectionEnabled.evaluate((node) => document.activeElement === node), true, "section toggle must retain focus");
      await page.keyboard.press("Tab");
      const sectionMin = page.getByLabel("Section X min");
      assert.equal(await sectionMin.evaluate((node) => document.activeElement === node), true, "Tab must reach the first section input");
      await sectionMin.fill("-0.05");
      await page.keyboard.press("Tab");
      await page.waitForFunction(() => window.__tubaViewer?.state?.sectionBox?.min?.[0] === -0.05);
      const sectionMax = page.getByLabel("Section X max");
      assert.equal(await sectionMax.evaluate((node) => document.activeElement === node), true, "field editing must retain sequential Tab focus");
      await sectionMax.fill("1.5");
      await sectionMax.press("Enter");
      await page.waitForFunction(() => (window.__tubaViewer?.state?.sectionBox?.max?.[0] ?? 0) === 1.5);
      assert.ok(
        (await page.evaluate(() => window.__tubaViewer?.lastRender?.objectIds ?? [])).includes("object:element:pipe_smoke"),
        "a pipe crossing the section box remains renderable for fragment clipping"
      );
      const sectionSnapshot = await framebufferSnapshot(canvas);
      assert.notEqual(sectionSnapshot.hash, zoomSnapshot.hash, "sectioning must change the framebuffer");

      await page.getByRole("button", { name: "Reset section", exact: true }).click();
      await page.waitForFunction(() => !window.__tubaViewer?.state?.sectionBox);
      await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      const resetSnapshot = await framebufferSnapshot(canvas);
      const maxChannelDifference = Math.max(...resetSnapshot.samples.map((value, index) => Math.abs(value - zoomSnapshot.samples[index])));
      assert.ok(maxChannelDifference <= 1, `section reset framebuffer drifted by ${maxChannelDifference} channel value(s)`);
      console.log(`section-camera fingerprints: reset-view-drift=${resetViewMaxDifference} zoom=${zoomSnapshot.hash} section=${sectionSnapshot.hash} reset=${resetSnapshot.hash}; max channel drift=${maxChannelDifference}`);
      assert.notEqual(baseline, 0);
    }
  },
  "view-gizmo": {
    bundle: "/smoke-scene",
    minimumObjects: 3,
    async run(page) {
      const canvas = page.locator("[data-canvas]");
      const before = await canvas.evaluate((node) => node.dataset.cameraDirection);
      assert.ok(before, "renderer must publish the camera direction");

      // The gizmo occupies a 128px box in the bottom-right corner spanning [-2, 2] world
      // units, so its axis balls sit 32px from the box centre. After the initial fit the
      // camera looks from (1, -1, 0.65), which puts world +Z at 0.909 screen-up.
      const box = await canvas.boundingBox();
      await page.mouse.click(box.x + box.width - 64, box.y + box.height - 64 - 29);

      await page.waitForFunction(
        (previous) => document.querySelector("[data-canvas]")?.dataset.cameraDirection !== previous,
        before
      );
      await page.waitForFunction(() => {
        const [x, y, z] = (document.querySelector("[data-canvas]")?.dataset.cameraDirection ?? "").split(",").map(Number);
        return Math.abs(x) < 0.01 && Math.abs(y) < 0.01 && z < -0.99;
      });

      // Hitting the gizmo must not double as a pick in the scene behind it.
      assert.deepEqual(await page.evaluate(() => window.__tubaViewer?.state?.selectedObjectIds ?? []), []);
    }
  },
  "bundle-picker": {
    bundle: "smoke-scene",
    minimumObjects: 3,
    async run(page) {
      const picker = page.locator("[data-bundle-picker]");
      await picker.waitFor({ state: "visible" });

      // The dropdown lists every public/ example the vite plugin discovered.
      const options = await picker.locator("option").evaluateAll((nodes) => nodes.map((node) => node.value));
      assert.ok(options.includes("smoke-scene"), `picker must list smoke-scene: ${options}`);
      assert.ok(options.includes("code-aster-review"), `picker must list code-aster-review: ${options}`);
      assert.ok(options.length >= 3, `picker must list every example: ${options}`);
      assert.equal(await picker.inputValue(), "smoke-scene");

      const sceneBefore = await page.evaluate(() => window.__tubaViewer?.state?.sceneId);

      // Selecting another example loads it and rewrites the ?bundle= query.
      await picker.selectOption("code-aster-review");
      await page.waitForFunction(
        (previous) => window.__tubaViewer?.state?.sceneId && window.__tubaViewer.state.sceneId !== previous,
        sceneBefore
      );
      assert.match(new URL(page.url()).searchParams.get("bundle") ?? "", /code-aster-review/);
      assert.equal(await picker.inputValue(), "code-aster-review");
    }
  },
  "layer-state": {
    bundle: "/test/fixtures/layer_state_scene",
    // The default "model" task preset hides the results + overlays categories, so only
    // object:cold renders on load; the scenario turns them on before exercising toggles.
    minimumObjects: 1,
    async run(page) {
      const layers = page.locator(".layer-tree");
      await layers.evaluate((details) => {
        details.open = true;
      });
      assert.equal(await layers.evaluate((details) => details.open), true);
      // Reveal the preset-hidden categories via the display-strip category switches.
      // object:cold -> design, object:deformed -> results, object:clash -> annotations
      // (this fixture carries no scene.layers, so it exercises the legacy fallback).
      await page.getByLabel(/^\s*Results\s*$/).check();
      await page.getByLabel(/^\s*Annotations\s*$/).check();
      await page.waitForFunction(() => {
        const ids = window.__tubaViewer?.lastRender?.objectIds ?? [];
        return ids.length === 3 && ids.includes("object:cold") && ids.includes("object:deformed") && ids.includes("object:clash");
      });

      await page.getByLabel(/Visual Centerline/).uncheck();
      await page.waitForFunction(() => {
        const ids = window.__tubaViewer?.lastRender?.objectIds ?? [];
        return ids.length === 2 && ids.includes("object:cold") && ids.includes("object:clash") && !ids.includes("object:deformed");
      });

      await page.getByLabel(/^\s*Annotations\s*$/).uncheck(); // category switch hides the clash marker
      await page.waitForFunction(() => {
        const ids = window.__tubaViewer?.lastRender?.objectIds ?? [];
        return ids.length === 1 && ids[0] === "object:cold";
      });
    }
  },
  "scene-inspection": {
    bundle: "/test/fixtures/inspection_scene",
    minimumObjects: 1,
    async run(page) {
      await page.getByLabel(/^\s*Annotations\s*$/).check();
      await page.getByLabel(/^\s*Analysis mesh\s*$/).check();
      await page.waitForFunction(() => (window.__tubaViewer?.lastRender?.objectIds ?? []).length === 3);
      await page.locator("[data-model-tools-home] details").filter({ hasText: "Objects" }).locator("summary").click();

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
      await reviewTask.focus();
      assert.deepEqual(await reviewTask.evaluate((button) => {
        const style = getComputedStyle(button);
        return { outlineColor: style.outlineColor, outlineWidth: style.outlineWidth };
      }), { outlineColor: "rgb(94, 216, 229)", outlineWidth: "3px" });
      assert.equal(await page.locator("[data-viewer-workspace]").isVisible(), true);
      assert.equal(await page.locator("[data-cockpit-status]").isVisible(), true);
      assert.equal(await page.locator("[data-inspector]").isHidden(), true);
      assert.equal(
        await page.getByRole("tab", { name: "Governing Results", exact: true }).getAttribute("aria-selected"),
        "true"
      );
      await assertSelectedEvidenceTab(page, "Governing Results");
      await page.getByRole("heading", { level: 1, name: "Governing Results", exact: true }).waitFor();
      assert.equal(await page.locator("[data-report-link]").isVisible(), true);
      const headerLayout = await page.locator("[data-app-header]").evaluate((header) => ({
        columns: getComputedStyle(header).gridTemplateColumns.split(" ").length,
        centers: [...header.children].map((child) => {
          const rect = child.getBoundingClientRect();
          return rect.top + rect.height / 2;
        })
      }));
      assert.equal(headerLayout.columns, 4);
      assert.ok(
        headerLayout.centers.every((center) => Math.abs(center - headerLayout.centers[0]) <= 1),
        JSON.stringify(headerLayout)
      );

      await page.getByRole("tab", { name: "Reports", exact: true }).click();
      await assertSelectedEvidenceTab(page, "Reports");
      await page.getByRole("heading", { level: 1, name: "Reports", exact: true }).waitFor();
      assert.match(await page.locator("[data-evidence-report-link]").getAttribute("href"), /code_aster_results\/index\.html$/);
      await page.getByRole("tab", { name: "Governing Results", exact: true }).click();
      await rememberCanvas(page);

      await page.getByRole("button", { name: "Model", exact: true }).click();
      await assertSelectedEvidenceTab(page, "Governing Results");
      await page.getByRole("heading", { level: 1, name: "Governing Results", exact: true }).waitFor();
      await assertSameCanvas(page);
      await page.getByRole("button", { name: "Results", exact: true }).click();
      await assertSelectedEvidenceTab(page, "Governing Results");
      await assertSameCanvas(page);

      assert.equal(await page.getByRole("combobox", { name: /^Load case/ }).inputValue(), "Hot");
      assert.equal(await page.getByRole("combobox", { name: /^Result state/ }).inputValue(), "result_state:Hot");
      assert.match(await page.locator("[data-result-legend]").textContent(), /max_von_mises.*Pa/);
      assert.match(await page.locator("[data-hotspot-list]").textContent(), /Hot pipe/);
      await page.getByLabel(/Stress threshold/i).evaluate((input) => {
        input.value = "50000000";
        input.dispatchEvent(new Event("change", { bubbles: true }));
      });
      const thresholdHotspots = await page.locator("[data-hotspot-list]").textContent();
      assert.match(thresholdHotspots, /Hot pipe/);
      assert.doesNotMatch(thresholdHotspots, /Warm pipe/);
      await page.getByLabel(/Displacement vector scale/i).evaluate((input) => {
        input.value = "10";
        input.dispatchEvent(new Event("input", { bubbles: true }));
      });
      await page.waitForFunction(() => window.__tubaViewer?.state?.resultVectorScales?.displacement === 10);
      await page.locator("[data-display-strip] details.layer-tree summary").click();
      const visualCenterline = page.getByLabel(/^\s*Visual Centerline/);
      const physicalCenterline = page.getByLabel(/^\s*Physical Centerline/);
      await visualCenterline.uncheck();
      await page.waitForFunction(() => {
        const ids = window.__tubaViewer?.lastRender?.objectIds ?? [];
        return ids.includes("object:deformed_physical") && !ids.includes("object:deformed_visual");
      });
      assert.equal(await physicalCenterline.isChecked(), true);
      await visualCenterline.check();
      await page.waitForFunction(() => {
        const ids = window.__tubaViewer?.lastRender?.objectIds ?? [];
        return ids.includes("object:deformed_physical") && ids.includes("object:deformed_visual");
      });
      await physicalCenterline.uncheck();
      await page.waitForFunction(() => {
        const ids = window.__tubaViewer?.lastRender?.objectIds ?? [];
        return !ids.includes("object:deformed_physical") && ids.includes("object:deformed_visual");
      });
      assert.equal(await visualCenterline.isChecked(), true);
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
      const compactExpand = page.locator("[data-evidence-expand]");
      assert.equal(await compactExpand.getAttribute("aria-expanded"), "false");
      await compactExpand.click();
      assert.equal(await compactExpand.getAttribute("aria-expanded"), "true");
      await page.getByRole("tab", { name: "Warnings", exact: true }).click();
      await page.getByRole("heading", { level: 1, name: "Warnings", exact: true }).waitFor();
      await assertSelectedEvidenceTab(page, "Warnings");
      await assertSameCanvas(page);
      await page.getByRole("button", { name: "Results", exact: true }).click();
      assert.equal(await page.getByRole("button", { name: "Results", exact: true }).getAttribute("aria-current"), "page");
      await assertSelectedEvidenceTab(page, "Warnings");
      await assertSameCanvas(page);
      await compactExpand.click();
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      assert.equal(await page.evaluate(() => window.innerWidth), 1440);
      await assertSameCanvas(page);
      await page.setViewportSize({ width: 1024, height: 768 });
      const railLayout = await page.locator("[data-workflow-tabs]").evaluate((nav) => {
        const buttons = [...nav.querySelectorAll("button")].map((button) => {
          const rect = button.getBoundingClientRect();
          return { text: button.textContent, left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom };
        });
        const overlaps = [];
        for (let left = 0; left < buttons.length; left += 1) {
          for (let right = left + 1; right < buttons.length; right += 1) {
            const a = buttons[left];
            const b = buttons[right];
            if (Math.min(a.right, b.right) - Math.max(a.left, b.left) > 1 && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 1) {
              overlaps.push([a.text, b.text]);
            }
          }
        }
        return { clientWidth: nav.clientWidth, scrollWidth: nav.scrollWidth, overlaps };
      });
      assert.deepEqual(railLayout.overlaps, [], JSON.stringify(railLayout));
      assert.ok(railLayout.scrollWidth <= railLayout.clientWidth + 1, JSON.stringify(railLayout));
      const expandEvidence = page.locator("[data-evidence-expand]");
      assert.equal(await expandEvidence.getAttribute("aria-expanded"), "false");
      const collapsedDock = await page.locator("[data-evidence-dock]").evaluate((dock) => ({
        height: dock.getBoundingClientRect().height,
        position: getComputedStyle(dock).position
      }));
      await expandEvidence.click();
      assert.equal(await expandEvidence.getAttribute("aria-expanded"), "true");
      const expandedDock = await page.locator("[data-evidence-dock]").evaluate((dock) => ({
        height: dock.getBoundingClientRect().height,
        position: getComputedStyle(dock).position
      }));
      assert.equal(expandedDock.position, "absolute");
      assert.ok(expandedDock.height > collapsedDock.height + 100, JSON.stringify({ collapsedDock, expandedDock }));
      await page.getByRole("tab", { name: "Governing Results", exact: true }).click();
      await assertSelectedEvidenceTab(page, "Governing Results");
      const expandedCanvasHeight = await page.locator("[data-canvas]").evaluate((canvas) => canvas.getBoundingClientRect().height);
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
      assert.ok(
        Math.abs(await page.locator("[data-canvas]").evaluate((canvas) => canvas.getBoundingClientRect().height) - expandedCanvasHeight) <= 1,
        "opening the inspector must not make the expanded evidence overlay shrink the canvas"
      );
      await assertInspectorIdentity(page, "object:pipe:hot", "element:pipe_hot");
      assert.equal(
        await page.locator('[data-workflow-panel] tr[data-entity-ref="element:pipe_hot"][data-selected="true"]').first().isVisible(),
        true
      );
      await expandEvidence.click();
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
      await page.setViewportSize({ width: 800, height: 900 });
      await expandEvidence.click();
      await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      const compactExpandedLayout = await page.evaluate(() => {
        const workspace = document.querySelector("[data-viewer-workspace]");
        const workspaceRect = workspace.getBoundingClientRect();
        const canvasRect = document.querySelector("[data-canvas]").getBoundingClientRect();
        return {
          columns: getComputedStyle(workspace).gridTemplateColumns.split(" ").length,
          workspace: { left: workspaceRect.left, right: workspaceRect.right },
          canvas: { left: canvasRect.left, right: canvasRect.right, width: canvasRect.width }
        };
      });
      assert.equal(compactExpandedLayout.columns, 1, JSON.stringify(compactExpandedLayout));
      assert.ok(
        Math.abs(compactExpandedLayout.canvas.left - compactExpandedLayout.workspace.left) <= 1 &&
          Math.abs(compactExpandedLayout.canvas.right - compactExpandedLayout.workspace.right) <= 1,
        JSON.stringify(compactExpandedLayout)
      );
      assert.ok(compactExpandedLayout.canvas.width >= 480, JSON.stringify(compactExpandedLayout));
      await expandEvidence.click();
      await page.setViewportSize({ width: 1440, height: 900 });

      await page.getByLabel(/Stress threshold/i).evaluate((input) => {
        input.value = "0";
        input.dispatchEvent(new Event("change", { bubbles: true }));
      });
      const hotspotList = page.locator("[data-hotspot-list]");
      await hotspotList.getByRole("button", { name: /Warm pipe/ }).click();
      await page.waitForFunction(() => window.__tubaViewer?.state?.selectedObjectIds?.[0] === "object:pipe:warm");
      await hotspotList.getByRole("button", { name: /Hot pipe/ }).click();
      await page.waitForFunction(() => {
        const selected = window.__tubaViewer?.state?.selectedObjectIds ?? [];
        return selected.length === 1 && selected[0] === "object:pipe:hot";
      });
      assert.equal(await page.locator("[data-inspector]").isVisible(), true);
      const hotspotProperties = await page.locator("[data-properties]").textContent();
      assert.match(hotspotProperties, /element:pipe_hot/);
      assert.match(hotspotProperties, /Result Values/);
      assert.match(hotspotProperties, /57000000/);
      assert.match(hotspotProperties, /Pa/);

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
          layers: Object.keys(state.layers).length,
          resultFields: state.resultFields.length,
          hasParserDiagnostics: state.overlays.some((overlay) => overlay.data?.result_type === "parser_diagnostics"),
          hasFieldContext: state.overlays.some((overlay) => overlay.kind === "field_context"),
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
      assert.equal(loaded.objects, 217);
      assert.equal(loaded.geometryPayloads, 214);
      assert.equal(loaded.overlays, 10);
      assert.equal(loaded.layers, 39);
      assert.equal(loaded.resultFields, 4);
      assert.equal(loaded.hasParserDiagnostics, true);
      assert.equal(loaded.hasFieldContext, true);
      assert.deepEqual(loaded.reviewLoadDiagnostics, []);
      assert.deepEqual(loaded.missingNodeGeometry, []);
      assert.deepEqual(loaded.solverParserDiagnostics, []);
      assert.equal(loaded.parserDiagnosticOverlays.length, 1);
      assert.equal(loaded.parserDiagnosticOverlays[0].data.result_state_id, "result_state:Operating");
      assert.deepEqual(loaded.renderDiagnostics, []);

      // The summary preset hides analysis mesh on load, dropping the scene to 37 renderable
      // objects — below MAX_HOVER_PICK_OBJECTS. Re-enable it so the hover-skip path is exercised.
      await page.getByLabel("Analysis mesh", { exact: true }).check();
      await page.waitForFunction(() => (window.__tubaViewer?.lastRender?.renderableCount ?? 0) > 50);

      const hoverBurst = await page.locator("[data-canvas]").evaluate((canvas) => {
        const rect = canvas.getBoundingClientRect();
        const nativeRequestAnimationFrame = window.requestAnimationFrame;
        let scheduledAnimationFrames = 0;
        window.requestAnimationFrame = (...args) => {
          scheduledAnimationFrames += 1;
          return nativeRequestAnimationFrame.apply(window, args);
        };
        const started = performance.now();
        try {
          for (let index = 0; index < 30; index += 1) {
            canvas.dispatchEvent(new MouseEvent("mousemove", {
              bubbles: true,
              clientX: rect.left + 10 + ((rect.width - 20) * index) / 29,
              clientY: rect.top + rect.height / 2
            }));
          }
          return { elapsedMs: performance.now() - started, scheduledAnimationFrames };
        } finally {
          window.requestAnimationFrame = nativeRequestAnimationFrame;
        }
      });
      assert.ok(hoverBurst.elapsedMs < 50, `dense-scene hover dispatch took ${hoverBurst.elapsedMs.toFixed(1)}ms`);
      assert.equal(hoverBurst.scheduledAnimationFrames, 0, "dense-scene hover must skip picking frames");

      const canvas = page.locator("[data-canvas]");
      const fingerprint = () => framebufferFingerprint(canvas);
      await canvas.evaluate((target) => {
        window.__tubaBlockCanvasApp = (event) => event.stopImmediatePropagation();
        target.addEventListener("mousemove", window.__tubaBlockCanvasApp, true);
        target.addEventListener("click", window.__tubaBlockCanvasApp, true);
      });
      const beforeOrbit = await fingerprint();
      const canvasBox = await canvas.boundingBox();
      const orbitStarted = Date.now();
      await page.mouse.move(canvasBox.x + canvasBox.width * 0.5, canvasBox.y + canvasBox.height * 0.5);
      await page.mouse.down();
      await page.mouse.move(canvasBox.x + canvasBox.width * 0.75, canvasBox.y + canvasBox.height * 0.65, { steps: 12 });
      await page.mouse.up();
      const orbitElapsedMs = Date.now() - orbitStarted;
      await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      const afterOrbit = await fingerprint();
      await canvas.evaluate((target) => {
        target.removeEventListener("mousemove", window.__tubaBlockCanvasApp, true);
        target.removeEventListener("click", window.__tubaBlockCanvasApp, true);
        delete window.__tubaBlockCanvasApp;
      });
      assert.notEqual(afterOrbit, beforeOrbit, "OrbitControls must redraw without the hover handler");
      assert.ok(orbitElapsedMs < 1500, `OrbitControls redraws must be frame-coalesced, took ${orbitElapsedMs}ms`);

      const selectionBeforeRealOrbit = await page.evaluate(() => window.__tubaViewer?.state?.selectedObjectIds ?? []);
      const realOrbitStarted = Date.now();
      await page.mouse.move(canvasBox.x + canvasBox.width * 0.5, canvasBox.y + canvasBox.height * 0.5);
      await page.mouse.down();
      await page.mouse.move(canvasBox.x + canvasBox.width * 0.75, canvasBox.y + canvasBox.height * 0.65, { steps: 12 });
      await page.mouse.up();
      const realOrbitElapsedMs = Date.now() - realOrbitStarted;
      const selectionAfterRealOrbit = await page.evaluate(() => window.__tubaViewer?.state?.selectedObjectIds ?? []);
      assert.ok(realOrbitElapsedMs < 1500, `a real orbit gesture must not trigger click picking, took ${realOrbitElapsedMs}ms`);
      assert.deepEqual(selectionAfterRealOrbit, selectionBeforeRealOrbit, "an orbit gesture must not change selection");

      await page.getByRole("button", { name: "Results", exact: true }).click();
      assert.equal(await page.getByRole("button", { name: "Results", exact: true }).getAttribute("aria-current"), "page");
      await assertSelectedEvidenceTab(page, "Governing Results");
      await assertSameCanvas(page);
      assert.equal(await page.getByRole("combobox", { name: /^Load case/ }).inputValue(), "Operating");
      assert.equal(
        await page.getByRole("combobox", { name: "Field", exact: true }).inputValue(),
        "field:solver_result:stress:result_state:Operating"
      );
      assert.equal(await page.getByRole("combobox", { name: /^Result state/ }).count(), 0);
      assert.equal(await page.getByRole("combobox", { name: "Component", exact: true }).count(), 0);

      await page.getByRole("combobox", { name: "Field", exact: true }).selectOption(
        "field:solver_result:displacement:result_state:Operating"
      );
      await page.getByRole("combobox", { name: "Component", exact: true }).selectOption("DZ");
      await page.waitForFunction(() => {
        const review = window.__tubaViewer?.resultReview;
        return review?.legend?.component === "DZ" && review.legend?.field === "displacement_magnitude";
      });
      assert.match(await page.locator("[data-result-legend]").textContent(), /displacement_magnitude DZ:/);

      await page.getByRole("combobox", { name: "Field", exact: true }).selectOption(
        "field:solver_result:tuyau_subpoints:result_state:Operating"
      );
      await page.waitForFunction(() => window.__tubaViewer?.resultReview?.legend?.field === "FE VMIS (not code stress) (subpoint)");
      assert.match(await page.locator("[data-compliance-notice]").textContent(), /FE stress - not ASME code stress/);

      const deformedState = page.getByRole("combobox", { name: "Deformed state", exact: true });
      await deformedState.selectOption("geometry_state:Operating:physical");
      await page.waitForFunction(() => window.__tubaViewer?.state?.activeGeometryStateId === "geometry_state:Operating:physical");
      const physicalObjectIds = await page.evaluate(() => window.__tubaViewer?.lastRender?.objectIds ?? []);
      assert.ok(physicalObjectIds.includes("object:deformed_centerline:geometry_state:Operating:physical:pipe_str_0"));
      assert.ok(!physicalObjectIds.includes("object:deformed_centerline:geometry_state:Operating:visual_x40:pipe_str_0"));

      await deformedState.selectOption("geometry_state:Operating:visual_x40");
      await page.waitForFunction(() => window.__tubaViewer?.state?.activeGeometryStateId === "geometry_state:Operating:visual_x40");
      const visualObjectIds = await page.evaluate(() => window.__tubaViewer?.lastRender?.objectIds ?? []);
      assert.ok(visualObjectIds.includes("object:deformed_centerline:geometry_state:Operating:visual_x40:pipe_str_0"));
      assert.ok(!visualObjectIds.includes("object:deformed_centerline:geometry_state:Operating:physical:pipe_str_0"));
      assert.ok(visualObjectIds.includes("object:element:pipe_str_0"));

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
      const modelTask = page.getByRole("button", { name: "Model", exact: true });
      await modelTask.waitFor();
      assert.equal(await modelTask.getAttribute("aria-current"), "page");
      assert.equal(await page.getByRole("button", { name: "Issues", exact: true }).count(), 1);
      assert.equal(await page.getByRole("button", { name: "Review", exact: true }).count(), 0);
      assert.equal(await page.getByRole("button", { name: "Display", exact: true }).count(), 0);
      assert.equal(await page.getByRole("tab", { name: "Warnings", exact: true }).count(), 1);
      assert.equal(await page.getByRole("tab", { name: "Governing Results", exact: true }).count(), 0);
      assert.equal(await page.getByRole("tab", { name: "Reports", exact: true }).count(), 0);
      assert.equal(await page.locator("[data-report-link]").isVisible(), false);
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
        activeTab: "model",
        legacyReview: true,
        review: null,
        reviewDiagnostics: []
      });
    }
  },
  "partial-compliance-neutrality": {
    bundle: "/test/fixtures/code_aster_results",
    minimumObjects: 7,
    async beforeNavigate(page) {
      await page.route("**/test/fixtures/code_aster_results/review.json", async (route) => {
        const response = await route.fetch();
        const review = await response.json();
        review.analysis_status = "compliance_complete";
        review.tables.code_compliance = {
          id: "code_compliance",
          title: "Code compliance",
          source: "compliance_report",
          columns: [
            { id: "load_case", label: "Load case" },
            { id: "entity_ref", label: "Entity reference" },
            { id: "sustained_ratio", label: "Sustained ratio" },
            { id: "sustained_pass", label: "Sustained pass" },
            { id: "expansion_ratio", label: "Expansion ratio" },
            { id: "expansion_pass", label: "Expansion pass" }
          ],
          rows: [{
            load_case: "Partial Operating",
            entity_ref: "element:pipe_partial",
            sustained_ratio: 0.74,
            expansion_ratio: 0.86
          }]
        };
        await route.fulfill({ response, json: review });
      });
    },
    async run(page) {
      const status = await page.locator("[data-cockpit-status]").textContent();
      assert.match(status, /Compliance\s*Not available/i);
      assert.match(status, /Governing case\s*Not available/i);
      assert.match(status, /Governing ratio\s*Not available/i);
      assert.doesNotMatch(status, /Partial Operating|pipe_partial|0\.86/);
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
  "clash-review": {
    bundle: "/test/fixtures/code_aster_results",
    minimumObjects: 7,
    async run(page) {
      await page.getByRole("button", { name: "Issues", exact: true }).click();
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
      await page.waitForFunction(() => {
        const ids = window.__tubaViewer?.lastRender?.objectIds ?? [];
        return ids.includes("object:pipe:hot") && ids.includes("object:clash") && !ids.includes("object:reaction_vector");
      });

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
      assert.equal(await page.evaluate(() => window.__tubaViewer?.state?.activeTab), "model");
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
      assert.match(layerText, /Agent Proposal/);
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
      await page.locator("[data-model-tools-home] details").filter({ hasText: "Objects" }).locator("summary").click();
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
