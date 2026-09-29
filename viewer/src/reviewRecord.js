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

// A disposition can be recorded against a bundle *issue* or against a *finding* -
// a result the reviewer looked at and decided about. Nothing in the piping
// benchmark joins those two: a tool can mark a clash resolved, and it can
// annotate a node, and it cannot say "this element, this component, this result
// step, was examined and waived".
//
// The subject id has to be *stable*, because a disposition recorded in March
// against a finding must still mean something in April when the hotspot list
// re-sorts. It therefore names every coordinate rather than any of them alone:
// the result step, the field, the component and the object. Drop the component and
// "waived" silently changes from meaning MFY to meaning MFZ; drop the result step
// and it changes from meaning Hot to meaning Cold.
const SUBJECT_SEPARATOR = ":";
// A field id is itself colon-delimited - `field:solver_result:stress:Hot` - so a
// raw join is ambiguous and split() recovers the wrong boundaries. The separator
// is therefore encoded inside each component, which is what makes the id
// parseable back into exactly the coordinates it was built from.
const ENCODED_SEPARATOR = "%3A";

export function findingSubjectId(finding, { fieldId = null, component = null, resultStateId = null } = {}) {
  const objectId = finding?.objectId ?? "";
  if (!objectId) {
    return null;
  }
  const parts = [resultStateId, fieldId, component, objectId];
  if (parts.some((part) => part === null || part === undefined)) {
    // A coordinate that is not known cannot be a coordinate. Returning null
    // rather than a placeholder means the caller finds out, instead of recording
    // a disposition against a "-" that reads like a real result step.
    return null;
  }
  return `finding${SUBJECT_SEPARATOR}${parts.map(encodeComponent).join(SUBJECT_SEPARATOR)}`;
}

function encodeComponent(value) {
  return String(value).replaceAll(SUBJECT_SEPARATOR, ENCODED_SEPARATOR);
}

function decodeComponent(value) {
  return String(value).replaceAll(ENCODED_SEPARATOR, SUBJECT_SEPARATOR);
}

// The address is what travels with the disposition into the record. It is the
// same shape as the reporting layer's `governing_location`, and for the same
// reason: a number on a table that sorts is not an address.
//
// `object_id` may come from the finding or from the context, because the two
// callers differ: one has the finding in hand, the other is reconstructing an
// address from a subject id and has nothing but the id.
export function findingAddress(finding, { fieldId = null, component = null, resultStateId = null, loadCase = null, unit = null, object_id = null } = {}) {
  return {
    object_id: object_id ?? finding?.objectId ?? null,
    element_id: finding?.elementId ?? null,
    subpoint_index: finding?.subpointIndex ?? null,
    row_index: finding?.rowIndex ?? null,
    field: fieldId,
    component,
    result_state_id: resultStateId,
    load_case: loadCase,
    value: finding?.value ?? null,
    unit: unit ?? finding?.unit ?? null,
    utilization: finding?.utilization ?? null
  };
}

// Everything a disposition is recorded against, in one lookup: what it is, and
// how to name it.
export function resolveSubject(state, subjectId) {
  if (typeof subjectId !== "string" || subjectId.length === 0) {
    return null;
  }
  if (subjectId.startsWith("finding:")) {
    return { kind: "finding", subjectId, address: parseFindingSubjectId(subjectId) };
  }
  const issue = (state.issues ?? []).find((candidate) => candidate.id === subjectId);
  return issue ? { kind: "issue", subjectId, issue } : null;
}

// The inverse of findingSubjectId, for a subject that arrived as an id and needs
// its address back for a record.
//
// Only the *coordinates* come back. The descriptive parts of an address - the
// element, the value, the utilisation, the load case - are deliberately not
// encoded, because they are what the number was when the decision was taken, and
// a record that reconstructed them from an id would report a value the reviewer
// never saw. That is why a disposition stores its address when the caller has one.
export function parseFindingSubjectId(subjectId) {
  if (typeof subjectId !== "string" || !subjectId.startsWith(`finding${SUBJECT_SEPARATOR}`)) {
    return null;
  }
  const parts = subjectId.slice(`finding${SUBJECT_SEPARATOR}`.length).split(SUBJECT_SEPARATOR);
  if (parts.length < 4) {
    return null;
  }
  const [resultStateId, fieldId, component, ...objectParts] = parts;
  return findingAddress(null, {
    resultStateId: decodeComponent(resultStateId),
    fieldId: decodeComponent(fieldId),
    component: decodeComponent(component),
    object_id: objectParts.map(decodeComponent).join(SUBJECT_SEPARATOR)
  });}

