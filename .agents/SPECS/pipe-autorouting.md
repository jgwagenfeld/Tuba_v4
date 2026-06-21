# Pipe Autorouting Spec

## Purpose

Add a practical, engineer-reviewable pipe autorouting subsystem to Tuba v4. The first production target is not a fully automatic plant-layout system. The target is a deterministic routing engine that can generate clash-free, code-aware candidate pipe routes, convert accepted candidates into the existing `TubaModel`, and optionally use Code_Aster plus ASME B31.3 checks to score and improve route alternatives.

The design must fit the current Tuba v4 architecture:

- `tuba.model.TubaModel` is the canonical model container.
- `tuba.builder.PipingBuilder` is the current manual cursor DSL.
- `tuba.geometry.collision.PipingCollisionChecker` checks pipe/obstacle collisions.
- `tuba.solver.aster.CodeAsterSolver` exports/runs/parses Code_Aster studies.
- `tuba.compliance.asme_b313.ASMEB313Evaluator` evaluates pipe stress results.
- `tuba.visualizer` exports reviewable 3D artifacts.

## Background

The research scan points to a staged approach:

- Start with deterministic 3D grid routing: A*, Dijkstra, JPS/Theta* variants.
- Add multi-pipe planning using prioritized planning and conflict-based search ideas.
- Couple route candidates to structural/stress checks only after cheap geometry filters.
- Keep deep RL, OMPL, MILP, and full CAD-grade geometry as later optional backends.

The implementation should therefore prefer a small internal routing core first, with extension points for external planners later.

## Non-Goals

The initial autorouting implementation will not:

- Replace piping engineers or certify a route automatically.
- Implement full plant-design authoring equivalent to Plant 3D, AVEVA E3D, PDMS, or CAESAR II.
- Perform full process design, pipe sizing, hydraulic network balancing, or equipment layout.
- Generate production isometrics, fabrication spool drawings, or full MTO/BOM in Phase 1.
- Use deep reinforcement learning as the first route generator.
- Require ROS, MoveIt, OMPL, CadQuery, or pythonOCC for the first usable version.
- Guarantee global optimality for all routes.

## Definitions

- **Route request**: A single pipe connection request from one endpoint to another, with pipe spec, constraints, and cost preferences.
- **Endpoint**: A point in 3D space, usually a nozzle, tie-in, or model node. It may include preferred direction and minimum straight length.
- **Candidate**: A complete route geometry proposed by a router, with diagnostics and cost breakdown.
- **Accepted route**: A candidate converted into actual Tuba nodes/elements/supports.
- **Routing grid**: A 3D voxel grid over the design volume. Cells can be free, blocked, soft-penalized, preferred, or reserved.
- **Clearance envelope**: Pipe radius plus insulation plus required engineering clearance.
- **Hard constraint**: A condition that invalidates a candidate.
- **Soft cost**: A preference that affects ranking but does not invalidate a candidate.
- **Solver-in-the-loop**: A workflow where selected route candidates are turned into Tuba models, solved, evaluated, and ranked by engineering results.

## Proposed Package Layout

Add a new package:

```text
tuba/
  routing/
    __init__.py
    types.py
    grid.py
    cost.py
    astar.py
    postprocess.py
    adapter.py
    network.py
    solver_loop.py
    report.py
```

### `tuba.routing.types`

Owns dataclasses and public type contracts. This module must stay mostly dependency-light.

Required dataclasses:

```python
@dataclass(frozen=True)
class RouteEndpoint:
    id: str
    point: tuple[float, float, float]
    direction: tuple[float, float, float] | None = None
    min_straight: float = 0.0
```

```python
@dataclass(frozen=True)
class RoutingGridSpec:
    cell_size: float = 0.25
    bounds_min: tuple[float, float, float] | None = None
    bounds_max: tuple[float, float, float] | None = None
    margin: float = 1.0
    allow_diagonal: bool = False
```

