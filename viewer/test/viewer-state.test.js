import assert from "node:assert/strict";
import test from "node:test";

import { createViewerState, setLayerVisibility } from "../src/sceneLoader.js";
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

test("Build keeps a volume review's mesh and the review restores what the bundle declared", () => {
  const base = bundle().scene;
  const state = createViewerState(bundle({
    objects: [
      ...base.objects,
      {
        id: "object:skin",
        kind: "analysis_mesh_surface",
        name: "Volume skin",
        geometry_asset_id: "asset:skin",
        layer_ids: ["analysis_mesh:volume_skin"],
      },
    ],
    geometry_assets: [
      ...base.geometry_assets,
      { id: "asset:skin", format: "mesh", bounds: [0, 0, 0, 1, 1, 1], object_ids: ["object:skin"], generation_config: {} },
    ],
    layers: [
      { id: "analysis_mesh:volume_skin", category: "analysis_mesh", label: "Volume skin", default_visible: true },
      { id: "analysis_mesh:identity:mesh", category: "analysis_mesh", label: "Mesh identity", default_visible: false },
    ],
  }));

  assert.equal(state.layers["analysis_mesh:volume_skin"].visible, true);

  const build = reduceViewerState(state, { type: "enterBuild" });
  // Build is a stage, not a task, so entering it no longer claims one. It used
  // to set activeTab "model" purely to get past a preset table keyed by task
  // id, which meant leaving Build dropped you on Model however you arrived -
  // and workspaceView reports no active task outside the review stage anyway.
  assert.equal(build.activeTab, state.activeTab, "entering Build leaves the review's task alone");
  // A volume review carries no procedural design geometry - the mesh skin is
  // the model - so Build keeps it rather than emptying the canvas.
  assert.equal(build.layers["analysis_mesh:volume_skin"].visible, true);
  assert.ok(build.visibleObjectIds.includes("object:skin"));
  // A layer the bundle declared hidden is not revived by the preset.
  assert.equal(build.layers["analysis_mesh:identity:mesh"].visible, false);
  // Result overlays belong to the review, not to the built model.
  assert.equal(build.layers["overlay:result_state"].visible, false);

  const review = reduceViewerState(build, { type: "resetLayerVisibility" });
  assert.equal(review.layers["analysis_mesh:volume_skin"].visible, true);
  assert.equal(review.layers["overlay:result_state"].visible, true);
});

// Verified end to end for a published bundle, where Build is only a view
// change. A studio additionally swaps its build bundle in, and that bundle
// cannot offer a review's task, so preserveViewerStateForReload still falls
// back to Model on the way through - state discards the task the view is now
// capable of guarding on its own. Fixing that means the remaining raw
// activeTab readers move to workspaceView first.
test("entering Build no longer resets the review's task", () => {
  const onResults = reduceViewerState(
    createViewerState(bundle()),
    { type: "activateTask", tabId: "results" }
  );
  assert.equal(onResults.activeTab, "results");

  const andBack = reduceViewerState(
    reduceViewerState(onResults, { type: "enterBuild" }),
    { type: "resetLayerVisibility" }
  );

  assert.equal(andBack.activeTab, "results", "Build is a detour, not a reset of where you were");
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
  const fixture = bundle();
  Object.assign(fixture.scene.overlays.find((overlay) => overlay.kind === "geometry_state").data, { load_case: "Hot", purpose: "visualization" });
  const state = createViewerState(fixture);
  const result = reduceViewerState(state, { type: "setActiveResultState", resultStateId: "result_state:Hot" });
  const scaled = reduceViewerState(result, { type: "setVisualDeformationScale", scale: 12.5 });
  const geometry = reduceViewerState(scaled, { type: "setActiveGeometryState", geometryStateId: "geometry_state:Hot:visual_x50" });

  assert.equal(geometry.visualDeformationScale, 50);
  assert.equal(geometry.activeResultStateId, "result_state:Hot");
  assert.equal(geometry.activeGeometryStateId, "geometry_state:Hot:visual_x50");
});

