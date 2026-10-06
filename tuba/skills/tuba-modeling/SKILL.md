---
name: tuba-modeling
description: Author, verify, solve, review and share piping/structural projects with the Tuba Python library. Use for Tuba model.py / study.py folders, STEP imports, mesh refinement and convergence, ZIP/TGZ handoffs, pipe routing, RackRow racks, supports, clash checks, or Code_Aster-backed stress and displacement results.
---

# Tuba modeling

Tuba is a Code_Aster-backed piping engineering workflow. Its contract never changes:

1. Define the structure in Python (`model.py`).
2. Evaluate it with Code_Aster (`study.py`).
3. Display the processed Code_Aster results (web review scene or PyVista).

A `.comm`, `.mail`, or `.export` file is solver input, not a result. Never present
export-only output, hand-derived numbers, or proxy values as solver results. A new
solve requires Code_Aster; if it is unavailable, stop with the runtime blocker.
Reviewing existing verified Code_Aster artifacts needs no new solver execution.

**Pipe-free structural models are a different contract.** Portal frames, roof
trusses, racks and other beam/bar assemblies go through the same workflow but
carry traps of their own: `bar` elements have no rotational stiffness and can make
the frame's matrix singular, and a model with no pipe elements gets displacements
and reactions but no von Mises stress. Load the `tuba-structural-frames` skill
before building or debugging one.

## Author Python, not node dumps

`model.py` is engineering code. Write procedural, parametric Python: constants,
loops, construction units (`units/<name>.py` applied with `assemble(...)`), and
the fluent builder. Do not emit flat `add_node` / `add_element` coordinate dumps.

```python
from tuba import Model
from tuba.assemblies import RackRow

model = Model("Plant", standard="ASME B31.3")
model.add_material("SS316L", E=1.95e11, nu=0.3, rho=8000.0, alpha=1.6e-5)
model.add_pipe_section("DN80_SCH80", OD=0.0889, WT=0.00762)

with model.pipe(section="DN80_SCH80", material="SS316L", route="HP_H2") as p:
    p.start([14.0, -6.5, 1.5], support="anchor")
    p.run(4.0)
    p.bend(radius=0.4, angle=90.0, plane="XZ")
    p.end(support="anchor")

model.define_load_case("Operating", pressure=3.0e6, temperature=65.0, gravity=True)
model.validate()
```

The reference layout is `examples/hydrogen-plant-layout/`: obstacles, a `RackRow`
bridge, shoe supports at beam midpoints, and two routed process lines.

## Verify before you solve

`model.verify()` is the one cold-model gate; every surface that solves runs it
and refuses on a blocking error. Run it after every routing change:

```python
report = model.verify()               # validation + clashes + rules
assert report.passed, report.errors   # blocking: bad refs, hard clashes, error rules
print(report.warnings)                # clearance clashes and warnings, non-blocking
```

Under it, `ClashEngine().check_all(model)` is the full cold-model triple —
obstacles, self, and duplicate nodes. `check_model(model)` covers obstacles
only. `check_self(model)` covers element vs element without a topological
connection (shared node, support link, shared coupling target). A route that
doubles back onto itself passes obstacle checks and fails `check_self`. Never
treat a green obstacle-only test as "clash free".

## Prove every route by its endpoints

A fluent route can look right in a screenshot and still end in the wrong place.
Assert the final coordinates against the equipment the line feeds:

```python
end = model.nodes[model.elements[-1].n2].coords
assert [round(float(value), 3) for value in end] == [33.0, -3.25, 1.5]
```

Compare against the obstacle bounds (`model.obstacles`). Stop about 1 m short of
an obstacle face: the end anchor is a nozzle stub, and touching the face is an
obstacle clash.

### Bend sign semantics (the classic bug)

`bend(radius, angle, plane)` picks its rotation axis from the **current
heading**:

- `plane="XY"`: axis is +Z; the sign is stable for any heading.
- `plane="XZ"`: axis is `cross(direction, up)`, with a fallback to +Y for
  headings along ±Z. A `+90` "up" bend from +X becomes a "backwards" bend from
  +Z. The plane is not fixed, so a loop written as `+90, -90, -90, +90` folds
  back over itself instead of continuing forward.

For loops and risers, say the axis explicitly:

```python
p.bend_by_orientation(radius=0.4, angle=90.0, axis=[0.0, -1.0, 0.0])   # +X -> +Z
p.bend_by_orientation(radius=0.4, angle=90.0, axis=[0.0, 1.0, 0.0])    # +Z -> +X
```

