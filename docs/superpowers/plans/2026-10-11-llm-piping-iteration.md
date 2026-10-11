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
