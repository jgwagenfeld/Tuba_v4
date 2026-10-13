# Share and open a project

A Tuba project is a folder of Python source and the files that source reads.
Share it as one **`.tubaproject` or `.tgz` file** or through version control.
`.tubaproject` and `.zip` use ZIP; `.tgz` and `.tar.gz` use gzip-compressed tar.
Both contain the same readable `manifest.json` and unchanged files under
`project/`. Studio extracts it to a new working folder; Studio, the
CLI and MCP agents then use that same folder.

## Export a project

In local Studio, open **Tools & files → Files & export → Export project**, choose **ZIP (.tubaproject)**
or **Tar + gzip (.tgz)**, then download.
Save editor changes with **Update geometry** first. Source-only is the default;
the dialog shows the file count and size before compression. Select
**Include current verified Code_Aster results** to carry saved evidence too.
Export refuses missing, stale, damaged or unverified results; solve first or
export source-only. It does not solve or generate a mesh during export.

From an activated Tuba environment, on Windows or Linux:

```bash
python -m tuba.project.package export "/path/to/my-project" --output "/path/to/my-project.tubaproject"
python -m tuba.project.package export "/path/to/my-project" --output "/path/to/solved-project.tubaproject" --include-results
python -m tuba.project.package export "/path/to/my-project" --output "/path/to/my-project.tgz"
```

The output suffix selects the format; `.tar.gz` also creates a TGZ package.

Packages exclude `.tuba`, `.build`, `.scratch`, `.tmp`, caches, environments,
dependency folders, common local credential files, previous archives and generated result/mesh output. The
optional results selection includes only the complete attested files for the
current study operations in `evidence/`. Projects remain editable Python;
packages do not include the Tuba installation or the Code_Aster runtime.

## Inspect or unpack a package

Use 7-Zip, `unzip -l my-project.tubaproject`, or Python's ZIP support:

```bash
python -m zipfile -l my-project.tubaproject
python -m tuba.project.package inspect my-project.tubaproject
python -m tuba.project.package unpack my-project.tubaproject --output "/path/to/new-working-folder"
```

On Linux, use native `tar` commands to review a TGZ without opening Studio:

```bash
tar -tzf my-project.tgz
tar -xOzf my-project.tgz manifest.json
tar -xOzf my-project.tgz project/model.py | less
python -m tuba.project.package inspect my-project.tgz
python -m tuba.project.package unpack my-project.tgz --output "/path/to/new-working-folder"
```

`inspect` checks every SHA-256; `unpack` also refuses unsafe paths, links,
case collisions and existing destinations. Neither executes project Python.
Checksums detect damage, not the author's identity. Opening the extracted
project runs its Python, so use trusted project sources.
You may rename a ZIP `.tubaproject` to `.zip` for an archive application.
Tuba detects ZIP or TGZ content when reading a package. An arbitrary archive of a
folder needs Tuba's manifest and layout; create it with Tuba's export command.
Manual extraction leaves the
working project in `project/`; open that folder, not the manifest's parent.
Packages are limited to 20,000 files, 2 GiB compressed and 4 GiB expanded.

Choose what the recipient needs:

| Purpose | Share | Recipient needs |
| --- | --- | --- |
| Edit the model and regenerate its mesh | Project source, helpers and CAD/data files | Tuba and the project's Python dependencies |
| Open saved engineering results in Studio | The project plus complete `evidence/<operation>/` folders | Tuba and the study's result-reading dependencies |
| Recalculate engineering results | The project, with or without saved evidence | Tuba and a configured Code_Aster runtime |
| Inspect a completed review | The complete review bundle | A Tuba viewer, or a browser if the review is hosted |

## What belongs in the project

```text
my-project/
├── model.py
├── study.py
├── units/                     # optional construction units
├── geometry/                  # referenced STEP/STP/STL or other CAD files
├── data/                      # referenced JSON, tables or other inputs
├── README.md                  # dependencies, Tuba revision and run instructions
└── evidence/                  # optional complete saved Code_Aster runs
    ├── Operating/
    └── Hot/
```

`model.py` defines the structure, materials, sections, supports and operations.
`study.py` declares the operations to evaluate, solver options, checks and review
builder. Studio can open a folder with only `model.py` for geometry inspection;
engineering evaluation and review need a suitable study.

`units/`, `geometry/` and `data/` are conventions, not required directory names.
Include every local file read by `model.py`, `study.py` or their imported helpers.
Move helpers imported from another workspace into the project, preserving their
Python package layout, or remove that dependency before sharing. Export rejects
detectable external workspace imports, absolute literal `Path`/`open` inputs,
links and filenames that Windows or Linux cannot preserve. Dynamic imports and
computed paths remain the author's responsibility; open an extracted copy to
verify custom projects. Install additional Python dependencies separately.
The Tuba installation does not supply a source checkout's `examples` package.

Developer/gallery builds can explicitly approve a mapping of archive-relative
names to absolute helper files through `external_sources` on
`plan_project_package`/`export_project_package`. Every referenced external helper
must be named; the planned inventory records its external source. Ordinary
Studio and CLI exports use the project-contained default.

Resolve local assets from the script's location so moving the folder works:

```python
from pathlib import Path

PROJECT = Path(__file__).resolve().parent
STEP_FILE = PROJECT / "geometry" / "component.step"
```

Use `STEP_FILE` in the model's authored import call. Copying a STEP into a folder
does not automatically add a component to the model or define its material,
units, ports or connections. Those remain Python engineering definitions.

