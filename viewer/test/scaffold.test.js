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

test("browser entry modules avoid literal Node imports", async () => {
  const sceneLoader = await readViewerFile("src/sceneLoader.js");

  assert.doesNotMatch(sceneLoader, /import\(["']node:/);
});
