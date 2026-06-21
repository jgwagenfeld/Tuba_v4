# Code_Aster Operating-State Clash Workplan

## Purpose

Implement the solver-result workflow needed for Tuba to detect, visualize, route around, and report clashes that appear only after operating loads deform the system.

This workplan implements `.agents/SPECS/code-aster-operating-state-clash.md` and feeds into the broader multidomain roadmap packages MD21-MD24.

## Execution Loop

For each package:

1. Read the package goal and acceptance criteria.
2. Add or update focused tests first where practical.
3. Implement only the package scope.
4. Run the package verification command.
5. Fix failures before moving to the next package.
6. Record any new architectural decision in `.agents/DECISIONS/code-aster-operating-state-clash.md`.
7. Run the full Python suite after CA04, CA08, CA12, and CA16.

Do not require an installed Code_Aster runtime for unit tests. Code_Aster execution belongs in optional integration tests or developer-local validation.

## Status Legend

- `Pending`: not started.
- `In Progress`: active package.
- `Complete`: implemented and verified.
- `Blocked`: cannot continue without an external decision.

## Milestones

| Milestone | Outcome | Packages |
| --- | --- | --- |
| CA-M0 | Baseline and test fixtures | CA00 |
| CA-M1 | Traceable solver input | CA01, CA02 |
| CA-M2 | Serializable solver output | CA03, CA04 |
| CA-M3 | Physical deformed geometry | CA05, CA06, CA07 |
| CA-M4 | Operating-state clash engine | CA08, CA09 |
| CA-M5 | Optimization and visualization integration | CA10, CA11, CA12 |
| CA-M6 | IFC/BCF coordination and performance hardening | CA13, CA14 |
| CA-M7 | Documentation, examples, and release gate | CA15, CA16 |

## Dependency Graph

```text
CA00 -> CA01 -> CA02 -> CA03 -> CA04
                         CA04 -> CA05 -> CA06 -> CA07 -> CA08 -> CA09
                                      CA07 + CA08 -> CA10
                                      CA07 + CA08 -> CA11
                                      CA04 + CA08 -> CA12
                                      CA08 + CA11 -> CA13
                                      CA07 + CA08 -> CA14
all -> CA15 -> CA16
```

## Package Checklist

| ID | Package | Status | Verification Gate |
| --- | --- | --- | --- |
| CA00 | Baseline audit and fixtures | Complete | current tests and fixture inventory |
| CA01 | Analysis domain objects | Complete | analysis dataclass and serialization tests |
| CA02 | Code_Aster study export manifest | Complete | export-only solver manifest tests |
| CA03 | Generated mesh result capture | Complete | generated node parser tests |
| CA04 | ResultState persistence | Complete | result-state JSON roundtrip tests |
| CA05 | GeometryState validation | Complete | state validation tests |
| CA06 | Deformed centerline projection | Complete | straight and bend projection tests |
| CA07 | DeformedEnvelope builder and cache | Complete | envelope bounds/cache tests |
| CA08 | Operating clash engine | Complete | cold versus operating clash tests |
| CA09 | Thermal expansion clash fixture | Complete | hot-only clash regression test |
| CA10 | Routing objective integration | Complete | route scoring uses operating clash |
| CA11 | Visualization integration | Complete | scene contains geometry states and issues |
| CA12 | Load path and reaction integration | Complete | support/rack reaction trace tests |
| CA13 | IFC/BCF operating-state export metadata | Complete | BCF topic and IFC property tests |
| CA14 | Performance indexes and benchmark smoke | Complete | deformed broadphase benchmark smoke |
| CA15 | Example workflow and docs | Complete | example script smoke |
| CA16 | Final release gate | Complete | full suite and viewer tests |

## CA00 - Baseline Audit And Fixtures

**Goal:** Freeze existing behavior and create fixtures that make operating-state clash work measurable.

**Tasks:**

