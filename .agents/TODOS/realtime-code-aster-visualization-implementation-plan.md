# Realtime Code_Aster Visualization Implementation Plan

## Purpose

This is the goal-ready execution roadmap for implementing Tuba's realtime visualization workflow: cold geometry, Code_Aster analysis mesh, solver result overlays, deformed/warped operating states, operating-state clash review, and live Python/JSON patch preview.

Use this plan together with:

- `.agents/SPECS/realtime-code-aster-visualization.md`
- `.agents/TODOS/realtime-code-aster-visualization.md`
- `.agents/DECISIONS/realtime-code-aster-visualization.md`
- `.agents/SPECS/visualization-engine.md`
- `docs/visualization_engine_vision.md`

## Execution Loop

For each package:

1. Read the package section and relevant spec sections.
2. Add focused tests before or alongside implementation.
3. Implement only the current package scope.
4. Run the package verification command.
5. Fix failures before moving to the next package.
6. Update package status in this file.
7. Record new architecture decisions in `.agents/DECISIONS/realtime-code-aster-visualization.md`.
8. Keep existing Code_Aster, `VisualizationScene`, PyVista, and viewer compatibility.

## Core Constraints

- `VisualizationScene` remains the canonical viewer contract.
- Web viewer is the primary interactive review engine.
- First renderer stack is Vite + TypeScript + Three.js.
- PyVista/trame remains for notebooks, screenshots, and engineering plots.
- IFC is exchange/context, not the internal visualization state.
- Code_Aster is not executed automatically on preview save.
- Unit tests must not require a local Code_Aster installation.
- Browser tests must be deterministic and verify a nonblank canvas for the smoke fixture.
- Visual deformation scale must never affect engineering clash results.
- Realtime preview starts with full scene reload before `SceneDiff`.
- Python live preview only runs trusted local scripts in a subprocess with timeout.
- JSON `ModelPatch` preview dry-runs through `ModelTransaction` and does not mutate committed model state.

## Milestones

| Milestone | Outcome | Packages |
| --- | --- | --- |
| RV-M0 | Baseline and fixtures | RV00, RV01 |
| RV-M1 | Scene data for solver and operating states | RV02, RV03, RV04, RV05 |
| RV-M2 | Review-ready example bundle | RV06 |
| RV-M3 | Real browser rendering foundation | RV07, RV08, RV09 |
| RV-M4 | Engineering inspection UX | RV10, RV11, RV12 |
| RV-M5 | Realtime authoring loop | RV13, RV14, RV15 |
| RV-M6 | Reports, notebook bridge, performance, adapters | RV16, RV17, RV18 |
| RV-M7 | Release gate | RV19 |

## Dependency Graph

```text
RV00 -> RV01
RV01 -> RV02 -> RV03 -> RV04 -> RV05 -> RV06
RV06 -> RV07 -> RV08 -> RV09 -> RV10
RV10 + RV03 + RV04 -> RV11
RV10 + RV05 -> RV12
RV06 + RV07 -> RV13 -> RV14 -> RV15
RV06 + RV10 -> RV16
RV08 + RV09 -> RV17
RV17 -> RV18
all -> RV19
```

## Package Checklist

