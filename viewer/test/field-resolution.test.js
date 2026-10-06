import assert from "node:assert/strict";
import test from "node:test";
import { getColoringLegend, getColoringValues, getComplianceNotice, getEnvelopeWinners, setColoringComponent, setColoringField } from "../src/coloring.js";
import { ENVELOPE_FIELD_ID, buildEnvelope } from "../src/envelope.js";
import { fieldBodyState, getActiveScalarOverlay, getHotspots, getObjectScalarColor, getScalarLegend, getScalarValues } from "../src/resultReview.js";
import { reduceViewerState } from "../src/viewerState.js";
import { getSelectionSummary } from "../src/selectionSummary.js";
import { createSceneGraphCache, createThreeSceneGraph, disposeThreeSceneGraph } from "../src/renderer.js";

function fieldState(values, components = ["magnitude"]) {
  return {
    colorChannel: "results",
    activeLoadCase: "Hot",
    geometryAssets: [],
    issues: [],
    objects: Object.keys(values).map(id => ({ id, entity_ref: id.replace("object:", ""), kind: "pipe" })),
    overlays: [{ id: "stress", kind: "solver_result", object_ids: Object.keys(values),
      data: { result_type: "stress", field: "stress", unit: "Pa", values } }],
    resultFields: [{ id: "field:stress", overlay_id: "stress", support: "cell", load_case: "Hot",
      field: "stress", unit: "Pa", components }],
    coloring: { loadCase: "Hot", fieldId: "field:stress", component: "magnitude" }
  };
}

test("range, bands and reset repaint both member and vertex colours through the graph cache", () => {
  const state = fieldState({ "object:element:E": 5, "object:surface": 10, "object:low": 0 });
  const vertices = [[0, 1, 0], [1, 1, 0], [0, 2, 0]];
  state.geometryAssets = [
    { id: "member", format: "tube", object_ids: ["object:element:E"],
      generation_config: { points: [[0, 0, 0], [1, 0, 0]], radius_m: .05 } },
    { id: "surface", format: "mesh", object_ids: ["object:surface"],
      generation_config: { vertices, faces: [[0, 1, 2]], vertex_values: [0, 5, 10] } }
  ];
  state.visibleObjectIds = ["object:element:E", "object:surface"];
  const cache = createSceneGraphCache(createThreeSceneGraph, disposeThreeSceneGraph);
  try {
    let previous = cache.get(state);
    let previousMember = previous.objectsByObjectId.get("object:element:E").material.color.getHex();
    let previousSurface = [...previous.objectsByObjectId.get("object:surface").geometry.getAttribute("color").array];
    let next = state;
    for (const action of [
      { type: "setLegendRange", range: { min: 0, max: 20 } },
      { type: "setLegendBands", bands: 4 },
      { type: "resetLegendScale" }
    ]) {
      next = reduceViewerState(next, action);
      const graph = cache.get(next);
      assert.notStrictEqual(graph, previous, action.type);
      const member = graph.objectsByObjectId.get("object:element:E").material.color.getHex();
      const surface = [...graph.objectsByObjectId.get("object:surface").geometry.getAttribute("color").array];
      assert.equal(member, getObjectScalarColor(next, ["object:element:E"]));
      assert.notEqual(member, previousMember, action.type);
      assert.notDeepEqual(surface, previousSurface, action.type);
      previous = graph; previousMember = member; previousSurface = surface;
    }
  } finally { cache.clear(); }
});

test("colouring a field reads each value once, including across object and legend lookups", () => {
  const raw = Object.fromEntries(Array.from({ length: 100 }, (_, i) => [`object:element:E${i}`, [i, 0, 0]]));
  let reads = 0;
  const values = new Proxy(raw, { get(target, key, receiver) { reads++; return Reflect.get(target, key, receiver); } });
  const state = fieldState(values, ["magnitude", "DX", "DY"]);
  for (const object of state.objects) getObjectScalarColor(state, [object.id]);
  assert.equal(reads, 100);
  assert.deepEqual(getColoringLegend(state).range, { min: 0, max: 99 });
  assert.equal(reads, 100);
  const changed = setColoringComponent(state, "DY");
  assert.deepEqual(getColoringLegend(changed).range, { min: 0, max: 0 });
  assert.equal(reads, 200);
  const reloaded = { ...state, overlays: [{ ...state.overlays[0], data: { ...state.overlays[0].data, values: { "object:element:E0": [7, 0, 0] } } }] };
  assert.deepEqual(getColoringValues(reloaded), { "object:element:E0": 7 });
});

