import assert from "node:assert/strict";
import test from "node:test";
import { createThreeSceneGraph, applyHoverHighlight, applySelectionHighlight } from "../src/renderer.js";
import { selectObject, hideSelected, isolateSelection, fitSelection } from "../src/selection.js";

test("engineering selection follows solved bodies without selecting mesh nodes or unrelated members", () => {
  const objects = [
    { id: "beam", entity_ref: "element:B1", kind: "rack_member" },
    { id: "deformed", entity_ref: "element:B1", kind: "deformed_centerline" },
    { id: "node", entity_ref: "element:B1", kind: "analysis_mesh_node" },
    { id: "other", entity_ref: "element:B2", kind: "rack_member" }
  ];
  const geometryAssets = objects.map((o, i) => ({
    id: `asset:${o.id}`, object_ids: [o.id], format: "cuboid",
    bounds: [0, i, 0, 1, i + 0.1, 1], generation_config: {}
  }));
  const state = { objects, geometryAssets, layers: {}, selectedObjectIds: [], visibleObjectIds: objects.map(o => o.id) };
  const selected = selectObject(state, "deformed");
  assert.deepEqual(selected.selectedObjectIds, ["beam"]);
  assert.deepEqual(hideSelected(selected).hiddenObjectIds, ["beam", "deformed"]);
  assert.deepEqual(isolateSelection(selected).isolatedObjectIds, ["beam", "deformed"]);
  assert.deepEqual(fitSelection(selected).camera.fitRequest.bounds, [0, 0, 0, 1, 1.1, 1]);
  const graph = createThreeSceneGraph(state);
  applySelectionHighlight(graph, selected.selectedObjectIds);
  applyHoverHighlight(graph, "deformed");
  for (const id of ["beam", "deformed"]) {
    assert.equal(graph.objectsByObjectId.get(id).userData.selected, true);
    assert.equal(graph.objectsByObjectId.get(id).userData.hovered, true);
  }
  assert.equal(graph.objectsByObjectId.get("node").userData.selected, false);
  assert.equal(graph.objectsByObjectId.get("other").userData.selected, false);
  applyHoverHighlight(graph, null);
  assert.equal(graph.objectsByObjectId.get("deformed").userData.hovered, false);
  assert.equal(graph.objectsByObjectId.get("deformed").userData.selected, true);
});

test("support highlight preserves its status colour and clears its outline", () => {
  const state = {
    objects: [{ id: "shoe", kind: "support", entity_ref: "support:S1" }], visibleObjectIds: ["shoe"],
    geometryAssets: [{ id: "asset:shoe", object_ids: ["shoe"], format: "point", bounds: [1, 0, 0, 1, 0, 0],
      generation_config: { source: "tuba.support", point: [1, 0, 0], support_type: "rest" } }]
  };
  const graph = createThreeSceneGraph(state);
  const shoe = graph.objectsByObjectId.get("shoe");
  const colours = [];
  shoe.traverse(part => { if (part.material?.color) colours.push([part.material, part.material.color.getHex()]); });
  applySelectionHighlight(graph, ["shoe"]);
  applyHoverHighlight(graph, "shoe");
  assert.equal(shoe.userData.highlightOutline.visible, true);
  for (const [material, colour] of colours) assert.equal(material.color.getHex(), colour);
  applyHoverHighlight(graph, null);
  applySelectionHighlight(graph, []);
  assert.equal(shoe.userData.highlightOutline.visible, false);
});