export function recordDisposition(state, change) {
  // `issueId` is accepted as an alias so the two reducer actions that predate
  // findings keep working; every subject is addressed the same way underneath.
  const subjectId = change?.subjectId ?? change?.issueId;
  if (!subjectId) {
    return state;
  }
  const existing = state.reviewDispositions?.[subjectId] ?? {};
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
    reviewDispositions: {
      ...(state.reviewDispositions ?? {}),
      [subjectId]: {
        ...existing,
        // Stored on the record rather than reconstructed on export, so a finding
        // disposition keeps the address it was recorded against even if the
        // subject id's encoding ever changes.
        ...(change.address ? { address: change.address } : existing.address ? { address: existing.address } : {}),
        status,
        comment,
        author,
        at,
        transitions: [...transitionsOf(existing), transition]
      }
    }
  };
}

export function dispositionFor(state, subjectId) {
  const record = state.reviewDispositions?.[subjectId];
  if (!record) {
    return null;
  }
  return {
    subjectId,
    status: record.status ?? DEFAULT_REVIEW_STATUS,
    comment: record.comment ?? "",
    author: record.author ?? null,
    at: record.at ?? null,
    address: record.address ?? null,
    transitions: transitionsOf(record)
  };
}

export function dispositionTally(state) {
  const tally = Object.fromEntries(REVIEW_STATUSES.map((status) => [status.id, 0]));
  let touched = 0;
  for (const record of Object.values(state.reviewDispositions ?? {})) {
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
  const dispositions = Object.entries(state.reviewDispositions ?? {})
    .filter(([subjectId, record]) => subjectId && record && transitionsOf(record).length > 0)
    .map(([subjectId, record]) => dispositionEntry(subjectId, record, issues.get(subjectId), state))
    // A disposition whose subject has vanished from the bundle - a scene that
    // reloaded and lost the issue, a finding whose field was replaced - still
    // belongs in the record, and losing it would silently delete a decision.
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

function dispositionEntry(subjectId, record, issue, state) {
  const transitions = transitionsOf(record);
  const latest = transitions.at(-1);
  const isFinding = subjectId.startsWith("finding:");
  const address = record.address ?? (isFinding ? parseFindingSubjectId(subjectId) : null);
  return {
    subject_kind: isFinding ? "finding" : "issue",
    subject_id: subjectId,
    type: issue?.type ?? null,
    title: issue?.title ?? findingTitle(address),
    severity: issue?.severity ?? null,
    status: latest?.status ?? record.status ?? DEFAULT_REVIEW_STATUS,
    comment: latest?.comment ?? record.comment ?? "",
    author: latest?.author ?? record.author ?? null,
    recorded_at: latest?.at ?? record.at ?? null,
    transition_count: transitions.length,
    entity_refs: issue?.entity_refs ?? [],
    address,
    // The full log, so the JSON export answers "was this ever looked at" for a
    // record whose current status says nothing about it.
    transitions
  };
}

// A finding has no title of its own, so the record names it the way the viewport
// did: what it is, on what, in what result step. That string is what a person
// reads in a review meeting, so it is the one in the export.
function findingTitle(address) {
  if (!address) {
    return null;
  }
  const where = address.element_id ?? address.object_id ?? "unknown element";
  const what = [address.field, address.component].filter(Boolean).join(" / ");
  const when = address.load_case ?? address.result_state_id ?? "unknown case";
  return `${where}${what ? ` — ${what}` : ""} (${when})`;
}

export const REVIEW_RECORD_COLUMNS = Object.freeze([
  "subject_kind",
  "subject_id",
  "type",
  "title",
  "severity",
  "status",
  "comment",
  "author",
  "recorded_at",
  "transition_count",
  "entity_refs",
  "address"
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
