import assert from "node:assert/strict";
import test from "node:test";

import { createViewerState, setLayerVisibility } from "../src/sceneLoader.js";
import { applySceneDiffToState } from "../src/sceneDiff.js";
import { preserveViewerStateForReload, reduceViewerState } from "../src/viewerState.js";
import { createWorkflowState } from "../src/workflowState.js";

function bundle(overrides = {}) {
  return {
    objectMap: { "element:cold": "object:cold" },
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
  assert.equal(preserved.objectMap["element:cold"], "object:cold");
  assert.deepEqual(preserved.visibleObjectIds, ["object:cold"]);
});

test("live reload inherits a new overlay's visibility from the preserved kind layer", () => {
  const previous = setLayerVisibility(createViewerState(bundle()), "overlay:clash", false);
  assert.equal(previous.layers["overlay:clash"].visible, false);

  const nextScene = createViewerState(
    bundle({
      overlays: [
        { id: "overlay:clash:reloaded", kind: "clash", name: "Clash", object_ids: ["object:cold", "object:clash"], visible: true },
        { id: "overlay:result:hot", kind: "result_state", name: "Hot result", object_ids: ["object:deformed"], data: { id: "result_state:Hot", load_case: "Hot" }, visible: true },
      ],
    }),
  );

  const preserved = preserveViewerStateForReload(previous, nextScene);

  const reloadedClash = preserved.overlays.find((overlay) => overlay.id === "overlay:clash:reloaded");
  assert.equal(reloadedClash.visible, false);
  assert.ok(!preserved.visibleOverlayIds.includes("overlay:clash:reloaded"));

  // Exact-id match path must not regress: a visible overlay whose kind layer stays visible remains visible.
  assert.equal(preserved.overlays.find((overlay) => overlay.id === "overlay:result:hot").visible, true);
  assert.ok(preserved.visibleOverlayIds.includes("overlay:result:hot"));
});

test("viewer state reload preserves a still-valid workflow tab and review controls", () => {
  const review = {
    schema_version: "engineering_review.v1",
    analysis_status: "solved",
    tables: {}
  };
  const initial = {
    ...createViewerState({ ...bundle(), review, legacyReview: false }),
    ...createWorkflowState({ review, embed: false })
  };
  const selected = reduceViewerState(initial, { type: "selectObjects", objectIds: ["object:cold"] });
  const previous = reduceViewerState(selected, { type: "setWorkflowTab", tabId: "results" });
  const nextState = {
    ...createViewerState({ ...bundle(), review, legacyReview: false }),
    ...createWorkflowState({ review, embed: false })
  };

  const preserved = preserveViewerStateForReload(previous, nextState);

  assert.equal(previous.activeTab, "results");
  assert.deepEqual(previous.selectedObjectIds, ["object:cold"]);
  assert.equal(previous.activeLoadCase, "Hot");
  assert.equal(previous.activeResultStateId, "result_state:Hot");
  assert.equal(preserved.activeTab, "results");
  assert.deepEqual(preserved.selectedObjectIds, ["object:cold"]);
  assert.equal(preserved.activeLoadCase, "Hot");
  assert.equal(preserved.activeResultStateId, "result_state:Hot");
});

test("full scene reload adopts the new coherent result pair when the old load case disappears", () => {
  const previous = {
    ...createViewerState(bundle()),
    camera: { mode: "orbit", target: [4, 5, 6], distance: 9 },
    issueReviewState: { "issue:kept": { status: "resolved", comment: "Checked" } },
    review: { schema_version: "engineering_review.v1", analysis_status: "solved", tables: {} },
    reviewDiagnostics: [{ code: "review:kept" }]
  };
  const coldOverlay = {
    id: "overlay:result:cold",
    kind: "result_state",
    name: "Cold result",
    object_ids: ["object:deformed"],
    data: { id: "result_state:Cold", load_case: "Cold" },
    visible: true
  };
  const nextState = createViewerState(bundle({ overlays: [coldOverlay] }));

  const preserved = preserveViewerStateForReload(previous, nextState);

  assert.equal(preserved.activeResultStateId, "result_state:Cold");
  assert.equal(preserved.activeLoadCase, "Cold");
  assert.deepEqual(preserved.camera, previous.camera);
  assert.deepEqual(preserved.issueReviewState, previous.issueReviewState);
  assert.equal(preserved.review, nextState.review);
});

