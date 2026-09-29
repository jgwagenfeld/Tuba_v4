import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_REVIEW_STATUS,
  REVIEW_RECORD_SCHEMA,
  REVIEW_STATUSES,
  dispositionFor,
  dispositionRefusal,
  dispositionTally,
  isReviewStatus,
  recordDisposition,
  reviewRecordCsv,
  reviewStatus,
  toReviewRecord
} from "../src/reviewRecord.js";
import { reduceViewerState } from "../src/viewerState.js";

function state(issues = [{ id: "issue:1", type: "clash", title: "Operating clash", severity: "error", entity_refs: ["element:e1"] }]) {
  return {
    issues,
    sceneId: "scene:review",
    activeLoadCase: "Hot",
    activeResultStateId: "result_state:Hot",
    issueReviewState: {}
  };
}

const at = (minutes) => `2026-09-29T10:0${minutes}:00.000Z`;

test("the five statuses read as a progression, and only waived needs a reason", () => {
  assert.deepEqual(REVIEW_STATUSES.map((status) => status.id), ["open", "reviewing", "resolved", "accepted", "waived"]);
  assert.deepEqual(REVIEW_STATUSES.filter((status) => status.requiresReason).map((status) => status.id), ["waived"]);
  assert.equal(isReviewStatus("waived"), true);
  assert.equal(isReviewStatus("nope"), false);
  assert.equal(reviewStatus("accepted").label, "Accepted");
  assert.equal(reviewStatus("nope"), null);
  assert.equal(DEFAULT_REVIEW_STATUS, "open");
});

test("a waiver without a reason is refused, and refused before anything is written", () => {
  const refusal = dispositionRefusal({ status: "waived", comment: "   " });
  assert.match(refusal, /Waived needs a reason/);
  // The state must be untouched: a half-valid record is worse than no record.
  const before = state();
  assert.equal(recordDisposition(before, { issueId: "issue:1", status: "waived", comment: "" }), before);
  assert.equal(recordDisposition(before, { issueId: "issue:1", status: "waived" }), before);
  assert.deepEqual(before.issueReviewState, {});
});

test("a waiver with a reason is recorded", () => {
  const recorded = recordDisposition(state(), {
    issueId: "issue:1",
    status: "waived",
    comment: "Rack column is inside the code envelope; accepted by the owner on 2026-09-29.",
    author: "J. Georg",
    at: at(0)
  });
  const disposition = dispositionFor(recorded, "issue:1");
  assert.equal(disposition.status, "waived");
  assert.equal(disposition.author, "J. Georg");
  assert.equal(disposition.transitions.length, 1);
});

test("an unknown status is refused rather than written", () => {
  assert.match(dispositionRefusal({ status: "fine-ish", comment: "x" }), /Unknown review status/);
  const before = state();
  assert.equal(recordDisposition(before, { issueId: "issue:1", status: "fine-ish" }), before);
});

test("history is kept, so an item examined and re-opened still shows it", () => {
  // Overwriting `status` loses the fact that an item was looked at and then sent
  // back, which is usually the interesting part of a review.
  let recorded = recordDisposition(state(), { issueId: "issue:1", status: "reviewing", author: "A", at: at(1) });
  recorded = recordDisposition(recorded, { issueId: "issue:1", status: "resolved", author: "A", at: at(2) });
  recorded = recordDisposition(recorded, { issueId: "issue:1", status: "open", comment: "Owner reopened", author: "B", at: at(3) });
  const disposition = dispositionFor(recorded, "issue:1");
  assert.equal(disposition.status, "open");
  assert.equal(disposition.transitions.length, 3);
  assert.deepEqual(disposition.transitions.map((transition) => transition.status), ["reviewing", "resolved", "open"]);
  assert.equal(disposition.author, "B");
});

test("re-selecting the status a reviewer is already on records nothing", () => {
  // A log with one entry per render click is a log nobody reads.
  const once = recordDisposition(state(), { issueId: "issue:1", status: "reviewing", author: "A", at: at(1) });
  const twice = recordDisposition(once, { issueId: "issue:1", status: "reviewing", author: "A", at: at(1) });
  assert.equal(twice, once);
  assert.equal(dispositionFor(twice, "issue:1").transitions.length, 1);
});

