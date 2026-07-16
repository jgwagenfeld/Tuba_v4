import assert from "node:assert/strict";
import test from "node:test";
import * as workflowState from "../src/workflowState.js";

import {
  WORKFLOW_TABS,
  createWorkflowState,
  getVisibleCockpitTaskIds,
  getVisibleWorkflowTabs,
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

test("legacy and embed workflow modes default to 3d", () => {
  assert.equal(createWorkflowState({ review: null, embed: false }).activeTab, "3d");
  assert.equal(createWorkflowState({ review: reviewFixture, embed: true }).activeTab, "3d");
});

test("legacy workflow hides data tabs but retains 3d and diagnostics", () => {
  assert.deepEqual(getVisibleWorkflowTabs({ review: null }), ["3d", "diagnostics"]);
  assert.deepEqual(getVisibleCockpitTaskIds({ review: null }), ["3d", "diagnostics"]);
});

test("cockpit tasks omit the evidence-only compliance destination", () => {
  assert.deepEqual(
    getVisibleCockpitTaskIds({ review: reviewFixture }),
    ["summary", "model", "load-cases", "results", "diagnostics", "3d"]
  );
});

test("workflow tab changes reject hidden and unknown tabs", () => {
  const legacyState = createWorkflowState({ review: null, embed: false });
  const reviewState = createWorkflowState({ review: reviewFixture, embed: false });

  assert.throws(() => setWorkflowTab(legacyState, "summary"), /not visible/i);
  assert.throws(() => setWorkflowTab(reviewState, "unknown"), /unknown workflow tab/i);
});

test("workflow keyboard navigation wraps across visible tabs", () => {
  const state = createWorkflowState({ review: reviewFixture, embed: false });

  assert.equal(workflowTabForKey(state, "summary", "ArrowLeft"), "3d");
  assert.equal(workflowTabForKey(state, "summary", "ArrowRight"), "model");
  assert.equal(workflowTabForKey(state, "diagnostics", "ArrowRight"), "3d");
});

test("workflow keyboard navigation supports Home and End in legacy mode", () => {
  const state = createWorkflowState({ review: null, embed: false });

  assert.equal(workflowTabForKey(state, "diagnostics", "Home"), "3d");
  assert.equal(workflowTabForKey(state, "3d", "End"), "diagnostics");
  assert.equal(workflowTabForKey(state, "3d", "Enter"), null);
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
