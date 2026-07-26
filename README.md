# Tuba v4

Open-source Python project for piping models, Code_Aster workflows, and result
review.

## Core Workflow

Tuba v4 is organized around this workflow:

1. Define the piping structure in Tuba.
2. Evaluate the model with Code_Aster.
3. Display, review, and report processed Code_Aster results.

Generating `.comm`, `.mail`, and `.export` files is only the solver handoff.
It is not a completed evaluation. Full stress, displacement, reaction,
thermal-expansion, operating-state clash, compliance, and result visualization
workflows must run Code_Aster or import real Code_Aster result artifacts before
showing solver results. If Code_Aster is unavailable, Tuba should stop with a
clear runtime/setup blocker rather than substitute mock values.

Code_Aster is required for the full Tuba workflow. It is required for full
stress, displacement, reaction, compliance, and result visualization workflows.

## Documentation Map

Read these first - they describe what the code actually does today:

| Source | Role |
|---|---|
| `README.md`, `CONTRIBUTING.md` | Project workflow and contributor guidance |
| `notebooks/00`-`10` | The end-to-end notebook course, in order |
| `docs/site/` | GitHub Pages source: tutorial, modeling basics, overview, workflow, autorouting, commands, examples, setup, developer |
| `docs/architecture/library-architecture-review.md` | Current architecture map |
| `docs/architecture/*` | Focused design decisions and explicitly labeled roadmap docs |
| `docs/code_aster_installation.md` | Canonical Code_Aster setup |

## Code_Aster Runtime

Code_Aster execution is required for production stress, displacement, reaction,
compliance, operating-state clash, and result visualization workflows.
Exporting `.comm`, `.mail`, and `.export` files is only the solver handoff; the
engineering evaluation is incomplete until Code_Aster has executed and Tuba has
imported the generated artifacts.

Run the runtime doctor:

```powershell
.\.venv\Scripts\python.exe -m tuba.solver.code_aster_doctor
```

Equivalent module form: `python -m tuba.solver.code_aster_doctor`.

Run the bounded runtime readiness check before enabling solver execution from notebooks:

```powershell
.\.venv\Scripts\python.exe -m tuba.solver.code_aster_doctor --check
```

Equivalent module form: `python -m tuba.solver.code_aster_doctor --check`.

VS Code notebooks default to loading committed Code_Aster artifacts when those
artifacts are present. Set `RUN_CODE_ASTER = True` only after the doctor check
reports a ready runtime; the notebook loader preserves existing result tables
when runtime preflight fails.

Full Windows/WSL installation walkthrough:
[`docs/code_aster_installation.md`](docs/code_aster_installation.md).

Preferred Windows/WSL setup:

```powershell
$env:TUBA_CODE_ASTER_EXEC_METHOD = "wsl"
$env:TUBA_CODE_ASTER_WSL_DISTRO = "Ubuntu"
```

Use `TUBA_CODE_ASTER_PYTHON` only when the configured Python executable is
directly executable by the Tuba process, for example when Tuba itself runs
inside Linux/WSL:

```powershell
$env:TUBA_CODE_ASTER_PYTHON = "<host-executable Python that can import run_aster>"
```

Fallback setup:

```powershell
$env:TUBA_CODE_ASTER_RUNNER = "run_aster"
```

Real solver smoke:

```powershell
$env:TUBA_CODE_ASTER_EXEC_METHOD = "wsl"
$env:TUBA_CODE_ASTER_WSL_DISTRO = "Ubuntu"
$env:TUBA_RUN_CODE_ASTER_INTEGRATION = "1"
.\.venv\Scripts\python.exe -m unittest tests.test_code_aster_real_smoke -v
```

## Installation

```bash
pip install tuba
```

This pip installs Tuba; it does not install Code_Aster. The solver is a
separate Linux runtime. On Windows, install it in WSL2 Ubuntu by following
[`docs/code_aster_installation.md`](docs/code_aster_installation.md). The
`code-aster-rmed` extra adds result-file reading support only; it is not the
solver.

Tuba v4 requires Python 3.10 or newer.

Install only the optional surfaces you use:

```bash
pip install "tuba[viz]"       # PyVista quick-look and RMED reading
pip install "tuba[collision]" # exact Trimesh/FCL collision checks
pip install "tuba[ifc]"       # IFC exchange
```

The wheel includes the built Three.js review application. Its installed asset
directory is available through `tuba.visualization.viewer_assets_path()`.
Start it against a generated scene bundle with:

```bash
python -m tuba.visualization.viewer path/to/bundle --open
```

The command validates `scene.json`, serves only the packaged viewer and selected
bundle, and prints the exact local URL. `tuba-viewer` is the equivalent installed
console command.

## Quick Notebook Path

