# Architecture Deepening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deepen seven shallow seams surfaced by the 2026-09-17 architecture review, so each rule the product depends on has one module, one interface, and one test surface.

**Architecture:** Each workstream moves a decision to the module that owns the domain concept and turns its callers into projections. No new top-level package. Two workstreams change solver input identities (W3, W5), so all their evidence churn is batched into one refresh pass. W7 and ADR-0002 coexist: the viewer keeps its fallbacks for external legacy bundles, but no bundle Tuba writes today takes them.

**Tech Stack:** Python 3.12 (unittest + pytest), Code_Aster 18 on WSL, viewer JavaScript (`node --test`, Vite bundle committed under `tuba/visualization/_viewer/`).

**Design source:** the 2026-09-17 architecture review report and its grilling session; the settled decisions are recorded per workstream below. Glossary terms added to `CONTEXT.md` the same day: **Rack**, **Rack row**, **Rack bay**, **Attachment point**, **Reusable evidence**, **Combined modelization**, **Restraint state**.

## Global Constraints

- The core workflow contract holds throughout: model -> Code_Aster solve -> processed results; never present a value the solver did not return (AGENTS.md).
- `model.py` is the only source of a model and authored scripts are never rewritten (ADR-0003). Every workstream here treats `to_dict` as a derived serialization, nothing more.
- No compatibility shims for internal API; tests and call sites migrate in the same change (ADR-0001).
- Windows runs Python through `D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe`; `uv run` is `UV_NO_SYNC=1 uv run --no-sync`.
- Real Code_Aster tests are opt-in with `TUBA_RUN_CODE_ASTER_INTEGRATION=1`. The WSL runtime is present (`python -m tuba.solver.code_aster_doctor --check` reports ready).
- Viewer changes run `npm test` and `npm run build` in `viewer/`; the rebuilt bundle is committed, and `tests/test_package_release.py` asserts a clean rebuild is byte-identical.
- Conventional commit subjects (`refactor(...)`, `feat(...)`, `test: ...`, `docs: ...`), no trailers.
- One branch per workstream, merged in order: `deepen-racks`, `deepen-evidence`, `deepen-operation-field`, `deepen-scene-contract`, `deepen-compiler-contract`, `deepen-study-settings`, `deepen-restraint-state`. W2 and W6 share a session (both rewrite the preview seam) and may share a branch.

## File Map

| Workstream | Primary files | Tests |
|---|---|---|
| W1 Racks own attachment points | `tuba/assemblies.py`, `tuba/load_path.py`, `tuba/visualization/builders/_review.py`, `examples/rack_bridge_demo/study.py` | `tests/test_rack_assemblies.py`, `tests/test_load_path.py`, `tests/test_visualization_racks.py` |
| W2 One evidence verdict | `tuba/project/evidence.py`, `tuba/project/solve.py`, `tuba/project/freshness.py`, `tuba/solver/aster.py`, `tuba/visualization/preview/server.py` | `tests/test_project_solve.py`, `tests/test_project_freshness.py`, `tests/test_solver_input_provenance.py`, new `tests/test_evidence_verdict.py` |
| W3 One OperationField encoding | `tuba/model.py`, `tuba/analysis/provenance.py`, `tuba/reporting/tables.py`, `tuba/validation.py`, `tuba/solver/aster_loads.py` | `tests/test_node_temperatures.py`, `tests/test_operation_fields.py`, `tests/test_reporting_tables.py` |
| W4 Scene request + contribution | `tuba/visualization/builders/` (all), examples, scripts, notebooks, tests | `tests/test_visualization_*.py` |
| W5 Compiler contract | new `tuba/solver/compiler_contract.py`, `tuba/solver/aster.py`, `aster_mesh.py`, `aster_volume.py`, `mixed_study.py`, `aster_sidecar.py`, `tuba/analysis/results.py`, `tuba/reporting/builder.py`, `tuba/visualization/builders/_core.py` | `tests/test_solver_input_provenance.py`, `tests/test_project_freshness.py`, `tests/test_code_aster_volume_study.py` |
| W6 Study settings + protocol | `tuba/project/study.py`, `tuba/project/__init__.py`, `tuba/project/solve.py`, `tuba/visualization/preview/server.py` | `tests/test_studio_project.py`, `tests/test_project.py`, `tests/test_mcp_units.py` |
| W7 Restraint state | `tuba/model.py`, `tuba/solver/aster_comm.py`, `aster_contact.py`, `tuba/visualization/builders/_objects.py`, `viewer/src/supports.js`, `viewer/src/sceneLoader.js` | `tests/test_code_aster_supports.py`, `tests/test_visualization_builders.py`, `viewer/test/supports.test.js`, `viewer/test/scene-loader.test.js` |

