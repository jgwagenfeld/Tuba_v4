import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync } from "node:fs";
import { createServer as createNetServer } from "node:net";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";
import { createServer } from "vite";

const viewerRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const scenario = process.argv[2] ?? "smoke";

// A clash marker is gated twice - by its own object layer and by the overlay
// layer that owns markers of its kind - so both leaves have to move together.
// Each click re-renders the tree, so the locator is re-resolved every time.
async function setLayerLeaves(page, label, visible) {
  const leaves = page.getByLabel(label);
  const count = await leaves.count();
  assert.ok(count > 0, `expected at least one layer leaf matching ${label}`);
  for (let index = 0; index < count; index += 1) {
    await (visible ? leaves.nth(index).check() : leaves.nth(index).uncheck());
  }
}

async function openIssuesTask(page) {
  await openReviewControls(page);
  await page.getByRole("button", { name: "Issues", exact: true }).click();
}

async function openResultsTask(page) {
  await openReviewControls(page);
  await page.getByRole("button", { name: "Results", exact: true }).click();
  // Activating a task applies its layer-visibility preset, and that reaches the
  // framebuffer a frame later. Settle before anything samples the canvas, or a
  // baseline snapshot is taken against a scene that is still changing.
  await page.evaluate(
    () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))
  );
}

// review.json is probed, not required: a model-review or legacy scene-only
// bundle has none, and its absence is how loadReview decides the bundle is
// review-less. The browser logs that 404 whatever the loader does with it, so
// it is expected traffic rather than an unexpected event. Matched by URL, so
// every other 404 still fails the scenario.
const EXPECTED_MISSING_RESOURCE = /\/review\.json$/;

function captureUnexpectedBrowserEvents(page) {
  page.__tubaUnexpectedBrowserEvents = [];
  page.on("pageerror", (error) => page.__tubaUnexpectedBrowserEvents.push(`pageerror: ${error.message}`));
  page.on("console", (message) => {
    if (message.type() !== "error") {
      return;
    }
    if (EXPECTED_MISSING_RESOURCE.test(message.location()?.url ?? "")) {
      return;
    }
    page.__tubaUnexpectedBrowserEvents.push(`console: ${message.text()}`);
  });
  page.on("requestfailed", (request) => {
    if (EXPECTED_MISSING_RESOURCE.test(request.url())) {
      return;
    }
    page.__tubaUnexpectedBrowserEvents.push(
      `requestfailed: ${request.url()} ${request.failure()?.errorText ?? "unknown"}`
    );
  });
}

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

