import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";

const viewerRoot = new URL("..", import.meta.url);

async function readViewerFile(...parts) {
  return readFile(new URL(path.posix.join(...parts), viewerRoot), "utf8");
}

test("viewer exposes the Vite JavaScript scaffold commands", async () => {
  const packageJson = JSON.parse(await readViewerFile("package.json"));

  for (const scriptName of ["build", "dev", "e2e", "preview", "test"]) {
    assert.ok(packageJson.scripts[scriptName], `${scriptName} script is required`);
  }
  assert.match(packageJson.scripts.dev, /^vite\b/);
  assert.equal(packageJson.scripts.build, "vite build");
  assert.equal(packageJson.scripts.test, "node --test");
  assert.match(packageJson.scripts.preview, /^vite preview\b/);
  assert.match(packageJson.scripts.e2e, /^node scripts\/e2e-smoke\.mjs\b/);
  assert.ok(packageJson.dependencies?.three, "three dependency is required");
  assert.ok(packageJson.devDependencies?.["@playwright/test"], "playwright test dependency is required");
  assert.ok(packageJson.devDependencies?.vite, "vite dependency is required");
  assert.equal(packageJson.devDependencies?.typescript, undefined);
});

test("viewer has one Vite JavaScript config", async () => {
  const viteConfig = await readViewerFile("vite.config.js");

  assert.match(viteConfig, /defineConfig/);
  assert.match(viteConfig, /chunkSizeWarningLimit:\s*1024/);
  await assert.rejects(readViewerFile("tsconfig.json"), { code: "ENOENT" });
});

test("viewer app enters through JavaScript and owns CSS layout", async () => {
  const html = await readViewerFile("index.html");
  const main = await readViewerFile("src/main.js");
  const css = await readViewerFile("src/styles.css");

  assert.match(html, /\/src\/main\.js/);
  assert.doesNotMatch(html, /<style>/);
  assert.match(main, /import "\.\/styles\.css"/);
  assert.match(css, /data-canvas/);
});

