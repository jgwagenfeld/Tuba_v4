# L2: Authored piping iterations in shared search history

Spec: [LLM roadmap](../../architecture/llm-piping-design-roadmap.md), L2.
Baseline: `71dc59f`. History/replay integration parent: `bbc19e6`.

## Contract

An agent submits a trusted procedural `model.py` (and explicitly named local
construction-unit dependencies), a candidate ID, parent IDs and an intent.
The session freezes the task, evaluator implementation and solve budget.
Each submission executes its retained source, checks the compiled requirements,
and uses the native permanent-attempt Code_Aster evaluator. All outcomes remain
in `tuba.search` history. A retry uses the same source and a fresh attempt.
No grid or genetic optimizer is required. This is a local coding-agent tool,
not an autonomous API/model provider integration or Python sandbox.

The new `thermal-guided-design-v1` case preserves the L1 thermal problem except
that zero to four ideal bilateral ground guides are permitted at distinct
interior pipe nodes, restraining global Y or Z only. No friction, imposed motion,
support mass, stiffness, gaps, attachments or changed nozzle anchors. The agent
may rewrite the route and construction units within the original geometric
envelope. L1's evaluator and two-anchor policy remain unchanged.

One coordinator owns a session. Published evaluations and source snapshots are
immutable; interruption recovery seals partial evidence without inventing results.
Source diffs are retained for each parent. Reviews must use that candidate's
source, compiled model, solver identity and sealed attempt. Missing or damaged
artifacts cannot establish a new pass. A terminal evaluation published before a
crash may have its missing decision recovered without solving again.

No dependencies installed, no generated evidence tracked, no remote push.
Reuse the checkout Python environment. Use the existing web-scene review/replay.

## Shared interfaces

| Producer | Consumer | Contract |
| --- | --- | --- |
| ArtifactStore.capture_files | authored candidate runner | Explicit project-relative file inventory; no links/caches/outside files |
| frozen requirement checks | native evaluate_candidate | Required prechecks run before solver; retained even for rejection |
| candidate source_manifest_ref | history export/review | Per-candidate inventory with fallback for existing parameter-grid runs |
| native Evaluation / Decision | existing viewer | Existing event schema, explicit units, operation/state/entity scope |

## Tasks

1. Integrate committed M1/M2 history/replay, excluding M3 film commits and dirty
   work. Inspect merge index against both parents; run search/replay Python and
   relevant viewer checks. Commit the integration locally.
2. Add meaningful failing tests for source capture, frozen support policy,
   parent diffs, dependency replay, immutable resume, pre-solve rejection,
   evaluation failure/interruption, decision-gap recovery and candidate review.
   Implement a small authored-iteration script using shared history/evaluation.
   Extend native numeric checks to canonical `N m` moments and expose prechecks;
   add candidate source references to existing export/review. Run focused tests.
3. Execute at least two actual Code_Aster candidates in one retained session,
   including a measured rejection and revision; reopen/review them and verify
   source/identity correspondence. Document commands, results and limitations.
4. Independent whole-change review required by executing-plans; fix important
   findings with regression tests. Commit owned files, integrate locally into
   clean main, preserve evidence and remove completed task worktree.

## Review Focus

- Candidate source can differ arbitrarily from its parent; check that result
  reviews never display a run-global starter source instead of the candidate.
- Hard process death can occur between any archive write and history event;
  distinguish an interrupted attempt from a published evaluation missing a decision.
- Source dependencies, mutable requirements, changed evaluator, missing or
  tampered inventories, and retries must not silently change the evaluated problem.
- Optional guide fields must not hide stiffness, contact or prescribed motion.
- Existing parameter-grid evaluation/replay must retain behavior and compatibility.

## Execution ledger

- Pre-flight: shared interfaces above checked against the committed history API.
- Integration in progress: clean merge of `bbc19e6`; index inspected against both
  parents, no deletions. Foreign film checkout remains untouched.
- Integration commit: `2bcfa5f`. Seven viewer replay unit checks passed; broader
  search/history/review baseline tests are running.
- Task 2: initial contract suite failed because the iteration module was absent;
  implemented source submission, fixed guide policy, native evaluation adapter,
  parent diffs and retry/recovery. L1 + L2 focused tests: 51 passed. Corrected the
  recovery test expectation: a later interrupted attempt makes the current
  candidate incomplete while the prior rejection remains in its decision history.
- Baseline qualification finished: 157 passed, 1 skipped in 1243.90 s; seven
  viewer replay unit tests passed. This baseline run preceded final hardening.
- Independent review found three Important issues, no Critical or Minor issues:
  source/inventory replacement, orphan attempt metadata after process death, and
  decision recovery without candidate integrity. Five new regression cases
  failed as expected (including sealed attempt-inventory replacement). Fixes
  bind source references to their canonical inventory digest, fingerprint newly
  sealed attempt inventories in immutable evaluation records, retain orphan
  bytes without invented candidate attribution, and verify candidate source/
  model before restoring a decision. Final combined checks are running.
- Final: Ruling: Trusted Python is the declared scope; hostile script execution
  is not sandboxed. Cost if wrong: untrusted scripts can affect the host.
- Final: Ruling: Industrial engineering qualification and benchmark allowables
  remain outside this thermal research task. Cost if wrong: these results do not
  establish operating-system or piping-code acceptability.
- Final: Ruling: Provider integration and statistical design-quality comparison
  remain L3 work. Cost if wrong: no repeat-run reliability or model ranking is shown.
- Final: Ruling: The executor owns real-solver and final-suite qualification;
  the reviewer did not rerun them. Cost if wrong: review alone cannot substantiate
  execution results, so they must be measured and reported separately.
- Task 3: Ruling: L2 uses a frozen 600-second execution timeout after the loaded
  runtime exceeded the inherited 180-second limit. Use a fresh session and keep
  earlier failures; mechanical loads, limits and mesh settings do not change.
  Cost if wrong: a stalled solver can consume ten minutes per call.
- Final combined regression run: 213 passed, 1 skipped, 1 stale diagnostic
  assertion failed. The corrupted-source replay now correctly fails the earlier
  immutable-inventory gate. Updated that assertion; its focused rerun passed in
  17.36 s. Thus 214 distinct checks pass across runs, with one platform skip;
  the combined command was not repeated after the assertion-only correction.
  A separate final-policy run passed all 27 authored-iteration tests in 87.45 s.
- Task 3: two real Code_Aster solves completed in the 600-second session. C1
  rejects at 7496.016 N; its child C2 passes at 3639.423 N, with guides/limits
  unchanged and 0.8 m more pipe. Operation elapsed: 104.514 s and 49.277 s.
  Earlier runtime failures remain retained; total L2 development qualification
  is five solver calls (three completed, two timeouts), not just the final two.
- Final verification: both native Code_Aster 18.0.12 runs reopened against their
  recorded identities and passed publication checks. Replay has two valid result
  scenes and exact candidate source, no availability diagnostics. Five focused
  browser checks passed, no page errors. Shared viewer source identity matched
  the existing build, so it was reused without rebuild or dependency copies.
- Final: fixed all three Important review findings via five failing regression
  cases and passing final checks. No Minor findings were deferred. All four
  review boundary decisions and the timeout-budget decision are recorded above.
