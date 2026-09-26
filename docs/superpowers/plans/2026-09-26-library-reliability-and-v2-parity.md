# Library Reliability and V2 Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking. This document schedules the work; it does not authorize publishing, pushing, or replacing concurrent work.

**Goal:** Make Tuba's supported engineering workflows reject invalid input, restore valuable v2 piping capabilities, and qualify realistic combinations through Code_Aster and processed results.

**Architecture:** Keep the explicit Python model, native external-process Code_Aster integration, provenance-bearing `AnalysisRun`, and existing two visualization paths. Extend existing validation, physical-property, compiler-contract, and reporting owners. Deliver small end-to-end capabilities rather than a new solver abstraction or a library rewrite.

**Tech Stack:** Python >=3.11,<3.13, NumPy, pytest, Code_Aster, Gmsh, existing JSON/model contracts, GitHub Actions; existing PyVista and Three.js consumers only where a feature changes their inputs.

**Spec:** The requirements and acceptance criteria in this document derive from the 2026-09-26 library review requested in this conversation, v4 `f56240f1df5afa4fa1ec2b50385b4111e5ce8a2b`, v2 `fe4dbe0ebcd91e059fb69644683dcb4546a618c0`, and `AGENTS.md`. Read the related designs listed below before implementing their extensions. This is an umbrella work plan: Milestone 1 has immediate implementation tasks; Milestones 2-4 define separate subsystem plans to write before those implementations.

## Global Constraints

- "The whole point of Tuba v4 is to define piping structure, evaluate it with Code_Aster, and display processed results."
- "Do not present fabricated, mock, hand-built, or proxy values as solver results."
- "Do not treat `.comm`, `.mail`, or `.export` generation as a completed Tuba evaluation workflow."
- "If Code_Aster is unavailable, fail loudly with the runtime/setup blocker and stop before displaying or reporting solver results."
- "Solver integration must remain native Tuba code with external-process Code_Aster execution."
- Preserve authored procedural Python and the model -> solve -> processed-result workflow.
- Keep `tuba/plotting/` for quick-look/export and `tuba/visualization/` + `viewer/` for review bundles. Do not add a third display path.
- Built-in piping-standard checks remain retired. Material physics and solver flexibility are distinct from standards compliance and SIF calculations.
- Use an isolated worktree for multi-file implementation while other sessions use the checkout. Inspect HEAD and staged/unstaged changes first; stage only owned files. Planning here creates only this new document.
- Use `$env:UV_NO_SYNC='1'; uv run ...` for local Windows Python commands. Set real-solver opt-in explicitly; do not change the shared environment or lockfile merely to run a check.
- New engineering inputs must survive model serialization, authored/generated project replay, fingerprints, study compilation, result import, and reporting. Old artifacts must become stale when an engineering input changes.
- Invalid or unsupported engineering input must fail before meshing, launching a solver, overwriting valid artifacts, or publishing a review.

## Review Focus

1. Non-finite scalar input must never become a missing load or a passing validation result: Milestone 1, Tasks 1-2.
2. A material, section, or operation mutated after construction must be checked again at export/solve: Milestone 1, Tasks 1-2.
3. A missing Code_Aster runtime, empty test selection, or skipped required reference must fail the dedicated qualification job: Milestone 1, Task 3.
4. Changing fluid contents or a material curve must invalidate old evidence, including repeated nonlinear path endpoints: Milestone 2, Packages A-B and Milestone 3, Package F.
5. A result envelope must retain the governing case/increment and must not masquerade as one physically simultaneous nonlinear state: Milestone 4, Package H.

## Findings and baseline evidence

The review reproduced acceptance by validation and study export of negative E/density, invalid Poisson ratio, NaN wall thickness/temperature, infinite pressure, and corrosion allowance exceeding wall thickness. A NaN uniform temperature omitted the thermal load entirely. Reference owners are `tuba/validation.py`, `tuba/solver/aster_loads.py`, and the export entry points.

V2 has fluid weight (`tuba/define_properties.py:RhoFluid`), temperature-dependent material export (`tuba/write_Aster_file.py:ELAS_FO`), and tapered sections (`V_Reducer`, `VARI_SECT='HOMOTHETIQUE'`). These are implementation evidence, not claims that v2 was numerically qualified in this review.