- Inventory current Code_Aster export behavior in `tuba/solver/aster.py`.
- Inventory current result parsing into `FEAResults`.
- Inventory current visual deformation behavior.
- Inventory legacy deformed collision behavior.
- Add fixture models:
  - straight pipe near obstacle with cold clearance.
  - bend near obstacle with cold clearance.
  - insulated pipe near rack member.
  - pipe supported by rack with mock support reactions.
  - simple load case with thermal expansion displacement.
- Add fixture helper for mock `FEAResults` without Code_Aster.
- Document current limitations as comments in tests or fixture README.

**Acceptance Criteria:**

- Existing tests pass before architectural changes.
- Fixtures can be loaded without Code_Aster.
- Mock displacement can move a pipe from clear to clashing.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
.\.venv\Scripts\python.exe -m unittest tests.test_visualization_results tests.test_clash_engine -v
```

## CA01 - Analysis Domain Objects

**Goal:** Add lightweight, serializable objects for solver studies, analysis meshes, mesh source records, result states, and geometry states.

**Tasks:**

- Add `tuba/analysis/__init__.py`.
- Add `tuba/analysis/study.py` with `AnalysisStudy`.
- Add `tuba/analysis/mesh.py` with:
  - `AnalysisMesh`
  - `MeshNodeSource`
  - `MeshElementSource`
- Add `tuba/analysis/results.py` with `ResultState`.
- Add `tuba/analysis/states.py` with `GeometryState`.
- Use existing `EntityRef` conventions instead of raw free-form IDs.
- Add `to_dict()` / `from_dict()` helpers or reuse the project serializer pattern.
- Add validation for:
  - model revision consistency.
  - unique mesh nodes.
  - mesh source refs.
  - geometry state purpose and scale.

**Acceptance Criteria:**

- Domain objects roundtrip through JSON.
- Unknown metadata is preserved.
- Invalid displacement scale for engineering clash state fails clearly.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_analysis_study tests.test_analysis_mesh tests.test_geometry_states -v
```

## CA02 - Code_Aster Study Export Manifest

**Goal:** Make Code_Aster solver input traceable to native Tuba entities without changing normal solver execution.

**Tasks:**

- Add `CodeAsterSolver.export_analysis_study(model, load_case_name, output_dir)`.
- Keep existing `export_study()` behavior compatible.
- During `.mail` generation, record:
  - native node mesh IDs.
  - generated bend node mesh IDs.
  - generated bend segment mesh IDs.
  - structural member mesh IDs.
  - Code_Aster groups.
  - node and element source refs.
- Write `study_manifest.json` beside `.mail`, `.comm`, and `.export`.
- Include file paths and hashes where cheap to compute.
- Add diagnostics for unmapped mesh entities.

**Acceptance Criteria:**

- Export-only tests do not need Code_Aster.
- Every generated bend node has `role="generated_bend_node"`.
- Every generated bend segment has `role="bend_segment"`.
- Native straight pipe, beam, bar, and cable elements map back to native refs.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_code_aster_study -v
```

## CA03 - Generated Mesh Result Capture

**Goal:** Preserve solver displacement rows for generated mesh nodes, especially bend intermediate nodes.

**Tasks:**

- Extend `FEAResults` or add an attached result map for analysis mesh node IDs.
- Update Code_Aster CSV parsing to retain rows that do not correspond to native nodes.
- Preserve rotations where available.
- If MED parsing is available later, ensure it writes into the same result abstraction.
- Add parser diagnostics:
  - result node has no analysis mesh mapping.
  - analysis mesh node missing displacement result.
  - native node result missing.

**Acceptance Criteria:**

- Parser retains generated bend node displacement.
- Native node parsing remains unchanged for existing callers.
- Missing generated results produce diagnostics, not crashes.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_code_aster_results tests.test_visualization_results -v
```

## CA04 - ResultState Persistence

**Goal:** Convert in-memory solver results into durable, traceable state that downstream tools can consume.

**Tasks:**

- Add `result_state_from_fea_results(model, study, results)`.
- Add optional `fea_results_from_result_state(model, result_state)`.
- Store:
  - native node displacements.
  - generated mesh node displacements.
  - node reactions.
  - element forces.
  - stresses.
  - result file paths.
  - parser diagnostics.
