# Piping Search History Initial Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a deterministic, sequential piping search that permanently retains every candidate, available solver artifact, check result and selection decision, including rejected trials, and exports the records needed for subsequent viewer replay.

**Architecture:** Add a small `tuba/search/` package that owns search records, scheduling and durable attempt directories. It consumes authored project builders, the existing verification gate, validated study settings, native Code_Aster export/execute/import and existing clash/scene APIs. Ordinary project evidence promotion remains unchanged; a search never solves into the authored project's replaceable `evidence/` or staging folders.

**Tech Stack:** Python `>=3.11,<3.15`; standard-library `sqlite3`, `json`, `hashlib`, `pathlib`, `itertools` and `uuid`; existing Tuba/Code_Aster/visualization dependencies; pytest for focused tests. No new optimizer, database service, video or frontend dependency in this milestone.

**Spec:** [Explainable piping-layout search roadmap](../../architecture/piping-search-roadmap.md).

**Status:** proposed plan, not an implemented feature. Proposed commands, modules and interfaces below do not exist at the baseline. Date: 2026-10-10. Source baseline: `7652065e1637e5c7ab102cb2ceb5236a3d4a92b6`.

## Global Constraints

- Python support remains `>=3.11,<3.15`.
- The engineering workflow remains Tuba model -> Code_Aster solve -> processed-result display.
- Authored `model.py` scripts remain procedural Python and are never overwritten by search.
- Code_Aster execution remains native Tuba code using an external solver process; prefer the Python-managed bridge.
- Export-only studies, predictions, proxy calculations and test fixtures are never presented as engineering solver results.
- Feasibility is always scoped to the declared checks, operations, modelling assumptions and evidence; it is not a claim of full piping-code compliance.
- Applicable piping-standard checks remain user-owned; this roadmap does not restore the retired built-in ASME evaluator.
- Search replay uses `tuba/visualization/` and `viewer/`; it does not introduce another rendering path.
- Required check outcomes are `pass`, `fail`, `unknown` or `not_applicable`; missing evidence cannot establish a pass.
- Source changes and small final deliverables belong in Git; histories, solver artifacts, generated scenes and films belong in durable storage outside tracked source.
- Commit locally by default; never push without an explicit user request.
- Reuse checkout dependencies and shared caches. Validate only the affected behavior; preserve real failure evidence and never copy dependency/build/cache payloads into trial archives.

## Review Focus

1. A required reaction/displacement is missing, NaN, infinite, or has mixed force/moment units: verdict is unknown or a configuration error, never pass. Task 5 owns the tests.
2. A second operation or checker fails after the first operation solved: completed and partial artifacts survive, no selected solution appears, and failure is distinct from an engineering violation. Task 4 owns the tests.
3. A crash occurs between artifact completion and event insertion, or an archive write runs out of space: recovery preserves files and reports interruption; no event advertises nonexistent completed evidence. Task 3 owns the tests.
4. An obstacle or policy changes while solver inputs stay identical: the solve may be reused only through the existing evidence verdict, but design/check identities change and new checks are recorded. Task 6 owns the tests.
5. Native result/entity IDs repeat between candidates, or the same design is retried: exports resolve the exact candidate/attempt/state and preserve prior decisions. Tasks 2 and 7 own the tests.

## Milestone scope and success criteria

This plan implements roadmap M1. It includes records, durable solver attempts,
explicit verification/acceptance, a sequential parameter grid, CLI inspection,
JSON export and on-demand candidate review through the existing viewer.

Interactive timeline/branch UI, movie rendering, LLM proposals, surrogate models,
parallel execution, multi-line optimization and a new piping-standard evaluator
are separate milestones. The initial search has no prediction-based pruning.

Acceptance requires:

- Every proposed candidate has a permanent record and a precise outcome.
- Every solved or failed attempt has an immutable inventory of available evidence.
- Required operations and declared checks are complete before a candidate can be feasible or selected.
- A real Code_Aster benchmark retains at least one solved rejection and one candidate passing its fixed, named demonstration checks.
- A required missing/unsupported check yields incomplete acceptance.
- Restart and read-only export require neither a solver nor an LLM.
- The authored source project, its current evidence and its staging directory remain unchanged.

## File map

