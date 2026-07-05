# Tuba v4 Library Architecture Review

Status: current-code review, based on the live checkout.

This document explains how the library works today, where the useful modules
are, which features already exist, and what is still missing. It intentionally
separates shipped interfaces from roadmap docs.

## Existing Documentation

Read these documents before changing architecture:

| Document | Current role |
|---|---|
| `README.md` | Product contract, notebook entrypoint, Code_Aster runtime setup, autorouting summary. |
| `AGENTS.md` | Non-negotiable workflow rules: Tuba model, Code_Aster solve, processed result display. |
| `docs/code_aster_installation.md` | Windows/WSL Code_Aster setup and runtime verification. |
| `docs/future_ready_architecture.md` | Implemented semantic layers plus forward-looking multidomain direction. |
| `docs/architecture/user-facing-piping-dsl-and-agent-ops.md` | Roadmap for cleaner DSL and agent operations. Operation/local-field and bend-geometry basics are now shipped; higher-level verbs remain roadmap. |
| `docs/architecture/expansion-aware-autorouting.md` | Current expansion-aware routing decision and limits. |
| `docs/architecture/step-mixed-code-aster.md` | Mixed STEP/Code_Aster export warning. Export is not a completed evaluation. |
| `docs/architecture/adapy-alignment.md` | License and product boundary for optional ada-py interop. |
| `docs/architecture/b31j-compliance-migration.md` | Compliance status, safe implemented subset, and blocked B31J work. |

Historical root-level `*_design.md`, `*_specification.md`, and
`*_strategy.md` files are not the best source for current behavior.

## Product Spine

Tuba v4 is a pipe-native workflow:

```text
TubaModel
  -> Code_Aster study export
  -> Code_Aster execution
  -> imported solver artifacts
  -> FEAResults / ResultState
  -> PyVista quick-look or web review bundle
```

The important rule is that `.comm`, `.mail`, and `.export` generation is only a
solver handoff. It is not a completed engineering evaluation.

## Core Modules

| Module | Interface | What it owns |
|---|---|---|
| `tuba.model` | `TubaModel` / `Model` | Materials, sections, nodes, elements, supports, load cases, operations, local operation fields, obstacles, groups, attributes, placement frames, CAD/mixed-analysis records. |
| `tuba.builder` | `PipingBuilder` through `model.pipe(...)` | Cursor-based authoring of routed pipe, stored bend geometry, beam, bar, and cable elements. |
| `tuba.validation` | `model.validate()` / `validate_model(model)` | Structural invariants and reference checks. |
| `tuba.solver.aster` | `CodeAsterSolver` | Study export, Code_Aster execution, result parsing. |
| `tuba.solver.aster_comm` | `_write_comm(...)` | Code_Aster command-file generation. |
| `tuba.solver.aster_loads` | load-block helpers | Operation/load-case pressure and temperature compilation for `.comm` output. |
| `tuba.solver.aster_mesh` | `_write_mail(...)` | Code_Aster mesh generation plus `AnalysisMesh` provenance. |
| `tuba.analysis.*` | `AnalysisStudy`, `AnalysisMesh`, `ResultState`, artifact import helpers | Traceability and persisted result context. |
| `tuba.plotting` | `FEAResults.plot_*()` | PyVista quick-look and export path. |
| `tuba.visualization` | `build_visualization_scene(...)`, `write_scene_bundle(...)` | Semantic web-scene review bundle for the Three.js viewer. |
| `tuba.routing` | `GridRouter`, `NetworkRouter`, `AutoroutingAgent`, `SolverLoopScorer` | Route candidates, route reports, optional solver handoff/scoring. |
| `tuba.compliance` | `ASMEB313Evaluator` | ASME B31.3/B31J-compatible checks for the implemented safe subset. |
| `tuba.external` | IFC and optional bridge modules | Exchange adapters, not the internal model. |

