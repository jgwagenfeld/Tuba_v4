// Renderer baseline: what a real review bundle actually costs.
//
// The renderer refused to guess at this. `renderer.js` carries a note from an
// earlier attempt at a detail LOD: it was removed because it emptied the
// viewport of the analysis mesh, and the note ends "if orbit ever does judder,
// measure first and thin the thing that is actually slow." This is the
// measurement that note is waiting for, run against a real solved bundle rather
// than a synthetic one.
//
// It reports what loading a bundle costs, what building the scene graph costs,
// and what a frame and an orbit cost to draw, then checks the result against a
// budget declared below. The numbers go to `viewer/.benchmarks/` as a working
// artifact and are not committed; the budget is, because a budget is a decision
// and a measurement is not.
//
//   node scripts/perf-baseline.mjs <bundle-directory>
//
// The bundle is a directory a review was written to. `scripts/build_pages.py`
// and the example studies produce them; a quick one is
// `python -m pytest tests/test_visualization_web_export.py` to build into .build.

import { createServer } from "vite";
import { chromium } from "@playwright/test";
import { writeFileSync, mkdirSync } from "node:fs";
import { dirname, isAbsolute, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const VIEWER_ROOT = resolve(HERE, "..");
const REPO_ROOT = resolve(VIEWER_ROOT, "..");
const OUT = resolve(VIEWER_ROOT, ".benchmarks");

// What we are willing to pay per frame on the reference machine. Ceilings for a
// regression, not targets: the question this answers is "did a change make
// drawing this bundle slower", not "is drawing it fast".
//
// Both sub-point display modes are measured per bundle. Peak mode is the
// default and thins the field to a fraction of its points, so measuring only
// the default would hide the cost of the mode a reviewer switches to when they
// want the whole field. The ceiling has to cover the more expensive of the two.
const BUDGET = {
  frame_ms: 33,          // a full repaint of the scene, at 30 fps
  orbit_ms: 22,          // a drag, which is the motion a reviewer feels
  draw_calls: 2500,
  // The glyph batch is one draw call whatever its instance count, so triangles
  // are its meaningful ceiling.
  triangles: 2_000_000,
  graph_build_ms: 4000,  // the one-time cost of opening a bundle
  load_ms: 20_000
};

const bundleArg = process.argv[2];
if (!bundleArg) {
  console.error("usage: node scripts/perf-baseline.mjs <bundle-directory>");
  process.exit(2);
}
const bundleDir = resolve(bundleArg);
const bundleRelative = relative(REPO_ROOT, bundleDir);
if (bundleRelative.startsWith("..") || isAbsolute(bundleRelative)) {
  console.error(
    `the bundle must be inside the checkout so vite can serve it: ${bundleDir}\n` +
    `Build one with a study's build_review, e.g. into .build/perf-bundle/review_scene.`
  );
  process.exit(2);
}

// Served from the repo root rather than `viewer/`, so a bundle built anywhere in
// the checkout is reachable at a plain URL. `three` still resolves, because
// vite walks up from the importing file and the modules live under `viewer/`.
const server = await createServer({
  root: REPO_ROOT,
  logLevel: "error",
  server: { host: "127.0.0.1", port: 4198, strictPort: true },
  fs: { allow: [REPO_ROOT] }
});
await server.listen();

mkdirSync(OUT, { recursive: true });
const pageFile = resolve(OUT, "measure.html");
writeFileSync(pageFile, measurePage(), "utf8");

const browser = await chromium.launch({ channel: "chromium", timeout: 60_000 });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const pageErrors = [];
// The measurement page has no favicon and the dev server has no icon route, so
// that 404 arrives on every run. Two handlers cover it: `response` names the
// URL and can filter it, while the browser's own console message for a failed
// resource carries no URL at all, so anything that looks like a bare resource
// failure is left to `response` to report with enough detail to act on.
const isNoise = (text) => /favicon/i.test(text);
const isUnattributedResourceError = (text) => /failed to load resource/i.test(text);
page.on("pageerror", (error) => pageErrors.push(String(error)));
page.on("console", (message) => {
  if (message.type() !== "error") return;
  if (isNoise(message.text()) || isUnattributedResourceError(message.text())) return;
  pageErrors.push(message.text());
});
page.on("requestfailed", (request) => {
  if (!isNoise(request.url())) pageErrors.push(`request failed: ${request.url()}`);
});
page.on("response", (response) => {
  if (response.status() >= 400 && !isNoise(response.url())) {
    pageErrors.push(`${response.status()} ${response.url()}`);
  }
});

const bundleUrl = `/${bundleRelative.replace(/\\/g, "/")}`;
const url = `http://127.0.0.1:4198/viewer/.benchmarks/measure.html`;
await page.goto(url, { waitUntil: "load" });
try {
  await page.waitForFunction(() => typeof window.__measure === "function", null, { timeout: 30_000 });
} catch (error) {
  console.error(`the measurement page never became ready (${bundleUrl})`);
  console.error(pageErrors.length ? `page errors:\n  ${pageErrors.join("\n  ")}` : "  no page errors");
  await browser.close();
  await server.close();
  process.exit(2);
}

let result;
try {
  result = await page.evaluate((target) => window.__measure(target), bundleUrl);
} catch (error) {
  console.error(`measurement failed: ${error.message}`);
  console.error(pageErrors.length ? `page errors:\n  ${pageErrors.join("\n  ")}` : "");
  await browser.close();
  await server.close();
  process.exit(2);
}
result.pageErrors = pageErrors;

await browser.close();
await server.close();

const report = { measured_at: new Date().toISOString(), bundle: bundleArg, budget: BUDGET, ...result };
writeFileSync(resolve(OUT, "perf-baseline.json"), JSON.stringify(report, null, 2), "utf8");

const ms = (value) => `${value.toFixed(1)} ms`;
const rows = [
  ["bundle load", ms(result.load_ms)],
  ["viewer state", ms(result.state_ms)],
  ["assets / objects", `${result.asset_count} / ${result.object_count}`]
];
const width = Math.max(...rows.map(([label]) => label.length), 28);
console.log(`\nbundle  ${bundleArg}`);
console.log(`gpu     ${result.gpu}\n`);
for (const [label, value] of rows) {
  console.log(`  ${label.padEnd(width)}  ${value}`);
}

const breaches = [];
for (const [mode, m] of Object.entries(result.modes)) {
  console.log(`\n  sub-point mode: ${mode}`);
  for (const [label, value] of [
    ["scene graph build", ms(m.graph_build_ms)],
    ["frame median / p95 / max", `${ms(m.still_frame.median)} / ${ms(m.still_frame.p95)} / ${ms(m.still_frame.max)}`],
    ["orbit median / p95 / max", `${ms(m.orbit.median)} / ${ms(m.orbit.p95)} / ${ms(m.orbit.max)}`],
    ["draw calls", m.draw_calls.toLocaleString("en-US")],
    // Draw calls per object is the number that decides whether batching the pipe
    // shells is worth the regression risk in picking and morph targets, because
    // it is the rate a bigger model will keep paying. Report the rate, not just
    // the total, so a small bundle still says something about a large one.
    ["draw calls per object", (m.draw_calls / Math.max(m.rendered_objects, 1)).toFixed(2)],
    ["triangles", m.triangles.toLocaleString("en-US")],
    ["geometries / textures / programs", `${m.geometries} / ${m.textures} / ${m.programs}`],
    ["rendered objects", m.rendered_objects.toLocaleString("en-US")],
    ["sub-point instances drawn", m.subpoint_instances.toLocaleString("en-US")],
    ["renderer diagnostics", String(m.diagnostics)]
  ]) {
    console.log(`    ${label.padEnd(width)}  ${value}`);
  }
  for (const [label, value, limit] of [
    ["frame median", m.still_frame.median, BUDGET.frame_ms],
    ["orbit median", m.orbit.median, BUDGET.orbit_ms],
    ["draw calls", m.draw_calls, BUDGET.draw_calls],
    ["triangles", m.triangles, BUDGET.triangles],
    ["graph build", m.graph_build_ms, BUDGET.graph_build_ms]
  ]) {
    if (value > limit) breaches.push([`${mode} ${label}`, value, limit]);
  }
}
if (result.load_ms > BUDGET.load_ms) {
  breaches.push(["bundle load", result.load_ms, BUDGET.load_ms]);
}
console.log(`\nreport  ${resolve(OUT, "perf-baseline.json")}`);

const diagnostics = Object.values(result.modes).reduce((total, m) => total + m.diagnostics, 0);
if (diagnostics > 0) {
  console.error(`\nthe scene reported ${diagnostics} renderer diagnostics`);
}
if (breaches.length > 0) {
  console.error("\nover budget:");
  for (const [label, value, limit] of breaches) {
    console.error(`  ${label}: ${value.toFixed?.(1) ?? value} > ${limit}`);
  }
}
if (pageErrors.length > 0) {
  console.error(`\npage errors:\n  ${pageErrors.join("\n  ")}`);
}
process.exit(breaches.length > 0 || diagnostics > 0 || pageErrors.length > 0 ? 1 : 0);

// Generated, not committed: a thin shell that hands the studio's own loader and
// renderer to the harness. It must go through `loadSceneBundleFromUrl` and
// `createThreeSceneGraph` rather than assembling a scene itself, or the numbers
// would be measuring the harness.
function measurePage() {
  return `<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>perf baseline</title>
<style>body{margin:0;background:#0f1417;color:#dfe6e8;font:12px ui-monospace,monospace;padding:8px}</style>
</head><body><pre id="log">measuring…</pre>
<script type="module">
const log = document.getElementById("log");

async function measure(bundleUrl) {
  const THREE = await import("three");
  const { loadSceneBundleFromUrl, createViewerState, getVisibleObjectIds } = await import("/viewer/src/sceneLoader.js");
  const { createThreeSceneGraph } = await import("/viewer/src/renderer.js");

  const mark = () => performance.now();
  let t = mark();
  const bundle = await loadSceneBundleFromUrl(bundleUrl);
  const load_ms = mark() - t;

  t = mark();
  const base = createViewerState(bundle);
  const visibleObjectIds = getVisibleObjectIds(base);
  const state_ms = mark() - t;
  log.textContent = "loaded; building graphs…";
  await new Promise((done) => setTimeout(done, 0));

  // Every sub-point display mode is a separate scene graph, because the mode
  // changes what is drawn, not just how it is filtered after the fact. Peak
  // mode is the default and thins the field; measured mode draws all of it.
  const modes = ["peak", "measured"];
  const scenes = {};
  for (const mode of modes) {
    t = mark();
    const state = { ...base, subpointMode: mode, visibleObjectIds };
    scenes[mode] = {
      graph: createThreeSceneGraph(state, { backgroundColor: 0xf8fafc }),
      graph_build_ms: mark() - t
    };
  }

  const canvas = document.createElement("canvas");
  canvas.width = 1440;
  canvas.height = 900;
  document.body.append(canvas);
  const gl = new THREE.WebGLRenderer({ canvas, antialias: true });
  gl.setSize(1440, 900, false);
  gl.setPixelRatio(1);

  const camera = new THREE.PerspectiveCamera(45, 1440 / 900, 0.05, 20_000);
  const b = scenes[modes[0]].graph.bounds ?? [0, 0, 0, 10, 10, 10];
  const center = [(b[0] + b[3]) / 2, (b[1] + b[4]) / 2, (b[2] + b[5]) / 2];
  const radius = Math.hypot(b[3] - b[0], b[4] - b[1], b[5] - b[2]) / 2 || 1;
  const frame = (angle) => {
    camera.position.set(
      center[0] + Math.cos(angle) * radius * 1.3,
      center[1] + radius * 0.55,
      center[2] + Math.sin(angle) * radius * 1.3
    );
    camera.lookAt(...center);
  };

  // The scene is rebuilt per mode because a WebGLRenderer holds one scene at a
  // time; the buffers of the previous mode have to be released or the counts
  // below are a running total rather than a single frame's cost.
  function drawMode(mode) {
    const graph = scenes[mode].graph;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf8fafc);
    scene.add(graph.scene);
    scene.add(new THREE.AmbientLight(0xffffff, 2.0));
    const key = new THREE.DirectionalLight(0xffffff, 1.2);
    key.position.set(3, 4, 5);
    scene.add(key);
    frame(0.6);

    const samples = (count, orbit) => {
      const times = [];
      for (let i = 0; i < count; i += 1) {
        if (orbit) frame((i / count) * Math.PI * 0.6);
        const start = performance.now();
        gl.render(scene, camera);
        times.push(performance.now() - start);
      }
      times.sort((a, b) => a - b);
      return {
        // Median, not mean: shader compilation and the first frame are one-off
        // costs that would drag a mean away from what an orbit feels like.
        median: times[Math.floor(times.length / 2)],
        p95: times[Math.floor(times.length * 0.95)],
        max: times[times.length - 1]
      };
    };

    // One throwaway frame, so shader compilation is not billed to the first
    // sample: it is a real cost but a one-off, and the budget is about the
    // steady state a reviewer actually drags through.
    gl.render(scene, camera);
    const still_frame = samples(30, false);
    const orbit = samples(60, true);

    let subpoint_instances = 0;
    for (const object of graph.objectsByObjectId.values()) {
      if (object.isInstancedMesh) subpoint_instances += object.count;
    }
    const measured = {
      graph_build_ms: scenes[mode].graph_build_ms,
      still_frame,
      orbit,
      draw_calls: gl.info.render.calls,
      triangles: gl.info.render.triangles,
      // Read before this mode's buffers are released below, or the counts are
      // whatever the last dispose left behind rather than what was drawn.
      geometries: gl.info.memory.geometries,
      textures: gl.info.memory.textures,
      programs: gl.info.programs?.length ?? null,
      rendered_objects: graph.renderedObjectCount,
      subpoint_instances,
      diagnostics: graph.diagnostics?.length ?? 0
    };
    // Release this mode's buffers before the next one is measured.
    graph.scene.traverse((object) => {
      object.geometry?.dispose?.();
      if (Array.isArray(object.material)) object.material.forEach((m) => m.dispose?.());
      else object.material?.dispose?.();
    });
    gl.renderLists.dispose();
    return measured;
  }

  const byMode = {};
  for (const mode of modes) {
    byMode[mode] = drawMode(mode);
  }

  const context = gl.getContext();
  const debug = context.getExtension("WEBGL_debug_renderer_info");
  return {
    load_ms,
    state_ms,
    modes: byMode,
    asset_count: (bundle.geometryAssets ?? []).length,
    object_count: (bundle.objects ?? []).length,
    gpu: debug ? context.getParameter(debug.UNMASKED_RENDERER_WEBGL) : "unknown"
  };
}

window.__measure = measure;
log.textContent = "ready";
</script></body></html>`;
}
