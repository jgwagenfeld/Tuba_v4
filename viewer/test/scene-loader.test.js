import assert from "node:assert/strict";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import {
  createViewerState,
  loadSceneBundle,
  loadSceneBundleFromUrl,
  setLayerVisibility
} from "../src/sceneLoader.js";

async function createFixtureBundle() {
  const root = join(tmpdir(), `tuba-viewer-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  await mkdir(join(root, "metadata"), { recursive: true });
  await mkdir(join(root, "geometry"), { recursive: true });
  const scene = {
    schema_version: "visualization.scene.v1",
    scene_id: "scene_001",
    model_id: "model_001",
    units: { length: "m" },
    coordinate_system: { up_axis: "Z" },
    objects: [
      {
        id: "object:element:pipe_0",
        entity_ref: "element:pipe_0",
        kind: "pipe",
        name: "P-100",
        geometry_asset_id: "geometry:element:pipe_0",
        metadata: { section: "PipeSec" }
      }
    ],
    geometry_assets: [
      {
        id: "geometry:element:pipe_0",
        format: "tube",
        uri: "geometry/geometry_element_pipe_0.json",
        bounds: [0, -0.1, -0.1, 1, 0.1, 0.1],
        object_ids: ["object:element:pipe_0"],
        generation_config: { entity_ref: "element:pipe_0", points: [[0, 0, 0], [1, 0, 0]] }
      }
    ],
    materials: [],
    styles: [],
    overlays: [],
    issues: [],
    route_reviews: [],
    agent_proposals: [],
    views: [],
    scene_diffs: [],
    diagnostics: []
  };
  await writeFile(join(root, "scene.json"), JSON.stringify(scene), "utf8");
  await writeFile(join(root, "metadata", "objects.json"), JSON.stringify(scene.objects), "utf8");
  await writeFile(join(root, "metadata", "object_map.json"), JSON.stringify({ "object:element:pipe_0": { entity_ref: "element:pipe_0" } }), "utf8");
  await writeFile(join(root, "metadata", "overlays.json"), "[]", "utf8");
  await writeFile(join(root, "geometry", "geometry_assets.json"), JSON.stringify(scene.geometry_assets), "utf8");
  await writeFile(join(root, "geometry", "geometry_element_pipe_0.json"), JSON.stringify({
    asset_id: "geometry:element:pipe_0",
    object_ids: ["object:element:pipe_0"],
    generation_config: { entity_ref: "element:pipe_0" }
  }), "utf8");
  return root;
}

test("loads scene bundle files and geometry payloads", async () => {
  const bundle = await loadSceneBundle(await createFixtureBundle());

  assert.equal(bundle.scene.scene_id, "scene_001");
  assert.equal(bundle.objects.length, 1);
  assert.equal(bundle.geometryPayloads.length, 1);
  assert.equal(bundle.geometryPayloads[0].asset_id, "geometry:element:pipe_0");
});

test("creates viewer state with visible layers and scene bounds", async () => {
  const bundle = await loadSceneBundle(await createFixtureBundle());

  const state = createViewerState(bundle);

  assert.deepEqual(state.bounds, [0, -0.1, -0.1, 1, 0.1, 0.1]);
  assert.equal(state.objectMap, bundle.objectMap);
  assert.equal(state.layers.pipe.visible, true);
  assert.deepEqual(state.visibleObjectIds, ["object:element:pipe_0"]);
});

test("loads scene files before the optional review and exposes review state", async () => {
  const fixtureRoot = new URL("./fixtures/code_aster_results/", import.meta.url);
  const fixturePaths = [
    "scene.json",
    "metadata/objects.json",
    "metadata/object_map.json",
    "metadata/overlays.json",
    "geometry/geometry_assets.json",
    "review.json"
  ];
  const fixtureFiles = Object.fromEntries(
    await Promise.all(
      fixturePaths.map(async (path) => [path, await readFile(new URL(path, fixtureRoot), "utf8")])
    )
  );
  const requestedUrls = [];
  const fetcher = async (url) => {
    requestedUrls.push(url);
    const relativePath = url.replace(/^\/bundle\//, "");
    return relativePath in fixtureFiles
      ? new Response(fixtureFiles[relativePath], { status: 200 })
      : new Response("", { status: 404 });
  };

  const bundle = await loadSceneBundleFromUrl("/bundle", fetcher);
  const state = createViewerState(bundle);

  assert.equal(requestedUrls.at(-1), "/bundle/review.json");
  assert.equal(bundle.review.analysis_status, "solved");
  assert.deepEqual(bundle.reviewDiagnostics, []);
  assert.equal(bundle.legacyReview, false);
  assert.equal(state.review, bundle.review);
  assert.deepEqual(state.reviewDiagnostics, []);
  assert.equal(state.legacyReview, false);
  assert.equal(state.sceneId, "scene:code_aster_results");
  assert.equal(state.activeLoadCase, "Hot");
});

test("reports the requested URL when a scene JSON request receives HTML", async () => {
  const fetcher = async () =>
    new Response("<!doctype html><title>Wrong application</title>", {
      status: 200,
      headers: { "content-type": "text/html; charset=utf-8" }
    });

  await assert.rejects(
    loadSceneBundleFromUrl("http://127.0.0.1:5173/code-aster-review", fetcher),
    /Expected JSON from http:\/\/127\.0\.0\.1:5173\/code-aster-review\/scene\.json, but received text\/html.*different application or server/s
  );
});

test("starts URL geometry requests concurrently and preserves asset order", async () => {
  const assets = ["geometry:first", "geometry:second", "geometry:third"].map((id) => ({
    id,
    uri: `${id.replace(":", "_")}.json`
  }));
  const basePayloads = {
    "scene.json": { schema_version: "visualization.scene.v1", scene_id: "concurrent", geometry_assets: assets },
    "metadata/objects.json": [],
    "metadata/object_map.json": {},
    "metadata/overlays.json": [],
    "geometry/geometry_assets.json": assets,
    "review.json": { schema_version: "engineering_review.v1", analysis_status: "solved", tables: [] }
  };
  const geometryResolvers = new Map();
  const geometryRequests = [];
  const fetcher = async (url) => {
    const relativePath = url.replace(/^\/concurrent\//, "");
    if (relativePath in basePayloads) {
      return new Response(JSON.stringify(basePayloads[relativePath]), { status: 200 });
    }
    geometryRequests.push(relativePath);
    return new Promise((resolve) => geometryResolvers.set(relativePath, resolve));
  };

  const loading = loadSceneBundleFromUrl("/concurrent", fetcher);
  await new Promise((resolve) => setImmediate(resolve));

  assert.deepEqual(geometryRequests, ["geometry_first.json", "geometry_second.json", "geometry_third.json"]);
  for (const relativePath of [...geometryRequests].reverse()) {
    geometryResolvers.get(relativePath)(
      new Response(JSON.stringify({ asset_id: relativePath.replace("geometry_", "geometry:").replace(".json", "") }), {
        status: 200
      })
    );
  }
  const bundle = await loading;

  assert.deepEqual(bundle.geometryPayloads.map((payload) => payload.asset_id), [
    "geometry:first",
    "geometry:second",
    "geometry:third"
  ]);
});

test("updates layer visibility without mutating prior state", async () => {
  const bundle = await loadSceneBundle(await createFixtureBundle());
  const state = createViewerState(bundle);

  const next = setLayerVisibility(state, "pipe", false);

  assert.equal(state.layers.pipe.visible, true);
  assert.equal(next.layers.pipe.visible, false);
  assert.deepEqual(next.visibleObjectIds, []);
});
