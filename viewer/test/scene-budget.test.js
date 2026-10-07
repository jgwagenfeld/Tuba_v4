import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import { createThreeSceneGraph } from "../src/renderer.js";
import { loadSceneBundleFromUrl } from "../src/sceneLoader.js";
import { SCENE_LIMITS, readBoundedJson, tubeTessellation, validateSceneBudget } from "../src/sceneBudget.js";

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
  const chunks = new ReadableStream({ start(controller) { controller.enqueue(new Uint8Array(SCENE_LIMITS.responseBytes + 1)); }, cancel() { cancelled = true; } });
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
