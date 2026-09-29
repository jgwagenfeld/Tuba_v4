import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { readFile } from "node:fs/promises";

const VIEWPORTS = {
  desktop: { width: 1440, height: 900 },
  compact: { width: 1024, height: 768 },
  narrow: { width: 800, height: 900 },
  // Phone. This case did not exist, and that is why a broken header survived:
  // at 390px the wordmark, the scene name, the bundle picker and the stage
  // switch all competed for one row, the scene name collapsed to nothing and
  // the picker overprinted the switch. The narrowest golden was 800px, so no
  // committed reference image could see it. Every layout claim about a phone in
  // this file is now backed by a phone.
  phone: { width: 390, height: 844 }
};

// Above this width a viewport is expected to behave like a desktop with a
// narrower window; at or below it the shell goes to its single-column form.
const PHONE_WIDTH = 520;

const NARROW_VIEWPORTS = new Set(["narrow", "phone"]);

const DOCUMENTATION_PAGES = ["/index.html", "/setup.html"];

test("review keeps technical details optional and stress fields distinguishable", async ({ page }) => {
  await page.goto("/viewer/?bundle=code-aster-review");
  await expect(page.locator("[data-runtime-status]")).toHaveText("Ready");
  await expect(page.locator("[data-color-legend]")).toBeEmpty();
  await expect(page.locator("[data-field-description]")).toBeHidden();
  await expect(page.locator("[data-solver-fact]")).toBeHidden();
  await expect(page.locator("[data-discretisation-check]")).toBeHidden();
  await expect(page.locator("[data-scene-title]")).toHaveClass("visually-hidden");
  const fields = page.getByRole("combobox", { name: "Colour the scene by" });
  await fields.selectOption({ label: "Von Mises stress (wall points)" });
  await expect(page.locator("[data-viewport-legend]")).toContainText("Von Mises stress (wall points)");
  await expect(page.locator("[data-compliance-notice]")).toBeVisible();
  await page.locator("[data-field-details] > summary").click();
  await expect(page.locator("[data-field-description]")).toContainText("Support: subpoint");
  await page.locator("[data-analysis-summary]").press("Enter");
  await expect(page.locator("[data-solver-fact]")).toContainText("Code_Aster");
  await expect(page.locator("[data-discretisation-check]")).toBeVisible();
  await fields.selectOption({ label: "Displacement" });
  await expect(page.locator("[data-compliance-notice]")).toHaveCount(0);
  await expect(page.locator("[data-field-description]")).toContainText("Support: node");
  await expect(page.locator("[data-projection-note]")).toBeHidden();
});