test("editing a comment is itself a recorded change", () => {
  const recorded = recordDisposition(state(), { issueId: "issue:1", status: "open", comment: "first", at: at(1) });
  const edited = recordDisposition(recorded, { issueId: "issue:1", comment: "second", at: at(2) });
  assert.equal(dispositionFor(edited, "issue:1").comment, "second");
  assert.equal(dispositionFor(edited, "issue:1").transitions.length, 2);
});

test("a partial change keeps the fields it does not mention", () => {
  const recorded = recordDisposition(state(), {
    issueId: "issue:1",
    status: "accepted",
    comment: "fits within the owner's envelope",
    author: "A",
    at: at(1)
  });
  const later = recordDisposition(recorded, { issueId: "issue:1", status: "reviewing" });
  assert.equal(dispositionFor(later, "issue:1").comment, "fits within the owner's envelope");
  assert.equal(dispositionFor(later, "issue:1").author, "A");
});

test("a change with no issue id is not a change", () => {
  const before = state();
  assert.equal(recordDisposition(before, { status: "resolved" }), before);
  assert.equal(dispositionFor(before, "issue:1"), null);
});

test("the tally counts by status and reports how many were touched at all", () => {
  let recorded = state([
    { id: "issue:1" },
    { id: "issue:2" },
    { id: "issue:3" }
  ]);
  recorded = recordDisposition(recorded, { issueId: "issue:1", status: "resolved" });
  recorded = recordDisposition(recorded, { issueId: "issue:2", status: "waived", comment: "owner accepted" });
  const tally = dispositionTally(recorded);
  assert.equal(tally.resolved, 1);
  assert.equal(tally.waived, 1);
  assert.equal(tally.open, 0);
  assert.equal(tally.touched, 2);
  // An untouched issue is not an "open" disposition; it is an untriaged issue,
  // and conflating the two would overstate how much review has happened.
  assert.equal(dispositionTally(state()).touched, 0);
});

test("the record is attributed, and says the attribution is self-declared", () => {
  const recorded = recordDisposition({ ...state(), reviewerName: "J. Georg" }, {
    issueId: "issue:1",
    status: "accepted",
    at: at(1)
  });
  const record = toReviewRecord(recorded, { at: at(9) });
  assert.equal(record.schema, REVIEW_RECORD_SCHEMA);
  assert.equal(record.author, "J. Georg");
  // A static bundle has no authentication. A record implying a signed identity
  // would be claiming something this viewer cannot support.
  assert.equal(record.author_is_self_declared, true);
  assert.equal(record.scene_id, "scene:review");
  assert.equal(record.load_case, "Hot");
});

test("the record joins a disposition to the issue it is about", () => {
  const recorded = recordDisposition(state(), { issueId: "issue:1", status: "resolved", at: at(1) });
  const record = toReviewRecord(recorded, { at: at(9) });
  assert.equal(record.dispositions.length, 1);
  const [entry] = record.dispositions;
  assert.equal(entry.issue_id, "issue:1");
  assert.equal(entry.type, "clash");
  assert.equal(entry.title, "Operating clash");
  assert.equal(entry.severity, "error");
  // The address is what makes a disposition traceable back to a result rather
  // than being an opinion about a row number in a table that has since sorted.
  assert.deepEqual(entry.entity_refs, ["element:e1"]);
  assert.equal(entry.transition_count, 1);
});

test("an issue with no disposition is not in the record", () => {
  const record = toReviewRecord(state([{ id: "issue:1" }, { id: "issue:2" }]), { at: at(9) });
  assert.deepEqual(record.dispositions, []);
  assert.equal(record.summary.touched, 0);
});

test("the record is ordered most recently recorded first", () => {
  let recorded = state([{ id: "issue:1" }, { id: "issue:2" }]);
  recorded = recordDisposition(recorded, { issueId: "issue:1", status: "resolved", at: at(1) });
  recorded = recordDisposition(recorded, { issueId: "issue:2", status: "accepted", at: at(5) });
  const record = toReviewRecord(recorded, { at: at(9) });
  assert.deepEqual(record.dispositions.map((entry) => entry.issue_id), ["issue:2", "issue:1"]);
});