| Proposed file | Responsibility |
| --- | --- |
| `tuba/search/__init__.py` | The small public API |
| `tuba/search/contracts.py` | Record types, configuration validation, lifecycle/decision vocabulary and strict serialization |
| `tuba/search/history.py` | SQLite schema, append-only transactions, causal ordering and read projections |
| `tuba/search/artifacts.py` | Shared source/assets, owned attempt directories, inventories, hashes and interrupted-write recovery |
| `tuba/search/checks.py` | Adapters over verification, clash and imported solver results; structured verdicts |
| `tuba/search/evaluate.py` | Sequential required-operation evaluation in permanent attempt directories |
| `tuba/search/run.py` | Project loading, deterministic proposals, scheduling, reuse, budgets and selection |
| `tuba/search/export.py` | Portable history/replay manifest and on-demand native candidate scene |
| `tuba/search/__main__.py` | CLI parser and stable exit behavior |
| `examples/piping-search/model.py`, `study.py`, `search.py`, `README.md` | One authored, bounded hot-line benchmark |
| `tests/test_search_contracts.py`, `test_search_history.py`, `test_search_artifacts.py` | Contracts, transactions and permanent storage |
| `tests/test_search_checks.py`, `test_search_evaluate.py`, `test_search_run.py` | Evidence, operation coverage and scheduling |
| `tests/test_search_export.py`, `test_search_cli.py` | Inspection, replay references and native scenes |
| `tests/integration/test_piping_search_code_aster.py` | Opt-in real backend qualification |
| `docs/content/piping-search.md`, `docs/content/autorouting.md` | Usage, scope and links to the search workflow |

No changes to `tuba/assemblies.py` are required. Do not change
`tuba/project/solve.py` or `promote_evidence` to retain every ordinary solve.
Do not rebuild the packaged viewer unless an actual viewer source change occurs
in a subsequent milestone.

## Shared contracts

The names in this section are the interfaces implemented by the tasks below.
Use frozen dataclasses, explicit `to_dict`/`from_dict` methods and JSON with
`allow_nan=False`. Reject Boolean values wherever a numeric measurement, limit,
budget or sequence is required. Keep full precision; do not round engineering
inputs for identity or caching.

| Type | Fields and rules |
| --- | --- |
| `Candidate` | `id: str`, `parent_ids: tuple[str, ...]`, `parameters: dict[str, JsonValue]`, `intent: str`; unique proposal identity, parameters are JSON literals |
| `CheckSpec` | `id: str`, `kind: str`, `required: bool`, `operations: tuple[str, ...]`, `target_refs: tuple[str, ...]`, `limit: float | None`, `unit: str | None`, `options: dict[str, JsonValue]`; explicit scope and coverage |
| `CheckResult` | `constraint_id: str`, `verdict: str`, `required: bool`, `basis: str`, `reason_code: str`, `message: str`, plus default-empty `entity_refs`, `evidence_refs`, `details`, and default-None `operation`, `result_state_id`, `measured_value`, `limit`, `unit`, `comparator`; verdict and evidence must agree |
| `Evaluation` | `id`, `candidate_id`, `attempt_id`, `status`, `operations`, `completed_operations`, `checks`, `evidence_manifest_ref`, `error_kind`; tuples for collections, optional final two references when evaluation is incomplete |
| `Decision` | `candidate_id`, `evaluation_id`, `outcome`, `reason_codes`, `primary_constraint_id`, `comparison_ids`, `details`; stored decisions are never rewritten |
| `SearchDefinition` | `parameter_grid: dict[str, tuple[JsonValue, ...]]`, `objective_fields: tuple[str, ...]`, `candidate_limit: int`, `max_solver_calls: int`, `max_artifact_bytes: int | None`; finite, nonempty inputs and explicit bounded budgets |
| `LoadedSearch` | `project`, `namespace`, `settings`, `definition`, `check_specs`, `build_candidate`, `user_evaluator`; validated authored source, native `StudySettings`, and project-owned optional evaluator |

`JsonValue` is recursive JSON data: None, Boolean, finite number, string, list or
string-keyed dict. Records may use tuples internally but serialize them as arrays.
`entity_refs` and `evidence_refs` in check results are tuples of strings. Persist
candidate/attempt scope outside a native `EntityRef`; native IDs alone are not
global identifiers.

Evaluation statuses are `complete`, `failed`, `interrupted`, `not_started` and
`blocked`. Decision outcomes are the vocabulary in the roadmap. Built-in check
kinds for M1 are `cold_model`, `cold_clearance`, `evidence_verified`,
`operating_clearance`, `reaction_force` and `displacement`. A project-owned
`user_evaluator` kind is supported only when an actual evaluator is configured;
absence is a required unknown. Predictions cannot produce a required pass.

`not_applicable` requires a reason and an applicability condition in the authored
check spec. Missing data, unknown entities and unsupported geometry do not meet
that condition. The run always includes the cold-model gate and an evidence
verification gate for each required operation; source configuration cannot
disable them.

The M1 public functions are:

```text
load_search(project: Project) -> LoadedSearch
grid_parameters(definition: SearchDefinition) -> list[dict[str, JsonValue]]
evaluate_candidate(candidate, model, loaded, *, archive, history, solver=None) -> Evaluation
decide(evaluation: Evaluation, check_specs, required_operations) -> Decision
run_search(project_root: Path, run_dir: Path, *, resume: bool = False) -> dict
export_history(run_dir: Path, output_dir: Path) -> Path
write_candidate_review(run_dir: Path, candidate_id: str, output_dir: Path) -> Path
```

These are interface declarations, not runtime code. Task-specific algorithms
and tests below pin their behavior. Add type annotations using the defined
contracts, native `TubaModel`/`Project` types and the Task 2/3 classes.

## Task 1: Define records and acceptance semantics

