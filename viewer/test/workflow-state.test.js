import assert from "node:assert/strict";
import test from "node:test";
import * as workflowState from "../src/workflowState.js";

import {
  WORKFLOW_TABS,
  createWorkflowState,
  EMBED_TASK_ID,
  defaultWorkflowTab,
  getVisibleCockpitTaskIds,
  openingStage,
  visibilityPresetForTask,
  workflowTabForKey,
  workspaceView,
  setWorkflowTab
} from "../src/workflowState.js";

const reviewFixture = {
  schema_version: "engineering_review.v1",
  analysis_status: "solved",
  tables: {}
};

test("workflow tabs follow the engineering review order", () => {
  assert.deepEqual(
    WORKFLOW_TABS.map(({ id, label }) => [id, label]),
    [
      ["model", "Model"],
      ["results", "Results"],
      ["diagnostics", "Issues"]
    ]
  );
});

test("the embed destination is not a tab the rail could ever offer", () => {
  // It was a fourth WORKFLOW_TABS entry labelled "Display": the only one
  // getVisibleCockpitTaskIds could never return, so the rail could not show it
  // and setWorkflowTab would have thrown on it. It is a real state, not a tab.
  assert.equal(EMBED_TASK_ID, "3d");
  assert.equal(WORKFLOW_TABS.find((tab) => tab.id === EMBED_TASK_ID), undefined);
  assert.throws(
    () => setWorkflowTab(createWorkflowState({ review: reviewFixture, embed: false }), EMBED_TASK_ID),
    RangeError
  );
});

test("full review workflow defaults to the model task", () => {
  // The review's tables live in the generated report now, so the rail opens on
  // what you can actually do to the scene.
  assert.equal(createWorkflowState({ review: reviewFixture, embed: false }).activeTab, "model");
});

test("cockpit tasks are the three focused destinations in review mode", () => {
  assert.deepEqual(
    getVisibleCockpitTaskIds({ review: reviewFixture }),
    ["model", "results", "diagnostics"]
  );
});

test("legacy mode keeps model and issues tasks and defaults to model", () => {
  assert.deepEqual(getVisibleCockpitTaskIds({ review: null }), ["model", "diagnostics"]);
  // Without a review the Results task is still the only home of the coloring
  // channel, so a scene that carries fields must keep it.
  assert.deepEqual(
    getVisibleCockpitTaskIds({ review: null, resultFields: [{ id: "field:stress" }] }),
    ["model", "results", "diagnostics"]
  );
  assert.deepEqual(
    getVisibleCockpitTaskIds({ review: null, resultStates: [{ id: "state:Operating" }] }),
    ["model", "results", "diagnostics"]
  );
  // The rail must never offer a task setWorkflowTab would reject.
  for (const state of [
    { review: null },
    { review: null, resultFields: [{ id: "field:stress" }] },
    { review: reviewFixture }
  ]) {
    for (const id of getVisibleCockpitTaskIds(state)) {
      assert.doesNotThrow(() => setWorkflowTab(state, id), `cockpit task ${id} must be a visible workflow tab`);
    }
  }
  assert.equal(defaultWorkflowTab({ review: null, embed: false }), "model");
  assert.equal(createWorkflowState({ review: null, embed: false }).activeTab, "model");
});

test("embed still defaults to the 3d canvas destination", () => {
  assert.equal(defaultWorkflowTab({ review: reviewFixture, embed: true }), EMBED_TASK_ID);
  assert.equal(createWorkflowState({ review: reviewFixture, embed: true }).activeTab, EMBED_TASK_ID);
});

