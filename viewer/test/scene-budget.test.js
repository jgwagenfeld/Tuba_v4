import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import { createThreeSceneGraph, disposeThreeSceneGraph } from "../src/renderer.js";
import { createViewerState, getVisibleObjectIds, loadSceneBundleFromUrl } from "../src/sceneLoader.js";
import { SCENE_LIMITS, readBoundedJson, textTextureSize, tubeTessellation, validateSceneBudget, validateJsonBudget } from "../src/sceneBudget.js";

test("JSON quotas count every primitive, nested array and repeated reference", () => {
  const budget = { values: 10 };
  const input = [1, null, [2, { x: 3 }], false];
  assert.equal(validateJsonBudget(input, budget), input);
  assert.equal(budget.values, 18);
  const shared = [1, 2];
  const repeated = { values: 0 };
  validateJsonBudget([shared, shared], repeated);
  assert.equal(repeated.values, 7, "JSON counts each occurrence, even when JS references are shared");
  validateJsonBudget(Array(10).fill(0), { values: SCENE_LIMITS.values - 11 });
  assert.throws(() => validateJsonBudget(Array(11).fill(0), { values: SCENE_LIMITS.values - 11 }), /values/);
});

test("primitive array fast paths still enforce depth and aggregate scene limits", () => {
  const nest = (value, depth) => { for (let i = 0; i < depth; i++) value = [value]; return value; };
  validateJsonBudget(nest(0, SCENE_LIMITS.depth));
  validateJsonBudget(nest([], SCENE_LIMITS.depth));
  assert.throws(() => validateJsonBudget(nest([0], SCENE_LIMITS.depth)), /depth/);
  assert.throws(() => validateSceneBudget({ scene: { nested: nest(0, SCENE_LIMITS.depth) } }, []), /depth/);
  const numbers = Array(SCENE_LIMITS.values - 5).fill(0);
  validateSceneBudget({ scene: { numbers } }, []);
  numbers.push(0);
  assert.throws(() => validateSceneBudget({ scene: { numbers } }, []), /values/);
});

test("oversized tubes and total generated surfaces reject before renderer construction", () => {
  const asset = { id: "tube", format: "tube", generation_config: { points: Array.from({ length: 257 }, () => [0, 0, 0]), radius_m: .1 } };
  assert.throws(() => createThreeSceneGraph({ geometryAssets: [asset] }), /tubePoints/);
  const config = { points: Array.from({ length: 160 }, (_, x) => [x, 0, 0]), radius_m: .1, inner_radius_m: .08, radial_segments: 48 };
  const outer = tubeTessellation({ ...config, inner_radius_m: 0 });
  const hollow = tubeTessellation(config);
  assert.ok(hollow.vertices > outer.vertices * 2, "inner skin and caps count toward allocation");
  assert.throws(() => validateSceneBudget({ geometryAssets: Array.from({ length: 6 }, (_, id) => ({ id, format: "tube", generation_config: config })) }), /generatedVertices|generatedFaces/);
});

test("stream limits cover declared size, chunked responses and aggregate bytes", async () => {
  await assert.rejects(readBoundedJson(new Response("{}", { headers: { "Content-Length": String(SCENE_LIMITS.responseBytes + 1) } })), /response bytes/);
  let cancelled = false;
  const chunk = new Uint8Array(1024 * 1024);
  const chunks = new ReadableStream({ start(controller) {
    for (let bytes = 0; bytes <= SCENE_LIMITS.responseBytes; bytes += chunk.length) controller.enqueue(chunk);
  }, cancel() { cancelled = true; } });
  await assert.rejects(readBoundedJson(new Response(chunks)), /response\/aggregate bytes/);
  assert.equal(cancelled, true);
  await assert.rejects(readBoundedJson(new Response("{}"), { bytes: SCENE_LIMITS.totalBytes }), /aggregate bytes/);
});

test("object, asset and external payload point totals cannot evade scene quotas", async () => {
  assert.throws(() => validateSceneBudget({ objects: Array(SCENE_LIMITS.objects + 1).fill({}) }), /objects/);
  assert.throws(() => validateSceneBudget({ geometryAssets: Array(SCENE_LIMITS.assets + 1).fill({}) }), /assets/);
  const points = Array(SCENE_LIMITS.points / 2 + 1).fill([0, 0, 0]);
  assert.throws(() => validateSceneBudget({ geometryPayloads: [{ generation_config: { points } }, { generation_config: { points: [...points] } }] }), /points/);
  const assets = [{ id: "tube", format: "tube", uri: "geometry/tube.json" }];
  await assert.rejects(loadSceneBundleFromUrl("/bundle", async (url) => new Response(JSON.stringify(
    url.endsWith("scene.json") ? { objects: [], overlays: [], geometry_assets: assets } :
      url.endsWith("tube.json") ? { asset_id: "tube", generation_config: { points: Array(257).fill([0, 0, 0]) } } : {}))), /tubePoints/);
});

