# Developer guide

Tuba is split by ownership: model authoring, Code_Aster export/execution/import, solver evidence, reporting, and the two result-display paths. Put changes at the lowest shared boundary that owns the behavior.

## Module map

| Module | Owns |
| --- | --- |
| `tuba.model` | Materials, sections, nodes, elements, supports, loads, operations, and serialization |
| `tuba.builder` | Cursor-based pipe authoring through `model.pipe(...)` |
| `tuba.validation` | Pre-export model invariants |
| `tuba.schema` | Model and patch JSON schemas |
| `tuba.routing` | Requests, grid search, expansion candidates, network routing, solver-loop review, reports |
| `tuba.solver.aster` | Code_Aster study export, external execution, and result parsing |
| `tuba.solver.aster_mesh` | `study.mail` mesh generation and mesh provenance |
| `tuba.solver.aster_comm` | `study.comm` command generation |
| `tuba.analysis` | Studies, analysis meshes, result states, RMED, notebook and artifact import helpers |
| `tuba.reporting` | Renderer-independent engineering review records and tables |
| `tuba.plotting` | PyVista quick-look and export |
| `tuba.visualization` | JSON scene contract and scene bundle writing |
| `viewer/` | Three.js review renderer; no engineering calculation |
| `tuba.compliance` | ASME B31.3 evaluation and B31J factors |
| `tuba.clash`, `tuba.rules` | Geometric clash and rule checks |
| `tuba.quantities`, `tuba.load_path` | Quantity takeoff, wind loads, and load-path analysis |
| `tuba.external` | IFC and BOM boundaries |

The dependency direction is:

```text
tuba.builder -> tuba.model -> tuba.solver.aster -> tuba.analysis
     routing -> adapter ----^                         |-> tuba.plotting
                                                       -> tuba.reporting
                                                       -> tuba.visualization -> viewer/
```

Routing proposes geometry; `tuba.routing.adapter` owns explicit model mutation. Solver output enters review only through artifact parsing and `ResultState` creation.

## Change ownership

| Stage | Owns |
| --- | --- |
| Authoring | Builder methods, route requests, operations, validation |
| Evidence | Solver runtime, raw artifacts, parsers, identity, hashes, provenance |
| Review | Reporting, plotting, web scenes, viewer metadata |

Do not let a review component infer evidence that the solver/artifact boundary did not supply.

## Core records and invariants

| Record | Important contract |
| --- | --- |
| `Material` | Elastic, density, thermal-expansion, and optional allowable-stress data |
| `PipeSection` | `OD > 0`, `WT > 0`, and `2 * WT < OD` |
| `Node` | Finite global 3-vector; nearby points can be deduplicated |
| `Element` | Existing node, section, and material references; non-zero length |
| `BendGeometry` | True arc metadata retained separately from the FE chord |
| `Operation` / `LoadCase` | Operation compiles to the case consumed by the writer |
| `AnalysisRun` / `ResultState` / `FEAResults` | One provenance-bearing run; persistent authority in result state and transient numerical access in FEA results |

Model JSON must round-trip through `model.to_dict()` / `Model.from_dict(...)` and `MODEL_SCHEMA_V4`. Incremental edits use `ModelPatch` and `ModelTransaction` so reviewed changes can be applied atomically.

## Solver file map

| File | Meaning | Completed result? |
| --- | --- | --- |
| `study.mail` | Code_Aster mesh input | No |
| `study.comm` | Code_Aster model, load, solve, and table commands | No |
| `study.export` | Runner handoff | No |
| `study_manifest.json` | Study metadata and generated-file inventory | No |
| `study_tuba_fem.json` | Solver-label and mesh-reference mapping | No |
| `study_depl.csv` | Solver displacement table | Yes, when produced by Code_Aster |
| `study_effo.csv` | Solver internal-force table | Yes, when produced by Code_Aster |
| `study_reac.csv` | Solver reaction table | Yes, when produced by Code_Aster |
| `study_sieq.csv` | Solver equivalent-stress table | Yes, when produced by Code_Aster |
| `study.rmed` | MED result artifact | Yes, when produced by Code_Aster |
| `study_execution.json` | Attested solver identity, solve timestamp, and exact artifact hashes | Evidence record, not a result table |