| ID | Package | Status | Verification Gate |
| --- | --- | --- | --- |
| RV00 | Spec and precedent baseline | Complete | planning docs exist |
| RV01 | Fixture and current viewer baseline | Complete | fixture inventory and existing viewer tests |
| RV02 | Analysis mesh scene assets | Complete | analysis mesh scene tests |
| RV03 | Result scalar/vector overlays | Complete | result overlay scene tests |
| RV04 | Deformed and warped scene layers | Complete | deformed scene tests |
| RV05 | Clash issue visualization contract | Complete | clash issue scene tests |
| RV06 | Operating-state review bundle | Complete | example bundle smoke |
| RV07 | Vite/TypeScript viewer scaffold | Complete | viewer unit/build gate |
| RV08 | Three.js geometry renderer | Complete | nonblank canvas smoke |
| RV09 | Scene loader, viewer state, and layer model | Complete | loader/state tests |
| RV10 | Selection, object tree, and property panel | Complete | inspection UI tests |
| RV11 | Code_Aster result review UI | Complete | result overlay browser test |
| RV12 | Clash review UI | Complete | clash focus browser test |
| RV13 | Live preview server and Python watcher | Complete | script save reload test |
| RV14 | JSON patch preview | Complete | dry-run patch preview test |
| RV15 | SceneDiff incremental updates | Complete | diff application tests |
| RV16 | Notebook and static HTML report export | Complete | exported report smoke |
| RV17 | Viewer performance benchmarks | Complete | benchmark smoke |
| RV18 | Optional adapter spike boundaries | Complete | adapter docs/tests |
| RV19 | Final release gate | Complete | full suite and viewer gates |

## RV00 - Spec And Precedent Baseline

**Goal:** Freeze direction and precedent findings.

**Tasks:**

- Maintain `.agents/SPECS/realtime-code-aster-visualization.md`.
- Maintain `.agents/DECISIONS/realtime-code-aster-visualization.md`.
- Maintain this implementation plan.
- Keep `docs/visualization_engine_vision.md` linked to this addendum.

**Acceptance Criteria:**

- Web viewer is specified as primary interactive review engine.
- PyVista/trame remains specified for notebook/debug plots.
- Vite + TypeScript + Three.js is specified for the first custom renderer.
- IFC/BIM/scientific renderers are optional adapters.

**Verify:**

```powershell
Get-ChildItem .agents\SPECS\realtime-code-aster-visualization.md, .agents\TODOS\realtime-code-aster-visualization-implementation-plan.md, .agents\DECISIONS\realtime-code-aster-visualization.md
```

## RV01 - Fixture And Current Viewer Baseline

**Goal:** Freeze existing viewer and visualization behavior before changing the stack.

**Tasks:**

- Inventory current `viewer/` scripts, loader tests, controls tests, and build output.
- Inventory existing Python visualization tests.
- Add or update a fixture generator for:
  - cold geometry,
  - `AnalysisMesh`,
  - mock `ResultState`,
  - physical operating geometry,
  - visual deformed geometry,
  - operating-only clash.
- Add fixture expected counts:
  - objects,
  - assets,
  - overlays,
  - issues,
  - views.
- Confirm existing viewer and scene tests pass.

**Acceptance Criteria:**

- Baseline fixture can be generated without Code_Aster.
- Existing viewer tests pass before scaffold migration.
- Fixture expected counts are available for later regression tests.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_operating_state_example tests.test_visualization_web_export tests.test_visualization_results -v
npm.cmd --prefix viewer test
npm.cmd --prefix viewer run build
```

**Implementation Note 2026-06-21:** Added `tests/realtime_visualization_fixtures.py` and `tests/test_realtime_visualization_fixture.py`.
The fixture exports a Code_Aster `AnalysisStudy`/`AnalysisMesh` manifest without running Code_Aster, creates a mock Code_Aster `ResultState`, builds cold/physical/visual `GeometryState` records, produces one operating-only insulation clash, and writes a deterministic scene bundle. Focused fixture tests, the Python package verification slice, `npm.cmd --prefix viewer test`, and `npm.cmd --prefix viewer run build` pass.

## RV02 - Analysis Mesh Scene Assets

**Goal:** Visualize the actual solver mesh submitted to Code_Aster.

**Tasks:**

- Extend `build_visualization_scene()` or add a focused builder input for `AnalysisMesh`.
- Add `SceneObject`/`GeometryAsset` records for mesh nodes and mesh elements.
- Add layer IDs:
  - `analysis_mesh:nodes`
  - `analysis_mesh:elements`
  - `analysis_mesh:generated_bend_nodes`
  - `analysis_mesh:groups`
- Attach source metadata:
  - source `EntityRef`,
  - role,
  - segment index,
  - parametric position,
  - Code_Aster group membership.
- Add diagnostics for unmapped mesh nodes/elements.
- Add tests using export-only `CodeAsterSolver.export_analysis_study()`.

**Acceptance Criteria:**

- Native mesh nodes link to native `node:*` refs.
- Generated bend nodes link to source `element:*` refs and role `generated_bend_node`.
- Mesh assets are selectable and traceable.
- Tests do not need Code_Aster execution.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_visualization_analysis_mesh tests.test_code_aster_study -v
```