The reviewed v4 baseline had 201 focused tests pass and nine skip. Two public-import subprocess timeouts passed on a separate 4/4 public-API rerun. Two real Code_Aster smoke/reference tests passed, including independent cantilever displacement and reactions. These are historical baseline results; rerun the appropriate checks on each implementation commit.

## Delivery order and dependencies

| Milestone | Deliverable | Depends on | Completion gate |
| --- | --- | --- | --- |
| 1. Reliability | Numerical admission rules; early study rejection; required solver-reference gate | Existing code | Invalid inputs fail before side effects; required reference tests run without skips |
| 2. V2 parity | A: fluid contents; B: material curves; C: concentric reducers | Milestone 1 | Each feature completes authoring -> Code_Aster -> imported review with independent expected values |
| 3. Combined workflows | D: study preflight; E: heated native solids; F: loaded friction histories; G: imported STEP solves | Milestone 1; relevant Milestone 2 inputs | Supported combinations have real reference evidence; others fail before meshing |
| 4. Review productivity | H: result comparisons/envelopes; I: convergence reports; J: catalogs | Qualified underlying features | Governing evidence is traceable; no invented results or implicit code-compliance claims |

Recommended sequence: **1 -> A -> B -> C -> D -> E -> F -> G -> H -> I -> J**. D may be brought forward when first extending a formulation. A and B can be designed independently, but both modify model/schema/provenance contracts, so their implementations need coordinated ownership. No calendar estimates are assigned until each later package's solver spike and implementation plan are complete.

The next implementation batch is **Milestone 1 only**. Milestones are independently reviewable and releasable; do not accumulate all four into one branch.

## Milestone 1: Reliability

### Implementation record, 2026-09-26 — complete

Branch `codex/library-reliability` is isolated at `.worktrees/library-reliability`,
based on `f56240f1df5afa4fa1ec2b50385b4111e5ce8a2b`. Implementation and reference
repairs are at `c4618ed13f16a566850a4606fd11e2a46401e119`. No merge or push is included.

Implemented numerical admission in the existing validator, added the three
missing pre-side-effect validation calls, and replaced smoke-only CI/release
qualification with the shared mandatory selection. Review also closed mutable
I-beam properties and coupled-pipe diagnostic gaps. No dependencies or solver
physics were changed.

Verification completed so far:

- Original baseline: 12 validation/export/schema tests passed.
- Numerical regression first run: 130 failed, 18 passed; implementation selection:
  208 passed and 5 subtests passed.
- Side-effect regression first run: 4 failed; implementation selection: 129 passed.
  Two real Code_Aster smoke/reference tests passed.
- Gate regression first run: 19 failed. Review regressions reproduced all three
  findings (one platform test, 13 numerical cases). After fixes, the combined
  selection passed 265 tests and 5 subtests. All 174 bundled I-beam profiles pass.
- First expanded real qualification: 31 passed, 1 failed, 2 subtests passed.
  The failure exposed a stale tee-reference calculation: the current mixed
  fixture supplies both model aliases and physical mesh reactions. The reference
  now counts each mesh reaction once and includes beam-anchor nodal moments.
  Its arithmetic regression failed first and passes after repair; the real tee
  reference passes both mesh sizes with its original tolerances. Gate/workflow
  tests then passed 33 tests.
- Full Python suite after the production fixes: 1,667 passed, 42 skipped,
  138 subtests passed in 1,178.59 s. One Windows ZMQ event-loop compatibility
  warning. The additional tee-helper regression is covered by the 33-test run
  above; the solver references require their separate opt-in run.
- Complete real-solver gate after the tee-reference repair: **32 passed, zero
  skipped, 2 subtests passed in 1,159.45 s**. Command exited zero and the shared
  gate independently accepted its JUnit report. This completes Milestone 1.

Local evidence is preserved under `.build/qualification/`: the JUnit report
`code-aster-references.xml`, `qualification-final.log`, `python-suite.log`,
`doctor.log`, and `implementation-log.md`. These generated files are not committed.

Real-solver execution uses WSL Ubuntu, Code_Aster `18.0.12 (n/a)`, after a passing
runtime doctor. The required file selection is listed under Task 3. Its existing
acceptance thresholds remain unchanged:

