import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const VIEWPORTS = {
  desktop: { width: 1440, height: 900 },
  compact: { width: 1024, height: 768 },
  narrow: { width: 800, height: 900 }
};

const DOCUMENTATION_PAGES = ["/index.html", "/setup.html"];

test("published expansion loop contains pipe geometry without legacy envelope skins", async ({ page }) => {
  test.setTimeout(90_000);
  await page.goto("/viewer/?bundle=autorouted-expansion-loop", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("status")).toHaveText("Ready", { timeout: 60_000 });
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
      if (pixels[i] > 180 && pixels[i + 1] < 160 && pixels[i + 2] < 90) count++;
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
  await expect(page.getByRole("status")).toHaveText("Ready", { timeout: 60_000 });
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
  await expect(page.getByRole("status")).toHaveText("Results ready · 3D unavailable");
  await expect(page.locator("[data-canvas]")).toBeHidden();

  await page.getByRole("button", { name: "Results", exact: true }).click();
  await expect(page.locator("[data-task-panel]")).toContainText("FE VMIS (not code stress)");
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
  await expect(page.getByRole("status")).toHaveText("Ready");
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

  // Keep the existing full-canvas visual baseline; initial open state is checked above.
  await page.locator("[data-rail-toggle]").click();
  for (const [name, viewport] of Object.entries(VIEWPORTS)) {
    await page.setViewportSize(viewport);
    await page.getByRole("button", { name: "Reset 3D view", exact: true }).click();
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
      // Narrow software-rendered WebGL varies slightly between Ubuntu runners.
      maxDiffPixelRatio: name === "narrow" ? 0.015 : 0.002
    });
  }

  expect(browserErrors).toEqual([]);
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
  await expect(page.getByRole("status")).toHaveText("Ready");
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
    new Set(["stress", "displacement", "reaction_force", "reaction_moment"])
  );
  expect(JSON.stringify(scene)).toContain("visualization_only_not_asme_code_stress");
});