Exclude `.tuba/` session pointers and recent-project state, `.build/`, `.scratch/`,
`.tmp/`, environments, dependency folders, caches and old archives. Record the
Tuba revision and any additional dependencies in the project README; use the
[setup guide](setup.md) to prepare the recipient's environment. Inspect the archive's
file list and try opening an extracted copy before distributing it. Gallery
**Project ZIP** downloads contain the files selected by the gallery builder and
omit solver evidence; they are not a general dependency collector for custom
projects.

## Open a package or folder in Studio

Activate the Tuba Python environment, then run:

```bash
python -m tuba.cli_studio
```

Choose a `.tubaproject`, `.zip`, `.tgz` or `.tar.gz` in **Open a shared project**, enter a **new working
folder** and select **Open package**. Existing destinations are refused. The
extracted folder holds the editable project; keep it for later sessions.

For an existing folder, choose **Open Folder**, use **Browse folders** or enter the full local path,
and select the folder containing `model.py`. **Projects** in Studio returns to
the chooser. **Open Folder** preserves authored files; **New Project** creates a
starter in a new or empty folder.

You can also open the folder directly:

```bash
python -m tuba.cli_studio "/path/to/my-project"
python -m tuba.cli_studio "/path/to/my-project.tubaproject" --extract-to "/path/to/new-working-folder"
python -m tuba.cli_studio "/path/to/my-project.tgz" --extract-to "/path/to/new-working-folder"
```

In the Windows developer setup, run from the Tuba checkout:

```powershell
.\.venv\Scripts\python.exe -m tuba.cli_studio "D:\Projects\my-project"
```

When Tuba runs inside WSL, use its Linux path, such as
`/mnt/d/Projects/my-project`. Studio's chooser browses the filesystem visible to
its Python process. Without `--extract-to`, a package extracts beside itself to
a new folder named after the package. The hosted gallery does not open arbitrary
local projects; package opening and export run in local Studio.
Studio binds to localhost; sending its URL does not share a session with another
computer. Share the files or publish a completed review instead.

## Geometry, mesh and solved results

The [STEP and mesh guide](step-meshing.md) gives the import/connection recipe and
headless diagnostic mesh and verified convergence commands for CLI and MCP.

**Build** shows geometry from the Python definition. **Generate mesh** explicitly
creates the actual analysis mesh for inspection without solving. **Solve**
generates the required mesh and evaluates the study with Code_Aster. Native
members are discretized by Tuba; imported STEP solids and shells use Gmsh.
Mesh sizing and refinements are authored in Python and resolved for these jobs.
No separate hand-authored mesh is needed for a supported model.

After changing geometry or sizing, regenerate the mesh and solve again to obtain
results for those inputs. A geometry preview or an unsolved mesh contains no
engineering result evidence. See [mesh refinement](workflow.md#mesh-refinement-and-convergence)
for sizing and convergence review.

To carry saved results with an editable project, include every file in each
required `evidence/<operation>/` directory, including its manifests and
`study_execution.json` attestation. An `.rmed` or CSV file alone is not the complete
Tuba handoff. Studio imports available attested evidence on opening and checks
whether it matches the current model and study. Missing, damaged or mismatched
evidence cannot establish current results; the project needs a new solve.
Changes to solver inputs make previous results stale. Keeping the same source and
CAD content allows saved evidence to travel with a moved project; Tuba checks
compatibility with the current study and compiler before reusing it.

Reading existing verified Code_Aster evidence requires no new solver execution.
Running a new analysis requires the configured runtime. The study may also need
result readers such as `meshio` or `h5py`; the shared environment in [Setup](setup.md)
includes these.

## Use the same folder through the CLI or MCP

Build a review from the project using the activated environment:

```bash
python -m tuba.project "/path/to/my-project" --output "/path/to/my-review"
```

The CLI reuses matching verified evidence and solves missing or stale operations.
`--force` requests a new solve even when evidence matches. For a study declaring
analysis operations, a source-only project requires Code_Aster for this command.
The study writes the completed
review bundle; standard studies place it in `my-review/review_scene/`.

For an agent, configure `python -m tuba.mcp.server` as a stdio subprocess using
the same Tuba environment. Bind to the extracted project's **file**, or use
`open_project_package` to extract and bind in one step:

```text
inspect_project_package(file_path="/path/to/shared.tgz")
init_session(file_path="/path/to/my-project/model.py", load_existing=True)
inspect_model()
verify_model()
solve_model()
export_project(output_path="/path/to/shared.tubaproject", include_results=False)
export_project(output_path="/path/to/shared.tgz", include_results=False)
open_project_package(file_path="/path/to/shared.tgz", destination="/path/to/new-working-folder")
```

`inspect_project_package` validates the manifest and every checksum without
extraction, Python execution or an active project session. Opening the package
executes its trusted Python.

MCP loads authored Python for inspection and solving without rewriting it.
`init_session` preserves a user-owned study and creates a managed `study.py` if
one is absent. `solve_model` follows the study and reuses or refreshes its
evidence; an open Studio imports externally completed results into **Review**.
MCP and Studio communicate through the local project files, so use the same
filesystem environment for both. The [modeling skill](workflow.md#teach-your-agent-the-authoring-contract)
teaches this workflow to agents.

## Share a completed review

Keep the entire bundle containing `scene.json`, geometry, reports, metadata and
staged solver artifacts. A review bundle is a result deliverable; its `source.py`
snapshot does not replace the editable project and its dependencies.

With Tuba installed, open a received bundle using:

```bash
python -m tuba.visualization.viewer "/path/to/my-review/review_scene" --open
```

The viewer serves the bundle and prints its browser URL. For recipients who only
need a browser, [publish the bundle with the packaged viewer](workflow.md#publish-a-static-review)
on a static web server and share that web URL. Static review hosting provides
the saved results; recalculation happens in a local Tuba and Code_Aster workflow.
