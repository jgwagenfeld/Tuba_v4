import assert from "node:assert/strict";
import test from "node:test";
import { getActiveField, getColoringValues } from "../src/coloring.js";
import { getModelObjectColor } from "../src/modelColoring.js";
import { getGeometryStateOptions, getVisualDeformationDisplayScale } from "../src/resultReview.js";
import { reduceViewerState, preserveViewerStateForReload } from "../src/viewerState.js";
import { getVisibleObjectIds } from "../src/sceneLoader.js";
import { createSceneGraphCache, createThreeSceneGraph, applySelectionHighlight, applyHoverHighlight } from "../src/renderer.js";

test("colour changes rebuild cached materials, and solved bodies inherit their source colour", () => {
  const objects = [
    { id: "beam", kind: "rack_member", entity_ref: "element:B", metadata: { material: "steel", section: "IPE100" } },
    { id: "shape", kind: "deformed_centerline", entity_ref: "element:B" },
    { id: "mesh", kind: "deformed_analysis_mesh_element", metadata: { source_ref: "element:B" } },
    { id: "node", kind: "analysis_mesh_node", metadata: { source_ref: "element:B" } }
  ];
  const state = { objects, colorChannel: "model", modelColorBy: "default", visibleObjectIds: objects.map(o => o.id),
    geometryAssets: objects.map((o, i) => ({ id: `asset:${o.id}`, object_ids: [o.id], format: "cuboid",
      bounds: [0, i, 0, 1, i + 0.1, 1], generation_config: { color: "#888888" } })) };
  const cache = createSceneGraphCache(createThreeSceneGraph);
  const initial = cache.get(state);
  const materialState = reduceViewerState(state, { type: "setModelColorBy", colorBy: "material" });
  const graph = cache.get(materialState);
  assert.notStrictEqual(graph, initial);
  for (const id of ["beam", "shape", "mesh"]) {
    assert.equal(getModelObjectColor(materialState, [id]), "#2563eb");
    const object = graph.objectsByObjectId.get(id);
    assert.equal(object.material.color.getHex(), 0x2563eb);
    applySelectionHighlight(graph, [id]);
    applyHoverHighlight(graph, id);
    assert.equal(object.material.color.getHex(), 0x2563eb);
    assert.equal(object.material.emissive.getHex(), 0);
    assert.equal(Boolean(object.userData.highlightOutline), false, "structural selection must never draw bounding boxes");
    assert.equal(object.userData.outlineSurface, id !== "mesh");
    applyHoverHighlight(graph, null);
    applySelectionHighlight(graph, []);
    assert.equal(object.userData.selected, false);
  }
  assert.equal(getModelObjectColor(materialState, ["node"]), null);
  assert.notStrictEqual(cache.get({ ...materialState, colorChannel: "results" }), graph);
});

function resultContext() {
  const steps = ["Hot:0", "Hot:1", "Cold:0", "Cold:1"];
  const resultStates = steps.map(id => ({ id, kind: "result_state", data: { id, load_case: id.split(":")[0] } }));
  const geometryStates = steps.map(id => ({ id: `shape:${id}`, kind: "geometry_state", data: {
    id: `shape:${id}`, result_state_id: id, load_case: id.split(":")[0], purpose: "visualization", visual_scale: 12
  } }));
  const overlays = steps.flatMap((id, i) => ["stress", "displacement"].map(quantity => ({
    id: `${quantity}:${id}`, kind: "solver_result", data: { result_state_id: id, load_case: id.split(":")[0],
      result_type: quantity, values: { N: quantity === "stress" ? 100 + i : [i, 10 + i, 20 + i] } }
  })));
  const resultFields = overlays.map(o => ({ id: o.id, overlay_id: o.id, label: o.data.result_type,
    load_case: o.data.load_case, result_state_id: o.data.result_state_id, support: "node",
    components: o.data.result_type === "stress" ? ["magnitude"] : ["DX", "DY", "DZ"], unit: o.data.result_type === "stress" ? "Pa" : "m" }));
  return { objects: [], layers: {}, resultStates, geometryStates, overlays: [...resultStates, ...geometryStates, ...overlays], resultFields,
    activeLoadCase: "Hot", activeResultStateId: "Hot:1", activeGeometryStateId: "shape:Hot:1", colorChannel: "results",
    coloring: { loadCase: "Hot", fieldId: "displacement:Hot:1", component: "DZ" }, visualDeformationScale: 12 };
}

test("switching cases retains quantity/component and uses only that case's values", () => {
  let state = reduceViewerState(resultContext(), { type: "setActiveLoadCase", loadCase: "Cold" });
  assert.equal(getActiveField(state).label, "displacement");
  assert.equal(state.coloring.component, "DZ");
  assert.deepEqual(getColoringValues(state), { N: 22 });
  state = reduceViewerState(state, { type: "setActiveLoadCase", loadCase: "Unavailable" });
  assert.equal(getActiveField(state), null);
  assert.deepEqual(getColoringValues(state), {});
});

test("history geometry options and reload stay on the selected result step", () => {
  const state = resultContext();
  assert.deepEqual(getGeometryStateOptions(state).map(o => o.id), ["shape:Hot:1"]);
  const reloaded = preserveViewerStateForReload(state, resultContext());
  assert.equal(reloaded.activeResultStateId, "Hot:1");
  assert.equal(reloaded.activeGeometryStateId, "shape:Hot:1");
  const noShape = { ...state, geometryStates: state.geometryStates.filter(o => o.data.result_state_id !== "Cold:1") };
  const changed = reduceViewerState(noShape, { type: "setActiveResultState", resultStateId: "Cold:1" });
  assert.equal(changed.activeGeometryStateId, null, "never reuse another step's shape");
});

test("case, step and shape controls preserve explicit material colouring", () => {
  const state = { ...resultContext(), colorChannel: "model", modelColorBy: "material" };
  for (const action of [
    { type: "setActiveLoadCase", loadCase: "Cold" },
    { type: "setActiveResultState", resultStateId: "Cold:1" },
    { type: "setActiveGeometryState", geometryStateId: "shape:Hot:1" }
  ]) assert.equal(reduceViewerState(state, action).colorChannel, "model");
});

test("zero deformation scale is displayed and rendered as zero", () => {
  assert.equal(getVisualDeformationDisplayScale({ visualDeformationScale: 0 }), 0);
});

test("changing cases switches applied loads and legacy result vectors together", () => {
  const state = resultContext();
  state.objects = [
    { id: "beam", kind: "rack_member" },
    ...["Hot", "Cold"].flatMap(load_case => ["applied_load", "reaction_vector"].map(kind => ({
      id: `${kind}:${load_case}`, kind, metadata: { load_case }
    })))
  ];
  assert.deepEqual(getVisibleObjectIds(state), ["beam", "applied_load:Hot", "reaction_vector:Hot"]);
  const cold = reduceViewerState(state, { type: "setActiveLoadCase", loadCase: "Cold" });
  assert.deepEqual(cold.visibleObjectIds, ["beam", "applied_load:Cold", "reaction_vector:Cold"]);
});
