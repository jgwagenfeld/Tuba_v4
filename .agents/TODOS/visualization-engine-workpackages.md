# Visualization Engine Workpackages

## Purpose

This roadmap packages the future visualization engine into implementable stages. It assumes the existing future-ready library foundations remain in place: entity refs, typed attributes, patch-first generation, physical properties, clash reports, route plans, route costs, rack assemblies, rules, quantities, and IFC adapters.

## Execution Strategy

- Build the semantic scene contract before UI features.
- Keep PyVista working while adding the new web-first path.
- Every package must have tests or fixture validation.
- Use scene fixtures as the coordination point between Python and the web viewer.
- Prefer review workflows first: inspect, compare, annotate, approve.
- Add authoring only after patch-review flows are stable.

## Status Legend

- `Pending`: not started.
- `In Progress`: actively being implemented.
- `Blocked`: needs a decision or dependency.
- `Complete`: implemented and verified.

## Milestones

| Milestone | Outcome | Packages |
| --- | --- | --- |
| VM0 | Spec and architecture baseline | VE00 |
| VM1 | Scene contract and exportable bundles | VE01, VE02, VE03 |
| VM2 | Interactive viewer MVP | VE04, VE05, VE06 |
| VM3 | Routing, clash, and rules review | VE07, VE08, VE09 |
| VM4 | Engineering overlays | VE10, VE11, VE12, VE13 |
| VM5 | Agentic and exchange workflows | VE14, VE15, VE16 |
| VM6 | Realtime and agentic preview | VE21, VE22 |
| VM7 | Scale, federation, operations | VE17, VE18, VE19, VE20 |

## Dependency Graph

```text
VE00
  -> VE01 Scene manifest
      -> VE02 Scene builders
          -> VE03 Geometry bundle export
              -> VE04 Web viewer shell
                  -> VE05 Selection/property panel
                  -> VE06 Tree/search/layers/sectioning
                  -> VE07 Route review
                  -> VE08 Clash and issue review
                  -> VE09 Rule review
      -> VE10 Physical envelope overlays
      -> VE11 Cost/quantity overlays
      -> VE12 Rack/support/load-path overlays
      -> VE13 Solver-result overlays
      -> VE14 Model diff and agent proposal review
      -> VE15 IFC mapping
      -> VE16 BCF exchange
  -> VE17 Performance and large-scene strategy
      -> VE18 External model federation
      -> VE19 Point cloud and field context
      -> VE20 Digital twin state overlays
  -> VE21 Realtime Python and JSON patch preview
      -> VE22 Agentic Python workspace
```

## Package Checklist

| ID | Package | Status | Verification Gate |
| --- | --- | --- | --- |
| VE00 | Visualization architecture baseline | Complete | docs/spec review |
| VE01 | Scene manifest and schema | Complete | scene schema unit tests |
| VE02 | Semantic scene builders | Complete | model-to-scene fixture tests |
| VE03 | Geometry bundle export | Complete | bundle layout and glTF metadata tests |
| VE04 | Web viewer shell | Complete | local fixture loads in browser |
| VE05 | Selection and property panel | Complete | E2E object selection test |
| VE06 | Tree, filters, layers, measurement, sectioning | Complete | E2E UI workflow tests |
| VE07 | Route alternatives review | Complete | route fixture comparison test |
| VE08 | Clash and issue review | Complete | issue focus and BCF-compatible fixture |
| VE09 | Rule/compliance review | Complete | rule diagnostics fixture |
| VE10 | Physical envelope overlays | Complete | insulation/clearance toggle tests |
| VE11 | Cost and quantity overlays | Complete | cost heatmap fixture |
| VE12 | Rack/support/load-path overlays | Complete | rack attachment fixture |
| VE13 | Solver-result overlays | Complete | result overlay fixture |
| VE14 | Model diff and agent proposal review | Complete | patch preview fixture |
| VE15 | IFC visualization mapping | Complete | IFC GUID mapping tests |
| VE16 | BCF issue exchange | Complete | BCF export/import tests |
| VE17 | Performance and large-scene strategy | Complete | benchmark report |
| VE18 | External model federation | Complete | multi-source fixture |
| VE19 | Point cloud and field context | Complete | point-cloud fixture |
| VE20 | Digital twin state overlays | Complete | time/state fixture |
| VE21 | Realtime Python and JSON patch preview | Complete | script watcher and scene diff tests |
| VE22 | Agentic Python workspace | Complete | sandboxed cell execution and proposal trace tests |

