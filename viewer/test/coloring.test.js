import assert from "node:assert/strict";
import test from "node:test";

import {
  componentIsSelectable,
  createColoringState,
  getActiveComponent,
  getActiveField,
  getActiveLoadCase,
  getColoringLegend,
  getColoringValues,
  getComplianceNotice,
  getFieldOptions,
  getLoadCaseOptionsFromFields,
  scalarFor,
  setColoringComponent,
  setColoringField,
  setColoringLoadCase,
  withCoherentColoring
} from "../src/coloring.js";
import { preserveViewerStateForReload } from "../src/viewerState.js";

const STRESS_OVERLAY = {
  id: "overlay:solver_result:stress:Operating",
  kind: "solver_result",
  data: { result_type: "stress", load_case: "Operating", values: { e1: 100, e2: 250 }, unit: "Pa" }
};

const DISPLACEMENT_OVERLAY = {
  id: "overlay:solver_result:displacement:Operating",
  kind: "solver_result",
  data: {
    result_type: "displacement",
    load_case: "Operating",
    values: { N1: [3, 4, 0], N2: [0, 0, 10] },
    unit: "m"
  }
};

const COLD_OVERLAY = {
  id: "overlay:solver_result:stress:Cold",
  kind: "solver_result",
  data: { result_type: "stress", load_case: "Cold", values: { e1: 10 }, unit: "Pa" }
};

const TUYAU_OVERLAY = {
  id: "overlay:solver_result:tuyau:Operating",
  kind: "solver_result",
  data: {
    result_type: "tuyau_subpoints",
    load_case: "Operating",
    values: { s1: 187 },
    unit: "Pa",
    compliance_role: "visualization_only_not_asme_code_stress"
  }
};

function field(id, overlay, extra = {}) {
  return {
    id,
    label: overlay.data.result_type,
    load_case: overlay.data.load_case,
    result_state_id: "rs1",
    overlay_id: overlay.id,
    support: "cell",
    components: ["magnitude"],
    unit: overlay.data.unit,
    range: null,
    compliance_role: overlay.data.compliance_role ?? null,
    ...extra
  };
}

function baseState(overrides = {}) {
  const state = {
    overlays: [STRESS_OVERLAY, DISPLACEMENT_OVERLAY, COLD_OVERLAY],
    resultFields: [
      field("field:stress:Operating", STRESS_OVERLAY),
      field("field:displacement:Operating", DISPLACEMENT_OVERLAY, {
        support: "node",
        components: ["DX", "DY", "DZ", "magnitude"]
      }),
      field("field:stress:Cold", COLD_OVERLAY)
    ],
    ...overrides
  };
  return { ...state, coloring: createColoringState(state) };
}

test("coloring initialises onto the first available field", () => {
  const state = baseState();
  assert.equal(state.coloring.loadCase, "Operating");
  assert.equal(state.coloring.fieldId, "field:stress:Operating");
  assert.equal(state.coloring.component, "magnitude");
});

test("load case options come from the field catalogue", () => {
  assert.deepEqual(
    getLoadCaseOptionsFromFields(baseState()).map((option) => option.id),
    ["Operating", "Cold"]
  );
});

test("field options are scoped to the active load case", () => {
  const state = baseState();
  assert.deepEqual(
    getFieldOptions(state).map((option) => option.id),
    ["field:stress:Operating", "field:displacement:Operating"]
  );
});

test("changing load case re-points the field instead of keeping a stale one", () => {
  // The same field id belongs to one case; carrying it over would silently
  // show the previous case's numbers under the new case's label.
  const next = setColoringLoadCase(baseState(), "Cold");
  assert.equal(next.coloring.loadCase, "Cold");
  assert.equal(next.coloring.fieldId, "field:stress:Cold");
});

test("selecting a field adopts that field's load case", () => {
  const next = setColoringField(baseState(), "field:stress:Cold");
  assert.equal(next.coloring.loadCase, "Cold");
  assert.equal(getActiveField(next).id, "field:stress:Cold");
});

