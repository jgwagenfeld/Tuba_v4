# Future Visualization Engine Spec

## Purpose

Build a future-ready visualization engine for Tuba that turns scripted geometry, routing, clash checks, costs, physical attributes, rack assemblies, solver results, IFC data, and agent proposals into an interactive engineering review environment.

The goal is not only to render pipes. The viewer must become the decision cockpit for piping, racks, structure, route alternatives, insulation and cladding envelopes, cost optimization, load paths, wind effects, rule diagnostics, clash issues, and generated model changes.

Realtime preview should be built around trusted Python scripts and schema-valid JSON patches/scene diffs. YAML or Mermaid-style text can be reconsidered later for simple templates, but it is not part of the first-class architecture because piping and rack generation need real programming constructs, typed validation, and patch review.

## Summary Recommendation

Tuba should keep the current PyVista visualizer for engineering plots, solver-result exploration, screenshots, notebooks, and quick local workflows.

Tuba should add a separate semantic, web-first visualization engine for interactive review and future agentic workflows. Both renderers must consume the same semantic scene manifest.

```text
TubaModel + routes + clashes + rules + costs + solver results + IFC data
        |
        v
Semantic VisualizationScene
        |
        +-- PyVista adapter: solver plots, quick debug, screenshots
        +-- Web viewer adapter: design review, routing, issues, agent proposals
        +-- Export adapters: glTF/GLB, metadata JSON, IFC, BCF, screenshots
```

## Existing Starting Point

Current capabilities:

- `tuba.visualizer.scenes.build_model_scene()` creates a PyVista scene from a model and optional solver results.
- `tuba.visualizer.plots` renders stress, deformation, displacement vectors, reactions, temperature, supports, and local axes.
- `tuba.visualizer.export` exports HTML, PLY, glTF, screenshots, and Blender scripts.
- `tuba.routing.visualization` renders obstacles, endpoints, selected route candidates, alternative candidates, and model pipes.
- `tuba.physical`, `tuba.clash`, `tuba.quantities`, `tuba.rules`, and `tuba.routing.cost_model` already carry richer semantic data than the viewer currently displays.

Main gaps:

- No shared semantic scene contract.
- No object picking or property inspection.
- No model tree, layer filters, saved views, section box, measurement, or issue workflow.
- Routing visuals are simplified and not tied deeply enough to physical envelopes, cost breakdowns, rule diagnostics, or patch review.
- Clash and rule results are not first-class visual entities.
- IFC and BCF are exchange concerns, not integrated into the visualization workflow.
- Exports focus on geometry, not traceable object metadata.

## Product Principles

1. **Visualization is a review workflow, not a screenshot generator.**
   Users must be able to select, inspect, filter, compare, annotate, and approve.

2. **Semantics are first-class.**
   A pipe is not only a mesh. It has a route ID, section, material, insulation, cladding, cost, weight, wind diameter, clash envelope, supports, rules, and provenance.

3. **Geometry is a projection of model state.**
   The viewer must not infer engineering meaning from mesh shape when the model already knows that meaning.

4. **IFC is an adapter, not the internal source of truth.**
   Tuba owns its internal model, routing state, clash state, and issue state. IFC and BCF exchange those facts with external tools.

5. **Agents propose patches, not silent mutations.**
   Agentic workflows must show proposed changes as reviewable diffs with rationale, cost delta, clash delta, and rule impact.

6. **Performance is architectural.**
   Large projects require stable IDs, geometry batching, spatial indexes, progressive loading, and cacheable scene bundles.

7. **Every visual claim must trace back to data.**
   A highlighted clash, cost, weight, route ranking, or rule violation must identify source entities and source computations.

## Non-Goals

- Do not replace professional CAD authoring in the first visualization phase.
- Do not make the browser viewer the solver engine.
- Do not make IFC mandatory for internal routing, clash checking, or optimization.
- Do not attempt exact CAD-kernel rendering for every feature in the first version.
- Do not require a cloud backend for the first local interactive viewer.
- Do not mutate `TubaModel` directly from the viewer without a `ModelPatch` or equivalent approval boundary.
- Do not remove PyVista; reduce its responsibility to scientific visualization and compatibility paths.
- Do not add YAML or a Mermaid-style DSL as a first-class modeling input in the first visualization phase.
- Do not execute untrusted Python from scene bundles or remote viewer input.

## User Roles

### Piping Engineer

Needs to inspect pipe routes, dimensions, insulation, supports, bends, stress, displacement, clearances, and code/rule diagnostics.

### Structural / Rack Engineer