**Files:** Create `tuba/search/__init__.py`, `tuba/search/contracts.py` and
`tests/test_search_contracts.py`.

**Consumes:** The shared contracts and outcome vocabulary above.
**Produces:** Their frozen dataclasses, strict round trips, configuration
validation and `decide`.

- [ ] Add failing tests for unknown verdicts, empty IDs, non-JSON parameters,
  invalid units, Boolean/non-finite measurements and unreasoned non-applicability.
  Include the following test with real constructors and defaults from the table:

  ```python
  import pytest
  from tuba.search.contracts import CheckResult

  @pytest.mark.parametrize("value", [float("nan"), float("inf"), True])
  def test_numeric_pass_requires_a_finite_measurement(value):
      with pytest.raises(ValueError):
          CheckResult(
              constraint_id="pump.force", verdict="pass", required=True,
              basis="code_aster", reason_code="within_limit", message="Force checked",
              operation="Hot", result_state_id="result_state:Hot",
              measured_value=value, limit=1000.0, unit="N", comparator="max",
              evidence_refs=("attempt:A/Hot/study_reac.csv",),
          )
  ```

- [ ] Run `python -m pytest tests/test_search_contracts.py -q`; observe failure
  because the new contracts are absent.
- [ ] Implement the dataclasses and validation. Numeric `max`/`min` checks require
  finite measurements, limits and matching units. Collision checks may use
  `comparator=None` and explicit native findings/coverage instead of inventing a
  minimum clearance for a no-clash result. Validate numeric required passes have
  evidence, operation and result-state scope.
- [ ] Implement decision precedence with this algorithm: explicit execution or
  checker error -> `evaluation_failed`; observed required failure ->
  `rejected_constraint`; absent/unknown required checks, incomplete operations or
  missing trusted evidence -> `incomplete`; otherwise -> `feasible_retained`.
  An interrupted attempt remains incomplete with an interruption reason. Never
  select inside `decide`; selection requires cross-candidate objective comparison.
- [ ] Add a test matrix for every precedence branch, including a required spec
  absent from the returned checks, an optional warning, and a justified
  non-applicability. Use a complete `Evaluation` with all required operations for
  the feasible case; an empty checks list cannot satisfy a nonempty check spec.
- [ ] Run the focused tests and commit only these files:

  ```powershell
  git add tuba/search/__init__.py tuba/search/contracts.py tests/test_search_contracts.py
  git commit -m "feat(search): define candidate and check records"
  ```

## Task 2: Append-only history and branch ancestry

**Files:** Create `tuba/search/history.py`, `tests/test_search_history.py`.

**Consumes:** Task 1 records.
**Produces:** `History.create(path, manifest)`, `History.open(path, readonly=False)`,
`record_candidate(candidate)`, `append(kind, payload, candidate_id=None) -> int`,
`events(after_seq=0) -> list[dict]`, `candidates() -> list[Candidate]`,
`manifest() -> dict`, and context-manager close. Methods are on `History`.

- [ ] Add restart, parent-validation and duplicate-ID tests. Use this round trip:

  ```python
  from tuba.search.contracts import Candidate
  from tuba.search.history import History

  def test_restart_preserves_branch_and_event_order(tmp_path):
      path = tmp_path / "history.sqlite3"
      with History.create(path, {"schema": "tuba.search.history.v1", "run_id": "R"}) as h:
          h.record_candidate(Candidate("C1", (), {"depth_m": 0.8}, "Initial loop"))
          h.record_candidate(Candidate("C2", ("C1",), {"depth_m": 1.0}, "Increase depth"))
          h.append("candidate.decision", {"outcome": "rejected_constraint"}, "C1")
      with History.open(path, readonly=True) as h:
          assert [c.id for c in h.candidates()] == ["C1", "C2"]
          events = h.events()
          assert [e["sequence"] for e in events] == [1, 2, 3]
          assert events[1]["payload"]["parent_ids"] == ["C1"]
  ```

- [ ] Run `python -m pytest tests/test_search_history.py -q` and observe the absent
  history module failure.
- [ ] Implement a versioned database with run metadata, candidates and events.
  Use foreign keys, one transaction for candidate registration plus its event,
  and `INTEGER PRIMARY KEY AUTOINCREMENT` for event sequence. Encode payloads as
  sorted strict JSON. Parents must already exist in the same run, so insertion
  cannot introduce ancestry cycles. A duplicate design receives a new candidate
  ID; a duplicate candidate ID is an error.
- [ ] Enforce append-only records with SQL triggers. The event table includes
  sequence, UTC timestamp, kind, candidate ID, producer and payload. Add equivalent
  immutable guards for candidate rows and the run manifest:

  ```sql
  CREATE TRIGGER events_no_update BEFORE UPDATE ON events
  BEGIN SELECT RAISE(ABORT, 'search events are immutable'); END;
  CREATE TRIGGER events_no_delete BEFORE DELETE ON events
  BEGIN SELECT RAISE(ABORT, 'search events are immutable'); END;
  ```