---

## W1: Racks own their attachment points

**Decision:** `tuba/assemblies.py` gains one accessor over rack group metadata; both rack classes write the same vocabulary; `load_path` and the review builder are projections. `RackRow` bay groups gain `attachment_points` (point names `mid_{station}`) and `levels`, matching `RackBay`'s `level_N_*` vocabulary. A `RackRow` load-path test lands against committed `rack_bridge_demo` evidence, and that example turns on `include_load_paths`.

### Task 1.1: Accessor and metadata

**Files:** `tuba/assemblies.py`, `tests/test_rack_assemblies.py`

**Interfaces:**
- Produces: `RackAssembly` frozen dataclass (`group_name: str`, `assembly_type: str`, `levels: tuple[float, ...]`, `zone: str | None`, `attachment_points: dict[str, str]` mapping point name -> node id, `nodes: tuple[str, ...]` the group's members) and `rack_assemblies(model) -> list[RackAssembly]`.
- `RackBay` and `RackRow` bay groups both write `assembly_type`, `levels`, optional `zone`, and `attachment_points`.

- [ ] Write failing tests in `tests/test_rack_assemblies.py`: a `RackBay` model and a `RackRow` model with `shoes`/`shoe_level` each yield records whose `attachment_points` name every mid node; a `RackRow` without `shoe_level` yields records with an empty map.
- [ ] Implement `RackAssembly` and `rack_assemblies`; extend `RackRow.to_patch`'s bay metadata with `levels` and `attachment_points` (stations already tracked per bay).
- [ ] Run `pytest tests/test_rack_assemblies.py -q`.

### Task 1.2: Load-path association consumes the accessor

**Files:** `tuba/load_path.py`, `tests/test_load_path.py`

**Interfaces:**
- `_rack_nodes` is deleted; `analyze_load_paths` projects `rack_assemblies(model)` into node -> `[(group_name, point_name)]`.

- [ ] Add a failing test: a `RackRow` model (shoes attached to mid nodes) plus reactions from committed `examples/rack_bridge_demo/evidence/Operating` via `import_code_aster_artifacts` yields associations and non-zero `rack_loads` for the row's bay groups.
- [ ] Keep the existing `RackBay` tests (`tests/test_load_path.py`, `tests/test_support_attachment.py::RackExampleEvidence`) passing unchanged.
- [ ] Implement the projection; remove the `assembly_type == "rack_bay"` check and the diagnostics for row racks.
- [ ] Run `pytest tests/test_load_path.py tests/test_support_attachment.py tests/test_visualization_racks.py -q`.

### Task 1.3: Review scene builds overlays from records

**Files:** `tuba/visualization/builders/_review.py`, `tests/test_visualization_racks.py`

- [ ] Write a failing test: a `RackRow` model's scene contains a `rack_assembly` overlay per bay with attachment points.
- [ ] Rewrite `_build_rack_assembly_overlays` to consume `rack_assemblies(model)`, covering both assembly types.
- [ ] Run `pytest tests/test_visualization_racks.py -q`.

### Task 1.4: Acceptance in the bridge example

**Files:** `examples/rack_bridge_demo/study.py`, `docs/content/examples.md`

- [ ] Add `include_load_paths=True` to the example's `run_example(...)` call.
- [ ] Rebuild its review over matching evidence (`python -m tuba.project examples/rack_bridge_demo --output .build/rack-bridge`); if the review gains load-path vectors, commit the refreshed review artifacts the example carries. If the rebuild churns evidence artifacts instead of reusing them, stop and report; the test from Task 1.2 remains the acceptance.
- [ ] Run `TUBA_RUN_CODE_ASTER_INTEGRATION=1 pytest tests/test_code_aster_supports.py tests/test_support_attachment.py -q` if a solve is needed.

---

## W2: One evidence verdict

**Decision:** `tuba/project/evidence.py` owns three functions: `evidence_state(folder)` (one load: presence, integrity, trust, attestation payload), `evidence_verdict(folder, identity)` (state plus identity match, `reusable` property), `exported_study_matches(work_dir, identity)` (the deliberately trust-free reuse probe). Freshness becomes a projection: stale means not reusable, with memoization internal to the verdict keyed by path and mtime. After import, `result_state.metadata["result_trust"]` remains the downstream authority (publication, reporting, `ProjectSolve.unverified`).

### Task 2.1: The verdict module

**Files:** `tuba/project/evidence.py`, new `tests/test_evidence_verdict.py`

**Interfaces:**
- `EvidenceState(status: str, trust: str, reason: str, attestation: Mapping[str, Any] | None)` where status is `verified | unverified | damaged | missing`.
- `EvidenceVerdict(state: EvidenceState, identity_matches: bool)` with `reusable: bool` (`verified` and matching).
- `evidence_state(folder)`, `evidence_verdict(folder, identity)`, `exported_study_matches(work_dir, identity)`.

- [ ] Write failing tests over committed evidence: `examples/support-rack-review/evidence/Operating` (`verified`), a tampered copy (`damaged`), a folder without `study_execution.json` (`missing`), and a docker-attested fixture (`unverified`).
- [ ] Implement the three functions. `evidence_state` loads once via `load_code_aster_execution_attestation` and classifies `ValueError` as damaged; `exported_study_matches` moves the body of `_attested_solve_matches` and keeps its no-trust docstring.
- [ ] Memoize integrity results internally keyed by artifact path and mtime.
- [ ] Run `pytest tests/test_evidence_verdict.py -q`.

### Task 2.2: Solve and solver consume the verdict

**Files:** `tuba/project/solve.py`, `tuba/solver/aster.py`

- [ ] Replace `_evidence_attests` with `evidence_verdict(...).reusable`; delete the private.
- [ ] Replace `_attested_solve_matches` with `exported_study_matches`; delete the private.
- [ ] Run `pytest tests/test_project_solve.py tests/test_solver_input_provenance.py -q`.

### Task 2.3: Freshness is a projection

**Files:** `tuba/project/freshness.py`, `tuba/visualization/preview/server.py`, `tests/test_project_freshness.py`

**Interfaces:**
- `stale_operations(model, attested, *, project_root, solver_options=None, volume_export=None) -> list[str]`.

- [ ] Extend the freshness tests: a matching-but-damaged folder reads stale; a missing evidence folder reads stale; an unverified folder reads stale; matching verified evidence reads fresh.
- [ ] Resolve `evidence_dir(project_root, identity.load_case)` per attested identity and ask the verdict; keep the existing "operation can no longer be compiled" and "solver rejects options" behaviour.
- [ ] Update `preview/server.py`'s `review_stale` to pass `project_root=self.project.root`.
- [ ] Run `pytest tests/test_project_freshness.py tests/test_studio_project.py tests/test_studio_server.py -q`.

---

## W3: One OperationField encoding

**Decision:** `OperationField.to_dict()` is the only serialization: compact (absent optionals omitted), matching today's `_operation_field_to_dict`. `provenance` hashes it directly; `tables` projects declared columns from it with `None` fills. Legality moves behind one public batch function in `validation.py`, used by admission and by the exporter. Fingerprint churn is accepted: `support-rack-review` and `line-load-studio` evidence are re-solved with W5's refresh.

### Task 3.1: Canonical serialization

**Files:** `tuba/model.py`, `tests/test_operation_fields.py`

- [ ] Write a failing round-trip test: `OperationField` -> `to_dict` -> `model.add_field(**payload)` reproduces the field for every optional present and absent.
- [ ] Move `_operation_field_to_dict`'s body to `OperationField.to_dict`; `model.to_dict` calls it. Generated scripts keep byte-identical output (they already read this shape).
- [ ] Run `pytest tests/test_operation_fields.py tests/test_model_script.py -q`.

### Task 3.2: Provenance and reporting delegate

**Files:** `tuba/analysis/provenance.py`, `tuba/reporting/tables.py`, `tests/test_node_temperatures.py`

- [ ] Replace `_operation_field_payload` with `field.to_dict()` in `build_solver_input_identity`; delete the private.
- [ ] Rebuild the `load_cases` report row from its declared columns, filling from `to_dict()`; delete `_operation_field_dict`; a test asserts every declared column is sourced from the canonical dict.
- [ ] Replace `tests/test_node_temperatures.py`'s three-private agreement assertions with one-encoding assertions (round trip plus the declared report columns).
- [ ] Run `pytest tests/test_node_temperatures.py tests/test_reporting_builder.py tests/test_solver_input_provenance.py -q`.

### Task 3.3: One legality rule

**Files:** `tuba/validation.py`, `tuba/solver/aster_loads.py`

**Interfaces:**
- Produces: `operation_fields_problem(fields, model) -> list[str]` (public), covering intrinsic rules and the model-dependent rules `aster_loads` re-implements today.

- [ ] Write failing tests: duplicate node values across fields, a node covered by an element temperature field, wind/line-load profile and direction rules, empty selection, and duplicate-element refusal each produce the same message through `validate_model` and through the exporter.
- [ ] Move the duplicated checks into the public function; `validate_model` extends its errors with it; `aster_loads` calls it and keeps only resolution and compilation.
- [ ] Delete the solver's import of `_node_field_problem`/`_pipe_node_ids`.
- [ ] Run `pytest tests/test_operation_fields.py tests/test_node_temperatures.py tests/test_code_aster_line_loads.py -q`.

---

## W4: Scene request and contribution records

**Decision:** A new `tuba/visualization/builders/_contract.py` holds `SceneRequest`, `SceneContribution` and the moved `SceneBuildOptions`. `build_visualization_scene(request)` is one record in; each of the ten builders returns one `SceneContribution`; builder inputs stay fine-grained; every call site migrates, no shim.

### Task 4.1: The contract module

**Files:** `tuba/visualization/builders/_contract.py` (new), `_helpers.py`, `__init__.py`

**Interfaces:**
- `SceneBuildOptions` moves unchanged from `_helpers.py`.
- `SceneRequest(model, options=..., plus every current keyword input)`.
- `SceneContribution(objects=(), assets=(), overlays=(), issues=(), route_reviews=(), views=(), diagnostics=())`, all tuple-typed with empty defaults.

- [ ] Move the dataclass; keep `from tuba.visualization.builders import SceneBuildOptions` working via re-export.
- [ ] Run `pytest tests/test_visualization_builders.py -q`.

### Task 4.2: Builders return contributions

**Files:** `_objects.py`, `_states.py`, `_results.py`, `_review.py`, `_loads.py`, `_imported.py`

- [ ] Convert the ten top-level builders; internal helpers (physical envelopes, deformed sub-scenes, glyph vectors) keep their current tuples.
- [ ] `_core.build_visualization_scene` takes `SceneRequest`, merges contributions, and keeps `build_layer_registry` / `build_result_fields` unchanged.
- [ ] Run `pytest tests/test_visualization_builders.py tests/test_visualization_results.py tests/test_visualization_issues.py -q`.

### Task 4.3: Migrate every call site

**Files:** `tuba/visualization/preview/server.py`, `examples/*/study.py`, `examples/code_aster_artifact_review.py`, `scripts/docs/generate_figures.py`, `viewer/scripts/make_geometry_mesh_deformed_fixture.py`, notebooks, `tests/**`

- [ ] Mechanically rewrite each call to `build_visualization_scene(SceneRequest(...))`; model-only calls become `SceneRequest(model)`.
- [ ] Regenerate any published copy of a call site through its build script (`scripts/build_pages.py`) rather than hand-editing generated output.
- [ ] Run `python -m pytest -q` and `python scripts/docs/generate_figures.py` to prove figures still build.

---

## W5: Compiler contract

**Decision:** A pure `tuba/solver/compiler_contract.py` decides composition and identity inputs: which element families are present, their ids and groups, coupling terminals and mesh settings; the compiler id derives from that composition (`BEAM/TUYAU`, `SOLID_3D`, MIXED for combinations). The writer consumes the contract's values (bend segments, line segments, discrete-support predicate), the identity hashes the same contract, and the export records it in `AnalysisStudy.metadata`. The MIXED identity is unified on the composition-bearing form, including the export-only mixed study. Bend segments: 32 for `POU_D_T`, 16 otherwise, declared once.

### Task 5.1: The contract module

**Files:** new `tuba/solver/compiler_contract.py`, new `tests/test_compiler_contract.py`

**Interfaces:**
- `CompilerContract(compiler_id: str, compiler_inputs: Mapping[str, Any], bend_segments: int, line_segments: int, discrete_support_nodes: bool, mixed_analysis: bool)`.
- `compiler_id_for(metadata) -> str` — the single mapping consumed by the six re-deriving modules.
- `beam_contract(model, load_case_name, *, pipe_modelization, line_segments, load_path, load_step, contact_specs) -> CompilerContract`.
- `volume_contract(model, load_case_name, *, element_ids, element_order, max_element_size, export_tensor_stress) -> CompilerContract`.
- `mixed_contract(model, load_case_name) -> CompilerContract` (export-only path; records the composition it compiles).

- [ ] Write failing tests: bend segments per modelization; a volume selection leaving line elements yields MIXED with `line_element_ids`; a pure volume yields the volume id; a mixed export-only model yields MIXED with its composition recorded.
- [ ] Implement the contract; move `needs_discrete_element`/support predicate ownership here (re-export from `modelisation` while callers migrate).

### Task 5.2: Writers consume the contract

**Files:** `tuba/solver/aster.py`, `aster_mesh.py`, `aster_comm.py`, `aster_volume.py`, `mixed_study.py`

- [ ] Delete the four `_BEND_SEGMENTS` declarations; every reader takes the contract's value.
- [ ] `analysis_study_inputs` and `export_analysis_study` build the contract once; the export writes `contract.compiler_inputs` into metadata and the writer reads `bend_segments`/`line_segments`/support predicates from it.
- [ ] `volume_study_inputs` and `mixed_study` build their contracts the same way; the export-only mixed identity stops being the one MIXED form without `compiler_inputs`.
- [ ] Run `pytest tests/test_solver_input_provenance.py tests/test_code_aster_study.py tests/test_code_aster_beam_pipes.py tests/test_code_aster_volume_study.py -q`.

### Task 5.3: Consumers ask the contract

**Files:** `tuba/analysis/results.py`, `tuba/solver/aster_sidecar.py`, `tuba/visualization/builders/_core.py`, `tuba/reporting/builder.py`

- [ ] Replace each re-derived `MIXED_/VOLUME_/CODE_ASTER_COMPILER_ID` selection with `compiler_id_for(metadata)`.
- [ ] Keep `code_aster_runtime.py`'s consistency check; it now validates the contract's own output.
- [ ] Run `pytest tests/test_solver_input_provenance.py tests/test_reporting_builder.py tests/test_visualization_results.py tests/test_code_aster_runtime.py -q`.

---

## W6: Study settings and protocol

**Decision:** `tuba/project/study.py` declares the `Study` Protocol and returns one `StudySettings` record from `study_settings`: operations, solver options, volume export, artifact dir, review builder, optional check, and a `solver(work_dir)` factory. A project without `study.py` gets an empty record. `Project.load_settings(study_file)` is the one loader; the preview stops using `getattr` entirely.

### Task 6.1: Settings and protocol

**Files:** `tuba/project/study.py`, `tests/test_project.py`

- [ ] Define the Protocol (`LOAD_CASES`, `SOLVER_OPTIONS`, `VOLUME_EXPORT`, optional `ARTIFACT_DIR`, `build_review(namespace, output, *, artifact_dir=None) -> Path`, optional `check`) and `StudySettings`; `study_settings` validates by constructing the solver once through the factory.
- [ ] Keep the runtime-option deny-list single-sourced with `solver/aster.py`'s env handling.
- [ ] Run `pytest tests/test_project.py tests/test_project_solve.py -q`.

### Task 6.2: One loader, every surface

**Files:** `tuba/project/__init__.py`, `tuba/project/solve.py`, `tuba/visualization/preview/server.py`, `tuba/mcp/server.py`

- [ ] Add `Project.load_settings`; the CLI, `solve_project`, freshness callers and the preview consume it.
- [ ] Delete the eight `getattr(self.study, ...)` probes in `preview/server.py`; replace with settings fields.
- [ ] Update the MCP scaffold text so generated studies match the declared signature.
- [ ] Run `pytest tests/test_studio_project.py tests/test_studio_server.py tests/test_mcp_units.py tests/test_mcp_server.py -q`.

---

## W7: Restraint state

**Decision:** `Support.restraint()` owns the six restraint states (`fixed / one-way / spring / free`) and the resolved spring stiffness; the scalar-stiffness-without-direction refusal moves from export to the record. `aster_comm._held_dofs`, `_spring_stiffness` and the shoe's one-way axis become projections. The scene writes `metadata["dof_states"]`; the viewer prefers it, keeping its derivation only for legacy bundles (ADR-0002). `sceneLoader.js` prefers the scene's `layer.label` where it recomputes today, keeping `leafLabel` as the legacy fallback.

### Task 7.1: `Support.restraint()`

**Files:** `tuba/model.py`, `tests/test_code_aster_supports.py`

- [ ] Write a failing state table test: anchor, guide with direction, rest with and without direction, spring with matrix and with scalar plus direction, explicit `blocked_dof` override, and the scalar-without-direction refusal.
- [ ] Implement `SupportRestraint(states: tuple[str, ...], spring_stiffness: tuple[float, ...])` and `Support.restraint()`; the solver's messages for the refusal stay recognisable to existing tests.
- [ ] Run `pytest tests/test_code_aster_supports.py tests/test_code_aster_study.py -q`.

### Task 7.2: Solver projections

**Files:** `tuba/solver/aster_comm.py`, `tuba/solver/aster_contact.py`

- [ ] `_held_dofs` and `_spring_stiffness` become projections of `support.restraint()`; the shoe's normal axis reads the one-way state.
- [ ] Exported `study.comm` text is unchanged for existing models; the byte-identical guard from `tests/test_code_aster_study.py` proves it.
- [ ] Run `pytest tests/test_code_aster_study.py tests/test_code_aster_friction.py tests/test_contact_results.py -q`.

### Task 7.3: Scene carries the states

**Files:** `tuba/visualization/builders/_objects.py`, `tests/test_visualization_builders.py`, `viewer/scripts/make_geometry_mesh_deformed_fixture.py`

- [ ] Write a failing test: a support object's metadata carries the six states from `Support.restraint()`.
- [ ] Add `dof_states` beside the raw fields in the support metadata.
- [ ] Regenerate the committed viewer fixture through `viewer/scripts/make_geometry_mesh_deformed_fixture.py` (it calls the real builder).

### Task 7.4: Viewer reads, fallbacks remain

**Files:** `viewer/src/supports.js`, `viewer/src/sceneLoader.js`, `viewer/test/supports.test.js`, `viewer/test/scene-loader.test.js`, `tuba/visualization/_viewer/`

- [ ] `supports.js` prefers `config.dof_states`, deriving only when absent; `sceneLoader.js` prefers `layer.label` at the tree entry that ignores it today (`:425`), deriving only when absent.
- [ ] Tests pin both the primary path and the legacy fallback.
- [ ] Run `npm test` in `viewer/`, then `npm run build` and commit the rebuilt bundle; run `pytest tests/test_package_release.py -q`.

---

## Evidence Refresh (after W3 and W5)

Both workstreams change solver input identities. Land both, then refresh once:

- [ ] `TUBA_RUN_CODE_ASTER_INTEGRATION=1 uv run python scripts/refresh_code_aster_gallery.py --all` (covers `support-rack-review` and the volume/mixed galleries).
- [ ] Re-solve `examples/line-load-studio` through `python -m tuba.project examples/line-load-studio --output .build/line-load-studio` and commit its evidence.
- [ ] Rebuild published pages: `python scripts/build_pages.py pages --output .build/code-aster-pages`.
- [ ] Run the full suite: `python -m pytest -q`; `npm test` in `viewer/`.

## Not in this plan

- The `Element` and `Support` record fan-out (dataclass, both JSON schemas, patch dicts, script codegen): a follow-up of W3's method on `OperationField`.
- Group metadata is hashed into the model fingerprint even though the solver never reads it (found in W1: adding rack attachment points staled the bridge evidence). The identity should hash the solver-relevant projection of `groups` (names, members); belongs with W5's compiler contract.
- `viewer/src/app.js` and `renderer.js` god modules, and the e2e script as the de-facto viewer interface.
- The export-only mixed study (`mixed_study.py`) becoming solve-ready: W5 records its composition, but the runtime blocker stands until the couplings and result extraction are validated.
- Bundle validation duplicated across `scene.py`, `sceneLoader.js`, `build_pages.py` and `reviewLoader.js`.
