import assert from "node:assert/strict";
import test from "node:test";

import { getReferenceStress } from "../src/resultReview.js";
import { createViewerState } from "../src/sceneLoader.js";

// A sub-point payload is fetched beside the bundle rather than inlined, because
// a tuyau asset holds tens of thousands of glyphs. So the population under test
// arrives in state.geometryPayloads, exactly as it does in the browser.
function subpointState({ values = [10, 20, 30, 40, 50], totalCount = null, payloadStateId = "result_state:Hot" } = {}) {
  return createViewerState({
    scene: {
      schema_version: "visualization.scene.v1",
      scene_id: "scene:percentile",
      model_id: "model:percentile",
      objects: [
        { id: "object:pipe", kind: "pipe", name: "Run", geometry_asset_id: "asset:pipe" },
        { id: "object:subpoints", kind: "subpoint_field", name: "Wall points", geometry_asset_id: "asset:subpoints" }
      ],
      geometry_assets: [
        { id: "asset:pipe", format: "tube", bounds: [0, 0, 0, 1, 0.1, 0.1], object_ids: ["object:pipe"], generation_config: {} },
        { id: "asset:subpoints", format: "tuyau_subpoint_glyphs", bounds: [0, 0, 0, 1, 0.1, 0.1], object_ids: ["object:subpoints"], generation_config: { count: values.length, range: { min: Math.min(...values), max: Math.max(...values) } } }
      ],
      overlays: [
        { id: "overlay:result_state:Hot", kind: "result_state", data: { id: "result_state:Hot", load_case: "Hot", solver_name: "code_aster" } },
        {
          id: "overlay:solver_result:tuyau_subpoints:Hot",
          kind: "solver_result",
          object_ids: ["object:subpoints"],
          data: {
            result_type: "tuyau_subpoints",
            result_state_id: "result_state:Hot",
            load_case: "Hot",
            field: "SIEQ_ELNO",
            component: "VMIS",
            unit: "Pa",
            total_count: totalCount ?? values.length,
            values: { "object:subpoints": Math.max(...values) },
            legend: { field: "SIEQ_ELNO", unit: "Pa", range: { min: Math.min(...values), max: Math.max(...values) } }
          }
        }
      ],
      views: [],
      diagnostics: []
    },
    geometryPayloads: [{
      asset_id: "asset:subpoints",
      format: "tuyau_subpoint_glyphs",
      generation_config: { result_state_id: payloadStateId, values, component: "VMIS", field: "SIEQ_ELNO" }
    }]
  });
}

test("the reference stress reads the wall-point population, not the element maxima", () => {
  const reference = getReferenceStress(subpointState({ values: [10, 20, 30, 40, 50] }));
  assert.equal(reference.count, 5);
  assert.equal(reference.min, 10);
  assert.equal(reference.max, 50);
  assert.equal(reference.truncated, false);
  // Nearest-rank, no interpolation: the population is a set of measured points.
  assert.deepEqual(reference.percentiles.map((entry) => entry.value), [50, 50]);
});

test("the percentile is the value a fraction of the population exceeds", () => {
  // 100 points: the 99th is the 99th smallest, the 95th the 95th.
  const values = Array.from({ length: 100 }, (_unused, index) => index + 1);
  const reference = getReferenceStress(subpointState({ values }));
  const byFraction = Object.fromEntries(reference.percentiles.map((entry) => [entry.fraction, entry.value]));
  assert.equal(byFraction[0.01], 99);
  assert.equal(byFraction[0.05], 95);
  assert.equal(reference.max, 100);
  // The whole point: the peak is 100 and the 1% line is 99, so one point is
  // doing nothing and the answer barely moves when the mesh is refined.
  assert.ok(reference.max - byFraction[0.01] < 2);
});

test("a population of one point has no spread to report", () => {
  const reference = getReferenceStress(subpointState({ values: [640] }));
  assert.equal(reference.count, 1);
  assert.equal(reference.max, 640);
  assert.ok(reference.percentiles.every((entry) => entry.value === 640));
});

test("a truncated payload is reported rather than absorbed", () => {
  // The bundle declares how many sub-points Code_Aster wrote. A payload with
  // fewer is an unknown selection, and a percentile of an unknown selection is
  // not a number anyone should act on.
  const reference = getReferenceStress(subpointState({ values: [10, 20, 30], totalCount: 24255 }));
  assert.equal(reference.count, 3);
  assert.equal(reference.declaredCount, 24255);
  assert.equal(reference.truncated, true);
});

test("a payload belonging to another result step is not this step's population", () => {
  const state = subpointState({ values: [10, 20, 30], payloadStateId: "result_state:Cold" });
  // One payload for a different step means the active step has none of its own.
  assert.equal(getReferenceStress(state), null);
});

test("a payload with no result state id is still this bundle's population", () => {
  // A legacy bundle that omitted the id is the only payload there is; refusing it
  // would lose the number for nothing.
  const state = subpointState({ values: [10, 20, 30] });
  state.geometryPayloads[0].generation_config.result_state_id = undefined;
  const reference = getReferenceStress(state);
  assert.equal(reference.count, 3);
});

test("non-finite values are dropped from the population", () => {
  const reference = getReferenceStress(subpointState({ values: [10, NaN, 20, Infinity, 30] }));
  assert.equal(reference.count, 3);
  assert.equal(reference.max, 30);
});

test("there is no reference stress without a sub-point field", () => {
  // The cell FE field's values are one number per element, already reduced to a
  // maximum. A percentile of maxima says nothing about the peak problem, so the
  // figure is not offered there rather than offered meaninglessly.
  const state = subpointState();
  state.overlays = state.overlays.filter((overlay) => overlay.data?.result_type !== "tuyau_subpoints");
  assert.equal(getReferenceStress(state), null);
});

test("an empty payload yields nothing rather than a zero", () => {
  const state = subpointState({ values: [] });
  assert.equal(getReferenceStress(state), null);
});
