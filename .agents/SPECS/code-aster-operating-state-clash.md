# Code_Aster Operating-State Clash And Result Workflow Spec

## Purpose

Define the complete Tuba workflow for using Code_Aster results as first-class engineering state: mesh provenance, solver execution, result persistence, deformed geometry, operating-state clash detection, route scoring, load transfer, visualization, IFC/BCF coordination, and agent review.

The core requirement is to detect and explain clashes that do not exist in cold geometry but appear after thermal expansion, gravity sag, pressure, support movement, nonlinear contact, or imposed displacement.

## Summary Recommendation

Code_Aster remains the core solver. Tuba should not build a parallel solver path. Instead, Tuba needs a traceable result-state layer between Code_Aster and downstream workflows.

```text
TubaModel cold design
  -> AnalysisStudy
  -> AnalysisMesh with source mapping
  -> Code_Aster solve
  -> FEAResults in memory
  -> ResultState for persistence and traceability
  -> GeometryState for cold / operating / deformed states
  -> DeformedEnvelope cache
  -> clash, routing, load path, visualization, IFC/BCF
```

Important distinction:

- Visual deformation can be exaggerated for review.
- Physical clash detection must use actual displacement, normally scale `1.0`.
- Conservative checks should use an explicit safety factor, not a visual deformation factor.

## Existing Starting Point

Current capabilities in the repository:

- `CodeAsterSolver` exports `.mail`, `.comm`, and `.export` files.
- The solver adapter handles pipe, bend, beam, bar, cable, rectangular, and I-beam-like elements.
- Pipe bends are discretized into generated intermediate mesh nodes and segment elements.
- The Code_Aster command file writes `DEPL`, `SIEQ_ELNO`, `EFFO_ELNO`, and `FORC_NODA`.
- `FEAResults` stores node displacements, reactions, element forces, and stresses.
- The visualizer already warps meshes by `DEPL`.
- The legacy `PipingCollisionChecker` already has a deformed-collision path.
- The newer visualization engine already creates solver-result overlays.
- Routing objectives can optionally penalize deformed clashes.

Main gaps:

- Code_Aster generated mesh nodes and segment elements are not persisted as a traceable analysis mesh.
- Generated bend-node displacements are not a first-class result source.
- Deformed geometry exists as visualization behavior, not reusable engineering state.
- The structured clash engine checks cold native element centerlines against obstacles only.
- Load-case-specific operating clashes are not distinguished from cold clashes.
- Route scoring does not consistently use the newer structured clash/report model.
- IFC/BCF exports do not yet carry operating-state issue semantics.

## Non-Goals

- Do not replace Code_Aster.
- Do not require Code_Aster execution in unit tests or CI.
- Do not make visual deformation scale affect engineering clash decisions.
- Do not mutate `TubaModel` when creating result states or deformed envelopes.
- Do not serialize heavy deformed meshes as authoritative model data.
- Do not solve full coupled pipe-plus-rack nonlinear behavior in the first package.
- Do not require IFC export/import to perform operating-state clash checks.

## Domain Concepts

### Cold Geometry

The installed/as-modeled geometry from `TubaModel`: native nodes, elements, supports, obstacles, racks, and semantic envelopes.

### Analysis Study

The immutable solver-input package for one model revision, solver backend, and load case.

```python
@dataclass(frozen=True)
class AnalysisStudy:
    id: str
    model_revision: int
    solver_name: str
    load_case: str
    work_dir: str | None
    input_files: dict[str, str]
    mesh_id: str
    metadata: dict[str, Any] = field(default_factory=dict)
```

### Analysis Mesh

The Code_Aster mesh as generated from the native model.

```python
@dataclass(frozen=True)
class AnalysisMesh:
    id: str
    model_revision: int
    solver_name: str
    nodes: dict[str, tuple[float, float, float]]
    elements: dict[str, tuple[str, ...]]
    groups: dict[str, tuple[str, ...]]
    node_sources: dict[str, MeshNodeSource]
    element_sources: dict[str, MeshElementSource]
    files: dict[str, str] = field(default_factory=dict)
```

