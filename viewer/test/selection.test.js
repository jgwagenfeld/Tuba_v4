import assert from "node:assert/strict";
import test from "node:test";

import { createViewerState } from "../src/sceneLoader.js";
import {
  getPropertySections,
  hideSelected,
  isolateSelection,
  pickObjectAt,
  selectObject
} from "../src/selection.js";

function fixtureState() {
  return createViewerState({
    scene: {
      schema_version: "visualization.scene.v1",
      scene_id: "scene_selection",
      model_id: "model_selection",
      objects: [
        {
          id: "object:element:pipe_0",
          entity_ref: "element:pipe_0",
          kind: "pipe",
          name: "P-100",
          geometry_asset_id: "geometry:element:pipe_0",
          metadata: {
            section: "PipeSec",
            material: "Steel",
            profile: {
              kind: "pipe",
              outer_diameter_m: 0.1,
              wall_thickness_m: 0.01,
              inner_diameter_m: 0.08
            },
            attributes: { insulation: "mw_50" },
            insulation: { id: "mw_50", material: "mineral_wool" }
          },
          physical: { effective_od_m: 0.2 },
          quantities: { length_m: 2.0 }
        },
        {
          id: "object:obstacle:equipment_box",
          entity_ref: "obstacle:equipment_box",
          kind: "obstacle",
          name: "equipment_box",
          geometry_asset_id: "geometry:obstacle:equipment_box",
          metadata: { type: "cuboid" }
        }
      ],
      geometry_assets: [
        {
          id: "geometry:element:pipe_0",
          format: "tube",
          bounds: [0, -0.1, -0.1, 2, 0.1, 0.1],
          object_ids: ["object:element:pipe_0"],
          generation_config: { points: [[0, 0, 0], [2, 0, 0]] }
        },
        {
          id: "geometry:obstacle:equipment_box",
          format: "cuboid",
          bounds: [3, -0.5, -0.5, 4, 0.5, 0.5],
          object_ids: ["object:obstacle:equipment_box"],
          generation_config: {}
        }
      ],
      overlays: [],
      issues: [],
      route_reviews: [],
      agent_proposals: [],
      views: [],
      scene_diffs: [],
      diagnostics: []
    },
    objects: [],
    objectMap: {},
    overlays: [],
    geometryAssets: [],
    geometryPayloads: []
  });
}

function inspectionState() {
  return createViewerState({
    scene: {
      schema_version: "visualization.scene.v1",
      scene_id: "scene_inspection",
      model_id: "model_inspection",
      objects: [
        {
          id: "object:pipe",
          entity_ref: "element:pipe_insulated",
          kind: "pipe",
          name: "Insulated pipe",
          geometry_asset_id: "asset:pipe",
          metadata: {
            section: "DN100",
            material: "Steel",
            insulation: { id: "mw_30", material: "mineral_wool", thickness_m: 0.03 },
            external_refs: { ifc_guid: "2abc" },
            source_ref: "element:pipe_insulated"
          },
          physical: { effective_radius_m: 0.08, effective_od_m: 0.16 },
          quantities: { length_m: 2 }
        },
        {
          id: "object:clash",
          entity_ref: "issue:clash:pipe:rack",
          kind: "clash_marker",
          name: "Clash marker",
          geometry_asset_id: "asset:clash",
          metadata: {
            issue_id: "issue:clash:pipe:rack",
            left: "element:pipe_insulated",
            right: "obstacle:rack",
            distance_m: 0.04,
            penetration_m: 0.02
          }
        },
        {
          id: "object:mesh",
          entity_ref: "analysis_mesh:Hot:element:pipe_insulated",
          kind: "analysis_mesh_element",
          name: "Analysis mesh element",
          geometry_asset_id: "asset:mesh",
          group_ids: ["AllPipes"],
          metadata: {
            mesh_id: "analysis_mesh:Hot",
            role: "native_element",
            source_ref: "element:pipe_insulated",
            groups: ["AllPipes"]
          },
          source: { analysis_mesh: { id: "analysis_mesh:Hot", member_type: "element", member_id: "pipe_insulated" } }
        }
      ],
      geometry_assets: [
        { id: "asset:pipe", format: "tube", bounds: [0, 0, 0, 2, 0.16, 0.16], object_ids: ["object:pipe"], generation_config: {} },
        { id: "asset:clash", format: "marker", bounds: [1, 0.08, 0, 1, 0.08, 0], object_ids: ["object:clash"], generation_config: {} },
        { id: "asset:mesh", format: "polyline", bounds: [0, 0.2, 0, 2, 0.2, 0], object_ids: ["object:mesh"], generation_config: {} }
      ],
      overlays: [
        {
          id: "overlay:stress",
          kind: "solver_result",
          name: "Stress",
          object_ids: ["object:pipe"],
          data: { field: "max_von_mises", unit: "Pa", values: { "object:pipe": 57000000 } }
        }
      ],
      issues: [
        {
          id: "issue:clash:pipe:rack",
          type: "clash",
          title: "Pipe clashes with rack",
          severity: "error",
          status: "open",
          object_ids: ["object:pipe", "object:clash"],
          entity_refs: ["element:pipe_insulated", "obstacle:rack"]
        }
      ],
      views: [],
      diagnostics: []
    }
  });
}

