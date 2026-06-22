# Tuba v4

AI-ready piping stress analysis & routing library.

## Installation

```bash
pip install -e .
```

Tuba v4 requires Python 3.10 or newer.

## Pipe Autorouting

Tuba includes a deterministic grid-based pipe autorouter. It routes pipe
centerlines between declared endpoints while avoiding model obstacles and
existing pipes with the requested pipe OD, insulation, and clearance envelope.

For the complete review workflow, use `AutoroutingAgent`. It generates route
candidates, exports Code_Aster study files for the top candidates, optionally
applies the selected route to the model, and writes Markdown/JSON reports.

```powershell
.\.venv\Scripts\python.exe examples\autoroute_single_pipe.py
.\.venv\Scripts\python.exe examples\autoroute_network.py
```

Expected outputs are written below `routing_reports/`, including
`route_report.md`, `route_result.json`, and `studies/<pipe>/candidate_*/study.*`
files when study export is enabled.

For interactive Jupyter review, install the optional PyVista/Trame notebook
stack and open the notebook:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[notebook-viz]"
jupyter lab notebooks\autorouting_quick_iteration.ipynb
```

```python
from tuba import Model
from tuba.routing import AutoroutingAgent, GridRouter
from tuba.routing.solver_loop import SolverLoopConfig
from tuba.routing.types import (
    PipeRouteRequest,
    RouteEndpoint,
    RoutingConstraints,
    RoutingGridSpec,
)

model = Model("RoutingDemo")
model.add_material("steel", E=210e9, nu=0.3, rho=7850, alpha=12e-6)
model.add_pipe_section("DN100", OD=0.1143, WT=0.00602)
model.add_obstacle(
    id="equipment_box",
    type="cuboid",
    min_point=(1.5, -0.4, -0.4),
    max_point=(2.5, 0.4, 0.4),
)

request = PipeRouteRequest(
    id="P-100",
    start=RouteEndpoint("A", (0.0, 0.0, 0.0)),
    goal=RouteEndpoint("B", (4.0, 0.0, 0.0)),
    section="DN100",
    material="steel",
    constraints=RoutingConstraints(clearance=0.10, min_bend_radius=0.20),
)

run = AutoroutingAgent(
    router=GridRouter(RoutingGridSpec(cell_size=0.25, margin=1.0), candidate_count=3),
    solver_config=SolverLoopConfig(run_solver=False, export_study=True),
    output_root="routing_reports",
).route_pipe(model, request, apply=True)
```

For multiple pipes, use `NetworkRouter` with `NetworkRouteRequest`. It routes
requests in a deterministic priority order and treats accepted earlier routes
as obstacles for later routes. Supported order strategies are `given`,
`large_bore_first`, `critical_first`, and `least_flexible_first`.

Candidate review can be extended with `SolverLoopScorer`. With
`SolverLoopConfig(run_solver=False, export_study=True)`, Tuba exports Code_Aster
study folders for the highest-ranked candidates without launching Code_Aster.
This provides reviewable `.comm`, `.mail`, and `.export` files for engineering
checks or downstream solver automation.

Current autorouting scope:

- Orthogonal 3D A* routing over a bounded occupancy grid.
- Cuboid and cylinder obstacle envelopes.
- Existing pipe avoidance using OD, insulation, and clearance.
- Multiple alternative candidates by penalizing/blocking prior route cells.
- Model mutation into straight and bend elements.
- Markdown and JSON route reports.
- Agent-style orchestration for route, rank/export, apply, and report workflows.

Current limitations:

- Route geometry is centerline-based and still requires engineering review.
- Mesh obstacles use conservative bounds when available, not exact voxelization.
- Slope, rack preferences, stress-code allowables, valve/instrument placement,
  constructability checks, and support optimization are API hooks but not full
  engineering-grade solvers yet.

Troubleshooting:

- `No route found`: increase grid bounds/margin, reduce clearance, or inspect
  inflated obstacles in the route report.
- `outside routing grid bounds`: explicit bounds do not include the endpoint.
- `Routing grid has ... exceeding max_cells`: increase `cell_size`, reduce the
  design volume, or raise `max_cells` deliberately.
- Solver unavailable: use `run_solver=False`; study export and cheap ranking
  still work.
- HTML visualization dependencies missing: Markdown/JSON reports remain the
  supported headless review output.

## Future-Ready Semantic Workflow

The semantic architecture keeps generated geometry patch-first and attaches
engineering facts, such as insulation, as typed attributes. The same semantic
input can then feed physical envelopes, clash checks, quantities, route cost,
load-path reports, rules, and BOM export.

```powershell
.\.venv\Scripts\python.exe examples\future_ready_semantic_workflow.py
```

See [`docs/future_ready_architecture.md`](docs/future_ready_architecture.md)
for the implemented layers and extension points.

## IFC And External Interop

Tuba exports pipe runs as IFC pipe systems while keeping `TubaModel` as the
source of truth. Pipe flow elements are emitted as `IfcPipeSegment` and
`IfcPipeFitting` products grouped by an `IfcDistributionSystem`. Tuba property
sets carry section, material, bend, support, stress, and operating-state
metadata for round-trip and coordination review.

`ada-py` is treated as an optional interoperability bridge, not a core
dependency. See [`docs/architecture/adapy-alignment.md`](docs/architecture/adapy-alignment.md)
before enabling the optional bridge.

## Reusable Fragments And Agent Workflows

Reusable local-coordinate assemblies are represented as `ModelFragment` objects
and placed into parent models with `CoordinateSystem`. This supports templates,
repeated subassemblies, GUI groups, and safer agent-generated model changes.
Generated edits can be validated as `ModelPatch` payloads and applied through
`ModelTransaction` for rollback-safe mutation.

See [`docs/agent_model_workflow.md`](docs/agent_model_workflow.md).

## Section Catalog

I-beam profile data is loaded through `SectionCatalog` from `tuba.sections`.
The runtime package no longer carries the old vendored Euclid geometry code or
Salome section-generation scripts; active profile data lives under
`tuba/sections/data`.