This is a good high-level shape: the source model, solver adapter, result
state, and review surfaces are separate enough to reason about.

## Current Authoring Interface

The shipped builder is a simple cursor DSL:

```python
from tuba import Model

model = Model(project_name="Demo")
model.add_material("Steel", E=210e9, nu=0.3, rho=7850, alpha=12e-6)
model.add_pipe_section("DN100", OD=0.1143, WT=0.00602)

with model.pipe(section="DN100", material="Steel", route="P-100") as b:
    b.start([0.0, 0.0, 0.0], support="anchor")
    b.run(2.0)
    b.bend_to([2.0, 1.0, 0.0], radius=0.8, plane_normal=[0.0, 0.0, 1.0])
    b.run(2.0)
    b.end(support="anchor")

hot = model.define_operation(
    "Hot",
    gravity=True,
    pressure=1.6e6,
    temperature=180.0,
    ref_temperature=20.0,
)
hot.add_field("temperature", 140.0, route_id="P-100", station_start=0.0, station_end=1.5)

model.validate()
```

Shipped builder methods include `start`, `run`, `bend`, `bend_to`,
`bend_in_plane`, `bend_by_orientation`, `add_support`, `spring`,
`run_element`, `beam`, `bar`, `cable`, `end`, and `set_direction`.
`model.pipe(..., route=...)` stores route and station metadata on generated
pipe elements.

The roadmap methods in `user-facing-piping-dsl-and-agent-ops.md`, such as
`anchor`, `guide`, `block`, `temperature_sweep`, and structured agent
operations, are not the current public interface.

## Code_Aster Workflow

The normal real-solver path is:

```python
from pathlib import Path
from tuba.solver.aster import CodeAsterSolver

solver = CodeAsterSolver(
    work_dir="runs/demo_hot",
    exec_method="wsl",
    wsl_distro="Ubuntu",
)

study = solver.export_analysis_study(model, "Hot", Path("runs/demo_hot"))
results = solver.solve_exported_study(model, study)
```

Notebook code should usually use the shared helper:

```python
from tuba.analysis.code_aster_notebook import load_or_run_code_aster_results

run = load_or_run_code_aster_results(
    model,
    "Hot",
    "notebooks/code_aster_results/stress_analysis_operating",
    run_solver=True,
    exec_method="wsl",
    wsl_distro="Ubuntu",
)

results = run.results
```

For artifact review without executing Code_Aster:

```python
from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts

artifact = import_code_aster_artifacts(
    model=model,
    work_dir="notebooks/code_aster_results/stress_analysis_operating",
    load_case="Hot",
)

results = artifact.results
```

Only use this when the directory already contains real Code_Aster result
artifacts.

## Code_Aster Command Map

`tuba/solver/aster_comm.py` writes the current `.comm` file. These links are the
technical basis for the generated command file. The HTML pages mirror the
Code_Aster U4 command manuals and link back to the Code_Aster PDF docs.