## VE00 - Visualization Architecture Baseline

**Goal:** Make the visualization direction durable and align it with the already implemented future-ready library architecture.

**Deliverables:**

- `.agents/SPECS/visualization-engine.md`
- `.agents/DECISIONS/visualization-engine.md`
- `.agents/TODOS/visualization-engine-workpackages.md`
- `docs/visualization_engine_vision.md`

**Acceptance Criteria:**

- The spec states that visualization is semantic and review-first.
- The spec states that PyVista remains for engineering plots.
- The spec states that IFC is an adapter.
- The package list covers routing, clash, rules, physical envelopes, cost, rack, solver, agentic, IFC/BCF, performance, federation, point cloud, and digital twin features.

**Verify:**

```powershell
Get-ChildItem .agents\SPECS\visualization-engine.md, .agents\DECISIONS\visualization-engine.md, .agents\TODOS\visualization-engine-workpackages.md, docs\visualization_engine_vision.md
```

## VE01 - Scene Manifest And Schema

**Goal:** Define `VisualizationScene` as the canonical data contract between Tuba model/results and renderer adapters.

**Dependencies:** VE00.

**Deliverables:**

- `tuba/visualization/scene.py`
- `tuba/visualization/schema.py`
- Dataclasses for:
  - `VisualizationScene`
  - `SceneObject`
  - `GeometryAsset`
  - `SceneMaterial`
  - `SceneStyle`
  - `Overlay`
  - `Issue`
  - `RouteReview`
  - `AgentProposal`
  - `ViewState`
  - `SceneDiagnostic`
- JSON serialization and deserialization.
- Schema version field.
- Validation for stable IDs, object/asset links, and entity refs.

**Acceptance Criteria:**

- A minimal scene roundtrips through JSON.
- Invalid object references produce clear validation errors.
- Unknown future fields can be preserved or rejected by explicit policy.
- Scene objects can reference `EntityRef`.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_visualization_scene -v
```

## VE02 - Semantic Scene Builders

**Goal:** Build `VisualizationScene` objects from existing Tuba data without requiring a web viewer.

**Dependencies:** VE01.

**Deliverables:**

- `tuba/visualization/builders.py`
- `SceneBuildOptions`
- Model object extraction for:
  - pipes,
  - bends,
  - supports,
  - rack members,
  - obstacles,
  - groups,
  - assemblies.
- Metadata projection from:
  - sections,
  - materials,
  - attributes,
  - physical properties,
  - quantities,
  - IFC refs.
- Builders for routes, clashes, rules, costs, solver results, and agent proposals.

**Acceptance Criteria:**

- A simple Tuba model becomes a scene with selectable objects.
- Insulation specs are visible in object metadata.
- Physical properties are visible in object metadata.
- Scene builder does not require PyVista.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_visualization_builders -v
```

## VE03 - Geometry Bundle Export

**Goal:** Export geometry and metadata into a browser-loadable scene bundle.

**Dependencies:** VE01, VE02.

**Deliverables:**

- `tuba/visualization/web_export.py`
- Bundle writer:
  - `scene.json`
  - `metadata/*.json`
  - `geometry/*.glb`
  - optional `snapshots/*.png`
- GLB export with object picking metadata sidecar.
- Deterministic asset IDs and hashes.
- Fallback polyline/tube geometry for simplified route candidates.
- Diagnostics for failed mesh generation.

**Acceptance Criteria:**

