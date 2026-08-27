import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const VIEWPORTS = {
  desktop: { width: 1440, height: 900 },
  compact: { width: 1024, height: 768 },
  narrow: { width: 800, height: 900 }
};

const DOCUMENTATION_PAGES = ["/index.html", "/setup.html"];

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

  for (const [name, viewport] of Object.entries(VIEWPORTS)) {
    await page.setViewportSize(viewport);
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