| Reference | Existing acceptance basis |
| --- | --- |
| Cantilever smoke | Displacement 3%; force and moment reactions 0.1% |
| Beam pipes | Axial, bending, thermal, elbow and refinement differences 1%; elbow reaction moment 0.1 Nm |
| Supports | Existing displacement/reaction/contact checks, including 1-2% references and Coulomb ratio 0.1% |
| Line loads | Existing 0.1-0.2% relative / 1 N absolute reaction comparisons |
| Nodal temperature | Displacement-vector error at most 0.25% |
| Pipe volumes | Hoop stress 5%, radial stress 8%, bend pressure resultant 3% |
| Mixed volumes | Solve/import, artifact identity and scene-contract assertions; these cases alone do not establish a numerical error bound |
| Tee refinement | Force 5%, moment 8%, stress 35%, hotspot movement 0.02 m, hotspot within 0.06 m of junction |
| Insulation | Weight and wind reactions `rel=1e-5` |
| Friction cycles | Force/equilibrium/Coulomb bounds 10 N, penetration 1e-5 m, refinement endpoint difference 30 N, plus existing slip/work/status checks |

Reproduce from the implementation worktree on this host:

```powershell
$env:UV_NO_SYNC='1'
$env:UV_PROJECT_ENVIRONMENT='D:\Gitprojects\Tuba_v4\.venv'
uv run python -m pytest -q --tb=short
$env:TUBA_CODE_ASTER_EXEC_METHOD='wsl'
uv run python -m tuba.solver.code_aster_doctor --check
uv run python scripts/check_code_aster_references.py
```

Decisions made during implementation:

- Reuse the installed Python environment with `UV_NO_SYNC=1` and
  `UV_PROJECT_ENVIRONMENT`, without installing packages. This preserves shared
  work; optional-package availability remains an environment constraint.
- Keep the JSON schema structural and the existing semantic validator authoritative.
  Callers using only `validate_model_dict` still receive structural checks.
- Add project-level admission before claiming or clearing solve staging. This adds
  one validation traversal but preserves prior artifacts on invalid forced solves.
- Correct the stale Pages test expectation to include its already-configured IFC
  dependency. The Pages workflow itself is unchanged.
- Require finite persisted I-beam properties, positive required A/IY/IZ/JX and
  supplied H/B/Tw/Tf, while preserving signed catalog offsets. Malformed custom
  sections previously admitted are deliberately rejected.
- Let newly mandatory beam, insulation and friction references inherit the runtime
  configuration instead of forcing WSL/Ubuntu. Local execution follows the same
  runtime discovery contract as Linux CI.
- Repair the tee reference's reaction aggregation instead of changing its
  convergence tolerances. It qualifies the existing mixed tee fixture; separate
  mixed-workflow checks remain in the gate.

Fresh review reported three Important findings, all fixed with failing-then-passing
regressions; no Minor findings were deferred. Its exclusions remain explicit:
later milestones are unimplemented, this is not a comprehensive admission audit
of every field/support/geometry/formulation, and numerical qualification is based
on the actual runs recorded here rather than the reviewer's inspection.

### Task 1: Reject invalid engineering scalars consistently

**Files:** Modify `tuba/validation.py`; modify `tuba/schema.py` only where schema admission otherwise contradicts semantic validation; inspect `tuba/model.py` reconstruction and section semantics. Create `tests/test_numeric_validation.py`; extend `tests/test_validation.py` and `tests/test_schema.py` as needed. Document input rules in `docs/content/reference/public-api.md`.

**Interfaces:** Preserve `validate_model(model: TubaModel) -> None`, `Model.validate()`, and `ModelValidationError`. Constructors may continue to assemble a model incrementally; validation and all execution boundaries must reject invalid completed records. Errors name the entity, property, supplied value, and expected domain. Reuse private validation helpers instead of adding a second validation API.

**Required admission rules:**

| Input | Rule |
| --- | --- |
| Material E | Finite and strictly positive |
| Material nu | Finite, -1 < nu < 0.5 for the supported isotropic elastic material |
| Material rho | Finite and nonnegative; zero remains valid for deliberately massless idealizations |
| Material alpha | Finite; zero and negative values are not rejected merely for their sign |
| Uniform temperature/reference temperature | Finite, in both operations and load cases; do not impose an arbitrary Celsius sign restriction |
| Uniform internal pressure | Finite and nonnegative for the current internal-pressure interface; explicitly reject negative values rather than silently dropping them |
| Pipe OD/WT | Finite, OD > 0, 0 < WT < OD/2 |
| Corrosion allowance | Finite, 0 <= allowance < WT; validation does not change the current stiffness/mass interpretation |
| Other section dimensions | Finite and consistent with the existing documented solid/hollow conventions; negative thickness is invalid |
| Cable radius/pretension/compression ratio | Finite; radius > 0, pretension >= 0, 0 <= ratio <= 1; retain the existing default in this task |

