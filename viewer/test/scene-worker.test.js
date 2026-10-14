import assert from "node:assert/strict";
import test from "node:test";
import { Worker as NodeWorker } from "node:worker_threads";
import { Vector3 } from "three";
import { loadSceneBundleFromUrl } from "../src/sceneLoader.js";
import { packGeometryArrays, unpackGeometryArrays } from "../src/geometryTransfer.js";
import { validateJsonBudget, validateSceneBudget } from "../src/sceneBudget.js";
import { createThreeSceneGraph, applyVisualDeformationScale, disposeThreeSceneGraph } from "../src/renderer.js";

// Run the production browser worker through Node's real structured-clone and
// transfer boundary. Only the browser event API needs an adapter.
test("scene loading shares equal geometry arrays across the real worker boundary", async () => {
  const workers = [], packets = [];
  const originalWorker = globalThis.Worker;
  globalThis.Worker = class extends NodeWorker {
    constructor(url) {
      super(`const { parentPort } = require('node:worker_threads');
        globalThis.self = { postMessage: (value, transfer) => parentPort.postMessage(value, transfer) };
        import(${JSON.stringify(url.href)}).then(() => parentPort.on('message', data => self.onmessage({ data })));`, { eval: true });
      workers.push(this);
      this.on("message", data => { packets.push(data); this.onmessage?.({ data }); });
      this.on("error", error => this.onerror?.(error));
    }
  };
  const vertices = [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],
    [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]];
  const scene = { objects: [], overlays: [], geometry_assets: [
    { id: "cold", format: "mesh", generation_config: { vertices } },
    { id: "hot", format: "mesh", generation_config: { vertices, base_vertices: vertices } }
  ] };
  try {
    const bundle = await loadSceneBundleFromUrl("/bundle", async url =>
      url.endsWith("scene.json") ? new Response(JSON.stringify(scene)) :
        url.endsWith("object_map.json") ? new Response("{}") : new Response("", { status: 404 }));
    assert.deepEqual(bundle.scene, scene, "all geometry values and ordinary array shapes survive delivery");
    const [cold, hot] = bundle.geometryAssets.map(asset => asset.generation_config);
    assert.equal(cold.vertices, hot.vertices, "equal result-state geometry should be copied only once");
    assert.equal(cold.vertices, hot.base_vertices, "base geometry shares the same immutable source arrays");
    assert.equal(workers.length, 1);
    assert.ok(packets.some(packet => packet.geometryArrays?.buffer?.byteLength === 24 * 8),
      "one Float64 buffer carries the unique coordinates without changing precision");
  } finally {
    globalThis.Worker = originalWorker;
    await Promise.all(workers.map(worker => worker.terminate()));
  }
});

test("transferred coordinates retain Float64 precision, signed zero and array shape", () => {
  const precise = [Math.PI, -0, Number.MIN_VALUE, 1 / 3, -1e120, 1e120, 42, 0.123456789012345];
  const scene = { geometry_assets: [
    { generation_config: { vertex_values: [...precise], values: [...precise], vertices: precise.map(x => [x, 0, 1]) } },
    { generation_config: { vertex_values: precise.map(x => Object.is(x, -0) ? 0 : x) } }
  ] };
  const expected = structuredClone(scene);
  const packet = packGeometryArrays(scene);
  const received = structuredClone(packet, { transfer: [packet.geometryArrays.buffer] });
  assert.equal(packet.geometryArrays.buffer.byteLength, 0, "the buffer transfers ownership instead of copying");
  const restored = unpackGeometryArrays(received);
  assert.deepEqual(restored, expected);
  const [a, b] = restored.geometry_assets.map(asset => asset.generation_config);
  assert.equal(a.vertex_values, a.values);
  assert.notEqual(a.vertex_values, b.vertex_values, "positive and negative zero arrays remain distinct");
});

test("numeric transfer leaves irregular, mixed, short and unrelated arrays untouched", () => {
  const input = { generation_config: {
    vertices: [[1, 2], [3], [4, 5], [6], [7, 8], [9], [10, 11], [12]],
    faces: [1, 2, 3, 4, 5, 6, 7, "8"],
    vertex_values: [null, 1, 2, 3, 4, 5, 6, 7], points: [[0, 0, 0]],
    arbitrary: Array(8).fill(1), values: Array(8).fill(2)
  } };
  const expected = structuredClone(input);
  const untouched = { vertices: input.generation_config.vertices, faces: input.generation_config.faces,
    vertex_values: input.generation_config.vertex_values, points: input.generation_config.points,
    arbitrary: input.generation_config.arbitrary };
  const packet = packGeometryArrays(input);
  for (const [key, original] of Object.entries(untouched)) assert.equal(input.generation_config[key], original);
  assert.deepEqual(unpackGeometryArrays(structuredClone(packet)), expected);
  assert.deepEqual(packGeometryArrays({ unrelated: Array(8).fill(2) }), { value: { unrelated: Array(8).fill(2) } });
  assert.equal(unpackGeometryArrays({ value: null }), null);
});