test("large vector fields and envelopes calculate ranges without argument spreading", () => {
  const values = Object.fromEntries(Array.from({ length: 200000 }, (_, i) => [`N${i}`, [i, 0, 0]]));
  const state = fieldState(values, ["magnitude", "DX", "DY"]);
  assert.deepEqual(getColoringLegend(state).range, { min: 0, max: 199999 });
  const scalarValues = Object.fromEntries(Object.keys(values).map((id, i) => [id, i]));
  const envelopeState = { ...state, overlays: [{ id: "step1", kind: "solver_result",
    data: { field: "stress", unit: "Pa", result_state_id: "s1", values: scalarValues } }] };
  assert.deepEqual(buildEnvelope(envelopeState, state.resultFields[0]).range, { min: 0, max: 199999 });
});

test("legacy missing values stay unavailable while true zero remains colourable", () => {
  const state = { ...fieldState({ "object:missing": null, "object:empty": "", "object:zero": 0, "object:peak": 10 }), resultFields: [] };
  assert.equal(getObjectScalarColor(state, ["object:missing"]), null);
  assert.equal(getObjectScalarColor(state, ["object:empty"]), null);
  assert.equal(fieldBodyState(state, ["object:missing"]), "no_result");
  assert.notEqual(getObjectScalarColor(state, ["object:zero"]), null);
  assert.deepEqual(getScalarLegend(state).range, { min: 0, max: 10 });
});

test("related vector nodes are indexed once and replaced on reload", () => {
  const state = fieldState(Object.fromEntries(Array.from({ length: 100 }, (_, i) => [`N${i}`, i])));
  state.objects = Array.from({ length: 100 }, (_, i) => ({ id: `object:element:E${i}`, kind: "pipe" }));
  let reads = 0;
  state.overlays[0].data.vectors = state.objects.map((object, i) => ({
    node_id: `N${i}`, get object_ids() { reads++; return [object.id]; }
  }));
  for (const object of state.objects) assert.notEqual(getObjectScalarColor(state, [object.id]), null);
  assert.equal(reads, 100);
  const next = { ...state, overlays: [{ ...state.overlays[0], data: { ...state.overlays[0].data,
    vectors: [{ node_id: "N99", object_ids: [state.objects[0].id] }] } }] };
  assert.notEqual(getObjectScalarColor(next, [state.objects[0].id]), getObjectScalarColor(state, [state.objects[0].id]));
});

test("envelope values, range and winners share one resolution and follow changed steps", () => {
  const state = fieldState({ E: 1 });
  const first = { ...state.overlays[0], data: { ...state.overlays[0].data, result_state_id: "s1" } };
  let reads = 0;
  const values = new Proxy({ E: 2 }, { get(target, key, receiver) { reads++; return Reflect.get(target, key, receiver); } });
  const second = { ...first, id: "second", data: { ...first.data, result_state_id: "s2", values } };
  state.overlays = [first, second];
  state.resultStates = [{ data: { id: "s1", load_case: "Hot" } }, { data: { id: "s2", load_case: "Hot" } }];
  state.coloring = { ...state.coloring, fieldId: ENVELOPE_FIELD_ID };
  assert.deepEqual(getColoringValues(state), { E: 2 });
  assert.deepEqual(getColoringLegend(state).range, { min: 2, max: 2 });
  assert.deepEqual(getEnvelopeWinners(state).winners, { E: "s2" });
  assert.equal(reads, 1);
  const changed = { ...state, overlays: [first, { ...second, data: { ...second.data, values: { E: 3 } } }] };
  assert.deepEqual(getColoringValues(changed), { E: 3 });
});

function envelopeState() {
  const state = fieldState({ "object:a": 10, "object:b": 90, "object:zero": 0, "object:missing": null });
  const first = { ...state.overlays[0], data: { ...state.overlays[0].data, load_case: "Hot", result_state_id: "s1" } };
  const second = { ...first, id: "second", data: { ...first.data, result_state_id: "s2",
    values: { "object:a": 70, "object:b": 20, "object:zero": 0, "object:missing": null } } };
  state.overlays = [first, second];
  state.resultStates = [{ name: "First", data: { id: "s1", load_case: "Hot" } }, { name: "Second", data: { id: "s2", load_case: "Hot" } }];
  return state;
}