Do not clamp values, substitute zero, silently change cable behavior, or globally rewrite serializers. Catch inappropriate scalar types as actionable `ModelValidationError` messages rather than leaking incidental arithmetic exceptions.

- [x] Add the following regression to `tests/test_numeric_validation.py`, then parameterize the same admission boundary over the table above. Include both mutation and load-case/operation variants.

```python
import pytest
from tuba import Model
from tuba.validation import ModelValidationError

def test_nan_operating_temperature_is_rejected():
    model = Model('Invalid hot case')
    model.define_operation('Hot', temperature=float('nan'))
    with pytest.raises(ModelValidationError, match='Hot.*temperature'):
        model.validate()
```

- [x] Run `$env:UV_NO_SYNC='1'; uv run python -m pytest tests/test_numeric_validation.py -q` and record the missing-validation failures.
- [x] Implement shared finite/domain checks in `tuba/validation.py`; invoke material and uniform-case checks from `validate_model`, and strengthen `_validate_section`. Apply matching schema constraints where expressible; semantic finiteness checks remain authoritative for Python values.
- [x] Add passing boundary examples: zero density, zero alpha, a finite negative Celsius temperature, valid negative nu, zero pressure, zero corrosion, and the existing solid-bar representation. Add invalid string/bool values for material and load scalars so error behavior is deliberate.
- [x] Verify deserialized invalid records are refused by reconstruction or subsequent `validate()`; check mutable records cannot bypass admission. Preserve valid old-model round trips.
- [x] Run `$env:UV_NO_SYNC='1'; uv run python -m pytest tests/test_numeric_validation.py tests/test_validation.py tests/test_schema.py tests/test_tuba_core.py tests/test_operation_model.py tests/test_operation_fields.py -q`.
- [x] Review the diff and record the exact rules and test results. Commit only this task's owned paths when implementation is being committed; no repo-wide staging.

### Task 2: Enforce validation before study side effects

**Files:** Modify only the boundaries that fail the new tests in `tuba/solver/aster.py`, `tuba/solver/aster_volume.py`, `tuba/solver/mixed_study.py`, `tuba/solver/model_solve.py`, and `tuba/solver/compiler_contract.py`. Extend `tests/test_export_validation.py`, `tests/test_code_aster_volume_study.py`, `tests/test_mixed_code_aster_export.py`, and `tests/test_project_solve.py` where their public surfaces are involved.

**Interfaces:** Existing `export_study`, `analysis_study_inputs`, `export_analysis_study`, `volume_study_inputs`, mixed export, and `Model.solve` consume Task 1 validation. Preserve their signatures and successful return types. Do not reimplement scalar rules in individual writers.

- [x] Add an export regression with an output directory that does not exist. This pins the observed NaN-temperature failure and the side-effect boundary.

```python
def test_invalid_temperature_does_not_create_study(tmp_path):
    import pytest
    from tuba import Model
    from tuba.solver.aster import CodeAsterSolver
    from tuba.validation import ModelValidationError

    model = Model('Rejected before export')
    model.add_material('Steel', E=2e11, nu=0.3, alpha=12e-6)
    model.add_pipe_section('Pipe', OD=0.1, WT=0.01)
    with model.pipe(section='Pipe', material='Steel') as pipe:
        pipe.start([0, 0, 0], support='anchor')
        pipe.run(2)
    model.define_operation('Hot', temperature=float('nan'))
    output = tmp_path / 'study'
    with pytest.raises(ModelValidationError, match='Hot.*temperature'):
        CodeAsterSolver().export_analysis_study(model, 'Hot', output)
    assert not output.exists()
```

- [x] Run the export tests and inspect every entry point above. Extend existing volume/mixed fixtures with one invalid material and one invalid uniform load; spy on their meshing/runtime boundary and assert it is not called. Verify a pre-existing valid artifact directory remains byte-identical after rejection.
- [x] Move calls to the common validation boundary ahead of writes/meshing where tests require it. Ensure direct solver calls and the project solve path receive the same error. Do not remove formulation-specific guards.
- [x] Run `$env:UV_NO_SYNC='1'; uv run python -m pytest tests/test_export_validation.py tests/test_code_aster_study.py tests/test_code_aster_volume_study.py tests/test_mixed_code_aster_export.py tests/test_project_solve.py tests/test_solver_input_provenance.py -q`.
- [x] Run the two real Code_Aster smoke/reference tests using the command below, confirming valid loads still compile, solve, and import. Review and record the scoped result before committing owned changes.

