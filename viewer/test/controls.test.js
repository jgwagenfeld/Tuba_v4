import assert from "node:assert/strict";
import test from "node:test";

import { createViewerState } from "../src/sceneLoader.js";
import { selectObject } from "../src/selection.js";
import {
  applySectionBox,
  buildObjectTree,
  filterIssues,
  focusIssue,
  getIssueSummary,
  groupIssues,
  restoreViewState,
  saveViewState,
  sectionBoxDefaults
} from "../src/controls.js";

function fixtureState() {
  return createViewerState({
    scene: {
      schema_version: "visualization.scene.v1",
      scene_id: "scene_controls",
      model_id: "model_controls",
      objects: [
        {
          id: "object:element:pipe_0",
          entity_ref: "element:pipe_0",
          kind: "pipe",
          name: "P-100",
          geometry_asset_id: "geometry:element:pipe_0",
          metadata: {
            material: "Steel",
            attributes: { insulation: "mw_50" },
            insulation: { id: "mw_50", material: "mineral_wool" }
          }
        },
        {
          id: "object:obstacle:equipment_box",
          entity_ref: "obstacle:equipment_box",
          kind: "obstacle",
          name: "equipment_box",
          geometry_asset_id: "geometry:obstacle:equipment_box",
          metadata: { type: "cuboid" }
        },
        {
          id: "object:issue:clash:element:pipe_0:obstacle:equipment_box",
          kind: "clash_marker",
          name: "Clash marker",
          geometry_asset_id: "geometry:issue:clash:element:pipe_0:obstacle:equipment_box",
          metadata: { issue_id: "issue:clash:element:pipe_0:obstacle:equipment_box" }
        }
      ],
      geometry_assets: [
        {
          id: "geometry:element:pipe_0",
          format: "tube",
          bounds: [0, -0.1, -0.1, 2, 0.1, 0.1],
          object_ids: ["object:element:pipe_0"],
          generation_config: {}
        },
        {
          id: "geometry:obstacle:equipment_box",
          format: "cuboid",
          bounds: [3, -0.5, -0.5, 4, 0.5, 0.5],
          object_ids: ["object:obstacle:equipment_box"],
          generation_config: {}
        },
        {
          id: "geometry:issue:clash:element:pipe_0:obstacle:equipment_box",
          format: "point",
          bounds: [1, 0.12, 0, 1, 0.12, 0],
          object_ids: ["object:issue:clash:element:pipe_0:obstacle:equipment_box"],
          generation_config: { point: [1, 0.12, 0] }
        }
      ],
      overlays: [
        {
          id: "overlay:clash:issue:clash:element:pipe_0:obstacle:equipment_box",
          kind: "clash",
          object_ids: [
            "object:element:pipe_0",
            "object:obstacle:equipment_box",
            "object:issue:clash:element:pipe_0:obstacle:equipment_box"
          ],
          data: { issue_ids: ["issue:clash:element:pipe_0:obstacle:equipment_box"] }
        }
      ],
      issues: [
        {
          id: "issue:clash:element:pipe_0:obstacle:equipment_box",
          type: "clash",
          title: "Pipe clashes with equipment box",
          severity: "error",
          status: "open",
          entity_refs: ["element:pipe_0", "obstacle:equipment_box"],
          view_id: "view:issue:clash:element:pipe_0:obstacle:equipment_box"
        }
      ],
      views: [
        {
          id: "view:issue:clash:element:pipe_0:obstacle:equipment_box",
          issue_id: "issue:clash:element:pipe_0:obstacle:equipment_box",
          selected_object_ids: [
            "object:element:pipe_0",
            "object:obstacle:equipment_box",
            "object:issue:clash:element:pipe_0:obstacle:equipment_box"
          ],
          active_overlay_ids: ["overlay:clash:issue:clash:element:pipe_0:obstacle:equipment_box"],
          camera: { mode: "orbit", target: [1, 0.12, 0], distance: 2 }
        }
      ],
      diagnostics: []
    },
    objects: [],
    objectMap: {},
    overlays: [],
    geometryAssets: [],
    geometryPayloads: []
  });
}

test("buildObjectTree groups objects by kind", () => {
  const tree = buildObjectTree(fixtureState(), { groupBy: "kind" });
  const pipeGroup = tree.children.find((node) => node.id === "kind:pipe");

  assert.equal(tree.children.length, 3);
  assert.equal(pipeGroup.label, "pipe");
  assert.deepEqual(pipeGroup.objectIds, ["object:element:pipe_0"]);
});

test("buildObjectTree groups objects by route group and source", () => {
  const state = createViewerState({
    scene: {
      schema_version: "visualization.scene.v1",
      scene_id: "scene_tree_groups",
      model_id: "model_tree_groups",
      objects: [
        {
          id: "object:pipe",
          kind: "pipe",
          metadata: { route: "R-100", groups: ["AllPipes"] },
          source: { model: { id: "model_tree_groups" } }
        },
        {
          id: "object:mesh",
          kind: "analysis_mesh_element",
          group_ids: ["AllPipes"],
          metadata: { source_ref: "element:pipe" },
          source: { analysis_mesh: { id: "analysis_mesh:Hot", member_type: "element" } }
        }
      ],
      geometry_assets: [],
      overlays: [],
      issues: [],
      views: [],
      diagnostics: []
    }
  });

  assert.equal(buildObjectTree(state, { groupBy: "route" }).children[0].label, "R-100");
  assert.equal(buildObjectTree(state, { groupBy: "group" }).children[0].label, "AllPipes");
  assert.deepEqual(
    buildObjectTree(state, { groupBy: "source" }).children.map((node) => node.label).sort(),
    ["analysis_mesh:Hot", "model_tree_groups"],
  );
});

