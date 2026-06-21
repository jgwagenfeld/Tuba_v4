import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { createViewerState, loadSceneBundle, setLayerVisibility } from "../src/sceneLoader.js";

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
  assert.equal(state.layers.pipe.visible, true);
  assert.deepEqual(state.visibleObjectIds, ["object:element:pipe_0"]);
});

test("updates layer visibility without mutating prior state", async () => {
  const bundle = await loadSceneBundle(await createFixtureBundle());
  const state = createViewerState(bundle);

  const next = setLayerVisibility(state, "pipe", false);

  assert.equal(state.layers.pipe.visible, true);
  assert.equal(next.layers.pipe.visible, false);
  assert.deepEqual(next.visibleObjectIds, []);
});