- Validate `model_revision`.
- Add compact array-backed internal lookup helpers if needed.

**Acceptance Criteria:**

- Result state JSON roundtrips without losing displacement data.
- Result state refuses to apply to the wrong model revision by default.
- Existing visualizer can still consume `FEAResults`.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_result_state tests.test_visualization_results -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

## CA05 - GeometryState Validation

**Goal:** Make cold, physical operating, and visual deformed states explicit and hard to misuse.

**Tasks:**

- Add helpers:
  - `create_cold_geometry_state(model)`.
  - `create_operating_geometry_state(model, result_state, load_case, safety_factor=1.0)`.
  - `create_visual_deformed_geometry_state(model, result_state, load_case, visual_scale)`.
- Enforce:
  - engineering state scale defaults to `1.0`.
  - visualization states are rejected by engineering clash checks unless explicitly overridden.
  - safety factor is separate from visual scale.
- Add clear validation errors.

**Acceptance Criteria:**

- A visual state with scale `50.0` cannot silently drive clash checks.
- Operating state carries load case and result-state ID.
- Cold state does not need solver results.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_geometry_states -v
```

## CA06 - Deformed Centerline Projection

**Goal:** Project native and generated solver displacements onto useful deformed centerlines.

**Tasks:**

- Add `tuba/analysis/projection.py`.
- Implement straight element projection using endpoint displacement interpolation.
- Implement bend projection using generated mesh nodes where available.
- Implement interpolation fallback for bends without generated results.
- Emit diagnostics when fallback is used.
- Keep projection pure: no mutation of `TubaModel`.
- Add support for displacement scale and safety factor.

**Acceptance Criteria:**

- Straight element deformed polyline matches endpoint displacement.
- Bend deformed polyline uses generated mesh node displacement.
- Missing bend node displacement falls back with diagnostic.
- Scale `1.0` means physical deformation.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_deformed_projection -v
```

## CA07 - DeformedEnvelope Builder And Cache

**Goal:** Build reusable physical envelopes for clash, routing, visualization, and reports.

**Tasks:**

- Add `tuba/geometry/deformed.py`.
- Add `tuba/geometry/envelopes.py` if not already present or extend existing envelope code.
- Implement `build_deformed_envelopes(model, result_state, geometry_state, envelope_type)`.
- Envelope types:
  - bare.
  - insulation.
  - clearance.
  - maintenance.
  - wind.
- Use physical attributes such as insulation thickness and clearance rules.
- Compute AABB bounds.
- Add cache keyed by:
  - model revision.
  - result state ID.
  - geometry state ID.
  - envelope type.
  - safety factor.
  - clearance policy.

**Acceptance Criteria:**

- Envelope radius includes insulation where requested.
- Envelope radius includes clearance where requested.
- Cache returns equivalent results for unchanged inputs.
- Cache invalidates when model revision or state ID changes.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_deformed_envelopes tests.test_physical_properties -v
```

## CA08 - Operating Clash Engine

**Goal:** Add structured clash checks that compare cold and operating/deformed states.

**Tasks:**

- Add `tuba/clash/operating.py`.
- Extend `TrimeshClashEngine.check_model()` or add a dedicated method:
  - `check_operating_state(model, cold_state, operating_state, result_state, envelope_type)`.
- Use cold envelopes and operating envelopes.
- Report:
  - cold distance.
  - operating distance.
  - penetration.
  - load case.
  - geometry state.
  - envelope type.
  - introduced-by-deformation flag.
- Classify:
  - `cold_hard`
  - `cold_clearance`
  - `operating_hard`
  - `operating_clearance`
  - `operating_only_hard`
  - `operating_only_clearance`
  - `resolved_in_operating`

**Acceptance Criteria:**

- Cold clash and operating clash are distinguishable.
- An operating-only clash is reported when cold distance is positive and operating distance is negative.
- Clash result references involved `EntityRef` values.
- Existing cold clash tests still pass.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_operating_clash tests.test_clash_engine -v
```