- [ ] Test attempted SQL mutation, unknown parent IDs, interrupted transactions,
  a second writer receiving a bounded busy error, unknown schema versions and
  reopening without changing database bytes. Start with sequential execution and
  one coordinator; do not add a distributed event allocator.
- [ ] Run the focused tests, then commit the two files with subject
  `feat(search): persist append-only trial history`.

## Task 3: Durable artifacts, inventories and recovery

**Files:** Create `tuba/search/artifacts.py`, `tests/test_search_artifacts.py`.

**Consumes:** Task 2 history and native evidence attestation formats.
**Produces:** `ArtifactStore(root)`, `capture_source(project, dependency_paths) -> str`,
`save_model(candidate_id, model) -> str`, `begin_attempt(candidate_id) -> str`,
`operation_dir(attempt_id, operation) -> Path`,
`seal_attempt(attempt_id, status) -> str`, `verify_inventory(manifest_ref) -> dict`,
and `recover(history) -> list[str]`. Methods are on `ArtifactStore`.

- [ ] Write tests proving sealed rejected output survives object destruction and
  process restart, invalid relative paths/symlinks are refused, and an archive
  inventory reports actual bytes and hashes. A small diagnostic file is enough
  for these storage tests; it must not be labelled a solver result.
- [ ] Run `python -m pytest tests/test_search_artifacts.py -q` and observe failure.
- [ ] Implement this owned layout; returned references are relative to `root`:

  ```text
  run_dir/
    history.sqlite3
    source/<digest>/model.py, study.py, search.py, explicit helper sources
    assets/<digest>/shared input asset
    candidates/<candidate_id>/parameters.json, model.json
    attempts/<attempt_id>/<operation>/native solver files
    attempts/<attempt_id>/inventory.json
    exports/<export_id>/search_history.json, events.jsonl
  ```

  Capture only the explicit source/dependency inventory. Exclude `.scratch`,
  `.tmp`, `.build`, dependencies, environments, Git internals and prior archives.
  Use the project's `__tuba_project_dependencies__` plus explicit CAD/data inputs;
  configuration references missing assets must fail before scheduling. Reject
  symlinks/reparse points and unsafe paths rather than following them. Record
  exact bytes, SHA-256 and logical names. Share unchanged source/assets; M1 does
  not need hard links or a separate copy of solver output in another archive.

- [ ] Implement streaming hashes and inventories. Write JSON to a sibling
  temporary file, flush and `fsync`, then `os.replace` to the final filename.
  The solver writes directly to its permanent attempt operation directory.
  `seal_attempt` records every available input/output/log on both success and
  failure. An inventory is not an execution attestation and never upgrades trust.
- [ ] Add interruption tests at: source-copy completion, inventory replacement,
  and before the completed event transaction. Recovery checks inventories and
  the event log, seals active orphan attempts as interrupted and appends a
  recovery event. It cannot invent checks or silently relaunch a solver.
- [ ] Inject `OSError` for full-disk writes. Preserve existing output, record the
  failure when the database is writable, and propagate a blocking storage error.
  Never clean up a failed trial to create space. Test that recovery is idempotent.
- [ ] Run the focused tests and commit with subject
  `feat(search): retain attempt artifacts and recover interruptions`.

## Task 4: Evaluate operations without touching project evidence

**Files:** Create `tuba/search/evaluate.py`, `tests/test_search_evaluate.py`.
Add record/lifecycle helpers to the Task 1/2 files only as required by this task.

**Consumes:** `LoadedSearch`, `ArtifactStore`, `History`, the native `StudySettings`
and existing export/solve/import APIs.
**Produces:** `evaluate_candidate` and its evaluation lifecycle events.

- [ ] Write tests with a temporary authored source project and a solver-port test
  double. Portable tests may replay committed real artifacts using
  `tests/project_replay.py`; do not fabricate an engineering result. Cover cold
  rejection, operation-one success followed by operation-two failure, import
  failure, missing runtime, cancellation and recorder failure. Snapshot source,
  project evidence and staging bytes before evaluation and assert no changes.
- [ ] Run `python -m pytest tests/test_search_evaluate.py -q` and observe failure.
- [ ] Implement the operation loop using the existing owners:

  ```python
  from tuba.project.freshness import export_study

  for operation in loaded.settings.operations:
      folder = archive.operation_dir(attempt_id, operation)
      exporter = loaded.settings.solver(folder)
      port = solver if solver is not None else exporter
      study = export_study(
          exporter, model, operation, folder, loaded.settings.volume_export,
      )
      run = port.solve_exported_study(model, study)
      run.validate_for_publication(model)
      runs[operation] = run
  ```

  Run `model.verify` with the archived authored script and cold-clearance policy
  before this loop. Adapt its native findings to Task 1 check records; structural
  errors or hard clashes block execution. Avoid checking geometry on structurally
  invalid models. Capture inputs/artifacts after each operation, before invoking
  any acceptance callback. Emit started/completed/failed events with operation,
  elapsed time and exact result-state IDs. A publication validation failure means
  untrusted/incomplete evidence, not a qualified engineering result.

  The optional solver argument supplies only the execution port; exports always
  use the native configured exporter. This preserves compatibility with the
  existing `ReplaySolver`, which implements `solve_exported_study` only.

