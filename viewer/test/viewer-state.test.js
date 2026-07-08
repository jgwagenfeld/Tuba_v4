import assert from "node:assert/strict";
import test from "node:test";

import { createViewerState, setLayerVisibility } from "../src/sceneLoader.js";
import { applySceneDiffToState } from "../src/sceneDiff.js";
import { preserveViewerStateForReload, reduceViewerState } from "../src/viewerState.js";

function bundle(overrides = {}) {
  return {
    scene: {
      schema_version: "visualization.scene.v1",
      scene_id: "scene:rv09",
      model_id: "model:rv09",
      objects: [
        {
          id: "object:cold",
          kind: "pipe",
          name: "Cold pipe",
          geometry_asset_id: "asset:cold",
          layer_ids: ["cold_geometry"],
        },
        {
          id: "object:deformed",
          kind: "deformed_centerline",
          name: "Visual deformation",
          geometry_asset_id: "asset:deformed",
          layer_ids: ["deformed:visual_centerline", "result:hot"],
        },
        {
          id: "object:clash",
          kind: "clash_marker",
          name: "Clash marker",
          geometry_asset_id: "asset:clash",
          layer_ids: ["issues:clash"],
        },
      ],
      geometry_assets: [
        { id: "asset:cold", format: "tube", bounds: [0, 0, 0, 1, 0.1, 0.1], object_ids: ["object:cold"], generation_config: {} },
        { id: "asset:deformed", format: "polyline", bounds: [0, 1, 0, 1, 1, 0], object_ids: ["object:deformed"], generation_config: {} },
        { id: "asset:clash", format: "marker", bounds: [0.5, 0.1, 0, 0.5, 0.1, 0], object_ids: ["object:clash"], generation_config: {} },
      ],
      overlays: [
        { id: "overlay:clash", kind: "clash", name: "Clash", object_ids: ["object:cold", "object:clash"], visible: true },
        { id: "overlay:result:hot", kind: "result_state", name: "Hot result", object_ids: ["object:deformed"], data: { id: "result_state:Hot", load_case: "Hot" }, visible: true },
        { id: "overlay:geometry:visual", kind: "geometry_state", name: "Visual x50", object_ids: ["object:deformed"], data: { id: "geometry_state:Hot:visual_x50", visual_scale: 50 }, visible: true },
      ],
      issues: [],
      views: [],
      diagnostics: [],
      ...overrides,
    },
  };
}

test("createViewerState builds layers from object layer_ids and overlay kinds", () => {
  const state = createViewerState(bundle());

  assert.ok(state.layers.cold_geometry);
  assert.ok(state.layers["deformed:visual_centerline"]);
  assert.ok(state.layers["overlay:clash"]);
  assert.equal(state.layers["deformed:visual_centerline"].count, 1);
  assert.deepEqual(state.objectLayerIds["object:deformed"], ["deformed:visual_centerline", "result:hot"]);
  assert.equal(state.activeResultStateId, "result_state:Hot");
  assert.equal(state.activeGeometryStateId, "geometry_state:Hot:visual_x50");
  assert.equal(state.visualDeformationScale, 50);
});

test("layer toggles hide objects without mutating source scene objects", () => {
  const state = createViewerState(bundle());
  const next = setLayerVisibility(state, "deformed:visual_centerline", false);

  assert.deepEqual(state.visibleObjectIds, ["object:cold", "object:deformed", "object:clash"]);
  assert.deepEqual(next.visibleObjectIds, ["object:cold", "object:clash"]);
  assert.equal(state.objects[1].layer_ids[0], "deformed:visual_centerline");
});

test("overlay kind layers hide overlay-owned marker objects independently", () => {
  const state = createViewerState(bundle());
  const next = setLayerVisibility(state, "overlay:clash", false);

  assert.equal(next.layers["overlay:clash"].visible, false);
  assert.deepEqual(next.visibleOverlayIds, ["overlay:result:hot", "overlay:geometry:visual"]);
  assert.deepEqual(next.visibleObjectIds, ["object:cold", "object:deformed"]);
});

