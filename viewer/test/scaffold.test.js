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
  assert.match(main, /import "\.\/app\.js"/);
  assert.match(css, /data-canvas/);
});

test("scaffold exposes one semantic engineering workflow shell", async () => {
  const html = await readViewerFile("index.html");
  const hooks = [
    "app-header",
    "status",
    "scene-title",
    "scene-meta",
    "report-link",
    "cockpit-status",
    "task-rail",
    "rail-toggle",
    "task-panel",
    "workflow-tabs",
    "workflow-panel",
    "viewer-workspace",
    "inspector",
    "evidence-dock",
    "evidence-expand",
    "evidence-tabs",
    "layer-list",
    "display-strip",
    "body-list",
    "projection-note",
    "section-profile",
    "discretisation-check",
    "coloring-bar",
    "viewport-legend",
    "body-legend",
    "saved-views",
    "result-controls",
    "result-legend",
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
  assert.match(html, /<section[^>]*class="cockpit-status"[^>]*aria-label="Engineering review status"[^>]*data-cockpit-status/);
  assert.match(html, /<section[^>]*class="viewer-workspace"[^>]*data-viewer-workspace/);
  assert.match(html, /<aside[^>]*class="cockpit-rail"[^>]*data-task-rail/);
  assert.match(html, /<button[^>]*aria-expanded="false"[^>]*aria-controls="review-controls"[^>]*data-rail-toggle/);
  assert.match(html, /<nav[^>]*aria-label="Engineering review tasks"[^>]*data-workflow-tabs/);
  assert.match(html, /<div[^>]*class="task-panel"[^>]*data-task-panel/);
  assert.match(html, /<aside[^>]*class="inspector"[^>]*data-inspector[^>]*hidden/);
  assert.match(html, /<section[^>]*class="evidence-dock"[^>]*aria-label="Engineering evidence"[^>]*data-evidence-dock/);
  assert.match(html, /<button[^>]*type="button"[^>]*aria-expanded="false"[^>]*data-evidence-expand/);
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

test("browser table orchestration uses text content and the workflow reducer", async () => {
  const app = await readViewerFile("src/app.js");

  assert.match(app, /workflowViewModel/);
  assert.match(app, /setAttribute\(["']aria-current["']/);
  assert.match(app, /addEventListener\(["']keydown["']/);
  assert.match(app, /workflowTabForKey/);
  assert.match(app, /\.textContent\s*=/);
  assert.doesNotMatch(app, /\.innerHTML\s*=/);
});

test("browser entry modules avoid literal Node imports", async () => {
  const sceneLoader = await readViewerFile("src/sceneLoader.js");

  assert.doesNotMatch(sceneLoader, /import\(["']node:/);
});