test("the CSV is a spreadsheet, with a waiver reason that contains a comma and a quote", () => {
  // A waiver reason is free text typed into a comment box. Unescaped it silently
  // shifts every column after it, which is the exact failure that makes a review
  // record untrustworthy - so the whole row is pinned rather than counted.
  const recorded = recordDisposition(state(), {
    issueId: "issue:1",
    status: "waived",
    comment: 'Owner accepted: "column is in the envelope", see note 4',
    author: "A",
    at: at(1)
  });
  const csv = reviewRecordCsv(toReviewRecord(recorded, { at: at(9) }));
  assert.equal(csv, [
    "issue_id,type,title,severity,status,comment,author,recorded_at,transition_count,entity_refs",
    'issue:1,clash,Operating clash,error,waived,"Owner accepted: ""column is in the envelope"", see note 4",A,2026-09-29T10:01:00.000Z,1,"[""element:e1""]"'
  ].join("\n"));
  // And every one of the ten columns survives the round trip intact, which a
  // comma-count cannot tell you - splitting on the delimiter would split inside
  // the very quotes that protect it.
  assert.deepEqual(csvFields(csv)[1], [
    "issue:1", "clash", "Operating clash", "error", "waived",
    'Owner accepted: "column is in the envelope", see note 4', "A", "2026-09-29T10:01:00.000Z", "1", '["element:e1"]'
  ]);
});

test("the CSV escapes a newline typed into a comment", () => {
  const recorded = recordDisposition(state(), {
    issueId: "issue:1",
    status: "resolved",
    comment: "line one\nline two",
    at: at(1)
  });
  const csv = reviewRecordCsv(toReviewRecord(recorded, { at: at(9) }));
  // A raw newline would end the record early and start a new, unheaded row that
  // every spreadsheet reads as a second disposition.
  assert.equal(csvFields(csv).length, 2, "header plus exactly one disposition");
  assert.equal(csvFields(csv)[1][5], "line one\nline two");
});

test("the CSV renders an empty record as a header, and no record as nothing", () => {
  // A review with nothing triaged is a real state and gets a header; a caller
  // that passes no record at all has a bug and gets an empty file rather than
  // one that downloads cleanly and reads as a review of nothing.
  assert.equal(reviewRecordCsv(toReviewRecord(state(), { at: at(9) })), "issue_id,type,title,severity,status,comment,author,recorded_at,transition_count,entity_refs");
  assert.equal(reviewRecordCsv(null), "");
});

// A minimal RFC 4180 reader, so the tests can assert on what a spreadsheet would
// actually see rather than on the byte count of a delimiter that is also a legal
// character inside a quoted field.
function csvFields(text) {
  const rows = [];
  let row = [];
  let field = "";
  let quoted = false;
  for (let index = 0; index < text.length; index += 1) {
    const character = text[index];
    if (quoted) {
      if (character === '"') {
        if (text[index + 1] === '"') {
          field += '"';
          index += 1;
        } else {
          quoted = false;
        }
      } else {
        field += character;
      }
      continue;
    }
    if (character === '"') quoted = true;
    else if (character === ",") {
      row.push(field);
      field = "";
    } else if (character === "\n") {
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
    } else field += character;
  }
  if (field !== "" || row.length > 0) {
    row.push(field);
    rows.push(row);
  }
  return rows;
}

test("the reducer routes the old status and comment actions through the record", () => {
  // Anything already dispatching setIssueReviewStatus must get attribution and
  // history too, rather than overwriting a bare field.
  let reduced = reduceViewerState({ ...state(), reviewerName: "A" }, {
    type: "setIssueReviewStatus",
    issueId: "issue:1",
    status: "reviewing"
  });
  assert.deepEqual(reduced.issueReviewState["issue:1"].transitions.map((entry) => entry.status), ["reviewing"]);
  assert.equal(reduced.issueReviewState["issue:1"].author, "A");
  reduced = reduceViewerState(reduced, { type: "setIssueReviewComment", issueId: "issue:1", comment: "note" });
  assert.equal(reduced.issueReviewState["issue:1"].comment, "note");
  assert.equal(reduced.issueReviewState["issue:1"].transitions.length, 2);
});

test("the reducer refuses a waiver with no reason rather than writing one", () => {
  const before = reduceViewerState({ ...state(), reviewerName: "A" }, {
    type: "setIssueReviewStatus",
    issueId: "issue:1",
    status: "reviewing"
  });
  const after = reduceViewerState(before, {
    type: "recordDisposition",
    issueId: "issue:1",
    status: "waived",
    comment: "  "
  });
  assert.equal(after, before);
});

test("the reviewer name is trimmed, and a blank one clears it", () => {
  const named = reduceViewerState(state(), { type: "setReviewerName", name: "  J. Georg  " });
  assert.equal(named.reviewerName, "J. Georg");
  assert.equal(reduceViewerState(named, { type: "setReviewerName", name: "   " }).reviewerName, null);
});