test("derived envelopes reach tint, availability, hotspots and probe values without a solver overlay", () => {
  const state = setColoringField(envelopeState(), ENVELOPE_FIELD_ID);
  assert.equal(getActiveScalarOverlay(state), null, "the maximum is not a separate solver overlay");
  assert.deepEqual(getScalarValues(state), { "object:a": 70, "object:b": 90, "object:zero": 0 });
  assert.deepEqual(getScalarLegend(state).range, { min: 0, max: 90 });
  assert.equal(getScalarLegend(state).complianceRole, "derived_envelope_not_a_solver_result");
  assert.equal(getComplianceNotice(state), "Envelope - the worst of the result steps, not a separate solve");
  assert.deepEqual(getHotspots(state).map(h => [h.objectId, h.value, h.unit]),
    [["object:b", 90, "Pa"], ["object:a", 70, "Pa"], ["object:zero", 0, "Pa"]]);
  assert.deepEqual(getEnvelopeWinners(state).winners, { "object:a": "s2", "object:b": "s1", "object:zero": "s1" });
  const probe = getSelectionSummary(state, "object:a").sections.find(section => section.title.startsWith("Probe"));
  assert.ok(probe.lines.some(line => line.label === "Envelope"));
  assert.equal(probe.lines.find(line => line.label === "Rank").value, "2 of 3");
  assert.notEqual(getObjectScalarColor(state, ["object:a"]), null);
  assert.notEqual(getObjectScalarColor(state, ["object:zero"]), null);
  assert.equal(fieldBodyState(state, ["object:missing"]), "no_result");
  assert.deepEqual(getHotspots({ ...state, resultThreshold: 80 }).map(h => h.objectId), ["object:b"]);
  assert.equal(getObjectScalarColor({ ...state, colorChannel: "model" }, ["object:a"]), null);
  assert.deepEqual(getHotspots({ ...state, colorChannel: "model" }), []);
});

test("switching to an envelope repaints the real member graph and preserves missing-result hatching", () => {
  const base = envelopeState();
  base.geometryAssets = base.objects.map((object, i) => ({ id: object.id, format: "tube", object_ids: [object.id],
    generation_config: { points: [[0, i, 0], [1, i, 0]], radius_m: .05 } }));
  base.visibleObjectIds = base.objects.map(object => object.id);
  const cache = createSceneGraphCache(createThreeSceneGraph, disposeThreeSceneGraph);
  try {
    const previous = cache.get(base);
    const previousColor = previous.objectsByObjectId.get("object:a").material.color.getHex();
    const state = setColoringField(base, ENVELOPE_FIELD_ID);
    const next = cache.get(state);
    const color = next.objectsByObjectId.get("object:a").material.color.getHex();
    assert.notEqual(color, previousColor);
    assert.equal(color, getObjectScalarColor(state, ["object:a"]));
    assert.equal(next.objectsByObjectId.get("object:missing").material.userData.noResultHatch, true);
  } finally { cache.clear(); }
});

test("a nodal envelope retains object-to-node mappings from every source step", () => {
  const state = envelopeState();
  state.objects = [{ id: "object:a", kind: "pipe" }, { id: "object:b", kind: "pipe" }];
  state.resultFields = [{ ...state.resultFields[0], support: "node", field: "displacement_magnitude", unit: "m", components: ["DX", "DY", "DZ", "magnitude"] }];
  state.overlays = state.overlays.map((overlay, i) => ({ ...overlay, data: { ...overlay.data,
    result_type: "displacement", field: "displacement_magnitude", unit: "m",
    values: i ? { N1: [3, 0, 0], N2: [0, 6, 0] } : { N1: [1, 0, 0] },
    vectors: [{ node_id: i ? "N2" : "N1", object_ids: [i ? "object:b" : "object:a"] }] } }));
  const next = setColoringField(state, ENVELOPE_FIELD_ID);
  assert.deepEqual(getScalarValues(next), { N1: 3, N2: 6 });
  assert.notEqual(getObjectScalarColor(next, ["object:a"]), null);
  assert.notEqual(getObjectScalarColor(next, ["object:b"]), null);
  assert.equal(getScalarLegend(next).unit, "m");
});

