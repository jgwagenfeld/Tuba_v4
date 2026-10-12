import { readBoundedJson } from "./sceneBudget.js";

export const hydraulicSolverLabel = basis => basis === 'openmodelica' ? 'OpenModelica' : basis === 'pandapipes' ? 'pandapipes' : null;

export function safeReplayUrl(base, relative) {
  if (typeof relative !== "string" || !relative) throw new Error("Unsafe relative replay path");
  let decoded = relative;
  try {
    for (let i = 0; i < 5; i++) {
      const next = decodeURIComponent(decoded);
      if (next === decoded) break;
      decoded = next;
    }
  } catch { throw new Error("Unsafe relative replay path"); }
  const parts = decoded.split("/");
  if (/^[\/]/.test(decoded) || /[\\%\s\x00-\x1f:?#]/.test(decoded) || parts.some(p => !p || p === "." || p === "..")) {
    throw new Error("Unsafe relative replay path outside package");
  }
  const root = new URL("./", base);
  if (!["http:", "https:"].includes(root.protocol)) throw new Error("Unsafe package URL");
  return new URL(parts.map(encodeURIComponent).join("/"), root).href;
}

export async function loadSearchReplay(url, fetcher = fetch) {
  const target = new URL(url);
  if (!["http:", "https:"].includes(target.protocol) ||
      (typeof window !== "undefined" && target.origin !== window.location.origin)) throw new Error("Unsafe package URL");
  const response = await fetcher(target.href);
  if (!response.ok) throw new Error(`Search replay unavailable (${response.status})`);
  const manifest = await readBoundedJson(response);
  if (manifest?.schema !== "tuba.search.viewer.v1" || !Array.isArray(manifest.candidates) || !Array.isArray(manifest.events)) {
    throw new Error("Unsupported search replay manifest");
  }
  const ids = new Set();
  for (const row of manifest.candidates) {
    if (typeof row.id !== "string" || ids.has(row.id) || !Array.isArray(row.parent_ids)) throw new Error("Invalid replay candidate");
    ids.add(row.id);
    for (const view of [row.preview, ...(row.attempt_reviews ?? [])]) if (view?.bundle) safeReplayUrl(target, view.bundle);
  }
  let sequence = 0;
  for (const event of manifest.events) {
    if (!Number.isSafeInteger(event.sequence) || event.sequence <= sequence) throw new Error("Invalid replay event sequence");
    if (event.candidate_id && !ids.has(event.candidate_id)) throw new Error("Unknown replay event candidate");
    sequence = event.sequence;
  }
  return manifest;
}

export function replayAt(manifest, sequence) {
  const originals = new Map(manifest.candidates.map(row => [row.id, row]));
  const rows = new Map();
  const events = manifest.events.filter(e => e.sequence <= sequence);
  for (const event of events) {
    const original = originals.get(event.candidate_id);
    if (!original) continue;
    if (event.kind === "candidate.proposed") {
      rows.set(original.id, { ...original, build: null, preview: { availability: "unavailable", message: "Geometry not yet recorded" },
        attempt_reviews: [], evaluations: [], decisions: [], reason_codes: [], outcome: "awaiting_evaluation", proposal_sequence: event.sequence });
    }
    const row = rows.get(original.id);
    if (!row) continue;
    if (event.kind === "candidate.built") { row.build = event.payload; row.preview = original.preview; }
    if (event.kind === "attempt.recovered") {
      row.evaluations.push({ ...event.payload, id: `recovered:${event.payload.attempt_id}`, sequence: event.sequence,
        source_event_kind: event.kind, operations: manifest.run.settings?.operations ?? [], completed_operations: [],
        checks: [], outcome: "incomplete", decisions: [],
        review: original.attempt_reviews?.find(v => v.evaluation_id == null && v.attempt_id === event.payload.attempt_id)
          ?? { availability: "unavailable", message: "No evaluation was published before crash recovery" } });
      row.outcome = "awaiting_evaluation";
    }
    if (["evaluation.completed", "evaluation.failed", "evaluation.interrupted"].includes(event.kind)) {
      row.evaluations.push({ ...event.payload, sequence: event.sequence, outcome: "incomplete", decisions: [],
        review: original.attempt_reviews?.find(v => v.evaluation_id === event.payload.id) ?? { availability: "unavailable", message: "Review not exported" } });
      row.outcome = "awaiting_decision";
    }
    if (event.kind === "candidate.decision") {
      row.decisions.push({ ...event.payload, sequence: event.sequence });
      row.outcome = event.payload.outcome;
      row.reason_codes = event.payload.reason_codes;
      const evaluation = row.evaluations.find(e => e.id === event.payload.evaluation_id);
      if (evaluation) { evaluation.outcome = event.payload.outcome; evaluation.decisions.push({ ...event.payload, sequence: event.sequence }); }
    }
  }
  const candidates = [...rows.values()];
  return { sequence, event: events.at(-1) ?? null, events, candidates,
    bestFeasibleIds: candidates.filter(c => ["feasible_retained", "feasible_not_selected", "selected"].includes(c.outcome)).map(c => c.id) };
}

export function parameterDiff(candidate, reference) {
  const a = candidate?.parameters ?? {}, b = reference?.parameters ?? {};
  return [...new Set([...Object.keys(a), ...Object.keys(b)])].sort()
    .filter(key => JSON.stringify(a[key]) !== JSON.stringify(b[key]))
    .map(key => ({ key, before: b[key], after: a[key] }));
}

export function branchIds(rows, root) {
  const result = new Set([root]);
  let changed = true;
  while (changed) {
    changed = false;
    for (const row of rows) if (!result.has(row.id) && row.parent_ids?.some(id => result.has(id))) {
      result.add(row.id); changed = true;
    }
  }
  return result;
}

export function latestViewRequest() {
  let generation = 0;
  return { next() { const id = ++generation; return { current: () => generation === id }; } };
}

// Hydraulic checks use their sealed attempt even without a structural operation.
export function reviewForCheck(candidate, evaluation, check) {
  return check ? (check.operation || hydraulicSolverLabel(check.basis) ? evaluation?.review : candidate?.preview)
    : evaluation?.review ?? candidate?.preview;
}
