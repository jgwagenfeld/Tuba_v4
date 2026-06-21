# Realtime Code_Aster Visualization Spec

## Purpose

Define the concrete visualization implementation for Tuba's scripted geometry, Code_Aster results, deformed/warped geometry, and operating-state clash review.

This spec is an implementation addendum to `.agents/SPECS/visualization-engine.md`. It narrows the broad visualization vision into a practical technology stack, runtime architecture, and package plan.

The goal-ready package roadmap is `.agents/TODOS/realtime-code-aster-visualization-implementation-plan.md`; the copyable Codex goal prompt is `.agents/TODOS/realtime-code-aster-visualization-goal-prompt.md`.

## Core Recommendation

Use a web-first viewer as the primary interactive review engine, fed by Tuba's existing `VisualizationScene` contract.

Keep PyVista for notebook/debug/engineering plots. Do not make notebooks the primary product UI. Do not make Blender the primary review engine. Do not make IFC the internal visualization data model.

```text
Python generation script / Code_Aster export / ResultState
        |
        v
TubaModel + AnalysisStudy + AnalysisMesh + ResultState + GeometryState
        |
        v
VisualizationScene + geometry assets + overlays + issues
        |
        +-- Web viewer: interactive review and live preview
        +-- PyVista/trame: notebooks, quick solver plots, screenshots
        +-- BCF/IFC/glTF exports: coordination artifacts
```

## Technology Choices

### Viewer Application

Use the existing `viewer/` workspace and evolve it into a real browser app.

Recommended baseline:

- TypeScript.
- Vite for dev server, hot module reload, and production build.
- Three.js for first renderer.
- Web Workers for parsing large scene bundles later.
- Playwright for browser regression tests and screenshot/canvas checks.
- Node test runner or Vitest for pure state/utility tests.

Why:

- Current Tuba geometry is mostly procedural pipes, racks, supports, envelopes, markers, routes, and overlays. Three.js is enough for this first interactive layer.
- Tuba needs product UI: object tree, property panel, issue list, route comparison, patch review, load-case selector, and live preview. That UI is easier in a web app than in PyVista or Blender.
- Browser viewer can be embedded in notebooks or exported as local HTML later.

### Geometry Transport

Use `VisualizationScene` JSON plus geometry assets.

Initial formats:

- `tube`, `polyline`, `point`, `vector`, `marker`, `aabb`, and `mesh` generation configs for lightweight viewer-generated geometry.
- GLB for heavier prebuilt geometry.
- Metadata sidecars for object identity and engineering properties.

Do not put all engineering semantics into GLB extras. Keep `VisualizationScene` authoritative.

### Code_Aster Result Transport

Use existing Tuba abstractions:

- `AnalysisStudy`: generated Code_Aster input files and manifest.
- `AnalysisMesh`: native and generated mesh node/element provenance.
- `FEAResults`: in-memory solver convenience object.
- `ResultState`: persistent result state.
- `GeometryState`: cold, physical operating, and visual deformed states.
- `DeformedEnvelope`: derived clash/review geometry.

The viewer must never read raw Code_Aster output directly as its primary API. Python parses/imports solver output and emits scene overlays.

### Solver Mesh And Warped Mesh

Support two levels:

1. **Line/beam mesh MVP**
   - Render `AnalysisMesh.nodes` and `AnalysisMesh.elements` as selectable line/segment assets.
   - Color by element stress, utilization, displacement magnitude, or source role.
   - Warp using `ResultState.node_displacements`.

2. **MED/VTK mesh adapter**
   - Optional import through Python, likely `meshio`, when `.rmed` is available.
   - Convert to a viewer asset format such as GLB with scalar metadata or VTK-compatible data.
   - Keep this optional. Unit tests must not need Code_Aster or MED files.

### Scientific/Notebook Path

Keep PyVista for:

- notebook previews,
- stress/deformation screenshots,
- quick local solver debugging,
- high-quality engineering plots,
- optional trame-backed interactive notebook/web preview.

PyVista is not the main review engine because it is not ideal for a full object tree, issue workflow, patch approval, BCF review, and browser-based live updates.

### IFC/BIM Scale Path

Use IFC only as exchange/context.

Add adapters later:

- That Open Fragments for IFC-to-fragments workflows and large BIM contexts.
- xeokit/XKT for high-performance BIM model viewing and metadata-heavy coordination.
- Autodesk Platform Services or Bentley iTwin only as future external integrations, not as the core local engine.

The internal viewer contract remains `VisualizationScene`.

## Online Precedents

Reference patterns, not direct architecture dependencies:

- PyVista supports trame-backed Jupyter/browser rendering and is strong for scientific mesh/result plots: https://docs.pyvista.org/user-guide/jupyter/trame.html
- VTK.js is a browser-side scientific visualization toolkit, useful as a future adapter for VTK-style meshes and scalar fields: https://kitware.github.io/vtk-js/docs/
- Three.js is the general-purpose WebGL/WebGPU rendering base for the first custom viewer: https://threejs.org/docs/
- xeokit is a browser BIM viewer SDK focused on large AEC models, metadata, and BIM-style interaction: https://xeokit.github.io/xeokit-sdk/
- That Open Engine/Fragments is an IFC/BIM-oriented web stack with worker-friendly fragment models: https://docs.thatopen.com/
- Speckle shows a precedent for web-based AEC object review and federated model workflows: https://speckle.systems/
- Autodesk Platform Services Viewer shows the commercial precedent: translate design data to web-viewable derivatives, then review in a browser viewer: https://aps.autodesk.com/apis-and-services/viewer
- Bentley iTwin.js shows the same pattern at infrastructure scale: frontend web viewer plus optimized model/data services: https://www.itwinjs.org/

The lesson is consistent: serious engineering visualization is usually browser-based, metadata-aware, and backed by preprocessed/optimized scene assets. Tuba should do the same locally first.

## Required Visual States

### 1. Cold Design Geometry

Scene layers:

- `cold:centerline`
- `cold:pipe_body`
- `cold:supports`
- `cold:racks`
- `cold:obstacles`
- `cold:insulation_envelope`
- `cold:clearance_envelope`

Viewer capabilities:

- select pipe/support/rack/obstacle,
- inspect physical attributes,
- toggle bare/insulated/clearance geometry,
- show generated object provenance.

### 2. Analysis Mesh

Scene layers:

- `analysis_mesh:nodes`
- `analysis_mesh:elements`
- `analysis_mesh:generated_bend_nodes`
- `analysis_mesh:groups`

Viewer capabilities:

- toggle analysis mesh over cold geometry,
- color native versus generated mesh nodes,
- select mesh node/element and show source `EntityRef`,
- show Code_Aster group membership,
- show missing provenance diagnostics.

### 3. Code_Aster Results

Result overlays:

- stress/utilization from `SIEQ_ELNO` or `ResultState.element_results`,
- element forces/moments from `EFFO_ELNO`,
- reactions from `FORC_NODA`,
- displacements from `DEPL`,
- temperature/load-case metadata,
- parser diagnostics.

Viewer capabilities:

- load-case selector,
- result-set selector,
- scalar legend,
- min/max labels,
- threshold filters,
- stress hotspot list,
- reaction vector scale control,
- hover/selection shows source values.

### 4. Deformed/Warped Geometry

Scene layers:

- `deformed:physical_centerline`
- `deformed:physical_envelope`
- `deformed:visual_centerline`
- `deformed:visual_envelope`
- `deformed:mesh`

Rules:

- physical engineering scale defaults to `1.0`,
- visual scale is explicit and display-only,
- viewer scale slider cannot mutate engineering clash results,
- all warped assets include `geometry_state_id`, `result_state_id`, `load_case`, and `visual_scale` metadata.

Viewer capabilities:

- side-by-side or overlay cold/deformed geometry,
- scale slider for visual deformation,
- ghost cold geometry while deformed view is active,
- display displacement vectors and magnitudes,
- warn if only endpoint interpolation was available for bends.

### 5. Clash Visualization

Scene objects:

- clash marker at computed location,
- involved object highlights,
- cold envelope ghost,
- operating envelope ghost,
- optional swept/deformation path indicator,
- issue row linked to marker and involved objects.

Issue metadata:

- clash ID,
- severity,
- status,
- left/right `EntityRef`,
- cold distance,
- operating distance,
- penetration,
- envelope type,
- load case,
- geometry state,
- result state,
- introduced-by-deformation flag,
- diagnostics.

Viewer capabilities:

- focus issue,
- isolate involved objects,
- toggle cold/operating envelopes,
- filter by `operating_only_hard`, `operating_only_clearance`, `cold_hard`, `resolved_in_operating`,
- export BCF with viewpoint and metadata.

## Realtime Preview Architecture

Yes, Mermaid-like realtime feedback is possible, but the source should be Python scripts and JSON patches, not YAML.

### Local Preview Mode

Command shape:

```powershell
.\.venv\Scripts\python.exe -m tuba.visualization.preview watch examples\my_model.py --port 8765 --out generated\live_scene
```

Runtime:

```text
trusted Python script save
  -> debounce
  -> run script in preview subprocess
  -> collect produced model, scene, patch, diagnostics
  -> validate model/scene/patch
  -> build VisualizationScene
  -> write bundle
  -> emit websocket event
  -> viewer reloads scene or applies SceneDiff
```

First implementation can reload the full scene bundle. Incremental `SceneDiff` comes after stable object identity and changed-object detection are proven.

### Script Contract

A trusted local script can expose any of these:

```python
model = build_model()
scene = build_visualization_scene(model)
patch = build_patch()
```

or call helper functions:

```python
from tuba.visualization.preview import show_model, show_scene, show_patch

model = build_model()
show_model(model)
```

