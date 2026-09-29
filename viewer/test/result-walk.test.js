import assert from "node:assert/strict";
import test from "node:test";

import {
  colorForScalarValue,
  getFindingIndex,
  getFindings,
  getScalarLegend,
  resetLegendScale,
  setActiveFinding,
  setLegendBands,
  setLegendRange,
  stepFinding
} from "../src/resultReview.js";
import { focusFinding, findingFitSpan, fitSelection } from "../src/selection.js";
import { bandEdges } from "../src/legendScale.js";
import { reduceViewerState } from "../src/viewerState.js";
import { createViewerState } from "../src/sceneLoader.js";

function scene() {
  return createViewerState({
    scene: {
      schema_version: "visualization.scene.v1",
      scene_id: "scene:walk",
      model_id: "model:walk",
      bounds: [0, 0, 0, 20, 4, 6],
      objects: [
        { id: "object:pipe:a", kind: "pipe", name: "Run A", geometry_asset_id: "asset:a" },
        { id: "object:pipe:b", kind: "pipe", name: "Run B", geometry_asset_id: "asset:b" },
        { id: "object:pipe:c", kind: "pipe", name: "Run C", geometry_asset_id: "asset:c" }
      ],
      geometry_assets: [
        // Run C is twenty metres of straight pipe. Fitting it whole puts the
        // camera outside the model with the hot spot in the middle of nowhere.
        { id: "asset:a", format: "tube", bounds: [0, 0, 0, 0.4, 0.4, 0.4], object_ids: ["object:pipe:a"], generation_config: {} },
        { id: "asset:b", format: "tube", bounds: [1, 0, 0, 1.4, 0.4, 0.4], object_ids: ["object:pipe:b"], generation_config: {} },
        { id: "asset:c", format: "tube", bounds: [2, 0, 0, 22, 0.4, 0.4], object_ids: ["object:pipe:c"], generation_config: {} }
      ],
      overlays: [
        {
          id: "overlay:result_state:Hot",
          kind: "result_state",
          data: { id: "result_state:Hot", load_case: "Hot", solver_name: "code_aster" }
        },
        {
          id: "overlay:stress:Hot",
          kind: "solver_result",
          name: "Stress Hot",
          object_ids: ["object:pipe:a", "object:pipe:b", "object:pipe:c"],
          data: {
            result_type: "stress",
            result_state_id: "result_state:Hot",
            load_case: "Hot",
            field: "max_von_mises",
            unit: "Pa",
            values: { "object:pipe:a": 6000000, "object:pipe:b": 30000000, "object:pipe:c": 57000000 },
            range: { min: 6000000, max: 57000000 },
            legend: { field: "max_von_mises", unit: "Pa", range: { min: 6000000, max: 57000000 } },
            hotspots: [
              { object_id: "object:pipe:c", value: 57000000, unit: "Pa" },
              { object_id: "object:pipe:b", value: 30000000, unit: "Pa" },
              { object_id: "object:pipe:a", value: 6000000, unit: "Pa" }
            ]
          }
        }
      ],
      views: [],
      diagnostics: []
    }
  });
}

test("the legend starts on the field's own range, continuously scaled", () => {
  const legend = getScalarLegend(scene());
  assert.equal(legend.bands, 0);
  assert.equal(legend.range.min, 6000000);
  assert.equal(legend.range.max, 57000000);
  assert.equal(legend.rangeOverride, null);
});

test("bands and typed bounds reach the legend the scene is tinted from", () => {
  const state = setLegendRange(setLegendBands(scene(), 6), { min: 0, max: 60e6 });
  const legend = getScalarLegend(state);
  assert.equal(legend.bands, 6);
  // 60e6 over six bands is a 10 MPa step, so the ramp is asked to read 0-60.
  assert.equal(legend.range.min, 0);
  assert.equal(legend.range.max, 60e6);
  // And the 3D tint goes through the same legend, so the picture cannot keep
  // the old range while the legend bar shows the new one.
  assert.equal(getScalarLegend(state).range.max, legend.range.max);
});