**Implementation Note 2026-06-21:** `build_visualization_scene(..., analysis_meshes=[...])` emits selectable `analysis_mesh_node` and `analysis_mesh_element` scene objects with point/polyline assets, mesh provenance metadata, Code_Aster group layers, and missing-provenance diagnostics. Package verification passes.

## RV03 - Result Scalar And Vector Overlays

**Goal:** Represent Code_Aster result fields in the semantic scene.

**Tasks:**

- Add scalar overlay data for stress/utilization.
- Add vector overlay data for displacement and reactions.
- Add selected-element force/moment metadata from element results.
- Add legend/range metadata:
  - field name,
  - unit,
  - min,
  - max,
  - color map name,
  - threshold values.
- Add parser/import diagnostics overlay.
- Add stress hotspot summary data.
- Keep `FEAResults` visualizer compatibility.

**Acceptance Criteria:**

- `ResultState` can produce stress, displacement, and reaction overlays.
- Overlay values retain `result_state_id` and `load_case`.
- Stress overlay object IDs map back to scene objects.
- Missing results produce diagnostics, not crashes.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_visualization_result_overlays tests.test_visualization_results tests.test_result_state -v
```

**Implementation Note 2026-06-21:** `ResultState` scene projection emits solver-result overlays for stress/utilization, displacement vectors, reaction vectors, parser diagnostics, force/moment element metadata, legends, ranges, thresholds, and stress hotspots. Package verification passes.

## RV04 - Deformed And Warped Scene Layers

**Goal:** Show physical and visual deformed states without mutating `TubaModel`.

**Tasks:**

- Add deformed centerline scene assets from `project_deformed_centerline()`.
- Add deformed envelope scene assets from `build_deformed_envelopes()`.
- Add optional warped analysis mesh assets from `AnalysisMesh` and `ResultState`.
- Add separate layer IDs for:
  - `deformed:physical_centerline`
  - `deformed:physical_envelope`
  - `deformed:visual_centerline`
  - `deformed:visual_envelope`
  - `deformed:mesh`
- Add visual-only deformation scale metadata.
- Add tests proving visual scale changes rendered points but not engineering clash results.

**Acceptance Criteria:**

- Physical operating state uses engineering scale `1.0`.
- Visual state can render exaggerated deformation.
- Deformed assets carry `geometry_state_id`, `result_state_id`, `load_case`, and `visual_scale`.
- Engineering clash metadata remains unchanged by visual scale.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_visualization_deformed_states tests.test_deformed_projection tests.test_deformed_clash -v
```

**Implementation Note 2026-06-21:** Added deformed centerline, deformed envelope, and warped analysis-mesh scene layers driven by `GeometryState` and `ResultState`. Physical and visual layers carry explicit scale metadata and do not mutate `TubaModel`. Package verification passes.

## RV05 - Clash Issue Visualization Contract

**Goal:** Make operating-state clashes focusable, inspectable, and BCF-compatible in the scene.

**Tasks:**

- Add marker geometry for clash locations.
- Add issue focus metadata for involved objects.
- Add clash overlays with:
  - cold distance,
  - operating distance,
  - penetration,
  - load case,
  - geometry state,
  - result state,
  - envelope type,
  - introduced-by-deformation flag.
