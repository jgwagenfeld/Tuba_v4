# Architecture Gap Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the architecture gaps identified in `docs/architecture/library-architecture-review.md` while preserving the product contract: Tuba models must be solved with Code_Aster before stress, displacement, reaction, compliance, operating clash, or result visualization is presented as engineering evidence.

**Architecture:** Keep `TubaModel` as the source of truth, `CodeAsterSolver` as the Code_Aster adapter, `tuba/plotting/` as the quick-look/export path, and `tuba/visualization/` plus `viewer/` as the reviewable web-scene path. Add missing product concepts in the model layer first, then compile them into existing Code_Aster study generation.

**Tech Stack:** Python 3.10+, `unittest`/`pytest`, existing Code_Aster `.mail/.comm/.export` writer, existing runtime bridge, existing notebook/result import helpers, existing viewer tests when scene output changes.

> **Path-accuracy note (2026-07-05):** This plan was re-reconciled against the live checkout after the Tier 2 module cleanup. During that cleanup `routing/objectives.py` moved to `tuba/optimization/objectives.py`, `aster.py` was split into `aster_comm.py` + `aster_mesh.py`, and several test-module names differ from earlier drafts. **Every path below is verified against the current tree.** Test files marked `(new)` do not exist yet and must be created; all other paths exist today. Complete **Phase 0** before any other phase — it is the guard against this drift recurring.

## Global Constraints

- Do not present fabricated, mock, hand-built, or proxy values as Code_Aster solver results.
- Do not add a third visualization path.
- Do not treat generated `.comm`, `.mail`, or `.export` files as a completed engineering workflow.
- Keep export-only paths labeled as development, diagnostic, or handoff surfaces.
- Keep B31J tee/branch work blocked until licensed source text is available; do not infer table values.
- Do not vendor or copy ada-py implementation code.
- Do not split `tuba/solver/aster_comm.py` speculatively. Split it only when a real operation/support compiler seam exists.
- Keep existing shipped builder methods working unless a migration step includes compatibility wrappers and tests.
- **Every phase must leave the full suite green with no new skips.** Baseline before starting: run `.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test*.py"` and record the OK/skip counts. A phase that increases the skip count is a silent regression and is not "done".

---

## Workstream Order

1. **Phase 0** — Reconcile paths and baseline the suite (do this first, always).
2. Validation seam: make invalid models fail before normal 1D Code_Aster export.
3. Current API guard: keep notebooks/examples on shipped API until new DSL methods exist.
4. Operation model MVP: add first-class operating scenarios without changing solver behavior for uniform cases.
5. Route/station metadata and local fields: make non-uniform operation data addressable.
6. Robust bend geometry: store enough 3D bend data for solver, visualization, and compliance.
7. Code_Aster command compiler cleanup: split only around the new operation/local-field seams.
8. Compliance and engineering expansion: deepen B31.3/B31J and route-scoring capabilities after the model concepts are stable.

This order matters. Operations need a stable model contract before local fields, local fields need addressable route/station metadata, and directional compliance needs richer bend/local-axis geometry.

### Serialization-versioning rule (applies to Phases 3, 4, 5)

Phases 3-5 each add fields to canonical JSON (`Operation`, `route_id`/`station_*`, `BendGeometry`). The model manifest already carries `meta.version` (see `tuba/schema.py:19-25` and `tuba/model.py:841-846`). For each of these phases:

- New fields must be **optional on load**: an older serialized model (missing the field) must still deserialize and validate.
- Add a **backward-load test** that reads a pre-change fixture (a JSON blob captured before the field existed, checked into `tests/fixtures/`) and asserts it loads, validates, and exports without error.
- Committed result fixtures under `notebooks/code_aster_results/` and `viewer/public/code-aster-review/` must still load after the change. If a schema `version` bump is required, bump it and add a load-path that accepts the previous version.

---

## Phase 0: Reconcile Paths And Baseline The Suite

**Files:**

- Read-only sweep of `tuba/`, `tests/`, `notebooks/`, `examples/`
- This plan document (annotate any path that has drifted since the last edit)