```powershell
$env:UV_NO_SYNC='1'
$env:TUBA_RUN_CODE_ASTER_INTEGRATION='1'
$env:TUBA_CODE_ASTER_EXEC_METHOD='wsl'
uv run python -m pytest tests/test_code_aster_real_smoke.py -q
```

### Task 3: Make numerical qualification a shared CI/release gate

**Files:** Create `scripts/check_code_aster_references.py` and `tests/test_code_aster_reference_gate.py`; modify `.github/workflows/ci.yml` and `.github/workflows/release.yml`. Keep gallery refresh and publication validation as separate existing steps.

**Interfaces:** The new script is a local/CI command, not a public library API. `main(argv: list[str] | None = None) -> int` invokes pytest for an explicit reference-file list with `TUBA_RUN_CODE_ASTER_INTEGRATION=1`, writes JUnit XML under `.build/qualification/`, and returns nonzero for failures, errors, no tests, or any skips in this required selection. Pass through platform/runtime selection; do not force WSL on Linux. A failed runtime doctor stops the workflow before this command.

The initial required selection is:

```text
tests/test_code_aster_real_smoke.py
tests/test_code_aster_beam_pipes.py
tests/test_code_aster_supports.py
tests/test_code_aster_line_loads.py
tests/test_code_aster_node_temperatures.py
tests/test_code_aster_pipe_volume_reference.py
tests/test_code_aster_mixed_volume_reference.py
tests/test_code_aster_tee_volume_reference.py
tests/test_insulation_solver.py
tests/integration/test_code_aster_friction.py
```

- [x] Add tests around JUnit verdict handling for passing results, failures, errors, one skipped required case, and zero collected tests. Use actual minimal XML documents, for example `<testsuites><testsuite tests="1" failures="0" errors="0" skipped="1"><testcase name="reference"><skipped/></testcase></testsuite></testsuites>`, which must return a failing verdict.
- [x] Run `$env:UV_NO_SYNC='1'; uv run python -m pytest tests/test_code_aster_reference_gate.py -q` before implementation to establish failing cases.
- [x] Implement the small subprocess/JUnit gate. Count verdicts once rather than double-counting suite aggregates and child records. Remove only this invocation's previous report before running; a failed invocation must never reuse an old passing report. Preserve the subprocess failure code even if XML is absent.
- [x] Replace both workflows' smoke-only pytest command with `uv run python scripts/check_code_aster_references.py`. Retain the existing release dependency on `code-aster-integration`. Upload the qualification report on failure as well as success. Do not weaken existing gallery/release checks.
- [x] Run the gate tests and then the full real reference command locally with WSL selected. Record solver version, source SHA, selection, tolerances already asserted by each test, and result counts. A discovered engineering failure is a blocker with a bounded fix, not a reason to skip the case.
- [x] Keep self-hosted solver execution restricted to trusted code; do not expose it to arbitrary fork PRs. Main/manual/release qualification remains the default until runner isolation supports more triggers.
- [x] Review the workflow diff and commit the gate independently from physics changes. Milestone 1 is complete only when Tasks 1-3 pass on the integrated revision.

## Milestone 2: Restore valuable V2 capabilities

Each package below first produces its own design and implementation plan. Those plans must specify exact public signatures, default/backward-compatibility behavior, serialization, compiler support, and test commands. The decisions below are the bounded requirements; they are not permission to invent solver behavior while implementing.

### Package A: Operation-specific fluid contents

**Owners:** `tuba/model.py`, `tuba/schema.py`, `tuba/attributes.py` if scoped assignments reuse that owner, `tuba/physical.py`, `tuba/quantities.py`, `tuba/solver/aster_comm.py`, `tuba/solver/aster_loads.py`, `tuba/reporting/tables.py`, and provenance/project replay tests. Add `tests/test_fluid_contents.py` and `tests/test_code_aster_fluid_contents.py`.

