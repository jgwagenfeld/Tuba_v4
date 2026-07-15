import assert from "node:assert/strict";
import test from "node:test";

import {
  WORKFLOW_TABS,
  createWorkflowState,
  getVisibleWorkflowTabs,
  setWorkflowTab
} from "../src/workflowState.js";

const reviewFixture = {
  schema_version: "engineering_review.v1",
  analysis_status: "solved",
  tables: {}
};

test("workflow tabs follow the engineering review order", () => {
  assert.deepEqual(
    WORKFLOW_TABS.map((tab) => tab.id),
    ["summary", "model", "load-cases", "results", "compliance", "3d", "diagnostics"]
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
});

test("workflow tab changes reject hidden and unknown tabs", () => {
  const legacyState = createWorkflowState({ review: null, embed: false });
  const reviewState = createWorkflowState({ review: reviewFixture, embed: false });

  assert.throws(() => setWorkflowTab(legacyState, "summary"), /not visible/i);
  assert.throws(() => setWorkflowTab(reviewState, "unknown"), /unknown workflow tab/i);
});