- Add optional cold/operating envelope ghost references.
- Add issue grouping metadata by severity, route, load case, and object pair.
- Keep BCF export/import compatibility.

**Acceptance Criteria:**

- Operating-only clash creates an issue and marker.
- Selecting/focusing issue can identify both involved objects.
- Issue payload includes cold and operating distances.
- BCF export contains operating-state metadata.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_visualization_clash_review tests.test_visualization_bcf tests.test_operating_clash -v
```

**Implementation Note 2026-06-21:** Clash markers, overlays, issues, and BCF payloads now expose a normalized operating-state review payload with cold/operating distances, geometry state, result state, envelope type, deformation-introduced flag, focus object IDs, and grouping metadata. Package verification passes.

## RV06 - Operating-State Review Bundle

**Goal:** Produce one canonical bundle that exercises cold, mesh, results, deformed, and clash layers.

**Tasks:**

- Extend `examples/operating_state_clash.py` or add `examples/realtime_visualization_review.py`.
- Export a scene bundle with:
  - cold geometry,
  - analysis mesh,
  - mock `ResultState`,
  - result overlays,
  - physical operating geometry,
  - visual deformed geometry,
  - clash issue marker.
- Add bundle metadata with expected counts.
- Ensure bundle can be loaded by existing viewer loader.
- Keep the example Code_Aster-free by using export-only manifest plus mock results.

**Acceptance Criteria:**

- Example writes `scene.json` and geometry metadata.
- Bundle includes at least one result overlay and one operating-only clash.
- Bundle validates through `VisualizationScene.from_dict()`.

**Verify:**

```powershell
.\.venv\Scripts\python.exe examples\realtime_visualization_review.py
.\.venv\Scripts\python.exe -m unittest tests.test_realtime_visualization_bundle -v
```

**Implementation Note 2026-06-21:** Added `examples/realtime_visualization_review.py` and `tests/test_realtime_visualization_bundle.py`. The example writes a browser-loadable scene bundle with cold geometry, Code_Aster analysis mesh, mock `ResultState`, result overlays, physical and visual deformed layers, warped mesh, and one operating-only clash marker. Package verification passes.

## RV07 - Vite/TypeScript Viewer Scaffold

**Goal:** Convert the current viewer shell into a modern app scaffold without losing existing tests.

**Tasks:**

- Add Vite configuration.
- Add TypeScript configuration.
- Preserve existing pure JS/Node tests or migrate incrementally.
- Add scripts:
  - `dev`
  - `build`
  - `test`
  - `e2e`
  - `preview`
- Add app entrypoint and CSS layout.
- Keep current scene loader API compatible.
- Add CI-friendly build output.

**Acceptance Criteria:**

- Viewer tests pass.
- Viewer build produces `viewer/dist`.
- Existing scene-loader tests still pass.
- No browser e2e is required yet beyond build smoke.

**Verify:**

```powershell
npm.cmd --prefix viewer test
npm.cmd --prefix viewer run build
```

**Implementation Note 2026-06-21:** Added Vite and TypeScript scaffold files, externalized viewer CSS, switched the browser entrypoint to `/src/main.ts`, and installed viewer dev dependencies. Existing Node viewer tests and Vite production build pass.

## RV08 - Three.js Geometry Renderer

**Goal:** Render the canonical review bundle in a real 3D canvas.

**Tasks:**

- Add Three.js dependency.
- Add renderer, camera, orbit controls, lights, grid, and axes.
- Render asset formats:
  - `tube`,
  - `polyline`,
  - `point`,
  - `vector`,
  - `marker`,
  - `aabb`,
  - simple `mesh`.
- Add stable object ID to rendered object metadata.
- Add fit-all camera.
- Add error state for invalid assets.
- Add Playwright canvas nonblank test.

**Acceptance Criteria:**

- Review bundle renders a nonblank canvas.
- Cold geometry and clash marker are visible.
- Scene bounds drive fit-all camera.
- Rendered objects retain scene object IDs for later picking.

**Verify:**

```powershell
npm.cmd --prefix viewer test
npm.cmd --prefix viewer run build
npm.cmd --prefix viewer run e2e -- smoke
```

**Implementation Note 2026-06-21:** Added the Three.js renderer module, browser canvas integration, deterministic Playwright smoke fixture, renderer unit tests, and `three`/`@playwright/test` dependencies. Verified the unit suite, Vite production build, and nonblank WebGL canvas smoke test.

## RV09 - Scene Loader, Viewer State, And Layer Model

**Goal:** Create stable client-side state for layers, overlays, result states, and geometry states.

**Tasks:**

- Normalize scene bundle loading.
- Add viewer state reducer/store for:
  - selected objects,
  - hidden objects,
  - active layers,
  - active overlays,
  - active result state,
  - active geometry state,
  - visual deformation scale.
- Add layer registry from object layer IDs and overlay kinds.
- Add scene validation diagnostics panel.
- Add tests for layer toggle and state persistence.

**Acceptance Criteria:**

- Toggling a layer changes visible objects without mutating scene data.
- Result/deformed/clash layers are independently controllable.
- State can preserve camera/selection across full scene reload where object IDs still exist.

**Verify:**

```powershell
npm.cmd --prefix viewer test
npm.cmd --prefix viewer run e2e -- layer-state
```

**Implementation Note 2026-06-21:** Added object `layer_ids` and overlay-kind layers to the viewer state registry, scene validation diagnostics, active result/geometry state fields, independent visual deformation scale control state, reload state preservation helpers, and a deterministic layer-state browser workflow.

## RV10 - Selection, Object Tree, And Property Panel

**Goal:** Make rendered objects inspectable as engineering objects.

**Tasks:**

- Add raycast picking.
- Add hover highlight.
- Add single and multi-select.
- Add object tree grouped by kind, route, group, and source.
- Add property panel sections:
  - identity,
  - geometry,
  - physical,
  - attributes,
  - quantities,
  - result values,
  - clash/issues,
  - IFC/external refs,
  - provenance.
- Add copy entity ref.
- Add fit/isolate/hide selected.

**Acceptance Criteria:**

- Selecting an insulated pipe shows insulation material/thickness and effective radius.
- Selecting a clash marker shows involved refs and distance data.
- Selecting analysis mesh entity shows source ref and role.

**Verify:**

```powershell
npm.cmd --prefix viewer test
npm.cmd --prefix viewer run e2e -- scene-inspection
```

**Implementation Note 2026-06-21:** Added rendered-object picking and hover highlight helpers, route/group/source object tree grouping, engineering property sections for insulation/effective geometry/result/clash/IFC/provenance data, copy entity-ref action, fit/hide/isolate selection controls, and the deterministic `scene-inspection` browser workflow.

## RV11 - Code_Aster Result Review UI

**Goal:** Make solver results reviewable in the web viewer.

**Tasks:**

- Add load-case selector.
- Add result-state selector.
- Add scalar legend for stress/utilization.
- Add threshold controls and hotspot list.
- Add displacement vector scale control.
- Add reaction vector scale control.
- Add deformed state selector.
- Add visual deformation scale slider with display-only labeling.
- Add guard that engineering clash issue values do not change with visual slider.

**Acceptance Criteria:**

- Stress overlay colors objects by scalar value.
- Displacement/reaction vectors can be scaled visually.
- Deformed physical/visual layers can be toggled independently.
- Visual slider does not alter clash issue metadata.

**Verify:**

```powershell
npm.cmd --prefix viewer test
npm.cmd --prefix viewer run e2e -- code-aster-results
```

**Implementation Note 2026-06-21:** Added result-review controls for load case, result state, geometry state, stress thresholds, displacement/reaction vector scale, and display-only visual deformation scale. Added scalar legend/hotspot rendering, vector scaling in the Three.js renderer, result-state property values, and a deterministic Code_Aster results browser workflow that verifies clash metadata is unchanged by visual scale edits.

## RV12 - Clash Review UI

**Goal:** Provide the core operating-state clash review experience.

**Tasks:**

- Add issue list grouped by severity/load case/status.
- Add focus issue behavior.
- Highlight involved objects and marker.
- Add filter for operating-only clashes.
- Add clash details panel.
- Add BCF export action path if supported by backend/export helper.
- Add status/comment fields in scene state or local review state.

**Acceptance Criteria:**

- Clicking an operating-only clash focuses the marker and selects involved objects.
- Details panel shows cold distance, operating distance, penetration, envelope type, and load case.
- User can hide unrelated objects and restore view.

**Verify:**

```powershell
npm.cmd --prefix viewer test
npm.cmd --prefix viewer run e2e -- clash-review
```

**Implementation Note 2026-06-21:** Added grouped/filterable clash issues, operating-only filtering, marker-first issue focus, details for cold/operating distance, penetration, envelope, and load case, local issue status/comment state, BCF action status, restore visibility behavior, and a deterministic clash-review browser workflow. Package verification passes.

## RV13 - Live Preview Server And Python Watcher

**Goal:** Provide realtime feedback from trusted Python generation scripts.

**Tasks:**

- Add `tuba.visualization.preview` package.
- Add CLI:
  - `python -m tuba.visualization.preview watch script.py --out generated\live_scene --port 8765`
- Watch trusted local script files.
- Debounce changes.
- Execute script in a subprocess with timeout.
- Support script outputs:
  - `model`,
  - `scene`,
  - `patch`,
  - `show_model()`,
  - `show_scene()`,
  - `show_patch()`.
- Validate outputs.
- Write scene bundle.
- Send websocket events:
  - `run_started`,
  - `scene_reloaded`,
  - `diagnostic`,
  - `run_finished`.
- Add viewer connection and reload handling.

**Acceptance Criteria:**

- Saving a trusted Python script updates the viewer without full browser refresh.
- Invalid scripts produce visible diagnostics.
- Code_Aster is not executed automatically.
- Preview subprocess timeout is enforced.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_visualization_preview_server -v
npm.cmd --prefix viewer run e2e -- live-preview
```

