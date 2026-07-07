# Tuba v4 Library Architecture Review

Status: current-code review, refreshed 2026-07-07.

This is the canonical architecture guide for the current library. It explains
the live module boundaries, the end-to-end Code_Aster workflow, the shipped
features, and the missing pieces. It deliberately separates implemented code
from roadmap documents.

## Verdict

The high-level architecture is sound enough to keep:

```text
TubaModel
  -> validation
  -> Code_Aster study export
  -> Code_Aster execution
  -> imported result artifacts
  -> FEAResults / ResultState
  -> PyVista quick-look or web review bundle
```

There is no need for a broad rewrite. The useful boundaries already exist:
`TubaModel` owns the pipe-native engineering model, `CodeAsterSolver` owns the
solver adapter, `ResultState` owns traceable imported results, and the two
visualization paths are intentionally separate.

The major issues are narrower:

| Priority | Issue | Why it matters | Current answer |
|---|---|---|---|
| P0 | Real Code_Aster runtime proof is external to normal CI. | Exported `.comm`, `.mail`, and `.export` files are not engineering results. | Keep failing loudly when runtime/artifacts are missing; run the integration gate with `TUBA_RUN_CODE_ASTER_INTEGRATION=1` on a configured machine. |
| P1 | Roadmap docs can look like shipped API. | Engineers may call unimplemented DSL or assume export-only examples are solved. | Keep this doc and `README.md` as current-code docs; keep roadmap docs explicitly labeled. |
| P1 | `_write_comm(...)` is still large. | New loads can easily be patched in the wrong place. | Keep command ordering there, but put reusable load compilation in small helpers like `tuba/solver/aster_loads.py`. |
| P1 | Some engineering domains are partial. | Wind, seismic, B31J tee/branch, and mixed STEP workflows can be overclaimed. | Document the supported slice and fail unsupported cases before solver export. |

## Existing Documentation

Read these first before changing architecture:

| Document | Current role |
|---|---|
| `README.md` | Product contract, setup, notebook entrypoint, autorouting summary. |
| `AGENTS.md` | Non-negotiable workflow rules: model, Code_Aster solve, processed result display. |
| `docs/code_aster_installation.md` | Windows/WSL Code_Aster setup and runtime doctor flow. |
| `docs/architecture/library-architecture-review.md` | This current-code architecture guide. |
| `docs/architecture/user-facing-piping-dsl-and-agent-ops.md` | Roadmap for cleaner DSL and agent operations. Some basics are shipped; higher-level verbs remain roadmap. |
| `docs/architecture/expansion-aware-autorouting.md` | Current expansion-aware routing decision and limits. |
| `docs/architecture/step-mixed-code-aster.md` | Mixed STEP/Code_Aster export warning. Export is not completed evaluation. |
| `docs/architecture/adapy-alignment.md` | License and boundary for optional ada-py interop. |
| `docs/architecture/b31j-compliance-migration.md` | Compliance status and blocked B31J work. |

Historical root-level `*_design.md`, `*_specification.md`, and
`*_strategy.md` files are not the best source for current behavior.

## Core Modules

| Module | Main interface | What it owns |
|---|---|---|
| `tuba.model` | `TubaModel` / `Model` | Materials, sections, nodes, elements, supports, load cases, operations, fields, obstacles, groups, attributes, placements, CAD/mixed records. |
| `tuba.builder` | `PipingBuilder` through `model.pipe(...)` | Cursor-based route authoring: starts, runs, bends, supports, beams, bars, cables. |
| `tuba.validation` | `model.validate()` / `validate_model(model)` | Structural invariants before export. |
| `tuba.solver.aster` | `CodeAsterSolver` | Study export, runtime execution, result parsing. |
| `tuba.solver.aster_mesh` | `_write_mail(...)` | Code_Aster `.mail` generation and `AnalysisMesh` provenance. |
| `tuba.solver.aster_comm` | `_write_comm(...)` | Code_Aster command-file orchestration in solver execution order. |
| `tuba.solver.aster_loads` | load-block helpers | Pressure, temperature, and wind operation-field compilation. |
| `tuba.solver.code_aster_runtime` | runtime discovery/execution | WSL, command runner, Python bridge, and Docker fallback command construction. |
| `tuba.analysis.*` | `AnalysisStudy`, `AnalysisMesh`, `ResultState`, artifact import helpers | Traceability from Tuba model to solver files and parsed outputs. |
| `tuba.solver.base` | `FEAResults` | Solver-neutral result container and plotting convenience methods. |
| `tuba.plotting` | `results.plot_*()` | PyVista quick-look, notebook rendering, PLY/glTF export. |
| `tuba.visualization` | `build_visualization_scene(...)`, `write_scene_bundle(...)` | JSON scene contract for the Three.js viewer and review bundles. |
| `tuba.routing` | `GridRouter`, `NetworkRouter`, `AutoroutingAgent`, `SolverLoopScorer` | Route candidates, route reports, optional solver export/scoring. |
| `tuba.compliance` | `ASMEB313Evaluator` | Implemented ASME B31.3 / safe B31J-compatible checks. |
| `tuba.external` | IFC and optional bridge modules | Exchange adapters, not internal model authority. |