test("viewer reducer owns compound selection and visibility transitions", () => {
  const initial = createViewerState(bundle());
  const selected = reduceViewerState(
    reduceViewerState(initial, { type: "selectObject", objectId: "object:cold" }),
    { type: "selectObject", objectId: "object:clash", additive: true },
  );
  const hidden = reduceViewerState(selected, { type: "hideSelected" });
  const isolated = reduceViewerState(hidden, { type: "isolateSelection" });
  const restored = reduceViewerState(isolated, { type: "restoreVisibility" });
  const sectioned = reduceViewerState(restored, {
    type: "applySectionBox",
    sectionBox: { min: [0, 0, 0], max: [0.5, 0.5, 0.5] },
  });
  const view = reduceViewerState(sectioned, {
    type: "restoreViewState",
    view: { selectedObjectIds: ["object:cold"], visibleLayers: { "issues:clash": false } },
  });

  assert.deepEqual(selected.selectedObjectIds, ["object:cold", "object:clash"]);
  assert.ok(!hidden.visibleObjectIds.includes("object:cold"));
  assert.deepEqual(isolated.isolatedObjectIds, ["object:cold", "object:clash"]);
  assert.deepEqual(restored.hiddenObjectIds, []);
  assert.deepEqual(sectioned.sectionBox, { min: [0, 0, 0], max: [0.5, 0.5, 0.5] });
  assert.equal(view.layers["issues:clash"].visible, false);
});

test("viewer reducer fits the current selection through a camera request", () => {
  const selected = reduceViewerState(createViewerState(bundle()), { type: "selectObject", objectId: "object:cold" });
  const fitted = reduceViewerState(selected, { type: "fitSelection" });

  assert.deepEqual(fitted.camera.fitRequest.bounds, [0, 0, 0, 1, 0.1, 0.1]);
});

test("viewer reducer owns task and issue transitions", () => {
  const review = { schema_version: "engineering_review.v1", analysis_status: "solved", tables: {} };
  const initial = {
    ...createViewerState(bundle({
      issues: [{ id: "issue:clash", type: "clash", object_ids: ["object:clash"] }],
    })),
    ...createWorkflowState({ review }),
  };
  const task = reduceViewerState(initial, { type: "activateTask", tabId: "model" });
  const issue = reduceViewerState(task, { type: "focusIssue", issueId: "issue:clash" });

  assert.equal(task.activeTab, "model");
  assert.equal(task.layers["result:hot"].visible, false);
  assert.equal(issue.activeIssueId, "issue:clash");
  assert.deepEqual(issue.selectedObjectIds, ["object:clash"]);
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
  assert.equal(loadCase.resultVectorScales.displacement, 2);
  assert.equal(loadCase.resultVectorScales.reaction, 0.5);
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
  const previous = reduceViewerState(selected, { type: "activateTask", tabId: "results" });
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

test("label layer visibility survives result changes and full reload", () => {
  const source = bundle();
  source.scene.objects.push({ id: "label:comparison", kind: "scene_label", name: "Comparison", geometry_asset_id: "asset:label", layer_ids: ["annotations:labels"] });
  source.scene.geometry_assets.push({ id: "asset:label", format: "label", bounds: [0, 0, 0, 0, 0, 0], object_ids: ["label:comparison"], generation_config: { text: "Comparison", position: [0, 0, 0], height: 0.2 } });
  source.scene.layers = [{ id: "annotations:labels", category: "annotations", label: "Labels", default_visible: true }];
  let previous = setLayerVisibility(createViewerState(source), "annotations:labels", false);

  previous = reduceViewerState(previous, { type: "setActiveLoadCase", loadCase: "Hot" });
  const preserved = preserveViewerStateForReload(previous, createViewerState(source));

  assert.equal(preserved.layers["annotations:labels"].visible, false);
  assert.equal(preserved.visibleObjectIds.includes("label:comparison"), false);
});

test("reduceViewerState handles setBodyOpacity action", () => {
  const state = createViewerState(bundle());
  const updated = reduceViewerState(state, {
    type: "setBodyOpacity",
    bodyId: "geometry",
    opacity: 0.35
  });
  assert.equal(updated.bodyOpacity.geometry, 0.35);
});