The builder resolves `bend(plane=...)` against the heading when you call it and
records that absolute axis, so a saved recipe replays the same turn even if an
earlier step changes. While authoring, `bend_by_orientation` still states your
intent most clearly.

A 90° bend consumes `r * tan(45°)` of straight leg on each side, so runs that
must land on a target need to account for the tangent length.

## Name the context in the 3D scene

Analytical obstacles (buildings, vessels) render as plain boxes. Label them from
the study with `scene_modifier`, so reviewers read the plant, not the boxes:

```python
def _add_obstacle_labels(scene, model):
    for obstacle in model.obstacles:
        low, high = obstacle["min_point"], obstacle["max_point"]
        add_scene_label(
            scene,
            OBSTACLE_LABELS[obstacle["id"]],
            [(low[0] + high[0]) / 2, (low[1] + high[1]) / 2, high[2] + 1.0],
            label_id=obstacle["id"],
            height=0.9,   # metres; scale to the model, 0.18 is for bench-scale models
        )
```

Sandbox-scale studies pass `scene_modifier=_add_labels` to
`run_example(...)`; see `examples/support-rack-review/study.py`.

## Solve and review

- `study.py` declares `LOAD_CASES`, `SOLVER_OPTIONS`, `VOLUME_EXPORT`, and
  `build_review(namespace, output, ...)`. Standard managed studies use
  `tuba.project.study.build_study_review`; custom review helpers must travel with
  the project if they are not part of the installed Tuba package.
- `python -m tuba.cli_studio <project-folder>` opens the live studio;
  `python -m tuba.project <project-folder> --output <dir>` builds the review.
- `python -m tuba.skills --list` shows the shipped skills;
  `--name tuba-structural-frames --target <skills-folder>` installs the
  structural one.
- `python -m tuba.mcp.server` exposes inspection, `check_clashes`, units, and
  `solve_model` to agents. Use it to inspect and verify, not to unroll geometry.
- Two display paths, never mixed in one study: `tuba.plotting` (PyVista quick
  look / export) and `tuba.visualization` + `viewer/` (reviewable web scene).

## Open and share project folders

Studio, the CLI and MCP use the same local project files. Share a ZIP
`.tubaproject` or a gzip-compressed tar `.tgz` through Studio's
**Exchange → Export project** format selector, or the package CLI.
The local project chooser opens packages into explicit **new working folders**;
the hosted gallery does not load arbitrary local projects. Studio also accepts
the existing folder containing `model.py`:

```bash
python -m tuba.cli_studio                         # Open Folder / Browse folders
python -m tuba.cli_studio "/path/to/project"       # direct folder opening
python -m tuba.cli_studio "/path/to/shared.tubaproject" --extract-to "/path/to/new-project"
python -m tuba.project.package export "/path/to/project" --output "/path/to/shared.tubaproject"
python -m tuba.project.package export "/path/to/project" --output "/path/to/shared.tgz"
python -m tuba.project.package inspect "/path/to/shared.tubaproject"
tar -tzf shared.tgz                               # Linux archive listing
tar -xOzf shared.tgz project/model.py              # read source without extraction
python -m tuba.project "/path/to/project" --output "/path/to/review"
```

Configure `python -m tuba.mcp.server` as a stdio subprocess in the same filesystem
environment as Studio. Bind to the **file** with
`init_session(file_path="/path/to/project/model.py", load_existing=True)`, then use
`inspect_model`, `verify_model` and `solve_model`. Authored Python is inspected and
solved without rewriting it. MCP preserves a user-owned study and creates a
managed `study.py` if absent; Studio's Open Folder does not scaffold one.