- [ ] Wrap the loop and callbacks with failure preservation: seal the permanent
  attempt, retain completed operations and partial failing-operation output,
  mark outstanding required checks unknown and append a failed/interrupted
  evaluation. Propagate recorder/storage failures so scheduling stops. Runtime
  setup failures stop the run; ordinary candidate solver failures can be recorded
  while subsequent candidates continue within the budget. Never swallow
  `KeyboardInterrupt` or make a failure geometrically selectable.
- [ ] Test that the archive is finalized before a project-owned checker can
  reject or raise. Seal the solver attempt after operation execution and before
  check callbacks; its inventory status describes execution, while subsequent
  check/evaluation events describe acceptance. Keep checker diagnostics in the
  evaluation record without mutating a sealed solver inventory. A rejected check
  returns data; an exception is a checker
  execution failure. Neither path deletes completed solver artifacts. Preserve
  the original exception class and bounded diagnostic text with evidence links.
- [ ] Test operation coverage: all required operations must have complete,
  trusted evidence; a one-operation result cannot accept a two-operation study.
  Contact runs retain all `run.result_states`, not just their final state.
- [ ] Run these focused tests plus `tests/test_project_solve.py` and
  `tests/test_project_evidence.py`. Commit owned files with subject
  `feat(search): evaluate candidates in permanent solver attempts`.

## Task 5: Structured constraint adapters and explanations

**Files:** Create `tuba/search/checks.py`, `tests/test_search_checks.py`;
connect it in `tuba/search/evaluate.py`.

**Consumes:** Native `VerifyReport`, `ClashResult`, verified `AnalysisRun` objects
and `CheckSpec` records.
**Produces:** `evaluate_checks(model, runs, check_specs, *, user_evaluator=None) -> tuple[CheckResult, ...]`,
`verification_checks(report, check_specs) -> tuple[CheckResult, ...]`, and
`render_reason(result: CheckResult) -> str`.

- [ ] Write finite-evidence, unit, entity-coverage and operation/increment tests.
  Add this scalar helper API and its test:

  ```python
  import pytest
  from tuba.search.checks import compare_scalar

  @pytest.mark.parametrize("value", [None, float("nan"), float("inf"), True])
  def test_unavailable_reaction_is_unknown(value):
      result = compare_scalar(
          constraint_id="pump.force", value=value, limit=1000.0,
          unit="N", comparator="max", required=True, basis="code_aster",
          operation="Hot", result_state_id="result_state:Hot",
          entity_refs=("node:PumpNozzle",),
          evidence_refs=("attempt:A/Hot/study_reac.csv",),
      )
      assert result.verdict == "unknown"
      assert result.reason_code == "measurement_unavailable"
  ```

  `compare_scalar` takes exactly these keyword arguments and returns a
  `CheckResult`; `value` is an optional numeric input. It retains unavailable
  values as None and supplies a clear message without serializing NaN.

- [ ] Run `python -m pytest tests/test_search_checks.py -q` and observe failure.
- [ ] Implement native adapters. Force magnitude uses translational reaction
  components only, in N. Moment components are separate quantities and must not
  enter the force norm. Displacement magnitude uses translational components in
  m. Check every requested target across the authored operation/increment scope;
  absent target evidence is unknown. Retain the governing measurement and all
  observed failing targets, not only a maximum that hides missing nodes.
- [ ] For operating clashes, construct cold/operating states with
  `create_cold_geometry_state` and `create_operating_geometry_state`, then call
  `ClashEngine.check_operating_state` with the actual result state, analysis mesh,
  envelope type and clearance. Use engineering displacement scale 1 and preserve
  native distance/penetration semantics. Evaluate every retained contact
  increment when required by the policy. Unsupported scope or missing insulation
  information needed by the declared envelope is unknown, never assumed clear.
- [ ] Produce complete no-clash check records only after the engine finished for
  the declared scope. Keep hard overlap and required clearance failure distinct.
  Do not promote advisory clearance/sliding findings to required failures unless
  the authored policy declares them required.
- [ ] Define `study.py`'s optional project-owned `evaluate_search(context)` hook.
  Its context contains `model`, `runs`, `check_specs` and `candidate_id`; it returns
  `tuple[CheckResult, ...]`. Validate exact requested IDs, scopes, units and
  evidence references. Missing required evaluator output is unknown. Built-in
  FE stress summaries remain descriptive, not piping-code checks.
- [ ] Test explanation rendering includes constraint ID, operation, increment,
  target objects, measurement/limit/units and evidence. Cold/hot collision tests
  assert both entity references and location are retained. Test a successful
  force check does not erase a failed hot-clearance check, and early rejection
  leaves subsequent checks explicitly unexecuted.