test("ordinary generated review fixture passes with unchanged geometry", async () => {
  const root = new URL("./fixtures/code_aster_results/", import.meta.url);
  const bundle = await loadSceneBundleFromUrl(root.href.replace(/\/$/, ""), async (url) => {
    try { return new Response(await readFile(new URL(url))); }
    catch { return new Response("", { status: 404 }); }
  });
  assert.ok(validateSceneBudget(bundle).generatedVertices < SCENE_LIMITS.generatedVertices);
});

test("instanced subpoints budget shared geometry and per-instance buffers separately", () => {
  const count = 133056; // The existing hydrogen-plant review's real subpoint count.
  const totals = validateSceneBudget({ geometryAssets: [{ id: "subpoints", format: "tuyau_subpoint_glyphs",
    generation_config: { starts: Array(count).fill([0, 0, 0]), ends: Array(count).fill([0, 0, 1]), radial_segments: 16 }
  }] });
  assert.equal(totals.generatedVertices, 100 + count * 7);
  assert.equal(totals.generatedFaces, 64);
  const shared = { asset_id: "shared", generation_config: { starts: Array(Math.floor(SCENE_LIMITS.generatedInstances / 2) + 1).fill([0, 0, 0]) } };
  const sharedBundle = { geometryPayloads: [shared], geometryAssets: [
    { id: "shared", format: "tuyau_subpoint_glyphs" }, { id: "shared", format: "tuyau_subpoint_glyphs" }
  ] };
  assert.throws(() => validateSceneBudget(sharedBundle), /generatedInstances/);
  assert.throws(() => createThreeSceneGraph(sharedBundle), /generatedInstances/);
  assert.throws(() => validateSceneBudget({ geometryAssets: [{ id: "subpoints", format: "tuyau_subpoint_glyphs",
    generation_config: { starts: Array(SCENE_LIMITS.instances + 1).fill([0, 0, 0]), radial_segments: 16 }
  }] }), /instances/);
});

test("line-load arrows count as instances and generated geometry before rendering", () => {
  const config = { arrow_starts: [[0, 0, 0], [1, 0, 0]], arrow_ends: [[0, 0, 1], [1, 0, 1]], show_badge: false };
  const asset = { id: "comb", format: "line_load_comb", generation_config: config };
  const totals = validateSceneBudget({ geometryAssets: [asset] });
  assert.equal(totals.points, 4);
  assert.equal(totals.instances, 2);
  assert.equal(totals.generatedVertices, 1026);
  assert.equal(createThreeSceneGraph({ geometryAssets: [asset] }).renderedObjectCount, 1);
  const count = Math.floor(SCENE_LIMITS.generatedFaces / 512) + 1;
  const arrows = Array(count).fill([0, 0, 0]);
  assert.throws(() => createThreeSceneGraph({ geometryAssets: [{ ...asset, generation_config: {
    ...config, arrow_starts: arrows, arrow_ends: arrows, crest_points: arrows
  } }] }), /generatedVertices|generatedFaces/);
  assert.equal(validateSceneBudget({ geometryAssets: [{ ...asset, generation_config: {
    ...config, crest_points: Array(10).fill([0, 0, 0])
  } }] }).points, 14);
});

test("label strings and cumulative texture pixels reject before allocating canvases", () => {
  const asset = { id: "label", format: "label", generation_config: { text: "Review", position: [0, 0, 0], height: 1 } };
  let allocated = 0;
  const canvasFactory = () => { allocated++; return { width: 0, height: 0, getContext: () => ({
    measureText: text => ({ width: text.length * 32 }), fillRect() {}, fillText() {}
  }) }; };
  assert.equal(createThreeSceneGraph({ geometryAssets: [asset] }, { canvasFactory }).renderedObjectCount, 1);
  allocated = 0;
  const text = "x".repeat(SCENE_LIMITS.labelCharacters);
  const oversized = { ...asset, generation_config: { ...asset.generation_config, text: text + "x" } };
  assert.throws(() => createThreeSceneGraph({ geometryAssets: [oversized] }, { canvasFactory }), /labelCharacters/);
  const count = Math.floor(SCENE_LIMITS.texturePixels / textTextureSize(text).pixels) + 1;
  assert.throws(() => createThreeSceneGraph({ geometryAssets: Array.from({ length: count }, (_, id) => ({
    ...asset, id: `label:${id}`, generation_config: { ...asset.generation_config, text }
  })) }, { canvasFactory }), /texturePixels/);
  assert.equal(allocated, 0);
  assert.throws(() => validateSceneBudget({ geometryAssets: [{ id: "force", format: "vector",
    generation_config: { badge_text: text + "x" } }] }), /labelCharacters/);
});