test("gallery Build edits stay drafts and invalidate the published review", async ({ page }) => {
  test.setTimeout(120_000);
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/viewer/?bundle=code-aster-review");
  await expect(page.locator("[data-runtime-status]")).toHaveText("Ready", { timeout: 60_000 });
  await page.getByRole("button", { name: "Build", exact: true }).click();
  const editor = page.locator("[data-code-text]");
  await expect(editor).toBeEditable();
  await expect(page.locator("[data-code-run]")).toHaveText("Update geometry");
  const original = await editor.inputValue();
  const draft = original.replace("builder.run(3.0)", "builder.run(4.0)");
  expect(draft).not.toBe(original);
  const objects = await page.evaluate(() => JSON.stringify(window.__tubaViewer.state.objects));
  const badge = page.locator("[data-status-chip] [data-status]");
  const originalStatus = await badge.getAttribute("data-status");
  expect(originalStatus).not.toBe("stale");
  const wouldLoseDraft = () => page.evaluate(() => {
    const event = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(event);
    return event.defaultPrevented;
  });
  await editor.fill(draft);
  await expect(badge).toHaveAttribute("data-status", "stale");
  await expect(page.locator("[data-code-case-status]")).toHaveText("Review outdated");
  await expect(page.locator("[data-code-foot]")).toContainText("Python in your browser");
  await expect(page.locator("[data-code-foot]")).toContainText("published Code_Aster results");
  expect(await wouldLoseDraft()).toBe(true);
  expect(await page.evaluate(() => JSON.stringify(window.__tubaViewer.state.objects))).toBe(objects);
  await page.screenshot({ path: "../.build/gallery-edit-build.png" });
  await page.getByRole("button", { name: /Solver \.comm/ }).click();
  await expect(page.locator("[data-comm-text]")).toHaveAttribute("data-state", "ready");
  await expect(page.locator("[data-code-state]")).toHaveText("Read-only");
  await expect(page.locator("[data-code-download]")).toBeHidden();
  await page.getByRole("button", { name: /model\.py/ }).click();
  await expect(editor).toHaveValue(draft);
  await page.getByRole("button", { name: "Review", exact: true }).click();
  await expect(badge).toHaveAttribute("data-status", "stale");
  await page.screenshot({ path: "../.build/gallery-edit-review.png" });
  await page.locator("[data-bundle-picker]").selectOption("autorouted-expansion-loop");
  await expect(page.locator("[data-runtime-status]")).toHaveText("Ready");
  await expect(badge).not.toHaveAttribute("data-status", "stale");
  await page.locator("[data-bundle-picker]").selectOption("code-aster-review");
  await expect(page.locator("[data-runtime-status]")).toHaveText("Ready");
  await expect(badge).toHaveAttribute("data-status", "stale");
  await page.getByRole("button", { name: "Build", exact: true }).click();
  await expect(editor).toHaveValue(draft);
  const downloaded = page.waitForEvent("download");
  await page.getByRole("button", { name: "Exchange", exact: true }).click();
  await page.getByRole("button", { name: "Download model.py", exact: true }).click();
  await page.getByRole("button", { name: "Close exchange", exact: true }).click();
  const file = await downloaded;
  expect(file.suggestedFilename()).toBe("model.py");
  expect(await readFile(await file.path(), "utf8")).toBe(draft);
  expect(await wouldLoseDraft()).toBe(false);
  await expect(badge).toHaveAttribute("data-status", "stale");
  await editor.fill(original);
  await expect(badge).toHaveAttribute("data-status", originalStatus);
  expect(await wouldLoseDraft()).toBe(false);
  await page.getByRole("button", { name: "Review", exact: true }).click();
  await page.locator("[data-objects-section] > summary").click();
  await page.getByRole("searchbox", { name: "Search objects" }).fill("pipe_str_0");
  await page.locator('[data-object-id="object:element:pipe_str_0"]').click();
  await page.getByRole("button", { name: "Build", exact: true }).click();
  const length = page.getByRole("spinbutton", { name: /Length/ });
  await length.fill("4");
  await length.press("Tab");
  await expect(editor).toHaveValue(draft);
  await expect(page.locator("[data-code-state]")).toHaveText("Geometry preview", { timeout: 90_000 });
  await expect(badge).toHaveAttribute("data-status", "not_solved");
  expect(await wouldLoseDraft()).toBe(true);
  await page.getByRole("button", { name: "Exchange", exact: true }).click();
  await page.getByText("Example actions", { exact: true }).click();
  await page.getByRole("button", { name: "Reset example", exact: true }).click();
  expect(errors).toEqual([]);
});

test("load-case gallery exposes four solved cases and their input assignments", async ({ page }) => {
  test.setTimeout(90_000);
  await page.goto("/viewer/?bundle=load-case-preparation");
  await expect(page.locator("[data-runtime-status]")).toHaveText("Ready", { timeout: 60_000 });
  const cases = page.getByRole("combobox", { name: /^Case/ });
  expect(await cases.locator("option").evaluateAll(options => options.map(option => option.value).sort()))
    .toEqual(["Occasional", "OperatingHot", "PressureOnly", "Sustained"]);
  for (const name of ["OperatingHot", "PressureOnly", "Sustained", "Occasional"]) {
    await cases.selectOption(name);
    await expect.poll(() => page.evaluate(() => window.__tubaViewer.state.activeLoadCase)).toBe(name);
    const state = await page.evaluate(() => {
      const viewer = window.__tubaViewer.state;
      return viewer.resultStates.find(result => result.data.id === viewer.activeResultStateId)?.data;
    });
    expect(state.load_case).toBe(name);
  }
  await cases.selectOption("OperatingHot");
  await page.locator("[data-review-inputs] > summary").click();
  await expect(page.getByRole("table", { name: "OperatingHot input assignments" })).toContainText("temperature");
  await expect(page.locator("[data-canvas]")).toHaveAttribute("data-render-diagnostics", "0");
  await page.screenshot({ path: "../.build/load-case-inputs.png" });
});