MCP `export_project(output_path="/path/to/shared.tubaproject", include_results=False)`
packages the bound project's **saved files**. `open_project_package(file_path=...,
destination="/path/to/new-project")` validates, extracts and binds its `model.py`.
Opening executes project Python; inspection/extraction alone does not. The output
suffix selects ZIP (`.tubaproject`, `.zip`) or TGZ (`.tgz`, `.tar.gz`); both have
the same readable manifest and `project/` payload. ZIP tools or native `tar` can
review them. Tuba detects the content when reading; arbitrary archives without
Tuba's manifest are not project packages. Studio, CLI and MCP accept both formats
on Windows and Linux.

Source-only is the default. Studio's results checkbox, CLI `--include-results`
and MCP `include_results=True` require complete current verified Code_Aster
evidence for every study operation. Missing, damaged, stale or unverified evidence
refuses export; solve first or share source-only. Packages never ship an environment
or runtime. Save editor changes before Studio export; keep helpers/CAD/data local
and paths relative to the script. Dynamic dependencies still need author review.

For an editable handoff, include `model.py`, `study.py`, construction units, every
imported local helper, and all referenced CAD/JSON/table files. Keep package layout
intact and resolve assets relative to `Path(__file__).resolve().parent`. Adding a
STEP file to the folder does not import it into the model: Python declares its
units, material, placement, ports and connections. Record the Tuba revision and
dependencies. Exclude `.tuba/` session state, builds, environments, caches and old
archives; inspect the package and open an extracted copy. Gallery ZIP generation is
not a general dependency collector for custom projects.

Meshes are generated from the authored geometry and sizing: **Generate mesh**
creates diagnostic cells; **Solve** generates the required mesh and runs Code_Aster.
After changing geometry or sizing, regenerate and solve for current results.

To reuse saved results in Studio, include the complete `evidence/<operation>/`
folders with their manifests and `study_execution.json`. Studio imports available
evidence and checks it against the current inputs; the CLI and `solve_model` reuse
matching verified evidence and solve missing or stale operations. Copying only an
RMED or CSV is not a complete Tuba handoff.

Studio, CLI and MCP project solves enforce the same structural, cold-clash, rule
and script-style gate before changing staging or evidence. `--force` and
`solve_model(force=True)` rerun reusable evidence; they never bypass blockers.

For result inspection, share the whole bundle containing `scene.json`, geometry,
reports, metadata and staged solver artifacts. Open it with
`python -m tuba.visualization.viewer "/path/to/review/review_scene" --open`, or
publish it with the packaged viewer for browser-only recipients. A review's
`source.py` snapshot does not replace the editable project. A localhost Studio
URL does not share a session with another computer.

## STEP solids, diagnostic meshes and convergence

Keep CAD project-local and resolve it from `Path(__file__).resolve().parent`.
`model.import_step(path, id="spool", material="Steel", interfaces=...)` imports
a closed volume. Gmsh normalizes STEP coordinates to millimetres; source-local
interface positions/radii/selectors use that basis. The default `.001` scale
converts to model metres once. Placement origins, pipe dimensions and mesh sizes
use metres; rotation is a unit `wxyz` quaternion. Check the resulting port position
against the intended physical dimensions. Do not copy a fixture's scale blindly.

Explicit named `interfaces` confirm unique planar faces. Automatically detected
ports remain candidates. Reauthor selectors before connecting with
`connect_pipe_to_port` or `connect_beam_to_port`; an unattached reference node is
not a solid connection. Pressure needs explicit `pressure_surfaces`. STL imports
provide reference geometry without stiffness. Use project construction units for
repeated solid/line or shell/rigid-patch connections.

Author sizing in Python: `set_mesh_size(size_m, region=...)`,
`add_mesh_refinement(id, target="port:spool_outlet", size_m=..., influence_distance_m=...,
transition_distance_m=...)`, `remove_mesh_refinement(id)` and
`set_mesh_size_factor(factor)`. The smallest applicable request wins. Inspection
returns `mesh_settings`, `mesh_refinements` and `mesh_groups` alongside the CAD,
ports, regions and couplings. Edit source and reload rather than unrolling mesh cells.

```bash
python -m tuba.project.mesh mesh "/path/to/project" --output "/path/to/new-mesh-output"
python -m tuba.project.mesh convergence "/path/to/project" --output "/path/to/new-comparison-output"
```

MCP equivalents are `generate_mesh(output_dir=...)` and
`run_mesh_convergence(output_dir=...)`. Each output folder must be new; JSON returns
its job directory. Mesh generation is unsolved and requires the `mixed` extra for
MED reading. Convergence requires real Code_Aster, exactly one study operation,
`MESH_CONVERGENCE = {"scales": [1.0, 0.75], "relative_tolerance": 0.03}` and the
shared verification gate. Each level is independently verified. Completion and
tolerance are separate; unavailable quantities and unchanged actual meshes have
no relative verdict. Comparison levels do not replace ordinary project evidence.
After changing geometry/sizing, regenerate and solve. Quality and measured changes
do not certify engineering accuracy or compliance.

Before binding a received archive, `inspect_project_package(file_path=...)`
verifies its manifest and checksums without executing Python or changing the active
session. Export, inspect, unpack and load an extracted copy to check computed CAD
paths; packing source does not execute it or discover all dynamic dependencies.

## Report what was verified

State the checks you ran and what they returned: `check_all` clash count, route
endpoint assertions, and whether the review came from a fresh Code_Aster solve or
imported verified evidence. Evidence must match the current solver inputs; an
engineering change can invalidate it even when the original solve passed.