`AnalysisMesh` is the missing link for accurate deformed bends. Native Tuba may have one bend element, while Code_Aster may solve it as many segment elements with generated nodes.

### Mesh Source Records

```python
@dataclass(frozen=True)
class MeshNodeSource:
    node_id: str
    source_ref: EntityRef
    role: str                       # native_node, generated_bend_node, support_node
    parametric_t: float | None = None
    segment_index: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
```

```python
@dataclass(frozen=True)
class MeshElementSource:
    element_id: str
    source_ref: EntityRef
    role: str                       # native_element, bend_segment, discrete_support
    segment_index: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
```

### Result State

Serializable solver result for one study and one model revision.

```python
@dataclass(frozen=True)
class ResultState:
    id: str
    study_id: str
    model_revision: int
    solver_name: str
    load_case: str
    mesh_id: str | None
    node_displacements: dict[str, tuple[float, float, float, float, float, float]]
    node_reactions: dict[str, tuple[float, float, float, float, float, float]]
    element_results: dict[str, dict[str, Any]]
    files: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
```

`FEAResults` remains the in-memory convenience object. `ResultState` is the persistent and traceable result object used for downstream workflows.

### Geometry State

Named view of the model geometry under a physical state.

```python
@dataclass(frozen=True)
class GeometryState:
    id: str
    model_revision: int
    state_type: str                 # cold, operating, deformed, construction, preview
    load_case: str | None = None
    result_state_id: str | None = None
    displacement_scale: float = 1.0
    safety_factor: float = 1.0
    purpose: str = "engineering"    # engineering, visualization, preview
    metadata: dict[str, Any] = field(default_factory=dict)
```

Rules:

- `purpose="engineering"` defaults to displacement scale `1.0`.
- `purpose="visualization"` may use an exaggerated scale.
- Clash checks must reject a visualization geometry state unless explicitly overridden.

### Deformed Envelope

Derived clash/routing geometry for one entity under one geometry state.

```python
@dataclass(frozen=True)
class DeformedEnvelope:
    entity: EntityRef
    geometry_state_id: str
    envelope_type: str              # bare, insulation, clearance, maintenance, wind
    polyline: tuple[tuple[float, float, float], ...]
    radius_m: float
    bounds: tuple[float, float, float, float, float, float]
    source_mesh_elements: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
```

This is derived data. It can be cached, but it is not authoritative model geometry.

### Operating Clash

Structured clash result with cold and operating state context.

Required metadata:

- `geometry_state_id`
- `load_case`
- `envelope_type`
- `cold_distance_m`
- `operating_distance_m`
- `introduced_by_deformation`
- `displacement_source`
- `safety_factor`
- involved `EntityRef` values
- optional IFC GUIDs

## Tuba Workflow Integration

### 1. Scripted Model Generation

Agents or Python scripts generate the cold `TubaModel`:

- pipe centerlines
- bends
- supports
- rack assemblies
- insulation specs
- obstacles
- load cases
- routing metadata
- cost attributes

No solver result is required at this stage.

### 2. Cheap Pre-Solver Checks

Before Code_Aster:

- schema validation
- native cold clash check
- envelope clash check
- route cost proxy
- support spacing rules
- constructability rules
- missing support diagnostics

This filters obviously invalid candidates before expensive solver runs.

### 3. Code_Aster Study Export

`CodeAsterSolver.export_study()` should produce:

- `study.mail`
- `study.comm`
- `study.export`
- `study_manifest.json`

The manifest contains:

- `AnalysisStudy`
- `AnalysisMesh`
- mesh node source map
- mesh element source map
- Code_Aster groups
- solver backend metadata
- model revision
- load case
- generated file paths

This export path must be testable without running Code_Aster.

### 4. Code_Aster Solve

`CodeAsterSolver.solve()` runs as it does today:

- WSL or Docker execution
- `.rmed` result output
- CSV tables for `DEPL`, `EFFO_ELNO`, `FORC_NODA`, `SIEQ_ELNO`
- parser returns `FEAResults`

Future enhancement:

- capture generated mesh-node result rows, not only native node IDs.
- parse MED result fields when CSV tables omit generated mesh data.