**Intent:** Prevent the wrong-path failure mode. Before implementing anything, confirm every file and test module named in later phases still exists, and capture the current green baseline so per-phase regressions are detectable.

- [x] Confirm each `Modify`/`Create` path in Phases 1-7 resolves. Known-correct anchors as of 2026-07-05:
  - `tuba/solver/aster.py` — `export_study` at ~line 144, `export_analysis_study` at ~line 199.
  - `tuba/solver/mixed_study.py:29` — already calls `model.validate()` (the pattern to mirror).
  - `tuba/solver/aster_comm.py` — `_write_comm(...)`; `tuba/solver/aster_mesh.py` — `_write_mail(...)`.
  - `tuba/model.py` — `define_load_case` (~699), `pipe` (~760), `solve` (~806). `define_operation`/`operation` do **not** exist yet (they are the Phase 3 deliverable).
  - `tuba/builder.py:107` — `bend(...)`; sets `bend_radius`/`bend_angle` at ~162-163.
  - Compliance lives in `tuba/compliance/asme_b313.py` + `tuba/compliance/sif.py`.
  - `objectives.py` is at `tuba/optimization/objectives.py` (NOT `tuba/routing/`).
  - `load_path.py` is at `tuba/load_path.py` (NOT `tuba/analysis/`).
- [x] Confirm test-module names. Real modules that exist today:
  - `tests/test_validation.py`, `tests/test_schema.py`, `tests/test_public_api.py`, `tests/test_pipe_run_recipe.py`, `tests/test_tuba_core.py` (these cover model/validation/serialization/builder/export behavior).
  - `tests/test_code_aster_study.py`, `tests/test_code_aster_docs.py`, `tests/test_code_aster_results.py`, `tests/test_notebook_code_aster_results.py`.
  - `tests/test_compliance_b31j.py` (there is **no** `test_compliance.py`).
  - `tests/test_examples.py`, `tests/test_route_plan.py`, `tests/test_routing_adapter.py`, `tests/test_routing_objectives.py`, `tests/test_routing_solver_loop.py`, `tests/test_visualization_analysis_mesh.py`.
  - `tests/test_code_aster_real_smoke.py` (env-gated integration).
- [x] Record the baseline: run `.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test*.py"` and note OK/skip counts in the phase notes.

**Phase notes:** Baseline on 2026-07-05: `407 tests`, `OK`, `skipped=3`. Bare `.\.venv\Scripts\python.exe -m unittest` ran 0 tests in this checkout, so this plan now uses explicit discovery for full-suite checks.

**Acceptance:**

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test*.py"
```

Expected: baseline recorded (currently 407 OK / 3 skip as of 2026-07-05; verify live). No path in Phases 1-7 references a file that cannot be found. Any drift found here is fixed in this plan before proceeding.

---

## Phase 1: Validation At The Normal Code_Aster Export Seam

**Files:**

- Modify `tuba/solver/aster.py`
- Modify `tests/test_code_aster_study.py`
- Add `tests/test_export_validation.py` (new) — dedicated failing-export tests
- Possibly modify tests/examples that intentionally construct partial models

**Intent:** The normal `CodeAsterSolver.export_study()` and `export_analysis_study()` paths should call `model.validate()` before writing `.mail`, `.comm`, `.export`, or manifests. Mixed-study export already validates (`tuba/solver/mixed_study.py:29`); the normal 1D path should match that safety boundary.

- [x] **Blast-radius discovery first.** Before changing code, grep the test suite and `examples/` for models that call `export_study`/`export_analysis_study`/`solve` without first adding a material, section, support, and load case. Count and list them - this is the set step 4 must fix, and it is the main risk of this phase ballooning. Record the count in the phase notes.
- [x] Add failing tests (in `tests/test_export_validation.py`) for invalid normal export:
  - missing section reference fails before `study.mail` is written;
  - missing material reference fails before `study.comm` is written;
  - `export_study()` and `export_analysis_study()` both raise the same validation exception/message.
- [x] Call `model.validate()` at the start of both normal export paths, after arguments are accepted but before clearing/writing output files.
- [x] Keep load-case selection errors clear when the model has no load cases or an unknown load case is requested.
- [x] Fix every test/example found in the blast-radius sweep by adding the required material, section, support, or load-case setup.

**Phase notes:** Export-call sweep found the normal export seam in `tuba/solver/aster.py` as the shared fix point. No caller/example setup edits were needed after adding validation: focused tests passed and the full suite passed with `409 tests`, `OK`, `skipped=3`.

**Acceptance:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_export_validation tests.test_code_aster_study -v
.\.venv\Scripts\python.exe -m unittest tests.test_validation tests.test_public_api tests.test_tuba_core -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test*.py"
```