The preview runner validates outputs and rejects unsafe/invalid states with a viewer-visible error overlay.

### JSON Patch Preview

Agents and tools should prefer JSON `ModelPatch` preview:

```text
patch.json save
  -> validate schema
  -> dry-run ModelTransaction against base model
  -> recompute affected scene
  -> emit full scene or SceneDiff
  -> viewer updates preview
```

This lets agents add or revise parts and see them appear in the scene editor without directly mutating the committed model.

### Websocket Protocol

Initial messages:

```json
{ "type": "scene_reloaded", "scene_uri": "scene.json", "bundle_revision": 12 }
{ "type": "scene_diff", "diff": { "...": "..." }, "base_scene_id": "scene:abc" }
{ "type": "diagnostic", "severity": "error", "message": "..." }
{ "type": "run_started", "revision": 13 }
{ "type": "run_finished", "revision": 13, "duration_ms": 284 }
```

### Safety

- Execute only trusted local files.
- Never execute Python from a scene bundle.
- Run preview execution in a subprocess.
- Add timeout and cancellation.
- Restrict current working directory to project/workspace by default.
- Do not run Code_Aster automatically on every save.
- Solver-backed results are imported from existing result files or mock states unless the user explicitly runs a solve.

## Notebook Strategy

Notebook support should be a consumer of the same viewer, not a separate architecture.

Options:

1. Embed the local web viewer in an iframe.
2. Use PyVista/trame for quick result plots.
3. Export a scene bundle and link/open it from the notebook.

Notebook is useful for exploration. The production review workflow should be the web viewer.

## Blender Strategy

Blender is optional export/review, not the main engine.

Use Blender for:

- high-quality screenshots,
- rendered animations,
- marketing/communication visuals,
- manual visual inspection by Blender users.

Do not use Blender for:

- primary issue list,
- route comparison UI,
- live code preview,
- patch approval,
- browser-embedded agent workflows.

## Implementation Plan

### Phase A - Make Existing Scene Data More Renderable

1. Add explicit `AnalysisMesh` scene assets.
2. Add result scalar overlay schema with legends.
3. Add deformed centerline/envelope scene assets.
4. Add clash marker and issue focus metadata.
5. Add scene bundle examples for cold, result, deformed, and clash states.

### Phase B - Build Real Viewer MVP

1. Convert `viewer/` to Vite + TypeScript.
2. Add Three.js renderer.
3. Render pipes, supports, obstacles, envelopes, vectors, markers.
4. Add object tree and property panel.
5. Add load-case/result-state/layer controls.
6. Add issue list and focus behavior.
7. Add Playwright screenshot/canvas tests.

### Phase C - Add Code_Aster Result Review

1. Render analysis mesh.
2. Render stress/utilization colors.
3. Render displacement/reaction vectors.
4. Render deformed physical and visual states.
5. Add legends and thresholds.
6. Add stress hotspot and clash issue filters.

### Phase D - Add Live Preview

1. Add preview server and file watcher.
2. Add full scene reload through websocket.
3. Add error overlay.
4. Add JSON patch dry-run preview.
5. Add `SceneDiff` incremental updates.
6. Add agent proposal preview through the same channel.

### Phase E - Scale And Adapters

1. Add asset hashing and cache reuse.
2. Add instancing/batching for repeated supports/markers.
3. Add worker parsing for large bundles.
4. Add optional IFC/Fragments/xeokit adapter.
5. Add optional VTK/vtk.js adapter for dense mesh/scalar fields.
6. Add benchmark gates for load time, selection latency, and diff update latency.

## First Vertical Slice

Build this first:

1. `examples/operating_state_clash.py` exports `scene.json`.
2. Viewer loads that scene.
3. Viewer shows cold pipe, rack obstacle, insulation envelope, operating envelope, clash marker.
4. User clicks the clash issue.
5. Viewer focuses the marker and highlights `element:pipe_hot_0` and `obstacle:rack_member_0`.
6. Property panel shows cold distance, operating distance, penetration, load case, and result state.
7. Deformation scale slider changes only visual deformed geometry.
8. Engineering clash metadata remains unchanged.
9. Saving the example script hot reloads the viewer.

## Acceptance Criteria

- Cold geometry, analysis mesh, solver results, deformed geometry, and clashes are separate togglable layers.
- A Code_Aster-derived stress overlay can be displayed without losing object identity.
- A warped/deformed view can be displayed with explicit visual scale.
- The viewer rejects or warns when visual scale is confused with engineering scale.
- An operating-only clash can be focused from the issue list.
- The viewer can reload a scene after saving a trusted local Python generation script.
- The viewer can preview a JSON `ModelPatch` without mutating the committed model.
- Notebook users can open or embed the same scene bundle.
- Unit tests do not require Code_Aster.
- Browser tests verify a nonblank rendered canvas for at least one fixture.
