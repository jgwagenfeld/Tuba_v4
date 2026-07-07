# Remaining Architecture Gap Workplan

Status: current remaining-work plan, refreshed 2026-07-07.

Source review: `docs/architecture/library-architecture-review.md`.

Goal: close the remaining architecture gaps without changing Tuba's product
contract:

```text
Tuba model -> Code_Aster solve -> imported artifacts -> reviewed results
```

This plan is intentionally not a rewrite plan. Keep `TubaModel`,
`CodeAsterSolver`, `tuba.plotting`, `tuba.visualization`, and `viewer/` as the
main boundaries.

## Implementation Notes

- 2026-07-07 baseline: `python -m unittest discover -s tests -p "test*.py"`
  ran 432 tests successfully with 3 skips.
- 2026-07-07 doc/API guards:
  `python -m unittest tests.test_code_aster_docs tests.test_current_api_docs -v`
  ran successfully.
- 2026-07-07 runtime proof: WSL/Ubuntu doctor reported `wsl -d Ubuntu --`
  ready; `tests.test_code_aster_real_smoke` passed with real Code_Aster.
- 2026-07-07 mixed runtime finding: the previous mixed test reached
  Code_Aster with an invalid fallback MED and failed at `LIRE_MAILLAGE`
  because the mixed path is not solve-ready. Mixed exports are now explicitly
  marked `export_only`/`code_aster_solve_ready=False`, and
  `solve_exported_study(...)` stops before solver execution until the mixed
  STEP path has real Code_Aster proof.
- 2026-07-07 runtime diagnostics: Code_Aster failure messages now include the
  attempted command, return code, stdout/stderr tails, and per-runtime log paths.
- 2026-07-07 final verification after the first execution slice:
  `python -m unittest discover -s tests -p "test*.py"` ran 432 tests
  successfully with 2 skips.
- 2026-07-07 Phase 2 guard slice: current API docs now scan non-roadmap
  architecture docs, roadmap architecture docs must say `roadmap`, and
  export-only examples must state they are not a completed engineering
  evaluation.
- 2026-07-07 Phase 3 discipline slice: added a `.comm` command-order
  regression test. No production refactor was needed because support compilation
  is not duplicated and load helpers already live in `tuba/solver/aster_loads.py`.
- 2026-07-07 Phase 4 first slice: linear temperature fields scoped by
  route/station now export as per-element midpoint `CREA_CHAMP` assignments.
  Pressure, wind, and piecewise profiles remain blocked before export. A real
  WSL/Ubuntu Code_Aster smoke solved and produced `study_depl.csv`,
  `study_effo.csv`, `study_reac.csv`, and `study_sieq.csv`.
- 2026-07-07 Phase 5 guard slice: wind remains limited to beam-modeled
  `FORCE_POUTRE(TYPE_CHARGE='VENT')`; `TUYAU_3M` wind and `FORCE_NODALE`
  production shortcuts are rejected/documented, and seismic remains a separate
  vertical slice.
- 2026-07-07 Phase 5 runtime proof: beam wind now writes
  `AFFE_CHAR_MECA_F` with constant `FORMULE` components. WSL/Ubuntu Code_Aster
  solved both a beam-only wind case (`DEPL`, `EFFO`, `REAC`; no `SIEQ`) and a
  pipe-plus-beam wind case (`DEPL`, `EFFO`, `REAC`, `SIEQ`).

## Global Rules

- Do not show stress, displacement, reaction, compliance, clash, or result
  visualization values unless they came from real Code_Aster artifacts.
- Do not treat `.comm`, `.mail`, or `.export` generation as a completed
  engineering workflow.
- Do not add a third visualization path.
- Do not vendor or copy ada-py code.
- Do not guess B31J factors from secondary sources.
- Do not split `tuba/solver/aster_comm.py` for style. Extract only concrete,
  repeated command-generation seams.
- Each implementation phase must leave the portable test suite green and must
  not add skips.

## Phase 0: Baseline And Drift Check

Intent: make every later phase start from the real checkout, not stale plan
paths.

Files to read:

- `docs/architecture/library-architecture-review.md`
- `tuba/solver/aster.py`
- `tuba/solver/aster_comm.py`
- `tuba/solver/aster_loads.py`
- `tuba/solver/code_aster_runtime.py`
- `tuba/analysis/code_aster_notebook.py`
- `tuba/analysis/code_aster_artifacts.py`
- `tuba/visualization/builders.py`
- `tests/test_current_api_docs.py`
- `tests/test_code_aster_docs.py`

Steps:

- [x] Run `git status --short` and note unrelated dirty files.
- [x] Run the portable baseline:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test*.py"
```

- [x] Run doc/API guard tests:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_code_aster_docs tests.test_current_api_docs -v
```

- [x] Run `python -m tuba.solver.code_aster_doctor --check` through the repo
  venv and capture the runtime status.
- [x] Update this plan if any named file or test module has moved.

Acceptance:

- Current test count, skip count, and Code_Aster runtime status are recorded in
  the implementation notes before code changes start.

## Phase 1: Real Code_Aster Runtime Proof

Intent: make "real solver available" a reproducible local/integration boundary,
not a vague environment claim.

Files:

- `docs/code_aster_installation.md`
- `README.md`
- `tuba/solver/code_aster_runtime.py`
- `tuba/solver/code_aster_doctor.py`
- `tests/test_code_aster_runtime.py`
- `tests/test_code_aster_doctor.py`
- `tests/test_code_aster_real_smoke.py`
- `tests/integration/test_code_aster_real_smoke.py`
- `tests/integration/test_mixed_code_aster_runtime.py`

Steps:

- [x] Run the doctor with the intended production method:

```powershell
$env:TUBA_CODE_ASTER_EXEC_METHOD = "wsl"
$env:TUBA_CODE_ASTER_WSL_DISTRO = "Ubuntu"
.\.venv\Scripts\python.exe -m tuba.solver.code_aster_doctor --check
```

- [x] No setup/documentation mismatch was found; solver parsing and notebooks
  were left alone during runtime proof.
- [x] When the doctor is green, run the real pipe smoke:

```powershell
$env:TUBA_RUN_CODE_ASTER_INTEGRATION = "1"
.\.venv\Scripts\python.exe -m unittest tests.test_code_aster_real_smoke -v
```

- [x] Run the mixed runtime smoke only after the pipe smoke passes:

```powershell
$env:TUBA_RUN_CODE_ASTER_INTEGRATION = "1"
.\.venv\Scripts\python.exe -m unittest tests.integration.test_mixed_code_aster_runtime -v
```

- [x] Make runtime failure messages include the attempted method, command, return
  code, and log file paths.
- [x] Reviewed `docs/code_aster_installation.md`; no update was needed because
  the actual doctor output matches the documented flow.

Acceptance:

- `code_aster_doctor --check` reports an `ok` runtime on the target machine.
- Real pipe smoke solves and imports `study_depl.csv`, `study_effo.csv`,
  `study_reac.csv`, `study_sieq.csv`, and optional `study.rmed`.
- If the machine is not configured, the doctor and integration tests fail or
  skip with a precise setup blocker.

## Phase 2: Stop Roadmap/API Overclaims

Intent: prevent current docs, notebooks, and examples from teaching future API
as shipped behavior.

Files:

- `README.md`
- `docs/architecture/library-architecture-review.md`
- `docs/architecture/user-facing-piping-dsl-and-agent-ops.md`
- `notebooks/*.ipynb`
- `examples/*.py`
- `tests/test_current_api_docs.py`
- `tests/test_notebook_code_aster_results.py`

Steps:

- [x] Extend `tests/test_current_api_docs.py` to include current-code
  architecture docs, not only README/examples/notebooks.
- [x] Keep roadmap docs allowlisted only when they clearly say roadmap.
- [x] Add a guard that export-only examples include the phrase "not a completed
  engineering evaluation" or equivalent.
- [x] Add a guard that notebooks do not instantiate `FEAResults`, `NodeResult`,
  or `ElementResult` by hand in result-display cells.
- [x] Move any future DSL examples out of current-code docs or label them as
  roadmap.