Expected: invalid models fail in Tuba before Code_Aster files are written; valid existing studies still export unchanged except for validation timing; full suite green with no new skips.

---

## Phase 2: Current API Guard For Examples And Notebooks

**Files:**

- Modify `README.md`
- Modify `notebooks/*.ipynb` as needed
- Modify `examples/*.py` as needed
- Add `tests/test_current_api_docs.py` (new)
- Possibly create `docs/current-api-examples.md`

**Intent:** User-facing examples should not teach future DSL methods as current behavior. The current builder API is `start()`, `run()`, `bend()`, `add_support()`, `spring()`, `run_element()`, and model-level APIs such as `add_support()` and `define_load_case()`. Future methods such as `anchor`, `guide`, `block`, `bend_to`, `operation`, and local fields should appear only in roadmap docs until implemented.

- [x] Add a documentation guard test that scans current notebooks/examples/README for future-only API names.
- [x] **Make the guard derive its allowed/banned sets from the live public API, not a hardcoded denylist.** Introspect `PipingBuilder` and `TubaModel` for the method names they actually define, then flag any *undefined* method name that appears in current-code docs. This way the guard self-updates as Phases 3 and 5 ship `define_operation`, `operation`, and `bend_to` - a hardcoded denylist would otherwise block the very examples those phases add. If introspection is impractical, fall back to a denylist but add an explicit `# remove when Phase N ships <method>` comment per entry.
- [x] Allow future-only names only in explicitly roadmap-marked files, including `docs/architecture/user-facing-piping-dsl-and-agent-ops.md`.
- [x] Update notebooks/examples that show future API as current code.
- [x] Add a compact current-API examples page or README section:
  - define material and pipe section;
  - build a pipe with `PipingBuilder`;
  - add supports;
  - define a load case;
  - export/solve with Code_Aster;
  - import/display real result artifacts.

**Phase notes:** Added `tests/test_current_api_docs.py`. It checks method-call forms only, so valid support strings such as `support="anchor"` and `type="guide"` are not false positives. No README/notebook/example rewrites were needed. Full suite after Phase 2: `410 tests`, `OK`, `skipped=3`.

**Acceptance:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_current_api_docs tests.test_examples tests.test_notebook_code_aster_results -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test*.py"
```

Expected: current-code docs use only shipped APIs unless a section is explicitly labeled as roadmap; guard passes without modification after later phases add real methods.

---

## Phase 3: First-Class Operation Model MVP

**Files:**

- Modify `tuba/model.py` — public surface: `define_operation`, `operation`, `solve(operation=...)`
- Modify `tuba/schema.py` — serialize/deserialize `Operation`; honor the versioning rule above
- Modify `tuba/solver/aster.py` — route `operation=` through export
- Modify `tuba/solver/aster_comm.py` — compile a uniform operation into the same commands as the equivalent `LoadCase`; leave a `# TODO(phase6): extract operation/load compiler` marker at the new logic so Phase 6 can find the seam
- Modify `tuba/compliance/asme_b313.py` — accept operation names in lookup
- Modify `tests/test_validation.py` and/or add `tests/test_operation_model.py` (new)
- Modify `tests/test_schema.py`
- Modify `tests/test_code_aster_study.py`
- Modify `tests/test_compliance_b31j.py`

