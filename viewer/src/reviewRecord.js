// The review record: what the engineer decided, and who decided it.
//
// No tool in the piping category can do this. AutoPIPE has node annotations - a
// label attached to a point - and an image gallery; CAEPIPE has a QA block, which
// is a report section rather than a workflow; Codeware generates a deficiency
// summary nobody authored. Nothing in the benchmark can mark an item *under
// review*, *fixed*, *accepted* or *waived*, attach a reason, record who did it,
// or hand the result to anyone. E3D and Tekla get closest, by diffing two model
// versions and marking changed/new/deleted - and that is tied to CAD objects, not
// to stress results.
//
// What already existed here was a status select and a comment box on the active
// issue. That is an opinion. Three things turn it into a record:
//
//   - **Attribution.** A disposition with no author and no date is a shrug.
//   - **History.** Overwriting `status` loses the fact that an item was examined
//     and then re-opened, which is usually the interesting part.
//   - **A way out.** Dispositions that die with the tab answer no one's
//     question. The export is the deliverable; the checkbox is not.
//
// Two things it deliberately does not claim. The author is **self-declared**:
// this is a static bundle with no authentication, and a record implying a signed
// identity would be a claim the product cannot support. And `waived` **requires a
// justification**, because it is the one status that overrides something - a
// waived clash is still a clash, and the reason is the only thing that survives
// review of the review.

export const REVIEW_RECORD_SCHEMA = "tuba.review_record.v1";

// Ordered so the list reads as a progression. `requiresReason` is the whole
// reason `waived` is not interchangeable with `accepted`: accepting a condition
// is a decision to live with it, and waiving one is a decision to ignore it.
export const REVIEW_STATUSES = Object.freeze([
  { id: "open", label: "Open", requiresReason: false, description: "Not yet examined." },
  { id: "reviewing", label: "Reviewing", requiresReason: false, description: "Being examined now." },
  { id: "resolved", label: "Resolved", requiresReason: false, description: "Fixed, by a change to the model." },
  { id: "accepted", label: "Accepted", requiresReason: false, description: "Examined and accepted as it stands." },
  { id: "waived", label: "Waived", requiresReason: true, description: "Examined and set aside. Needs a reason." }
]);

export const DEFAULT_REVIEW_STATUS = "open";

export function reviewStatus(id) {
  return REVIEW_STATUSES.find((status) => status.id === id) ?? null;
}

export function isReviewStatus(id) {
  return REVIEW_STATUSES.some((status) => status.id === id);
}

// Why a change cannot be recorded, or null when it can. Kept separate from the
// writer so the UI can refuse *before* the reviewer loses what they typed, and
// so the rule is testable without a form.
export function dispositionRefusal({ status, comment }) {
  if (!isReviewStatus(status)) {
    return `Unknown review status ${JSON.stringify(status)}.`;
  }
  const declaration = reviewStatus(status);
  if (declaration.requiresReason && !String(comment ?? "").trim()) {
    return `${declaration.label} needs a reason. A waiver that cannot say what it waived is not a record.`;
  }
  return null;
}

export function recordDisposition(state, change) {
  const issueId = change?.issueId;
  if (!issueId) {
    return state;
  }
  const existing = state.issueReviewState?.[issueId] ?? {};
  const status = change.status ?? existing.status ?? DEFAULT_REVIEW_STATUS;
  const comment = change.comment ?? existing.comment ?? "";
  if (dispositionRefusal({ status, comment })) {
    // A refusal leaves state untouched rather than writing a half-valid record.
    return state;
  }
  const at = change.at ?? null;
  const author = change.author ?? existing.author ?? null;
  const transition = { status, comment, author, at };
  // A transition is only recorded when something actually moved. Re-selecting the
  // status a reviewer is already on is not an event, and a log of one entry per
  // render click is a log nobody reads.
  const last = transitionsOf(existing).at(-1);
  if (last && sameTransition(last, transition)) {
    return state;
  }
  return {
    ...state,
    issueReviewState: {
      ...(state.issueReviewState ?? {}),
      [issueId]: {
        ...existing,
        status,
        comment,
        author,
        at,
        transitions: [...transitionsOf(existing), transition]
      }
    }
  };
}