## CA09 - Thermal Expansion Clash Fixture

**Goal:** Prove the exact scenario the workflow is designed for: no cold clash, hot clash after thermal expansion.

**Tasks:**

- Add a deterministic fixture with:
  - pipe plus insulation.
  - nearby obstacle or rack beam.
  - cold clearance.
  - mock hot displacement toward obstacle.
- Add test with physical scale `1.0`.
- Add test that visual scale does not alter engineering result.
- Add bend-specific variant if CA03 generated result fixture is available.

**Acceptance Criteria:**

- Test reports `operating_only_hard` or `operating_only_clearance`.
- Cold-only clash check passes.
- Engineering result is unchanged by visual deformation scale.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_deformed_clash -v
```

## CA10 - Routing Objective Integration

**Goal:** Let route scoring penalize operating-state clashes after solver evaluation of shortlisted candidates.

**Tasks:**

- Update routing objective API to accept `ResultState` and `GeometryState`.
- Update `ClashObjective` to use structured operating clash reports where available.
- Keep cheap cold/proxy clash scoring available for early route search.
- Add objective terms:
  - operating hard clash penalty.
  - operating clearance penalty.
  - support/rack collision penalty.
  - deformation safety factor.
- Ensure Code_Aster is not called inside low-level grid expansion loops.

**Acceptance Criteria:**

- Route candidate with operating clash scores worse than a clear candidate.
- Existing route objective tests still pass.
- Solver-backed scoring is explicit and optional.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_routing_objectives tests.test_pipe_autorouting -v
```

## CA11 - Visualization Integration

**Goal:** Make the operating-state workflow inspectable in the viewer and scene model.

**Tasks:**

- Add scene objects for:
  - cold geometry state.
  - physical operating envelope.
  - visual deformed polyline.
  - displacement vectors.
  - operating clash markers.
- Add metadata fields:
  - `geometry_state_id`
  - `load_case`
  - `result_state_id`
  - `visual_scale`
  - `engineering_scale`
- Add load-case and geometry-state filters in the viewer if the viewer is part of this package.
- Ensure visual deformation scale is shown as visual-only metadata.

**Acceptance Criteria:**

- Scene JSON can represent cold and operating state simultaneously.
- Operating-only clash issue appears in visualization scene.
- Selecting the issue exposes cold distance and operating distance.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_visualization_results tests.test_visualization_issues -v
npm --prefix viewer test
```

## CA12 - Load Path And Reaction Integration

**Goal:** Connect solver reactions to support and rack structure so deformed clash decisions can consider support modifications.

**Tasks:**

- Map `FORC_NODA` reactions from `ResultState` to supports and support components.
- Add relationship from support component to rack member where available.
- Update load-path analysis to accept result-state reactions.
- Add rollups by:
  - support.
  - support component.
  - rack member.
  - rack assembly.
  - load case.
- Add diagnostics for solver supports without physical support components.

**Acceptance Criteria:**

- A support reaction can be traced from Code_Aster node to support component to rack member.
- Missing physical support component is diagnostic, not silent loss.
- Visualization can show reaction vectors and load path metadata.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_load_path tests.test_visualization_racks tests.test_visualization_results -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

## CA13 - IFC/BCF Operating-State Export Metadata

**Goal:** Coordinate operating-state clashes without making IFC the internal clash engine.

**Tasks:**

- Add optional IFC property-set output for:
  - load case.
  - displacement summary.
  - stress summary.
  - support reaction summary.
  - operating clash count.
- Add BCF topic export for operating-only clashes.
- Include:
  - involved IFC GUIDs where available.
  - Tuba entity refs.
  - load case.
  - geometry state.
  - cold distance.
  - operating distance.
  - viewpoint location.
- Keep deformed geometry export optional and clearly marked as review geometry.

**Acceptance Criteria:**

- BCF topic distinguishes operating clash from cold clash.
- IFC export does not replace as-designed geometry by default.
- Missing IFC GUIDs produce diagnostics.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_visualization_bcf tests.test_ifc tests.test_ifc_mapping -v
```

