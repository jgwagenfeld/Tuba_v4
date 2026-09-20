import assert from "node:assert/strict";
import test from "node:test";

import {
  COLOR_CHANNELS,
  STAGES,
  colorChannelOf,
  createWorkflowState,
  openingStage,
  sceneStage,
  visibilityPresetForStage,
  workspaceView
} from "../src/workflowState.js";

const reviewFixture = {
  schema_version: "engineering_review.v1",
  analysis_status: "solved",
  tables: {}
};

// The stage is carried by the scene state; the session holds only what is
// genuinely per-session, which is whether the reader has collapsed the rail.
const at = (state, stage, extra = {}) => ({ ...state, stage, ...extra });
const session = (railExpanded = true) => ({ railExpanded });

test("visibility presets are stage-scoped: only Build rewrites layers", () => {
  // Build keeps the analysis mesh: in a volume or mesh review the mesh is the
  // model, and there is no procedural geometry to show in its place.
  assert.deepEqual(visibilityPresetForStage("build"), {
    design: true, analysis_mesh: true, results: false, annotations: false
  });
  // Review carries none. Its rail sections change what is shown beside the
  // viewport, never what is drawn on it.
  for (const stage of ["review", "embed", "3d", "unknown", "toString", "constructor"]) {
    assert.equal(visibilityPresetForStage(stage), null);
  }
});

test("the colouring channel is explicit, defaulting by scene content", () => {
  assert.deepEqual(COLOR_CHANNELS, ["model", "results"]);
  assert.equal(colorChannelOf({ colorChannel: "model" }), "model");
  assert.equal(colorChannelOf({ colorChannel: "results" }), "results");
  // A scene with a field catalogue, result states, or legacy solver overlays
  // opens on results; a bare model opens on its own properties.
  assert.equal(colorChannelOf({}), "model");
  assert.equal(colorChannelOf({ resultFields: [{ id: "f" }] }), "results");
  assert.equal(colorChannelOf({ resultStates: [{ id: "s" }] }), "results");
  assert.equal(colorChannelOf({ overlays: [{ kind: "solver_result" }] }), "results");
  assert.equal(colorChannelOf({ overlays: [{ kind: "result_state" }] }), "results");
  assert.equal(colorChannelOf({ overlays: [{ kind: "clash" }] }), "model");
  // An explicit channel wins over the default.
  assert.equal(colorChannelOf({ colorChannel: "model", resultFields: [{ id: "f" }] }), "model");
});

test("the embedded canvas is a stage of its own and outranks every other", () => {
  const state = createWorkflowState({ review: reviewFixture, embed: true });

  // Even a scene staged for Build renders as the bare embedded canvas.
  const view = workspaceView(at(state, "build"), session());
  assert.equal(view.stage, "embed");
  assert.equal(view.railVisible, false);
  assert.equal(view.scriptVisible, false);
  assert.equal(view.headerVisible, false);
});

test("the stage is whatever the scene state says it is", () => {
  const state = createWorkflowState({ review: reviewFixture, embed: false });

  assert.equal(sceneStage(at(state, "build")), "build");
  assert.equal(sceneStage(at(state, "review")), "review");
  // A bundle that has never been staged is a review, and an unknown stage is
  // not honoured rather than being passed through to the renderer.
  assert.equal(sceneStage(state), "review");
  assert.equal(sceneStage(at(state, "nonsense")), "review");
  assert.deepEqual(STAGES, ["embed", "build", "review"]);
});

test("a bundle that was never staged is simply a review", () => {
  const state = createWorkflowState({ review: reviewFixture, embed: false });
  const view = workspaceView(state, session());

  assert.equal(view.stage, "review");
  assert.equal(view.railVisible, true);
  assert.equal(view.scriptVisible, false);
});

test("the rail belongs to the review stage, and a collapsed rail keeps its toggle", () => {
  const state = createWorkflowState({ review: reviewFixture, embed: false });

  const build = workspaceView(at(state, "build"), session());
  assert.equal(build.railVisible, false, "Build gives the rail's column to the script");
  assert.equal(build.scriptVisible, true);
  // The toggle is the rail's control, so it goes where the rail goes; in Build
  // there is no rail to toggle.
  assert.equal(build.railToggleVisible, false);

  const collapsed = workspaceView(at(state, "review"), session(false));
  assert.equal(collapsed.railVisible, false, "a collapsed rail is hidden");
  assert.equal(collapsed.railToggleVisible, true, "but its toggle stays, or it could never reopen");
  assert.equal(collapsed.scriptVisible, false, "collapsing the rail does not open the script");
});

test("the stage picks the layer preset", () => {
  const state = createWorkflowState({ review: reviewFixture, embed: false });

  assert.equal(workspaceView(at(state, "build"), session()).visibility, "build");
  // Review has no preset: its sections leave the scene as the bundle declared it.
  assert.equal(workspaceView(at(state, "review"), session()).visibility, null);
  assert.equal(
    workspaceView(createWorkflowState({ review: reviewFixture, embed: true }), session()).visibility,
    null,
    "the embedded scene is shown as the bundle declared it"
  );
});

test("the review bundle is only loaded where a review is both wanted and present", () => {
  const state = createWorkflowState({ review: reviewFixture, embed: false });

  assert.equal(workspaceView(at(state, "review"), { ...session(), studio: { hasReview: true } }).bundle, "review");
  assert.equal(workspaceView(at(state, "build"), { ...session(), studio: { hasReview: true } }).bundle, "build");
  assert.equal(
    workspaceView(at(state, "review"), { ...session(), studio: { hasReview: false } }).bundle,
    "build",
    "Review with nothing solved still shows the live model"
  );
});

test("a studio opens on a current review and on the script for anything else", () => {
  assert.equal(openingStage({ hasReview: true, reviewStale: false }), "review");
  assert.equal(openingStage({ hasReview: true, reviewStale: true }), "build");
  assert.equal(openingStage({ hasReview: false, reviewStale: false }), "build");
  assert.equal(openingStage({}), "build");
});