| Tuba generation point | Code_Aster command | Why Tuba uses it | Manual |
|---|---|---|---|
| Mesh read | `LIRE_MAILLAGE(FORMAT='ASTER')` | Reads the generated `study.mail` mesh. Mixed studies use MED. | [U4.21.01 LIRE_MAILLAGE](https://biba1632.gitlab.io/code-aster-manuals/docs/user/u4.21.01.html) |
| Discrete spring/mass support mesh | `CREA_MAILLAGE(CREA_POI1=...)` | Adds point elements for discrete springs and masses. | [U4.23.02 CREA_MAILLAGE](https://biba1632.gitlab.io/code-aster-manuals/docs/user/u4.23.02.html) |
| Mechanical model assignment | `AFFE_MODELE` | Assigns `TUYAU_3M` for pipes, `POU_D_T` for beams, `BARRE`, `CABLE`, and `DIS_TR`. | [U4.41.01 AFFE_MODELE](https://biba1632.gitlab.io/code-aster-manuals/docs/user/u4.41.01.html) |
| Material definition | `DEFI_MATERIAU` | Defines elastic material parameters and cable material data. | [U4.43.01 DEFI_MATERIAU](https://biba1632.gitlab.io/code-aster-manuals/docs/user/u4.43.01.html) |
| Material assignment | `AFFE_MATERIAU` | Assigns materials and thermal reference variables to mesh groups. | [U4.43.03 AFFE_MATERIAU](https://biba1632.gitlab.io/code-aster-manuals/docs/user/u4.43.03.html) |
| Element characteristics | `AFFE_CARA_ELEM` | Defines pipe, bend, beam, bar, cable, discrete spring/mass, and `GENE_TUYAU` orientation data. | [U4.42.01 AFFE_CARA_ELEM](https://biba1632.gitlab.io/code-aster-manuals/docs/user/u4.42.01.html) |
| Supports, gravity, pressure, wind, mixed couplings | `AFFE_CHAR_MECA` | Writes `DDL_IMPO`, `PESANTEUR`, `FORCE_TUYAU`, beam-modelized wind via `FORCE_POUTRE(TYPE_CHARGE='VENT')`, and `LIAISON_ELEM` for mixed pipe-to-port studies. | [U4.44.01 AFFE_CHAR_MECA](https://biba1632.gitlab.io/code-aster-manuals/docs/user/u4.44.01.html) |
| Thermal expansion field | `CREA_CHAMP` | Creates nodal temperature fields for thermal expansion. | [U4.72.04 CREA_CHAMP](https://biba1632.gitlab.io/code-aster-manuals/docs/user/u4.72.04.html) |
| Nonlinear thermal evolution | `CREA_RESU` | Creates the thermal result evolution used by nonlinear cases. | [U4.44.12 CREA_RESU](https://www-mdp.eng.cam.ac.uk/web/CD/engapps/aster_docs/UDocs-HTML/U44412g1/U44412g1.pdf.html) |
| Rest/contact time list | `DEFI_LIST_REEL`, `DEFI_LIST_INST` | Defines the simple nonlinear solve increments. | [U4.34.01 DEFI_LIST_REEL](https://biba1632.gitlab.io/code-aster-manuals/docs/user/u4.34.01.html), [U4.34.03 DEFI_LIST_INST](https://biba1632.gitlab.io/code-aster-manuals/docs/user/u4.34.03.html) |
| Unilateral rests | `DEFI_CONTACT(FORMULATION='LIAISON_UNIL')` | Models unilateral rest/lift-off behavior when support conditions are nonlinear. | [U4.44.11 DEFI_CONTACT](https://biba1632.gitlab.io/code-aster-manuals/docs/user/u4.44.11.html) |
| Linear solve | `MECA_STATIQUE` | Solves linear static mechanical cases. | [U4.51.01 MECA_STATIQUE](https://www-mdp.eng.cam.ac.uk/web/CD/engapps/aster_docs/UDocs-HTML/U45101i1/U45101i1.pdf.html) |
| Nonlinear solve | `STAT_NON_LINE` | Solves rest/friction/contact nonlinear cases. | [U4.51.03 STAT_NON_LINE](https://biba1632.gitlab.io/code-aster-manuals/docs/user/u4.51.03.html) |
| Derived fields | `CALC_CHAMP` | Computes displacement-derived stresses, element forces, equivalent stress, and nodal forces. | [U4.81.04 CALC_CHAMP](https://biba1632.gitlab.io/code-aster-manuals/docs/user/u4.81.04.html) |
| MED result file | `IMPR_RESU(FORMAT='MED')` | Writes `study.rmed` for visualization and artifact review. | [U4.91.01 IMPR_RESU](https://biba1632.gitlab.io/code-aster-manuals/docs/user/u4.91.01.html) |
| Parseable CSV tables | `CREA_TABLE`, `IMPR_TABLE` | Writes `study_depl.csv`, `study_effo.csv`, `study_reac.csv`, and `study_sieq.csv`. | [U4.91.03 IMPR_TABLE](https://www-mdp.eng.cam.ac.uk/web/CD/engapps/aster_docs/UDocs-HTML/U49103e/U49103e.pdf.html) |

When adding solver features, update this table and keep generated `.comm`
snippets aligned with the relevant Code_Aster manual page.

## Result And Visualization Flow

There are two display paths. Do not add a third.

### PyVista Quick-Look

`FEAResults` in `tuba.solver.base` has convenience methods:

```python
plotter = results.plot_deformed_stress(scale=40.0)
plotter.show()
```

This path lives under `tuba.plotting`. It is good for notebooks, quick
inspection, and PLY/glTF export. It must still be fed by real Code_Aster
artifacts when displaying engineering results.

### Web Review Bundle

The reviewable web-scene path is:

```python
from tuba.analysis.results import result_state_from_fea_results
from tuba.visualization import build_visualization_scene, write_scene_bundle

result_state = result_state_from_fea_results(
    model=model,
    study=study,
    results=results,
)

scene = build_visualization_scene(
    model,
    result_states=[result_state],
    analysis_meshes=[run.artifact.analysis_mesh] if run.artifact.analysis_mesh else [],
)

bundle = write_scene_bundle(scene, "runs/demo_hot/review_scene")
```

The viewer under `viewer/` renders that bundle. This path is for shareable
review, overlays, object maps, route alternatives, issues, and deformed states.

## Shipped Feature Inventory

### Modeling

- Pipe-native `TubaModel` source model.
- Materials with elastic and thermal expansion data.
- Pipe, bar, cable, rectangular, and I-beam sections.
- Nodes, elements, supports, load cases, obstacles, groups, semantic
  attributes, insulation specs, placement frames, and mixed-analysis records.
- First-class operations with uniform pressure/temperature/gravity and local
  pressure/temperature fields by all, group, route/station range, or explicit
  element selection.
- Route/station metadata on generated pipe elements.
- Cursor builder for pipe routes, stored 3D bends, beams, bars, and cables.
- JSON serialization and JSON-schema validation.
- Model validation for references, sections, groups, placements, attributes,
  operation fields, route/station metadata, bend geometry, and mixed records.

### Code_Aster

- 1D pipe/beam/bar/cable Code_Aster export.
- `TUYAU_3M` pipe modelisation.
- Bend meshing from stored `BendGeometry`, with generated analysis nodes and
  sidecar lineage.
- Local uniform pressure and temperature operation fields compiled into
  Code_Aster mesh groups.
- Beam-modelized wind operation fields compiled into
  `FORCE_POUTRE(TYPE_CHARGE='VENT')`.
- `.mail`, `.comm`, `.export`, `study_manifest.json`, and
  `study_tuba_fem.json` generation.
- Runtime discovery and execution through WSL, command runner, Python bridge,
  or Docker fallback.
- CSV and RMED artifact parsing into `FEAResults`.
- Notebook helper that either loads real artifacts or runs Code_Aster when
  configured.
- Mixed STEP/pipe study export for the first pipe-to-solid-port slice.

### Results And Review

- `FEAResults` for displacements, reactions, element forces, stresses, and
  plotting.
- `AnalysisStudy`, `AnalysisMesh`, and `ResultState` for provenance.
- Cold, operating, and visual deformed geometry states.
- Physical deformed envelopes for clash checks and review.
- PyVista notebook/quick-look plotting.
- Web-scene bundle export for the Three.js viewer.

### Routing And Engineering Helpers

- Deterministic 3D grid A* routing.
- Network routing with conflict repair.
- Expansion-aware U-loop candidate generation.
- Route cost model and route reports.
- Solver-loop export/scoring for selected candidates, including imported
  displacement, reaction, and operating-clearance gates.
- Physical quantities, insulation/wind metadata, load-path reports, rule
  checks, Trimesh clash checks, IFC export/import, and optional ada-py bridge.
- ASME B31.3 evaluator with the implemented safe B31J-compatible subset.

## Closed Architecture Gaps

### 1. Normal Code_Aster export validates first

`CodeAsterSolver.export_study()` and `export_analysis_study()` now call
`model.validate()` before writing solver files. Invalid references and
unsupported local fields fail at the Tuba boundary instead of inside generated
`.mail`, `.comm`, or Code_Aster execution.

### 2. Current API drift has a guard

`tests/test_current_api_docs.py` scans current-code docs, notebooks, and
examples for method calls that are not present on `TubaModel` or
`PipingBuilder`, while allowing explicitly roadmap-marked documents.

### 3. Operations and local fields are first-class

`TubaModel.define_operation(...)` and `model.operation(...)` create operating
scenarios that compile through the existing load-case path. `OperationField`
records support pressure and temperature values scoped to all pipe elements,
groups, route/station ranges, or explicit elements. Uniform fields export to
Code_Aster today; linear and piecewise profiles fail loudly until the writer
supports them.

### 4. Route/station and bend geometry are stored model facts

Generated pipe elements can carry `route_id`, `station_start`, and
`station_end`. Bend elements can carry `BendGeometry` with center, normal,
radius, angle, and tangent data. Mesh generation, analysis-mesh provenance,
scene output, routing adapters, and compliance hooks now use that stored data.

### 5. `_write_comm` has a real load compiler seam

The command writer still owns Code_Aster command ordering, but pressure and
temperature load-block generation lives in `tuba/solver/aster_loads.py`.
Support compilation remains in `_write_comm(...)` because there is not yet a
shared support compiler seam.

## Remaining Gaps

### 1. Real Code_Aster runtime must be configured for production solves

The library has WSL, command-runner, Python-bridge, and Docker execution paths,
but this checkout cannot prove a fresh solve unless one of those paths finds a
real Code_Aster runner. If no runner is available, production result display
must stop with the setup blocker.

### 2. Occasional wind/seismic loads are only partially end to end

Tuba now represents wind as an operation field for beam-modelized pipe sections
and compiles it to `FORCE_POUTRE(TYPE_CHARGE='VENT')`, using the existing
physical wind diameter calculation. This is intentionally limited to elements
that export as `POU_D_T`; validation rejects wind fields on `TUYAU_3M` pipe
elements. Code_Aster U4.44.01 documents `FORCE_TUYAU` as internal pipe pressure
only, and `FORCE_NODALE` is still not acceptable as a production wind shortcut
because the manual warns that nodal loads are physically incorrect and can
create stress concentrations. Seismic loads remain unimplemented.

### 3. B31J tee/branch factors remain externally blocked

The evaluator keeps the implemented safe subset and bend directional indices,
but exact tee/branch factors require licensed ASME B31J source text or
authorized user-provided tables. Do not infer those coefficients from public
secondary material.

### 4. Mixed STEP remains export/handoff oriented

Mixed STEP/pipe studies can generate analysis handoff artifacts for the first
pipe-to-solid-port slice. A complete mixed STEP solve/import/result-display
workflow still needs the same real Code_Aster runtime proof as the pipe-native
solve path.

## Recommended Next Architecture Work

1. Configure and verify a real Code_Aster runner with
   `python -m tuba.solver.code_aster_doctor --check`.
2. Extend wind beyond the current beam-modelized slice only when the selected
   Code_Aster pipe modelization has a documented distributed-load command.
   Add seismic as its own end-to-end slice: model field, Code_Aster writer,
   imported-result check, and compliance/routing use.
3. Add B31J tee/branch factors only from licensed or authorized source tables.
4. Expand mixed STEP beyond export-only after the runtime path is proven.

This is now mostly a runtime/source-data problem, not a missing core-model
problem.