export function dispositionFor(state, issueId) {
  const record = state.issueReviewState?.[issueId];
  if (!record) {
    return null;
  }
  return {
    issueId,
    status: record.status ?? DEFAULT_REVIEW_STATUS,
    comment: record.comment ?? "",
    author: record.author ?? null,
    at: record.at ?? null,
    transitions: transitionsOf(record)
  };
}

export function dispositionTally(state) {
  const tally = Object.fromEntries(REVIEW_STATUSES.map((status) => [status.id, 0]));
  let touched = 0;
  for (const record of Object.values(state.issueReviewState ?? {})) {
    const status = record?.status;
    if (status in tally) {
      tally[status] += 1;
      touched += 1;
    }
  }
  return { ...tally, touched };
}

// The export. A record that names the bundle it came from, because a
// disposition list detached from the review that produced it is a list of
// opinions about nothing.
export function toReviewRecord(state, { scene = null, at = null } = {}) {
  const issues = new Map((state.issues ?? []).map((issue) => [issue.id, issue]));
  const dispositions = Object.entries(state.issueReviewState ?? {})
    .filter(([issueId, record]) => issueId && record && transitionsOf(record).length > 0)
    .map(([issueId, record]) => dispositionEntry(issueId, record, issues.get(issueId)))
    .sort((left, right) => (right.recorded_at ?? "").localeCompare(left.recorded_at ?? ""));
  return {
    schema: REVIEW_RECORD_SCHEMA,
    // Self-declared, and said so. A static bundle has no authentication, and a
    // record that implied a signed identity would be claiming something this
    // viewer cannot support.
    author: state.reviewerName ?? null,
    author_is_self_declared: true,
    generated_at: at,
    scene_id: scene?.id ?? state.sceneId ?? null,
    model_id: scene?.id ?? null,
    load_case: state.activeLoadCase ?? null,
    result_state_id: state.activeResultStateId ?? null,
    dispositions,
    summary: dispositionTally(state)
  };
}

function dispositionEntry(issueId, record, issue) {
  const transitions = transitionsOf(record);
  const latest = transitions.at(-1);
  return {
    issue_id: issueId,
    type: issue?.type ?? null,
    title: issue?.title ?? null,
    severity: issue?.severity ?? null,
    status: latest?.status ?? record.status ?? DEFAULT_REVIEW_STATUS,
    comment: latest?.comment ?? record.comment ?? "",
    author: latest?.author ?? record.author ?? null,
    recorded_at: latest?.at ?? record.at ?? null,
    transition_count: transitions.length,
    entity_refs: issue?.entity_refs ?? [],
    external_refs: issue?.external_refs ?? {},
    transitions
  };
}

export const REVIEW_RECORD_COLUMNS = Object.freeze([
  "issue_id",
  "type",
  "title",
  "severity",
  "status",
  "comment",
  "author",
  "recorded_at",
  "transition_count",
  "entity_refs"
]);

// CSV, not JSON, because the audience is a review meeting and a spreadsheet is
// what is already open in it. Quoting and newline escaping are not optional: a
// waiver reason is free text and will contain a comma, often a quote, and
// sometimes a line break typed into a comment box.
export function reviewRecordCsv(record) {
  if (!record) {
    // Empty, not a bare header. A caller that passes no record has a bug, and a
    // header-only file would download cleanly and read as a review of nothing.
    return "";
  }
  const header = REVIEW_RECORD_COLUMNS.join(",");
  const rows = (record.dispositions ?? []).map((entry) =>
    REVIEW_RECORD_COLUMNS.map((column) => csvCell(entry[column])).join(","));
  return [header, ...rows].join("\n");
}

function csvCell(value) {
  if (value === null || value === undefined) {
    return "";
  }
  if (Array.isArray(value) || (value && typeof value === "object")) {
    return csvCell(JSON.stringify(value));
  }
  const text = String(value);
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function transitionsOf(record) {
  return Array.isArray(record?.transitions) ? record.transitions : [];
}

function sameTransition(left, right) {
  return left.status === right.status
    && (left.comment ?? "") === (right.comment ?? "")
    && (left.author ?? null) === (right.author ?? null);
}

// The reviewer name is one field, remembered for the session, and never
// persisted to the bundle - there is nowhere in a published bundle to put it
// that the publisher would not then be attesting to.
export function reviewerName(state) {
  return state.reviewerName ?? null;
}
