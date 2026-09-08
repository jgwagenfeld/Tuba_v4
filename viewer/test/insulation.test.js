import assert from "node:assert/strict";
import test from "node:test";
import { createViewerState } from "../src/sceneLoader.js";
import { getBodies, setBodyVisibility } from "../src/bodies.js";
import { createThreeSceneGraph } from "../src/renderer.js";

test("opaque insulation occludes internal mesh nodes", () => {
  const graph = createThreeSceneGraph({ visibleObjectIds: ["insulation"], geometryAssets: [{
    id: "insulation", object_ids: ["insulation"], format: "tube_envelope",
    generation_config: { points: [[0, 0, 0], [2, 0, 0]], radius_m: 0.1,
      inner_radius_m: 0.05, envelope_type: "insulation", opacity: 1 }
  }] });
  graph.scene.traverse((object) => {
    if (!object.isMesh) return;
    assert.equal(object.material.transparent, false);
    assert.equal(object.material.depthWrite, true);
  });
});

test("Geometry cannot resurrect legacy clearance/wind shells; insulation is independently labelled", () => {
  const pipe = { id: "pipe", kind: "pipe", geometry_asset_id: "pipe", metadata: {
    insulation: { material: "mineral wool", thickness_m: 0.05 }
  }};
  const envelopes = ["bare_pipe", "wind", "clearance", "insulation"].map((type) => ({
    id: type, kind: "physical_envelope", geometry_asset_id: type,
    layer_ids: [`physical_envelope:${type}`], metadata: { envelope_type: type }
  }));
  const state = createViewerState({ scene: { objects: [pipe, ...envelopes], geometry_assets: [], overlays: [] } });
  assert.deepEqual(state.objects.map((obj) => obj.id), ["pipe", "insulation"]);
  const bodies = getBodies(state);
  assert.deepEqual(bodies.map((body) => body.id), ["geometry", "insulation"]);
  assert.match(bodies[1].metrics[0], /mineral wool/);
  assert.match(bodies[1].metrics[0], /50.*mm/);
  const toggled = setBodyVisibility(setBodyVisibility(state, "geometry", false), "geometry", true);
  assert.deepEqual(toggled.visibleObjectIds.sort(), ["insulation", "pipe"]);
  assert.equal(toggled.layers["physical_envelope:clearance"], undefined);
});