Needs to inspect rack modules, members, load paths, support reactions, utilization, attachments, occupied lanes, and added-structure alternatives.

### BIM / Coordination Lead

Needs IFC import/export, BCF topics, model federation, issue status, clash grouping, viewpoints, and deterministic object IDs.

### Cost / Planning User

Needs quantities, material takeoff, route cost breakdowns, support costs, structure costs, insulation/cladding cost, and delta comparisons.

### Agent / Automation Operator

Needs to review proposed patches, compare generated alternatives, inspect rationale, accept/reject changes, and capture provenance.

### Developer

Needs a clear scene API, renderer adapters, fixtures, golden metadata tests, and stable contracts that can evolve without rewriting routing or clash engines.

## Target Architecture

### Layer 1 - Core Engineering Model

Existing and future core modules:

- `TubaModel`
- `EntityRef`
- `AttributeAssignment`
- `InsulationSpec`, `CladdingSpec`, cost specs, route specs, rack specs
- `ModelPatch` and `ModelTransaction`
- `RoutePlan`
- `RouteCostBreakdown`
- `ClashReport`
- `RuleReport`
- `QuantityTakeoff`
- solver result containers

This layer is authoritative.

### Layer 2 - Visualization Scene Builder

New package:

```text
tuba/visualization/
  scene.py
  builders.py
  geometry_assets.py
  overlays.py
  issues.py
  styles.py
  schema.py
```

Responsibilities:

- Build a `VisualizationScene` from model state and result objects.
- Resolve stable object IDs.
- Produce geometry asset descriptors.
- Attach metadata and derived properties.
- Create overlays for routes, clashes, rules, loads, quantities, and agent proposals.
- Validate scene schema.

### Layer 3 - Renderer Adapters

New packages:

```text
tuba/visualization/pyvista_adapter.py
tuba/visualization/web_export.py
tuba/visualization/ifc_exchange.py
tuba/visualization/bcf.py
```

Responsibilities:

- Render or export the same `VisualizationScene` through different engines.
- Keep renderer-specific concerns out of routing, clash, rules, and model code.
- Allow multiple web engines later: plain Three.js, xeokit, That Open Fragments, or vtk.js.

### Layer 4 - Interactive Web App

New package:

```text
viewer/
  package.json
  src/
    app/
    scene/
    viewer/
    panels/
    overlays/
    issues/
    agents/
```

Responsibilities:

- Load scene bundles.
- Render model geometry.
- Provide selection, filtering, overlays, route review, issue review, and patch approval.
- Work locally from generated static files first.

### Layer 5 - Exchange And Collaboration

Adapters:

- IFC property-set mapping.
- BCF issue import/export.
- glTF/GLB plus metadata sidecar.
- Optional Fragments/XKT export for large BIM models.
- Optional Speckle/iTwin/CDE integration later.

## Core Data Model

### `VisualizationScene`

Canonical scene manifest.

Required fields:

- `schema_version`
- `scene_id`
- `model_id`
- `created_at`
- `units`
- `coordinate_system`
- `objects`
- `geometry_assets`
- `materials`
- `styles`
- `overlays`
- `issues`
- `route_reviews`
- `agent_proposals`
- `views`
- `scene_diffs`
- `diagnostics`

### `SceneObject`

One selectable engineering object.

Required fields:

- `id`: stable scene object ID.
- `entity_ref`: `element:pipe_0`, `route:P-100`, `group:rack_A`, `obstacle:box_1`, etc.
- `kind`: `pipe`, `bend`, `support`, `rack_member`, `obstacle`, `equipment`, `route_candidate`, `clash_marker`, `load_vector`, etc.
- `name`
- `geometry_asset_id`
- `parent_id`
- `group_ids`
- `layer_ids`
- `metadata`
- `quantities`
- `physical`
- `style_id`
- `source`
- `diagnostics`

### `GeometryAsset`

Geometry descriptor, not business logic.

Required fields:

- `id`
- `format`: `mesh`, `polyline`, `tube`, `glyph`, `point_cloud`, `glb`, `xkt`, `fragments`, `ifc_ref`
- `uri`
- `bounds`
- `lod`
- `object_ids`
- `hash`
- `generation_config`

### `ObjectMetadata`

User-facing and machine-readable facts.

Examples:

- Section ID.
- Material ID.
- Line ID.
- System ID.
- Route ID.
- Rack assembly ID.
- Insulation spec ID and material.
- Insulation thickness.
- Cladding spec.
- Cost code.
- Revision/provenance.
- IFC GUID.
- Solver element ID.

### `PhysicalProperties`

Derived engineering properties:

- bare OD/radius.
- effective OD/radius.
- insulation thickness.
- cladding thickness.
- mass per meter.
- insulation mass per meter.
- fluid mass placeholder.
- wind projected diameter.
- clash radius.
- clearance radius.
- surface area.
- volume.

### `Overlay`

Visual layer derived from engineering results.

Kinds:

- `route_alternatives`
- `selected_route`
- `clash`
- `clearance`
- `rule_violation`
- `cost_heatmap`
- `mass_heatmap`
- `wind_envelope`
- `insulation_envelope`
- `rack_lane_occupancy`
- `support_reactions`
- `load_path`
- `stress`
- `displacement`
- `temperature`
- `agent_proposal`
- `model_diff`
- `point_cloud_alignment`
- `digital_twin_state`

### `Issue`

Internal issue object compatible with BCF concepts.

Required fields:

- `id`
- `type`: `clash`, `rule`, `routing`, `cost`, `constructability`, `review_comment`
- `title`
- `description`
- `severity`
- `status`
- `entity_refs`
- `view_id`
- `source_report_id`
- `created_by`
- `created_at`
- `comments`
- `external_refs`

### `RouteReview`

Interactive route comparison object.

Required fields:

- `request_id`
- `selected_candidate_id`
- `candidates`
- `cost_terms`
- `rule_results`
- `clash_results`
- `support_plan`
- `structure_plan`
- `patch_preview`
- `diagnostics`

### `AgentProposal`

Reviewable generated change.

Required fields:

- `proposal_id`
- `agent_id`
- `goal`
- `rationale`
- `model_patch`
- `before_metrics`
- `after_metrics`
- `changed_entity_refs`
- `created_entity_refs`
- `removed_entity_refs`
- `risks`
- `approval_state`
- `review_comments`

### `SceneDiff`

Incremental viewer update payload.

Required fields:

- `diff_id`
- `base_scene_id`
- `created_at`
- `added_objects`
- `updated_objects`
- `removed_object_ids`
- `added_geometry_assets`
- `updated_overlays`
- `updated_issues`
- `updated_route_reviews`
- `updated_agent_proposals`
- `diagnostics`

Scene diffs are for realtime preview and hot reload. They are not a replacement for `ModelPatch`; they describe viewer changes after the model, patch, and result layers have already been evaluated.

### `ViewState`

Saved camera and visual context.

Required fields:

- `id`
- `name`
- `camera`
- `section_box`
- `visible_layers`
- `hidden_object_ids`
- `selected_object_ids`
- `active_overlay_ids`
- `issue_id`
- `snapshot_uri`

## Feature Specification

### F01 - Interactive Navigation

Required:

- Orbit, pan, zoom.
- Fit all, fit selection, fit issue, fit route.
- Standard views: top, front, side, isometric.
- Orthographic and perspective cameras.
- Camera reset.
- Navigation cube or equivalent.
- Coordinate axes and scale reference.
- Grid/floor toggle.

Acceptance:

- User can inspect a rack and route candidate without losing orientation.
- Saved viewpoints restore camera, clipping, selected object, and active overlays.

### F02 - Object Picking And Property Panel

Required:

- Click object to select.
- Multi-select.
- Hover highlight.
- Property panel grouped into:
  - identity,
  - geometry,
  - physical properties,
  - attributes/specs,
  - quantities/cost,
  - routing,
  - clash/rules,
  - IFC/external refs,
  - provenance.
- Copy entity ref.
- Reveal object in tree.
- Isolate/hide selected.

Acceptance:

- Selecting an insulated pipe shows both bare OD and effective OD.
- Selecting a route candidate shows length, bends, cost terms, validity, and diagnostics.

### F03 - Model Tree, Search, Filters, And Layers

Required:

- Tree by system, line, route, rack assembly, object kind, IFC spatial hierarchy when imported.
- Text search by ID, tag, material, route, group, issue, cost code.
- Layer toggles:
  - pipes,
  - bends,
  - supports,
  - rack/structure,
  - obstacles/equipment,
  - insulation envelopes,
  - clearance envelopes,
  - route candidates,
  - solver results,
  - issues,
  - point clouds.
- Filter by severity, status, material, route, rack, cost code, rule type.

Acceptance:

- User can isolate one route and its conflicts without deleting or mutating model data.

### F04 - Measurement And Sectioning

Required:

- Point-to-point distance.
- Object-to-object distance where available.
- Pipe clearance measurement using effective envelopes.
- Section box.
- Clipping planes.
- Explode/fade by assembly or discipline.
- Transparent ghost mode.

Acceptance:

- User can verify whether insulation/clearance creates a spatial conflict.

### F05 - Visual Styling And Color Modes

Required:

- Color by material.
- Color by system/line.
- Color by route.
- Color by cost.
- Color by mass.
- Color by rule severity.
- Color by clash status.
- Color by utilization/stress.
- Color by revision/proposal.
- Opacity controls by layer.
- Standard color palette for hard clash, warning, info, selected, proposed, removed, unchanged.

Acceptance:

- Color semantics are consistent across PyVista, web viewer, screenshots, and exported review images.

### F06 - Route Alternatives Review

Required:

- Show all candidates with selected candidate emphasized.
- Display invalid candidates with reason.
- Compare candidate table:
  - length,
  - bends,
  - vertical travel,
  - support count,
  - structure additions,
  - insulation cost,
  - total cost,
  - hard clashes,
  - clearance violations,
  - rule violations,
  - risk score.
- Toggle candidate visibility.
- Ghost candidate geometry.
- Show route centerline, pipe outer envelope, insulation envelope, and required clearance envelope separately.
- Show routing grid/blocked cells optionally for debugging.
- Apply selected candidate only through `RoutePlan` and `ModelPatch`.

Acceptance:

- User can answer: "Is this detour cheaper than adding structure?"
- User can see why an automatic route was selected or rejected.

### F07 - Clash And Clearance Review

Required:

- Clash issue list.
- Click issue to focus viewpoint.
- Highlight both involved objects.
- Show hard clash, soft clearance violation, touching, and info statuses.
- Show penetration or clearance distance where available.
- Group clashes by route, object pair, zone, severity, and type.
- Mark issue status: open, reviewed, accepted risk, fixed, false positive.
- Add comments.
- Export/import BCF-compatible topics.

Acceptance:

- An insulated pipe that creates a clash is visually distinguishable from a bare-pipe clash.
- Clash report and viewer issue list have matching IDs and counts.

### F08 - Rule And Compliance Review

Required:

- Display rule results from `RuleEngine`.
- Show failed/passed/warning states.
- Link each result to entity refs.
- Visualize support spacing violations.
- Visualize slope violations.
- Visualize rack lane occupancy.
- Visualize constructability clearances.
- Visualize ASME/code check ratios where available.

Acceptance:

- User can click a failed rule and see the relevant geometry plus source calculation.

### F09 - Physical Envelope Review

Required:

- Toggle bare pipe geometry.
- Toggle insulation envelope.
- Toggle cladding envelope.
- Toggle clearance envelope.
- Toggle maintenance envelope.
- Toggle wind projected envelope.
- Show envelope source:
  - section OD,
  - insulation spec,
  - cladding spec,
  - route clearance,
  - rule clearance.

Acceptance:

- The viewer makes non-geometry attributes visible and auditable.

### F10 - Cost, Quantity, And Optimization Review

Required:

- Cost breakdown panel by:
  - route,
  - element,
  - system,
  - rack,
  - material,
  - cost code.
- Quantity overlays:
  - pipe length,
  - steel weight,
  - insulation volume,
  - insulation cost,
  - cladding quantity,
  - support count,
  - rack steel.
- Delta view:
  - before/after route cost,
  - before/after structure cost,
  - before/after clashes,
  - before/after rule violations.
- Heatmaps for high-cost or high-weight regions.

Acceptance:

- User can inspect why a route is expensive and whether the cost is pipe length, supports, insulation, or added structure.

### F11 - Rack And Support Review

Required:

- Show rack assemblies as first-class groups.
- Show rack bays, levels, lanes, members, attachment points.
- Show occupied/free pipe lanes.
- Show support-to-rack associations.
- Show load path from pipe support to rack member to column/base.
- Show member utilization when available.
- Show missing support attachment diagnostics.

Acceptance:

- User can identify which rack member receives which pipe support load.

### F12 - Solver Result Review

Required:

- Existing PyVista result plots remain available.
- Web viewer can load simplified overlays for:
  - displacement magnitude,
  - deformed shape,
  - stress utilization,
  - reaction vectors,
  - temperature,
  - support forces.
- Result overlays must identify source load case and result set.
- Deformation scale must be visible and adjustable.

Acceptance:

- Solver outputs can be reviewed next to clash/routing/physical attributes without losing object identity.

### F13 - Model Diff And Patch Review

Required:

- Load a `ModelPatch` or `AgentProposal`.
- Show added geometry in green/proposed style.
- Show removed geometry in red/removed style.
- Show modified objects with before/after comparison.
- Show semantic changes, not just geometry changes:
  - insulation assignment,
  - material change,
  - cost rate change,
  - support association,
  - route status.