test("applySectionBox hides objects outside the clipping bounds", () => {
  const next = applySectionBox(fixtureState(), { min: [-1, -1, -1], max: [2.5, 1, 1] });

  assert.deepEqual(next.visibleObjectIds, [
    "object:element:pipe_0",
    "object:issue:clash:element:pipe_0:obstacle:equipment_box"
  ]);
  assert.deepEqual(next.sectionBox.min, [-1, -1, -1]);
});

test("section box defaults pad degenerate linear and point bounds", () => {
  const linear = sectionBoxDefaults([0, 0, 0, 2, 0, 0]);
  const point = sectionBoxDefaults([0, 0, 0, 0, 0, 0]);

  assert.deepEqual(linear.min, [0, -0.000002, -0.000002]);
  assert.deepEqual(linear.max, [2, 0.000002, 0.000002]);
  assert.ok(point.min.every((value, index) => value < point.max[index]));
  assert.deepEqual(point.min, [-0.000001, -0.000001, -0.000001]);
  assert.deepEqual(point.max, [0.000001, 0.000001, 0.000001]);
});

test("saveViewState and restoreViewState roundtrip selection and sectioning", () => {
  const state = applySectionBox(selectObject(fixtureState(), "object:element:pipe_0"), {
    min: [-1, -1, -1],
    max: [2.5, 1, 1]
  });

  const view = saveViewState(state, "Pipe focus");
  const restored = restoreViewState(fixtureState(), view);

  assert.equal(view.name, "Pipe focus");
  assert.deepEqual(restored.selectedObjectIds, ["object:element:pipe_0"]);
  assert.deepEqual(restored.visibleObjectIds, [
    "object:element:pipe_0",
    "object:issue:clash:element:pipe_0:obstacle:equipment_box"
  ]);
});

test("filterIssues narrows by status severity and type", () => {
  const state = fixtureState();
  const matches = filterIssues(state, { status: "open", severity: "error", type: "clash" });

  assert.deepEqual(matches.map((issue) => issue.id), ["issue:clash:element:pipe_0:obstacle:equipment_box"]);
  assert.deepEqual(filterIssues(state, { severity: "warning" }), []);
});

test("groupIssues groups operating clash review by severity load case and status", () => {
  const state = createViewerState({
    scene: {
      schema_version: "visualization.scene.v1",
      scene_id: "scene:clash_review",
      model_id: "model:clash_review",
      objects: [
        { id: "object:pipe", entity_ref: "element:pipe", kind: "pipe", geometry_asset_id: "asset:pipe" },
        {
          id: "object:clash",
          entity_ref: "issue:clash",
          kind: "clash_marker",
          geometry_asset_id: "asset:clash",
          metadata: { issue_id: "issue:clash", operating_distance_m: 0.04, cold_distance_m: 0.12, load_case: "Hot" }
        }
      ],
      geometry_assets: [],
      overlays: [],
      issues: [
        {
          id: "issue:clash",
          type: "clash",
          title: "Operating clash",
          severity: "error",
          status: "open",
          object_ids: ["object:pipe", "object:clash"]
        }
      ],
      views: [],
      diagnostics: []
    }
  });

  const groups = groupIssues(state, { operatingOnly: true });
  const focused = focusIssue(state, "issue:clash");
  const summary = getIssueSummary(focused, "issue:clash");

  assert.equal(groups[0].id, "error:Hot:open");
  assert.deepEqual(focused.selectedObjectIds, ["object:pipe", "object:clash"]);
  assert.equal(summary.review.operating_distance_m, 0.04);
});

test("focusIssue selects involved objects and activates issue view", () => {
  const focused = focusIssue(fixtureState(), "issue:clash:element:pipe_0:obstacle:equipment_box");

  assert.equal(focused.activeIssueId, "issue:clash:element:pipe_0:obstacle:equipment_box");
  assert.deepEqual(focused.selectedObjectIds, [
    "object:element:pipe_0",
    "object:obstacle:equipment_box",
    "object:issue:clash:element:pipe_0:obstacle:equipment_box"
  ]);
  assert.deepEqual(focused.activeOverlayIds, ["overlay:clash:issue:clash:element:pipe_0:obstacle:equipment_box"]);
  assert.deepEqual(focused.camera.target, [1, 0.12, 0]);
});

test("getIssueSummary exposes the title and related object names", () => {
  const summary = getIssueSummary(fixtureState(), "issue:clash:element:pipe_0:obstacle:equipment_box");

  assert.equal(summary.title, "Pipe clashes with equipment box");
  assert.deepEqual(summary.relatedObjects.map((obj) => obj.id), [
    "object:element:pipe_0",
    "object:obstacle:equipment_box"
  ]);
});