```python
@dataclass(frozen=True)
class RoutingConstraints:
    clearance: float = 0.05
    insulation_thickness: float = 0.0
    min_bend_radius: float | None = None
    min_straight_between_bends: float = 0.0
    max_bends: int | None = None
    max_length: float | None = None
    slope: float | None = None
    slope_axis: str | None = None
    avoid_existing_pipes: bool = True
    avoid_obstacles: bool = True
    allowed_directions: tuple[tuple[int, int, int], ...] | None = None
```

```python
@dataclass(frozen=True)
class RoutingCostWeights:
    length: float = 1.0
    bend: float = 5.0
    vertical: float = 1.0
    clearance: float = 2.0
    support_span: float = 0.5
    rack_preference: float = 0.0
    direction_change: float = 0.0
```

```python
@dataclass(frozen=True)
class PipeRouteRequest:
    id: str
    start: RouteEndpoint
    goal: RouteEndpoint
    section: str
    material: str
    constraints: RoutingConstraints = RoutingConstraints()
    costs: RoutingCostWeights = RoutingCostWeights()
    preferred_waypoints: tuple[tuple[float, float, float], ...] = ()
    forbidden_zones: tuple[str, ...] = ()
    preferred_zones: tuple[str, ...] = ()
```

```python
@dataclass
class RouteSegment:
    start: tuple[float, float, float]
    end: tuple[float, float, float]
    kind: Literal["straight", "bend"]
    bend_radius: float | None = None
    bend_angle: float | None = None
```

```python
@dataclass
class PipeRouteCandidate:
    request_id: str
    points: list[tuple[float, float, float]]
    segments: list[RouteSegment]
    cost: float
    cost_breakdown: dict[str, float]
    diagnostics: list[str] = field(default_factory=list)
    is_valid: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
```

```python
@dataclass
class PipeRouteResult:
    request: PipeRouteRequest
    candidates: list[PipeRouteCandidate]
    selected_index: int | None
    diagnostics: list[str]

    @property
    def selected(self) -> PipeRouteCandidate | None: ...
```

```python
@dataclass
class NetworkRouteRequest:
    id: str
    pipe_requests: list[PipeRouteRequest]
    order_strategy: Literal["given", "large_bore_first", "critical_first", "least_flexible_first"] = "given"
    max_reroute_attempts: int = 20
```

```python
@dataclass
class NetworkRouteResult:
    request: NetworkRouteRequest
    pipe_results: dict[str, PipeRouteResult]
    accepted_candidates: dict[str, PipeRouteCandidate]
    unresolved_conflicts: list[dict[str, Any]]
    diagnostics: list[str]
```

### `tuba.routing.grid`

Builds and queries the design-space occupancy grid.

Responsibilities:

- Compute routing bounds from model nodes, endpoints, obstacles, and user margins.
- Convert world coordinates to grid indices and back.
- Mark hard-blocked cells from obstacles.
- Inflate obstacles by pipe radius, insulation, and clearance.
- Optionally mark existing pipes as hard-blocked inflated cylinders.
- Support soft penalty fields for rack zones, preferred corridors, keepout zones, and support zones.
- Provide line-of-sight and swept-cylinder validity helpers.

Required public API:

```python
class RoutingGrid:
    @classmethod
    def from_model(
        cls,
        model: TubaModel,
        request: PipeRouteRequest,
        grid_spec: RoutingGridSpec,
    ) -> "RoutingGrid": ...

    def world_to_index(self, point: Sequence[float]) -> tuple[int, int, int]: ...
    def index_to_world(self, index: tuple[int, int, int]) -> tuple[float, float, float]: ...
    def is_blocked(self, index: tuple[int, int, int]) -> bool: ...
    def penalty(self, index: tuple[int, int, int]) -> float: ...
    def neighbors(self, index: tuple[int, int, int], constraints: RoutingConstraints) -> Iterable[tuple[int, int, int]]: ...
```

Implementation details:

- Phase 1 may use numpy arrays for occupancy.
- Cuboid obstacles can be voxelized exactly by bounds overlap.
- Cylinder and mesh obstacles may be approximated by bounding boxes first, then improved using `trimesh`/`python-fcl`.
- Existing pipe elements should be inflated as cylinders using existing helper logic in `tuba.geometry.collision`.
- Mesh obstacle voxelization must be optional because it can be expensive.

### `tuba.routing.cost`