## How The Library Works

### 1. Author A Pipe-Native Model

The public API is deliberately small at the top level:

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
```

Shipped builder methods include `start`, `run`, `bend`, `bend_to`,
`bend_in_plane`, `bend_by_orientation`, `add_support`, `spring`,
`run_element`, `beam`, `bar`, `cable`, `end`, and `set_direction`.

Route and station metadata are stored on generated pipe elements. Stored
`BendGeometry` records make bend meshing, analysis-mesh lineage, visualization,
and compliance hooks use model facts instead of re-inferring geometry later.

### 2. Define Operating Loads

`Operation` is the higher-level operating scenario. It converts back to the
low-level `LoadCase` record that the Code_Aster writer consumes.

```python
hot = model.define_operation(
    "Hot",
    gravity=True,
    pressure=1.6e6,
    temperature=180.0,
    ref_temperature=20.0,
)

hot.add_field(
    "temperature",
    140.0,
    route_id="P-100",
    station_start=0.0,
    station_end=1.5,
)

model.validate()
```

Supported operation-field quantities are `pressure`, `temperature`, and `wind`.
The Code_Aster writer supports uniform fields for all three quantities. It also
supports `profile="linear"` for temperature fields scoped by route/station,
exported as per-element midpoint temperature assignments through `CREA_CHAMP`.
Non-uniform pressure, non-uniform wind, and piecewise profiles still fail
validation before export.
Wind fields are currently limited to beam-modeled elements because the writer
uses `FORCE_POUTRE(TYPE_CHARGE='VENT')`; `TUYAU_3M` pipe wind and nodal-load
shortcuts are rejected before export.

### 3. Export And Run Code_Aster

Use `CodeAsterSolver` for the explicit solver path:

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

`export_analysis_study(...)` writes:

- `study.mail`
- `study.comm`
- `study.export`
- `study_manifest.json`
- `study_tuba_fem.json`

The manifest and sidecar are not decoration. They map shortened Code_Aster
names and generated analysis-mesh entities back to stable Tuba references.

`model.solve(solver="code_aster", operation="Hot", exec_method="wsl",
wsl_distro="Ubuntu")` dispatches to the same backend, but the explicit solver
object is clearer for architecture and debugging.

### 4. Load Notebook Results Safely

Notebook result cells should use the shared helper instead of hand-building
`FEAResults`:

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

If `run_solver=False`, the directory must already contain real Code_Aster
result tables. If tables are missing, the helper stops before displaying solver
results.

For artifact review without running Code_Aster:

```python
from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts

artifact = import_code_aster_artifacts(
    model=model,
    work_dir="notebooks/code_aster_results/stress_analysis_operating",
    load_case="Hot",
)

results = artifact.results
```

Only use this for directories that already contain real Code_Aster artifacts.

### 5. Display Results Through One Of Two Paths

There are exactly two result-display paths.

#### PyVista Quick-Look

`FEAResults` exposes notebook/interactive helpers:

```python
plotter = results.plot_deformed_stress(scale=40.0, model=model)
plotter.show(jupyter_backend="html")
```

This path lives under `tuba.plotting`. Use it for quick notebook inspection and
PLY/glTF/Blender export. It must still receive real Code_Aster-backed results
when displaying stress, displacement, reactions, or compliance-relevant output.

#### Web Review Bundle

The reviewable web scene path is:

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
)

bundle = write_scene_bundle(scene, "runs/demo_hot/review_scene")
```