**Intent:** Replace ad hoc expansion of `LoadCase` with a first-class operation/scenario concept while keeping `LoadCase` as the low-level compatibility record used by the current Code_Aster writer.

**Proposed public surface:**

```python
operating = model.define_operation(
    "Operating",
    pressure=1.6e6,
    temperature=120.0,
    ref_temperature=20.0,   # match the shipped define_load_case kwarg name, not "reference_temperature"
    gravity=True,
)

model.solve(operation="Operating")
```

Compatibility rule: a uniform operation compiles to an equivalent `LoadCase`. Existing `define_load_case()` and `solve(load_case=...)` keep working. **Kwarg naming:** reuse `ref_temperature` (the name shipped on `define_load_case`, `tuba/model.py:699`) so the uniform-operation→LoadCase compile step does not have to rename fields.

- [x] Add an `Operation` dataclass with name, gravity, pressure, temperature, reference temperature, and metadata.
- [x] Add `TubaModel.define_operation(...)` and `TubaModel.operation(...)` convenience methods.
- [x] Serialize/deserialize operations through canonical JSON; **operations absent in old JSON must load fine** (versioning rule). Add the backward-load test.
- [x] Compile a uniform operation into the same Code_Aster input as the equivalent `LoadCase`.
- [x] Teach compliance lookup to accept operation names while preserving load-case lookup.
- [x] Add deprecation-free compatibility: existing `LoadCase` users should not see warnings yet.

**Phase notes:** Added uniform `Operation` support through `TubaModel.resolve_load_case(...)`, so `CodeAsterSolver` and compliance share one lookup path. No `aster_comm.py` extraction or TODO marker was needed: uniform operations compile before command generation and the generated `.comm` matches the equivalent load case. Backward-load fixture: `tests/fixtures/pre_operation_model.json`. Full suite after Phase 3: `415 tests`, `OK`, `skipped=3`.

**Acceptance:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_operation_model tests.test_schema tests.test_code_aster_study tests.test_compliance_b31j -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test*.py"
```

Expected: operation roundtrip works, uniform operation export matches existing load-case behavior byte-for-byte, old load-case flows still pass, and a pre-Phase-3 model fixture still loads.

---

## Phase 4: Route/Station Metadata And Local Operation Fields

**Files:**

- Modify `tuba/model.py`
- Modify `tuba/builder.py`
- Modify `tuba/patches.py`
- Modify `tuba/schema.py` (honor versioning rule)
- Modify `tuba/routing/adapter.py`
- Modify `tuba/solver/aster_comm.py`
- Modify `tests/test_validation.py` and/or add `tests/test_operation_fields.py` (new)
- Modify `tests/test_route_plan.py`
- Modify `tests/test_routing_adapter.py`
- Modify `tests/test_code_aster_study.py`

**Intent:** Support real operating scenarios where pressure or temperature is not uniform across the whole model. This requires stable addressing by route, group, station range, and generated element lineage before Code_Aster compilation can be reliable.

**Proposed concepts:**

- `route_id` on generated pipe elements.
- `station_start` and `station_end` on generated pipe elements.
- Operation fields addressed by model scope: `all`; group; route; route station range; explicit element ids.
- Field profiles: uniform; linear; piecewise.

- [x] Add optional route/station metadata to elements without breaking existing JSON (versioning rule; add backward-load test).
- [x] Extend `PipingBuilder` with route naming, station tracking, and recipe replay coverage (see `tests/test_pipe_run_recipe.py` — the recipe replay path must preserve the new metadata).
- [x] Preserve route/station metadata in patches and routing adapters.
- [x] Add `OperationField` records under `Operation` for pressure and temperature.
- [x] Implement validation for overlapping incompatible fields and unsupported selectors.
- [x] Compile supported uniform/group/range fields into Code_Aster groups and temperature/pressure assignments.
- [x] Fail loudly for field shapes that the current Code_Aster writer cannot compile.

**Phase notes:** Added optional `route_id` / `station_start` / `station_end` on elements, route-aware builder/recipe replay, patch and routing-adapter preservation, first-class `OperationField` records, validation for unsupported/overlapping local fields, and Code_Aster grouped pressure/temperature compilation for uniform fields. Linear and piecewise profiles are accepted as schema concepts but fail validation/export until the writer supports them. Backward-load coverage reuses `tests/fixtures/pre_operation_model.json`. Focused Phase 4 acceptance: `36 tests`, `OK`. Full suite after Phase 4: `421 tests`, `OK`, `skipped=3`.

**Acceptance:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_operation_fields tests.test_route_plan tests.test_routing_adapter tests.test_code_aster_study tests.test_pipe_run_recipe -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test*.py"
```