**Implementation Note 2026-06-21:** Added `tuba.visualization.preview` subprocess/server entrypoints for trusted local scripts, `show_model`/`show_scene`/`show_patch` collection, timeout-enforced preview execution, polling watch reload, static bundle serving, websocket events, viewer full-scene reload handling, and visible diagnostics. Scene bundles publish `scene.json` last so live clients do not reload half-written metadata. Python preview-server tests, viewer unit/build gates, and the browser `live-preview` websocket workflow pass.

## RV14 - JSON Patch Preview

**Goal:** Let agents and tools preview model changes safely.

**Tasks:**

- Add JSON patch watch mode.
- Validate `ModelPatch` schema.
- Load base model snapshot.
- Apply patch through dry-run `ModelTransaction`.
- Build preview scene.
- Emit full scene reload event.
- Add diagnostics for validation or transaction failure.
- Keep committed model unchanged.

**Acceptance Criteria:**

- Valid JSON patch updates preview scene.
- Invalid patch shows diagnostics.
- Dry-run preview does not mutate committed model file.
- Agent proposal preview can reuse this path.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_visualization_patch_preview tests.test_patches -v
npm.cmd --prefix viewer run e2e -- patch-preview
```

**Implementation Note 2026-06-21:** Added JSON `ModelPatch` preview execution and watch mode through `PatchPreviewServer`, `execute_patch_preview`, `run_patch_preview_once`, and `python -m tuba.visualization.preview watch-patch`. Patch preview loads a committed model snapshot, validates the patch schema, builds the preview through the existing agent-proposal dry-run path, writes a normal scene bundle, emits full-scene reload events, and writes diagnostic scenes for invalid patches without mutating the committed model file. Package Python verification and the deterministic browser `patch-preview` reload workflow pass.

## RV15 - SceneDiff Incremental Updates

**Goal:** Add partial viewer updates after full reload preview is stable.

**Tasks:**

- Add diff builder for changed scene objects/assets/overlays/issues.
- Add conservative invalidation fallback to full reload.
- Add websocket `scene_diff` event.
- Add viewer reducer for applying `SceneDiff`.
- Preserve camera, selection, and layer state across diffs.
- Add tests for add/update/remove object cases.

**Acceptance Criteria:**

- Small object additions can apply without full scene reload.
- Invalid or incompatible diff falls back to full reload.
- Existing selected object remains selected if still present.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_visualization_scene_diff tests.test_visualization_live_preview -v
npm.cmd --prefix viewer run e2e -- scene-diff
```

