# Clash Detection And IFC Spec

## Purpose

Provide a durable clash detection architecture for Tuba that supports scripted geometry generation, modular rack construction, insulation and clearance envelopes, smart pipe routing, deformed-state checks, reports, and IFC exchange.

The goal is not to replace professional BIM coordination tools. The goal is to give Tuba a deep clash module with a small interface that routing, optimization, visualization, solver-loop scoring, and reports can share.

## Summary Recommendation

Tuba should own its clash interface and internal clash engine. IFC should be an adapter at the seam, not the primary interface.

The internal clash module answers local engineering questions quickly and deterministically. IFC remains the exchange adapter for external coordination, review, and roundtrip workflows.

## Non-Goals

- Do not build a full Navisworks/Solibri replacement in the first phase.
- Do not require IFC export/import to check every route candidate.
- Do not require external BIM software for CI.
- Do not require exact CAD-kernel solids for the first internal engine.
- Do not treat a routing occupancy grid as the final engineering clash result.
- Do not certify automatic route acceptance without engineer review.

## Existing Starting Point

Current internal functionality:

- `tuba.geometry.collision.PipingCollisionChecker` creates pipe cylinder meshes and checks them against obstacles.
- `tuba.routing.grid.RoutingGrid` performs coarse routing occupancy with OD, insulation thickness, and clearance.
- `tuba.routing.network.detect_candidate_conflicts()` checks route candidate centerline conflicts.
- `tuba.routing.objectives.ClashObjective` can score collisions.

Current IFC functionality:

- `tuba.external.ifc.IfcExporter` exports pipes, bends, beams, supports, obstacles, and stress/support property sets.
- `tuba.external.ifc.IfcImporter` imports a simplified model from IFC products.
- IFC tests validate basic roundtrip behavior.

Known gaps:

- Collision results only return element IDs, not obstacle IDs, distances, severity, or envelope source.
- Pipe radius does not yet derive from a typed physical envelope that includes insulation/cladding.
- Bends are simplified as straight cylinders between nodes.
- IFC export currently swallows some geometry errors.
- IFC import simplifies geometry and does not preserve full Tuba semantics.
- Routing grid, collision checker, and network conflict detection use different representations.

## Architecture

### Modules

#### `tuba.clash.types`

Owns public result and request dataclasses.

Required types:

```python
@dataclass(frozen=True)
class ClashEnvelope:
    target: EntityRef
    radius_m: float
    source: str
    includes: tuple[str, ...]
```

```python
@dataclass(frozen=True)
class ClashCheckConfig:
    clearance_m: float = 0.0
    include_insulation: bool = True
    include_cladding: bool = True
    include_deformed_state: bool = False
    deformation_scale: float = 1.0
    check_pipe_to_obstacle: bool = True
    check_pipe_to_pipe: bool = True
    check_pipe_to_structure: bool = True
    check_supports: bool = False
    tolerance_m: float = 1e-6
```

```python
@dataclass(frozen=True)
class ClashPair:
    left: EntityRef
    right: EntityRef
```

```python
@dataclass
class ClashResult:
    pair: ClashPair
    status: Literal["clash", "clearance_violation", "touching", "clear"]
    distance_m: float | None
    required_clearance_m: float
    penetration_m: float | None
    point_left: Point3D | None = None
    point_right: Point3D | None = None
    severity: Literal["hard", "soft", "info"] = "hard"
    diagnostics: list[str] = field(default_factory=list)
```

```python
@dataclass
class ClashReport:
    config: ClashCheckConfig
    results: list[ClashResult]
    diagnostics: list[str] = field(default_factory=list)
```

#### `tuba.clash.envelopes`

Computes physical clash envelopes from model geometry plus typed attributes.

Responsibilities:

- Pipe bare radius from section OD.
- Insulation thickness and cladding thickness from attributes/specs.
- Clearance allowance from config or route request.
- Optional deformed node coordinates from solver results.
- Consistent axis conventions.

The interface must hide where insulation data comes from. Callers should not know whether it was stored on a route request, element, line group, or assembly.

#### `tuba.clash.engine`

Owns the abstract clash engine seam.

