import assert from "node:assert/strict";
import test from "node:test";
import { OrthographicCamera, Plane, Vector3 } from "three";
import { applyFocusSelection, applySectionBoxClipping, createThreeSceneGraph, pickRenderedObject, pickRenderedPoints } from "../src/renderer.js";
import { getModelObjectColor } from "../src/modelColoring.js";
import { reduceViewerState } from "../src/viewerState.js";

test("stacked picking exposes distinct visible components, collapses representations, and restores focus", () => {
  const objects = [
    { id: "front", entity_ref: "element:frame", kind: "rack_member", metadata: { element_type: "beam" } },
    { id: "back", entity_ref: "element:pipe", kind: "pipe", metadata: { route_id: "Run A" } },
    { id: "back-mesh", entity_ref: "element:pipe", kind: "analysis_mesh_element" },
    { id: "second-run", entity_ref: "element:other", kind: "pipe", metadata: { route_id: "Run B" } },
    { id: "cad", entity_ref: "component:body", kind: "imported_component" }
  ];
  const asset = (id, y) => ({ id: `asset:${id}`, format: "marker", object_ids: [id],
    bounds: [-0.5, y - 0.5, -0.5, 0.5, y + 0.5, 0.5], generation_config: { point: [0, y, 0], radius_m: 0.5 } });
  const state = { objects, colorChannel: "model", modelColorBy: "default", selectedObjectIds: ["back"],
    geometryAssets: [asset("front", -2), asset("back", 0), asset("back-mesh", 0.1), asset("cad", 2)],
    visibleObjectIds: ["front", "back", "back-mesh", "cad"], layers: [], overlays: [] };
  const graph = createThreeSceneGraph(state);
  graph.camera = new OrthographicCamera(-5, 5, 5, -5, 0.1, 100);
  graph.camera.up.set(0, 0, 1);
  graph.camera.position.set(0, -10, 0);
  graph.camera.lookAt(0, 0, 0);
  const point = { x: 252, y: 252 };
  const viewport = { width: 500, height: 500 };
  const ids = () => pickRenderedPoints(graph, point, viewport).map(hit => hit.objectId);
  // back-mesh shares back's element, so Select Other lists the element once.
  assert.deepEqual(ids(), ["front", "back", "cad"]);
  assert.equal(pickRenderedObject(graph, point, viewport), "front");
  assert.equal(graph.objectsByObjectId.get("cad").userData.outlineSurface, true);
  graph.objectsByObjectId.get("front").visible = false;
  assert.deepEqual(ids(), ["back", "cad"]);
  graph.objectsByObjectId.get("front").visible = true;
  applySectionBoxClipping(graph, { min: [-5, -5, -5], max: [5, 1, 5] });
  assert.deepEqual(ids(), ["front", "back"]);
  applySectionBoxClipping(graph);
  graph.objectsByObjectId.get("front").material.clippingPlanes = [new Plane(new Vector3(0, 1, 0), -1)];
  assert.deepEqual(ids(), ["back", "cad"]);
  graph.objectsByObjectId.get("front").material.clippingPlanes = null;
  const front = graph.objectsByObjectId.get("front").material;
  const back = graph.objectsByObjectId.get("back").material;
  const before = [front.opacity, front.transparent, front.depthWrite];
  applyFocusSelection(graph, ["back"]);
  assert.equal(front.opacity, 0.14);
  assert.equal(front.depthWrite, false);
  assert.equal(back.opacity, 1);
  applyFocusSelection(graph, []);
  assert.deepEqual([front.opacity, front.transparent, front.depthWrite], before);
  assert.equal(getModelObjectColor(state, ["front"]), "#64748b");
  assert.equal(getModelObjectColor(state, ["back"]), getModelObjectColor(state, ["back-mesh"]));
  assert.notEqual(getModelObjectColor(state, ["back"]), getModelObjectColor(state, ["second-run"]));
  assert.equal(getModelObjectColor({ ...state, colorChannel: "results" }, ["front"]), null);
  const focused = reduceViewerState(state, { type: "setFocusSelection", enabled: true });
  assert.equal(focused.focusSelection, true);
  assert.equal(reduceViewerState(focused, { type: "restoreVisibility" }).focusSelection, false);
});