- [ ] Run these tests plus `tests/test_operating_clash.py`,
  `tests/test_deformed_clash.py`, `tests/test_contact_findings.py` and
  `tests/test_verify.py`.
  Commit with subject `feat(search): explain constraint outcomes from evidence`.

## Task 6: Deterministic scheduling, reuse, budgets and selection

**Files:** Create `tuba/search/run.py`, `tests/test_search_run.py`;
extend exports in `tuba/search/__init__.py`.

**Consumes:** Tasks 1-5, native project loading/dependency tracking,
`expected_identity`, `evidence_verdict`, `import_code_aster_artifacts`.
**Produces:** `load_search`, `grid_parameters`, `run_search` and explicit reuse,
budget, resume and selection events.

- [ ] Add failing tests for deterministic enumeration and input immutability:

  ```python
  from tuba.search.contracts import SearchDefinition
  from tuba.search.run import grid_parameters

  def test_grid_order_is_stable():
      definition = SearchDefinition(
          parameter_grid={"width_m": (2.0, 3.0), "depth_m": (0.8, 1.0)},
          objective_fields=("pipe_length_m", "bend_count", "support_count"),
          candidate_limit=4, max_solver_calls=8, max_artifact_bytes=None,
      )
      assert grid_parameters(definition) == [
          {"depth_m": 0.8, "width_m": 2.0},
          {"depth_m": 0.8, "width_m": 3.0},
          {"depth_m": 1.0, "width_m": 2.0},
          {"depth_m": 1.0, "width_m": 3.0},
      ]
  ```

- [ ] Run `python -m pytest tests/test_search_run.py -q` and observe failure.
- [ ] Load `model.py` through `Project.run_model`, `study.py` through the current
  loader/settings validation, and `search.py` through
  `tuba.project.execution.execute_project_script`. Require authored
  `build_model(parameters)` and a bound default `model`. `search.py` declares
  `SEARCH: SearchDefinition`; `study.py` declares `SEARCH_CHECKS` and optionally
  `evaluate_search`. Capture all their explicit dependencies once.
- [ ] Build a fresh model for each proposal; archive exact parameters and derived
  model state. Never patch the authored source text or write a flat node script.
  Register every bounded proposal before scheduling so a budget stop leaves
  explicit deferred records. Record `candidate.built` with its complete
  design/environment digest and per-operation solver identities.
- [ ] Implement the fixed-order grid with the following core:

  ```python
  from itertools import product

  keys = sorted(definition.parameter_grid)
  parameters = [
      dict(zip(keys, values))
      for values in product(*(definition.parameter_grid[key] for key in keys))
  ]
  ```

  Reject a grid exceeding `candidate_limit` before materializing it, using the
  product of axis lengths. Preserve authored axis-value order. Rank feasible
  candidates lexicographically by the declared finite objective fields and
  proposal sequence as the final tie-breaker. The default tuple is pipe length,
  bend count, support count; no hidden penalty score. Retain each objective value
  and explicitly name the governing comparison in selection events.

- [ ] Distinguish identities: full design/obstacles/envelopes, native solver
  inputs, and check policy including evaluator source/dependencies. Reuse only
  inventories with intact artifacts and the existing verified evidence verdict
  for the exact expected solver identity. Reimport against the new model and
  revalidate provenance. Record reuse links and fresh checks under the new policy;
  do not rewrite older evaluations. Unknown/failed attempts are never cache hits.
- [ ] Add obstacle-only and limit-only change tests that reuse a qualified
  operation but create new design/check identities and verdicts. Add support,
  mesh and operation-change tests that require new solver evidence. A reused
  operation links to its original attempt with candidate-local entity mapping.
  Reimport failure is recorded instead of silently returning cached metrics.
- [ ] Count actual solver invocations, including failed calls; reused operations
  do not consume a fresh-solve count. Stop before exceeding the declared call
  budget. Enforce byte limits before scheduling and after artifact writes, and
  report actual retained bytes/free space. Storage/runtime blockers stop further
  scheduling. All skipped proposals get `deferred`, not constraint failures.
- [ ] Resume only a run with matching frozen source/configuration. Task 3 recovery
  marks interrupted attempts; continuing makes new attempts and preserves the
  earlier ones. A changed source/policy starts a new run with a parent-run link.
  M1 restart guarantees recorded replay, not identical newly executed physics.
- [ ] Test no-feasible, tied objectives, duplicates, missing objectives, budget
  exhaustion and restart. Require complete trusted operations and all required
  checks before emitting `selected`; test a cheap incomplete candidate cannot
  displace a feasible one. Commit with subject
  `feat(search): run bounded deterministic layout experiments`.

## Task 7: CLI inspection, portable history and native review

**Files:** Create `tuba/search/__main__.py`, `tuba/search/export.py`,
`tests/test_search_cli.py`, `tests/test_search_export.py`.

**Consumes:** Tasks 1-6; `SceneRequest`, `build_visualization_scene`,
`write_scene_bundle` and existing result publication validation.
**Produces:** The following proposed commands, `export_history` and
`write_candidate_review`:

```powershell
python -m tuba.search run examples/piping-search --run-dir D:/tuba-runs/Tuba_v4/initial-001
python -m tuba.search inspect --run-dir D:/tuba-runs/Tuba_v4/initial-001
python -m tuba.search inspect --run-dir D:/tuba-runs/Tuba_v4/initial-001 --candidate C0001
python -m tuba.search export --run-dir D:/tuba-runs/Tuba_v4/initial-001 --output D:/tuba-runs/Tuba_v4/initial-001/exports/replay-001
python -m tuba.search review --run-dir D:/tuba-runs/Tuba_v4/initial-001 --candidate C0001 --output D:/tuba-runs/Tuba_v4/initial-001/exports/review-C0001
python -m tuba.visualization.viewer D:/tuba-runs/Tuba_v4/initial-001/exports/review-C0001 --open
```

The first command creates a new run; `run ... --resume` requires an existing
matching run. Other commands are read-only over source history. `C0001` is the
first sequential proposal's actual recorded ID; attempts use unique IDs.

- [ ] Write parser/exit-code tests and a test where inspection/export succeeds
  with the solver factory made unavailable. Test missing run/candidate IDs,
  read-only input, conflicting output and damaged inventories.
- [ ] Run `python -m pytest tests/test_search_cli.py tests/test_search_export.py -q`
  and observe failure.
- [ ] Implement `inspect` as candidate rows followed by requested evidence-backed
  detail. Every outcome has a reason; unknown checks and unevaluated operations
  remain visible. Use exit 0 for valid inspection/export and a run with a selected
  candidate; 2 for invalid command/configuration; 3 for a completed run without a
  feasible candidate; 4 for a runtime/storage/history blocker. Never print an
  engineering-success message merely because a CLI process finished normally.
- [ ] Export `search_history.json` with schema `tuba.search.replay.v1`, frozen
  run/criteria/objective records, scoped candidates/attempts/checks/decisions,
  available artifact inventories and ordered timeline events. Export a matching
  `events.jsonl`. All references are relative and include hash/size where files
  are referenced. Missing artifacts produce explicit availability diagnostics.
  The manifest carries parent edges, proposal/completion order, failed and
  unexecuted checks, and governing operation/increment; no video generation yet.
- [ ] Keep schema namespaces explicit: a result reference is
  `(candidate_id, attempt_id, operation, result_state_id)`, not just the native
  `result_state_id`. Test two candidates both contain `result_state:Hot` and the
  exported checks resolve their distinct artifact directories. Later decisions
  must not hide historical decisions on the same candidate.
- [ ] `review` reconstitutes derived candidate state from the archived model,
  imports verified results from retained attempts, revalidates identities and
  uses the existing scene builder. Include recorded clash findings and check
  associations in existing review metadata. A geometry-only candidate can show
  an explicitly unsolved preview; it cannot display stress/displacement/reactions.
  Scene generation is on demand. Reuse native staging/publication rather than
  introducing custom result meshes or another renderer.
- [ ] Export publication creates new files only in a new owned output folder,
  verifies referenced files, and reports measured output bytes. Do not silently
  overwrite an existing export. Do not copy the complete run archive per export;
  link history references to the retained archive and state that moving a manifest
  alone is not a self-contained handoff. Native review bundles follow their
  existing complete-bundle handoff contract.
- [ ] Run focused tests plus `tests/test_visualization_scene.py`,
  `tests/test_visualization_clash_review.py` and `tests/test_staged_run.py` for the
  native-review adapter. Commit with subject
  `feat(search): inspect trials and export replay records`.

## Task 8: Authored benchmark, real solver qualification and documentation

**Files:** Create the four `examples/piping-search/` files,
`tests/integration/test_piping_search_code_aster.py`, `docs/content/piping-search.md`;
link it from `docs/content/autorouting.md`. Amend earlier search tests for any
newly observed failures, without broadening their scope unnecessarily.

**Consumes:** The complete M1 API and current configured Code_Aster runtime.
**Produces:** A reproducible, explicitly scoped demonstration and a measured
qualification record. The real integration test opts in with
`TUBA_RUN_CODE_ASTER_INTEGRATION=1`, matching existing integration conventions.

- [ ] Write the opt-in integration test first. It invokes the public search
  entry point in a new run directory, checks native Code_Aster attestations and
  parsed result artifacts, and asserts the benchmark acceptance criteria below.
  With opt-in enabled it must fail loudly for an unavailable runtime, not skip
  the promised validation or substitute a fixture. Portable unit tests can skip
  real execution when opt-in is absent.
- [ ] Author `model.py` with `build_model(parameters)` and
  `model = build_model(DEFAULT_PARAMETERS)`. Use engineering constants and the
  existing route/loop generator/adapter or procedural builder. Define a bounded
  8 m hot line, explicit endpoint conditions, an equipment obstacle and support
  locations that correspond to actual support structures. Do not implement new
  one-off classes in `tuba/assemblies.py`.