test("sharing arrays preserves expanded JSON accounting and per-asset geometry costs", () => {
  const vertices = Array.from({ length: 8 }, (_, index) => [index, 0, 0]);
  const scene = { geometry_assets: [
    { id: "first", format: "mesh", generation_config: { vertices } },
    { id: "second", format: "mesh", generation_config: { vertices: structuredClone(vertices) } }
  ] };
  const before = { values: 0 };
  validateJsonBudget(scene, before);
  const expectedTotals = validateSceneBudget(scene);
  const restored = unpackGeometryArrays(structuredClone(packGeometryArrays(scene)));
  const after = { values: 0 };
  validateJsonBudget(restored, after);
  assert.deepEqual(after, before, "each logical occurrence retains its receiving cost");
  assert.deepEqual(validateSceneBudget(restored), expectedTotals);
  assert.equal(expectedTotals.points, 16);
});

test("the production worker rejects expanded duplicates before packing", async () => {
  const url = new URL("../src/sceneBudgetWorker.js", import.meta.url);
  const worker = new NodeWorker(`const { parentPort } = require('node:worker_threads');
    globalThis.self = { postMessage: (value, transfer) => parentPort.postMessage(value, transfer) };
    import(${JSON.stringify(url.href)}).then(() => parentPort.on('message', data => self.onmessage({ data })));`, { eval: true });
  const request = remaining => new Promise((resolve, reject) => {
    worker.once("message", resolve); worker.once("error", reject);
    worker.postMessage({ id: remaining, remaining, bytes: new TextEncoder().encode(
      '{"generation_config":{"values":[1,2,3,4,5,6,7,8],"vertex_values":[1,2,3,4,5,6,7,8]}}') });
  });
  try {
    const allowed = await request(20);
    assert.equal(allowed.values, 20);
    assert.ok(allowed.geometryArrays);
    const rejected = await request(19);
    assert.match(rejected.error, /values/);
    assert.equal(rejected.geometryArrays, undefined, "no oversized arrays are delivered");
  } finally { await worker.terminate(); }
});

test("signed-zero variants cannot cause quadratic fingerprint comparisons", () => {
  const scene = { geometry_assets: Array.from({ length: 500 }, (_, pattern) => ({
    generation_config: { vertex_values: Array.from({ length: 256 }, (_, index) =>
      index >= 247 && (pattern & (1 << (index - 247))) ? -0 : 0) }
  })) };
  const nativeIs = Object.is;
  let comparisons = 0;
  Object.is = (left, right) => { comparisons++; return nativeIs(left, right); };
  try { packGeometryArrays(scene); }
  finally { Object.is = nativeIs; }
  assert.ok(comparisons <= 500 * 256 * 2, `numeric comparisons must stay linear; observed ${comparisons}`);
});

test("deforming one rendered graph cannot mutate shared source arrays or another graph", () => {
  const base = [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],
    [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]];
  const config = { source: "tuba.deformed_analysis_mesh.solid", visual_scale: 4,
    base_vertices: base, vertices: base.map(([x, y, z]) => [x, y, z + 0.4]),
    faces: [[0, 1, 2, 3], [4, 5, 6, 7], [0, 1, 5, 4], [2, 3, 7, 6], [0, 3, 7, 4], [1, 2, 6, 5]] };
  const original = { geometry_assets: [
    { id: "a", format: "mesh", object_ids: ["a"], generation_config: structuredClone(config) },
    { id: "b", format: "mesh", object_ids: ["b"], generation_config: structuredClone(config) }
  ] };
  const scene = unpackGeometryArrays(structuredClone(packGeometryArrays(structuredClone(original))));
  assert.equal(scene.geometry_assets[0].generation_config.vertices, scene.geometry_assets[1].generation_config.vertices);
  const state = asset => ({ geometryAssets: [asset], visibleObjectIds: asset.object_ids, visualDeformationScale: 4 });
  const [a, b] = scene.geometry_assets;
  const graphA = createThreeSceneGraph(state(a)), graphB = createThreeSceneGraph(state(b));
  try {
    const positions = graph => {
      const mesh = graph.objectsByObjectId.values().next().value;
      return Array.from({ length: mesh.geometry.getAttribute("position").count }, (_, index) =>
        mesh.getVertexPosition(index, new Vector3()).toArray());
    };
    const initialA = positions(graphA).slice(), initialB = positions(graphB).slice();
    for (const scale of [0, 2, 8]) {
      applyVisualDeformationScale(graphA.root, { ...state(a), visualDeformationScale: scale });
      assert.notDeepEqual(positions(graphA), initialA, "display scale changes the rendered coordinates");
      assert.deepEqual(positions(graphB), initialB, "another graph retains its own coordinates");
      assert.deepEqual(scene, original, "shared source geometry remains unchanged at every scale");
    }
  } finally { disposeThreeSceneGraph(graphA); disposeThreeSceneGraph(graphB); }
});
