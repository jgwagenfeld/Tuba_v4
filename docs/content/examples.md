# Examples

Examples are labelled by evidence status so geometry, handoff files, and solved engineering results cannot be confused.

## Code_Aster review scene — solved engineering review

**Status: SOLVED / IMPORTED.** The published bundle contains an attested Code_Aster run, imported result tables, analysis mesh, result fields, review records, and scene geometry.

[Open the Code_Aster review scene](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=code-aster-review).

The browser performs no engineering calculation. It displays the preserved Python-produced review and scene contracts.

## Support-rack scene — solved engineering review

**Status: SOLVED / IMPORTED.** This Code_Aster-backed bundle shows the pipe,
beam rack, anchors and rests, 1D analysis mesh, reactions, deformation, stress,
and support-to-rack load paths.

[Open the solved support-rack review](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=support-rack-review).

## Autorouted expansion loop — solved engineering review

**Status: SOLVED / IMPORTED.** This bundle retains the selected U-loop and its
route-review metadata, then overlays the attested Code_Aster operating results,
analysis mesh, TUYAU wall sub-points, deformation, forces, and reactions.

[Open the solved autorouted expansion-loop review](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=autorouted-expansion-loop).

## Native 3D pipe tee mesh — unsolved mesh review

**Status: MESH ONLY / UNSOLVED.** Gmsh generates the conformal quadratic
tetrahedral wall mesh. The viewer opens on the authoritative analysis mesh;
the authored pipe tubes remain available as an optional layer but start hidden
so they cannot obscure the tee junction. It contains no Code_Aster result
fields or engineering review.

[Open the unsolved Gmsh tee mesh](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=gmsh-tee-mesh-review).

Generate the bundle directly into the local viewer:

```powershell
uv run python viewer/scripts/make_bundle.py --recipe examples/gmsh_tee_mesh_review.py --name gmsh-tee-mesh-review --force
Set-Location viewer
npm.cmd run dev
```

Select `Gmsh Tee Mesh Review` in the viewer. The recipe also works as a
standalone example with `uv run python examples/gmsh_tee_mesh_review.py`; that
writes `study.med`, `summary.json`, and the browser bundle under `.build/`.

## Native 3D pipe tee — solved engineering review

**Status: SOLVED / IMPORTED.** Gmsh generates one conformal quadratic
tetrahedral wall mesh for the header and branch; Code_Aster solves it as `3D`.
The viewer keeps the design tubes, analysis skin, displacement, terminal
resultants, and FE VMIS separate. FE VMIS is not ASME piping-code stress.

[Open the solved native 3D tee review](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=pipe-tee-volume-review).

The mesh-only recipe uses the following API without claiming solver results:

```python
from examples.code_aster_tee_volume_review import TEE_VOLUME_ELEMENT_IDS, build_tee_volume_model
from tuba.meshing import build_pipe_volume_mesh
from tuba.visualization import build_visualization_scene, write_scene_bundle

model = build_tee_volume_model()
generated = build_pipe_volume_mesh(
    model,
    ".build/tee-mesh/study.med",
    element_ids=TEE_VOLUME_ELEMENT_IDS,
    max_element_size=0.005,
)
scene = build_visualization_scene(model, analysis_meshes=[generated.analysis_mesh])
write_scene_bundle(scene, ".build/tee-mesh/viewer")
```

Run the complete Gmsh -> Code_Aster -> verified result workflow:

```python
from tuba import PipeModelization

run = model.solve(
    operation="Operating",
    pipe_modelization=PipeModelization.SOLID_3D,
    volume_element_ids=TEE_VOLUME_ELEMENT_IDS,
    max_element_size=0.005,
    work_dir=".build/tee-solve",
    exec_method="auto",
)
```

The first call writes analysis input only. The second must find a real Code_Aster runtime and returns an attested `AnalysisRun`; it fails before result display when no runtime is available.

## Imported-component scene — model review