test("reaction vectors can be hidden by result layer or solver overlay", () => {
  const base = bundle().scene;
  const state = createViewerState(bundle({
    objects: [
      ...base.objects,
      {
        id: "object:reaction",
        kind: "reaction_vector",
        name: "Reaction",
        geometry_asset_id: "asset:reaction",
        layer_ids: ["result:reaction"],
      },
    ],
    geometry_assets: [
      ...base.geometry_assets,
      { id: "asset:reaction", format: "vector", bounds: [0, 0, 0, 0, 1, 0], object_ids: ["object:reaction"], generation_config: {} },
    ],
    overlays: [
      ...base.overlays,
      {
        id: "overlay:solver_result:reaction:Hot",
        kind: "solver_result",
        name: "Reaction Hot",
        object_ids: ["object:reaction"],
        data: { result_type: "reaction" },
        visible: true,
      },
    ],
  }));

  assert.ok(state.visibleObjectIds.includes("object:reaction"));
  assert.ok(setLayerVisibility(state, "result:reaction", false).visibleObjectIds.includes("object:cold"));
  assert.ok(!setLayerVisibility(state, "result:reaction", false).visibleObjectIds.includes("object:reaction"));
  assert.ok(!setLayerVisibility(state, "overlay:solver_result", false).visibleObjectIds.includes("object:reaction"));
});

test("scene validation diagnostics expose missing geometry and overlay references", () => {
  const state = createViewerState(
    bundle({
      objects: [
        { id: "object:missing", kind: "pipe", geometry_asset_id: "asset:missing", layer_ids: ["cold_geometry"] },
      ],
      geometry_assets: [],
      overlays: [{ id: "overlay:bad", kind: "clash", object_ids: ["object:not-found"] }],
    }),
  );

  assert.deepEqual(
    state.diagnostics.map((diagnostic) => diagnostic.code),
    ["viewer.missing_geometry_asset", "viewer.overlay_missing_object"],
  );
});

test("viewer reducer updates active result and geometry state controls", () => {
  const state = createViewerState(bundle());
  const next = reduceViewerState(state, { type: "setVisualDeformationScale", scale: 12.5 });
  const result = reduceViewerState(next, { type: "setActiveResultState", resultStateId: "result_state:Hot" });
  const geometry = reduceViewerState(result, { type: "setActiveGeometryState", geometryStateId: "geometry_state:Hot:visual_x50" });

  assert.equal(geometry.visualDeformationScale, 12.5);
  assert.equal(geometry.activeResultStateId, "result_state:Hot");
  assert.equal(geometry.activeGeometryStateId, "geometry_state:Hot:visual_x50");
});

test("viewer reducer tracks result review controls without changing clash metadata", () => {
  const state = createViewerState(bundle({
    issues: [
      {
        id: "issue:clash",
        type: "clash",
        object_ids: ["object:clash"],
        metadata: { operating_distance_m: 0.04 }
      }
    ]
  }));

  const scaled = reduceViewerState(state, { type: "setVisualDeformationScale", scale: 10 });
  const displacement = reduceViewerState(scaled, { type: "setDisplacementVectorScale", scale: 2 });
  const reaction = reduceViewerState(displacement, { type: "setReactionVectorScale", scale: 0.5 });
  const threshold = reduceViewerState(reaction, { type: "setResultThreshold", threshold: 60000000 });
  const loadCase = reduceViewerState(threshold, { type: "setActiveLoadCase", loadCase: "Hot" });

  assert.equal(loadCase.visualDeformationScale, 10);
  assert.equal(loadCase.displacementVectorScale, 2);
  assert.equal(loadCase.reactionVectorScale, 0.5);
  assert.equal(loadCase.resultThreshold, 60000000);
  assert.equal(loadCase.activeLoadCase, "Hot");
  assert.deepEqual(loadCase.issues, state.issues);
});

