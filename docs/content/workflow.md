# Workflow

The current Tuba v4 engineering sequence is:

```text
Tuba model -> Code_Aster solve -> imported artifacts -> processed result review
```

![Validated model geometry before solving.](assets/figures/tutorial_model.png)

![PyVista quick-look of imported Code_Aster deformation and stress.](assets/figures/pyvista_deformed_stress.png)

## Execution sequence

1. Author through `model.pipe(...)` and other model APIs.
2. Run `model.validate()` and fix the complete error batch.
3. Use `export_analysis_study(...)` to write the `.mail`, `.comm`, `.export`, manifest, and sidecar handoff files.
4. Execute Code_Aster through the configured runtime.
5. Import the produced CSV/RMED artifacts into a provenance-bearing `AnalysisRun`, whose persistent authority is `ResultState` and whose transient numerical carrier is `FEAResults`.
6. Build engineering review records and display the imported state through one of the two visualization paths.

`solve_exported_study(...)` performs execution and verified import while preserving the inspectable export boundary. `model.solve()` is the convenience path; both return `AnalysisRun`.

```python
from pathlib import Path

from tuba import Model
from tuba.solver.aster import CodeAsterSolver

model = Model(project_name="Demo")
model.add_material("Steel", E=210e9, nu=0.3, rho=7850.0, alpha=12e-6)
model.add_pipe_section("DN100", OD=0.1143, WT=0.00602)

with model.pipe(section="DN100", material="Steel", route="P-100") as pipe:
    pipe.start([0.0, 0.0, 0.0], support="anchor")
    pipe.run(2.0)
    pipe.bend_to([2.0, 1.0, 0.0], radius=0.8, plane_normal=[0.0, 0.0, 1.0])
    pipe.run(2.0)
    pipe.end(support="anchor")

model.define_operation(
    "Hot",
    gravity=True,
    pressure=1.6e6,
    temperature=180.0,
    ref_temperature=20.0,
)
model.validate()

solver = CodeAsterSolver(
    work_dir="runs/demo_hot",
    exec_method="wsl",
    wsl_distro="Ubuntu",
)
study = solver.export_analysis_study(model, "Hot", Path("runs/demo_hot"))
run = solver.solve_exported_study(model, study)
```

Export success is not solve success. If required result tables are missing or empty, read the runner logs and treat the evaluation as incomplete.

## Engineering review records

Reporting is renderer-independent. It packages records supplied by the caller and does not run Code_Aster:

```python
from tuba.reporting import build_engineering_review, write_engineering_review

review = build_engineering_review(
    model,
    studies=[run.study],
    result_states=[run.result_state],
)
write_engineering_review(review, "runs/demo_hot/review")
```

FE stress remains labelled `FE Von Mises (not piping-code stress)`. Piping-code compliance is available only when an explicit compliance report is supplied.

## Exactly two visualization paths

Both paths consume real imported results. Choose one path per notebook or example.

### PyVista quick-look and export

`tuba/plotting/` is wired to `FEAResults.plot_*()`. It reads real `.rmed` artifacts and supports notebook inspection plus PLY, glTF, and Blender export.

```python
run.results.plot_deformed_stress(
    deform_scale=40.0,
    model=model,
    jupyter_backend="html",
)
```

### Reviewable web scene

`tuba/visualization/` and `viewer/` are the shareable review path. Python writes the JSON scene and engineering-review contracts; Three.js renders them without performing engineering calculations.

```python
from tuba.visualization import build_visualization_scene, write_scene_bundle

scene = build_visualization_scene(
    model,
    analysis_meshes=[run.analysis_mesh] if run.analysis_mesh is not None else [],
    result_states=[run.result_state],
)
write_scene_bundle(scene, "runs/demo_hot/review_scene")
```

`write_engineering_review_with_scene(...)` can place review tables beside the same scene bundle. That adapter combines reporting with the existing web-scene path; it does not create a third visualization path.

Legacy scene-only bundles remain displayable without implying that missing review evidence exists. Neither visualization path makes Code_Aster optional.
