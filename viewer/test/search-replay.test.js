import assert from "node:assert/strict";
import test from "node:test";
import { loadSearchReplay, replayAt, parameterDiff, safeReplayUrl, branchIds, latestViewRequest } from "../src/searchReplay.js";

function fixture() {
  const candidate = (id, parents = []) => ({ id, parent_ids: parents, parameters: { width: id === "C1" ? 1 : 2 },
    outcome: "selected", preview: { bundle: `previews/${id}`, availability: "available" },
    attempt_reviews: [{ evaluation_id: "E1", attempt_id: "A1", bundle: `reviews/${id}/E1`, availability: "available" }],
    evaluations: [], decisions: [] });
  const event = (sequence, kind, candidate_id, payload = {}) => ({ sequence, kind, candidate_id, payload, at_utc: `2026-10-10T10:00:0${sequence}Z` });
  return { schema: "tuba.search.viewer.v1", run: { run_id: "R" }, candidates: [candidate("C1"), candidate("C2", ["C1"])], comparison_ranges: {},
    events: [event(1, "candidate.proposed", "C1"), event(2, "candidate.built", "C1"),
      event(3, "evaluation.interrupted", "C1", { id: "EI", attempt_id: "AI", status: "interrupted", checks: [] }),
      event(4, "candidate.decision", "C1", { evaluation_id: "EI", outcome: "incomplete", reason_codes: ["interrupted"] }),
      event(5, "evaluation.completed", "C1", { id: "E1", attempt_id: "A1", status: "complete", checks: [{ constraint_id: "load", verdict: "pass" }] }),
      event(6, "candidate.decision", "C1", { evaluation_id: "E1", outcome: "feasible_retained", reason_codes: [] }),
      event(7, "candidate.proposed", "C2"),
      event(8, "candidate.decision", "C1", { evaluation_id: "E1", outcome: "selected", reason_codes: ["objective_minimum"] })] };
}

test("projection hides future candidates, checks and selection", () => {
  const manifest = fixture();
  assert.equal(replayAt(manifest, 0).candidates.length, 0);
  const before = replayAt(manifest, 2);
  assert.equal(before.candidates.length, 1);
  assert.equal(before.candidates[0].outcome, "awaiting_evaluation");
  assert.deepEqual(before.candidates[0].evaluations, []);
  assert.equal(replayAt(manifest, 6).candidates[0].outcome, "feasible_retained");
  assert.deepEqual(replayAt(manifest, 6).bestFeasibleIds, ["C1"]);
  assert.equal(replayAt(manifest, 8).candidates[0].outcome, "selected");
});

test("each interrupted or complete evaluation has only its recorded decisions", () => {
  const row = replayAt(fixture(), 8).candidates[0];
  assert.deepEqual(row.evaluations.map(e => e.outcome), ["incomplete", "selected"]);
  assert.equal(row.evaluations[0].review.bundle, undefined);
  assert.equal(row.evaluations[1].review.bundle, "reviews/C1/E1");
});

test("branch traversal handles cycles and missing parents without inventing links", () => {
  const rows = [{ id: "C1", parent_ids: ["missing", "C2"] }, { id: "C2", parent_ids: ["C1"] }, { id: "C3", parent_ids: [] }];
  assert.deepEqual([...branchIds(rows, "C1")].sort(), ["C1", "C2"]);
  assert.deepEqual(parameterDiff({ parameters: { x: 2, nested: { z: true } } }, { parameters: { x: 1, old: 5, nested: { z: true } } }),
    [{ key: "old", before: 5, after: undefined }, { key: "x", before: 1, after: 2 }]);
});

test("relative replay links stay inside the package", () => {
  const base = "http://localhost:8090/bundle/search_replay.json";
  assert.equal(safeReplayUrl(base, "reviews/C1/E1"), "http://localhost:8090/bundle/reviews/C1/E1");
  for (const path of ["../private", "%2e%2e/private", "%252e%252e/private", "https://outside.test/x", "javascript:alert(1)", "//outside/x", "a\\..\\private", "/absolute", "reviews/%2fprivate", "reviews/a?x=1", "reviews/a#x"]) {
    assert.throws(() => safeReplayUrl(base, path), /relative|package|Unsafe/);
  }
});

test("loader validates event ordering and resource bounded JSON", async () => {
  const manifest = fixture();
  const fetcher = async () => new Response(JSON.stringify(manifest));
  assert.equal((await loadSearchReplay("http://localhost/bundle/search_replay.json", fetcher)).run.run_id, "R");
  manifest.events[1].sequence = 1;
  await assert.rejects(loadSearchReplay("http://localhost/bundle/search_replay.json", fetcher), /sequence/);
});

test("latest request guard never accepts an older candidate load", async () => {
  const requests = latestViewRequest();
  const first = requests.next();
  const second = requests.next();
  assert.equal(first.current(), false);
  assert.equal(second.current(), true);
});