test("banding and continuous mode paint the same value differently", () => {
  const continuous = getScalarLegend(scene());
  const banded = getScalarLegend(setLegendBands(scene(), 4));
  assert.notEqual(continuous.bands, banded.bands);
  assert.notEqual(
    colorForScalarValue(30000000, banded),
    colorForScalarValue(30000000, { ...continuous, bands: 0, range: { min: 0, max: 60000000 } })
  );
});

test("a band is flat, and a band edge is visible", () => {
  // Derived from the band edges rather than guessed, because with no typed
  // bound the ramp starts at the data's own minimum and not at zero.
  const banded = getScalarLegend(setLegendBands(scene(), 4));
  const edges = bandEdges(banded);
  assert.ok(edges.length >= 3, `expected at least two bands, got ${edges.length - 1}`);
  const inside = (edge, fraction) => edges[edge] + (edges[edge + 1] - edges[edge]) * fraction;
  const first = colorForScalarValue(inside(0, 0.1), banded);
  const alsoFirst = colorForScalarValue(inside(0, 0.9), banded);
  const second = colorForScalarValue(inside(1, 0.5), banded);
  // Flat within a band, which is what makes the edge read as an edge.
  assert.equal(alsoFirst, first);
  assert.notEqual(second, first);
  // And monotonic lightness across bands, so a band boundary is never a jump
  // back the other way.
  const luminance = (colour) => ((colour >> 16 & 0xff) * 0.2126) + ((colour >> 8 & 0xff) * 0.7152) + ((colour & 0xff) * 0.0722);
  assert.ok(luminance(second) > luminance(first));
  // Values outside the ramp clamp into the end bands rather than going blank.
  assert.equal(colorForScalarValue(-1e9, banded), first);
});

test("scale controls are a no-op when there is no legend to scale", () => {
  const modelOnly = { ...scene(), resultFields: [], colorChannel: "model" };
  assert.equal(setLegendBands(modelOnly, 8), modelOnly);
  assert.equal(setLegendRange(modelOnly, { min: 0, max: 1 }), modelOnly);
  assert.equal(resetLegendScale(modelOnly), modelOnly);
});

test("a nonsense typed bound is dropped rather than half-applied", () => {
  const state = setLegendRange(setLegendBands(scene(), 6), { min: 60, max: 0 });
  assert.equal(getScalarLegend(state).rangeOverride, null);
  const zeroWidth = setLegendRange(setLegendBands(scene(), 6), { min: 10, max: 10 });
  assert.equal(getScalarLegend(zeroWidth).rangeOverride, null);
});

test("reset returns the ramp to the field's own range and a continuous scale", () => {
  const scaled = setLegendRange(setLegendBands(scene(), 9), { min: 0, max: 90e6 });
  const reset = resetLegendScale(scaled);
  assert.equal(getScalarLegend(reset).bands, 0);
  assert.equal(getScalarLegend(reset).rangeOverride, null);
  assert.equal(getScalarLegend(reset).range.max, 57000000);
});

test("the scale is remembered per field, not carried between them", () => {
  const state = setLegendRange(setLegendBands(scene(), 6), { min: 0, max: 60e6 });
  const key = Object.keys(state.legendRanges)[0];
  assert.equal(key, "overlay:stress:Hot");
  // A different field reads the field's own declared range, because a bound
  // typed for stress is meaningless against a displacement in millimetres.
  const other = { ...state, resultFields: [], overlays: state.overlays.concat([{
    id: "overlay:displacement:Hot",
    kind: "solver_result",
    data: { result_type: "displacement", result_state_id: "result_state:Hot", load_case: "Hot", values: { "object:pipe:a": 0.004 }, legend: { range: { min: 0, max: 0.01 } } }
  }]) };
  assert.equal(getScalarLegend(other).range.max, 60000000);
});

test("the findings are the hotspots, worst first", () => {
  assert.deepEqual(getFindings(scene()).map((finding) => finding.objectId), [
    "object:pipe:c",
    "object:pipe:b",
    "object:pipe:a"
  ]);
});