Expected: two route sections can export different operating temperatures or pressures, unsupported overlaps fail at validation, generated `.comm` groups remain traceable to Tuba routes/stations, and pre-Phase-4 models still load.

---

## Phase 5: Robust 3D Bend Geometry

**Files:**

- Modify `tuba/model.py`
- Modify `tuba/builder.py` (bend authoring is at `tuba/builder.py:107`)
- Modify `tuba/solver/aster_mesh.py`
- Modify `tuba/solver/aster_comm.py` only if local axes/groups need bend metadata
- Use existing `tuba/analysis/mesh.py` metadata contract; modify `tuba/visualization/builders.py` for scene output
- Modify `tuba/visualization/scene.py`
- Modify `tuba/compliance/asme_b313.py`
- Modify `tests/test_validation.py` and/or add `tests/test_bend_geometry.py` (new)
- Modify `tests/test_visualization_analysis_mesh.py`
- Modify `tests/test_code_aster_study.py`
- Modify `tests/test_compliance_b31j.py`

**Intent:** Store bend geometry explicitly instead of reconstructing it from `bend_radius` and `bend_angle` (set at `tuba/builder.py:162-163`). This is needed for arbitrary 3D bends, 180-degree bend disambiguation, local moment decomposition, and generated-node lineage.

**Proposed public surface:**

```python
with model.pipe(section="DN100", material="P265GH", route="P-100") as pipe:
    pipe.start([0, 0, 0], support="anchor")
    pipe.run(2.0)
    pipe.bend_to([2.0, 1.0, 1.0], radius=0.3, plane_normal=[0, 0, 1])
    pipe.run(2.0)
```

- [x] Add a `BendGeometry` record with center, normal, radius, angle, start tangent, end tangent, and generation mode.
- [x] Store `BendGeometry` on bend elements while keeping `bend_radius` and `bend_angle` for compatibility (versioning rule; add backward-load test — a pre-Phase-5 model with only `bend_radius`/`bend_angle` must still load and mesh).
- [x] Add builder methods for: explicit `bend_to(...)`; orientation/axis-based bend; current `bend(radius, angle, plane=...)` as a compatibility wrapper.
- [x] Reject ambiguous 180-degree bends unless a plane normal is supplied.
- [x] Update mesh generation and analysis mesh lineage to use stored bend geometry.
- [x] Update scene bundle output to expose bend metadata for review.
- [x] Add compliance hooks for local-axis/moment decomposition, even if full compliance formulas remain out of scope.

**Phase notes:** Added optional `BendGeometry` on elements with JSON/schema support, current `bend(...)` geometry recording, `bend_to(...)`, `bend_in_plane(...)`, and `bend_by_orientation(...)`, autoroute bend geometry records, Gmsh mesh generation from stored bend geometry with fallback reconstruction for old models, analysis-mesh provenance metadata, scene element metadata, and `bend_local_axes(...)` for later compliance moment decomposition. The old planned path `tuba/visualization/analysis_mesh.py` does not exist in this checkout; the live analysis-mesh contract is `tuba/analysis/mesh.py`, and existing source metadata support was sufficient. Backward-load fixture: `tests/fixtures/pre_bend_geometry_model.json`. Focused Phase 5 acceptance: `30 tests`, `OK`. Full suite after Phase 5: `426 tests`, `OK`, `skipped=3`.