- [x] Design operation-specific empty/full contents using density in kg/m3 and existing route/group/element selection conventions. Default to empty so existing models retain their meaning. Reject conflicting overlapping contents assignments. Defer partially filled/free-surface behavior until its geometry and scope are explicitly designed.
- [x] Implement the contents mass once in the physical-property owner; use it for gravity compilation and operation-specific quantity/report totals. Keep metal, insulation, and contents masses separately inspectable. Do not alter E or section stiffness to account for fluid mass.
- [x] Preserve the distinction between contents density and pressure; hydrotest users author both independently. Do not silently invent pressure head or fluid transients.
- [x] Qualify straight and bent 1D pipes, insulation plus fluid, empty/operating/hydrotest cases, and both supported 1D formulations. Reject unqualified solid/history combinations at preflight until their owning packages support contents.
- [x] Pin independent mass and reaction checks: for a full straight, `m_fluid = rho_fluid * pi * ID**2 / 4 * L`; summed gravity reactions must match total weight. For a bend, use arc length. Verify all reported mass totals and fingerprints change with density/case changes.

**Done:** One procedural example solves all three contents states, imports reactions/displacements, and reports attributable mass and reaction changes. Real-solver references join Task 3's gate.

Implementation and numerical qualification completed on `codex/fluid-contents`
(`816da68` implementation head). See [the package plan](2026-09-26-fluid-contents.md)
for APIs, evidence and exact limits: 45 mandatory real references passed without
skips, the full regression run and final boundary checks passed, and independent
review found no issues. Browser inspection of the local report was policy-blocked;
artifact checks passed. Package B remains the next planned task.

### Package B: Temperature-dependent material physics

**Owners:** `tuba/model.py`, `tuba/schema.py`, `tuba/solver/aster_comm.py`, `tuba/solver/aster_loads.py`, `tuba/analysis/provenance.py`, reporting and project replay. Create `tuba/materials.py` only if curve evaluation/validation requires a focused owner, plus `tests/test_material_curves.py` and `tests/test_code_aster_material_curves.py`.

- [ ] Design scalar-or-tabulated E, nu, and alpha, retaining scalar inputs unchanged. Require ordered unique finite temperatures, valid property domains, and explicit out-of-range behavior; default to rejecting extrapolation. Keep density scalar initially.
- [ ] Specify whether alpha is mean/secant or instantaneous, its reference temperature, and the conversion to Code_Aster's documented `ELAS_FO` convention. Read official `DEFI_MATERIAU` and `AFFE_MATERIAU` documentation before freezing the API. Do not copy v2's hard-coded 20 C reference or constant extrapolation blindly.
- [ ] Export material functions and temperature assignment even where temperature affects E but produces no thermal strain. Include an isothermal case at `temperature == ref_temperature` with a nonconstant E curve.
- [ ] Verify scalar/constant-curve equivalence, interpolation, endpoint values, out-of-range rejection, multiple materials, nonuniform temperatures, serialization and stale-evidence detection.
- [ ] Qualify an axial member under force against `u = F*L/(E(T)*A)` at uniform T; qualify free thermal expansion against an independently specified strain function and restrained expansion against its independent reaction. Pin numeric tolerances before evaluating solver outputs.

**Done:** Material curves survive the full workflow and have real independent references. No standards-derived allowable-stress evaluator is introduced.

### Package C: Concentric reducer parity

**Owners:** `tuba/builder.py`, `tuba/model.py`, `tuba/schema.py`, geometry/profile and meshing owners, `tuba/solver/aster_comm.py`, `tuba/physical.py`, and existing scene builders. Create `tests/test_reducers.py` and `tests/test_code_aster_reducers.py`.

- [ ] Inspect v2 `V_Reducer`/variable-section export and qualify Code_Aster's tapered-section support before selecting the initial formulation. The first capability is a finite-length concentric reducer with explicit inlet/outlet OD and wall thickness; eccentric reducers, flanges, and bellows stay outside it.
- [ ] Define a procedural builder operation and canonical record. Preserve node/route continuity, replay, mass, clash envelope, and section representation; do not approximate a taper by silently switching one uniform section at a node.
- [ ] Implement only the qualified formulation and fail other formulation requests before meshing. Keep reducer physics distinct from piping-code SIF checks.
- [ ] Test the equal-end limiting case against a straight pipe, volume/mass against independent integration of area along the taper, and axial compliance against `integral(1/(E*A(x)), x=0..L)`. Add mesh refinement and pressure/end-thrust checks before claiming pressure support.

**Done:** A straight-reducer-straight authored model solves and produces attributable forces/displacements with a correct taper in an existing review surface.