- A scene bundle can be generated from a simple model.
- Every selectable GLB object maps to a `SceneObject`.
- Bundle uses relative URIs.
- Existing `tuba.visualizer.export` remains compatible.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_visualization_web_export tests.test_visualizer_scenes -v
```

## VE04 - Web Viewer Shell

**Goal:** Add a local web viewer that loads generated scene bundles.

**Dependencies:** VE03.

**Deliverables:**

- `viewer/` workspace or equivalent.
- Three.js or selected first renderer.
- Scene loading.
- Camera controls.
- Axes/grid toggles.
- Fit-all and standard views.
- Basic layer visibility.
- Error state for invalid/missing bundles.

**Acceptance Criteria:**

- Local fixture scene loads in the browser.
- Canvas is nonblank.
- Camera navigation works.
- Viewer can run from local dev server.

**Verify:**

```powershell
npm --prefix viewer test
npm --prefix viewer run build
```

## VE05 - Selection And Property Panel

**Goal:** Make scene objects inspectable.

**Dependencies:** VE04.

**Deliverables:**

- Object picking.
- Hover highlight.
- Single and multi-select.
- Property panel sections:
  - identity,
  - geometry,
  - physical,
  - attributes,
  - quantities/cost,
  - route,
  - clash/rules,
  - IFC/external refs,
  - provenance.
- Copy entity ref.
- Fit selection.
- Hide/isolate selected.

**Acceptance Criteria:**

- Selecting an insulated pipe shows insulation material, thickness, effective OD, mass per meter, and wind diameter.
- Selecting a route candidate shows route metrics and diagnostics.

**Verify:**

```powershell
npm --prefix viewer test
npm --prefix viewer run e2e -- selection
```

## VE06 - Tree, Filters, Layers, Measurement, And Sectioning

**Goal:** Provide the basic review controls users expect in serious model viewers.

**Dependencies:** VE04, VE05.

**Deliverables:**

- Model tree grouped by route/system/group/assembly/kind.
- Search.
- Filters by material, route, severity, status, object kind, cost code.
- Layer manager.
- Section box.
- Clipping planes.
- Measurement tools.
- Saved view states.
- Screenshot from current view.

**Acceptance Criteria:**

- User can isolate one route and its clashes.
- User can restore a saved issue viewpoint.
- Measurement can show distance between two selected points or objects.

**Verify:**

```powershell
npm --prefix viewer run e2e -- review-controls
```

## VE07 - Route Alternatives Review

**Goal:** Turn automatic routing into an inspectable decision workflow.

**Dependencies:** VE02, VE05, VE06.

**Deliverables:**

- `RouteReview` builder.
- Candidate geometry overlays.
- Candidate comparison table.
- Cost breakdown panel.
- Valid/invalid state and diagnostics.
- Toggle centerline, pipe body, insulation envelope, and clearance envelope.
- Selected route emphasis.
- Patch preview link for candidate application.

**Acceptance Criteria:**

- User can compare detour versus added structure by cost terms.
- Invalid routes are visible but clearly marked.
- Viewer and route report agree on selected candidate and cost.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_visualization_route_review -v
npm --prefix viewer run e2e -- route-review
```

## VE08 - Clash And Issue Review

**Goal:** Make clash reports navigable and compatible with external coordination workflows.

**Dependencies:** VE02, VE05, VE06.

**Deliverables:**

- `Issue` builder from `ClashReport`.
- Clash marker geometry.
- Issue list.
- Focus issue.
- Highlight involved objects.
- Severity/status filters.
- Comments/status fields in scene data.
- BCF-compatible internal fields.

**Acceptance Criteria:**

- Clash report count matches viewer issue count.
- Focusing a clash restores camera and selection.
- Insulation-driven clash identifies envelope source.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_visualization_issues tests.test_clash_engine -v
npm --prefix viewer run e2e -- clash-review
```

## VE09 - Rule And Compliance Review

**Goal:** Visualize rule diagnostics, not only hard geometry clashes.

**Dependencies:** VE02, VE08.

**Deliverables:**

- Rule issue builder.
- Support spacing violation overlays.
- Slope violation overlays.
- Bend-count violation overlays.
- Rack occupancy violation overlays.
- Code/stress ratio overlays where result data exists.
- Rule details panel.

**Acceptance Criteria:**

- Clicking a rule violation focuses the relevant object/view.
- Rule report and viewer issue list agree on IDs and severity.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_visualization_rules tests.test_rules -v
```