Required interface:

```python
class ClashEngine(Protocol):
    def check_model(
        self,
        model: TubaModel,
        *,
        config: ClashCheckConfig | None = None,
        results: FEAResults | None = None,
    ) -> ClashReport:
        ...
```

#### `tuba.clash.trimesh_engine`

First internal adapter, based on existing `PipingCollisionChecker`.

Responsibilities:

- Reuse `trimesh.collision.CollisionManager`.
- Build pipe, insulation, and cladding envelopes as cylinders or swept approximations.
- Load cuboid/cylinder/mesh obstacles.
- Report element and obstacle refs.
- Preserve diagnostics instead of returning only IDs.
- Support deformed-state checks from `FEAResults`.

#### `tuba.clash.grid_adapter`

Lightweight adapter for routing-time occupancy.

Responsibilities:

- Use the same envelope computation as `tuba.clash.envelopes`.
- Produce blocked/penalty cells for routing.
- Stay approximate and fast.
- Never claim final engineering clash acceptance.

#### `tuba.clash.ifc_adapter`

Exchange and optional external review adapter.

Responsibilities:

- Export Tuba clash geometry and metadata into IFC property sets.
- Import external clash issue references if available.
- Support optional BCF issue export later.
- Map IFC product IDs back to Tuba `EntityRef`.

This adapter should not be called by every route search step.

#### `tuba.clash.filters`

Owns rules for allowed contacts and ignored pairs.

Examples:

- Pipe endpoint tying into a nozzle is not a clash.
- Pipe resting on its assigned support is not a clash.
- Shared endpoint between connected pipe segments is not a clash.
- Clearance violation can be a soft result if the pair is in an allowed installation zone.

## Data Model Requirements

### Entity References

Every clash result must identify entities by stable refs:

- `element:pipe_str_0`
- `obstacle:equipment_box`
- `support:support_id`
- `group:rack_A`
- `assembly:rack_bay_01`
- `route:P-100`

If support IDs do not exist yet, the first phase may use `support:<index>` with a clear migration note.

### Insulation And Cladding

Insulation should not be only a routing constraint. It should be a physical attribute or spec:

```python
InsulationSpec(
    id="mw_50_al_08",
    material="mineral_wool",
    thickness_m=0.05,
    density_kg_m3=120.0,
    cladding_material="aluminium",
    cladding_thickness_m=0.0008,
    cladding_density_kg_m3=2700.0,
)
```

The clash envelope for a pipe should be:

```text
bare_radius
+ insulation_thickness
+ cladding_thickness
+ required_clearance
```

The same spec should later feed:

- Weight per meter.
- Wind projected diameter.
- Cost per meter.
- IFC property sets.
- BOM quantities.

## Interfaces

### Public Use

Expected public use:

```python
from tuba.clash import ClashCheckConfig, TrimeshClashEngine

report = TrimeshClashEngine().check_model(
    model,
    config=ClashCheckConfig(clearance_m=0.05, include_insulation=True),
)

hard_clashes = [r for r in report.results if r.severity == "hard"]
```

### Routing Use

Routing should depend on the clash envelope module, not on IFC:

```python
envelope = envelope_provider.for_pipe_request(model, request)
grid = RoutingGrid.from_model(model, request, grid_spec, envelope_provider=envelope_provider)
```

### Solver Loop Use

Solver-loop candidate scoring should run internal clash checks on accepted/top candidates:

```python
report = clash_engine.check_model(temp_model, config=config, results=solver_results)
candidate.metadata["clash"] = clash_report_to_dict(report)
```

### IFC Use

IFC adapter use should be explicit:

```python
IfcClashExchange().export_review_model(model, report, "coordination.ifc")
IfcClashExchange().write_bcf(report, "clashes.bcfzip")
```

## Key Decisions

### Decision 1 - Own The Clash Interface

Routing, optimization, solver scoring, and reports depend on `tuba.clash`, not on IFC.

### Decision 2 - Keep IFC As Adapter

IFC remains valuable for exchange, review, external tools, and coordination deliverables. It is not the internal route-candidate check.