## Milestone 3: Complete combined engineering workflows

### Package D: Study-aware preflight

**Owners:** `tuba/verify.py`, `tuba/solver/compiler_contract.py`, `tuba/solver/aster.py`, `tuba/solver/aster_volume.py`, `tuba/project/study.py`, with tests in `tests/test_compiler_contract.py` and `tests/test_presolve_mesh.py`.

- [ ] Extend the existing pure study-input/compiler boundary to report incompatible loads, elements, supports, and formulation together before mesh creation. Preserve model-only verification as a useful operation.
- [ ] Move existing writer-only eligibility decisions into that boundary; writers consume the decision rather than duplicate a capability table. Return actionable entity/case references and supported alternatives without silently changing formulation.
- [ ] Exercise the same invalid combinations through Python solve, project solve, and export. Confirm no mesher/runtime invocation and no artifact mutation. Document the supported matrix from these tested rules.

**Done:** Users can inspect study eligibility without exporting, and all execution paths enforce the same eligibility rules.

### Package E: Thermal loading of native solid/mixed pipe studies

**Owners:** `tuba/solver/aster_volume.py`, `tuba/meshing/pipe_volume.py`, `tuba/solver/aster_volume_results.py`, and native volume reference tests. Recheck these owners at the implementation baseline.

- [ ] Write a separate plan extending the native-volume design. Begin with uniform temperature/reference temperature on native straight/bend/tee solids and 1D remainders, not arbitrary imported STEP thermal analysis.
- [ ] Support the same material definitions as the selected model, including Package B where applicable. Reject unsupported assignments rather than replacing them with one material or temperature.
- [ ] Qualify free expansion, fully restrained thermal reaction, pressure plus temperature, and mixed 1D/3D interface continuity/equilibrium. Use refinement studies near interfaces/tees; do not accept raw singular peak stress as a convergence metric.
- [ ] Import and review actual displacement, reactions, stress, load metadata, and changed provenance. Add scoped temperature fields, wind, and line loads as separate follow-on increments, each with its own references.

**Done:** A hot pressurized native tee in a mixed line completes a verified solve/review; unsupported fields remain explicit blockers.

### Package F: Pressure and contents through friction histories

**Owners:** `tuba/solver/aster_contact.py`, `tuba/solver/aster_comm.py`, `tuba/load_path.py`, `tuba/solver/contact_results.py`, history/provenance owners and `tests/integration/test_code_aster_friction.py`.

- [ ] First qualify the formulation strategy in a bounded real Code_Aster study: retaining TUYAU history versus extending POU_D_T pressure treatment. Evaluate pressure end thrust, thermal effects, and required result recovery before deciding. Keep current guards until that decision has evidence.
- [ ] Plan cold -> hot -> cold absolute states with pressure, contents, gravity, and nodal loads; preserve every converged increment and repeated state names. Extend prescribed support movement as a separate increment after load-history qualification.
- [ ] Check equilibrium, contact opening, sliding and reversal, path dependence, frictionless limits, penalty-stiffness sensitivity and load-step refinement. Check restart/caching cannot reuse evidence for changed intermediate endpoints.
- [ ] Keep native and derived contact statuses attributable; reject nonconvergence before result publication.

**Done:** A pressurized filled hot line on sliding shoes has qualified path results. Endpoint-only solves or algebraic superposition do not satisfy this package.

### Package G: Imported STEP components that actually solve

**Owners:** `tuba/geometry/step_analysis_importer.py`, `tuba/solver/mixed_study.py`, `tuba/mixed.py`, result-import owners and `tests/integration/test_mixed_code_aster_runtime.py`. Extend the existing imported-component design rather than creating another mixed-solver path.

- [ ] Select one reference component with stable port faces, one material, and a bounded mechanical load set. Define mesh groups, material assignment, load/support application, and compatible pipe-to-solid coupling explicitly.
- [ ] Implement missing solve/result extraction commands and qualify force/moment transfer, units, orientation, mesh refinement, and imported field lineage.
- [ ] Enable execution only for the qualified subset. Preserve export-only diagnostics for every other case and add one solved procedural example using imported results in an existing visualization path.

**Done:** A component attached to a line completes Code_Aster execution and verified import; merely writing a MED mesh or coupling command is insufficient.

## Milestone 4: Make qualified results easier to use

### Package H: Case comparisons and governing envelopes