test("published expansion loop contains pipe geometry without legacy envelope skins", async ({ page }) => {
  test.setTimeout(90_000);
  await page.goto("/viewer/?bundle=autorouted-expansion-loop", { waitUntil: "domcontentloaded" });
  await expect(page.locator("[data-runtime-status]")).toHaveText("Ready", { timeout: 60_000 });
  await expect(page.locator("[data-task-rail]")).toBeVisible();
  await expect(page.locator("[data-rail-toggle]")).toHaveAttribute("aria-expanded", "true");
  // Reviews ship without a design standard now that the code checks are gone,
  // so the header must not lead with the separator for the missing half.
  await expect(page.locator("[data-scene-meta]")).not.toHaveText(/^\s*·/);
  const shells = await page.evaluate(async () => {
    const scene = await (await fetch("./autorouted-expansion-loop/scene.json")).json();
    return scene.objects.filter(obj => ["physical_envelope", "deformed_envelope"].includes(obj.kind));
  });
  const canvas = page.locator("[data-canvas]");
  const arrowPixels = () => canvas.evaluate(target => {
    const gl = target.getContext("webgl2");
    const w = gl.drawingBufferWidth, h = gl.drawingBufferHeight;
    const pixels = new Uint8Array(w * h * 4);
    gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
    let count = 0;
    // Exclude the view gizmo in the lower-right corner.
    for (let y = 150; y < h; y++) for (let x = 0; x < w; x++) {
      const i = (y * w + x) * 4;
      // Support glyph amber, as drawn: ~rgb(224,176,80). Warm and clearly
      // warmer than it is blue, which excludes the pale background, the grid,
      // and the blue pipe and reaction arrows.
      if (pixels[i] > 180 && pixels[i + 2] < 140 && pixels[i] - pixels[i + 2] > 80) count++;
    }
    return count;
  });
  expect(await arrowPixels()).toBeGreaterThan(100);
  const box = await canvas.boundingBox();
  const direction = await canvas.getAttribute("data-camera-direction");
  await page.mouse.move(box.x + box.width * 0.65, box.y + box.height * 0.5);
  await page.mouse.down();
  try {
    await page.mouse.move(box.x + box.width * 0.72, box.y + box.height * 0.55, { steps: 8 });
    await expect(canvas).not.toHaveAttribute("data-camera-direction", direction);
    expect(await arrowPixels()).toBeGreaterThan(100);
  } finally {
    await page.mouse.up();
  }
  // This example has no assigned insulation, so neither cold nor deformed skins belong here.
  expect(shells).toEqual([]);
  await expect(page.locator("[data-canvas]")).toHaveAttribute("data-render-diagnostics", "0");
});

test("left controls toggle reserves space beside the viewport", async ({ page }) => {
  test.setTimeout(90_000);
  await page.goto("/viewer/?bundle=autorouted-expansion-loop");
  await expect(page.locator("[data-runtime-status]")).toHaveText("Ready", { timeout: 60_000 });
  for (const width of [1440, 1024, 800]) {
    await page.setViewportSize({ width, height: 900 });
    const rail = page.locator("[data-task-rail]");
    const toggle = page.getByRole("button", { name: "Hide controls", exact: true });
    await expect(toggle).toHaveAttribute("title", "Hide controls");
    const r = await rail.boundingBox(), t = await toggle.boundingBox();
    expect(Math.abs(t.x - (r.x + r.width))).toBeLessThan(2);
    // The rail reserves its width rather than floating over the scene: the
    // canvas starts where the rail ends, at every width.
    expect(Math.abs((await page.locator("[data-canvas]").boundingBox()).x - (r.x + r.width))).toBeLessThan(2);
    await toggle.click();
    const show = page.getByRole("button", { name: "Show controls", exact: true });
    await expect(rail).toBeHidden();
    expect((await show.boundingBox()).x).toBeLessThan(2);
    await show.focus();
    await page.keyboard.press("Enter");
    await expect(rail).toBeVisible();
  }
});