test("actual text dimensions and generated badges cannot exceed the reserved pixel budget", () => {
  assert.throws(() => textTextureSize("Review", 10000), /reserved dimensions/);
  assert.throws(() => textTextureSize("Review", 100, 100, { pixels: SCENE_LIMITS.texturePixels - 1 }), /texturePixels/);
  const canvas = { width: 0, height: 0, getContext: () => ({ measureText: () => ({ width: 10000 }) }) };
  const graph = createThreeSceneGraph({ geometryAssets: [{ id: "label", format: "label",
    generation_config: { text: "Review", position: [0, 0, 0], height: 1 } }] }, { canvasFactory: () => canvas });
  assert.equal(graph.renderedObjectCount, 0);
  assert.match(graph.diagnostics[0].message, /reserved dimensions/);
  assert.equal(canvas.width, 0);
  assert.equal(canvas.height, 0);
});

test("hidden assets retain receiving and per-asset hard limits", () => {
  const hidden = (generation_config, format = "mesh") => ({ geometryAssets: [{
    id: "hidden", object_ids: ["hidden"], format, generation_config
  }], visibleObjectIds: [] });
  assert.throws(() => createThreeSceneGraph(hidden({ vertices: Array(SCENE_LIMITS.points + 1).fill([0, 0, 0]) })), /points/);
  assert.throws(() => createThreeSceneGraph(hidden({ starts: Array(SCENE_LIMITS.instances + 1).fill([0, 0, 0]) }, "tuyau_subpoint_glyphs")), /instances/);
  assert.throws(() => createThreeSceneGraph(hidden({ points: Array(257).fill([0, 0, 0]) }, "tube")), /tubePoints/);
  assert.throws(() => createThreeSceneGraph(hidden({ points: Array(171).fill([0, 0, 0]) }, "tube")), /tubularSegments/);
  assert.throws(() => createThreeSceneGraph(hidden({ text: "x".repeat(257) }, "label")), /labelCharacters/);
  assert.throws(() => createThreeSceneGraph(hidden({ badge_text: "x".repeat(257), show_badge: false }, "vector")), /labelCharacters/);
});

test("loading exclusive geometry states budgets only the renderer's selected allocation", async () => {
  const states = ["physical", "visual"];
  const scene = { scene_id: "exclusive", objects: states.map(id => ({
    id: `object:${id}`, kind: "element", metadata: { geometry_state_id: id }
  })), overlays: states.map(id => ({ id, kind: "geometry_state",
    data: { id, purpose: id === "physical" ? "engineering" : "visualization" }
  })), geometry_assets: states.map(id => ({ id, format: "polyline", object_ids: [`object:${id}`],
    generation_config: { geometry_state_id: id, points: Array.from({ length: Math.floor(SCENE_LIMITS.generatedVertices / (2 * 512)) + 1 }, (_, x) => [x, 0, 0]) }
  })) };
  const bundle = await loadSceneBundleFromUrl("/exclusive", async url => new Response(JSON.stringify(
    url.endsWith("scene.json") ? scene : {})));
  assert.throws(() => validateSceneBudget(bundle), /generatedVertices|generatedFaces/);
  const state = createViewerState(bundle);
  assert.equal(state.activeGeometryStateId, "physical");
  const physical = createThreeSceneGraph(state);
  assert.equal(physical.renderedObjectCount, 1);
  assert.ok(physical.objectsByObjectId.has("object:physical"));
  disposeThreeSceneGraph(physical);
  const next = { ...state, activeGeometryStateId: "visual" };
  next.visibleObjectIds = getVisibleObjectIds(next);
  const visual = createThreeSceneGraph(next);
  assert.equal(visual.renderedObjectCount, 1);
  assert.ok(visual.objectsByObjectId.has("object:visual"));
  disposeThreeSceneGraph(visual);
});

test("revealing hidden excessive textures rejects before the first canvas allocation", () => {
  const text = "x".repeat(SCENE_LIMITS.labelCharacters);
  const count = Math.floor(SCENE_LIMITS.texturePixels / textTextureSize(text).pixels) + 1;
  const state = { visibleObjectIds: [], geometryAssets: Array.from({ length: count }, (_, id) => ({
    id: `label:${id}`, format: "label", object_ids: [`object:${id}`],
    generation_config: { text, position: [id, 0, 0], height: 1 }
  })) };
  let canvases = 0;
  const options = { canvasFactory: () => { canvases++; } };
  const hidden = createThreeSceneGraph(state, options);
  assert.equal(hidden.renderedObjectCount, 0);
  disposeThreeSceneGraph(hidden);
  assert.throws(() => createThreeSceneGraph({ ...state,
    visibleObjectIds: state.geometryAssets.flatMap(asset => asset.object_ids)
  }, options), /texturePixels/);
  assert.equal(canvases, 0);
});