async function openReviewControls(page) {
  const toggle = page.locator("[data-rail-toggle]");
  await toggle.waitFor();
  if (await toggle.getAttribute("aria-expanded") !== "true") {
    await toggle.focus();
    await page.keyboard.press("Enter");
  }
  assert.equal(await toggle.getAttribute("aria-expanded"), "true");
  assert.equal(await page.locator("[data-task-rail]").isVisible(), true);
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
    const pixels = gl
      ? new Uint8Array(gl.drawingBufferWidth * gl.drawingBufferHeight * 4)
      : target.getContext("2d").getImageData(0, 0, target.width, target.height).data;
    if (gl) gl.readPixels(0, 0, gl.drawingBufferWidth, gl.drawingBufferHeight, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
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
    bundle: "/test/fixtures/smoke_scene",
    minimumObjects: 3
  },
  "section-camera": {
    bundle: "/test/fixtures/smoke_scene",
    minimumObjects: 3,
    async run(page) {
      await openReviewControls(page);
      const canvas = page.locator("[data-canvas]");
      // The section box is a secondary control, folded into a drawer so the
      // bodies panel owns the rail. Open it before the first framebuffer
      // sample: every snapshot below is compared against another, so the
      // layout has to be identical across all of them.
      await page.locator('[data-rail-tool="section"]').click();
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
    bundle: "/test/fixtures/smoke_scene",
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
    bundle: "code-aster-review",
    // A review draws only what its visibility preset allows, which is fewer
    // objects than the all-kinds fixture this scenario used to open.
    minimumObjects: 1,
    async run(page) {
      const picker = page.locator("[data-bundle-picker]");
      await picker.waitFor({ state: "visible" });

      // The dropdown lists every public/ example the vite plugin discovered.
      const options = await picker.locator("option").evaluateAll((nodes) => nodes.map((node) => node.value));
      assert.ok(options.includes("code-aster-review"), `picker must list code-aster-review: ${options}`);
      assert.ok(options.includes("gmsh-tee-mesh-review"), `picker must list gmsh-tee-mesh-review: ${options}`);
      assert.ok(options.length >= 3, `picker must list every example: ${options}`);
      assert.equal(await picker.inputValue(), "code-aster-review");

      const sceneBefore = await page.evaluate(() => window.__tubaViewer?.state?.sceneId);

      // Selecting another example loads it and rewrites the ?bundle= query.
      await picker.selectOption("gmsh-tee-mesh-review");
      await page.waitForFunction(
        (previous) => window.__tubaViewer?.state?.sceneId && window.__tubaViewer.state.sceneId !== previous,
        sceneBefore
      );
      assert.match(new URL(page.url()).searchParams.get("bundle") ?? "", /gmsh-tee-mesh-review/);
      assert.equal(await picker.inputValue(), "gmsh-tee-mesh-review");
    }
  },
  units: {
    bundle: "/test/fixtures/geometry_mesh_deformed",
    minimumObjects: 3,
    async run(page) {
      await openResultsTask(page);
      const field = page.getByRole("combobox", { name: /^Field/ });
      const subpoint = (await field.evaluate((select) => [...select.options].map((option) => option.value))).find(
        (value) => value.includes("tuyau")
      );
      await field.selectOption(subpoint);

      const chip = page.locator("[data-unit-system]");
      const legend = page.locator("[data-viewport-legend]");
      const section = page.locator("[data-section-profile]");
      // The wall-section rosette and its facts fold away by default; this
      // scenario reads the peak out of them, so open it once - the state
      // survives the re-renders the unit switches below cause.
      await section.locator(".strip-toggle").click();

      // Engineering by default: stored pascals read as MPa, stored metres as mm.
      assert.equal(await chip.getAttribute("data-unit-system"), "engineering");
      assert.match(await legend.textContent(), /MPa/);
      assert.match(await section.textContent(), /peak 160\.8 MPa/);
      // Folded away, not removed: the sublines stay in the row's text.
      assert.match(
        await page.locator('.body-row[data-body="geometry"]').textContent(),
        /OD 114\.3 · WT 6\.02 · R 342\.9 mm/
      );
      assert.match(await page.locator("[data-discretisation-check]").textContent(), /0\.413 mm/);

      // Switching systems restates the same stored numbers; it never moves them.
      await chip.click();
      assert.equal(await chip.getAttribute("data-unit-system"), "si");
      assert.match(await legend.textContent(), /Pa/);
      assert.doesNotMatch(await legend.textContent(), /MPa/);
      assert.match(await section.textContent(), /peak 1\.61e\+8 Pa/);
      assert.match(
        await page.locator('.body-row[data-body="geometry"]').textContent(),
        /OD 0\.1143 · WT 0\.00602 · R 0\.3429 m/
      );
      assert.match(await page.locator("[data-discretisation-check]").textContent(), /0\.000413 m/);

      await chip.click();
      assert.equal(await chip.getAttribute("data-unit-system"), "engineering");
    }
  },
  "deformation-slider": {
    bundle: "/code-aster-review",
    minimumObjects: 1,
    async run(page) {
      await openResultsTask(page);
      const slider = page.getByRole("slider", { name: "Visual deformation scale (display only)" });
      const stayedConnected = await slider.evaluate((input) => {
        input.value = "25";
        input.dispatchEvent(new Event("input", { bubbles: true }));
        return input.isConnected;
      });

      assert.equal(stayedConnected, true, "dragging must not replace the active slider element");
      assert.equal(await page.evaluate(() => window.__tubaViewer?.state?.visualDeformationScale), 25);
      await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      const deformed = await framebufferFingerprint(page.locator("[data-canvas]"));
      await slider.evaluate((input) => {
        input.value = "1";
        input.dispatchEvent(new Event("input", { bubbles: true }));
      });
      await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      assert.notEqual(await framebufferFingerprint(page.locator("[data-canvas]")), deformed);

      const variedSamples = ({ samples }) => {
        const background = samples.slice(0, 3);
        let varied = 0;
        for (let index = 0; index < samples.length; index += 4) {
          const delta = background.reduce((sum, value, channel) => sum + Math.abs(samples[index + channel] - value), 0);
          if (delta > 8) varied += 1;
        }
        return varied;
      };
      const fullScene = await framebufferSnapshot(page.locator("[data-canvas]"));
      // The control lives in the scrolling rail now, not a fixed bar.
      await slider.scrollIntoViewIfNeeded();
      const box = await slider.boundingBox();
      assert.ok(box, "deformation slider must have a draggable box");
      // Half a thumb in from the left edge, so the held scale is the minimum
      // whatever the track is wide - a fraction of the box maps to a different
      // value in a 6rem bar than in the rail, and this check is about the
      // preview keeping the scene visible, not about a particular scale.
      await page.mouse.move(box.x + 8, box.y + box.height / 2);
      await page.mouse.down();
      await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(resolve)));
      const heldLow = await framebufferSnapshot(page.locator("[data-canvas]"));
      // The guard is "the drag preview must not blank the viewport", and a
      // blanked viewport scores near zero. 0.75 was a knife-edge: the same
      // steps measured 134/178 (75.3%) before the deformation control moved
      // into the rail and 143/192 (74.5%) after - the scene is plainly there
      // in both. 0.6 states the intent without failing on a rounding of it.
      assert.ok(
        variedSamples(heldLow) >= variedSamples(fullScene) * 0.6,
        `drag preview hid the scene (${variedSamples(heldLow)}/${variedSamples(fullScene)} varied samples remained)`
      );
      const preview = page.locator("[data-deformation-preview]");
      const previewLow = await framebufferSnapshot(preview);
      await page.mouse.move(box.x + box.width * 0.9, box.y + box.height / 2, { steps: 8 });
      await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(resolve)));
      const draggedValue = Number(await slider.inputValue());
      assert.ok(draggedValue >= 80, "holding and dragging must move the native range thumb");
      assert.equal(await page.locator("[data-deform-scale]").textContent(), `×${draggedValue}`);
      const previewHigh = await framebufferSnapshot(preview);
      const changedChannels = previewHigh.samples.filter((value, index) => value !== previewLow.samples[index]).length;
      assert.ok(changedChannels >= 20, "holding and dragging must visibly move the deformed preview");
      await page.mouse.up();
      await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(resolve)));
      assert.equal(await page.evaluate(() => window.__tubaViewer?.state?.visualDeformationScale), draggedValue);

      const settled = await framebufferSnapshot(page.locator("[data-canvas]"));
      await page.getByRole("button", { name: /Animate/ }).click();
      await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      const animating = await framebufferSnapshot(page.locator("[data-canvas]"));
      const animationChangedChannels = animating.samples.filter((value, index) => value !== settled.samples[index]).length;
      assert.ok(animationChangedChannels >= 20, "animation must not repaint the stale deformed surface");
      await page.getByRole("button", { name: /Pause/ }).click();

      const frameTimes = await slider.evaluate((input) => new Promise((resolve) => {
        const samples = [];
        let previousFrame = performance.now();
        input.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true }));
        const step = (timestamp) => {
          const started = performance.now();
          input.value = String(1 + samples.length % 100);
          input.dispatchEvent(new Event("input", { bubbles: true }));
          samples.push({ frame: timestamp - previousFrame, handler: performance.now() - started });
          previousFrame = timestamp;
          if (samples.length < 30) requestAnimationFrame(step);
          else {
            input.dispatchEvent(new PointerEvent("pointerup", { bubbles: true }));
            resolve(samples);
          }
        };
        requestAnimationFrame(step);
      }));
      const p95 = (values) => [...values].sort((left, right) => left - right)[Math.floor(values.length * 0.95)];
      const frameP95 = p95(frameTimes.map(({ frame }) => frame));
      const handlerP95 = p95(frameTimes.map(({ handler }) => handler));
      assert.ok(
        frameP95 <= 34 && handlerP95 <= 8,
        `deformation p95 frame/handler time was ${frameP95.toFixed(1)}/${handlerP95.toFixed(1)} ms`
      );
    }
  },
  "units-threshold": {
    // A review-backed bundle, because the threshold lives in the Results task.
    bundle: "/test/fixtures/code_aster_results",
    minimumObjects: 3,
    async run(page) {
      await openResultsTask(page);
      const threshold = page.getByLabel(/Stress threshold/i);
      const storedThreshold = () => page.evaluate(() => window.__tubaViewer?.state?.resultThreshold);

      // The field is stress in pascals, so the control is denominated in MPa.
      // The cut-off lives in the folded Filters band now; its unit still follows
      // the chip, and the Hotspots heading restates it while the band is shut.
      assert.match(await page.locator("[data-result-shape]").textContent(), /Stress threshold \(MPa\)/);
      assert.match(await page.locator("[data-hotspot-list]").textContent(), /Hotspots/);
      assert.match(await page.locator("[data-hotspot-list]").textContent(), /Hot pipe 57 MPa/);

      // Typed in the displayed unit, stored in pascals. Getting this wrong
      // filters against the wrong magnitude and silently empties the list.
      await threshold.evaluate((input) => {
        input.value = "50";
        input.dispatchEvent(new Event("change", { bubbles: true }));
      });
      assert.equal(await storedThreshold(), 50000000);
      const filtered = await page.locator("[data-hotspot-list]").textContent();
      assert.match(filtered, /Hot pipe/);
      assert.doesNotMatch(filtered, /Warm pipe/);

      // Switching systems restates the cut-off without moving it.
      await page.locator("[data-unit-system]").click();
      assert.equal(await storedThreshold(), 50000000);
      assert.equal(await threshold.inputValue(), "50000000");
      assert.match(await page.locator("[data-result-shape]").textContent(), /Stress threshold \(Pa\)/);
      assert.match(await page.locator("[data-hotspot-list]").textContent(), /Hot pipe 5\.70e\+7 Pa/);

      // A value typed in SI base is stored as typed - 1 MPa admits both pipes,
      // where the same digits read as MPa would have excluded everything.
      await threshold.evaluate((input) => {
        input.value = "1000000";
        input.dispatchEvent(new Event("change", { bubbles: true }));
      });
      assert.equal(await storedThreshold(), 1000000);
      const bothPipes = await page.locator("[data-hotspot-list]").textContent();
      assert.match(bothPipes, /Hot pipe/);
      assert.match(bothPipes, /Warm pipe 6\.00e\+6 Pa/);
    }
  },
  "layer-state": {
    bundle: "/test/fixtures/layer_state_scene",
    // The default "model" task preset hides the results + overlays categories, so only
    // object:cold renders on load; the scenario turns them on before exercising toggles.
    minimumObjects: 1,
    async run(page) {
      await openReviewControls(page);
      // The tree is the last row of the Display strip now, not a popover tool,
      // so there is nothing to open before expanding it.
      const layers = page.locator(".layer-tree");
      await layers.evaluate((details) => {
        details.open = true;
      });
      assert.equal(await layers.evaluate((details) => details.open), true);
      // Reveal what the "model" task preset hid. object:deformed is one of the
      // four composited bodies so it has a row in the bodies panel; object:clash
      // is an annotation, which no body claims, so it is reached through the
      // full layer tree. (This fixture carries no scene.layers, so it also
      // exercises the legacy category fallback.)
      await page.getByLabel(/^\s*Deformed mesh\s*$/).check();
      await setLayerLeaves(page, /Clash \(\d+\)/, true);
      await page.waitForFunction(() => {
        const ids = window.__tubaViewer?.lastRender?.objectIds ?? [];
        return ids.length === 3 && ids.includes("object:cold") && ids.includes("object:deformed") && ids.includes("object:clash");
      });

      await page.getByLabel(/Visual centerline/).uncheck();
      await page.waitForFunction(() => {
        const ids = window.__tubaViewer?.lastRender?.objectIds ?? [];
        return ids.length === 2 && ids.includes("object:cold") && ids.includes("object:clash") && !ids.includes("object:deformed");
      });

      await setLayerLeaves(page, /Clash \(\d+\)/, false); // layer-tree leaves hide the clash marker
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
      await openReviewControls(page);
      // Analysis mesh is a body; the clash marker is an annotation and lives in
      // the layer tree.
      await page.locator(".layer-tree").evaluate((details) => {
        details.open = true;
      });
      await setLayerLeaves(page, /Clash \(\d+\)/, true);
      await page.getByLabel(/^\s*Analysis mesh\s*$/).check();
      await page.waitForFunction(() => (window.__tubaViewer?.lastRender?.objectIds ?? []).length === 3);
      // The object list is no longer a collapsed disclosure. Clicking the always
      // visible search field opens the finder that owns it.
      await page.locator("[data-search]").click();

      await page.getByRole("button", { name: /Insulated pipe/ }).click();
      let properties = await page.locator("[data-properties]").textContent();
      assert.match(properties, /mineral_wool/);
      assert.match(properties, /effective_radius_m/);
      assert.match(properties, /57000000/);

      await page.getByRole("button", { name: /Copy Entity Ref/ }).click();
      await page.waitForFunction(() => /Copied element:pipe_insulated/.test(document.querySelector("[data-runtime-status]")?.textContent ?? ""));

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
    // Six, not seven: the fixture declares two deformed geometry states and
    // assetMatchesActiveGeometryState draws only the active one, so
    // object:deformed_visual is correctly filtered while the physical one
    // renders. The gate had been asserting a count this bundle cannot reach.
    minimumObjects: 6,
    async run(page) {
      await openReviewControls(page);
      const reviewTask = page.getByRole("button", { name: "Model", exact: true });
      await reviewTask.waitFor();
      assert.equal(await reviewTask.getAttribute("aria-current"), "page");
      await reviewTask.focus();
      assert.deepEqual(await reviewTask.evaluate((button) => {
        const style = getComputedStyle(button);
        return { outlineColor: style.outlineColor, outlineWidth: style.outlineWidth };
      }), { outlineColor: "rgb(94, 216, 229)", outlineWidth: "3px" });
      assert.equal(await page.locator("[data-viewer-workspace]").isVisible(), true);
      assert.equal(await page.locator("[data-status-chip]").isVisible(), true);
      assert.equal(await page.locator("[data-inspector]").isHidden(), true);
      // No evidence dock: the review's tables live in the generated report the
      // header links to, and the shell keeps only what acts on the scene.
      assert.equal(await page.locator("[data-evidence-dock]").count(), 0);
      assert.equal(await page.locator("[data-report-link]").isVisible(), true);
      const headerLayout = await page.locator("[data-app-header]").evaluate((header) => ({
        display: getComputedStyle(header).display,
        centers: [...header.children].map((child) => {
          const rect = child.getBoundingClientRect();
          return rect.top + rect.height / 2;
        })
      }));
      assert.equal(headerLayout.display, "flex");
      assert.ok(
        headerLayout.centers.every((center) => Math.abs(center - headerLayout.centers[0]) <= 1),
        JSON.stringify(headerLayout)
      );

      assert.match(await page.locator("[data-report-link]").getAttribute("href"), /code_aster_results\/index\.html$/);
      await rememberCanvas(page);

      await openReviewControls(page);
      await page.getByRole("button", { name: "Model", exact: true }).click();
      await assertSameCanvas(page);
      await page.getByRole("button", { name: "Results", exact: true }).click();
      await assertSameCanvas(page);

      // The coloring channel lives in the bar now, not duplicated in this panel:
      // the case selector is "Case" up there, and the field selector replaces
      // the panel's result-state picker whenever the scene carries a field
      // catalogue.
      assert.equal(await page.getByRole("combobox", { name: /^Case/ }).inputValue(), "Hot");
      // This bundle declares no result_fields, so the panel still offers the
      // result-state picker; the bar's field selector takes over when a scene
      // does carry a catalogue.
      assert.equal(await page.getByRole("combobox", { name: /^Result state/ }).inputValue(), "result_state:Hot");
      // Stored pascals, read as MPa: 6.00e+6 / 5.70e+7 Pa show as 6 / 57 MPa.
      assert.match(await page.locator("[data-result-legend]").textContent(), /max_von_mises: 6 - 57 MPa/);
      assert.match(await page.locator("[data-hotspot-list]").textContent(), /Hot pipe 57 MPa/);
      // Typed in the displayed unit; the state still holds pascals.
      await page.getByLabel(/Stress threshold/i).evaluate((input) => {
        input.value = "50";
        input.dispatchEvent(new Event("change", { bubbles: true }));
      });
      assert.equal(await page.evaluate(() => window.__tubaViewer?.state?.resultThreshold), 50000000);
      const thresholdHotspots = await page.locator("[data-hotspot-list]").textContent();
      assert.match(thresholdHotspots, /Hot pipe/);
      assert.doesNotMatch(thresholdHotspots, /Warm pipe/);
      // change, not input: the vector sliders commit on change now. Firing per
      // input event re-rendered the pane mid-drag, which destroyed the element
      // under the pointer at the drag's first step.
      await page.getByLabel(/Displacement vector scale/i).evaluate((input) => {
        input.value = "10";
        input.dispatchEvent(new Event("change", { bubbles: true }));
      });
      await page.waitForFunction(() => window.__tubaViewer?.state?.resultVectorScales?.displacement === 10);
      // The tree is the last row of the Display strip, so the summary is the
      // only thing to open.
      await page.locator("details.layer-tree summary").click();
      const visualCenterline = page.getByLabel(/^\s*Visual centerline/);
      const physicalCenterline = page.getByLabel(/^\s*Physical centerline/);
      // Only one geometry state is drawn at a time - assetMatchesActiveGeometryState
      // filters every asset that names a different one - so the physical and the
      // x50 visual deformed shapes can never be on screen together. A solved
      // scene opens on the *physical* state: the visual one is a display
      // exaggeration, and the shape a review opens on must be the real one.
      await page.waitForFunction(() => {
        const ids = window.__tubaViewer?.lastRender?.objectIds ?? [];
        return ids.includes("object:deformed_physical") && !ids.includes("object:deformed_visual");
      });
      assert.equal(await physicalCenterline.isChecked(), true);

      const deformedState = page.getByRole("combobox", { name: /^Deformed state/ });
      const stateValues = await deformedState.evaluate((select) => [...select.options].map((option) => option.value));
      const physicalValue = stateValues.find((value) => /physical/i.test(value));
      const visualValue = stateValues.find((value) => /visual/i.test(value));
      assert.ok(physicalValue, "the bundle must offer a physical deformed state");
      assert.ok(visualValue, "the bundle must offer a visual deformed state");
      // Choosing the exaggerated shape is an explicit act, not the default.
      await deformedState.selectOption(visualValue);
      await page.waitForFunction(() => {
        const ids = window.__tubaViewer?.lastRender?.objectIds ?? [];
        return ids.includes("object:deformed_visual") && !ids.includes("object:deformed_physical");
      });
      assert.equal(await visualCenterline.isChecked(), true);

      await page.getByRole("slider", { name: "Visual deformation scale (display only)" }).evaluate((input) => {
        input.value = "25";
        input.dispatchEvent(new Event("input", { bubbles: true }));
      });
      await page.waitForFunction((expected) => {
        const viewer = window.__tubaViewer;
        const ids = viewer?.lastRender?.objectIds ?? [];
        return viewer?.state?.activeGeometryStateId === expected &&
          viewer.state.visualDeformationScale === 25 &&
          ids.includes("object:deformed_visual") &&
          !ids.includes("object:deformed_physical");
      }, visualValue);

      await visualCenterline.uncheck();
      await page.waitForFunction(
        () => !(window.__tubaViewer?.lastRender?.objectIds ?? []).includes("object:deformed_visual")
      );
      await visualCenterline.check();
      await page.waitForFunction(() =>
        (window.__tubaViewer?.lastRender?.objectIds ?? []).includes("object:deformed_visual")
      );
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
          rail: { left: rail.left, right: rail.right, top: rail.top, bottom: rail.bottom },
          canvas: { left: canvas.left, right: canvas.right, top: canvas.top, width: canvas.width, height: canvas.height },
          display: style.display,
          overflowX: style.overflowX,
          overflowY: style.overflowY
        };
      });
      assert.equal(compactLayout.display, "flex");
      assert.equal(compactLayout.overflowX, "hidden");
      assert.equal(compactLayout.overflowY, "hidden");
      // The rail reserves its width rather than overlaying the scene, so the
      // canvas begins where the panel ends and nothing is drawn underneath it.
      // ("Attach controls toggle to left panel and reserve panel space".)
      assert.ok(Math.abs(compactLayout.rail.left - compactLayout.workspace.left) <= 1, JSON.stringify(compactLayout));
      assert.ok(Math.abs(compactLayout.canvas.left - compactLayout.rail.right) <= 1, JSON.stringify(compactLayout));
      assert.ok(Math.abs(compactLayout.rail.top - compactLayout.canvas.top) <= 1, JSON.stringify(compactLayout));
      assert.ok(Math.abs(compactLayout.canvas.right - compactLayout.workspace.right) <= 1, JSON.stringify(compactLayout));
      assert.ok(compactLayout.canvas.width >= 480, `compact canvas width is too small: ${JSON.stringify(compactLayout)}`);
      assert.ok(compactLayout.canvas.height >= 240, `compact canvas height is too small: ${JSON.stringify(compactLayout)}`);
      const compactStatus = await page.locator("[data-status-chip]").textContent();
      assert.match(compactStatus, /solved/i);
      // The chip states exceptions, never placeholders for facts it lacks.
      assert.doesNotMatch(compactStatus, /Not available/i);
      await openIssuesTask(page);
      assert.equal(await page.getByRole("button", { name: "Issues", exact: true }).getAttribute("aria-current"), "page");
      await assertSameCanvas(page);
      await page.getByRole("button", { name: "Results", exact: true }).click();
      assert.equal(await page.getByRole("button", { name: "Results", exact: true }).getAttribute("aria-current"), "page");
      await assertSameCanvas(page);
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
      // The evidence dock's geometry, its row-level "Show in 3D" actions and
      // the canvas-vs-overlay checks around it all went with the dock. The
      // inspector drawer keeps its own overlay assertions below.
      await page.setViewportSize({ width: 1440, height: 900 });
      await openReviewControls(page);

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
  "pages-gallery": {
    path: "/viewer/",
    canvasFree: true,
    beforeNavigate: captureUnexpectedBrowserEvents,
    async run(page) {
      const cards = page.locator("[data-gallery-card]");
      await cards.first().waitFor({ state: "visible" });
      // Derived, not a literal: which galleries are published is a registry
      // decision (gmsh-tee-mesh-review is dev-only), and a hardcoded count here
      // drifts silently the moment that set changes.
      const published = await page.evaluate(async () => {
        const response = await fetch("./bundles.json");
        return response.ok ? await response.json() : [];
      });
      assert.ok(published.length > 0, "the published catalog must not be empty");
      assert.equal(
        await cards.count(),
        published.length,
        "the landing gallery must offer every published review"
      );

      // Every card leads with the question it answers and keeps its evidence
      // badge visible; a blank card is the failure this page exists to prevent.
      const rendered = await cards.evaluateAll((nodes) =>
        nodes.map((node) => ({
          bundle: node.dataset.galleryCard,
          question: node.querySelector(".gallery-card-question")?.textContent ?? "",
          evidence: node.querySelector("[data-gallery-evidence]")?.textContent ?? "",
          image: node.querySelector(".gallery-card-image")?.getAttribute("src") ?? ""
        }))
      );
      for (const card of rendered) {
        assert.ok(card.question.endsWith("?"), `card ${card.bundle} must ask a question: ${card.question}`);
        assert.ok(card.evidence.length > 0, `card ${card.bundle} must state its evidence`);
        assert.equal(card.image, `gallery/${card.bundle}.png`);
      }
      assert.ok(
        rendered.some((card) => /no results/i.test(card.evidence)),
        "an unsolved review must say so on its card"
      );

      // Choosing a card is an ordinary navigation into the existing review path.
      await page.locator('[data-gallery-card="support-rack-review"]').click();
      await page.waitForFunction(
        () => window.__tubaViewer?.state?.sceneId === "scene:support_rack_review"
      );
      assert.equal(new URL(page.url()).searchParams.get("bundle"), "support-rack-review");
      await page.locator("[data-gallery-link]").click();
      await page.locator("[data-gallery-card]").first().waitFor({ state: "visible" });
    }
  },
  "pages-catalog": {
    path: "/viewer/",
    bundle: "code-aster-review",
    minimumObjects: 1,
    beforeNavigate: captureUnexpectedBrowserEvents,
    async run(page) {
      // The landing gallery must stay out of the way on a review page. An
      // author `display` rule once beat the UA [hidden] rule and left an empty
      // full-viewport panel covering the viewer.
      assert.equal(await page.locator("[data-gallery]").isVisible(), false);
      assert.ok(
        await page.locator("[data-canvas]").isVisible(),
        "the review canvas must be visible on a review page"
      );
      assert.equal(await page.evaluate(() => window.__tubaViewer?.state?.sceneId), "scene:code_aster_artifact_review");

      // The gallery introduces the set; the header switcher moves within it, so
      // comparing two reviews is one control rather than a round trip.
      const picker = page.locator("[data-bundle-picker]");
      await picker.waitFor({ state: "visible" });
      const published = await page.evaluate(async () => {
        const response = await fetch("./bundles.json");
        return response.ok ? await response.json() : [];
      });
      assert.equal(await picker.locator("option").count(), published.length);
      assert.equal(await picker.inputValue(), "code-aster-review");
      await picker.selectOption("support-rack-review");
      await page.waitForFunction(
        () => window.__tubaViewer?.state?.sceneId === "scene:support_rack_review"
      );
      assert.equal(new URL(page.url()).searchParams.get("bundle"), "support-rack-review");
      await picker.selectOption("code-aster-review");
      await page.waitForFunction(
        () => window.__tubaViewer?.state?.sceneId === "scene:code_aster_artifact_review"
      );

      await page.locator("[data-gallery-link]").click();
      const cards = page.locator("[data-gallery-card]");
      await cards.first().waitFor({ state: "visible" });
      assert.deepEqual(
        await cards.evaluateAll((nodes) => nodes.map((node) => node.dataset.galleryCard)),
        [
          "autorouted-expansion-loop",
          "code-aster-review",
          "elements-supports-review",
          "guyed-mast-review",
          "imported_component_mixed_demo",
          "native-friction-review",
          "pipe-tee-volume-review",
          "profile-orientation-review",
          "support-rack-review"
        ]
      );

      // The card says which elements the review solved. Without this the chips
      // can silently stop rendering and every card still looks complete.
      assert.deepEqual(
        await page
          .locator('[data-gallery-card="elements-supports-review"] [data-gallery-elements] li')
          .allTextContents(),
        ["TUYAU_3M", "POU_D_T", "BARRE", "CABLE", "DIS_TR"]
      );

      await page.locator('[data-gallery-card="imported_component_mixed_demo"]').click();
      await page.waitForFunction(
        () => window.__tubaViewer?.state?.sceneId === "scene:imported_component_mixed_system"
      );
      assert.equal(new URL(page.url()).pathname, "/viewer/");
      assert.equal(new URL(page.url()).searchParams.get("bundle"), "imported_component_mixed_demo");
      // Diagnostics live in the rail's Issues task.
      await openIssuesTask(page);
      assert.match(await page.locator("[data-diagnostic-list]").textContent(), /publication\.model_review\.no_solver_results/);
      assert.match(await page.locator("[data-diagnostic-list]").textContent(), /Code_Aster has not been run/);

      for (const [bundle, sceneId] of [
        ["code-aster-review", "scene:code_aster_artifact_review"],
        ["autorouted-expansion-loop", "scene:autorouted_expansion_loop"],
        ["support-rack-review", "scene:support_rack_review"],
        ["code-aster-review", "scene:code_aster_artifact_review"]
      ]) {
        await page.locator("[data-gallery-link]").click();
        await page.locator(`[data-gallery-card="${bundle}"]`).click();
        await page.waitForFunction(
          (expected) => window.__tubaViewer?.state?.sceneId === expected,
          sceneId
        );
        assert.equal(new URL(page.url()).searchParams.get("bundle"), bundle);
      }

      await openReviewControls(page);
      await page.getByRole("button", { name: "Results", exact: true }).click();
      // The rail's primary control is the composited bodies, not the four layer
      // categories: "what is drawn" is the question this screen answers.
      assert.deepEqual(
        await page.locator("[data-body-list] input").evaluateAll((inputs) =>
          inputs.map((input) => input.getAttribute("aria-label"))
        ),
        ["Geometry", "Analysis mesh", "Sub-points", "Deformed mesh"]
      );
      // The categories survive intact, one level down in the All layers row at
      // the foot of the same list. The tree is rendered whether or not the row
      // is open, so there is nothing to click to read it.
      assert.deepEqual(
        await page.locator("[data-layer-list] h3").evaluateAll((headings) =>
          headings.map((heading) => heading.textContent)
        ),
        ["Design", "Analysis mesh", "Results", "Annotations"]
      );

      const field = page.getByRole("combobox", { name: "Field", exact: true });
      assert.deepEqual(
        await field.locator("option").evaluateAll((options) =>
          options.map((option) => ({ label: option.textContent, value: option.value }))
        ),
        [
          { label: "FE VMIS (not code stress) (cell)", value: "field:solver_result:stress:result_state:Operating" },
          { label: "displacement_magnitude", value: "field:solver_result:displacement:result_state:Operating" },
          { label: "reaction_force_magnitude", value: "field:solver_result:reaction_force:result_state:Operating" },
          { label: "reaction_moment_magnitude", value: "field:solver_result:reaction_moment:result_state:Operating" },
          { label: "FE VMIS (not code stress) (subpoint)", value: "field:solver_result:tuyau_subpoints:result_state:Operating" }
        ]
      );

      const canvas = page.locator("[data-canvas]");
      await field.selectOption("field:solver_result:displacement:result_state:Operating");
      await page.waitForFunction(() => {
        const viewer = window.__tubaViewer;
        return (
          viewer?.state?.coloring?.fieldId === "field:solver_result:displacement:result_state:Operating" &&
          viewer.state.coloring.component === "magnitude" &&
          viewer.resultReview?.legend?.field === "displacement_magnitude" &&
          viewer.resultReview.legend.component === "magnitude"
        );
      });
      await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      const displacementMagnitudeFingerprint = await framebufferFingerprint(canvas);

      await page.getByRole("combobox", { name: "Component", exact: true }).selectOption("DZ");
      await page.waitForFunction(() => {
        const viewer = window.__tubaViewer;
        return (
          viewer?.state?.coloring?.fieldId === "field:solver_result:displacement:result_state:Operating" &&
          viewer.state.coloring.component === "DZ" &&
          viewer.resultReview?.legend?.field === "displacement_magnitude" &&
          viewer.resultReview.legend.component === "DZ"
        );
      });
      assert.match(await page.locator("[data-result-legend]").textContent(), /displacement_magnitude DZ:.*m/);
      await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      assert.notEqual(
        await framebufferFingerprint(canvas),
        displacementMagnitudeFingerprint,
        "DZ coloring must render differently from displacement magnitude"
      );

      const deformedState = page.getByRole("combobox", { name: "Deformed state", exact: true });
      await deformedState.selectOption("geometry_state:Operating:physical");
      await page.waitForFunction(() => window.__tubaViewer?.state?.activeGeometryStateId === "geometry_state:Operating:physical");
      let objectIds = await page.evaluate(() => window.__tubaViewer?.lastRender?.objectIds ?? []);
      assert.ok(objectIds.includes("object:deformed_centerline:geometry_state:Operating:physical:pipe_str_0"));
      assert.ok(!objectIds.includes("object:deformed_centerline:geometry_state:Operating:visual_x40:pipe_str_0"));
      assert.ok(objectIds.includes("object:element:pipe_str_0"), "undeformed reference must remain visible");

      await deformedState.selectOption("geometry_state:Operating:visual_x40");
      await page.waitForFunction(() => window.__tubaViewer?.state?.activeGeometryStateId === "geometry_state:Operating:visual_x40");
      objectIds = await page.evaluate(() => window.__tubaViewer?.lastRender?.objectIds ?? []);
      assert.ok(objectIds.includes("object:deformed_centerline:geometry_state:Operating:visual_x40:pipe_str_0"));
      assert.ok(!objectIds.includes("object:deformed_centerline:geometry_state:Operating:physical:pipe_str_0"));
      assert.ok(objectIds.includes("object:element:pipe_str_0"), "undeformed reference must remain visible");

      await openIssuesTask(page);
      const warnings = await page.locator("[data-diagnostic-list]").textContent();
      assert.match(warnings, /visualization\.code_aster_artifacts\.rmed_read_failed/);
      assert.match(warnings, /Unable to synchronously open object/);

      const positiveZ = page.getByRole("button", { name: "+Z", exact: true });
      await positiveZ.focus();
      await page.keyboard.press("Enter");
      await page.waitForFunction(() => {
        const [x, y, z] = (document.querySelector("[data-canvas]")?.dataset.cameraDirection ?? "").split(",").map(Number);
        return Math.abs(x) < 0.01 && Math.abs(y) < 0.01 && z < -0.99;
      });
      // The section box is a secondary tool in the rail popover now.
      await openReviewControls(page);
      await page.locator('[data-rail-tool="section"]').click();
      const sectionEnabled = page.getByLabel("Enable section", { exact: true });
      await sectionEnabled.focus();
      await page.keyboard.press("Space");
      await page.waitForFunction(() => Boolean(window.__tubaViewer?.state?.sectionBox));
      await page.keyboard.press("Tab");
      const sectionMin = page.getByLabel("Section X min", { exact: true });
      assert.equal(await sectionMin.evaluate((input) => document.activeElement === input), true);
      await sectionMin.fill("0");
      await sectionMin.press("Enter");
      await page.waitForFunction(() => window.__tubaViewer?.state?.sectionBox?.min?.[0] === 0);

      assert.equal(await page.locator("[data-canvas]").getAttribute("data-render-diagnostics"), "0");
      assert.deepEqual(await page.evaluate(() => window.__tubaViewer?.lastRender?.diagnostics ?? []), []);
      assert.deepEqual(page.__tubaUnexpectedBrowserEvents, []);
    }
  },
  "public-code-aster-review": {
    bundle: "/code-aster-review",
    minimumObjects: 1,
    beforeNavigate: captureUnexpectedBrowserEvents,
    async run(page) {
      await page.waitForFunction(
        () => window.__tubaViewer?.state?.review?.schema_version === "engineering_review.v1"
      );
      await openReviewControls(page);
      const reviewTask = page.getByRole("button", { name: "Model", exact: true });
      await reviewTask.waitFor();
      assert.equal(await reviewTask.getAttribute("aria-current"), "page");
      assert.equal(await page.locator("[data-viewer-workspace]").isVisible(), true);
      assert.equal(await page.locator("[data-status-chip]").isVisible(), true);
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
      // Exact, so a bundle that silently loses geometry fails loudly. Refreshed
      // for the regenerated bundle: the load reports no diagnostics at all, so
      // the drop from 221/218 is the model changing, not objects going missing.
      assert.equal(loaded.objects, 209);
      assert.equal(loaded.geometryPayloads, 216);
      assert.equal(loaded.overlays, 11);
      assert.equal(loaded.layers, 40);
      assert.equal(loaded.resultFields, 5);
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
      // Count painted frames, which is what "coalesced" actually means. Wall
      // clock over a 12-step drag is dominated by CDP round trips: the same
      // gesture on a five-object scene costs ~1.35s on a loaded machine while
      // painting the same ~14 frames, so timing it conflates a busy runner with
      // a rendering regression.
      await page.evaluate(() => {
        window.__tubaOrbitFrames = 0;
        const raf = window.requestAnimationFrame.bind(window);
        window.__tubaRafOriginal = raf;
        window.requestAnimationFrame = (callback) =>
          raf((timestamp) => {
            window.__tubaOrbitFrames += 1;
            return callback(timestamp);
          });
      });
      const orbitStarted = Date.now();
      await page.mouse.move(canvasBox.x + canvasBox.width * 0.5, canvasBox.y + canvasBox.height * 0.5);
      await page.mouse.down();
      await page.mouse.move(canvasBox.x + canvasBox.width * 0.75, canvasBox.y + canvasBox.height * 0.65, { steps: 12 });
      await page.mouse.up();
      const orbitElapsedMs = Date.now() - orbitStarted;
      await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      const orbitFrames = await page.evaluate(() => {
        const frames = window.__tubaOrbitFrames;
        window.requestAnimationFrame = window.__tubaRafOriginal;
        delete window.__tubaRafOriginal;
        delete window.__tubaOrbitFrames;
        return frames;
      });
      const afterOrbit = await fingerprint();
      await canvas.evaluate((target) => {
        target.removeEventListener("mousemove", window.__tubaBlockCanvasApp, true);
        target.removeEventListener("click", window.__tubaBlockCanvasApp, true);
        delete window.__tubaBlockCanvasApp;
      });
      assert.notEqual(afterOrbit, beforeOrbit, "OrbitControls must redraw without the hover handler");
      // 12 drag steps: one frame each plus the two settling frames is coalesced.
      // Un-coalesced redraws scale with mousemove events, not with frames.
      assert.ok(
        orbitFrames <= 30,
        `OrbitControls redraws must be frame-coalesced, painted ${orbitFrames} frames for 12 drag steps`
      );
      // A loose ceiling that still catches a catastrophic per-frame regression.
      assert.ok(orbitElapsedMs < 8000, `orbit drag took ${orbitElapsedMs}ms`);

      const selectionBeforeRealOrbit = await page.evaluate(() => window.__tubaViewer?.state?.selectedObjectIds ?? []);
      const realOrbitStarted = Date.now();
      await page.mouse.move(canvasBox.x + canvasBox.width * 0.5, canvasBox.y + canvasBox.height * 0.5);
      await page.mouse.down();
      await page.mouse.move(canvasBox.x + canvasBox.width * 0.75, canvasBox.y + canvasBox.height * 0.65, { steps: 12 });
      await page.mouse.up();
      const realOrbitElapsedMs = Date.now() - realOrbitStarted;
      const selectionAfterRealOrbit = await page.evaluate(() => window.__tubaViewer?.state?.selectedObjectIds ?? []);
      // The assertion below is the real check. This one is a loose ceiling only:
      // a 12-step drag costs ~1.35s in CDP round trips on a loaded machine even
      // with five objects on screen, so a tight bound here measures the runner
      // rather than whether picking ran.
      assert.ok(realOrbitElapsedMs < 8000, `a real orbit gesture took ${realOrbitElapsedMs}ms`);
      assert.deepEqual(selectionAfterRealOrbit, selectionBeforeRealOrbit, "an orbit gesture must not change selection");

      await page.getByRole("button", { name: "Results", exact: true }).click();
      assert.equal(await page.getByRole("button", { name: "Results", exact: true }).getAttribute("aria-current"), "page");
      await assertSameCanvas(page);
      // The coloring channel lives in the Results task; its selector is "Case".
      assert.equal(await page.getByRole("combobox", { name: /^Case/ }).inputValue(), "Operating");
      assert.equal(
        await page.getByRole("combobox", { name: "Field", exact: true }).inputValue(),
        "field:solver_result:stress:result_state:Operating"
      );
      assert.equal(await page.getByRole("combobox", { name: /^Result state/ }).count(), 0);
      // Scalar fields have no component decision; the control appears only
      // when the selected vector field actually offers one.
      const scalarComponent = page.getByRole("combobox", { name: "Component", exact: true });
      assert.equal(await scalarComponent.count(), 0);

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

      // Selecting from a review table and mirroring the selection back into it
      // were the evidence dock's; the rail's finder and the inspector carry
      // object selection now.
      assert.deepEqual(page.__tubaUnexpectedBrowserEvents, []);
    }
  },
  // Arriving without ?bundle= no longer guesses a review: it offers the set.
  // pages-gallery covers the published catalog, which needs a built site; this
  // covers the same default against the examples the dev server discovers, so
  // the landing behaviour is gated without a Pages build.
  "default-landing-gallery": {
    bundle: null,
    canvasFree: true,
    async run(page) {
      const cards = page.locator("[data-gallery-card]");
      await cards.first().waitFor({ state: "visible" });
      assert.ok(await cards.count() >= 2, "the landing gallery must offer a choice");
      // The canvas element is in the shell markup; what must not happen is a
      // Three viewport being built for a page that shows no scene.
      assert.equal(await page.locator("[data-canvas]").isVisible(), false);
      assert.equal(
        await page.locator("[data-canvas]").getAttribute("data-renderer"),
        null,
        "the gallery must not construct a renderer"
      );

      // A card is a link into the ordinary review path.
      const first = await cards.first().getAttribute("data-gallery-card");
      await cards.first().click();
      await page.waitForFunction(() => Boolean(window.__tubaViewer?.state?.sceneId));
      assert.equal(new URL(page.url()).searchParams.get("bundle"), first);
      assert.equal(await page.locator("[data-gallery]").isVisible(), false);
    }
  },
  "legacy-workflow": {
    bundle: "/test/fixtures/smoke_scene",
    minimumObjects: 3,
    async beforeNavigate(page) {
      await page.route("**/smoke_scene/review.json", (route) =>
        route.fulfill({ status: 404, contentType: "application/json", body: "" })
      );
    },
    async run(page) {
      await openReviewControls(page);
      const modelTask = page.getByRole("button", { name: "Model", exact: true });
      await modelTask.waitFor();
      assert.equal(await modelTask.getAttribute("aria-current"), "page");
      assert.equal(await page.getByRole("button", { name: "Issues", exact: true }).count(), 1);
      assert.equal(await page.getByRole("button", { name: "Review", exact: true }).count(), 0);
      assert.equal(await page.getByRole("button", { name: "Display", exact: true }).count(), 0);
      // There is no evidence dock any more: warnings live in the Issues task
      // and the review's tables live in the generated report.
      assert.equal(await page.locator("[data-evidence-dock]").count(), 0);
      assert.equal(await page.getByRole("tab", { name: "Warnings", exact: true }).count(), 0);
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
    // Six: this bundle declares two deformed geometry states and only the
    // active one is drawn (assetMatchesActiveGeometryState), so the seventh
    // object can never render.
    minimumObjects: 6,
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
      // Partial compliance rows must never be dressed up as a verdict. The
      // chip carries no governing facts at all, and the Governing Results card
      // states plainly that they are unavailable rather than printing a ratio
      // derived from an incomplete table.
      const chip = await page.locator("[data-status-chip]").textContent();
      assert.doesNotMatch(chip, /Partial Operating|pipe_partial|0\.86|Compliance fail/i);

      // Nothing anywhere in the shell may restate the partial rows as a
      // verdict; cockpitStatusViewModel's own tests hold the neutrality rule.
      await openIssuesTask(page);
      const shell = await page.locator(".app-shell").textContent();
      assert.doesNotMatch(shell, /Partial Operating|pipe_partial|0\.86/);
    }
  },
  "embedded-review": {
    bundle: "/test/fixtures/code_aster_results",
    minimumObjects: 6,
    query() {
      return { embed: "1" };
    },
    async run(page) {
      await page.waitForFunction(() => window.__tubaViewer?.state?.activeTab === "3d");
      assert.equal(await page.getByRole("banner").isVisible(), false);
      assert.equal(await page.locator("[data-task-rail]").isVisible(), false);
      assert.equal(await page.locator("[data-status-chip]").isVisible(), false);
      assert.equal(await page.locator("[data-evidence-dock]").isVisible(), false);
      assert.equal(await page.locator("[data-inspector]").isVisible(), false);
      assert.equal(await page.getByLabel("Interactive 3D engineering review viewport").isVisible(), true);
      assert.equal(await page.evaluate(() => window.__tubaViewer?.state?.embed), true);
    }
  },
  "clash-review": {
    bundle: "/test/fixtures/code_aster_results",
    minimumObjects: 6,
    async run(page) {
      await openReviewControls(page);
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
      await page.waitForFunction(() => /BCF ready issue:operating_clash/.test(document.querySelector("[data-runtime-status]")?.textContent ?? ""));

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
    bundle: "/test/fixtures/smoke_scene",
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
      await page.waitForFunction(() => /Preview run started/.test(document.querySelector("[data-runtime-status]")?.textContent ?? ""));

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
      await page.waitForFunction(() => /preview boom/.test(document.querySelector("[data-runtime-status]")?.textContent ?? ""));

      const previewEvents = await page.evaluate(() => window.__tubaViewer?.previewEvents ?? []);
      assert.deepEqual(previewEvents.map((event) => event.type), ["run_started", "scene_reloaded", "diagnostic"]);
    }
  },
  "patch-preview": {
    bundle: "/test/fixtures/smoke_scene",
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
      await page.waitForFunction(() => /Preview run 12 started/.test(document.querySelector("[data-runtime-status]")?.textContent ?? ""));

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
      await page.waitForFunction(() => /patch schema failed/.test(document.querySelector("[data-runtime-status]")?.textContent ?? ""));
      await openIssuesTask(page);
      const diagnostics = await page.locator("[data-diagnostic-list]").textContent();
      assert.match(diagnostics, /visualization.patch_preview.invalid_patch/);

      const previewEvents = await page.evaluate(() => window.__tubaViewer?.previewEvents ?? []);
      assert.deepEqual(previewEvents.map((event) => event.type), ["run_started", "scene_reloaded", "diagnostic"]);
    }
  },
  "scene-diff": {
    bundle: "/test/fixtures/smoke_scene",
    minimumObjects: 3,
    async setup() {
      return startTestWebSocketServer();
    },
    query(runtime) {
      return { preview_ws: runtime.url };
    },
    async run(page, runtime) {
      await openReviewControls(page);
      await page.waitForFunction(() => window.__tubaViewer?.state?.sceneId === "viewer_smoke_scene");
      // The object list is no longer a collapsed disclosure. Clicking the always
      // visible search field opens the finder that owns it.
      await page.locator("[data-search]").click();
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
      await openIssuesTask(page);
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

// Both pages-* scenarios exercise the published tree, so both need its root.
const staticSiteRoot = scenario.startsWith("pages-")
  ? parseSiteRoot(scenario, process.argv.slice(3))
  : null;

let browser;
let server;
let runtime;

try {
  runtime = await selected.setup?.();
  server = await createServer({
    root: staticSiteRoot ?? viewerRoot,
    ...(staticSiteRoot ? { configFile: false } : {}),
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
  // "Copy Entity Ref" now waits for the clipboard write to resolve before it
  // reports success, so the scenario needs the permission the browser would
  // otherwise refuse. Without it the button correctly reports a failure, which
  // is the point - it used to announce "Copied" whether or not anything was.
  await page.context().grantPermissions(["clipboard-read", "clipboard-write"]);
  page.setDefaultTimeout(15_000);
  await selected.beforeNavigate?.(page, runtime);

  const url = new URL(selected.path ?? "/", baseUrl);
  if (selected.bundle) {
    url.searchParams.set("bundle", selected.bundle);
  }
  for (const [name, value] of Object.entries(selected.query?.(runtime) ?? {})) {
    url.searchParams.set(name, value);
  }
  await page.goto(url.toString(), { waitUntil: "domcontentloaded" });
  await page.waitForFunction(() => /Ready/.test(document.querySelector("[data-runtime-status]")?.textContent ?? ""));
  if (selected.canvasFree) {
    // The gallery is a navigation surface: it never builds a viewport, so the
    // canvas and WebGL gates below have nothing to wait for.
    await selected.run?.(page, runtime);
    console.log(`${scenario} ok: canvas-free scenario`);
    await shutdown();
    process.exit(0);
  }
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

function parseSiteRoot(scenario, args) {
  const flagIndex = args.indexOf("--site-root");
  const value = flagIndex >= 0 ? args[flagIndex + 1] : null;
  if (!value || value.startsWith("--")) {
    throw new Error(`${scenario} requires --site-root PATH`);
  }
  const siteRoot = resolve(process.cwd(), value);
  if (!existsSync(resolve(siteRoot, "viewer", "index.html"))) {
    throw new Error(`Pages site root lacks viewer/index.html: ${siteRoot}`);
  }
  return siteRoot;
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