test("assembled Pages gallery scrolls to the final review", async ({ page }) => {
  await page.setViewportSize({ width: 800, height: 600 });
  await page.goto("/viewer/", { waitUntil: "domcontentloaded" });
  const cards = page.locator("[data-gallery-card]");
  // The published catalog decides how many reviews ship; the gallery has to
  // render all of them, so count against it rather than a number that rots.
  const published = await page.evaluate(async () => (await (await fetch("./bundles.json")).json()).length);
  expect(published).toBeGreaterThan(1);
  await expect(cards).toHaveCount(published);
  expect(await page.evaluate(() => getComputedStyle(document.body).overflowY)).toBe("auto");

  await page.mouse.wheel(0, 800);
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(0);
  await page.keyboard.press("End");
  await expect(cards.last()).toBeInViewport();
});

test("assembled Pages keeps results accessible when WebGL2 is unavailable", async ({ page }) => {
  const browserErrors = [];
  page.on("pageerror", (error) => browserErrors.push(`pageerror: ${error.message}`));
  page.on("console", (message) => {
    if (message.type() === "error") browserErrors.push(`console: ${message.text()}`);
  });
  await page.addInitScript(() => {
    const getContext = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (type, ...args) {
      return type === "webgl2" ? null : getContext.call(this, type, ...args);
    };
  });

  await page.goto("/viewer/?bundle=code-aster-review", { waitUntil: "domcontentloaded" });
  await expect(page.locator("[data-viewport-unavailable]")).toBeVisible();
  await expect(page.locator("[data-runtime-status]")).toHaveText("Results ready · 3D unavailable");
  await expect(page.locator("[data-canvas]")).toBeHidden();

  // The rail is one column; the colouring channel's legend names the field.
  await expect(page.locator("[data-viewport-legend]")).toContainText("Von Mises stress");
  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(accessibility.violations).toEqual([]);
  expect(browserErrors).toEqual([]);
});

test("assembled Pages viewer is accessible and visually stable", async ({ page }) => {
  const browserErrors = [];
  page.on("pageerror", (error) => browserErrors.push(`pageerror: ${error.message}`));
  page.on("console", (message) => {
    if (message.type() === "error") browserErrors.push(`console: ${message.text()}`);
  });
  page.on("requestfailed", (request) => {
    browserErrors.push(`requestfailed: ${request.url()} ${request.failure()?.errorText ?? "unknown"}`);
  });

  await page.goto("/viewer/?bundle=code-aster-review", { waitUntil: "domcontentloaded" });
  await expect(page.locator("[data-runtime-status]")).toHaveText("Ready");
  await page.waitForFunction(() => {
    const canvas = document.querySelector("[data-canvas]");
    return (
      canvas?.dataset.renderer === "three" &&
      Number(canvas.dataset.renderedObjects ?? 0) > 0 &&
      canvas.dataset.renderDiagnostics === "0"
    );
  });
  await page.evaluate(() => document.fonts.ready);
  const typography = await page.evaluate(() => ({
    loadedFamilies: [...document.fonts].filter((font) => font.status === "loaded").map((font) => font.family),
    ui: getComputedStyle(document.body).fontFamily,
    mono: getComputedStyle(document.querySelector(".runtime-status")).fontFamily
  }));
  expect(typography.loadedFamilies).toContain("Roboto Condensed");
  expect(typography.loadedFamilies).toContain("IBM Plex Mono");
  expect(typography.ui).toBe('"Roboto Condensed", sans-serif');
  expect(typography.mono).toBe('"IBM Plex Mono", monospace');

  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(accessibility.violations).toEqual([]);

  await expect(page.locator("[data-build-identity]")).toHaveText(/^Source [a-f0-9]{12}$/);
  await expect(page.locator("[data-viewer-identity]")).toHaveText(/^Viewer [a-f0-9]{12}$/);

  // Keep the existing full-canvas visual baseline; initial open state is checked above.
  await page.locator("[data-rail-toggle]").click();
  for (const [name, viewport] of Object.entries(VIEWPORTS)) {
    await page.setViewportSize(viewport);
    await page.getByRole("button", { name: /^Reset 3D view\b/ }).click();
    await page.waitForFunction(() => {
      const canvas = document.querySelector("[data-canvas]");
      const gl = canvas?.getContext("webgl2") || canvas?.getContext("webgl");
      return Boolean(
        gl &&
        canvas.clientWidth > 0 &&
        canvas.clientHeight > 0 &&
        gl.drawingBufferWidth === Math.round(canvas.clientWidth * devicePixelRatio) &&
        gl.drawingBufferHeight === Math.round(canvas.clientHeight * devicePixelRatio)
      );
    });
    await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    await expect(page).toHaveScreenshot(`pages-${name}.png`, {
      animations: "disabled",
      caret: "hide",
      // Content hashes change with each build; assert their format above and
      // keep the rest of the header covered by the visual comparison.
      mask: [page.locator("[data-build-identity]:visible, [data-viewer-identity]:visible")],
      // Narrow software-rendered WebGL varies slightly between Ubuntu runners.
      maxDiffPixelRatio: NARROW_VIEWPORTS.has(name) ? 0.015 : 0.002
    });
  }

  expect(browserErrors).toEqual([]);
});