test("viewer reducer stores local issue review status comment and restores visibility", () => {
  const state = createViewerState(bundle());
  const isolated = {
    ...state,
    hiddenObjectIds: ["object:cold"],
    isolatedObjectIds: ["object:clash"],
    sectionBox: { min: [0, 0, 0], max: [1, 1, 1] }
  };

  const reviewed = reduceViewerState(
    reduceViewerState(isolated, { type: "setIssueReviewStatus", issueId: "issue:clash", status: "resolved" }),
    { type: "setIssueReviewComment", issueId: "issue:clash", comment: "Checked" }
  );
  const restored = reduceViewerState(reviewed, { type: "restoreVisibility" });

  assert.equal(reviewed.issueReviewState["issue:clash"].status, "resolved");
  assert.equal(reviewed.issueReviewState["issue:clash"].comment, "Checked");
  assert.deepEqual(restored.hiddenObjectIds, []);
  assert.deepEqual(restored.isolatedObjectIds, []);
  assert.equal(restored.sectionBox, undefined);
});

test("viewer reducer applies compatible SceneDiff while preserving surviving selection", () => {
  const state = reduceViewerState(createViewerState(bundle()), { type: "selectObjects", objectIds: ["object:cold"] });
  const next = reduceViewerState(state, {
    type: "applySceneDiff",
    diff: {
      diff_id: "diff:rv15",
      base_scene_id: "scene:rv09",
      added_objects: [
        {
          id: "object:support",
          kind: "support",
          name: "New support",
          geometry_asset_id: "asset:support",
          layer_ids: ["supports"]
        }
      ],
      updated_objects: [
        {
          id: "object:cold",
          kind: "pipe",
          name: "Cold pipe revised",
          geometry_asset_id: "asset:cold",
          layer_ids: ["cold_geometry"]
        }
      ],
      removed_object_ids: ["object:clash"],
      added_geometry_assets: [
        { id: "asset:support", format: "point", bounds: [2, 0, 0, 2, 0, 0], object_ids: ["object:support"], generation_config: { point: [2, 0, 0] } }
      ],
      updated_overlays: [
        { id: "overlay:clash", kind: "clash", name: "Clash", object_ids: [], visible: true }
      ],
      diagnostics: [{ severity: "warning", code: "visualization.scene_diff.partial", message: "partial update" }]
    }
  });

  assert.deepEqual(next.selectedObjectIds, ["object:cold"]);
  assert.deepEqual(next.objects.map((obj) => obj.id), ["object:cold", "object:deformed", "object:support"]);
  assert.equal(next.objects.find((obj) => obj.id === "object:cold").name, "Cold pipe revised");
  assert.ok(next.geometryAssets.some((asset) => asset.id === "asset:support"));
  assert.equal(next.layers.supports.count, 1);
  assert.ok(!next.visibleObjectIds.includes("object:clash"));
  assert.equal(next.diagnostics.at(-1).code, "visualization.scene_diff.partial");
});

test("viewer reducer records SceneDiff fallback diagnostic for incompatible base scene", () => {
  const state = createViewerState(bundle());
  const next = reduceViewerState(state, {
    type: "applySceneDiff",
    diff: { diff_id: "diff:bad", base_scene_id: "scene:other", added_objects: [] }
  });

  const direct = applySceneDiffToState(state, { diff_id: "diff:bad", base_scene_id: "scene:other", added_objects: [] });
  assert.equal(direct.applied, false);
  assert.equal(direct.requiresFullReload, true);
  assert.deepEqual(next.objects.map((obj) => obj.id), state.objects.map((obj) => obj.id));
});