test("visibility presets hide analysis mesh in the review tasks and scope results/annotations", () => {
  assert.deepEqual(visibilityPresetForTask("model"), {
    design: true, analysis_mesh: false, results: false, annotations: false
  });
  assert.deepEqual(visibilityPresetForTask("results"), {
    design: true, analysis_mesh: false, results: true, annotations: true
  });
  assert.deepEqual(visibilityPresetForTask("diagnostics"), {
    design: true, analysis_mesh: false, results: false, annotations: true
  });
  // Build keeps the analysis mesh: in a volume or mesh review the mesh is the
  // model, and there is no procedural geometry to show in its place.
  assert.deepEqual(visibilityPresetForTask("build"), {
    design: true, analysis_mesh: true, results: false, annotations: false
  });
  assert.equal(visibilityPresetForTask("3d"), null);
  assert.equal(visibilityPresetForTask("unknown"), null);
  assert.equal(visibilityPresetForTask("toString"), null);
  assert.equal(visibilityPresetForTask("constructor"), null);
});

test("workflow tab changes reject hidden and unknown tabs", () => {
  const legacyState = createWorkflowState({ review: null, embed: false });
  const reviewState = createWorkflowState({ review: reviewFixture, embed: false });

  assert.throws(() => setWorkflowTab(legacyState, "results"), /not visible/i);
  assert.throws(() => setWorkflowTab(reviewState, "unknown"), /unknown workflow tab/i);
});

test("workflow keyboard navigation wraps across visible tabs", () => {
  const state = createWorkflowState({ review: reviewFixture, embed: false });

  assert.equal(workflowTabForKey(state, "model", "ArrowLeft"), "diagnostics");
  assert.equal(workflowTabForKey(state, "model", "ArrowRight"), "results");
  assert.equal(workflowTabForKey(state, "diagnostics", "ArrowRight"), "model");
});

test("workflow keyboard navigation supports Home and End in legacy mode", () => {
  const state = createWorkflowState({ review: null, embed: false });

  assert.equal(workflowTabForKey(state, "diagnostics", "Home"), "model");
  assert.equal(workflowTabForKey(state, "model", "End"), "diagnostics");
  assert.equal(workflowTabForKey(state, "model", "Enter"), null);
});

// --- the stage tree -------------------------------------------------------
//
// Build and the embedded canvas are not tasks, and pretending they were is what
// these tests exist to stop coming back. The rail's three tasks live *inside*
// the review stage; Build is a sibling of that whole stage, not a fourth tab.

const studioSession = (studio = {}, extra = {}) => ({
  studio: { available: true, mode: "review", hasReview: true, reviewStale: false, ...studio },
  sourceView: { available: false, mode: "review" },
  railExpanded: true,
  ...extra
});

const publishedSession = (mode = "review") => ({
  studio: { available: false, mode: "review", hasReview: false, reviewStale: false },
  sourceView: { available: true, mode },
  railExpanded: true
});

test("the embedded canvas is a stage of its own and outranks every other", () => {
  const state = createWorkflowState({ review: reviewFixture, embed: true });

  // Even a studio sitting in Build renders as the bare embedded scene.
  const view = workspaceView(state, studioSession({ mode: "build" }));
  assert.equal(view.stage, "embed");
  assert.equal(view.railVisible, false);
  assert.equal(view.scriptVisible, false);
  assert.equal(view.headerVisible, false);
});

test("a studio's stage is its own mode, a published bundle's is its source view", () => {
  const state = createWorkflowState({ review: reviewFixture, embed: false });

  assert.equal(workspaceView(state, studioSession({ mode: "build" })).stage, "build");
  assert.equal(workspaceView(state, studioSession({ mode: "review" })).stage, "review");
  assert.equal(workspaceView(state, publishedSession("build")).stage, "build");
  assert.equal(workspaceView(state, publishedSession("review")).stage, "review");
});

test("a bundle with neither a studio nor a source view is simply a review", () => {
  const state = createWorkflowState({ review: reviewFixture, embed: false });
  const view = workspaceView(state, {
    studio: { available: false },
    sourceView: { available: false },
    railExpanded: true
  });

  assert.equal(view.stage, "review");
  assert.equal(view.railVisible, true);
  assert.equal(view.scriptVisible, false);
});