## VE10 - Physical Envelope Overlays

**Goal:** Make non-geometry physical attributes visible and auditable.

**Dependencies:** VE02, VE03.

**Deliverables:**

- Bare pipe overlay.
- Insulation envelope overlay.
- Cladding envelope overlay.
- Clearance envelope overlay.
- Maintenance envelope overlay.
- Wind projected envelope overlay.
- Envelope source metadata.

**Acceptance Criteria:**

- User can toggle bare/effective/clearance geometry independently.
- Selecting an envelope explains its radius source.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_visualization_envelopes tests.test_physical_properties -v
```

## VE11 - Cost And Quantity Overlays

**Goal:** Connect economics and takeoff to the model view.

**Dependencies:** VE02, VE05.

**Deliverables:**

- Cost heatmap overlay.
- Quantity summary by route/system/rack/material.
- Cost breakdown by selected object.
- Route cost delta view.
- High-cost object filter.
- Export selected quantity/cost table.

**Acceptance Criteria:**

- User can identify whether cost comes from length, insulation, supports, or structure.
- Quantity totals in viewer match `quantity_takeoff()`.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_visualization_costs tests.test_quantities -v
```

## VE12 - Rack, Support, And Load-Path Overlays

**Goal:** Make rack construction and load transfer understandable.

**Dependencies:** VE02, VE05, VE10.

**Deliverables:**

- Rack assembly hierarchy.
- Rack level/lane visualization.
- Attachment point markers.
- Support-to-rack association overlays.
- Load path vectors.
- Rack member utilization overlays.
- Missing-association diagnostics.

**Acceptance Criteria:**

- Selecting a pipe support shows the rack member it loads.
- Missing support attachment is visible as a diagnostic.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_visualization_racks tests.test_load_path tests.test_rack_assemblies -v
```

## VE13 - Solver-Result Overlays

**Goal:** Bring selected solver results into the shared viewer while keeping PyVista for detailed engineering plots.

**Dependencies:** VE02, VE04.

**Deliverables:**

- Displacement magnitude overlay.
- Deformed shape overlay.
- Stress/utilization overlay.
- Reaction vector overlay.
- Temperature overlay.
- Load case selector.
- Deformation scale control.
- Source result metadata.

**Acceptance Criteria:**

- Existing solver visualizations remain available.
- Web overlays can be shown next to routes, clashes, and attributes.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_visualization_results tests.test_visualizer_scenes -v
```

## VE14 - Model Diff And Agent Proposal Review

**Goal:** Make generated changes inspectable before model mutation.

**Dependencies:** VE01, VE02, VE05, VE07.

**Deliverables:**

- `AgentProposal` scene model.
- `ModelPatch` preview builder.
- Added/removed/modified object overlays.
- Before/after metrics.
- Approval state.
- Review comments.
- Export proposal report.

**Acceptance Criteria:**

- Agent-generated geometry appears as proposal geometry, not applied geometry.
- User can inspect cost/clash/rule deltas before approval.
- Proposal can be approved into a patch application flow.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_visualization_agent_proposals tests.test_patches -v
```

## VE15 - IFC Visualization Mapping

**Goal:** Preserve object identity and semantics across IFC context and exported review models.

**Dependencies:** VE01, VE02, VE03.

**Deliverables:**

- IFC GUID mapping in scene metadata.
- IFC property set mapping for route, rack, insulation, cost, quantities, issues.
- External IFC context source support.
- IFC import diagnostics in scene diagnostics.

**Acceptance Criteria:**

- Scene object can carry both `EntityRef` and IFC GUID.
- Exported IFC contains route/rack/insulation metadata where supported.
- IFC import does not become required for native Tuba review.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_visualization_ifc tests.test_ifc -v
```

## VE16 - BCF Issue Exchange

**Goal:** Exchange Tuba clash/rule issues with external BIM coordination tools.

**Dependencies:** VE08, VE15.