test("full scene reload preserves camera, layer visibility, and surviving selection", () => {
  const state = reduceViewerState(
    setLayerVisibility(createViewerState(bundle()), "deformed:visual_centerline", false),
    { type: "selectObjects", objectIds: ["object:cold", "object:clash"] },
  );
  const nextScene = createViewerState(
    bundle({
      objects: [
        { id: "object:cold", kind: "pipe", geometry_asset_id: "asset:cold", layer_ids: ["cold_geometry"] },
      ],
      geometry_assets: [
        { id: "asset:cold", format: "tube", bounds: [0, 0, 0, 1, 0.1, 0.1], object_ids: ["object:cold"], generation_config: {} },
      ],
      overlays: [],
    }),
  );

  const preserved = preserveViewerStateForReload(state, nextScene);

  assert.deepEqual(preserved.selectedObjectIds, ["object:cold"]);
  assert.equal(preserved.layers["deformed:visual_centerline"], undefined);
  assert.deepEqual(preserved.camera, state.camera);
  assert.deepEqual(preserved.visibleObjectIds, ["object:cold"]);
});

test("scene diff adds objects and geometry while preserving review state", () => {
  const state = reduceViewerState(
    setLayerVisibility(createViewerState(bundle()), "deformed:visual_centerline", false),
    { type: "selectObjects", objectIds: ["object:cold"] },
  );
  const diff = {
    diff_id: "diff:add-support",
    base_scene_id: "scene:rv09",
    added_objects: [
      {
        id: "object:support",
        kind: "support",
        name: "Diff support",
        geometry_asset_id: "asset:support",
        layer_ids: ["supports"]
      }
    ],
    added_geometry_assets: [
      {
        id: "asset:support",
        format: "point",
        bounds: [1, 0, 0, 1, 0, 0],
        object_ids: ["object:support"],
        generation_config: { point: [1, 0, 0] }
      }
    ]
  };

  const result = applySceneDiffToState(state, diff);

  assert.equal(result.applied, true);
  assert.deepEqual(result.state.selectedObjectIds, ["object:cold"]);
  assert.equal(result.state.layers["deformed:visual_centerline"].visible, false);
  assert.ok(result.state.layers.supports);
  assert.ok(result.state.visibleObjectIds.includes("object:support"));
  assert.equal(result.state.objects.find((obj) => obj.id === "object:support").name, "Diff support");
});

test("scene diff updates and removes objects while pruning invalid geometry references", () => {
  const state = reduceViewerState(createViewerState(bundle()), { type: "selectObjects", objectIds: ["object:clash"] });
  const diff = {
    diff_id: "diff:update-remove",
    base_scene_id: "scene:rv09",
    updated_objects: [
      {
        id: "object:cold",
        kind: "pipe",
        name: "Cold pipe revised",
        geometry_asset_id: "asset:cold",
        layer_ids: ["cold_geometry"]
      }
    ],
    added_geometry_assets: [
      {
        id: "asset:cold",
        format: "tube",
        bounds: [0, 0, 0, 2, 0.1, 0.1],
        object_ids: ["object:cold"],
        generation_config: { points: [[0, 0, 0], [2, 0, 0]], radius_m: 0.05 }
      }
    ],
    removed_object_ids: ["object:clash"]
  };

  const result = applySceneDiffToState(state, diff);

  assert.equal(result.applied, true);
  assert.equal(result.state.objects.find((obj) => obj.id === "object:cold").name, "Cold pipe revised");
  assert.equal(result.state.geometryAssets.find((asset) => asset.id === "asset:cold").bounds[3], 2);
  assert.equal(result.state.objects.some((obj) => obj.id === "object:clash"), false);
  assert.equal(result.state.geometryAssets.some((asset) => asset.id === "asset:clash"), false);
  assert.deepEqual(result.state.selectedObjectIds, []);
});

test("scene diff requests full reload when base scene id does not match", () => {
  const state = createViewerState(bundle());

  const result = applySceneDiffToState(state, {
    diff_id: "diff:wrong-base",
    base_scene_id: "scene:other",
    added_objects: []
  });

  assert.equal(result.applied, false);
  assert.equal(result.requiresFullReload, true);
  assert.equal(result.reason, "base_scene_mismatch");
});