test("full scene reload keeps geometry state on the replacement result load case", () => {
  const hotResult = { id: "overlay:result:hot", kind: "result_state", data: { id: "result_state:Hot", load_case: "Hot" } };
  const coldResult = { id: "overlay:result:cold", kind: "result_state", data: { id: "result_state:Cold", load_case: "Cold" } };
  const hotVisual = { id: "overlay:geometry:hot", kind: "geometry_state", data: { id: "geometry_state:Hot:visual", load_case: "Hot", purpose: "visualization" } };
  const coldVisual = { id: "overlay:geometry:cold", kind: "geometry_state", data: { id: "geometry_state:Cold:visual", load_case: "Cold", purpose: "visualization" } };
  const previous = createViewerState(bundle({ overlays: [hotResult, hotVisual, coldVisual] }));
  const nextState = createViewerState(bundle({ overlays: [coldResult, hotVisual, coldVisual] }));

  const preserved = preserveViewerStateForReload(previous, nextState);

  assert.equal(preserved.activeLoadCase, "Cold");
  assert.equal(preserved.activeResultStateId, "result_state:Cold");
  assert.equal(preserved.activeGeometryStateId, "geometry_state:Cold:visual");
});

test("full scene reload preserves an old result pair only when both fields remain compatible", () => {
  const base = bundle().scene;
  const hot = base.overlays.find((overlay) => overlay.kind === "result_state");
  const cold = {
    id: "overlay:result:cold",
    kind: "result_state",
    name: "Cold result",
    object_ids: ["object:deformed"],
    data: { id: "result_state:Cold", load_case: "Cold" },
    visible: true
  };
  const previous = createViewerState(bundle());
  const nextState = createViewerState(bundle({ overlays: [cold, hot] }));

  const preserved = preserveViewerStateForReload(previous, nextState);

  assert.equal(preserved.activeResultStateId, "result_state:Hot");
  assert.equal(preserved.activeLoadCase, "Hot");
});

test("full scene reload keeps an absent result context absent", () => {
  const withoutResults = bundle().scene.overlays.filter((overlay) => overlay.kind !== "result_state");
  const previous = createViewerState(bundle({ overlays: withoutResults }));
  const nextState = createViewerState(bundle({ overlays: withoutResults }));

  const preserved = preserveViewerStateForReload(previous, nextState);

  assert.equal(preserved.activeResultStateId, null);
  assert.equal(preserved.activeLoadCase, null);
});

