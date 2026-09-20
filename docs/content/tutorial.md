# Build and solve a first pipe

This tutorial builds a pipe model, runs Code_Aster, and displays the imported results:

```text
model -> validate -> export -> Code_Aster solve -> import -> processed result review
```

The exported study files are a handoff. A `.comm`, `.mail`, or `.export` file does not prove that Code_Aster ran or that any stress, displacement, reaction, or compliance result exists.

## What you are building

![The tutorial pipe in the Tuba viewer: geometry and supports, before any solve.](assets/figures/tutorial_model.png)

The first figure is model geometry only. After a real Code_Aster solve, the review scene shows the same model with its imported results:

[![The solved tutorial pipe in the Tuba viewer, coloured by FE Von Mises stress, with support reactions.](https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/code-aster-review.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=code-aster-review)

## Prerequisites

```powershell
.\.venv\Scripts\python.exe -m pip install ".[course]"
.\.venv\Scripts\python.exe -m tuba.solver.code_aster_doctor --check
```

If the doctor is blocked, stop after export inspection or load an existing solved artifact directory. See [Setup](setup.md).

## Build, solve, and publish the review bundle

```python
from pathlib import Path

from tuba import Model
from tuba.solver.aster import CodeAsterSolver
from tuba.visualization import build_visualization_scene, write_scene_bundle

work_dir = Path("runs/first_pipe_operating")

model = Model(project_name="VizGalleryDemo")
model.add_material(
    "Steel",
    E=210e9,
    nu=0.3,
    rho=7850.0,
    alpha=12e-6,
    allowable_stress={20.0: 137e6, 150.0: 127e6},
)
model.add_pipe_section("DN100", OD=0.1143, WT=0.00602, corrosion_allowance=0.001)

with model.pipe(section="DN100", material="Steel") as pipe:
    pipe.start([0.0, 0.0, 0.0], support="anchor")
    pipe.run(3.0)
    pipe.add_support(type="guide")
    pipe.bend(radius=0.30, angle=90.0, plane="XY")
    pipe.run(2.0)
    pipe.add_support(type="rest")
    pipe.bend(radius=0.30, angle=90.0, plane="XZ")
    pipe.run(3.0)
    pipe.end(support="anchor")

model.define_load_case(
    "Operating",
    gravity=True,
    pressure=1.5e6,
    temperature=150.0,
    ref_temperature=20.0,
)
model.validate()

solver = CodeAsterSolver(
    work_dir=str(work_dir),
    exec_method="wsl",
    wsl_distro="Ubuntu",
)
study = solver.export_analysis_study(model, "Operating", work_dir)
run = solver.solve_exported_study(model, study)

scene = build_visualization_scene(
    model,
    analysis_meshes=[run.analysis_mesh] if run.analysis_mesh is not None else [],
    result_states=[run.result_state],
)
write_scene_bundle(scene, work_dir / "review_scene")
```

This is the model in both figures above and in the linked review scene below. The staged `CodeAsterSolver` path keeps export, execution, and import independently inspectable. `model.solve()` is the shorter convenience when that separation is not needed.

## Units

Tuba model values use SI units.

| Quantity | Unit | Example |
| --- | --- | --- |
| Length, diameter, wall thickness | m | `OD=0.1143` means 114.3 mm |
| Pressure | Pa | `1.5e6` means 1.5 MPa |
| Temperature | deg C | `150.0` |
| Force | N | Solver reactions |
| Young's modulus and stress | Pa | `E=210e9` means 210 GPa |
| Thermal expansion | 1/K | `alpha=12e-6` |

## Expected files

| Artifact | Created at | Result evidence? |
| --- | --- | --- |
| `study.mail` | Export | No: solver mesh input |
| `study.comm` | Export | No: solver command input |
| `study.export` | Export | No: runner handoff |
| `study_manifest.json` | Export | No: study and provenance metadata |
| `study_tuba_fem.json` | Export | No: solver-name mapping sidecar |
| `study_depl.csv` | Successful solve | Yes: displacement table |
| `study_effo.csv` | Successful solve | Yes: internal-force table |
| `study_reac.csv` | Successful solve | Yes: reaction table |
| `study_sieq.csv` | Successful solve | Yes: equivalent-stress table |
| `study.rmed` | Successful solve when requested | Yes: MED result artifact |
| `review_scene/` | After artifact import | Review surface for the imported state |

Missing or empty required result rows indicate a failed or incomplete run.

## Review controls

The browser rail is one column of sections, not a set of tabs; see [visualization architecture](architecture/visualization.md) for what each holds. What colours the scene - a model property or a solver field - is chosen from the pinned **Colour by** control, above the result refinements, the layer list, and the issue list. The review's tables live in the generated report that the header links to.

Those controls live in three places, not in a section of their own. Load-case and result-component selection, and physical or visual deformation, are with the result refinements. Camera presets and zoom sit on the viewport itself, beside the orientation gizmo. The six-plane section box is behind **Section box** at the foot of the rail. Section inputs clip crossing geometry in the renderer; they are not object-level hide/show filters.

[Open the Code_Aster review scene](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=code-aster-review).

## Notebook-safe variant

```python
from tuba.analysis.code_aster_notebook import load_or_run_code_aster_results

run = load_or_run_code_aster_results(
    model,
    "Operating",
    "examples/code-aster-review/evidence/Operating",
    run_solver=True,
    exec_method="wsl",
    wsl_distro="Ubuntu",
)
results = run.results
```

With `run_solver=False`, the directory must already contain real Code_Aster artifacts.

## Completion criteria

The tutorial is complete only when Code_Aster has produced result artifacts and Tuba has imported them as an `AnalysisRun` with a persistent `ResultState`. Export-only output is useful for diagnostics and handoff review, but it is not an engineering evaluation.

## The notebooks

There were fourteen. Twelve taught what this page, [Modeling](modeling.md),
[Autorouting](autorouting.md) and the [Examples](examples.md) gallery already
teach better - several by hand-copying a gallery model and reading that
gallery's own evidence, so one geometry change had to be chased through three
copies. Two remain, because nothing else in the repository runs what they run.

```powershell
.\.venv\Scripts\python.exe -m pip install ".[course]"
```

| Notebook | What it runs that nothing else does |
| --- | --- |
| `04_visualization_gallery.ipynb` | PLY, glTF, Blender-script and standalone-HTML export of a solved result |
| `07_bim_data_exchange.ipynb` | An IFC4 export, an `ifcopenshell` inspection, and a re-import back into a `TubaModel` |

```powershell
.\.venv\Scripts\jupyter.exe lab notebooks\04_visualization_gallery.ipynb
```

Both load committed Code_Aster artifacts by default and solve nothing unless
you ask them to. For the ordinary review path - geometry, deformed shape,
stress and support loads - open the [gallery](examples.md) in the browser
instead: it is the same evidence, in the reviewer the documentation figures are
shot in.