**Implementation Note 2026-06-21:** Added conservative Python `SceneDiff` build/apply helpers with full-reload fallback diagnostics for incompatible scene identity, value-based add/update/remove detection for scene objects and upsert detection for geometry, overlays, issues, route reviews, and agent proposals. Added viewer `applySceneDiffToState`, reducer support, websocket `scene_diff` handling, stale geometry pruning after object removal, and a deterministic browser workflow that applies a small support-object diff without navigation and falls back to bundle reload on base-scene mismatch. RV15 Python verification, viewer unit tests, the `scene-diff` e2e gate, and the viewer build pass.

## RV16 - Notebook And Static HTML Report Export

**Goal:** Support notebooks and shareable reports without making notebooks the core UI.

**Tasks:**

- Add standalone report writer:
  - `index.html`,
  - `scene.json`,
  - geometry metadata,
  - optional snapshots,
  - issue summary.
- Add notebook helper returning iframe/embed HTML for a scene bundle.
- Add static report viewer path that does not need a dev server.
- Add optional screenshot export from saved view if Playwright is installed.

**Acceptance Criteria:**

- Report folder opens locally and loads the scene.
- Notebook helper returns valid embeddable HTML.
- Missing Playwright screenshot support is diagnostic, not failure for core report.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_visualization_static_report -v
```

**Implementation Note 2026-06-21:** Added `tuba.visualization.static_report` with `write_static_report()`, `notebook_iframe_html()`, and `StaticReport`. Static reports reuse `write_scene_bundle()`, write `index.html`, root and metadata issue summaries, a report manifest, and JSON-embedded scene data so the report can be opened locally without a dev server. Optional Playwright screenshot capture is diagnostic-only when unavailable. RV16 verification passes.

## RV17 - Viewer Performance Benchmarks

**Goal:** Make viewer performance measurable before adding large-model adapters.

**Tasks:**

- Add scene build benchmark fixture.
- Add bundle size measurement.
- Add viewer load benchmark smoke.
- Add selection latency benchmark smoke.
- Add overlay toggle latency benchmark smoke.
- Add performance diagnostics into scene/bundle when limits are exceeded.
- Add asset hash/cache reuse for generated geometry.

**Acceptance Criteria:**

- Benchmark writes summary under `.benchmarks/`.
- Moderate fixture has measured build/load timings.
- Benchmarks are stable enough for local smoke validation.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_visualization_performance -v
.\.venv\Scripts\python.exe -m tuba.visualization.benchmarks viewer-smoke
```