- [ ] Parameterize loop width/depth and an explicit guide/support arrangement.
  Use a small fixed grid that fits the declared solver budget. Supports for the
  evaluated and displayed candidate must be identical; do not rely on scorer-only
  endpoint anchoring. Include material, section, insulation, fluid mass and
  endpoint assumptions in the source and archive. Reuse the existing expansion
  example as an authoring reference, not its results after geometry changes.
- [ ] Define sustained and hot operations in `study.py`, with explicit
  `SOLVER_OPTIONS`, `SEARCH_CHECKS` and `build_review`. Fix demonstration limits
  before qualification. Include required cold/operating clearances, named
  reaction-force and displacement checks, with real targets and units. State
  that piping-standard compliance is not configured in this example; a production
  study requiring it must provide its evaluator or remain incomplete.
- [ ] Choose obstacle envelopes so the grid exercises cold and operating-state
  rejection, and include sufficient geometric flexibility for an engineering
  reviewer to identify at least one plausible feasible arrangement. Do not
  guarantee a particular improvement direction or fabricate thresholds from
  desired output. If the fixed benchmark has no feasible candidate, investigate
  its geometry/support assumptions and document the revision before a new run;
  never rewrite old criteria or trials to hide that result.
- [ ] In `search.py`, declare `SEARCH` with explicit candidate/call budgets and
  objectives. In its README, include setup, units, assumptions, commands, named
  checked requirements, evidence directory ownership and the expected kinds of
  outcome. Explain the archived result inventory and how to inspect a rejected
  candidate's governing load/constraint in the existing viewer.
- [ ] Run narrow portable tests once after the final implementation fixes:

  ```powershell
  python -m pytest tests/test_search_contracts.py tests/test_search_history.py tests/test_search_artifacts.py tests/test_search_checks.py tests/test_search_evaluate.py tests/test_search_run.py tests/test_search_cli.py tests/test_search_export.py -q
  ```

  Run the adjacent checks named by Tasks 4/5/7 only when their adapters changed.
  Use the existing environment from the isolated source checkout; do not create
  another dependency/cache installation. If the environment points imports at
  another checkout, use `PYTHONPATH` for this worktree and verify module provenance.

- [ ] Verify the real runtime, then run the qualification using the existing
  Python-managed Code_Aster environment. PowerShell commands when using the
  checkout's Windows Python are:

  ```powershell
  python -m tuba.solver.code_aster_doctor --check
  $env:TUBA_RUN_CODE_ASTER_INTEGRATION = '1'
  python -m pytest tests/integration/test_piping_search_code_aster.py -q
  ```

  Prefer the qualified shared Linux/WSL Python-managed bridge when configured.
  A successful doctor probe is runtime evidence, not the benchmark solve.
  Record the actual selected runtime/version and invocation rather than assuming
  this baseline's previously stored WSL artifacts prove present readiness.

- [ ] Require the measured benchmark record to demonstrate: a retained cold
  rejection; a completed solved rejection with exact check/state/evidence links;
  a candidate passing every required demonstration operation/check; a
  feasible-but-not-selected or explicitly tied alternative when present; and
  inspect/export after restart with Code_Aster unavailable. Add a fault-injection
  case proving partial output survives evaluation failure, kept separate from the
  real-result qualification. Report actual counts; do not assert counts invented
  before running the final benchmark.
- [ ] Write a small qualification manifest in the durable run directory with
  source SHA/dirty diff, builder/study/check digests, runtime/version, operation
  coverage, tested candidate IDs, solver calls, test totals, retained bytes/free
  space and scope limitations. Preserve all rejected evidence. Do not refresh
  unrelated galleries or generate a whole-repository archive.
- [ ] Run `git diff --check`, verify source-only staging, and commit only the
  example/test/documentation paths with subject
  `feat(search): qualify the retained hot-line search workflow`.

## Final review and handoff

- [ ] Check every roadmap M1 acceptance requirement against its owning task and
  actual verification evidence. Search proposed code/plan for unfinished markers
  and resolve interface/name mismatches before implementation is declared ready.
- [ ] Review full event histories for a constraint failure, an evaluation failure,
  an incomplete attempt, a duplicate and a selected candidate. Their explanations
  must describe their different outcomes accurately.
- [ ] Verify cold/hot geometry, insulation envelopes, supported entity coverage,
  units, operation/increment selection and physical deformation scale against
  native records. A scalar score is not sufficient review evidence.
- [ ] Confirm a film implementer can recover ordered events, ancestry, exact
  candidate geometry, governing solver states, spatial findings and selection
  comparisons without asking the agent to reconstruct its earlier reasoning.
- [ ] Preserve source, the final run database/inventories, all required trial
  evidence and qualification logs. Remove only completed task-owned temporary
  files after verifying absolute paths and link boundaries. Keep active attempts
  and worktrees with uncommitted changes.
- [ ] Commit locally and hand off the implementation with document links, measured
  validation results, the durable archive path and any real solver blocker. Push
  only if the user explicitly asks.