// The landing gallery and the review are two front doors, and they were bundled
// as one. main.js used to statically import app.js, which statically imports
// renderer.js, which statically imports three - so three.core.js (2.08 MB) was a
// hard boot dependency of a page that never creates a WebGL context. Measured on
// the published gallery: 74.4% of its transfer, to draw thirteen photographs.
//
// This asserts the fix at the only place it can be asserted without a browser:
// the studio must be reached by a dynamic import, and nothing in the gallery's
// own import graph may reach three.
test("the gallery path does not bundle the renderer or three", async () => {
  const main = await readViewerFile("src/main.js");
  const gallery = await readViewerFile("src/gallery.js");
  const app = await readViewerFile("src/app.js");
  const renderer = await readViewerFile("src/renderer.js");

  // main.js loads the studio, but only on the branch that wants a review.
  assert.doesNotMatch(main, /^import .*"\.\/app\.js";$/m);
  assert.match(main, /await import\("\.\/app\.js"\)/);
  // And it must read the catalog before that import, or the decision to load
  // the studio is made after the studio is already on the wire.
  assert.ok(
    main.indexOf("bundles.json") < main.indexOf('await import("./app.js")'),
    "the catalog must be read before the studio is imported"
  );

  // gallery.js is what the landing page imports. It must not reach three, and
  // it must not reach the renderer.
  assert.doesNotMatch(gallery, /from "\.\/renderer\.js"/);
  assert.doesNotMatch(gallery, /from "three/);
  // exchange.js is imported by gallery.js for publishedDownloads, so it has to
  // be light too - it is the only thing gallery.js pulls in besides itself.
  const exchange = await readViewerFile("src/exchange.js");
  assert.doesNotMatch(exchange, /from "three/);
  assert.doesNotMatch(exchange, /from "\.\/renderer\.js"/);

  // Sanity: the studio really does need three, or the dynamic import buys
  // nothing and the assertion above is passing for the wrong reason.
  assert.match(renderer, /from "three/);
  assert.match(app, /from "\.\/renderer\.js"/);
});

test("scaffold exposes one semantic engineering workflow shell", async () => {
  const html = await readViewerFile("index.html");
  const hooks = [
    "app-header",
    "runtime-status",
    "scene-title",
    "scene-meta",
    "report-link",
    "status-chip",
    "status-strip",
    "solver-fact",
    "selection-fact",
    "strip-units",
    "task-rail",
    "rail-toggle",
    "viewer-workspace",
    "inspector",
    "layer-list",
    "display-strip",
    "body-list",
    "color-by",
    "projection-note",
    "section-profile",
    "discretisation-check",
    "viewport-legend",
    "body-legend",
    "body-legend-toggle",
    "saved-views",
    "result-controls",
    "field-details",
    "field-description",
    "analysis-details",
    "analysis-summary",
    "hotspot-list",
    "issue-list",
    "search",
    "object-list",
    "bodies-pane",
    "find-pane",
    "find-scope",
    "find-dismiss",
    "rail-utility",
    "rail-popover",
    "property-actions",
    "properties",
    "canvas",
    "diagnostic-list"
  ];

  assert.match(html, /<main[^>]*class="app-shell"[^>]*data-embed="false"/);
  assert.match(html, /<button[^>]*type="button"[^>]*class="status-chip"[^>]*data-status-chip[^>]*hidden/);
  // The session line is the shell's third row, after the workspace - not a
  // floating panel inside the viewport and not another header band.
  assert.match(html, /<\/section>\s*(?:<!--[\s\S]*?-->\s*)*<footer[^>]*class="status-strip"[^>]*data-status-strip/);
  // The verdict, the unit chip and the runtime line live there, not in the
  // header and not in the rail foot, so every mode keeps all three.
  assert.match(html, /data-status-strip[\s\S]*?data-status-chip[\s\S]*?data-discretisation-check[\s\S]*?data-strip-units[\s\S]*?data-runtime-status[\s\S]*?<\/footer>/);
  const headerActions = html.slice(html.indexOf('class="header-actions"'), html.indexOf("</header>"));
  assert.doesNotMatch(headerActions, /data-(?:status-chip|runtime-status)/);
  assert.match(html, /<section[^>]*class="viewer-workspace"[^>]*data-viewer-workspace/);
  assert.match(html, /<aside[^>]*class="cockpit-rail"[^>]*data-task-rail/);
  assert.match(html, /<button[^>]*aria-expanded="true"[^>]*aria-controls="review-controls"[^>]*data-rail-toggle/);
  // The rail is one column: no tab strip and no swapped task panel. The pinned
  // "Colour by" control and the issue list are its sections.
  assert.doesNotMatch(html, /data-workflow-tabs|data-task-panel/);
  assert.match(html, /<div[^>]*data-color-block[\s\S]*?data-color-by/);
  assert.match(html, /data-layers-block[\s\S]*?data-issue-list/);
  assert.match(html, /<aside[^>]*class="inspector"[^>]*data-inspector[^>]*hidden/);
  assert.doesNotMatch(html, /class="[^"]*\bworkflow-tabs\b/);
  // All layers stays a disclosure; it is a secondary tool inside the rail popover.
  assert.match(html, /<details[^>]*>[\s\S]*?data-layer-list(?:=|[\s>])[\s\S]*?<\/details>/);
  // The object list is no longer buried in a collapsed disclosure that the search
  // field could not open. It lives in the find pane, which is present in the DOM
  // at all times so its content stays readable and testable.
  assert.match(html, /data-find-pane[\s\S]*?data-object-list/);
  assert.doesNotMatch(html, /data-tree(?:=|[\s>])/);
  assert.match(html, /<canvas[^>]*data-canvas[^>]*tabindex="0"[^>]*aria-label="Interactive 3D engineering review viewport"/);
  assert.match(html, /<div[^>]*data-section-box-controls[^>]*><\/div>/);
  assert.match(
    html,
    /<div[^>]*class="camera-controls"[^>]*role="group"[^>]*aria-label="Standard camera views"[^>]*data-camera-controls[^>]*><\/div>/
  );
  assert.match(
    html,
    /<p[^>]*data-viewport-guidance[^>]*>[^<]*Orbit[^<]*Zoom[^<]*Select[^<]*axes[^<]*reset[^<]*<\/p>/i
  );
  assert.match(html, /<button[^>]*data-reset-view[^>]*aria-label="Reset 3D view"/);
  assert.match(html, /<input[^>]*type="search"[^>]*data-search[^>]*aria-label="Search objects"/);
  for (const hook of hooks) {
    assert.equal((html.match(new RegExp(`data-${hook}(?:=|[\\s>])`, "g")) ?? []).length, 1, `data-${hook} must occur once`);
  }
});

test("browser entry modules avoid literal Node imports", async () => {
  const sceneLoader = await readViewerFile("src/sceneLoader.js");

  assert.doesNotMatch(sceneLoader, /import\(["']node:/);
});