// Overlap is not overflow, which is why a scroll-width check did not catch the
// broken phone header: two flex children at left: 0 and left: 296px in a 390px
// row overprint each other and still report scrollWidth === clientWidth. This
// measures the boxes against each other instead, at every committed viewport.
test("no two header controls overprint each other at any committed width", async ({ page }) => {
  await page.goto("/viewer/?bundle=code-aster-review", { waitUntil: "domcontentloaded" });
  await expect(page.locator("[data-runtime-status]")).toHaveText("Ready");

  for (const [name, viewport] of Object.entries(VIEWPORTS)) {
    await page.setViewportSize(viewport);
    await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(resolve)));

    const overlaps = await page.evaluate(() => {
      // Only the identity block's own children and the two controls that
      // compete with it. Header actions are a separate flex line by design.
      const selectors = [
        ".wordmark",
        ".app-identity h1",
        ".bundle-picker",
        ".mode-switch"
      ];
      const boxes = selectors
        .map((selector) => ({ selector, element: document.querySelector(selector) }))
        .filter(({ element }) => element && element.getClientRects().length > 0)
        .map(({ selector, element }) => {
          const rect = element.getBoundingClientRect();
          return { selector, rect: { x: rect.x, y: rect.y, w: rect.width, h: rect.height } };
        });
      const found = [];
      for (let a = 0; a < boxes.length; a += 1) {
        for (let b = a + 1; b < boxes.length; b += 1) {
          const one = boxes[a].rect;
          const two = boxes[b].rect;
          const overlapX = Math.min(one.x + one.w, two.x + two.w) - Math.max(one.x, two.x);
          const overlapY = Math.min(one.y + one.h, two.y + two.h) - Math.max(one.y, two.y);
          if (overlapX > 1 && overlapY > 1) {
            found.push(`${boxes[a].selector} x ${boxes[b].selector} (${overlapX.toFixed(0)}x${overlapY.toFixed(0)}px)`);
          }
        }
      }
      return found;
    });

    expect(overlaps, `${name} (${viewport.width}px) header controls overprint`).toEqual([]);
  }
});