**Deliverables:**

- `tuba/visualization/bcf.py`
- BCF topic export.
- BCF viewpoint export.
- BCF import where object refs can be mapped.
- Status/comment roundtrip.

**Acceptance Criteria:**

- Tuba clash issue exports to BCF with viewpoint and involved objects.
- Imported BCF topic can become a scene issue when object mapping exists.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_visualization_bcf -v
```

## VE17 - Performance And Large-Scene Strategy

**Goal:** Keep visualization usable as models grow.

**Dependencies:** VE03, VE04.

**Deliverables:**

- Scene build benchmarks.
- Bundle size benchmarks.
- Viewer load benchmarks.
- Selection latency benchmarks.
- Geometry batching.
- Asset hashing and cache reuse.
- LOD descriptors.
- Progressive loading plan.
- Optional worker-based parsing.

**Acceptance Criteria:**

- Benchmarks are saved under `.benchmarks/`.
- Moderate demo scene has measured build/load/selection timings.
- Performance diagnostics appear in scene bundle when limits are exceeded.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_visualization_performance -v
```

## VE18 - External Model Federation

**Goal:** Review Tuba-generated design against external context models.

**Dependencies:** VE15, VE17.

**Deliverables:**

- Multi-source scene support.
- Source visibility toggles.
- Coordinate transform metadata.
- External object metadata.
- Source alignment diagnostics.
- Overlay support across sources.

**Acceptance Criteria:**

- Tuba model and imported IFC context can be loaded in one scene.
- Viewer can isolate by source.
- Transform metadata is visible and validated.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_visualization_federation -v
```

## VE19 - Point Cloud And Field Context

**Goal:** Prepare the viewer for retrofit and field verification workflows.

**Dependencies:** VE17, VE18.

**Deliverables:**

- Point cloud asset descriptor.
- Point cloud visibility/layer controls.
- Sectioning support for point cloud.
- Field note markers.
- Model-to-scan deviation issue placeholder.

**Acceptance Criteria:**

- A small point cloud fixture can be loaded beside model geometry.
- Field note can be attached to position or selected object.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_visualization_point_cloud -v
```

## VE20 - Digital Twin State Overlays

**Goal:** Allow the visualization engine to display operational/asset states later.

**Dependencies:** VE01, VE05, VE17.

**Deliverables:**

- Runtime state overlay schema.
- Asset ID mapping.
- Time/state selector.
- Status colors for active/inactive/alarm/maintenance/inspection.
- External data source placeholder.

**Acceptance Criteria:**

- Scene can include a non-geometry state overlay.
- Viewer can switch between two timestamped state sets.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_visualization_digital_twin -v
```

## VE21 - Realtime Python And JSON Patch Preview

**Goal:** Provide a Mermaid-like live feedback loop without adding YAML or a weak DSL to the core architecture.

**Dependencies:** VE01, VE02, VE03, VE04, VE14.

**Deliverables:**

- Trusted local Python script watch mode.
- JSON `ModelPatch` watch mode.
- Dry-run preview execution.
- Patch validation diagnostics.
- `SceneDiff` model and serializer if not already completed in VE01.
- Scene diff generation for added, updated, and removed objects.
- Hot reload channel for the web viewer.
- Full scene rebuild fallback.
- Error overlay in the viewer.
- Agent proposal preview through the same JSON patch path.
- Documentation that YAML/Mermaid-style DSL is deferred.

**Acceptance Criteria:**

- Saving a trusted Python script rebuilds or updates the viewer scene.
- Saving a JSON patch validates it, dry-runs it, and previews the result without mutating the committed model.
- Invalid Python scripts and invalid JSON patches produce visible diagnostics.
- A small object update can be delivered as `SceneDiff`.
- Full rebuild fallback is used when the diff cannot be computed safely.
- Agent-generated `ModelPatch` payloads use the same preview path.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_visualization_live_preview tests.test_visualization_scene -v
npm --prefix viewer run e2e -- live-preview
```

## VE22 - Agentic Python Workspace