**Acceptance:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_bend_geometry tests.test_visualization_analysis_mesh tests.test_code_aster_study tests.test_compliance_b31j -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test*.py"
```

Expected: arbitrary 3D bend geometry roundtrips, exports to Code_Aster, displays through existing visualization paths, ambiguous bends fail with actionable errors, and pre-Phase-5 bend models still mesh.

---

## Phase 6: Code_Aster Command Compiler Cleanup

**Files:**

- Modify `tuba/solver/aster_comm.py`
- Possibly create `tuba/solver/aster_loads.py`
- Possibly create `tuba/solver/aster_supports.py`
- Modify `tests/test_code_aster_study.py`
- Modify `tests/test_code_aster_docs.py`

**Intent:** Keep the `.comm` writer understandable once operations and local fields land. Do not split for style alone; split around real domain seams. Phases 3 and 4 deliberately add their compile logic *into* `aster_comm.py` behind `# TODO(phase6)` markers — this phase extracts that logic once it exists (build-then-extract), so start by locating those markers.

- [x] Add snapshot or focused substring tests for existing generated `.comm` behavior before refactoring.
- [x] Find the `# TODO(phase6)` markers left by Phases 3/4 and extract an operation/load compiler around that concrete field logic. Do not extract if the markers do not exist yet (the seam has not landed).
- [x] Extract a support-condition compiler only if support logic starts sharing validation/compilation behavior across linear and nonlinear solve paths.
- [x] Keep `_write_comm(...)` as the orchestration point that writes commands in Code_Aster execution order.
- [x] Preserve command coverage and links documented in the Code_Aster Command Map in `docs/architecture/library-architecture-review.md`.

**Phase notes:** Extracted the concrete pressure/temperature operation-field compilation seam into `tuba/solver/aster_loads.py` and left support compilation in `_write_comm(...)` because no shared support seam exists yet. Added a focused `.comm` substring regression to preserve legacy uniform pressure/temperature syntax while existing local-field tests cover grouped assignments. Focused Phase 6 acceptance: `21 tests`, `OK`. Full suite after Phase 6: `427 tests`, `OK`, `skipped=3`.

