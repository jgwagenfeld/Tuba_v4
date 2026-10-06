# Review local refinement and Code_Aster convergence

This authored project includes `geometry/spool.step`: a 0.2 m
hollow steel spool (100 mm OD, 80 mm ID), fixed at its base, coupled by
`3D_TUYAU` to a 1.0 m pipe continuation. `Bending` applies 100 N in global Y at
the tip; gravity and pressure are disabled. `model.py` owns geometry, engineering
inputs, and the named `connection_detail` refinement. Edit and save Python to
change them; Studio inspects them and starts generation/evaluation jobs.

With a working Code_Aster runtime, launch and open the printed **Studio** URL:

```bash
python -m tuba.cli_studio examples/mesh-refinement-review --out /path/to/output/studio --state-dir /path/to/output/launcher --port 0 --no-open
```

For a portable handoff, export this folder with
`python -m tuba.project.package export examples/mesh-refinement-review --output /path/to/project.tgz`.
The package includes the referenced STEP. Inspect and unpack it into a new folder
before opening it or generating a mesh. See the
[STEP and mesh guide](../../docs/content/step-meshing.md) for CLI/MCP commands.

In **Build**, expand **Mesh review**. The diagnostic sizing preview describes a
request; finite CAD face distances resolve during native generation. Choose
**Generate mesh** to inspect actual quadratic TETRA10 spool cells, TRI6 interface
faces, and the SEG3 pipe mesh. This operation is explicitly **unsolved**. Inspect
requested-size coloring/legend and the `connection_detail` annular outlet target,
then actual counts and measured geometric quality. Positive cells establish a
geometry gate; geometric quality is not an accuracy or compliance verdict.

The global request is 0.008 m. The outlet requests 0.004 m through a 0.005 m
influence distance from the **finite annular face**, then increases linearly
over another 0.04 m to the applicable base size. At `[x, .045, 0]` for
`x=[.20, .195, .175, .155]`, the bound request is `[.004, .004, .006, .008]` m.
The bore and distant points on the face's plane are outside the annulus.
Actual edges are mesher output, distinct from the requested-size legend.

`study.py` declares scales `[1.0, 0.75]` and relative tolerance `0.03`. Choose
**Run convergence**. Each level executes real Code_Aster and imports verified
artifacts. Only requested sizes scale; dimensions, target extents, influence
and transition distances, loads, material, and modelisation stay fixed. The
comparison shows actual counts/families, support-specific measured maxima,
changes, tolerance, and unavailable fields. Completing both solves and meeting
tolerance are separate outcomes. This pair cannot establish singular peak
stress accuracy.

The Build scene still represents the authored source and its unsolved diagnostic
mesh, so its footer can say **Not solved** while the comparison levels say
**Solved**. Each scaled level owns matching Code_Aster artifacts and results;
those results are not attached to the unchanged source as an ordinary Solve.
The standard **Solve** and **Review** workflow remains a separate action.

**Cancel** stops the owned job. Failures expose errors and retain diagnostics;
they do not publish results. Editing Python makes existing meshes/comparisons
stale. Save source, inspect the new preview, then explicitly regenerate or rerun.
Mesh and convergence evidence have separate lifetimes and remain re-openable
only while their exact input identities and attested bytes still match.

Independently qualify the cantilever and density, or reuse a completed Studio job:

```bash
python scripts/qualify_mesh_refinement_review.py --output /path/to/output/qualification
python scripts/qualify_mesh_refinement_review.py --output /path/to/output/qualification --comparison /path/to/completed/job
```

Use the directory returned by `GET /api/mesh`. The script reverifies artifacts,
derives `I=pi*(.05**4-.04**4)/4` and `uy=100*1.2**3/(3*2.1e11*I)`, checks tip
displacement within 5%, physical-node reaction force/moment within 1%, and
section-fit coupling continuity. Successive authored-tip Y displacement must
change by at most 3%. One additional **unsolved** mesh without the local rule
measures port triangles and unique primary-edge density in near/far wall bands.
Expected values are derived from physics rather than copied from a solver run.
Run it from the repository root with `git` on PATH and the same Code_Aster
runtime configuration as Studio.

## Other authored targets

`model.set_mesh_size(size_m, region="spool_solid")` overrides a supported
solid/shell region's base size. Named rules accept `element:...`, nonempty
`group:...`, `analysis_region:...`, `component:...`, confirmed `port:...`, or
source-local CAD face selectors. Spatial selectors use metres:

```python
model.add_mesh_refinement(
    "clearance_detail", target={"kind": "sphere", "center_m": [.2, 0, 0], "radius_m": .02},
    size_m=.004, influence_distance_m=.005, transition_distance_m=.04,
)
# A box uses kind="box", min_m=[...], max_m=[...].
model.remove_mesh_refinement("clearance_detail")
```

The smallest applicable request wins. CAD rules remain scoped to their owner;
spatial rules apply to supported intersecting geometry. Legacy
`interface_mesh_sizes` still resolves through the common policy. Invalid
sizes/selections, duplicate names, stale/unconfirmed CAD selectors, and
zero-width transitions fail actionably.

## Source-checkout viewer build

Reuse existing dependencies, check at least 10 GiB free on system/output drives
plus expected build space, and put generated output outside tracked source.
For the shared Windows developer environment:

```powershell
$env:PATH = 'D:/Gitprojects/Tuba_v4/.venv/Scripts;' + $env:PATH
$env:PYTHONPATH = (Get-Location).Path
$env:TEMP = 'D:/tmp/tuba-mesh-review/tmp'; $env:TMP = $env:TEMP
New-Item -ItemType Directory -Force $env:TEMP | Out-Null
npm --prefix viewer run build -- --outDir D:/tmp/tuba-mesh-review/viewer
$env:TUBA_VIEWER_ASSETS = 'D:/tmp/tuba-mesh-review/viewer'
python -m tuba.cli_studio examples/mesh-refinement-review --out D:/tmp/tuba-mesh-review/studio --state-dir D:/tmp/tuba-mesh-review/launcher --port 0 --no-open
```

`TUBA_VIEWER_ASSETS` opts into a directory with a built `index.html`; unset uses
the packaged viewer. Runtime selection remains machine configuration, outside
`study.py` (here `TUBA_CODE_ASTER_EXEC_METHOD=wsl` and
`TUBA_CODE_ASTER_WSL_DISTRO=Ubuntu`). Missing Code_Aster is a runtime blocker.
An exported study or diagnostic mesh is not a completed engineering evaluation.
