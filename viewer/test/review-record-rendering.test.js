import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { REVIEW_STATUSES, dispositionTally } from "../src/reviewRecord.js";

const app = readFileSync(new URL("../src/app.js", import.meta.url), "utf8");
const source = app.match(/^function renderReviewRecordExport\(\) \{[\s\S]*?^}/m)?.[0];
assert.ok(source, "the review record renderer must be present");
// The renderer is part of app.js's live bootstrap; execute its function without
// booting WebGL, connecting Studio, or opening a project.
const render = new Function("document", "currentState", "REVIEW_STATUSES", "dispositionTally",
  `${source}; return renderReviewRecordExport();`);
const document = { createElement: () => ({
  children: [], dataset: {}, append(...nodes) { this.children.push(...nodes); }, addEventListener() {}
}) };

function summary(reviewDispositions = {}, issues = []) {
  const rendered = render(document, { reviewDispositions, issues }, REVIEW_STATUSES, dispositionTally);
  return rendered.children[0].textContent;
}

test("the empty record explains how to record both issues and result findings", () => {
  assert.equal(summary(), "No dispositions recorded. Select an issue or result finding to record a decision.");
});

test("a reviewed result is counted as a finding even when the model has no issues", () => {
  assert.equal(summary({ "finding:Hot:e1": { status: "reviewing" } }), "1 reviewing across 1 result finding.");
});

test("mixed decisions count their actual subjects rather than dividing by current issues", () => {
  assert.equal(summary({
    "issue:removed": { status: "resolved" },
    "finding:Hot:e1": { status: "accepted" },
    "finding:Hot:e2": { status: "accepted" }
  }), "1 resolved · 2 accepted across 1 issue and 2 result findings.");
});

test("invalid legacy statuses do not inflate the recorded subject counts", () => {
  assert.equal(summary({
    "issue:1": { status: "reviewing" },
    "finding:Hot:e1": { status: "unknown" }
  }), "1 reviewing across 1 issue.");
});
