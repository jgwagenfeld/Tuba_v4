# L3 comparison foundation implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan inline, with one fresh final review.

**Goal:** Freeze several thermal cases and repeatable comparison protocols; run a real Code_Aster reference campaign without claiming unrun LLM results.

**Architecture:** Parameterize the existing benchmark checks explicitly. Each trial is an existing authored search session. A campaign uses the same append-only History class for immutable protocol and trial lifecycle events. Reports derive metrics from retained candidate/evaluation evidence. A provider-neutral submission API accepts model usage records; it does not invoke a provider or invent missing telemetry.

**Tech stack:** Python >=3.11,<3.15, existing Tuba/Code_Aster/SQLite; no new dependencies.

**Spec:** `docs/architecture/llm-piping-design-roadmap.md`, L3. This increment completes the comparison infrastructure and deterministic reference qualification; repeated pinned-provider trials remain open.

## Global constraints

- Keep Code_Aster mandatory for measured engineering acceptance. Preserve all failures.
- Three cases: original 200 C / 5000 N; 300 C / 5000 N; compact y<=1.2 m / 200 C / 8000 N. Other L2 requirements unchanged.
- One fixed-family reference: try loop rises 0.4, 0.8, 1.6 m in that order, stopping at first feasible. Never silently clamp a candidate to the envelope.
- Two repeats per case; 3 proposals, 3 solver calls and 1800 s admission budget per trial. An in-flight solve retains its result even after the admission deadline.
- Freeze method ID, representation, model/provider/settings (for LLMs), prompt, tools, starting source, evaluator and case definitions before any trial starts.
- External LLM driving is trusted local work, not a sandbox. Timing starts before design; caller-reported usage has explicit provenance. Unknown cost/tokens stay null. No token or dollar budget enforcement is claimed.
- Report planned/started/finished counts separately. Group by case, method and representation; do not pool free-topology and fixed-family objectives.
- A report must verify source, model and sealed solver evidence before counting feasibility. Damage cannot pass.
- All generated runs/logs outside source; reuse main .venv. Local commits only.

## Review focus

1. Partial campaign/trial initialization and interrupted submissions must remain visible and resumable or explicitly incomplete.
2. Changed case/protocol/source/evidence cannot silently produce a feasible report.
3. Admission budgets count invalid and failed proposals, and time includes design latency.
4. Missing usage and unstarted trials cannot become zero cost or successful runs.
5. A campaign cannot mutate another trial through path traversal or changed trial IDs.

## Task 1: Explicit immutable cases

Files: `scripts/piping_comparison_cases.py`, `scripts/benchmark_llm_piping.py`, `scripts/iterate_llm_piping.py`, `tests/test_llm_piping_comparison.py`.

Interfaces: `get_case(case_id)->dict` returns a fresh copy; `create_session(root, max_solver_calls=10, case_id=...)`; compiled and reaction checks accept explicit `case=`. Existing defaults remain unchanged.

- [ ] Write tests for independent copies, changed temperature rejection, compact envelope, case-aware reaction limits and unknown IDs.
- [ ] Run focused tests; expected missing case API failure.
- [ ] Implement case propagation without mutation of module globals.
- [ ] Run L1/L2 plus new tests; expected all pass. Commit explicit owned files.

## Task 2: Protocol, lifecycle and metrics

Files: `scripts/compare_llm_piping.py`, `tests/test_llm_piping_comparison.py`, `examples/llm-piping-comparison/README.md`.

Interfaces: `create_campaign(root, repeats=2, case_ids=..., methods=..., budgets=...)`; `start_trial(root, trial_id)`; `submit_trial(root, trial_id, project, intent=..., dependencies=(), usage=None)`; `finish_trial(root, trial_id, reason=...)`; `report_campaign(root)`; `run_reference(root)`.

- [ ] Test a six-slot campaign before any runs, metadata validation, invalid candidate accounting, caller-reported versus unknown usage, budgets, frozen source integrity, and report evidence damage.
- [ ] Run focused tests; expected missing campaign API failure.
- [ ] Implement immutable protocol in History, nested authored sessions, lifecycle events and conservative evidence-derived reporting. Reference source comes from the pinned authored example, adjusted only for case and prescribed rise.
- [ ] Add CLI init/reference/report and driver-facing API documentation. Run targeted checks, expected pass. Commit owned files.

## Task 3: Qualification and integration

- [ ] Run two real reference trials per case, retain logs and all attempts externally. Review measured reactions and report failure/coverage exactly.
- [ ] Request one independent final branch review, address important defects with reproducing tests and rerun affected checks.
- [ ] Document exact results, scope, limitations and commands; update roadmap L3 status to foundation complete, pinned LLM campaign pending.
- [ ] Commit locally, verify main ownership and clean status, integrate without pushing, remove only clean task-owned worktree.

## Execution ledger

- Pre-flight: Task 1 produces explicit case sessions consumed by Task 2; Task 2 produces report/runner consumed by Task 3. No interface conflict.
- The existing roadmap supplies the spec. Windows-native commands and this tracked ledger replace shell-only task bookkeeping.
- Task 1: explicit cases implemented; four new tests failed on missing APIs, then all 61 L1/L2/case checks passed (67.69 s). Baseline: 57 passed (48.64 s).

- Task 2: comparison API, CLI and documentation implemented. Seven missing-API tests failed first; two starter-brief tests then exposed missing source. Final combined L1/L2/comparison run: 72 passed in 80.14 s. Code_Aster bridge doctor ready. Independent final review in progress before native qualification.