test("components are only selectable for vector fields", () => {
  const scalar = baseState();
  assert.equal(componentIsSelectable(scalar), false);
  const vector = setColoringField(scalar, "field:displacement:Operating");
  assert.equal(componentIsSelectable(vector), true);
});

test("a component the new field also offers is carried across the switch", () => {
  // Both fields expose magnitude, so switching keeps the reader on the same
  // quantity rather than silently jumping to DX.
  const vector = setColoringField(baseState(), "field:displacement:Operating");
  assert.equal(getActiveComponent(vector), "magnitude");
});

test("a component the new field lacks falls back to its first", () => {
  let state = setColoringField(baseState(), "field:displacement:Operating");
  state = setColoringComponent(state, "DZ");
  assert.equal(getActiveComponent(state), "DZ");
  // The scalar stress field has no DZ.
  state = setColoringField(state, "field:stress:Operating");
  assert.equal(getActiveComponent(state), "magnitude");
});

test("an unavailable component snaps back to a real one", () => {
  const state = setColoringComponent(baseState(), "DZ");
  // The active field is scalar, so DZ does not exist on it.
  assert.equal(getActiveComponent(state), "magnitude");
});

test("component selection changes which scalar each node contributes", () => {
  let state = setColoringField(baseState(), "field:displacement:Operating");
  state = setColoringComponent(state, "DX");
  assert.deepEqual(getColoringValues(state), { N1: 3, N2: 0 });
  state = setColoringComponent(state, "magnitude");
  assert.deepEqual(getColoringValues(state), { N1: 5, N2: 10 });
});

test("scalarFor handles vectors and plain numbers", () => {
  assert.equal(scalarFor([3, 4, 0], "magnitude"), 5);
  assert.equal(scalarFor([3, 4, 0], "DY"), 4);
  assert.equal(scalarFor(42, "magnitude"), 42);
});

test("legend derives its range from the overlay when the field declares none", () => {
  const legend = getColoringLegend(baseState());
  assert.deepEqual(legend.range, { min: 100, max: 250 });
  assert.equal(legend.unit, "Pa");
});

test("compliance role surfaces as a notice", () => {
  const state = baseState({
    overlays: [TUYAU_OVERLAY],
    resultFields: [field("field:tuyau:Operating", TUYAU_OVERLAY, { support: "subpoint" })]
  });
  assert.equal(getComplianceNotice(state), "FE stress - not ASME code stress");
  assert.equal(getComplianceNotice(baseState()), null);
});

test("reload keeps the selection when the field survives", () => {
  const previous = setColoringField(baseState(), "field:stress:Cold");
  const next = baseState();
  const preserved = preserveViewerStateForReload(
    { ...previous, objects: [], layers: {}, overlays: previous.overlays },
    { ...next, objects: [], layers: {}, overlays: next.overlays, geometryStates: [], resultStates: [] }
  );
  assert.equal(preserved.coloring.fieldId, "field:stress:Cold");
  assert.equal(preserved.coloring.loadCase, "Cold");
});

test("reload snaps back when the selected field disappears", () => {
  const previous = setColoringField(baseState(), "field:stress:Cold");
  const shrunk = baseState({
    overlays: [STRESS_OVERLAY],
    resultFields: [field("field:stress:Operating", STRESS_OVERLAY)]
  });
  const preserved = preserveViewerStateForReload(
    { ...previous, objects: [], layers: {}, overlays: previous.overlays },
    { ...shrunk, objects: [], layers: {}, overlays: shrunk.overlays, geometryStates: [], resultStates: [] }
  );
  assert.equal(preserved.coloring.fieldId, "field:stress:Operating");
  assert.equal(preserved.coloring.loadCase, "Operating");
});

test("a scene with no fields yields an empty but valid coloring state", () => {
  const state = withCoherentColoring({ overlays: [], resultFields: [], coloring: {} });
  assert.equal(state.coloring.fieldId, null);
  assert.equal(getActiveLoadCase(state), null);
  assert.equal(getColoringLegend(state), null);
  assert.equal(getComplianceNotice(state), null);
});