### 5. Result State Creation

Convert `FEAResults` into `ResultState`:

```python
result_state = result_state_from_fea_results(
    model=model,
    study=study,
    analysis_mesh=analysis_mesh,
    results=fea_results,
)
```

This step:

- stores native node displacements.
- stores generated mesh node displacements if available.
- stores reactions.
- stores element forces and stresses.
- records result files.
- validates model revision.

### 6. Geometry State Creation

Create physical operating state:

```python
operating = GeometryState(
    id="geometry_state:hot:physical",
    model_revision=model.revision,
    state_type="operating",
    load_case="Hot",
    result_state_id=result_state.id,
    displacement_scale=1.0,
    safety_factor=1.0,
    purpose="engineering",
)
```

Create visual review state separately:

```python
visual = GeometryState(
    id="geometry_state:hot:visual_x50",
    model_revision=model.revision,
    state_type="deformed",
    load_case="Hot",
    result_state_id=result_state.id,
    displacement_scale=50.0,
    purpose="visualization",
)
```

### 7. Deformed Envelope Build

Build centerline/envelope representation:

- for straight native elements, use native endpoints plus solver displacements.
- for bends, prefer generated mesh nodes from `AnalysisMesh` and `ResultState`.
- for missing generated results, fall back to interpolation and emit diagnostics.
- for insulation, add insulation thickness to radius.
- for clearance, add clearance to effective radius.
- for wind, use wind envelope policy.
- for supports/racks, use solved displacements if they were included in the study, otherwise use cold geometry with diagnostics.

### 8. Operating Clash Check

Structured clash engine should accept:

```python
engine.check_model(
    model,
    geometry_state=operating,
    result_state=result_state,
    envelope_type="clearance",
)
```

It returns cold and operating comparisons:

- cold hard clash
- cold clearance clash
- operating hard clash
- operating clearance clash
- operating-only clash
- resolved-by-deformation clearance improvement

### 9. Route Scoring

Routing remains two-stage:

1. proxy scoring for many candidates:
   - cold clash
   - route length
   - support count
   - envelope clearance
   - approximate expansion allowance

2. Code_Aster scoring for top candidates:
   - stress objective
   - deflection objective
   - support reaction objective
   - operating clash objective
   - load path/rack utilization objective

No route grid expansion should call Code_Aster.

### 10. Visualization

Viewer should show:

- cold geometry
- physical operating envelope
- exaggerated visual deformed shape
- stress overlay
- displacement vectors
- reaction vectors
- load path vectors
- operating-only clash issues
- load-case selector
- geometry-state selector

The UI must make visual scale obvious and must not imply that visual scale is engineering scale.

### 11. IFC/BCF Coordination

IFC export:

- cold/as-designed geometry remains primary.
- optional property sets can include operating-state displacement/stress/reaction summaries.
- deformed geometry should not replace as-designed geometry unless exporting a special review model.

BCF export:

- operating-only clashes become BCF topics.
- topic title should include load case.
- topic metadata should include geometry state and cold/operating distances.
- viewpoints should focus on operating clash location.
- involved IFC GUIDs should be included when available.

## Code_Aster Mesh Provenance Requirements

### Native Node Mapping

Every native node written to `.mail` must map to:

```json
{
  "mesh_node": "N12",
  "source_ref": "node:N12",
  "role": "native_node"
}
```

### Bend Node Mapping

Every generated bend node must map to:

```json
{
  "mesh_node": "pipe_bend_0_n3",
  "source_ref": "element:pipe_bend_0",
  "role": "generated_bend_node",
  "parametric_t": 0.1875,
  "segment_index": 3
}
```

### Bend Segment Mapping

Every bend segment must map to:

```json
{
  "mesh_element": "pipe_bend_0_s3",
  "source_ref": "element:pipe_bend_0",
  "role": "bend_segment",
  "segment_index": 3
}
```

### Support Mapping

Every support node group must map to:

```json
{
  "group": "GN_N12",
  "source_ref": "support:support_0",
  "node_ref": "node:N12"
}
```

