# Workflow

The current Tuba v4 engineering sequence is:

```text
Tuba model -> Code_Aster solve -> imported artifacts -> processed result review
```

![Validated model geometry in the Tuba viewer, before solving.](assets/figures/tutorial_model.png)

[![The same model after the Code_Aster solve, with imported stress and support reactions in the Tuba viewer.](https://jgwagenfeld.github.io/Tuba_v4/viewer/gallery/code-aster-review.png)](https://jgwagenfeld.github.io/Tuba_v4/viewer/?bundle=code-aster-review)

## Projects in Studio, the CLI and agents

A project is an ordinary folder containing authored `model.py`, `study.py`,
optional `units/` and `geometry/`, and Code_Aster evidence in `evidence/`.
Python remains the engineering definition, including functions and imports.

For collaborators, [Share and open a project](project-sharing.md) covers the
complete source/CAD folder, Studio's folder chooser, generated meshes, optional
saved evidence and portable result-review bundles.

Run `python -m tuba.cli_studio` for **Open Folder**, **New Project** and
**Recent Projects**, or pass a project folder directly. The Studio **Projects**
link returns to the chooser. Open preserves authored files; New requires a new
or empty folder. Recent folders are disposable local state, never the active
target for an agent. Each full folder path gets its own bundle and server;
opening a running project reuses its discovered URL, including a random port.

Use the CLI for scripts and batch evaluation:

```bash
python -m tuba.project "/path/to/project" --output "/path/to/review"
```

For a local agent, launch `python -m tuba.mcp.server` as an MCP **stdio**
subprocess from the same Tuba environment. Bind it explicitly with
`init_session(file_path="/path/to/project/model.py", load_existing=True)`.
Author procedural Python normally; use MCP for `inspect_model`, `verify_model`,
`check_clashes`, construction units and `solve_model`. Inspection reloads changed
Python, helpers and CAD. Rebind before applying mutations to externally changed
source; merely inspecting never grants permission to overwrite it.

Studio, MCP and CLI solves all use the shared project verification gate before
changing staging or evidence: structural validation, cold-model clashes, rules
and the project script style check. Blocking findings prevent evaluation even
with `--force` or `solve_model(force=True)`; force only reruns otherwise reusable
evidence. Advisories remain visible in the verification report.

MCP and CLI solves both use `study.py`, its solver options and checks, the
project solve claim, and the same attested evidence. `solve_model(load_case=...)`
validates the selected study operation and evaluates all study operations
together. An open Studio imports externally promoted evidence into Review.
The `.tuba/studio.json` pointer advertises the actual local endpoint, which is
accepted only after checking the live server's folder and session identity.
Studio saves compare the loaded source revision; a conflict preserves both
the newer disk source and the unsaved editor draft.

The MCP adapter uses the official stable SDK 2 API (locked to 2.2.0).
It serves current and earlier MCP protocol clients. Use the qualified project environment's Python
in the agent configuration, rather than relying on whichever `python` is on PATH.

## Execution sequence

1. Author through `model.pipe(...)` and other model APIs.
2. Run `model.verify()` and fix the blocking errors; it composes structural validation, the join-aware cold-model clash check, and the rule engine. `model.validate()` alone is the structural subset.
3. Use `export_analysis_study(...)` to write the `.mail`, `.comm`, `.export`, manifest, and sidecar handoff files.
4. Execute Code_Aster through the configured runtime.
5. Import the produced CSV/RMED artifacts into a provenance-bearing `AnalysisRun`, whose persistent authority is `ResultState` and whose transient numerical carrier is `FEAResults`.
6. Build engineering review records and display the imported state through one of the two visualization paths.

`solve_exported_study(...)` performs execution and verified import while preserving the inspectable export boundary. `model.solve()` is the convenience path; both return `AnalysisRun`.

Activate the environment described in [Setup](setup.md) before running this
example. The solver uses that environment's configured runtime.

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

solver = CodeAsterSolver(work_dir="runs/demo_hot")
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
    analysis_runs=[run],
)
write_engineering_review(review, "runs/demo_hot/review")
```

FE stress remains labelled `FE Von Mises (not piping-code stress)`.

The printable report starts with governing values across the published cases,
including the winning case, entity and element end. Its model overview shows
undeformed authored centerlines with short drawing keys mapped to the exact
element, node and support IDs; canonical bend geometry is retained. Dimensioned
SVG section plates use each scheduled section's actual geometry, including
bores and rolled I-section fillets. Profile dimensions are labelled in mm.

The offline report uses Tuba's graphite/teal palette and bundled fonts. Detailed
tables can be expanded on screen and are all included when printing. JSON and
CSV retain full study and result-state lineage.

Equilibrium checks compare calculated applied loads with imported Code_Aster
reactions in global axes, with moments about `(0, 0, 0)` metres. Each of the six
components states its residual and numerical tolerance. Nodal loads, gravity
(including insulation, contents and support masses), and uniform line loads are
covered for linear 1D studies. Loaded bends require the authoritative analysis
mesh. Pressure, wind, contact/load-path, cable, spring/attached-support and
volume/mixed studies state why balance is **not evaluated** until complete
load/reaction recovery is available. A numerical balance is not a design-code
check. The `equilibrium.csv` download retains study and result-state lineage.

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
from tuba.visualization import SceneRequest, build_visualization_scene, write_scene_bundle

scene = build_visualization_scene(
    SceneRequest(model=model, analysis_runs=[run], include_analysis_mesh=True)
)
write_scene_bundle(scene, "runs/demo_hot/review_scene")
```

`write_engineering_review_with_scene(...)` can place review tables beside the same scene bundle. That adapter combines reporting with the existing web-scene path; it does not create a third visualization path.

Legacy scene-only bundles remain displayable without implying that missing review evidence exists. Neither visualization path makes Code_Aster optional.

## Tuba Studio and Project Structure

For interactive design, Tuba v4 provides a live engineering environment with real-time Three.js visualization, Code_Aster `.comm` compilation, and solver execution.

### Project Layout

A project directory separates structural authoring from FEA evaluation:

- **`model.py`:** Authored parametric geometry, routes, sections, materials, supports, and operations.
- **`study.py`:** FEA configuration declaring `LOAD_CASES = ("Operating", ...)`, solver options (`POU_D_T`, `TUYAU_3M`), and review builders.

### Running Tuba Studio

Launch the live studio on any project directory:

```bash
python -m tuba.cli_studio examples/line-load-studio
```

- **Live Scene Preview:** Changes saved in `model.py` are hot-reloaded automatically via WebSocket.
- **Code_Aster `.comm` Inspector:** The tab strip generates and previews the exact Code_Aster commands that will be executed for each load case.
- **Solve Integration:** Clicking **Solve** executes Code_Aster and automatically transitions the viewer to the solved engineering review bundle.

### Mesh refinement and convergence

[Import STEP and review its mesh](step-meshing.md) covers authoring interfaces,
units and refinements. CLI and MCP use the same native worker as Studio:

```bash
python -m tuba.project.mesh mesh "/path/to/project" --output "/path/to/new-mesh-output"
python -m tuba.project.mesh convergence "/path/to/project" --output "/path/to/new-comparison-output"
```

MCP exposes `generate_mesh(output_dir=...)` and `run_mesh_convergence(output_dir=...)`.
Both require a new output folder. Diagnostic meshes are unsolved; convergence
requires the study configuration and real Code_Aster, and independently verifies
its level artifacts. Ordinary project evidence and review stay separate.

The [authored spool project](https://github.com/jgwagenfeld/Tuba_v4/blob/main/examples/mesh-refinement-review/README.md)
demonstrates global/local sizing and `MESH_CONVERGENCE` in `study.py`. In Build,
Mesh review distinguishes requested-size preview from **Generate mesh** (actual
unsolved diagnostic cells) and **Run convergence** (verified Code_Aster levels).
Save sizing changes in Python, then explicitly regenerate. Source changes make
old artifacts stale; geometric quality and measured solver changes do not imply
accuracy or compliance. The example includes independent cantilever checks and
an external viewer-build command for source checkouts.

For solids and shells, Tuba translates requested sizes and refinements into
native Gmsh fields. Selected regions and 1D members keep independent sizing;
Gmsh's default curvature setting and volume-meshing algorithm are retained. CAD-face refinement uses Gmsh's
sampled distance to the finite face (100 samples per parametric direction),
with the requested face size applied directly on the selected face. The
requested-size preview uses exact CAD distances. Inspect the generated
mesh and run Code_Aster convergence levels to assess the resulting discretization.

### Browser geometry editing

The public gallery also accepts `model.py` edits in **Build**. **Update geometry**
executes Tuba Python in the browser and displays an unsolved scene through the
same web viewer. **Review** retains the published Code_Aster evidence and marks
it outdated after edits. Use a local Tuba installation with Code_Aster to
evaluate the downloaded script. See [browser setup and limits](setup.md#try-a-model-in-the-browser).

### Static Scene Inspection

To review a pre-compiled `.json` scene bundle without running a studio server:

```bash
python -m tuba.visualization.viewer .build/line-load-demo-scene
```

### Publish a static review

From a source checkout with Tuba installed, solve the project first, install the
packaged viewer into a dedicated web folder, then publish the completed review:

```bash
python -m tuba.project /path/to/project --output /path/to/project-review
python scripts/deploy_viewer.py viewer /path/to/web/tuba
python scripts/deploy_viewer.py bundle /path/to/project-review /path/to/web/tuba
```

The viewer shell is installed once; run `viewer` again after a Tuba update.
Repeat `bundle` after each solve. It also accepts a bundle folder containing
`scene.json` directly, such as Studio's solved review output. The complete
bundle is copied, including the printable `index.html` report and solver
evidence. A replacement removes stale files from that registered bundle;
other bundles and existing gallery metadata are preserved. Publish one bundle
at a time to each web folder.

Serve that folder with your static web server. For a local trial:

```bash
python -m http.server 8000 --bind 127.0.0.1 --directory /path/to/web/tuba
```

Open `http://127.0.0.1:8000/`. One registered bundle opens directly; multiple
bundles show a gallery. `?bundle=<bundle-id>` opens a named review. The id comes
from `review.json`'s `package_id` after removing `review:` and must be a safe
folder name. The publisher does not solve, validate new engineering results,
or provide Studio's local authoring and execution services. Results come from
the completed Code_Aster workflow above.

### AI & Headless Integration (MCP)

For external agents (Claude Desktop, Cursor) operating without terminal access:

```bash
python -m tuba.mcp.server
```

Provides standardized MCP tools for join-aware clash detection, model queries, construction unit verification, and solver dispatch.

Bind to an existing project's `model.py` with `init_session(..., load_existing=True)`;
MCP uses the same folder and evidence as Studio and the project CLI. Follow the
[project handoff instructions](project-sharing.md#use-the-same-folder-through-the-cli-or-mcp)
when the project arrived as a ZIP or was moved to another machine.

### Teach your agent the authoring contract

Tuba ships an agent skill so a coding agent knows how to write `model.py` and
verify it before solving - procedural authoring, the one `model.verify()` gate,
the bend-sign semantics of the fluent builder, and route-endpoint proof.
Install it into your agent harness's skills folder:

```bash
python -m tuba.skills --target ~/.config/opencode/skills   # or ~/.claude/skills, ~/.codex/skills
python -m tuba.skills --list                               # show what this Tuba version ships
```

## Geometry and model reports

Model geometry and attributes such as insulation can be used for physical
envelopes, geometric clash checks, quantity take-off, route cost, load-path
reports, rules, and BOM export without running Code_Aster.

```bash
python -m examples.future_ready_semantic_workflow
```

These outputs describe the model; operating-state checks require imported
Code_Aster results.