// The 1.83:1 download links were the only colour-contrast violation axe found on
// either surface, and they were in the primary action zone of a shared page. No
// rule ever named them, so they rendered in the browser's own link blue. The
// page has a card with downloads only when the catalog publishes one, so this
// asserts on the element wherever it appears rather than assuming a card.
test("gallery download links are legible on the card surface", async ({ page }) => {
  await page.goto("/viewer/", { waitUntil: "domcontentloaded" });
  await expect(page.locator("[data-gallery]")).toBeVisible();
  await expect(page.locator("[data-gallery-grid]").first()).toBeVisible();

  const links = page.locator(".gallery-card-downloads a");
  if ((await links.count()) === 0) {
    // No published download in this catalog. The rule still has to exist, or the
    // next bundle that publishes one inherits UA blue again.
    const styled = await page.evaluate(() => {
      const probe = document.createElement("a");
      probe.className = "gallery-card-downloads";
      probe.style.display = "none";
      document.body.append(probe);
      const inner = document.createElement("a");
      inner.textContent = "probe";
      probe.append(inner);
      const color = getComputedStyle(inner).color;
      probe.remove();
      return color;
    });
    expect(styled).not.toBe("rgb(0, 0, 238)");
    return;
  }

  const contrast = await links.evaluateAll((nodes) =>
    nodes.map((node) => {
      const style = getComputedStyle(node);
      return { color: style.color, fontSize: style.fontSize, decoration: style.textDecorationLine };
    })
  );
  for (const style of contrast) {
    expect(style.color).not.toBe("rgb(0, 0, 238)");
    expect(parseFloat(style.fontSize)).toBeGreaterThanOrEqual(11);
    expect(style.decoration).not.toBe("underline");
  }

  const violations = await new AxeBuilder({ page }).analyze();
  expect(violations.violations).toEqual([]);
});

test("assembled Pages documentation is accessible", async ({ page }) => {
  for (const path of DOCUMENTATION_PAGES) {
    await page.goto(path, { waitUntil: "load" });
    // The theme mounts its search dialog and clipboard buttons after load, and
    // docs/content/assets/a11y.js repairs them as they appear.
    await page.waitForFunction(
      () =>
        Boolean(document.querySelector('body > [role="search"]')) &&
        !document.querySelector("nav.md-code__nav:not([role])")
    );
    const loaded = await new AxeBuilder({ page }).analyze();
    expect(loaded.violations).toEqual([]);

    const input = page.locator('input[aria-label="Search"]');
    await page.locator("button.md-search__button").click();
    await expect(input).toBeFocused();
    const opened = await new AxeBuilder({ page }).analyze();
    expect(opened.violations).toEqual([]);

    await input.fill("code");
    await page.waitForFunction(() => {
      const dialog = document.querySelector('body > [role="search"]');
      return Number(dialog?.shadowRoot?.querySelectorAll("ol li a").length) > 0;
    });
    await page.getByRole("button", { name: "Filters" }).click();
    // Zensical 0.0.51 highlights matches in a colour that misses 4.5:1 against
    // the inline code chips in result titles. That palette defect is upstream
    // and unfixed here; every other check still gates this state.
    const results = await new AxeBuilder({ page }).disableRules(["color-contrast"]).analyze();
    expect(results.violations).toEqual([]);
  }
  // Console and network errors are deliberately not asserted here: the theme's
  // release badge requests /releases/latest, which 404s until the repository
  // publishes its first GitHub release.
});

test("assembled Pages renders the native 3D tee result fields", async ({ page, request }) => {
  await page.goto("/viewer/?bundle=pipe-tee-volume-review", { waitUntil: "domcontentloaded" });
  await expect(page.locator("[data-runtime-status]")).toHaveText("Ready", { timeout: 30_000 });
  await page.waitForFunction(() => {
    const canvas = document.querySelector("[data-canvas]");
    return canvas?.dataset.renderer === "three" && Number(canvas.dataset.renderedObjects ?? 0) > 0;
  });

  const response = await request.get("/viewer/pipe-tee-volume-review/scene.json");
  expect(response.ok()).toBe(true);
  const scene = await response.json();
  const objectKinds = new Set(scene.objects.map((object) => object.kind));
  for (const kind of ["analysis_mesh_surface", "volume_stress_field", "volume_displacement_field"]) {
    expect(objectKinds.has(kind)).toBe(true);
  }
  const overlays = new Map(scene.overlays.map((overlay) => [overlay.id, overlay]));
  expect(new Set(scene.result_fields.map((field) => overlays.get(field.overlay_id)?.data?.result_type))).toEqual(
    // tuyau_subpoints is the 1D remainder's wall stress: this is a mixed study,
    // so the TUYAU_3M extensions report subpoints beside the solid's cell field.
    new Set(["stress", "displacement", "reaction_force", "reaction_moment", "tuyau_subpoints"])
  );
  expect(JSON.stringify(scene)).toContain("visualization_only_not_asme_code_stress");
});