Owns deterministic cost calculation.

Cost terms:

- Total centerline length.
- Number of bends.
- Direction changes.
- Vertical movement.
- Clearance proximity penalties.
- Support span penalties.
- Preferred corridor/rack penalties.
- Endpoint direction mismatch.
- Slope mismatch.

The cost module must expose both incremental A* move cost and final candidate score:

```python
def transition_cost(
    grid: RoutingGrid,
    previous: GridState | None,
    current: GridState,
    nxt: GridState,
    request: PipeRouteRequest,
) -> float: ...

def score_candidate(
    candidate: PipeRouteCandidate,
    model: TubaModel,
    request: PipeRouteRequest,
) -> PipeRouteCandidate: ...
```

### `tuba.routing.astar`

Implements the first single-pipe router.

Required behavior:

- Deterministic A* over 3D grid cells.
- State includes current cell and incoming direction.
- Bend cost is applied when incoming direction changes.
- Endpoint direction preference is respected when specified.
- Hard constraints invalidate paths during expansion where possible.
- Heuristic defaults to Manhattan distance for orthogonal routing.
- Returns multiple candidates if requested by perturbing weights or reserving cells from prior candidates.

Required public API:

```python
class GridRouter:
    def __init__(
        self,
        grid_spec: RoutingGridSpec | None = None,
        max_expansions: int = 250_000,
        candidate_count: int = 1,
    ) -> None: ...

    def route(
        self,
        model: TubaModel,
        request: PipeRouteRequest,
    ) -> PipeRouteResult: ...
```

Candidate generation strategy:

- Candidate 1: base weights.
- Candidate 2..N: vary bend penalty, vertical penalty, and preferred elevation penalties.
- Optionally block or penalize cells used by previous candidates to encourage alternatives.

### `tuba.routing.postprocess`

Turns raw grid paths into clean pipe centerlines.

Responsibilities:

- Remove collinear intermediate points.
- Snap endpoints to exact requested coordinates.
- Validate bend radius and tangent lengths.
- Split long straight segments if support planning needs intermediate nodes.
- Detect near-zero segments.
- Ensure no segment crosses a hard obstacle after simplification.
- Produce `RouteSegment` objects with straight/bend metadata.

Required public API:

```python
def simplify_grid_path(points: list[Point3D]) -> list[Point3D]: ...
def validate_bend_geometry(points: list[Point3D], constraints: RoutingConstraints) -> list[str]: ...
def build_segments(points: list[Point3D], constraints: RoutingConstraints) -> list[RouteSegment]: ...
```

Phase 1 bend representation:

- Store bends as metadata at direction changes.
- Convert to Tuba `pipe_bend` elements using existing bend conventions.
- Do not require exact CAD elbow solids in Phase 1.

### `tuba.routing.adapter`

Converts a selected candidate into a Tuba model.

Responsibilities:

- Add nodes/elements/supports for a selected candidate.
- Reuse existing nodes when coordinates match within tolerance.
- Preserve pipe section/material.
- Assign globally unique element IDs.
- Create route metadata so results can trace back to the request/candidate.

Required public API:

```python
def apply_candidate_to_model(
    model: TubaModel,
    candidate: PipeRouteCandidate,
    request: PipeRouteRequest,
    *,
    add_supports: bool = False,
    support_spacing: float | None = None,
) -> list[str]:
    """Mutates model and returns created element ids."""
```

Required model change:

- Add a model-level element ID generator to avoid duplicate `pipe_str_0` / `pipe_bend_0` IDs across multiple builder contexts.

Suggested model API:

```python
class TubaModel:
    def next_element_id(self, prefix: str) -> str: ...
```

`PipingBuilder` should use this generator instead of its own local `_segment_counter`.

### `tuba.routing.network`

Routes multiple pipes in one design volume.

Phase 1 network behavior:

- Prioritized planning.
- Route one pipe at a time.
- Accepted routes are converted into temporary obstacles for later pipes.
- If a later pipe cannot route, attempt rerouting with a different route order or penalties.

Phase 2 network behavior:

- CBS-lite conflict repair:
  - Route all pipes with priority planning.
  - Detect collisions between routed candidates.
  - Branch on conflicts by adding constraints that force one route to avoid the other.
  - Replan only affected pipes.
  - Stop when no conflicts remain or max attempts is reached.

Required public API:

```python
class NetworkRouter:
    def __init__(self, single_router: GridRouter | None = None) -> None: ...

    def route_network(
        self,
        model: TubaModel,
        request: NetworkRouteRequest,
    ) -> NetworkRouteResult: ...
```

Initial route-order strategies:

- `given`: user-defined order.
- `large_bore_first`: larger OD first.
- `critical_first`: request metadata marks critical service.
- `least_flexible_first`: shortest endpoint distance or stricter max-bend/max-length constraints first.

### `tuba.routing.solver_loop`

Scores candidates using increasingly expensive checks.

Pipeline:

1. Geometry and routing-cost score.
2. Clash check against obstacles and existing pipes.
3. Approximate engineering checks:
   - bend count,
   - minimum straight length,
   - support span,
   - thermal expansion proxy,
   - expected elbow SIF severity.
4. Build temporary Tuba model.
5. Optionally export Code_Aster study.
6. Optionally run Code_Aster if available.
7. Evaluate ASME B31.3 report.
8. Rank by engineering objective.

Required public API:

```python
@dataclass
class SolverLoopConfig:
    run_solver: bool = False
    export_study: bool = True
    max_solver_candidates: int = 3
    work_root: str | Path = "routing_studies"
    load_case: str | None = None

class SolverLoopScorer:
    def score_candidates(
        self,
        model: TubaModel,
        request: PipeRouteRequest,
        candidates: list[PipeRouteCandidate],
        config: SolverLoopConfig,
    ) -> list[PipeRouteCandidate]: ...
```

Candidate metadata added by solver loop:

```python
candidate.metadata["solver"] = {
    "study_dir": "...",
    "solver_ran": True,
    "solver_name": "Code_Aster",
    "load_case": "hot_operation",
}
candidate.metadata["compliance"] = {
    "overall_pass": True,
    "worst_sustained_ratio": 0.72,
    "worst_expansion_ratio": 0.81,
}
candidate.metadata["reactions"] = {...}
candidate.metadata["displacements"] = {...}
candidate.metadata["nozzle_loads"] = {...}
```

Fallback behavior:

- If Code_Aster is unavailable, the scorer must still return ranked candidates with `solver_ran=False`.
- Missing solver must be a diagnostic, not a crash, unless `run_solver=True` and `strict=True`.

### `tuba.routing.report`

Produces engineer-readable review output.

Minimum Phase 1 report:

- Markdown route report.
- JSON route result.
- Optional PyVista/HTML route preview if visualization dependencies are installed.

Report sections:

- Inputs: endpoints, section, material, constraints, cost weights.
- Selected route summary.
- Candidate comparison table.
- Geometry: length, bends, elevations, low/high points.
- Clash status.
- Supports: proposed support locations and spans.
- Solver/compliance status if run.
- Known limitations.
- Reproduction commands.

Required public API:

```python
def write_route_report(
    result: PipeRouteResult | NetworkRouteResult,
    output_dir: str | Path,
    *,
    model: TubaModel | None = None,
) -> Path: ...
```

## Public Usage Examples

### Single Pipe Route

```python
from tuba import Model
from tuba.routing import GridRouter
from tuba.routing.types import PipeRouteRequest, RouteEndpoint, RoutingConstraints

model = Model(project_name="RouteDemo")
model.add_material("Steel", E=2.0e11, nu=0.3, allowable_stress={20.0: 137e6, 200.0: 120e6})
model.add_pipe_section("NPS4_SCH40", OD=0.1143, WT=0.00602)

request = PipeRouteRequest(
    id="P-100",
    start=RouteEndpoint(id="E1_N1", point=(0.0, 0.0, 1.0), direction=(1.0, 0.0, 0.0)),
    goal=RouteEndpoint(id="E2_N1", point=(8.0, 4.0, 1.0), direction=(-1.0, 0.0, 0.0)),
    section="NPS4_SCH40",
    material="Steel",
    constraints=RoutingConstraints(clearance=0.1, min_bend_radius=0.1524),
)

router = GridRouter(candidate_count=5)
result = router.route(model, request)

if result.selected:
    from tuba.routing.adapter import apply_candidate_to_model
    apply_candidate_to_model(model, result.selected, request)
```