**Implementation Note 2026-06-21:** Extended visualization benchmarks with bundle size measurement, deterministic geometry asset SHA-256 hashes, cache-friendly bundle JSON writes, viewer-smoke load/selection/overlay-toggle timing probes, `.benchmarks/viewer_smoke_latest.json`, and the `python -m tuba.visualization.benchmarks viewer-smoke` CLI. Performance diagnostics are emitted for configured scene-build and viewer-smoke limits. RV17 unit and CLI verification pass.

## RV18 - Optional Adapter Spike Boundaries

**Goal:** Define and lightly test adapter boundaries for future BIM/scientific renderers without committing the core viewer to them.

**Tasks:**

- Add adapter interface notes for:
  - vtk.js dense mesh/scalar adapter,
  - That Open Fragments/IFC context adapter,
  - xeokit/XKT context adapter.
- Add small capability matrix in docs.
- Add no-op or stub adapter registration if useful.
- Ensure core viewer does not depend on these packages.
- Add tests that missing optional adapters produce clear diagnostics.

**Acceptance Criteria:**

- Optional adapters are documented and isolated.
- Core viewer works without optional adapter dependencies.
- Missing adapter path returns diagnostics, not import crashes.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_visualization_optional_adapters -v
```

**Implementation Note 2026-06-21:** Added `tuba.visualization.optional_adapters` as a pure metadata/status registry for vtk.js dense mesh/scalar, That Open Fragments IFC context, and xeokit XKT context adapter boundaries. Missing and unknown adapters now return structured diagnostics without importing optional packages. Added `docs/visualization_optional_adapters.md` with the capability matrix and isolation rules. RV18 unit verification passes.

## RV19 - Final Release Gate

**Goal:** Confirm the realtime visualization workflow is stable enough for broader use.

**Tasks:**

- Run full Python suite.
- Run viewer unit tests.
- Run viewer build.
- Run viewer e2e tests where dependencies are installed.
- Run visualization benchmark smoke.
- Run operating-state review bundle example.
- Review docs/spec/workplan/decisions.
- Confirm live preview does not auto-run Code_Aster.
- Confirm visual deformation scale is display-only.
- Confirm all package statuses are updated.

**Acceptance Criteria:**

- Full Python tests pass.
- Viewer tests/build pass.
- E2E smoke passes or unavailable dependency is documented.
- Benchmark smoke passes.
- Example bundle opens through the viewer.
- Workplan and decision log are current.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
npm.cmd --prefix viewer test
npm.cmd --prefix viewer run build
npm.cmd --prefix viewer run e2e
.\.venv\Scripts\python.exe -m tuba.visualization.benchmarks viewer-smoke
.\.venv\Scripts\python.exe examples\realtime_visualization_review.py
```

