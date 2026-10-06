import assert from "node:assert/strict";
import test from "node:test";
import { createViewerState } from "../src/sceneLoader.js";
import { reduceViewerState, preserveViewerStateForReload } from "../src/viewerState.js";
import { getPropertySections, getGeometryRelations } from "../src/selection.js";
import { getSelectionSummary } from "../src/selectionSummary.js";
import { selectionRepresentative } from "../src/reviewSelection.js";
import { createThreeSceneGraph, applySelectionHighlight, disposeThreeSceneGraph } from "../src/renderer.js";

function fixture() {
  const mapping = { id: "map", kind: "interface_mapping", entity_ref: "coupling:mount", geometry_asset_id: "target",
    metadata: { owner_refs: ["component:part", "coupling:mount", "node:N1"], source_ref: "node:N1", target_ref: "component:part",
      model_mapping: "0D reference ↔ 3D solid", interface_mapping: "0D point ↔ 2D face", method: "LIAISON_SOLIDE",
      status: "authored", target_geometry_available: true, node_ids: [], element_ids: [] } };
  const state = createViewerState({ scene: { schema_version: "visualization.scene.v1", objects: [
    { id: "part", entity_ref: "component:part", kind: "imported_component", metadata: {} },
    { id: "tee", entity_ref: "element:tee_0", kind: "pipe", metadata: {} },
    { id: "stl", entity_ref: "component:reference", kind: "imported_component", metadata: { role: "reference" } },
    mapping,
    { ...mapping, id: "tee_map", entity_ref: "element:tee_0", metadata: { ...mapping.metadata, owner_refs: ["element:tee_0"],
      model_mapping: "1D pipe ↔ 3D solid", interface_mapping: "0D endpoint ↔ 2D cut face", method: "LIAISON_ELEM / 3D_TUYAU",
      status: "meshed", face_group: "G_END_N2", node_group: "G_NODE_N2", node_ids: ["VN1", "VN2", "VN3"], element_ids: ["VS1"] } },
    { ...mapping, id: "malformed", metadata: { owner_refs: "component:part" } }
  ], geometry_assets: [
    { id: "target", format: "mesh", bounds: [0, 0, 0, 0, 1, 1], object_ids: ["map"], generation_config: {
      source: "tuba.interface_mapping", part: "target", vertices: [[0, 0, 0], [0, 1, 0], [0, 0, 1]], faces: [[0, 1, 2]], color: "#06b6d4", opacity: .65 } },
    { id: "source", format: "marker", bounds: [-.1, 0, 0, -.1, 0, 0], object_ids: ["map"], generation_config: {
      source: "tuba.interface_mapping", part: "source", point: [-.1, 0, 0], radius_m: .01, color: "#f59e0b" } },
    { id: "spokes", format: "polyline", bounds: [-.1, 0, 0, 0, 1, 0], object_ids: ["map"], generation_config: {
      source: "tuba.interface_mapping", part: "spokes", points: [[-.1, 0, 0], [0, 1, 0]], color: "#f59e0b" } }
  ], overlays: [], issues: [], views: [], diagnostics: [] } });
  return reduceViewerState(state, { type: "setStage", stage: "build" });
}

test("Build shows mappings only for the selected owner and keeps them through isolation and reload", () => {
  const state = fixture();
  assert.ok(!state.visibleObjectIds.includes("map"));
  const selected = reduceViewerState(state, { type: "selectObject", objectId: "part" });
  assert.ok(selected.visibleObjectIds.includes("map"));
  assert.ok(!selected.visibleObjectIds.includes("tee_map"));
  assert.ok(!selected.visibleObjectIds.includes("malformed"));
  const isolated = reduceViewerState(selected, { type: "isolateSelection" });
  assert.ok(isolated.visibleObjectIds.includes("map"));
  assert.ok(!reduceViewerState(selected, { type: "hideSelected" }).visibleObjectIds.includes("map"));
  const off = reduceViewerState(isolated, { type: "setInterfaceMappingsVisible", visible: false });
  assert.ok(!off.visibleObjectIds.includes("map"));
  assert.equal(preserveViewerStateForReload(off, fixture()).interfaceMappingsVisible, false);
  assert.ok(!reduceViewerState(selected, { type: "setStage", stage: "review" }).visibleObjectIds.includes("map"));
  assert.ok(!reduceViewerState(state, { type: "selectObject", objectId: "stl" }).visibleObjectIds.includes("map"));
});

test("mapping inspection distinguishes model and boundary dimensions and reports only resolved membership", () => {
  const state = fixture();
  const authored = getPropertySections(state, "part").find(section => section.id === "interface_mapping:map");
  assert.equal(authored.rows.Interface, "0D point ↔ 2D face");
  assert.equal(authored.rows["Model coupling"], "0D reference ↔ 3D solid");
  assert.equal(authored.rows["Mapped nodes"], undefined);
  const resolved = getPropertySections(state, "tee").find(section => section.id === "interface_mapping:tee_map");
  assert.equal(resolved.rows["Mapped nodes"], 3);
  assert.equal(resolved.rows["Mapped cells"], 1);
  assert.equal(resolved.rows["Face group"], "G_END_N2");
  assert.match(resolved.rows.Method, /3D_TUYAU/);
  assert.equal(getSelectionSummary(state, "part").sections[0].id, "interface_mapping:map");
  assert.equal(selectionRepresentative(state, "tee_map"), "tee_map", "clicking the cut face inspects that mapping");
  assert.ok(getGeometryRelations(state, "part").some(link => link.id === "map"));
  assert.match(getGeometryRelations(state, "tee")[0].label, /tee_map/);
  assert.ok(getGeometryRelations(state, "map").some(link => link.id === "part"));
});

test("mapping footprints stay visible through the body and preserve source/target colours when selected", () => {
  const state = reduceViewerState(fixture(), { type: "selectObject", objectId: "part" });
  const graph = createThreeSceneGraph(state);
  applySelectionHighlight(graph, ["map"]);
  for (const name of ["target", "source", "spokes"]) {
    const rendered = graph.root.children.find(object => object.name === name);
    assert.ok(rendered);
    assert.equal(rendered.material.depthTest, false);
    assert.equal(rendered.material.transparent, true, "draw after transparent bodies");
    assert.equal(rendered.material.color.getHexString(), name === "target" ? "06b6d4" : "f59e0b");
  }
  disposeThreeSceneGraph(graph);
});
