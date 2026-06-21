# Realtime Code_Aster Visualization TODO

## Purpose

Implement the visualization path for cold geometry, Code_Aster result overlays, deformed/warped geometry, clash review, and realtime script/patch preview.

For goal-driven implementation, use the detailed package plan in `.agents/TODOS/realtime-code-aster-visualization-implementation-plan.md` and the copyable prompt in `.agents/TODOS/realtime-code-aster-visualization-goal-prompt.md`.

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
| RV11 | Result review controls | Complete | result review tests |
| RV12 | Clash review workflow | Complete | clash review tests |
| RV13 | Static local preview CLI | Complete | preview CLI tests |
| RV14 | Trusted Python live preview server | Complete | watcher/websocket tests |
| RV15 | Patch preview and agent proposal loop | Complete | patch/proposal tests |
| RV16 | Static report and notebook bridge | Complete | export/embed tests |
| RV17 | Performance budgets and benchmark harness | Complete | benchmark tests |
| RV18 | Optional renderer adapters | Complete | adapter smoke tests |
| RV19 | Documentation and final verification | Complete | full test/build gate |

## RV01 - Analysis Mesh Scene Assets

**Goal:** Visualize the actual solver mesh submitted to Code_Aster.

Tasks:

- Add scene builder support for `AnalysisMesh`.
- Add assets for mesh nodes and mesh elements.
- Show native nodes, generated bend nodes, generated bend segments, and Code_Aster groups.
- Attach source `EntityRef` and role metadata.
- Add diagnostics for missing provenance.

Verify:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_visualization_analysis_mesh -v
```

## RV02 - Result Scalar And Vector Overlays

**Goal:** Display Code_Aster result fields from `ResultState`.

Tasks:

- Add scalar overlay schema for stress/utilization.
- Add vector overlay schema for displacement and reactions.
- Add force/moment metadata for selected elements.
- Add legend range metadata and units.
- Add hotspot list data.

Verify:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_visualization_result_overlays -v
```

## RV03 - Deformed And Warped Scene Layers

**Goal:** Show physical and visual deformed states without mutating `TubaModel`.

Tasks:

- Add deformed centerline assets.
- Add deformed envelope assets.
- Add optional warped analysis mesh assets.
- Add visual deformation scale metadata.
- Add tests proving visual scale does not change engineering clash metadata.

Verify:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_visualization_deformed_states tests.test_deformed_clash -v
```

## RV04 - Clash Issue Visualization Contract

**Goal:** Make operating-state clashes focusable and inspectable.

Tasks:

- Add marker geometry for clash locations.
- Add issue focus metadata for involved objects.
- Add cold/operating distance fields to issue/property data.
- Add envelope-type and load-case filters.
- Keep BCF export compatible.

Verify:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_visualization_clash_review tests.test_visualization_bcf -v
```

## RV05 - Three.js/Vite Viewer MVP

**Goal:** Replace the current static shell with a real browser renderer.

Tasks:

- Add Vite + TypeScript setup in `viewer/`.
- Add Three.js renderer.
- Load scene bundle.
- Render tubes, polylines, boxes, vectors, markers, and simple meshes.
- Add fit-all camera, orbit controls, axes/grid, error state.
- Add Playwright canvas nonblank test.

Verify:

```powershell
npm.cmd --prefix viewer test
npm.cmd --prefix viewer run build
npm.cmd --prefix viewer run e2e -- smoke
```

## RV06 - Object Tree, Properties, Layers

**Goal:** Make rendered objects useful for engineering review.

Tasks:

- Add object tree grouped by kind, route, group, and source.
- Add property panel.
- Add selection and hover highlighting.
- Add layer toggles for cold, mesh, results, deformed, clashes, envelopes.
- Add isolate/hide/fit selection.

Verify:

```powershell
npm.cmd --prefix viewer run e2e -- scene-inspection
```

## RV07 - Code_Aster Result Review UI

**Goal:** Make solver results reviewable in the web viewer.

Tasks:

- Add load-case selector.
- Add result-state selector.
- Add stress legend and threshold controls.
- Add displacement/reaction vector scale controls.
- Add deformed state selector.
- Add stress hotspot panel.

Verify:

```powershell
npm.cmd --prefix viewer run e2e -- code-aster-results
```

## RV08 - Live Preview Server And Watcher

**Goal:** Provide realtime feedback from trusted Python scripts.

Tasks:

- Add `tuba.visualization.preview` package.
- Add CLI: `python -m tuba.visualization.preview watch script.py`.
- Watch trusted script files.
- Run script in a subprocess with timeout.
- Collect `model`, `scene`, `patch`, or `show_scene()` outputs.
- Build/write scene bundle.
- Send websocket reload events.
- Display diagnostics in viewer.

Verify:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_visualization_preview_server -v
npm.cmd --prefix viewer run e2e -- live-preview
```

## RV09 - JSON Patch Preview And SceneDiff

**Goal:** Let agents and tools preview changes safely.

Tasks:

- Watch JSON `ModelPatch` files.
- Validate schema.
- Dry-run `ModelTransaction`.
- Recompute affected scene.
- Emit full reload first.
- Add `SceneDiff` incremental update after full reload is stable.
- Add viewer application of `SceneDiff`.

Verify:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_visualization_patch_preview tests.test_visualization_live_preview -v
npm.cmd --prefix viewer run e2e -- patch-preview
```

## RV10 - Notebook And Static HTML Export

**Goal:** Support notebooks and shareable reports without making them the core viewer.

Tasks:

- Add helper to export a standalone local report folder.
- Add notebook helper returning iframe/embed HTML.
- Add static HTML route that loads a scene bundle.
- Add screenshots from saved viewpoints if Playwright is available.

Verify:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_visualization_static_report -v
```

## RV11 - Performance And Optional Adapters

**Goal:** Prepare for larger models and BIM/scientific context.

Tasks:

- Add viewer load and scene build benchmark.
- Add asset hashing/cache reuse.
- Add instancing for repeated markers/supports.
- Add optional VTK/vtk.js export path for dense mesh fields.
- Add optional IFC Fragments or xeokit adapter spike.
- Keep adapters behind the `VisualizationScene` contract.

Verify:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_visualization_performance -v
.\.venv\Scripts\python.exe -m tuba.visualization.benchmarks viewer-smoke
```

## Final Gate

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
npm.cmd --prefix viewer test
npm.cmd --prefix viewer run build
npm.cmd --prefix viewer run e2e
```