test("there is nothing to walk when the field has no findings", () => {
  const empty = { ...scene(), colorChannel: "model" };
  assert.deepEqual(getFindings(empty), []);
  assert.equal(stepFinding(empty, 1), null);
  assert.equal(stepFinding(empty, -1), null);
});

test("the walk starts at the top and goes round", () => {
  // CAEPIPE's item cycling is circular, and it is circular here for the same
  // reason: a review that stops at the end has to be re-entered from the top to
  // confirm nothing was missed.
  const state = scene();
  assert.equal(stepFinding(state, 1).objectId, "object:pipe:c");
  const onC = setActiveFinding(state, "object:pipe:c");
  assert.equal(getFindingIndex(onC), 0);
  assert.equal(stepFinding(onC, 1).objectId, "object:pipe:b");
  assert.equal(stepFinding(setActiveFinding(state, "object:pipe:a"), 1).objectId, "object:pipe:c");
  assert.equal(stepFinding(state, -1).objectId, "object:pipe:a");
});

test("the walk re-derives its position, so a moved threshold cannot strand it", () => {
  const state = setActiveFinding(setResultThresholdAt(scene(), 30000000), "object:pipe:c");
  assert.deepEqual(getFindings(state).map((finding) => finding.objectId), ["object:pipe:c", "object:pipe:b"]);
  assert.equal(getFindingIndex(state), 0);
  // The object that fell below the cut-off is no longer the active finding.
  assert.equal(getFindingIndex(setActiveFinding(state, "object:pipe:a")), -1);
});

function setResultThresholdAt(state, threshold) {
  return reduceViewerState(state, { type: "setResultThreshold", threshold });
}

test("a finding walk frames the spot, not the whole run", () => {
  const state = scene();
  const span = findingFitSpan(state);
  assert.ok(span > 0 && span < 20, `span ${span} should be a fraction of the scene`);
  // Run A is small enough to frame whole, so its bounds come back untouched.
  const onA = focusFinding(state, "object:pipe:a");
  const aBounds = onA.camera.fitRequest.bounds;
  assert.equal(aBounds[0], 0);
  assert.equal(aBounds[3], 0.4);
  // Run C is twenty metres long and gets clamped to a window about its centre.
  const onC = focusFinding(state, "object:pipe:c");
  const cBounds = onC.camera.fitRequest.bounds;
  assert.ok(Math.abs(cBounds[3] - cBounds[0] - span) < 1e-9);
  assert.equal((cBounds[0] + cBounds[3]) / 2, 12);
  assert.ok(cBounds[3] - cBounds[0] < 22 - 2);
});

test("fitting a selection with no max span is unchanged", () => {
  const state = { ...scene(), selectedObjectIds: ["object:pipe:c"] };
  const fitted = fitSelection(state);
  assert.equal(fitted.camera.fitRequest.bounds[0], 2);
  assert.equal(fitted.camera.fitRequest.bounds[3], 22);
  // And the request id advances, so the renderer acts on it.
  assert.equal(fitted.camera.fitRequest.id, Number(state.camera?.fitRequest?.id ?? 0) + 1);
});

test("focusFinding selects and frames in one transition", () => {
  const state = focusFinding(scene(), "object:pipe:b");
  assert.deepEqual(state.selectedObjectIds, ["object:pipe:b"]);
  assert.ok(state.camera.fitRequest);
});

test("focusFinding on an unknown object changes nothing", () => {
  const state = scene();
  assert.equal(focusFinding(state, "object:pipe:nope"), state);
});

test("a scene with no bounds cannot size a finding walk", () => {
  assert.equal(findingFitSpan({}), null);
  assert.equal(findingFitSpan({ bounds: [0, 0, 0] }), null);
  assert.equal(findingFitSpan({ bounds: [0, 0, 0, 0, 0, 0] }), null);
  // A degenerate scene still gets a floor so the lens does not end up inside
  // the pipe it is pointing at.
  assert.equal(findingFitSpan({ bounds: [0, 0, 0, 0, 0, 0] }, 0.15, 0.5), null);
});