Acceptance:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_current_api_docs tests.test_notebook_code_aster_results -v
```

Expected: current docs use shipped API only; export-only workflows are visibly
handoff/diagnostic paths.

## Phase 3: Keep `_write_comm(...)` Disciplined

Intent: make the Code_Aster writer easier to extend without inventing a generic
solver DSL.

Files:

- `tuba/solver/aster_comm.py`
- `tuba/solver/aster_loads.py`
- optional only when needed: `tuba/solver/aster_supports.py`
- `tests/test_code_aster_study.py`
- `tests/test_operation_fields.py`
- `tests/test_code_aster_docs.py`

Steps:

- [x] Add focused `.comm` regression tests before refactoring any command
  generation.
- [x] Keep `_write_comm(...)` as the command-order owner: `DEBUT`,
  `LIRE_MAILLAGE`, model, material, characteristics, loads, solve, derived
  fields, output, `FIN`.
- [x] Leave support compilation in `_write_comm(...)` unless the same support
  logic is needed in at least two places.
- [x] Extract only concrete repeated load writers into helpers. Current good
  pattern: `tuba/solver/aster_loads.py`.
- [x] For every new Code_Aster command, update the command map in
  `docs/architecture/library-architecture-review.md` in the same change.
- [x] Do not add a new abstraction unless it removes real duplication across
  multiple generated command blocks.

Acceptance:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_code_aster_study tests.test_operation_fields tests.test_code_aster_docs -v
```

Expected: generated command snippets remain behaviorally unchanged except for
the specific new feature under test.

## Phase 4: Linear And Piecewise Operation Fields

Intent: finish the operation-field model so non-uniform pressure/temperature is
not a schema-only concept.

Files:

- `tuba/model.py`
- `tuba/validation.py`
- `tuba/solver/aster_loads.py`
- `tuba/solver/aster_comm.py`
- `tuba/analysis/results.py`
- `tests/test_operation_fields.py`
- `tests/test_code_aster_study.py`
- `tests/test_code_aster_results.py`

Steps:

- [x] Pick one profile first: `linear` temperature by route/station. Do not
  implement pressure and piecewise in the same first slice.
- [x] Define exact interpolation semantics for the first slice: linear
  temperature is interpolated at the midpoint of each selected element's
  overlap with the route/station range.
- [x] Add validation for monotonic station breakpoints and overlapping profile
  ranges.
- [x] Compile the profile to documented Code_Aster commands. Prefer
  `CREA_CHAMP`/field assignment patterns already used for thermal loads.
- [x] Export enough mesh groups or nodal values to make the generated `.comm`
  inspectable.
- [x] Import/verify solver output against a small real or fixture-backed study.
- [ ] Add the second profile only after the first profile has solver/result
  proof.

Acceptance:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_operation_fields tests.test_code_aster_study tests.test_code_aster_results -v
```

Expected: unsupported profiles no longer fail by default once implemented; they
either compile to documented Code_Aster fields or fail before export with a
precise message.

## Phase 5: Wind And Seismic Loads

Intent: complete occasional-load support only where Code_Aster semantics are
documented and end to end.

Files:

- `tuba/model.py`
- `tuba/validation.py`
- `tuba/solver/aster_loads.py`
- `tuba/solver/aster_comm.py`
- `tuba/compliance/asme_b313.py`
- `tuba/routing/solver_loop.py`
- `tests/test_operation_fields.py`
- `tests/test_routing_solver_loop.py`
- `tests/test_compliance_b31j.py`

Steps:

- [x] Keep current wind support limited to beam-modeled elements using
  `FORCE_POUTRE(TYPE_CHARGE='VENT')`.
- [x] Research Code_Aster documentation before adding wind for `TUYAU_3M`.
  If no documented distributed pipe wind command exists, keep rejecting it.
- [x] Do not use `FORCE_NODALE` as a production pipe-wind shortcut.
- [ ] Add seismic as a separate vertical slice:
  - model record;
  - validation;
  - Code_Aster command map entry;
  - writer;
  - parsed result check;
  - routing/compliance usage.
- [x] Add examples only after the real or gated solver proof exists. No new
  examples were added in this guard slice.

Acceptance:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_operation_fields tests.test_routing_solver_loop tests.test_compliance_b31j -v
```

Expected: every occasional load is either a documented Code_Aster-backed solver
path or rejected before export.

## Phase 6: B31J Tee/Branch Factors