test("the rail belongs to the review stage, and a collapsed rail keeps its toggle", () => {
  const state = createWorkflowState({ review: reviewFixture, embed: false });

  const build = workspaceView(state, studioSession({ mode: "build" }));
  assert.equal(build.railVisible, false, "Build gives the rail's column to the script");
  assert.equal(build.scriptVisible, true);
  // The toggle is the rail's control, so it goes where the rail goes; in Build
  // there is no rail to toggle.
  assert.equal(build.railToggleVisible, false);

  const collapsed = workspaceView(state, studioSession({ mode: "review" }, { railExpanded: false }));
  assert.equal(collapsed.railVisible, false, "a collapsed rail is hidden");
  assert.equal(collapsed.railToggleVisible, true, "but its toggle stays, or it could never reopen");
  assert.equal(collapsed.scriptVisible, false, "collapsing the rail does not open the script");
});

test("tasks exist only inside the review stage", () => {
  const state = createWorkflowState({ review: reviewFixture, embed: false });

  const review = workspaceView(state, studioSession({ mode: "review" }));
  assert.equal(review.task, "model");
  assert.deepEqual(review.tabs, ["model", "results", "diagnostics"]);

  for (const view of [
    workspaceView(state, studioSession({ mode: "build" })),
    workspaceView(createWorkflowState({ review: reviewFixture, embed: true }), studioSession())
  ]) {
    assert.equal(view.task, null, "no task is active outside the review stage");
    assert.deepEqual(view.tabs, [], "and the rail offers none");
  }
});

test("the stage picks the layer preset, so Build stops posing as the Model task", () => {
  const state = createWorkflowState({ review: reviewFixture, embed: false });

  // Was: dispatch enterBuild, which set activeTab "model" - a lie, since the
  // reader is in Build - and then looked "build" up in a table keyed by task.
  assert.equal(workspaceView(state, studioSession({ mode: "build" })).visibility, "build");
  assert.equal(workspaceView(state, studioSession({ mode: "review" })).visibility, "model");
  assert.equal(
    workspaceView(createWorkflowState({ review: reviewFixture, embed: true }), studioSession()).visibility,
    null,
    "the embedded scene is shown as the bundle declared it"
  );
});

test("the review bundle is only loaded where a review is both wanted and present", () => {
  const state = createWorkflowState({ review: reviewFixture, embed: false });

  assert.equal(workspaceView(state, studioSession({ mode: "review" })).bundle, "review");
  assert.equal(workspaceView(state, studioSession({ mode: "build" })).bundle, "build");
  assert.equal(
    workspaceView(state, studioSession({ mode: "review", hasReview: false })).bundle,
    "build",
    "Results with nothing solved still shows the live model"
  );
});

test("the rail never marks current a task it is not offering", () => {
  // Reachable by swapping bundles: the reader is on Results, switches to Build,
  // edits until the review goes stale, and the live model carries no results.
  // The caller used to have to notice - preserveViewerStateForReload holds the
  // same rule - so the derived view could disagree with the rail beside it.
  const state = { ...createWorkflowState({ review: null, embed: false }), activeTab: "results" };
  const view = workspaceView(state, studioSession({ mode: "review", hasReview: false }));

  assert.deepEqual(view.tabs, ["model", "diagnostics"]);
  assert.equal(view.task, "model", "falls back to the first task the rail actually offers");
  assert.ok(view.tabs.includes(view.task), "the active task is always one of the offered tabs");
  assert.equal(view.visibility, "model", "and the layer preset follows the task that is really active");
});

test("a studio opens on a current review and on the script for anything else", () => {
  // The rule that used to be hardcoded in initStudio, where testing it meant
  // driving a browser and intercepting the project request.
  assert.equal(openingStage({ hasReview: true, reviewStale: false }), "review");
  assert.equal(openingStage({ hasReview: true, reviewStale: true }), "build");
  assert.equal(openingStage({ hasReview: false, reviewStale: false }), "build");
  assert.equal(openingStage({}), "build");
});