The `viewer/` Three.js app renders that bundle. Use this path for shareable
review, object maps, route alternatives, issues, overlays, deformed states, and
static review reports.

Do not add a third display path.

## Code_Aster Command Map

`tuba/solver/aster_comm.py` writes the current `.comm` file. The table below is
the technical basis for the generated commands. The linked HTML pages mirror
the Code_Aster U4 command manuals; the mirror also links back to Code_Aster PDF
docs. Code_Aster's U0.00.01 manual explains that U4 documents are user guides
for commands such as `DEFI_MATERIAU`.

| Tuba generation point | Code_Aster command | Why Tuba uses it | Manual |
|---|---|---|---|
| Mesh read | `LIRE_MAILLAGE(FORMAT='ASTER')` | Reads generated `study.mail`. Mixed studies use MED. | [U4.21.01 LIRE_MAILLAGE](https://biba1632.gitlab.io/code-aster-manuals/docs/user/u4.21.01.html) |
| Discrete spring/mass support mesh | `CREA_MAILLAGE(CREA_POI1=...)` | Adds point elements for discrete springs and masses. | [U4.23.02 CREA_MAILLAGE](https://biba1632.gitlab.io/code-aster-manuals/docs/user/u4.23.02.html) |
| Mechanical model assignment | `AFFE_MODELE` | Assigns `TUYAU_3M`, `POU_D_T`, `BARRE`, `CABLE`, and `DIS_TR`. | [U4.41.01 AFFE_MODELE](https://biba1632.gitlab.io/code-aster-manuals/docs/user/u4.41.01.html) |
| Material definition | `DEFI_MATERIAU` | Defines elastic material parameters and cable material data. | [U4.43.01 DEFI_MATERIAU](https://biba1632.gitlab.io/code-aster-manuals/docs/user/u4.43.01.html) |
| Material assignment | `AFFE_MATERIAU` | Assigns materials and thermal reference variables to mesh groups. | [U4.43.03 AFFE_MATERIAU](https://biba1632.gitlab.io/code-aster-manuals/docs/user/u4.43.03.html) |
| Element characteristics | `AFFE_CARA_ELEM` | Defines pipe, bend, beam, bar, cable, spring/mass, and `GENE_TUYAU` orientation data. | [U4.42.01 AFFE_CARA_ELEM](https://biba1632.gitlab.io/code-aster-manuals/docs/user/u4.42.01.html) |
| Supports, gravity, pressure, wind, mixed couplings | `AFFE_CHAR_MECA`, `AFFE_CHAR_MECA_F` | Writes `DDL_IMPO`, `PESANTEUR`, `FORCE_TUYAU`, beam-modeled wind through `FORCE_POUTRE(TYPE_CHARGE='VENT')`, and `LIAISON_ELEM`. | [U4.44.01 AFFE_CHAR_MECA](https://biba1632.gitlab.io/code-aster-manuals/docs/user/u4.44.01.html) |
| Thermal expansion fields | `CREA_CHAMP` | Creates temperature fields for uniform and route/station-linear thermal expansion. | [U4.72.04 CREA_CHAMP](https://biba1632.gitlab.io/code-aster-manuals/docs/user/u4.72.04.html) |
| Nonlinear thermal evolution | `CREA_RESU` | Creates thermal result evolution used by nonlinear cases. | [U4.44.12 CREA_RESU](https://www-mdp.eng.cam.ac.uk/web/CD/engapps/aster_docs/UDocs-HTML/U44412g1/U44412g1.pdf.html) |
| Rest/contact time list | `DEFI_LIST_REEL`, `DEFI_LIST_INST` | Defines the simple nonlinear solve increments. | [U4.34.01 DEFI_LIST_REEL](https://biba1632.gitlab.io/code-aster-manuals/docs/user/u4.34.01.html), [U4.34.03 DEFI_LIST_INST](https://biba1632.gitlab.io/code-aster-manuals/docs/user/u4.34.03.html) |
| Unilateral rests | `DEFI_CONTACT(FORMULATION='LIAISON_UNIL')` | Models unilateral rest/lift-off behavior when support conditions are nonlinear. | [U4.44.11 DEFI_CONTACT](https://biba1632.gitlab.io/code-aster-manuals/docs/user/u4.44.11.html) |
| Linear static solve | `MECA_STATIQUE` | Solves linear static mechanical cases. | [U4.51.01 MECA_STATIQUE](https://www-mdp.eng.cam.ac.uk/web/CD/engapps/aster_docs/UDocs-HTML/U45101i1/U45101i1.pdf.html) |
| Nonlinear static solve | `STAT_NON_LINE` | Solves rest/friction/contact nonlinear cases. | [U4.51.03 STAT_NON_LINE](https://biba1632.gitlab.io/code-aster-manuals/docs/user/u4.51.03.html) |
| Derived fields | `CALC_CHAMP` | Computes stresses, element forces, equivalent stress, and nodal forces. | [U4.81.04 CALC_CHAMP](https://biba1632.gitlab.io/code-aster-manuals/docs/user/u4.81.04.html) |
| MED result file | `IMPR_RESU(FORMAT='MED')` | Writes `study.rmed` for visualization and artifact review. | [U4.91.01 IMPR_RESU](https://biba1632.gitlab.io/code-aster-manuals/docs/user/u4.91.01.html) |
| Parseable CSV tables | `CREA_TABLE`, `IMPR_TABLE` | Writes `study_depl.csv`, `study_effo.csv`, `study_reac.csv`, and `study_sieq.csv`. | [U4.91.03 IMPR_TABLE](https://www-mdp.eng.cam.ac.uk/web/CD/engapps/aster_docs/UDocs-HTML/U49103e/U49103e.pdf.html) |
| Runtime execution | `run_aster` / `.export` | Executes studies from Code_Aster export files. | [run_aster package](https://codeaster.readthedocs.io/en/latest/devguide/run_aster/run_aster.html) |

Wind is deliberately narrow today. Code_Aster U4.44.01 documents
`FORCE_POUTRE(TYPE_CHARGE='VENT')` for beam modelizations; Tuba emits
`AFFE_CHAR_MECA_F` with constant `FORMULE` concepts for the wind components
because the current runtime accepts function/formula values for this VENT path.
The same command page documents `FORCE_TUYAU` with pressure (`PRES`) for
`TUYAU_3M` / `TUYAU_6M`, not as a wind line-load command, so Tuba rejects
`TUYAU_3M` wind rather than approximating it with `FORCE_NODALE`.
Equivalent-stress (`SIEQ_ELNO`) output is emitted only for studies with pipe
elements; pure beam/bar/cable studies return displacement, element-force, and
reaction artifacts without inventing a Von Mises stress table.

When adding solver features, update this table in the same change as the
writer. That keeps Tuba's command generation tied to Code_Aster documentation
instead of local memory.

## Shipped Feature Inventory

### Modeling

- Pipe-native `TubaModel` source model.
- Materials with elastic, density, thermal expansion, and allowable stress data.
- Pipe, bar, cable, rectangular, and I-beam sections.
- Nodes, elements, supports, load cases, operations, operation fields, obstacles,
  groups, attributes, insulation specs, placement frames, and mixed-analysis
  records.
- Cursor builder for pipe routes, stored 3D bends, beams, bars, and cables.
- Route/station metadata on generated pipe elements.
- JSON serialization and JSON-schema validation.
- Model validation for references, sections, groups, placements, attributes,
  operation fields, route/station metadata, bend geometry, and mixed records.

### Code_Aster

- 1D pipe/beam/bar/cable Code_Aster export.
- `TUYAU_3M` pipe modelization.
- Bend meshing from stored `BendGeometry`, with generated analysis nodes and
  sidecar lineage.
- Local uniform pressure and temperature fields compiled into Code_Aster mesh
  groups.
- Beam-modeled wind fields compiled into `FORCE_POUTRE(TYPE_CHARGE='VENT')`
  with constant `FORMULE` components; `TUYAU_3M` wind and `FORCE_NODALE` wind
  shortcuts are not implemented.
- `.mail`, `.comm`, `.export`, `study_manifest.json`, and
  `study_tuba_fem.json` generation.
- Runtime discovery/execution through WSL, command runner, Python bridge, or
  Docker fallback.
- CSV and optional RMED artifact parsing into `FEAResults`.
- `SIEQ_ELNO` stress tables are generated only for pipe-containing studies;
  beam-only studies keep real displacement, force, and reaction results without
  fabricated stress output.
- Notebook helper that loads real artifacts or runs Code_Aster when configured.
- Mixed STEP/pipe study export for the first pipe-to-solid-port slice.

### Results And Review

- `FEAResults` for displacements, reactions, element forces, stresses, and
  plotting.
- `AnalysisStudy`, `AnalysisMesh`, and `ResultState` provenance records.
- Cold, operating, and visual deformed geometry states.
- Physical deformed envelopes for clash checks and review.
- PyVista notebook/quick-look plotting.
- Web-scene bundle export for the Three.js viewer.
- Static reports, scene diffs, issue overlays, route review overlays, BCF
  exchange, and viewer smoke tests.

### Routing And Engineering Helpers

- Deterministic 3D grid A* routing.
- Network routing with conflict repair.
- Expansion-aware U-loop candidate generation.
- Route cost model and route reports.
- Solver-loop export/scoring for selected candidates, including imported
  displacement, reaction, and operating-clearance gates when real results exist.
- Physical quantities, insulation/wind metadata, load-path reports, rule checks,
  Trimesh clash checks, IFC export/import, and optional ada-py bridge.
- ASME B31.3 evaluator with the implemented safe B31J-compatible subset.

## Current Gaps

| Gap | Status | Next useful action |
|---|---|---|
| Real runtime proof | The library supports runtime discovery, but a fresh production solve requires a configured Code_Aster runner. | Run `python -m tuba.solver.code_aster_doctor --check`, then `TUBA_RUN_CODE_ASTER_INTEGRATION=1` integration tests on a solver machine. |
| Linear/piecewise operation fields | Uniform fields are supported; linear temperature by route/station is exported as per-element midpoint values. Pressure, wind, and piecewise profiles still fail before export. | Add one end-to-end writer slice per remaining profile shape, with result import and notebook proof. |
| Wind beyond beam-modeled elements | Wind currently works only for beam-modeled elements that can use `FORCE_POUTRE(TYPE_CHARGE='VENT')`. `TUYAU_3M` wind is rejected, and `FORCE_NODALE` is not used as a production pipe-wind shortcut. | Extend only when the chosen Code_Aster pipe modelization has a documented distributed-load command. |
| Seismic loads | Not implemented. Code_Aster has dedicated seismic commands, but Tuba does not yet have the model, writer, parser, or routing/compliance slice. | Add as a full vertical slice: model field, command writer, artifact import, compliance/routing use. |
| B31J tee/branch factors | Blocked by source-data rights. | Use licensed ASME B31J text or authorized user-provided tables. Do not infer coefficients from secondary sources. |
| Mixed STEP solve/import/display | Mixed export exists for the first pipe-to-solid-port slice. | Prove real mixed solve, import artifacts, and display results through the same review paths. |
| `_write_comm(...)` size | Command ordering is correct but concentrated. | Move only repeated load/support compilation to helpers. Do not create a generic solver DSL until duplication forces it. |

## What Not To Do

- Do not present `.comm`, `.mail`, or `.export` generation as a completed
  engineering evaluation.
- Do not display stress, displacement, reaction, compliance, or operating-state
  clash results from mock or hand-built values in user-facing workflows.
- Do not vendor ada-py code into Tuba core.
- Do not add a third visualization surface.
- Do not expand roadmap DSL examples into current-code docs unless the methods
  exist on `TubaModel` or `PipingBuilder`.

## Recommended Next Architecture Work

1. Prove the real Code_Aster runtime on the target machine with the doctor and
   integration smoke.
2. Pick one missing load/profile at a time and implement it end to end:
   model record, validation, Code_Aster command, result artifact, review output.
3. Keep `_write_comm(...)` as the Code_Aster command-order owner, but continue
   extracting repeated load compilers into small helpers.
4. Treat mixed STEP as export/handoff until real solve/import/display is proven.

The current architecture mostly needs runtime proof and disciplined feature
slices, not a new framework.