### Decision 3 - Share Envelope Computation

Routing grid, precise clash checks, wind loads, cost, and solver loads must share one physical envelope module. This gives locality for insulation changes.

### Decision 4 - Two Accuracy Levels

The system has two explicit modes:

- Fast mode: routing grid and bounding volumes.
- Review mode: `trimesh`/FCL mesh checks and richer diagnostics.

Future exact mode can use a CAD-kernel adapter.

### Decision 5 - Results Must Be Diagnostic

Returning only colliding element IDs is insufficient. Results must name both entities, severity, clearance, penetration/distance when available, and diagnostics.

## Edge Cases And Failure Modes

- Missing optional dependencies: return a diagnostic or raise a typed error depending on strictness.
- Mesh import failure: preserve obstacle ID and failure reason.
- Invalid obstacle geometry: diagnostic must name the obstacle.
- Zero-length elements: skip with diagnostic.
- Bends: phase 1 may use conservative cylinder approximations; report this limitation.
- Shared endpoints: filter connected pipe segments.
- Pipe on assigned support: filter expected contact.
- Insulated pipe near obstacle: use effective envelope.
- Deformed-state check with missing node result: default zero displacement and add diagnostic if strict.
- IFC product without representation: import as metadata or obstacle bounds only if safe.
- Axis convention mismatch: tests must lock Tuba coordinate convention before rack work expands.

## Acceptance Criteria

Phase 1 acceptance:

- `ClashEngine.check_model()` returns `ClashReport`, not a list of IDs.
- Existing cuboid and STEP mesh collision tests are migrated or wrapped to use the new interface.
- Insulation thickness increases the clash envelope in at least one unit test.
- A no-clash route with bare pipe becomes a clash when insulation envelope is enabled.
- Deformed-state clash check keeps current behavior and returns structured results.
- Routing grid uses the same envelope source as review clash checks.
- IFC export/import tests still pass.
- Missing `trimesh` or FCL produces a useful diagnostic.

Phase 2 acceptance:

- Pipe-to-pipe clashes are reported with entity pairs.
- Assigned support contact can be filtered.
- IFC export writes Tuba clash metadata/property sets.
- A JSON clash report can be written for agents and CI.
- Route reports include structured clash summaries.

Phase 3 acceptance:

- BCF issue export exists for external review.
- IFC imported products preserve enough IDs to map external clashes back to Tuba refs.
- Benchmarks exist for routing-time and review-time checks.

## Test Plan

Unit tests:

- Envelope computation for bare pipe, insulated pipe, cladded pipe, and clearance.
- Cuboid obstacle clash.
- Cuboid obstacle no-clash.
- STEP mesh obstacle clash.
- Pipe-to-pipe clash.
- Shared endpoint filter.
- Assigned support contact filter.
- Deformed-state clash.
- Missing dependency diagnostics.

Integration tests:

- Route candidate is scored with structured clash report.
- IFC export/import still roundtrips pipes, beams, supports, and obstacles.
- IFC review export includes clash property sets when a report is supplied.

Performance tests:

- Moderate model with 1k pipe elements and 100 obstacles completes review clash check under a documented benchmark target on the development machine.
- Routing grid envelope generation remains suitable for candidate search.

## Implementation Notes

### Initial Refactor Path

Do not delete `PipingCollisionChecker` immediately. Wrap it behind `TrimeshClashEngine`, then migrate callers.

### Compatibility

Keep a compatibility method:

```python
PipingCollisionChecker(model).check_collisions()
```

It may internally call the new engine and return element IDs for older code.

### Reporting

Clash reports should serialize to JSON and Markdown. Route reports should include:

- Number of hard clashes.
- Number of clearance violations.
- Worst penetration or minimum distance if available.
- Entity pairs.
- Known limitations.

## Open Questions

- Should insulation attributes be stored first on elements, groups, routes, or all three with inheritance?
- What is the first coordinate convention to formalize for vertical axis?
- Do supports need stable IDs before clash reporting includes support refs?
- Which external issue format should come first: BCF, IFC property sets, or plain JSON?
- Should exact CAD-kernel checking be planned before or after rack modules?

