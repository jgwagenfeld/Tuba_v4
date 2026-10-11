# LLM Piping First Task Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Make one reproducible, real-solver LLM piping repair possible and execute its first iteration.

**Architecture:** A standalone procedural example is evaluated by a repository benchmark script. Reuse Tuba verification, Code_Aster execution/import and web review; freeze the benchmark requirements independently of candidate code. Keep run evidence outside source and integrate with the existing generic search history in L2.

**Tech Stack:** Python 3.11-3.14, existing NumPy/pytest/Tuba, external-process Code_Aster.

**Spec:** [LLM piping roadmap and L1 specification](../../architecture/llm-piping-design-roadmap.md).

## Global Constraints

- Python support remains `>=3.11,<3.15`; add no dependencies.
- Commit locally; do not push.
- Unit tests may use deterministic fixtures, clearly separate from engineering evidence. Integration validation must execute real Code_Aster.
- Use the frozen task, preserve authored source, retain attempts outside tracked source, and reuse the existing visualization surface.

## Review Focus

- A changed load, section, material or restraint must be rejected before solving.
- Disconnected geometry or a detached loop must not satisfy endpoint connectivity.
- Missing/nonfinite/unverified results must not produce a feasible outcome.
- Existing attempt folders and input scripts must survive repeated invocation.
- Solver failure must retain diagnostics and remain separate from a reaction violation.

## Task 1: Executable thermal-flexibility benchmark

**Files:**
- Create `examples/llm-piping-benchmark/model.py` and `README.md`: procedural starter and task instructions.
- Create `scripts/benchmark_llm_piping.py`: fixed case, validation, evaluation, feedback and CLI.
- Create `tests/test_llm_piping_benchmark.py`: requirements, topology, evidence and failure tests.
- Update the research reports with a link to the current roadmap.
- Create `docs/architecture/llm-piping-first-task-results.md`: measured execution record.

**Interfaces:**
- `check_candidate(model: TubaModel) -> list[dict]`: checks on the compiled candidate.
- `reaction_checks(model: TubaModel, run: AnalysisRun) -> list[dict]`: endpoint values, components, units, limits, statuses; verified provenance is required.
- `evaluate(candidate: Path, output: Path, *, rationale: str, review: bool = True) -> dict`: exclusive fresh output directory, preserved source, fixed study, real solve and JSON feedback.
- `python -m scripts.benchmark_llm_piping MODEL --output NEW_DIRECTORY --rationale TEXT [--no-review]`: exit 0 feasible, 1 rejected/incomplete/evaluation failure; JSON feedback path printed.

- [x] Write tests first for frozen requirements, valid geometry, disconnected geometry, missing reaction data, existing output and runtime failure. Representative assertions:

  ```python
  model.load_cases['Hot'].temperature = 20.0
  assert any(c['status'] == 'fail' for c in check_candidate(model))
  assert evaluate(source, output, rationale='baseline', review=False)['status'] == 'evaluation_failed'
  assert (output / 'model.py').read_bytes() == source.read_bytes()
  ```

- [x] Run the new focused tests and confirm failures identify the absent implementation.
- [x] Implement the evaluator using canonical model serialization for protected fields, explicit endpoint/support and graph checks, and `verify_project` before `CodeAsterSolver.solve`. Call `validate_for_publication` before reaction extraction. Persist failures and never accept unknown checks.
- [x] Run `python -m pytest tests/test_llm_piping_benchmark.py tests/test_routing_agent.py tests/test_project_study.py -q -p no:cacheprovider`. Expected: all pass.
- [x] Run `python -m tuba.solver.code_aster_doctor --check`. Expected: an available runtime is ready; record the chosen runtime.
- [x] Evaluate the starter in a fresh external run folder. Inspect actual reactions. Revise procedural geometry based on those findings while preserving frozen requirements; evaluate the next candidate in another folder. Expected: a measured rejection and an improved evaluated candidate; report whether the fixed limits were met, without relaxing them.
- [x] Generate the existing web review for the solved candidates and validate scene/evidence references. Expected: readable bundles containing only Code_Aster-backed results.
- [x] Obtain an independent implementation review, fix material findings with regression checks, record validation and commit owned paths locally.

## Execution ledger

- Baseline `6126475`; isolated branch `codex/llm-piping-first-task-20261011`.
- Existing focused baseline: 41 tests passed (routing agent and project study).
- Runtime preflight: Ubuntu WSL `run_aster` ready. Reuse the repository Python environment; install no dependency copies.
- Scope: only Task 1 is scheduled for implementation in this turn. L2-L5 remain roadmap work.
- Initial benchmark tests failed on the absent evaluator import; after implementation, 20 new tests and 41 existing tests passed (61 total).
- The two real-solver attempts and their measured results are recorded in [the L1 result report](../../architecture/llm-piping-first-task-results.md). The first was rejected at 7496 N; the revision passed at 3639 N against unchanged 5000 N limits.
- Ruling: use native `CodeAsterSolver.solve` after `verify_project`, rather than project-solve transient staging. The latter removes failed staging in its finally block; a research attempt must retain failure evidence. Execution/import/provenance still use the existing Tuba implementation.
- Independent review found explicit-bend consistency and sharp-corner bypasses. Regression tests reproduced them; the gate now validates actual arc radius/angle/center/endpoints, solver-normal orientation, tangent continuity and exact arc coordinate extrema. A follow-up reversed-normal reproduction was also fixed and tested.
- The auditability note is addressed by an atomic pre-solve feedback checkpoint and an exact evaluator source snapshot. Interrupted attempts remain incomplete; `solver_evaluations` counts attempted calls, including failed calls.
- Final focused validation: **71 passed** (30 benchmark contract tests, 41 existing routing/study tests). No full repository or browser suite was run; there are no viewer source changes.
- Both Code_Aster 18.0.12 studies reopened with verified provenance. Both 392-object review scenes validated, and their external geometry/source references resolved. Final evaluator checks retain the original rejection/pass and exact reaction values without unnecessary new solves; see external `final-evaluator-recheck.json`.
- Review boundaries: numerical accuracy/mesh convergence and engineering qualification remain explicitly outside this pilot; existing provenance validation was exercised on both actual studies. Browser rendering was not independently tested. L2-L5 and malicious-code containment remain out of scope, as specified.
- Task 1: complete. Local integration is recorded by the Git commit containing this plan; no remote push is authorized.