- Approve, reject, or request revision.
- Export proposal report.

Acceptance:

- Generated geometry is never applied invisibly; it is reviewable before mutation.

### F14 - Agentic Review And Assistant Workflows

Required:

- Agent suggestions appear as proposals with explicit rationale.
- Viewer can show:
  - "why this route",
  - "what changed",
  - "risks",
  - "which constraints were active",
  - "which alternatives were rejected".
- Agent can create viewpoints and issue annotations.
- Agent can answer questions against selected scene data.
- Agent actions must be auditable:
  - input state,
  - proposed patch,
  - source metrics,
  - approval state.

Acceptance:

- User can compare agent-generated alternatives without trusting the agent blindly.

### F15 - IFC Integration

Required:

- Import IFC as external context where supported.
- Export Tuba objects with stable IDs and property sets.
- Preserve route, rack, insulation, cost, and clash metadata where possible.
- Map IFC GUIDs to `EntityRef`.
- Support external references in scene metadata.
- Do not require IFC roundtrip for internal route candidate review.

Acceptance:

- IFC coordination model can be exported and used in external BIM tools while Tuba remains the authoritative internal optimization model.

### F16 - BCF Issue Exchange

Required:

- Internal issue model compatible with BCF topic/viewpoint concepts.
- Export BCF for clashes and review comments.
- Import external BCF topics where object references can be mapped.
- Preserve comments, status, severity, viewpoint, and object selection.

Acceptance:

- A clash found in Tuba can become a coordination topic in external BIM review workflows.

### F17 - External Model Federation

Required:

- Multiple scene sources in one viewer:
  - Tuba model,
  - IFC context model,
  - point cloud,
  - equipment model,
  - existing plant model,
  - proposed route model.
- Source visibility toggles.
- Object source metadata.
- Coordinate transform metadata.
- Diagnostics for alignment uncertainty.

Acceptance:

- Tuba-generated routing can be reviewed against external plant/equipment context.

### F18 - Point Cloud And Field Context

Later-phase required:

- Load point cloud tiles or simplified point clouds.
- Clip point cloud with section box.
- Compare model geometry to scan context.
- Add field notes linked to position/object.
- Optional deviation markers.

Acceptance:

- Viewer can support retrofit and field verification workflows.

### F19 - Digital Twin And Operations State

Later-phase required:

- Attach operational status to objects:
  - active/inactive,
  - temperature,
  - pressure,
  - maintenance status,
  - inspection status,
  - sensor references.
- Time slider for historical states where data exists.
- Overlay alarm or inspection states.
- Link to asset IDs.

Acceptance:

- Tuba can evolve from design review into an operations-aware model navigator.

### F20 - Performance And Scalability

Required:

- Stable scene bundle format.
- Geometry caching by hash.
- Batching by material/layer where safe.
- Object picking metadata separated from mesh batching.
- Progressive loading for large assets.
- Spatial index for selection and issue focusing.
- LOD support.
- Optional web-worker loading and parsing.
- Benchmarks for:
  - scene build time,
  - bundle size,
  - viewer load time,
  - selection latency,
  - route overlay toggling,
  - issue focus time.

Acceptance:

- Viewer remains interactive on moderately large routed rack models.

### F21 - Export And Reporting

Required:

- Export scene bundle.
- Export screenshots from saved views.
- Export issue report.
- Export route review report.
- Export cost/quantity table from selected view.
- Export BCF topics.
- Export IFC coordination model.
- Export glTF/GLB geometry plus metadata sidecar.

Acceptance:

- Every visual review can produce a durable artifact for project communication.

### F22 - Developer Experience

Required:

- Python API for scene building.
- CLI command for exporting a scene bundle.
- Schema validation.
- Golden fixture tests.
- Small demo scenes.
- Clear optional dependency errors.
- Docs for adding a new overlay.
- Docs for adding a new renderer adapter.

Acceptance:

- A developer can add a new overlay without editing core routing, clash, or IFC code.

### F23 - Realtime Python And JSON Patch Preview

Required:

- File-watch mode for trusted local Python scripts.
- JSON `ModelPatch` watch mode.
- JSON `SceneDiff` stream for incremental viewer updates.
- Debounced rebuild on script save.
- Dry-run execution path that validates patches before applying them.
- Error overlay with Python exception, validation error, or patch diagnostic.
- Line/file reference where available.
- Hot reload without full browser refresh.
- Recompute affected geometry, physical envelopes, route reviews, clash issues, rule issues, and cost overlays where possible.
- Full scene rebuild fallback when diffing is not safe.
- Agent proposals use the same patch preview path.
- Explicitly defer YAML/DSL authoring until after Python and JSON patch workflows are proven.