### Solver-In-The-Loop Candidate Ranking

```python
from tuba.routing.solver_loop import SolverLoopConfig, SolverLoopScorer

scorer = SolverLoopScorer()
ranked = scorer.score_candidates(
    model,
    request,
    result.candidates,
    SolverLoopConfig(run_solver=False, export_study=True, max_solver_candidates=3),
)
```

### Multi-Pipe Network Route

```python
from tuba.routing.network import NetworkRouter
from tuba.routing.types import NetworkRouteRequest

network_request = NetworkRouteRequest(
    id="area-a-network",
    pipe_requests=[p100, p200, p300],
    order_strategy="large_bore_first",
)

network_result = NetworkRouter().route_network(model, network_request)
```

## Engineering Requirements

### Geometry

- Routes must be represented as centerline points and converted to Tuba pipe elements.
- Routes must support only orthogonal routing in Phase 1 unless explicitly enabled.
- Endpoints must preserve exact nozzle/tie-in coordinates after path simplification.
- Endpoint direction constraints must be supported.
- Minimum straight length from endpoints must be supported.
- Bend radius and minimum tangent lengths must be validated before model conversion.
- Candidate geometry must be reproducible from serialized JSON.

### Collision and Clearance

- Obstacles in `model.obstacles` must be considered.
- Existing pipe elements must optionally be considered as obstacles.
- Clearance envelope must include:
  - pipe outer radius,
  - insulation thickness,
  - user clearance.
- Candidate routes must be checked after simplification, not only on raw grid cells.
- Collision diagnostics must name the pipe request and obstacle or existing element where possible.

### Supports

Phase 1:

- Score routes with simple support-span penalties.
- Optionally add simple support nodes at spacing intervals.
- Report unsupported spans.

Phase 2:

- Use support zones and forbidden support zones.
- Allow support type preferences: rest, guide, anchor, spring/hanger placeholder.
- Include reactions in solver-loop score.

### Stress and Flexibility

Phase 1:

- Use cheap proxy scores before running Code_Aster:
  - straight distance between anchors,
  - direction changes,
  - expansion loop presence,
  - bend SIF severity,
  - support span.

Phase 2:

- Export top route candidates to Code_Aster.
- Parse real results when available.
- Evaluate ASME B31.3 ratios with `ASMEB313Evaluator`.
- Prefer candidates that reduce overstress, nozzle loads, and excessive support reactions.

### Piping Engineer Review

Autorouting is usable only if it exposes why a route was chosen. Reports must include:

- Route input assumptions.
- Selected route and alternatives.
- Route length and bend count.
- Clash status.
- Clearance assumptions.
- Support spans and proposed supports.
- Code/stress summary if solver ran.
- Known missing checks.
- Files generated for review.

### Determinism

- Given the same model, request, and seed, the router must return the same selected route.
- Candidate perturbation must use explicit seeds.
- Tests must not depend on random candidate order.

### Performance

Initial target:

- Route a single pipe in a 20 m x 20 m x 10 m volume at 0.25 m grid resolution in under 10 seconds on the development machine.
- Generate 5 candidates in under 30 seconds for a moderate obstacle case.
- Degrade gracefully with a clear diagnostic when the grid is too large.

## Required Fixes Before Autorouting

### Unique Element IDs

Current `PipingBuilder` creates duplicate IDs when multiple builder contexts are used. Autorouting will create many independent pipe runs, so this must be fixed first.

Required:

- Move element ID generation to `TubaModel`.
- Update `PipingBuilder` to use model-level IDs.
- Add regression test proving branch/multiple-builder models have unique element IDs.

### Solver Export Path Robustness

Current Code_Aster export/execution path handling should be hardened before solver-in-the-loop routing.

Required:

- Ensure `study.export` paths work when `as_run` is executed from the study directory.
- Add tests for relative and absolute `work_dir`.
- Preserve Windows/WSL behavior.