**Acceptance:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_code_aster_study tests.test_code_aster_docs -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test*.py"
```

Expected: legacy `.comm` output remains behaviorally unchanged, and local operation field logic has a single clear compiler seam.

---

## Phase 7: Compliance And Engineering Expansion

> **Not a single deliverable.** This phase is a set of independent, opportunistic engineering items — several are externally blocked (B31J tee/branch factors are paywalled; occasional loads need end-to-end model + solver support that does not exist yet). Treat each checkbox as its own mini-project, land whichever are unblocked, and do not report the phase as "complete". The Deliverable Checklist reflects this ("partially merged").

**Files:**

- Modify `tuba/compliance/asme_b313.py`, `tuba/compliance/sif.py`
- Modify `tuba/load_path.py` (NOT `tuba/analysis/load_path.py`)
- Modify `tuba/optimization/objectives.py` (NOT `tuba/routing/objectives.py`)
- Modify `tuba/routing/solver_loop.py`
- Modify `tuba/solver/aster_comm.py`
- Modify `tests/test_compliance_b31j.py`
- Modify `tests/test_routing_objectives.py`
- Modify `tests/test_routing_solver_loop.py`
- Add gated real-solver tests under `tests/` (e.g. extend `tests/test_code_aster_real_smoke.py`) when needed

**Intent:** Expand engineering capability only after the operation, local-field, and bend metadata contracts exist.

- [x] Implement full sustained stress evaluation from model/operation data already present in Tuba.
- [x] Add occasional wind support where the Code_Aster export path and operation model both represent it end to end. Beam-modelized pipe sections can now use `OperationField(quantity="wind", direction=[...])` and export through `FORCE_POUTRE(TYPE_CHARGE='VENT')`.
- [ ] Add seismic support only when the Code_Aster export path and operation model both represent it end to end.
- [ ] Add wind support for `TUYAU_3M` pipe modelization only if backed by a documented distributed-load Code_Aster command. Do not approximate production pipe wind with `FORCE_NODALE`.
- [x] Add directional local moment decomposition once bend/local-axis data (Phase 5) is trustworthy. (Today `M_o=0`, conservative; fixing needs solver local-axis output.)
- [x] Add nozzle reaction, displacement, and operating-clearance gates to route scoring from imported Code_Aster artifacts.
- [ ] Implement B31J tee/branch factors only from licensed source text or user-provided authorized tables. **Blocked — paywalled ASME B31J-2023 Table 1-1. Do not guess.**
- [ ] Expand mixed STEP solve/import/result-display beyond export-only once the runtime path is available.

**Phase notes:** Partially merged the unblocked Phase 7 items. Compliance now resolves local operation pressure and temperature fields per element, and bend elements with `BendGeometry` report directional moment components (`M_i`, `M_o`, `M_t`) with a traceable `moment_basis`. Route scoring can now evaluate displacement and reaction gates from imported `ResultState` artifacts in addition to existing operating-clearance clash checks. Beam-modelized pipe sections can now carry wind operation fields and export them through Code_Aster U4.44.01 `FORCE_POUTRE(TYPE_CHARGE='VENT')`; validation rejects wind fields on `TUYAU_3M` pipe elements. `FORCE_TUYAU` is internal pipe pressure only, and `FORCE_NODALE` is not a production wind shortcut because the manual warns that nodal loads are physically incorrect and can create stress concentrations. Seismic remains blocked because neither the operation model nor Code_Aster writer represents it end to end. B31J tee/branch factors remain blocked pending licensed/user-provided source text. Mixed STEP solve/import remains blocked by runtime-path availability. Focused Phase 7 acceptance after beam-wind support: `38 tests`, `OK`. Env-gated real Code_Aster smoke was attempted with `TUBA_RUN_CODE_ASTER_INTEGRATION=1` and failed before solve because WSL and Docker both reported `Code_Aster runner not found` (return code 127); `code_aster_doctor --check` confirmed the same setup blocker. Full portable suite after beam-wind support: `432 tests`, `OK`, `skipped=3`.

**Acceptance:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_compliance_b31j tests.test_routing_objectives tests.test_routing_solver_loop -v
$env:TUBA_RUN_CODE_ASTER_INTEGRATION = "1"
.\.venv\Scripts\python.exe -m unittest tests.test_code_aster_real_smoke -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test*.py"
```

Expected: production engineering checks are tied to real Code_Aster artifacts or fail with a clear runtime/setup blocker.

---

## Deliverable Checklist

- [x] Phase 0 merged: all Phase 1-7 paths verified against the tree; green baseline recorded.
- [x] Phase 1 merged: normal Code_Aster export validates before file generation.
- [x] Phase 2 merged: current-code docs/examples cannot drift into future DSL accidentally; guard is API-derived.
- [x] Phase 3 merged: uniform operations work, preserve existing load-case behavior, and old models still load.
- [x] Phase 4 merged: route/station metadata and local fields compile or fail clearly; old models still load.
- [x] Phase 5 merged: bends have explicit stored 3D geometry; old bend models still mesh.
- [x] Phase 6 merged: `.comm` generation has a concrete load compiler seam; support compilation stays in `_write_comm(...)` until a shared support seam exists.
- [x] Phase 7 partially merged: compliance/routing expansion proceeds only from real model and solver data; blocked items remain blocked.

## Stop Conditions

- Stop before reporting solver values if Code_Aster is unavailable and no real imported artifacts exist.
- Stop before B31J tee/branch implementation if licensed factors are unavailable.
- Stop before broad `_write_comm` refactoring if no operation/local-field seam (Phase 3/4 marker) has landed.
- Stop before changing notebook result displays if the source artifacts cannot be proven Code_Aster-backed.
- Stop and re-reconcile (re-run Phase 0) if any phase's named file or test module cannot be found — do not invent a path.
- Stop if any phase increases the suite's skip count relative to the Phase 0 baseline; investigate the newly-skipped test before continuing.