Acceptance:

- Editing a trusted Python script can regenerate a scene bundle and hot reload the viewer.
- Editing a JSON `ModelPatch` can update the preview without mutating the committed model.
- Agent-generated JSON patches can be previewed with the same validation and diff machinery.
- Viewer shows diagnostics instead of silently failing on invalid scripts or patches.

### F24 - Agentic Python Workspace

Required:

- Persistent, sandboxed Python workspace for agents.
- Preloaded Tuba model, catalogs, scene builder, routing planner, clash engine, rule engine, quantity/cost modules, and spatial utilities.
- Stepwise execution model: one small Python cell per agent step.
- Feedback after each step:
  - stdout,
  - errors,
  - selected variable summaries,
  - generated `VisualizationScene` snapshots,
  - generated overlays,
  - route/cost/clash/rule diagnostics.
- `show_scene(scene)`, `show_overlay(...)`, or equivalent helpers for intermediate visual feedback.
- Safety checks before executing agent code.
- Read-only default model context with explicit patch output.
- Final agent output must be a schema-valid JSON `ModelPatch`, `RoutePlan`, or `AgentProposal`.
- Dry-run validation through `ModelTransaction`.
- `SceneDiff` preview before human approval.
- Execution trace stored with proposal provenance.
- Time, memory, filesystem, and network limits.
- No direct dependency on SpatialClaw code; use the pattern of a persistent code action interface.

Acceptance:

- An agent can explore a route problem through several Python steps without mutating the committed model.
- The workspace can return intermediate visual snapshots to the viewer.
- The final agent output is a reviewable JSON patch/proposal, not an untracked model mutation.
- Invalid or unsafe agent code is rejected with diagnostics.
- The proposal captures code cells, outputs, generated metrics, and patch provenance.

## Public Python Interfaces

Initial proposed APIs:

```python
from tuba.visualization import (
    VisualizationScene,
    SceneBuildOptions,
    build_visualization_scene,
    write_scene_bundle,
)

scene = build_visualization_scene(
    model,
    options=SceneBuildOptions(
        include_physical=True,
        include_insulation_envelopes=True,
        include_clearance_envelopes=True,
    ),
    routes=[route_result],
    clashes=[clash_report],
    rules=[rule_report],
    quantities=takeoff,
    solver_results=results,
)

write_scene_bundle(scene, "generated/review_scene")
```

Route review:

```python
scene = build_visualization_scene(
    model,
    route_reviews=[RouteReview.from_result(model, request, result)],
)
```

Agent proposal review:

```python
scene = build_visualization_scene(
    model,
    agent_proposals=[AgentProposal.from_patch(model, patch, rationale=...)],
)
```

BCF export:

```python
from tuba.visualization.bcf import write_bcf

write_bcf(scene.issues, scene.views, "generated/tuba_issues.bcfzip")
```

## Realtime Authoring Strategy

The first realtime workflow should use Python and JSON only.

### Python Script Watch Mode

Python remains the expressive authoring surface for humans and advanced agents:

```python
from tuba import TubaModel
from tuba.visualization import build_visualization_scene, write_scene_bundle

model = TubaModel()
model.add_insulation_spec("mw_50", material="mineral_wool", thickness_m=0.05)

# Build rack modules, route plans, attributes, and patches here.

scene = build_visualization_scene(model)
write_scene_bundle(scene, "generated/live_scene")
```

Watcher behavior:

```text
save script
  -> execute trusted local script in dry-run preview mode
  -> validate produced model, patch, or scene
  -> write scene bundle or scene diff
  -> hot reload viewer
```

### JSON Patch Watch Mode

Agents and APIs should prefer JSON `ModelPatch` payloads:

```json
{
  "op": "assign_attribute",
  "target": "element:pipe_0",
  "key": "insulation",
  "value": "mw_50"
}
```

Patch preview behavior:

```text
patch JSON
  -> schema validation
  -> dry-run transaction
  -> recompute affected derived data
  -> emit SceneDiff
  -> viewer updates changed objects and overlays
```

### YAML / Mermaid-Style DSL

YAML is explicitly deferred.

Reasons:

- It would become a weak programming language once racks, route constraints, catalogs, loops, variables, and reusable modules are needed.
- Python already handles procedural generation well.
- JSON patches are better for agents because they are explicit, schema-validatable, easy to diff, and safe to review.
- A small YAML/template layer can be added later only if a clear non-programmer use case appears.