**Goal:** Add a SpatialClaw-inspired agent workspace where agents solve spatial/routing problems through small Python steps, inspect intermediate state, and then emit a reviewable patch.

**Dependencies:** VE01, VE02, VE03, VE14, VE21.

**Deliverables:**

- Persistent sandboxed Python workspace for agent sessions.
- Session model for:
  - agent ID,
  - goal,
  - input model snapshot or model reference,
  - executed cells,
  - stdout/stderr,
  - errors,
  - variable summaries,
  - generated scene snapshots,
  - generated route/cost/clash/rule diagnostics,
  - final proposal.
- Preloaded Tuba helpers:
  - model and entity lookup,
  - route planning,
  - route costing,
  - clash checking,
  - rule checking,
  - quantity/load-path queries,
  - `build_visualization_scene()`,
  - `show_scene()` / `show_route_candidates()` style feedback helpers.
- Resource limits for time, memory, filesystem, network, and subprocess access.
- Read-only default committed model.
- Explicit temporary working model or transaction scope for experiments.
- Final output restricted to schema-valid JSON `ModelPatch`, `RoutePlan`, or `AgentProposal`.
- Dry-run validation through `ModelTransaction`.
- `SceneDiff` preview through VE21.
- Execution trace linked to the final proposal.
- Documentation that SpatialClaw is a design pattern reference, not a direct dependency.

**Acceptance Criteria:**

- Agent can run multiple small Python cells in one persistent session.
- Workspace preserves useful variables between cells.
- Workspace returns stdout, errors, variable summaries, and scene snapshot references.
- Unsafe operations are blocked or fail with typed diagnostics.
- Agent cannot mutate the committed model without producing a patch/proposal.
- Final proposal includes rationale, metrics, diagnostics, executed-cell trace, and patch payload.
- Viewer can display at least one intermediate scene snapshot from the agent session.

**Verify:**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_agentic_python_workspace tests.test_visualization_agent_proposals tests.test_patches -v
npm --prefix viewer run e2e -- agent-workspace
```

## Suggested First Vertical Slice

Build the smallest useful review loop:

1. VE01: scene manifest with objects, assets, overlays, issues, and views.
2. VE02: scene builder for pipes, obstacles, physical properties, and route candidates.
3. VE03: bundle export with GLB geometry plus metadata sidecar.
4. VE04: viewer shell that loads the fixture.
5. VE05: selection and property panel.
6. VE07: route candidate comparison.
7. VE08: clash issue focus.
8. VE10: insulation/clearance envelope toggles.
9. VE21: JSON patch preview hot reload.
10. VE22: one agent workspace session emits a validated JSON patch.

This slice proves that one semantic model feeds route review, clash review, physical envelope review, and interactive object inspection.

## Parallelization Plan

After VE01:

- Track A: VE02 scene builders.
- Track B: VE03 geometry bundle exporter.
- Track C: VE15 IFC metadata mapping design.

After VE04:

- Track D: VE05 selection/property panel.
- Track E: VE06 tree/filter/sectioning controls.
- Track F: VE07 route review.
- Track G: VE08 clash issue review.

After VE07/VE08:

- Track H: VE10 physical envelopes.
- Track I: VE11 cost/quantity overlays.
- Track J: VE12 rack/load-path overlays.
- Track K: VE14 agent proposal review.

After VE14:

- Track L: VE21 live Python and JSON patch preview.

After VE21:

- Track M: VE22 agentic Python workspace.

## Final Verification Gate

Before considering the visualization engine foundation complete:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
npm --prefix viewer test
npm --prefix viewer run build
npm --prefix viewer run e2e
```

Required manual demos:

- Open a generated scene bundle.
- Select an insulated pipe and inspect physical/cost data.
- Compare route alternatives.
- Focus a clash issue and export BCF.
- Toggle insulation and clearance envelopes.
- Review an agent-generated `ModelPatch` before applying it.
- Preview a trusted Python script edit and JSON `ModelPatch` edit in the live viewer.
- Run an agentic Python workspace session that produces a validated proposal and intermediate scene snapshot.
- Export a screenshot/report from a saved viewpoint.