Export-only files are useful development and diagnostic surfaces. They are not a completed engineering evaluation.

## Extension seams

| Change | Start here | Required sibling work |
| --- | --- | --- |
| Builder command | `tuba.builder.PipingBuilder` | Create model records through public methods and preserve route/station metadata |
| Section type | `tuba.model` | Geometry profile, schema/round-trip, Code_Aster mapping, validation, and `scripts/docs/generate_section_drawings.py` |
| Solver execution behavior | `tuba.solver.aster`, `tuba.solver.code_aster_runtime` | Keep external Code_Aster execution and common artifact parsing |
| Result quantity | Artifact parser / `ResultState` | Reporting tables, scene fields, validation, and both consumers where applicable |
| Scene feature | `tuba.visualization` | Preserve the versioned JSON contract and viewer compatibility |

Do not introduce a third visualization stack. `tuba.plotting` remains the PyVista quick-look/export path; `tuba.visualization` plus `viewer/` remains the reviewable web-scene path.

## How to extend autorouting

Keep search, scoring, review, and model mutation separate.

| Change | Owner | Verification |
| --- | --- | --- |
| Request field | `tuba.routing.types` | Serialization and type tests |
| Obstacle or space behavior | `tuba.routing.grid`, `tuba.routing.spaces` | Occupancy and route tests |
| Cost term | `tuba.routing.cost_model` | Term calculation and selected-candidate ordering |
| Loop family | `tuba.routing.expansion`, `tuba.routing.hybrid` | Geometry, envelope, and network-conflict tests |
| Solver acceptance gate | `tuba.routing.solver_loop` | Deterministic unit fixture plus real Code_Aster integration when solver evidence is required |
| Review output | `tuba.routing.report`, `tuba.visualization` | Markdown/JSON and scene-contract tests |

## Test commands

Run the smallest focused test first, then the affected suite:

```powershell
uv run python -m pytest tests\test_tuba_core.py -q
uv run python -m pytest tests\test_code_aster_docs.py tests\test_static_site_docs.py -q
uv run --group docs zensical build --clean --strict
```

Viewer changes require the viewer suite and browser-visible checks:

```powershell
& "C:\Program Files\nodejs\npm.cmd" --prefix viewer test
& "C:\Program Files\nodejs\npm.cmd" --prefix viewer run build
```

Opt in to a real solver run when the change depends on Code_Aster execution:

```powershell
$env:TUBA_RUN_CODE_ASTER_INTEGRATION = "1"
uv run python -m unittest tests.test_code_aster_real_smoke -v
```

The self-hosted `code-aster-integration` jobs run on trusted pushes to `main`
and beta release dispatches, never on pull requests. They run the real solver
smoke and reference cases, refresh `code-aster-review`, `support-rack-review`,
`autorouted-expansion-loop`, and `pipe-tee-volume-review`, then pass the fresh
artifacts through the strict Pages assembler. A failed solve, attestation,
bundle profile, or Pages build blocks the gate and beta release.

Unit fixtures may remain portable. Integration claims require the real backend.

## Documentation figures

Figure generators use live Tuba objects but do not run the solver:

```powershell
uv run python scripts\docs\generate_figures.py
uv run python scripts\docs\generate_section_drawings.py
```

The deformed-stress figure loads committed Code_Aster artifacts with `run_solver=False`; it does not synthesize results.

## Contributing

Read [CONTRIBUTING.md](https://github.com/jgwagenfeld/Tuba_v4/blob/main/CONTRIBUTING.md) before changing public behavior. It defines what counts as Code_Aster-backed evidence, how export-only examples are labelled, and which visualization paths are supported.

Changes that display stress, displacement, reaction, compliance, or operating-state output must use real Code_Aster-backed artifacts or stop with a clear runtime requirement.