## Agentic Python Workspace Pattern

The SpatialClaw pattern is useful for Tuba: code is the flexible action interface, but final changes still need structured review. Tuba should adopt the pattern, not the repository as a product dependency.

Target loop:

```text
agent receives task, model summary, and available APIs
  -> writes one small Python cell
  -> sandbox executes cell in persistent workspace
  -> workspace returns stdout, errors, variable summaries, and scene snapshots
  -> agent writes next cell or revises strategy
  -> agent emits JSON ModelPatch / RoutePlan / AgentProposal
  -> dry-run validate
  -> emit SceneDiff
  -> human reviews and approves
```

Preloaded workspace modules:

- `TubaModel` and `EntityRef`.
- `ModelPatch` and `ModelTransaction`.
- route planners and route cost models.
- clash and rule engines.
- quantity and load-path helpers.
- `build_visualization_scene()`.
- spatial math helpers such as vector operations, KD-trees, nearest-neighbor queries, and bounding boxes.
- viewer feedback helpers such as `show_scene()` and `show_route_candidates()`.

Rules:

- Agent code may inspect and compute freely inside the sandbox.
- Agent code must not mutate the committed model directly.
- Long-running route searches must have limits and cancellation.
- External file/network access is disabled by default.
- Every final proposal must include rationale, metrics, diagnostics, and a patch.
- The viewer shows intermediate snapshots as temporary analysis artifacts, not committed model state.

## Scene Bundle Format

Initial local bundle:

```text
review_scene/
  scene.json
  metadata/
    objects.json
    overlays.json
    issues.json
    route_reviews.json
    agent_proposals.json
  geometry/
    model.glb
    envelopes.glb
    routes.glb
    markers.glb
  snapshots/
    issue_001.png
```

Rules:

- `scene.json` references all assets with relative URIs.
- All selectable geometry must map back to `SceneObject.id`.
- All `SceneObject.id` values must map back to `EntityRef` unless the object is purely visual.
- Bundles must be deterministic enough for tests where inputs are deterministic.

## Renderer Strategy

### Phase 1 Renderer

Use a lightweight web viewer with Three.js or a small BIM viewer wrapper. It must load local scene bundles and support core interaction.

### BIM-Scale Renderer Options

Add adapters later for:

- xeokit XKT when BIM-scale selection and metadata are the priority.
- That Open Fragments when IFC-to-fragments workflows are preferred.
- vtk.js when scientific/VTK-style result visualization is preferred.

The scene contract must not depend on any single renderer.

## IFC Strategy

IFC remains an exchange adapter.

Internal:

- `TubaModel`
- `EntityRef`
- `VisualizationScene`
- `ClashReport`
- `RouteReview`
- `AgentProposal`

External:

- IFC objects and property sets.
- IFC GUID references.
- BCF topics/viewpoints.

Mapping requirements:

- Tuba `EntityRef` to IFC GUID where exported.
- IFC GUID to external scene object where imported.
- Property sets for insulation, route ID, rack ID, cost code, quantity, and issue references.

## Security And Safety

Required:

- Scene bundles are data files, not executable scripts.
- Web viewer must not execute untrusted inline script from scene data.
- External model metadata must be escaped before display.
- File paths in scene bundles must be relative unless explicitly trusted.
- Agent proposals must require explicit approval before mutation.
- Python live preview must run only from trusted local files and must not be embedded in scene bundles.
- JSON patches and scene diffs must be schema-validated before the viewer applies them.
- Agentic Python workspace execution must be sandboxed and must store an audit trace for proposals.

## Accessibility And Usability

Required:

- Keyboard-accessible object tree and issue list.
- High-contrast clash and selection colors.
- Non-color indicators for issue severity.
- Search and filter controls usable without precise mouse interaction.
- Measurement and property values copyable as text.

## Diagnostics

Every scene build can include diagnostics:

- Missing optional dependency.
- Failed mesh generation.
- Missing section profile.
- Unsupported obstacle geometry.
- Missing entity ref.
- Missing IFC mapping.
- Route candidate invalid reason.
- Clash engine limitation.
- Unavailable solver result.
- Large-scene performance warning.

Diagnostics must be visible in the viewer and serializable in reports.

## Acceptance Criteria

### Architecture Acceptance

- `VisualizationScene` exists and can represent model objects, geometry assets, metadata, overlays, issues, route reviews, and agent proposals.
- Current PyVista scene builders can be adapted to consume or produce the semantic scene.
- Web viewer can load a generated scene bundle.
- Geometry and metadata are separated but connected by stable IDs.
- Route alternatives, clash issues, and physical envelopes can be visualized from the same scene contract.

