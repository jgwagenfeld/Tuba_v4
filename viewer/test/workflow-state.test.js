import assert from "node:assert/strict";
import test from "node:test";
import * as workflowState from "../src/workflowState.js";

import {
  WORKFLOW_TABS,
  createWorkflowState,
  defaultWorkflowTab,
  getVisibleCockpitTaskIds,
  getVisibleWorkflowTabs,
  visibilityPresetForTask,
  workflowTabForKey,
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
      ["summary", "Review"],
      ["model", "Model"],
      ["load-cases", "Load Cases"],
      ["results", "Results"],
      ["diagnostics", "Issues"],
      ["3d", "Display"],
      ["compliance", "Compliance"]
    ]
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
    const visible = getVisibleWorkflowTabs(state);
    for (const id of getVisibleCockpitTaskIds(state)) {
      assert.ok(visible.includes(id), `cockpit task ${id} must be a visible workflow tab`);
    }
  }
  assert.deepEqual(getVisibleWorkflowTabs({ review: null }), ["model", "diagnostics"]);
  assert.equal(defaultWorkflowTab({ review: null, embed: false }), "model");
  assert.equal(createWorkflowState({ review: null, embed: false }).activeTab, "model");
});

test("embed still defaults to the 3d canvas destination", () => {
  assert.equal(defaultWorkflowTab({ review: reviewFixture, embed: true }), "3d");
  assert.equal(createWorkflowState({ review: reviewFixture, embed: true }).activeTab, "3d");
});

test("visibility presets hide analysis mesh everywhere and scope results/annotations per task", () => {
  assert.deepEqual(visibilityPresetForTask("summary"), {
    design: true, analysis_mesh: false, results: true, annotations: true
  });
  assert.deepEqual(visibilityPresetForTask("model"), {
    design: true, analysis_mesh: false, results: false, annotations: false
  });
  assert.deepEqual(visibilityPresetForTask("results"), {
    design: true, analysis_mesh: false, results: true, annotations: true
  });
  assert.deepEqual(visibilityPresetForTask("diagnostics"), {
    design: true, analysis_mesh: false, results: false, annotations: true
  });
  assert.equal(visibilityPresetForTask("3d"), null);
  assert.equal(visibilityPresetForTask("unknown"), null);
  assert.equal(visibilityPresetForTask("toString"), null);
  assert.equal(visibilityPresetForTask("constructor"), null);
});

test("workflow tab changes reject hidden and unknown tabs", () => {
  const legacyState = createWorkflowState({ review: null, embed: false });
  const reviewState = createWorkflowState({ review: reviewFixture, embed: false });

  assert.throws(() => setWorkflowTab(legacyState, "summary"), /not visible/i);
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