**Owners:** `tuba/analysis/`, `tuba/reporting/tables.py`, `tuba/reporting/builder.py`; existing visualization consumers only if the result contract requires display changes.

- [ ] Design a comparison input of compatible verified `AnalysisRun` records; reject incompatible geometry/mesh/coordinate assumptions rather than matching by display label.
- [ ] Provide signed minima/maxima and governing operation/increment for support reactions, node displacement components, and element end forces. Preserve simultaneous vector components for each actual state alongside component-wise extrema.
- [ ] Distinguish hot/cold differences, component-wise envelopes, and approved linear combinations in types and labels. Never present an envelope or superposition of nonlinear states as a Code_Aster solved state.
- [ ] Test ties, missing entities, reversed local axes, stale evidence, repeated history labels, and mixed positive/negative extrema. Review one real multi-operation example.

### Package I: Convergence studies

**Owners:** Existing study/solver options, `tuba/analysis/mesh_quality.py`, reporting, and qualification tooling.

- [ ] Plan a small refinement runner over existing solver controls with explicit measured quantities, tolerances, and maximum refinement count. Retain every run's identity and artifacts.
- [ ] Report reaction balance, displacement change, selected stress measures, and solver/contact convergence separately. A runtime success or flat singular peak is not automatic convergence.
- [ ] Exercise a straight member, bend, and mixed interface; fail or report unresolved convergence when the refinement limit is reached.

### Package J: Traceable catalogs

**Owners:** `tuba/sections/catalog.py`, material owner introduced by Package B, packaging and docs.

- [ ] Start with explicitly sourced pipe dimensions/schedules and user-supplied material datasets. Record units, source, edition/version, temperature range, and permitted interpolation.
- [ ] Keep editable resolved values in the model so a future catalog update cannot silently change an existing project. Do not bundle unverified or unlicensed standards tables.
- [ ] Test catalog resolution against independent source records, model portability without the catalog, and reproducible fingerprints.

## Deferred work

Modal/seismic analyses, fatigue evaluation, bellows/expansion joints, specialized valve/flange models, eccentric reducers, and partially filled fluid behavior are separate future product decisions. No built-in piping-code certification/evaluator work is scheduled. Do not expand any package to cover them opportunistically.

## Definition of done for every engineering package

- [ ] A procedural Python example uses documented public inputs.
- [ ] Invalid and unsupported cases fail with actionable diagnostics before side effects.
- [ ] Serialization, project replay, fingerprinting, and evidence freshness account for every new engineering input.
- [ ] Independent reference values/invariants and tolerances are documented before interpreting solver outputs.
- [ ] Real Code_Aster execution, result import, and the selected existing review path work together.
- [ ] Dedicated reference tests join the required solver gate; no required case passes by skipping.
- [ ] Documentation states the exact supported formulation/load/support combinations.
- [ ] Visible changes are verified in their actual served surface. If official gallery/Pages artifacts change, apply `.agents/skills/tuba-pages-verification/SKILL.md`; local tests alone do not prove deployment.
- [ ] Review records the source revision, solver/runtime version, test results, known limitations, and owned changed paths. Publishing remains a separate action.

## Related designs and evidence

- `AGENTS.md`
- `docs/superpowers/plans/2026-08-27-lean-repository-and-capability-gates.md`
- `docs/superpowers/specs/2026-08-27-native-section-and-pipe-volume-meshing-design.md`
- `docs/superpowers/plans/2026-09-08-native-piping-friction.md`
- `docs/superpowers/specs/2026-09-09-imported-component-step-demo-design.md`
- `docs/superpowers/specs/2026-09-14-line-loads-and-pipe-wind-design.md`
- `docs/superpowers/specs/2026-09-14-node-temperatures-and-sampled-fields-design.md`
- `docs/superpowers/specs/2026-09-15-support-attachment-design.md`
- `docs/architecture/b31j-compliance-migration.md`
- Official material reference: https://code-aster.org/doc/v17/manuals/man_u/u4/u4.43.01/index.html

## Plan review

The five review priorities are assigned to Milestone 1 (validation and qualification), Packages A-B (contents and material parity), and Packages E-G (combined workflows). Reducers are Package C. The additional usability recommendations are D and H-J. Milestone 1's interfaces preserve existing APIs; later APIs are frozen in their separate subsystem plans before implementation. No implementation or new solver qualification is claimed by this planning document.