test("selectObject supports single and additive selection without mutation", () => {
  const state = fixtureState();

  const selected = selectObject(state, "object:element:pipe_0");
  const multi = selectObject(selected, "object:obstacle:equipment_box", { additive: true });

  assert.deepEqual(state.selectedObjectIds ?? [], []);
  assert.deepEqual(selected.selectedObjectIds, ["object:element:pipe_0"]);
  assert.deepEqual(multi.selectedObjectIds, ["object:element:pipe_0", "object:obstacle:equipment_box"]);
});

test("getPropertySections groups identity geometry attributes physical and quantities", () => {
  const state = fixtureState();

  const sections = getPropertySections(state, "object:element:pipe_0");
  const byId = Object.fromEntries(sections.map((section) => [section.id, section]));

  assert.equal(byId.identity.rows.entity_ref, "element:pipe_0");
  assert.equal(byId.geometry.rows.geometry_asset_id, "geometry:element:pipe_0");
  assert.equal(byId.attributes.rows.insulation, "mw_50");
  assert.equal(byId.profile.rows.outer_diameter_m, 0.1);
  assert.equal(byId.profile.rows.wall_thickness_m, 0.01);
  assert.equal(byId.profile.rows.inner_diameter_m, 0.08);
  assert.equal(byId.physical.rows.effective_od_m, 0.2);
  assert.equal(byId.quantities.rows.length_m, 2.0);
});

test("getPropertySections exposes result values clashes external refs and provenance", () => {
  const state = inspectionState();

  const pipeSections = Object.fromEntries(getPropertySections(state, "object:pipe").map((section) => [section.id, section]));
  assert.equal(pipeSections.attributes.rows.insulation_material, "mineral_wool");
  assert.equal(pipeSections.attributes.rows.insulation_thickness_m, 0.03);
  assert.equal(pipeSections.physical.rows.effective_radius_m, 0.08);
  assert.equal(pipeSections.result_values.rows.max_von_mises, 57000000);
  assert.equal(pipeSections.external_refs.rows.ifc_guid, "2abc");

  const clashSections = Object.fromEntries(getPropertySections(state, "object:clash").map((section) => [section.id, section]));
  assert.equal(clashSections.clash.rows.left, "element:pipe_insulated");
  assert.equal(clashSections.clash.rows.distance_m, 0.04);
  assert.equal(clashSections.issues.rows.issue_ids, "issue:clash:pipe:rack");

  const meshSections = Object.fromEntries(getPropertySections(state, "object:mesh").map((section) => [section.id, section]));
  assert.equal(meshSections.provenance.rows.source_ref, "element:pipe_insulated");
  assert.equal(meshSections.provenance.rows.role, "native_element");
});

test("hideSelected and isolateSelection update visible object ids", () => {
  const state = selectObject(fixtureState(), "object:element:pipe_0");

  const hidden = hideSelected(state);
  const isolated = isolateSelection(state);

  assert.deepEqual(hidden.visibleObjectIds, ["object:obstacle:equipment_box"]);
  assert.deepEqual(isolated.visibleObjectIds, ["object:element:pipe_0"]);
});

test("pickObjectAt selects nearest visible object from projected bounds", () => {
  const state = fixtureState();

  const picked = pickObjectAt(state, { x: 64, y: 200 }, { width: 400, height: 400 });

  assert.equal(picked, "object:element:pipe_0");
});