Intent: add tee/branch compliance only from authorized data.

Files:

- `tuba/compliance/sif.py`
- `tuba/compliance/asme_b313.py`
- optional: `tuba/compliance/b31j_data.py`
- `tests/test_compliance_b31j.py`
- docs only after data boundary is clear:
  `docs/architecture/b31j-compliance-migration.md`

Steps:

- [ ] Define a data-provider interface for B31J factors. Keep it small:
  lookup by fitting type, geometry, reinforcement/pad state, and edition.
- [ ] Add tests with tiny user-provided synthetic tables that prove lookup,
  interpolation, and missing-data errors without embedding licensed values.
- [ ] Add a runtime error for tee/branch cases when no authorized table is
  configured.
- [ ] Wire authorized tables through configuration or explicit function input.
- [ ] Add real factor tests only when licensed/user-provided source data is
  available.
- [ ] Document exactly which ASME edition/table source was used, without
  copying protected tables into public docs.

Acceptance:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_compliance_b31j -v
```

Expected: bend and existing safe checks keep working; tee/branch factors either
come from an authorized table or fail clearly.

## Phase 7: Mixed STEP Solve, Import, And Review

Intent: move mixed STEP from export/handoff to real solved review workflow.

Files:

- `tuba/mixed.py`
- `tuba/geometry/step_analysis_importer.py`
- `tuba/solver/mixed_study.py`
- `tuba/solver/aster.py`
- `tuba/analysis/code_aster_artifacts.py`
- `tuba/visualization/builders.py`
- `tests/test_mixed_model.py`
- `tests/test_mixed_code_aster_export.py`
- `tests/integration/test_mixed_code_aster_runtime.py`
- `tests/test_visualization_analysis_mesh.py`

Steps:

- [ ] Keep mixed export labeled handoff until Phase 1 runtime proof is green.
- [ ] Build the smallest mixed study: one pipe element coupled to one confirmed
  solid port with `LIAISON_ELEM`.
- [ ] Run it through real Code_Aster in the integration test.
- [ ] Import the generated result tables and optional RMED.
- [ ] Confirm `study_tuba_fem.json` maps solver names back to Tuba pipe/port
  references.
- [ ] Build a `ResultState` and web review bundle from the mixed result.
- [ ] Add a notebook/example only after the integration path passes or skips
  with a precise runtime blocker.

Acceptance:

```powershell
$env:TUBA_RUN_CODE_ASTER_INTEGRATION = "1"
.\.venv\Scripts\python.exe -m unittest tests.integration.test_mixed_code_aster_runtime -v
.\.venv\Scripts\python.exe -m unittest tests.test_mixed_code_aster_export tests.test_visualization_analysis_mesh -v
```

Expected: mixed STEP has a real solve/import/display path, or it remains
explicitly export-only with a runtime blocker.

## Phase 8: Final Evidence Gate

Intent: prove that docs, examples, solver boundaries, and review surfaces agree.

Steps:

- [ ] Run portable suite:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test*.py"
```

- [ ] Run doc guards:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_code_aster_docs tests.test_current_api_docs tests.test_notebook_code_aster_results -v
```

- [ ] Run viewer tests only if scene output changed:

```powershell
Push-Location viewer
npm.cmd test
npm.cmd run build
Pop-Location
```

- [ ] Run real solver gates on a configured machine:

```powershell
$env:TUBA_RUN_CODE_ASTER_INTEGRATION = "1"
.\.venv\Scripts\python.exe -m unittest tests.test_code_aster_real_smoke tests.integration.test_mixed_code_aster_runtime -v
```

Acceptance:

- Portable suite green with no new skips.
- Runtime-dependent gates pass on a configured solver machine or report a clear
  setup blocker.
- `docs/architecture/library-architecture-review.md` and this plan describe the
  same shipped/missing boundary.

## Completion Definition

The gap is closed only when:

- the model concept exists;
- validation rejects unsupported input before export;
- Code_Aster command generation is documented and tested;
- real or imported Code_Aster artifacts feed result display;
- notebooks/viewer examples do not use mock solver values;
- current-code docs no longer describe the item as missing.

Skipped: a new planning framework. Add one only if these checkbox phases stop
being enough to track implementation.
