import assert from "node:assert/strict";
import test from "node:test";
import { contactHistory, contactRecords, contactTangents, contactForceMaxima, contactStatusLabel } from "../src/contactReview.js";
import { setActiveResultState, setVisualDeformationScale, getScalarLegend } from "../src/resultReview.js";
import { createThreeSceneGraph } from "../src/renderer.js";

// Deterministic unit-test data only; never shipped in a review bundle.
function fixture() {
  const contact = { support_id: "S1", node_id: "N1", normal: [0,1,0], status: "sticking", status_source: "derived",
    normal_force: 10000, tangential_force: [-2000,0,0], gap: -1e-6, relative_displacement: [0.002,0,0], slip: [0,0,0], friction_limit: 3000, utilization: 2/3 };
  const resultStates = [0,1,2].map((i) => ({ kind: "result_state", id: `state-${i}`, data: { id: `state-${i}`, load_case: "thermal", metadata: { run_id: "run-1", stage_label: ["Heat","Cool","Uplift"][i], pseudo_time: i }, contact_results: i === 1 ? {} : { S1: { ...contact, ...(i === 2 ? { status: "open", normal_force: 0, tangential_force: [0,0,0], friction_limit: 0, utilization: null } : {}) } } } }));
  return { bounds: [0,0,0,4,1,1], resultStates, overlays: resultStates, activeResultStateId: "state-0", activeLoadCase: "thermal", visualDeformationScale: 50,
    objects: [{ id: "shoe", entity_ref: "support:S1", geometry_asset_id: "shoe-asset" }], visibleObjectIds: ["shoe"], selectedObjectIds: ["shoe"], camera: { target: [1,2,3] },
    geometryAssets: [{ id: "shoe-asset", format: "point", object_ids: ["shoe"], bounds: [1,0,0,1,0,0], generation_config: { source: "tuba.support", point: [1,0,0], support_type: "rest" } }], geometryStates: [], geometryPayloads: [] };
}

test("contact history retains missing steps, signed travel and independent run identity", () => {
  const state = fixture();
  state.resultStates.push({ id: "other", data: { id: "other", load_case: "thermal", metadata: { run_id: "comparison" }, contact_results: state.resultStates[0].data.contact_results } });
  const history = contactHistory(state, "S1");
  assert.equal(history.length, 3); assert.equal(history[0].travel, .002); assert.equal(history[0].force, -2000);
  assert.equal(history[1].available, false); assert.equal(history[2].contact.utilization, null);
  assert.deepEqual(contactTangents([0,1,0]), [[1,0,0],[0,0,-1]]);
  assert.equal(contactTangents([0,0,0]), null);
});

test("actual result selection preserves scale, support and camera and switches contact records", () => {
  const state = fixture(); state.geometryStates = [{ data: { id: "geom-2", result_state_id: "state-2", purpose: "visualization" } }];
  const next = setActiveResultState(state, "state-2");
  assert.equal(contactRecords(next).S1.status, "open"); assert.equal(next.visualDeformationScale, 50);
  assert.equal(next.activeGeometryStateId, "geom-2"); assert.equal(next.camera, state.camera); assert.equal(next.selectedObjectIds, state.selectedObjectIds);
  assert.equal(getScalarLegend(next), null);
  assert.deepEqual(contactForceMaxima(next), { normal: 10000, tangential: 2000 });
});

test("contact scene marks the true shoe location and independently toggles force arrows", () => {
  const state = fixture(); const graph = createThreeSceneGraph(state);
  const marker = graph.root.children.find((o) => o.userData.contactStatus);
  assert.equal(marker.userData.contactStatus, "sticking"); assert.deepEqual(marker.position.toArray(), [1,0,0]);
  assert.equal(marker.children.filter((o) => o.userData.contactForce).length, 2);
  state.contactArrows = { normal: false };
  const next = createThreeSceneGraph(state).root.children.find((o) => o.userData.contactStatus);
  assert.deepEqual(next.children.filter((o) => o.userData.contactForce).map((o) => o.userData.contactForce), ["tangential"]);
  state.activeResultStateId = "state-1";
  assert.equal(createThreeSceneGraph(state).root.children.some((o) => o.userData.contactStatus), false);
});

test("malformed contact data is unavailable, never a zero-valued solved marker", () => {
  const state = fixture(); delete state.resultStates[0].data.contact_results.S1.slip;
  assert.deepEqual(contactRecords(state), {});
  assert.equal(createThreeSceneGraph(state).root.children.some((o) => o.userData.contactStatus), false);
});


test("deformation scaling stays on the selected converged history frame", () => {
  const state = fixture();
  state.activeResultStateId = "state-2";
  state.activeGeometryStateId = "geom-2";
  state.geometryStates = [0,2].map((i) => ({ data: { id: `geom-${i}`, result_state_id: `state-${i}`, load_case: "thermal", purpose: "visualization" } }));
  const next = setVisualDeformationScale(state, 100);
  assert.equal(next.activeGeometryStateId, "geom-2");
  assert.equal(next.activeResultStateId, "state-2");
  assert.equal(next.visualDeformationScale, 100);
});


test("closed zero-friction contact explains indeterminate friction status without inventing stick", () => {
  assert.equal(contactStatusLabel({ status: "indeterminate", normal_force: 1000, friction_limit: 0 }), "closed (frictionless)");
  assert.equal(contactStatusLabel({ status: "open", normal_force: 0, friction_limit: 0 }), "open");
  assert.equal(contactStatusLabel({ status: "indeterminate", normal_force: 1000, friction_limit: 300 }), "indeterminate");
});

test("pseudo-time labels remove binary representation noise without changing stored time", async () => {
  const { formatPseudoTime, getResultStateOptions } = await import("../src/resultReview.js");
  const value = 0.30000000000000004;
  assert.equal(formatPseudoTime(value), "0.3");
  assert.equal(formatPseudoTime(null), "unavailable");
  const state = { resultStates: [{ data: { id: "step", metadata: { stage_label: "Cold", pseudo_time: value } } }] };
  assert.equal(getResultStateOptions(state)[0].label, "Cold / 0.3");
  assert.equal(state.resultStates[0].data.metadata.pseudo_time, value);
});

test("history visibility isolates the active increment and contact-neutral review suppresses unrelated arrows", async () => {
  const { reduceViewerState } = await import("../src/viewerState.js");
  const { getVisibleObjectIds } = await import("../src/sceneLoader.js");
  const state = fixture();
  state.layers = {};
  state.objects.push({ id: "load", kind: "applied_load" },
    ...[0,2].flatMap((i) => ["reaction_vector", "displacement_vector", "deformed_centerline"].map((kind) =>
      ({ id: `${kind}:${i}`, kind, metadata: { result_state_id: `state-${i}` } }))));
  const neutral = getVisibleObjectIds(state);
  assert.deepEqual(neutral, ["shoe", "deformed_centerline:0"]);
  const secondary = reduceViewerState(state, { type: "setContactNeutral", neutral: false });
  assert.deepEqual(secondary.visibleObjectIds, ["shoe", "load", "reaction_vector:0", "displacement_vector:0", "deformed_centerline:0"]);
  const next = reduceViewerState(secondary, { type: "setActiveResultState", resultStateId: "state-2" });
  assert.deepEqual(next.visibleObjectIds, ["shoe", "load", "reaction_vector:2", "displacement_vector:2", "deformed_centerline:2"]);
});