**Implementation Note 2026-06-21:** Final release gate passes on the current tree: Python discovery runs 239 tests; viewer unit tests run 50 tests; Vite production build succeeds; deterministic browser smoke reports a nonblank canvas (`228/2400` varied samples); viewer benchmark smoke reports no diagnostics; and `examples/realtime_visualization_review.py` writes the review scene bundle under `.benchmarks/realtime_visualization_review/review_scene`. Added an indexed element lookup on `TubaModel` and wired visualization element lookup through it before the final gate.

## Performance Checklist

- [x] Scene build avoids scanning all entities when indexed lookups exist.
- [x] Geometry assets have stable IDs and hashes.
- [x] Viewer can preserve camera/selection across scene reload.
- [x] Small updates can use `SceneDiff`; unsafe updates fall back to full reload.
- [x] Layer toggles do not mutate canonical scene data.
- [x] Visual deformation scale is display-only.
- [x] Code_Aster execution is never triggered by default preview watch.
- [x] Large optional adapters stay behind isolated interfaces.
- [x] Browser tests verify nonblank canvas.
- [x] Unit tests run without Code_Aster.

## Final Deliverable

At the end of this workplan, Tuba should support this workflow:

```text
Python generation script
  -> TubaModel / AnalysisStudy / ResultState
  -> VisualizationScene with cold, mesh, result, deformed, and clash layers
  -> browser viewer with object tree, property panel, layer controls, result controls, and clash issue focus
  -> trusted Python or JSON patch preview
  -> full scene reload first, SceneDiff later
  -> notebook/static report export
```