**Status: MODEL REVIEW / NO SOLVER RESULTS.** This bundle demonstrates imported-component geometry, local frames, object selection, and model provenance.

[Open the imported-component model review](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=imported_component_mixed_demo).

## Local examples

Run an example with:

```powershell
.\.venv\Scripts\python.exe examples\<name>.py
```

Tuba-owned benchmark and review outputs default to `.build/`. When no Tuba
command is running, remove all ignored Tuba build output with:

```powershell
git clean -fdX -- .build
```

Canonical Code_Aster artifacts under `notebooks/code_aster_results/` are
committed engineering evidence and are not cleanup targets.

| Example | Evidence status | Purpose |
| --- | --- | --- |
| `demo.py` | **MODEL JSON + STUDY HANDOFF** | Writes `piping_model.json` and Code_Aster input files, then stops before results |
| `autorouting_basic.py` | **ROUTE REPORT** | Applies a selected single-pipe candidate in memory and writes route report files; no study export |
| `autoroute_single_pipe.py` | **ROUTE REPORT + STUDY HANDOFF** | Writes a route report and exports candidate Code_Aster studies without running them |
| `autoroute_network.py` | **NETWORK ROUTE REPORT** | Writes prioritized multi-pipe routing and conflict reports; no study export |
| `autoroute_expansion_loop.py` | **ROUTE REPORT + STUDY HANDOFF** | Writes a hot-line U-loop report and exports candidate studies without running them |
| `operating_state_clash.py` | **STUDY HANDOFF; INTENTIONAL STOP** | Exports one study, then raises until real result artifacts are available |
| `future_ready_semantic_workflow.py` | **BOM + BENCHMARK; COMPUTED MODEL CHECKS** | Writes a BOM CSV and benchmark summary, then prints quantity, route-cost, load-path, and rule results; no solver study or results |
| `imported_component_mixed_system.py` | **MODEL REVIEW SCENE; OPTIONAL STEP HANDOFF** | Writes a model JSON and geometry-only scene; STEP/STP input can also export an unsolved mixed study |
| `realtime_visualization_review.py` | **STUDY HANDOFF; INTENTIONAL STOP** | Exports one study, then raises before writing any result-review scene |
| `gmsh_tee_mesh_review.py` | **GMSH MESH REVIEW; UNSOLVED** | Generates a native 3D tee MED mesh and a web scene with optional design geometry and no solver results |
| `code_aster_artifact_review.py` | **SOLVED ARTIFACT IMPORT + REVIEW BUNDLE** | Imports existing Code_Aster artifacts and writes engineering review and web-scene files |
| `code_aster_tee_volume_review.py` | **SOLVED 3D ARTIFACT IMPORT + REVIEW BUNDLE** | Imports the attested native Gmsh/Code_Aster tee study and writes its volume-result review |

No script in this table launches Code_Aster. Rows labelled **STUDY HANDOFF** write `.comm`, `.mail`, and `.export` inputs only; those files remain incomplete for engineering evaluation until Code_Aster runs and Tuba imports the result artifacts. Report-only and model-review rows do not claim to produce solver handoff or result evidence.

## Autorouting example outputs

```powershell
.\.venv\Scripts\python.exe examples\autoroute_single_pipe.py
.\.venv\Scripts\python.exe examples\autoroute_network.py
.\.venv\Scripts\python.exe examples\autoroute_expansion_loop.py
```

Default outputs under `.build/routing_reports/` can include `route_report.md`, `route_result.json`, and candidate `study.*` files. Reports explain candidate geometry and scoring. Study handoff files alone are not solver evidence.

See [Autorouting](autorouting.md) for the request fields, grid behavior, solver-loop options, U-loop limit, and acceptance boundary.

## Local postprocessing

After [Setup](setup.md) succeeds, open:

```powershell
.\.venv\Scripts\jupyter.exe lab notebooks\10_interactive_postprocessor.ipynb
```

Examples that display stress, reaction, displacement, compliance, or operating-state results must either execute Code_Aster or load real preserved Code_Aster artifacts.