## CA14 - Performance Indexes And Benchmark Smoke

**Goal:** Prevent deformed envelopes and operating clash checks from becoming scan-heavy.

**Tasks:**

- Add array-oriented internal representation for projected deformed polylines where useful.
- Add broadphase AABB index for deformed envelopes.
- Reuse model indexes for element/support/rack lookup.
- Avoid recomputing physical properties per clash candidate.
- Add benchmark fixture generator for:
  - many straight pipes.
  - many bends.
  - many rack obstacles.
  - mixed insulation/clearance envelopes.
- Add benchmark smoke thresholds that are stable enough for local development.

**Acceptance Criteria:**

- Deformed envelope broadphase reduces candidate pairs versus all-pairs.
- Repeated operating clash check reuses cached envelopes.
- Benchmark command writes timing summary.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_deformed_performance tests.test_spatial_index -v
.\.venv\Scripts\python.exe -m tuba.benchmarks deformed-clash --size smoke
```

## CA15 - Example Workflow And Docs

**Goal:** Provide an end-to-end developer example for future agents and users.

**Tasks:**

- Add example script:
  - build model.
  - assign insulation.
  - export Code_Aster study manifest.
  - use mock or imported result state.
  - import existing Code_Aster result artifacts into `ResultState` where parser-readable output tables exist.
  - create operating geometry state.
  - build deformed envelopes.
  - run operating clash.
  - build visualization scene.
  - export BCF topic.
- Update docs:
  - architecture overview.
  - operating-state clash workflow.
  - solver-result persistence.
  - visual scale versus engineering scale.
- Add troubleshooting notes for missing generated mesh results.

**Acceptance Criteria:**

- Example runs without Code_Aster using mock results.
- Existing Code_Aster artifact directories can be reviewed without re-running Code_Aster.
- Docs explain when Code_Aster is required and when mock/export-only paths are enough.
- Agents can follow the example without direct mutation of `TubaModel`.

**Verify:**

```powershell
.\.venv\Scripts\python.exe examples\operating_state_clash.py
.\.venv\Scripts\python.exe examples\code_aster_artifact_review.py
```

## CA16 - Final Release Gate

**Goal:** Confirm the whole workflow is stable and ready for the next roadmap package.

**Tasks:**

- Run full Python suite.
- Run viewer tests.
- Run viewer build if applicable.
- Run benchmark smoke.
- Review docs and examples.
- Confirm all new APIs have compatibility notes.
- Confirm no engineering clash path uses visual deformation scale.

**Acceptance Criteria:**

- Full suite passes.
- Viewer tests pass where viewer dependencies are installed.
- Benchmark smoke passes.
- Workplan package statuses are updated.
- Decision log is current.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
npm --prefix viewer test
npm --prefix viewer run build
.\.venv\Scripts\python.exe -m tuba.benchmarks deformed-clash --size smoke
```

## Performance Checklist

- [x] Solver execution is never in the route grid expansion loop.
- [x] Analysis mesh source lookup is O(1) after load.
- [x] Result-state displacement lookup is O(1) after indexing.
- [x] Deformed envelopes are cached by model revision, result state, geometry state, and envelope policy.
- [x] Cold and operating broadphase indexes are built once per state.
- [x] Bends use generated mesh nodes where available.
- [x] Fallback interpolation emits diagnostics.
- [x] Visual deformation scale is never used for engineering clash by default.
- [x] Large arrays are stored without duplicate per-object copies where possible.
- [x] Optional acceleration has pure-Python fallback.

## Final Deliverable

At the end of this workplan, Tuba should support this workflow:

```text
Python model generation
  -> insulation/support/rack semantics
  -> cheap cold checks
  -> Code_Aster study manifest
  -> solver results, imported artifacts, or mock results
  -> ResultState
  -> physical operating GeometryState
  -> deformed envelopes
  -> operating-state clash report
  -> route scoring / visualization / BCF coordination
```
