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

test("full review workflow defaults to summary", () => {
  assert.equal(createWorkflowState({ review: reviewFixture, embed: false }).activeTab, "summary");
});

test("cockpit tasks are the four focused destinations in review mode", () => {
  assert.deepEqual(
    getVisibleCockpitTaskIds({ review: reviewFixture }),
    ["summary", "model", "results", "diagnostics"]
  );
});

test("legacy mode keeps model and issues tasks and defaults to model", () => {
  assert.deepEqual(getVisibleCockpitTaskIds({ review: null }), ["model", "diagnostics"]);
  assert.deepEqual(getVisibleWorkflowTabs({ review: null }), ["model", "diagnostics"]);
  assert.equal(defaultWorkflowTab({ review: null, embed: false }), "model");
  assert.equal(createWorkflowState({ review: null, embed: false }).activeTab, "model");
});

test("embed still defaults to the 3d canvas destination", () => {
  assert.equal(defaultWorkflowTab({ review: reviewFixture, embed: true }), "3d");
  assert.equal(createWorkflowState({ review: reviewFixture, embed: true }).activeTab, "3d");
});

test("visibility presets hide analysis mesh everywhere and scope results/overlays per task", () => {
  assert.deepEqual(visibilityPresetForTask("summary"), {
    geometry: true, analysis_mesh: false, results: true, overlays: true, envelopes: false
  });
  assert.deepEqual(visibilityPresetForTask("model"), {
    geometry: true, analysis_mesh: false, results: false, overlays: false, envelopes: false
  });
  assert.deepEqual(visibilityPresetForTask("results"), {
    geometry: true, analysis_mesh: false, results: true, overlays: true, envelopes: false
  });
  assert.deepEqual(visibilityPresetForTask("diagnostics"), {
    geometry: true, analysis_mesh: false, results: false, overlays: true, envelopes: false
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

  assert.equal(workflowTabForKey(state, "summary", "ArrowLeft"), "diagnostics");
  assert.equal(workflowTabForKey(state, "summary", "ArrowRight"), "model");
  assert.equal(workflowTabForKey(state, "diagnostics", "ArrowRight"), "summary");
});

test("workflow keyboard navigation supports Home and End in legacy mode", () => {
  const state = createWorkflowState({ review: null, embed: false });

  assert.equal(workflowTabForKey(state, "diagnostics", "Home"), "model");
  assert.equal(workflowTabForKey(state, "model", "End"), "diagnostics");
  assert.equal(workflowTabForKey(state, "model", "Enter"), null);
});

test("evidence keyboard navigation wraps and supports Home and End", () => {
  assert.equal(typeof workflowState.getVisibleEvidenceTabIds, "function");
  assert.equal(typeof workflowState.evidenceTabForKey, "function");
  const getVisibleEvidenceTabIds = workflowState.getVisibleEvidenceTabIds;
  const evidenceTabForKey = workflowState.evidenceTabForKey;
  const reviewState = { review: reviewFixture };

  assert.deepEqual(getVisibleEvidenceTabIds(reviewState), ["summary", "diagnostics", "compliance", "reports"]);
  assert.deepEqual(getVisibleEvidenceTabIds({ review: null }), ["diagnostics"]);
  assert.equal(evidenceTabForKey(reviewState, "summary", "ArrowLeft"), "reports");
  assert.equal(evidenceTabForKey(reviewState, "summary", "ArrowRight"), "diagnostics");
  assert.equal(evidenceTabForKey(reviewState, "reports", "ArrowRight"), "summary");
  assert.equal(evidenceTabForKey(reviewState, "diagnostics", "Home"), "summary");
  assert.equal(evidenceTabForKey(reviewState, "summary", "End"), "reports");
  assert.equal(evidenceTabForKey(reviewState, "summary", "Enter"), null);
  assert.equal(evidenceTabForKey(reviewState, "model", "ArrowRight"), null);
  assert.equal(evidenceTabForKey({ review: null }, "diagnostics", "ArrowRight"), "diagnostics");
});

test("evidence reload preserves visible tabs and falls back when a destination disappears", () => {
  assert.equal(typeof workflowState.evidenceTabForReload, "function");
  const evidenceTabForReload = workflowState.evidenceTabForReload;

  assert.equal(evidenceTabForReload({ review: reviewFixture }, "reports"), "reports");
  assert.equal(evidenceTabForReload({ review: reviewFixture }, "compliance"), "compliance");
  assert.equal(evidenceTabForReload({ review: null }, "reports"), "diagnostics");
  assert.equal(evidenceTabForReload({ review: reviewFixture }, "unknown"), "summary");
});