One install command provides every dependency used by all 14 course and
supplemental notebooks:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[course]"
jupyter lab notebooks\00_welcome_and_setup.ipynb
```

The first workflow in that notebook builds a piping model, loads or runs
Code_Aster through the configured runtime, imports the generated result
artifacts, and opens an interactive deformed-stress view. Continue with
`notebooks\03_stress_analysis_and_compliance.ipynb` for compliance checks and
`notebooks\04_visualization_gallery.ipynb` for additional result exports.

Course sequence:

| Notebook | Purpose |
|---|---|
| `00_welcome_and_setup.ipynb` | Fast complete workflow: model, Code_Aster, interactive result |
| `01_building_piping_systems.ipynb` | Geometry authoring with the piping DSL |
| `02_supports_and_loading.ipynb` | Supports, boundary conditions, and load cases |
| `03_stress_analysis_and_compliance.ipynb` | Code_Aster-backed stress and ASME B31.3 checks |
| `04_visualization_gallery.ipynb` | Result visualization and export formats |
| `05_autorouting.ipynb` | Deterministic routing and Code_Aster study handoff |
| `06_structural_frames_and_optimization.ipynb` | Pipe racks and Code_Aster-backed design evaluation |
| `07_bim_data_exchange.ipynb` | JSON and IFC/BIM exchange with solver properties |
| `08_expansion_aware_autorouting.ipynb` | Hot-line routing with reserved expansion envelopes |
| `09_imported_component_mixed_system.ipynb` | Imported CAD component placement and pipe coupling |
| `10_interactive_postprocessor.ipynb` | Focused Code_Aster artifact post-processing |

Supplemental notebooks: `autorouting_quick_iteration.ipynb`,
`visualize_elements_and_supports.ipynb`, and
`advanced_piping_design_and_bim.ipynb`.

For focused post-processing, open:

```powershell
jupyter lab notebooks\10_interactive_postprocessor.ipynb
```

It loads preserved Code_Aster artifacts by default, renders interactive
PyVista result views, and writes a `viewer/` scene bundle for review.

## Project Page

The GitHub Pages source lives at `docs/site/`. It includes the first-analysis
tutorial, modeling basics for sections, coordinates, schemas, and validation,
current overview, workflow, autorouting manual, command reference, examples,
setup, developer guide, the post-processor notebook download, and a preserved
Code_Aster-backed viewer bundle.

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
.\.venv\Scripts\python.exe examples\autoroute_expansion_loop.py
```

Expected outputs are written below `routing_reports/`, including
`route_report.md`, `route_result.json`, and `studies/<pipe>/candidate_*/study.*`
files when study export is enabled.

For hot lines, `examples\autoroute_expansion_loop.py` combines a
`ThermalRouteRequirement` with an `ExpansionAwareRouter` and explicit expansion
loop specs. It also sets `SolverAcceptanceCriteria` and uses
`SolverLoopConfig(run_solver=False, export_study=True)` so the example produces
route-geometry reports and Code_Aster study files for review. That mode is a
development handoff only: engineering evaluation is incomplete until the study
is solved with Code_Aster and the generated result artifacts are imported. The
demo keeps normal movement constraints and selects the U-loop because its
geometry is lower cost than the valid grid detour around the equipment
envelope.

For interactive autorouting review, open the quick-iteration notebook:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[course]"
jupyter lab notebooks\autorouting_quick_iteration.ipynb
jupyter lab notebooks\08_expansion_aware_autorouting.ipynb
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
This provides reviewable `.comm`, `.mail`, and `.export` files for solver
handoff and debugging. It is not a completed engineering evaluation until
Code_Aster has run and Tuba has imported the generated result artifacts.

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
  constructability checks, and automatic support placement are not implemented.

Troubleshooting:

- `No route found`: increase grid bounds/margin, reduce clearance, or inspect
  inflated obstacles in the route report.
- `outside routing grid bounds`: explicit bounds do not include the endpoint.
- `Routing grid has ... exceeding max_cells`: increase `cell_size`, reduce the
  design volume, or raise `max_cells` deliberately.
- Solver unavailable: configure a Code_Aster runtime before displaying or
  reporting solver results. `run_solver=False` is acceptable only for authoring,
  export inspection, and CI-safe diagnostics.
- HTML visualization dependencies missing: Markdown/JSON reports remain the
  supported headless review output.

## Semantic Workflow Example

The semantic example keeps generated geometry patch-first and attaches
engineering facts, such as insulation, as typed attributes. The same input feeds
physical envelopes, clash checks, quantities, route cost, load-path reports,
rules, and BOM export.

```powershell
.\.venv\Scripts\python.exe examples\future_ready_semantic_workflow.py
```

See `docs/site/examples.html`, `docs/site/commands.html`, and
`docs/architecture/library-architecture-review.md` for the current documented
surface.

## IFC And External Interop

Tuba exports pipe runs as IFC pipe systems while keeping `TubaModel` as the
source of truth. Pipe flow elements are emitted as `IfcPipeSegment` and
`IfcPipeFitting` products grouped by an `IfcDistributionSystem`. Tuba property
sets carry section, material, bend, support, stress, and operating-state
metadata for round-trip and coordination review.

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

## License

Tuba v4 is licensed under `LGPL-3.0-or-later`. See `LICENSE` and
`LICENSE.GPL`.
