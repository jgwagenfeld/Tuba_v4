import assert from "node:assert/strict";
import test from "node:test";
import { contactHistory, contactRecords, contactTangents, contactForceMaxima, contactStatusLabel } from "../src/contactReview.js";
import { setActiveResultState, setVisualDeformationScale, getScalarLegend } from "../src/resultReview.js";
import { createThreeSceneGraph } from "../src/renderer.js";

// Deterministic unit-test data only; never shipped in a review bundle.
function fixture() {
  const contact = { support_id: "S1", node_id: "N1", normal: [0,1,0], status: "sticking", status_source: "solver",
    normal_force: 10000, tangential_force: [-2000,0,0], gap: -1e-6, relative_displacement: [0.002,0,0], slip: [0,0,0], friction_limit: 3000, utilization: 2/3 };
  const resultStates = [0,1,2].map((i) => ({ kind: "result_state", id: `state-${i}`, data: { id: `state-${i}`, load_case: "thermal", metadata: { run_id: "run-1", stage_label: ["Heat","Cool","Uplift"][i], pseudo_time: i }, contact_results: i === 1 ? {} : { S1: { ...contact, ...(i === 2 ? { status: "open", normal_force: 0, tangential_force: [0,0,0], friction_limit: 0, utilization: null } : {}) } } } }));
  // Contact colouring is the Results channel, and these fixtures carry result
  // states, so the scene opens on it. This used to be left unset and relied on
  // `activeTab !== "model"`; the channel is explicit state now.
  return { reviewFocus: "contact", bounds: [0,0,0,4,1,1], resultStates, overlays: resultStates, activeResultStateId: "state-0", activeLoadCase: "thermal", visualDeformationScale: 50,
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

test("contact marks follow the active result state's overlay visibility", () => {
  const state = fixture();
  state.visibleOverlayIds = ["state-0"];
  assert.equal(createThreeSceneGraph(state).root.children.some((o) => o.userData.contactStatus), true);
  // Build and Model presets hide the result state overlay; a solver mark drawn
  // on a still-visible support must not survive the layer it belongs to.
  state.visibleOverlayIds = [];
  assert.equal(createThreeSceneGraph(state).root.children.some((o) => o.userData.contactStatus), false);
});

test("a sticking shoe draws force arrows only, and an over-limit pad carries the red", () => {
  const state = fixture();
  state.geometryAssets[0].generation_config.friction_coefficient = 0.3;
  state.geometryAssets[0].generation_config.support_id = "S1";
  const graph = createThreeSceneGraph(state);
  const group = graph.root.children.find((o) => o.userData.contactStatus === "sticking");
  assert.ok(group);
  // Sticking is the rest state: no status glyph, just the two force arrows.
  assert.equal(group.children.length, 2);
  assert.ok(group.children.every((child) => child.userData.contactForce));

  let pad = null;
  graph.root.traverse((object) => { if (object.userData?.supportPart === "contact-shoe-pad") pad = object; });
  assert.equal(pad.material.color.getHex(), 0x2563eb);

  state.resultStates[0].data.contact_results.S1.utilization = 2;
  const over = createThreeSceneGraph(state);
  let overPad = null;
  over.root.traverse((object) => { if (object.userData?.supportPart === "contact-shoe-pad") overPad = object; });
  assert.equal(overPad.material.color.getHex(), 0xdc2626);

  // The states that need saying keep their glyph beside the force arrows.
  state.resultStates[0].data.contact_results.S1 = { ...state.resultStates[0].data.contact_results.S1, status: "sliding", utilization: 0.5 };
  assert.equal(createThreeSceneGraph(state).root.children.find((o) => o.userData.contactStatus === "sliding").children.length, 3);
  state.resultStates[0].data.contact_results.S1 = { ...state.resultStates[0].data.contact_results.S1, status: "open" };
  assert.equal(createThreeSceneGraph(state).root.children.find((o) => o.userData.contactStatus === "open").children.length, 3);
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

test("only a review that declares contact focus gives up its scalar legend", () => {
  // Every rest is a DIS_CHOC shoe now, so an ordinary pressurised line reports a
  // contact record too. Reading that as a contact review neutralised the pipe and
  // took the scalar legend off seven galleries, one of which is a plain stress
  // review. The study says which it is; the records no longer decide.
  const contactReview = { ...fixture(),
    resultFields: [{ id: "field:stress", overlay_id: "state-0", label: "FE VMIS", support: "cell",
      unit: "Pa", components: ["magnitude"], range: [1e6, 4e8], load_case: "thermal" }],
    coloring: { fieldId: "field:stress", component: "magnitude", loadCase: "thermal" } };

  assert.equal(getScalarLegend(contactReview), null, "a declared contact review colours the pipe neutrally");

  const { reviewFocus, ...restsOnShoes } = contactReview;
  assert.equal(getScalarLegend(restsOnShoes).field, "FE VMIS (cell)");
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