test("scene diff adds objects and geometry while preserving review state", () => {
  const review = {
    schema_version: "engineering_review.v1",
    analysis_status: "solved",
    tables: { project_summary: { id: "project_summary", rows: [] } },
    tableOrder: ["project_summary"]
  };
  const reviewDiagnostics = [
    {
      severity: "warning",
      code: "viewer.review.fixture_warning",
      source: "review.json",
      message: "Fixture warning"
    }
  ];
  const state = reduceViewerState(
    setLayerVisibility(
      createViewerState({ ...bundle(), review, reviewDiagnostics, legacyReview: false }),
      "deformed:visual_centerline",
      false
    ),
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
  assert.equal(result.state.review, review);
  assert.equal(result.state.reviewDiagnostics, reviewDiagnostics);
  assert.equal(result.state.legacyReview, false);
  assert.equal(result.state.objectMap["element:cold"], "object:cold");
});

test("scene diff preserves legacy review state", () => {
  const state = createViewerState({
    ...bundle(),
    review: null,
    reviewDiagnostics: [],
    legacyReview: true
  });

  const result = applySceneDiffToState(state, {
    diff_id: "diff:legacy-review",
    base_scene_id: "scene:rv09"
  });

  assert.equal(result.applied, true);
  assert.equal(result.state.review, null);
  assert.deepEqual(result.state.reviewDiagnostics, []);
  assert.equal(result.state.legacyReview, true);
});

test("viewer state reducer preserves workflow state across a compatible scene diff", () => {
  const review = {
    schema_version: "engineering_review.v1",
    analysis_status: "solved",
    tables: {}
  };
  const initial = {
    ...createViewerState({ ...bundle(), review, legacyReview: false }),
    ...createWorkflowState({ review, embed: true })
  };
  const selected = reduceViewerState(initial, { type: "selectObjects", objectIds: ["object:cold"] });
  const workflow = reduceViewerState(selected, { type: "setWorkflowTab", tabId: "results" });

  const result = reduceViewerState(workflow, {
    type: "applySceneDiff",
    diff: {
      diff_id: "diff:preserve-workflow",
      base_scene_id: "scene:rv09",
      updated_objects: []
    }
  });

  assert.equal(result.activeTab, "results");
  assert.equal(result.embed, true);
  assert.deepEqual(result.selectedObjectIds, ["object:cold"]);
  assert.equal(result.activeLoadCase, "Hot");
  assert.equal(result.activeResultStateId, "result_state:Hot");
  assert.equal(result.review, review);
  assert.equal(result.legacyReview, false);
});

test("compatible scene diff adopts a new coherent result pair when the old load case disappears", () => {
  const state = {
    ...createViewerState(bundle()),
    camera: { mode: "orbit", target: [1, 2, 3], distance: 7 },
    issueReviewState: { "issue:kept": { status: "accepted", comment: "Reviewed" } },
    review: { schema_version: "engineering_review.v1", analysis_status: "solved", tables: {} }
  };

  const result = applySceneDiffToState(state, {
    diff_id: "diff:cold-replaces-hot",
    base_scene_id: "scene:rv09",
    updated_overlays: [{
      id: "overlay:result:hot",
      kind: "result_state",
      name: "Cold result",
      object_ids: ["object:deformed"],
      data: { id: "result_state:Cold", load_case: "Cold" },
      visible: true
    }]
  });

  assert.equal(result.state.activeResultStateId, "result_state:Cold");
  assert.equal(result.state.activeLoadCase, "Cold");
  assert.deepEqual(result.state.camera, state.camera);
  assert.deepEqual(result.state.issueReviewState, state.issueReviewState);
  assert.equal(result.state.review, state.review);
});

test("scene diff keeps geometry state on the replacement result load case", () => {
  const hotResult = { id: "overlay:result:hot", kind: "result_state", data: { id: "result_state:Hot", load_case: "Hot" } };
  const hotVisual = { id: "overlay:geometry:hot", kind: "geometry_state", data: { id: "geometry_state:Hot:visual", load_case: "Hot", purpose: "visualization" } };
  const coldVisual = { id: "overlay:geometry:cold", kind: "geometry_state", data: { id: "geometry_state:Cold:visual", load_case: "Cold", purpose: "visualization" } };
  const state = createViewerState(bundle({ overlays: [hotResult, hotVisual, coldVisual] }));

  const result = applySceneDiffToState(state, {
    diff_id: "diff:cold-replaces-hot-with-hot-geometry-retained",
    base_scene_id: "scene:rv09",
    updated_overlays: [{ ...hotResult, data: { id: "result_state:Cold", load_case: "Cold" } }]
  });

  assert.equal(result.state.activeLoadCase, "Cold");
  assert.equal(result.state.activeResultStateId, "result_state:Cold");
  assert.equal(result.state.activeGeometryStateId, "geometry_state:Cold:visual");
});

test("compatible scene diff keeps an absent result context absent", () => {
  const overlays = bundle().scene.overlays.filter((overlay) => overlay.kind !== "result_state");
  const state = createViewerState(bundle({ overlays }));

  const result = applySceneDiffToState(state, {
    diff_id: "diff:no-result-context",
    base_scene_id: "scene:rv09",
    updated_objects: []
  });

  assert.equal(result.state.activeResultStateId, null);
  assert.equal(result.state.activeLoadCase, null);
});

test("viewer state reducer defaults a hidden workflow tab after a review transition", () => {
  const review = {
    schema_version: "engineering_review.v1",
    analysis_status: "solved",
    tables: {}
  };
  const fullReviewState = {
    ...createViewerState({ ...bundle(), review, legacyReview: false }),
    ...createWorkflowState({ review, embed: false })
  };
  const legacyState = {
    ...fullReviewState,
    review: null,
    legacyReview: true
  };

  const result = reduceViewerState(legacyState, {
    type: "applySceneDiff",
    diff: {
      diff_id: "diff:legacy-workflow-fallback",
      base_scene_id: "scene:rv09",
      updated_objects: []
    }
  });

  assert.equal(result.activeTab, "model");
  assert.equal(result.embed, false);
  assert.equal(result.review, null);
  assert.equal(result.legacyReview, true);
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
