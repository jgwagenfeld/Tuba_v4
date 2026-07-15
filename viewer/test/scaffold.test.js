import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";

const viewerRoot = new URL("..", import.meta.url);

async function readViewerFile(...parts) {
  return readFile(new URL(path.posix.join(...parts), viewerRoot), "utf8");
}

test("viewer exposes the Vite TypeScript scaffold commands", async () => {
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
  assert.ok(packageJson.devDependencies?.typescript, "typescript dependency is required");
});

test("viewer has Vite and TypeScript config files", async () => {
  const viteConfig = await readViewerFile("vite.config.ts");
  const tsConfig = JSON.parse(await readViewerFile("tsconfig.json"));

  assert.match(viteConfig, /defineConfig/);
  assert.match(viteConfig, /chunkSizeWarningLimit:\s*1024/);
  assert.equal(tsConfig.compilerOptions.moduleResolution, "Bundler");
  assert.ok(tsConfig.include.includes("src/**/*.ts"));
});

test("viewer app enters through TypeScript and owns CSS layout", async () => {
  const html = await readViewerFile("index.html");
  const main = await readViewerFile("src/main.ts");
  const css = await readViewerFile("src/styles.css");

  assert.match(html, /\/src\/main\.ts/);
  assert.doesNotMatch(html, /<style>/);
  assert.match(main, /import "\.\/styles\.css"/);
  assert.match(main, /import "\.\/app\.js"/);
  assert.match(css, /data-canvas/);
});

test("scaffold exposes one semantic engineering workflow shell", async () => {
  const html = await readViewerFile("index.html");
  const hooks = [
    "status",
    "scene-title",
    "scene-meta",
    "workflow-tabs",
    "workflow-panel",
    "viewer-workspace",
    "3d-heading",
    "scene-tools",
    "layer-list",
    "overlay-list",
    "result-controls",
    "result-legend",
    "hotspot-list",
    "tree",
    "issue-list",
    "search",
    "object-list",
    "property-actions",
    "properties",
    "canvas",
    "diagnostic-list"
  ];

  assert.match(html, /<main[^>]*class="app-shell"[^>]*data-embed="false"/);
  assert.match(html, /<nav[^>]*role="tablist"[^>]*aria-label="Engineering review"[^>]*data-workflow-tabs/);
  assert.match(html, /<section[^>]*id="engineering-workflow-panel"[^>]*role="tabpanel"[^>]*tabindex="0"[^>]*data-workflow-panel/);
  assert.match(html, /<section[^>]*id="engineering-3d-panel"[^>]*class="viewer-workspace"[^>]*role="tabpanel"[^>]*aria-labelledby="workflow-tab-3d"[^>]*tabindex="0"[^>]*data-viewer-workspace[^>]*hidden/);
  assert.equal((html.match(/<h1[^>]*class="visually-hidden"[^>]*data-3d-heading[^>]*>3D Engineering Review<\/h1>/g) ?? []).length, 1);
  assert.match(html, /<canvas[^>]*data-canvas[^>]*tabindex="0"[^>]*aria-label="Interactive 3D engineering review viewport"/);
  assert.match(html, /<input[^>]*type="search"[^>]*data-search[^>]*aria-label="Search objects"/);
  for (const hook of hooks) {
    assert.equal((html.match(new RegExp(`data-${hook}(?:=|[\\s>])`, "g")) ?? []).length, 1, `data-${hook} must occur once`);
  }
});

test("browser table orchestration uses text content and the workflow reducer", async () => {
  const app = await readViewerFile("src/app.js");

  assert.match(app, /workflowViewModel/);
  assert.match(app, /type:\s*["']setWorkflowTab["']/);
  assert.match(app, /setAttribute\(["']aria-selected["']/);
  assert.match(app, /addEventListener\(["']keydown["']/);
  assert.match(app, /workflowTabForKey/);
  assert.match(app, /\.textContent\s*=/);
  assert.doesNotMatch(app, /\.innerHTML\s*=/);
});

test("browser entry modules avoid literal Node imports", async () => {
  const sceneLoader = await readViewerFile("src/sceneLoader.js");

  assert.doesNotMatch(sceneLoader, /import\(["']node:/);
});