### HTML Export Dependency Diagnostics

Current demo can fail HTML export if PyVista trame dependencies are missing.

Required:

- Make report generation degrade to Markdown/JSON if HTML export is unavailable.
- Emit install hint for optional visualization dependencies.

## Failure Modes

- No route found because grid bounds are too tight.
- No route found because obstacle inflation blocks all corridors.
- Candidate exists on grid but postprocessed straight segment clips an obstacle.
- Candidate violates endpoint direction.
- Candidate violates min bend radius or min straight tangent length.
- Duplicate element IDs corrupt result mapping.
- Solver unavailable.
- Solver fails for a generated candidate.
- Candidate solves but fails ASME compliance.
- Multi-pipe network has unresolved conflicts after max attempts.
- Grid is too large for memory/time budget.

Every failure must be represented as structured diagnostics in the result object.

## Acceptance Criteria

### Phase 1 Acceptance

- A single pipe can be routed around a cuboid obstacle in 3D.
- The route avoids the inflated obstacle envelope.
- The selected route can be applied to a `TubaModel`.
- All created element IDs are unique.
- Route result serializes to JSON.
- A Markdown report is generated.
- Existing unit tests still pass.

Verification:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

### Phase 2 Acceptance

- Multiple pipes can be routed sequentially.
- Later pipes avoid earlier accepted routes when `avoid_existing_pipes=True`.
- At least one test demonstrates rerouting due to a conflict.
- Network report lists unresolved conflicts if any remain.

### Phase 3 Acceptance

- Top route candidates can be exported as Code_Aster studies without running the solver.
- If solver execution is disabled, candidates still rank by cheap engineering metrics.
- If solver execution is enabled and available, ASME B31.3 ratios are included in candidate metadata.
- Solver failure for one candidate does not discard all other candidates.

### Phase 4 Acceptance

- Example script demonstrates:
  - route generation,
  - candidate comparison,
  - model application,
  - study export,
  - report generation.
- The report is useful without reading Python logs.

## Test Plan

### Unit Tests

Add:

- `tests/test_routing_grid.py`
- `tests/test_routing_astar.py`
- `tests/test_routing_adapter.py`
- `tests/test_routing_network.py`
- `tests/test_routing_solver_loop.py`
- `tests/test_routing_report.py`

Coverage:

- Coordinate/index roundtrip.
- Obstacle voxelization and inflation.
- A* finds direct route in empty space.
- A* routes around cuboid obstacle.
- A* returns no route when corridor is blocked.
- Bend penalty changes candidate preference.
- Endpoint direction is respected.
- Postprocess removes collinear points.
- Postprocess detects obstacle clipping.
- Adapter creates unique nodes/elements.
- Adapter reuses matching endpoint nodes.
- Network router avoids already accepted pipe.
- Solver loop exports candidate study directories.
- Report writes Markdown and JSON.

### Integration Tests

Add a small demo test that:

1. Creates a model with material/section/load case.
2. Adds one cuboid obstacle.
3. Routes one pipe around it.
4. Applies the selected candidate.
5. Exports Code_Aster input.
6. Writes report.

Do not require actual Code_Aster execution in CI/local unit tests.

### Manual Verification

Run:

```powershell
.\.venv\Scripts\python.exe examples\autoroute_single_pipe.py
```

Expected outputs:

- `routing_reports/P-100/route_report.md`
- `routing_reports/P-100/route_result.json`
- `routing_reports/P-100/studies/candidate_*/study.comm`
- `routing_reports/P-100/studies/candidate_*/study.mail`
- optional HTML preview if dependencies are installed.

## Open Questions

- What default grid cell size should match typical plant-piping work: 0.1 m, 0.25 m, or user-defined per area?
- Should route coordinates snap to pipe-rack elevations by default?
- How should Tuba represent nozzles and equipment in the canonical model?
- What minimum support-spacing rules should be used per pipe size/service?
- Which nozzle-load standard should be first: API 610 pumps, API 650 tanks, or user-defined allowables?
- Should branch networks be represented as explicit topology requests or decomposed into independent two-terminal pipe requests first?