test("envelope quantity metadata follows the selected stress source instead of the first catalogue unit", () => {
  const state = envelopeState();
  const displacement = { id: "displacement", kind: "solver_result", data: { result_type: "displacement", field: "displacement_magnitude", unit: "m", load_case: "Hot", result_state_id: "s1", values: { N1: [100, 0, 0] } } };
  state.overlays = [displacement, ...state.overlays];
  state.resultFields = [{ id: "field:displacement", overlay_id: displacement.id, support: "node", field: "displacement_magnitude", unit: "m", load_case: "Hot" }, ...state.resultFields];
  const next = setColoringField(state, ENVELOPE_FIELD_ID);
  assert.equal(getScalarLegend(next).unit, "Pa");
  assert.deepEqual(getScalarLegend(next).envelope.sources,
    [{ field: "field:stress", label: "Field:stress (elements)", unit: "Pa" }]);
  assert.deepEqual(getScalarValues(next), { "object:a": 70, "object:b": 90, "object:zero": 0 });
});

test("reaction envelopes keep members as context and only tint the matching vector quantity", () => {
  const state = envelopeState();
  state.objects.push({ id: "reaction", kind: "reaction_vector", metadata: { result_type: "reaction_force" } },
    { id: "displacement", kind: "displacement_vector", metadata: { result_type: "displacement" } });
  state.resultFields = [{ ...state.resultFields[0], support: "node", field: "reaction_force_magnitude", unit: "N" }];
  state.overlays = state.overlays.map((overlay, i) => ({ ...overlay, data: { ...overlay.data,
    result_type: "reaction_force", field: "reaction_force_magnitude", unit: "N", values: { N1: i ? 4 : 2 },
    vectors: [{ node_id: "N1", object_ids: ["object:a", "reaction", "displacement"] }] } }));
  const next = setColoringField(state, ENVELOPE_FIELD_ID);
  assert.equal(fieldBodyState(next, ["object:a"]), "context");
  assert.equal(getObjectScalarColor(next, ["object:a"]), null);
  assert.notEqual(getObjectScalarColor(next, ["reaction"]), null);
  assert.equal(getObjectScalarColor(next, ["displacement"]), null);
});

test("generated catalogue display labels do not replace the source overlay quantity identity", () => {
  const state = envelopeState();
  const { field, ...descriptor } = state.resultFields[0];
  state.resultFields = [{ ...descriptor, label: "Von Mises stress (display name)" }];
  const next = setColoringField(state, ENVELOPE_FIELD_ID);
  assert.deepEqual(getScalarValues(next), { "object:a": 70, "object:b": 90, "object:zero": 0 });
  assert.equal(getScalarLegend(next).unit, "Pa");
  assert.deepEqual(getEnvelopeWinners(next).resultStateIds, ["s1", "s2"]);
});

test("an envelope follows reloads and falls back honestly when another case only has one step", () => {
  const state = setColoringField(envelopeState(), ENVELOPE_FIELD_ID);
  assert.equal(getScalarValues(state)["object:a"], 70);
  const changed = { ...state, overlays: state.overlays.map(overlay => overlay.id === "second"
    ? { ...overlay, data: { ...overlay.data, values: { "object:a": 80, "object:b": 20, "object:zero": 0 } } }
    : overlay) };
  assert.equal(getScalarValues(changed)["object:a"], 80);
  const single = { ...state, activeLoadCase: "Cold", activeResultStateId: "cold",
    coloring: { ...state.coloring, loadCase: "Cold" },
    resultStates: [{ data: { id: "cold", load_case: "Cold" } }],
    resultFields: [{ ...state.resultFields[0], id: "field:cold", overlay_id: "cold", load_case: "Cold" }],
    overlays: [{ id: "cold", kind: "solver_result", data: { result_type: "stress", field: "stress", unit: "Pa", load_case: "Cold", result_state_id: "cold", values: { "object:a": 3 } } }] };
  assert.deepEqual(getScalarValues(single), { "object:a": 3 });
  assert.equal(getEnvelopeWinners(single), null);
  assert.equal(getScalarLegend(single).complianceRole, null);
});