### Rack/Structure Mapping

Beam, column, bar, and cable mesh elements must map to native structural elements and, where available, assembly membership.

## Deformed Geometry Projection Rules

### Straight Elements

If only endpoint displacements are available:

```text
p(t) = p0 + t * (p1 - p0)
u(t) = u0 + t * (u1 - u0)
p_deformed(t) = p(t) + u(t) * displacement_scale * safety_factor
```

### Bend Elements

Preferred:

- use generated mesh nodes along the bend.
- apply each generated node displacement.
- build deformed polyline from those points.

Fallback:

- use existing bend geometry generator.
- interpolate endpoint displacements.
- emit diagnostic: `bend_displacement_interpolated`.

### Rotations

Initial engineering clash can use translational centerline displacement only.

Future enhancement:

- use rotations to update local cross-section orientation for exact swept solids.
- required for very large rotations or non-circular support components.

### Supports And Rack Members

If rack/support structure is part of the Code_Aster study:

- use its result displacements.

If not:

- keep rack/support cold.
- check pipe operating envelope against cold structure.
- record diagnostic: `target_structure_not_solved`.

## Clash Detection Requirements

### Broadphase

Use AABB envelopes for:

- cold pipe envelopes
- operating pipe envelopes
- insulation envelopes
- clearance envelopes
- rack members
- support components
- obstacles
- external IFC context geometry

Broadphase must be state-aware:

```text
cache key = model_revision + geometry_state_id + envelope_type + clearance
```

### Narrowphase

Initial implementation:

- segment/capsule to AABB distance for cuboid obstacles.
- capsule/capsule approximation for pipe/support/rack members.
- trimesh narrowphase only when needed and available.

Future implementation:

- exact swept solid or section-aware collision for non-circular structural members.

### Clash Classification

Operating-state clash classifications:

- `cold_hard`
- `cold_clearance`
- `operating_hard`
- `operating_clearance`
- `operating_only_hard`
- `operating_only_clearance`
- `resolved_in_operating`

### Result Fields

Structured clash result must include:

```json
{
  "left": "element:pipe_0",
  "right": "obstacle:box_0",
  "severity": "operating_hard",
  "load_case": "Hot",
  "geometry_state": "geometry_state:hot:physical",
  "cold_distance_m": 0.04,
  "operating_distance_m": -0.01,
  "penetration_m": 0.01,
  "introduced_by_deformation": true,
  "location": [1.2, 0.5, 0.0],
  "envelope_type": "insulation",
  "safety_factor": 1.0
}
```

## Performance Requirements

### Avoid Solver In Inner Loops

Route optimization should not call Code_Aster for every candidate expansion. Use:

- static envelope checks.
- approximate expansion allowances.
- support spacing heuristics.
- proxy stress/deflection heuristics.
- Code_Aster only for shortlisted candidates.

### Cache Derived Geometry

Cache:

- analysis mesh source mapping.
- result-state lookup arrays.
- deformed polylines.
- deformed AABBs.
- deformed envelopes.
- clash broadphase indexes.

Invalidate by:

- model revision.
- result state ID.
- geometry state ID.
- envelope type.
- clearance/safety factor.

### Use Array-Oriented Data

For large models:

- store node coordinates in arrays for projection.
- store displacements in aligned arrays.
- vectorize deformed AABB computation.
- avoid Python object traversal in hot loops.

### Benchmark Targets

Initial developer-hardware gates:

- build deformed envelopes for 10,000 straight elements under 2 seconds.
- build deformed bend envelopes for 1,000 bend elements under 2 seconds.
- operating clash broadphase for 10,000 elements and 1,000 obstacles under 3 seconds.
- result-state conversion for 10,000 nodes under 1 second.
- relationship from operating clash to scene issue under 10 ms per issue.

These are starting targets and can be adjusted after real plant-scale fixtures exist.

## APIs

### Study Export

```python
study = solver.export_study(
    model,
    load_case_name="Hot",
    output_dir=path,
    include_manifest=True,
)
```

Backwards compatibility:

- current callers expecting a `Path` should remain supported.
- new API may add `export_analysis_study()` instead of changing return type.