### Product Acceptance

- User can select a pipe and inspect insulation material, thickness, effective OD, mass per meter, wind diameter, cost per meter, route ID, and clashes.
- User can compare at least two route alternatives visually and numerically.
- User can focus a clash issue and see involved objects and viewpoint.
- User can toggle insulation and clearance envelopes.
- User can load an agent proposal and inspect proposed adds/removes/modifications before applying it.
- User can edit a trusted local Python script or JSON patch and see a validated preview update.
- Agent can iteratively explore a spatial/routing problem in a sandboxed Python workspace and produce a reviewable proposal.
- User can export a review bundle and screenshot.

### Interoperability Acceptance

- Scene objects can carry IFC GUIDs when available.
- BCF-compatible issue export exists for clash/rule issues.
- glTF/GLB export preserves object identity through metadata sidecar.
- IFC is not required to build, route, clash, or review a Tuba-native scene.

### Performance Acceptance

Initial benchmark targets must be measured and then tightened:

- Build a scene from a moderate demo rack model in under 5 seconds on the development machine.
- Load a moderate scene bundle in the browser in under 5 seconds on the development machine.
- Selection feedback under 100 ms for moderate scenes.
- Toggle route/clash overlays under 250 ms for moderate scenes.
- Apply a small `SceneDiff` in the viewer under 250 ms for moderate scenes.

These are first targets, not final product guarantees.

## Test Plan

### Unit Tests

- Scene object serialization.
- Geometry asset references.
- Entity ref mapping.
- Metadata validation.
- Physical property projection into scene object metadata.
- Overlay serialization.
- Issue serialization.
- Route review serialization.
- Agent proposal serialization.
- Scene diff serialization.
- Agent workspace session and execution trace serialization.
- BCF mapping helpers.

### Integration Tests

- Build scene from simple model.
- Build scene with insulation envelope.
- Build scene with clash report.
- Build scene with route candidates.
- Build scene with quantity/cost data.
- Build scene with rule diagnostics.
- Export scene bundle and validate file layout.
- Export glTF/metadata and verify object IDs.
- Generate a scene diff from a small patch and validate changed object IDs.
- Execute a safe agent workspace cell and capture stdout, variable summaries, and scene snapshot references.

### Viewer Tests

- Load fixture scene.
- Select object and show property panel.
- Toggle layers.
- Focus issue.
- Toggle route candidates.
- Apply filters.
- Restore saved view.
- Verify nonblank canvas screenshot.
- Hot reload fixture scene from a JSON scene diff.
- Show an agent intermediate scene snapshot without committing it.

### Regression Tests

- Existing PyVista visualization tests still pass.
- Existing routing visualization tests still pass until replaced or migrated.
- Existing IFC, clash, physical, routing, rules, and quantity tests remain green.

### Manual Demo Tests

- Insulated pipe route around obstacle.
- Detour versus added structure cost comparison.
- Rack lane occupancy.
- Clash issue export to BCF.
- Agent proposal with before/after diff.
- Live Python script preview.
- JSON patch preview with validation error overlay.
- Agentic Python workspace producing a patch from iterative cells.
- Solver stress overlay plus route/clash context.

## Workpackage Summary

Detailed workpackages live in `.agents/TODOS/visualization-engine-workpackages.md`.

High-level phases:

1. Scene contract and schema.
2. Semantic scene builder.
3. Geometry bundle export.
4. Web viewer MVP.
5. Route review.
6. Clash/rule issue review.
7. Physical/cost/load overlays.
8. Patch and agent proposal review.
9. IFC/BCF exchange.
10. Realtime Python and JSON patch preview.
11. Agentic Python workspace.
12. Performance, federation, point clouds, and digital twin extensions.

## Open Questions

- Should the first web viewer be plain Three.js, xeokit, or That Open Fragments?
- Should scene bundles be generated under `generated/` by default or only via explicit path?
- Should viewer code live inside this repository or a separate package/workspace?
- What is the first target browser/runtime?
- Which object hierarchy should be primary in the tree: Tuba groups, routes, systems, or IFC hierarchy?
- Should BCF be implemented before or after the internal issue UI?
- Which demo model should become the golden visualization acceptance fixture?
- How much authoring should the viewer support in phase 1 versus review-only interactions?
- What sandbox restrictions are required for local Python preview in shared environments?
- Which sandbox/runtime should host the agentic Python workspace?
- Which workspace helper APIs should be preloaded first for routing and clash review?
- What is the minimal `SceneDiff` shape needed before optimizing partial recomputation?