Preferred additive API:

```python
study = solver.export_analysis_study(model, "Hot", output_dir)
```

### Result Conversion

```python
result_state = result_state_from_fea_results(
    model=model,
    study=study,
    results=results,
)
```

### Geometry State

```python
operating = create_operating_geometry_state(
    model=model,
    result_state=result_state,
    load_case="Hot",
    safety_factor=1.0,
)
```

### Envelopes

```python
envelopes = build_deformed_envelopes(
    model=model,
    result_state=result_state,
    geometry_state=operating,
    envelope_type="insulation",
)
```

### Clash

```python
report = TrimeshClashEngine().check_model(
    model,
    geometry_state=operating,
    result_state=result_state,
    envelope_type="insulation",
    clearance_m=0.0,
)
```

### Visualization

```python
scene = build_visualization_scene(
    model,
    solver_results=results,
    result_states=[result_state],
    geometry_states=[operating],
    operating_clashes=report,
)
```

## File Layout

Proposed modules:

```text
tuba/analysis/
  __init__.py
  study.py
  mesh.py
  results.py
  states.py
  projection.py

tuba/geometry/
  states.py
  envelopes.py
  deformed.py

tuba/clash/
  operating.py
```

Solver integration:

```text
tuba/solver/aster.py
  export_analysis_study()
  _write_mail(..., provenance_recorder=...)
  _parse_results(..., analysis_mesh=...)
```

Visualization integration:

```text
tuba/visualization/builders.py
  result_states=
  geometry_states=
  operating_clash_results=
```

## Acceptance Criteria

- Existing tests pass.
- Existing `CodeAsterSolver.export_study()` behavior remains compatible.
- Export-only Code_Aster tests do not require Code_Aster installation.
- Study manifest records all generated bend mesh nodes and segment elements.
- `FEAResults` converts to `ResultState`.
- `ResultState` roundtrips through JSON.
- Deformed envelopes are built with physical scale `1.0`.
- Visualization can use exaggerated scale without affecting clash checks.
- A fixture with no cold clash produces an operating clash after displacement.
- Operating clash result includes cold distance, operating distance, load case, and geometry state.
- Routing objective can penalize operating clashes.
- Visualization scene can show operating-only clash issues.
- BCF export can include operating-state issue metadata.

## Test Plan

### Unit Tests

- analysis study serialization.
- analysis mesh source mapping.
- result state conversion.
- geometry state validation.
- deformed envelope projection.
- bend generated-node projection.
- fallback interpolation diagnostics.
- operating clash classification.
- cache key correctness.

### Integration Tests

- Code_Aster export-only study with straight pipe.
- Code_Aster export-only study with bend.
- mock `FEAResults` to result state.
- hot geometry envelope from mock displacement.
- cold no-clash / hot clash fixture.
- routing objective operating clash score.
- visualization scene includes geometry state and operating clash issue.
- BCF topic includes load case and state metadata.

### Performance Tests

- deformed envelope build smoke.
- operating broadphase smoke.
- result state conversion smoke.
- cache reuse check.

## Example Scenario

1. Pipe has 50 mm insulation.
2. Cold clearance to rack beam is 20 mm.
3. Hot load case displaces the pipe 35 mm toward rack beam.
4. Cold clash check passes.
5. Operating clash check reports 15 mm penetration.
6. Viewer shows:
   - cold pipe
   - operating envelope
   - exaggerated visual deformation
   - clash marker
   - load case `Hot`
   - issue: `operating_only_hard`
7. Route optimizer ranks an alternative route or support concept based on the operating clash penalty.

## Open Questions

1. Should `AnalysisStudy` be stored inside `TubaModel` or beside it as an external artifact?
2. Should result states be JSON only, or should large fields support compressed NumPy arrays later?
3. Should physical support components be included in the first coupled Code_Aster study or treated as cold collision objects initially?
4. Should nonlinear contact results have separate geometry states per time step/increment?
5. Should operating clash checks consider rotations in the first version or only translational displacement?
6. Should IFC export include optional deformed review geometry, or only property sets and BCF viewpoints?
