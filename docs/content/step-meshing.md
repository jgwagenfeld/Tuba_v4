# Import STEP and review its mesh

Author the component and its engineering connections in `model.py`, generate
diagnostic cells, then evaluate the study with Code_Aster. A CAD preview or a
generated MED mesh contains no stress, displacement or reaction results.

## Keep CAD in the project

Keep STEP/STP under `geometry/`, resolve it from `Path(__file__).resolve().parent`
and include it when [sharing the project](project-sharing.md). The
[mesh-refinement example](https://github.com/jgwagenfeld/Tuba_v4/tree/main/examples/mesh-refinement-review)
includes its own `geometry/spool.step` and opens independently of the checkout.
Its fixture uses an explicit `unit_scale_to_m=1.0`; ordinary millimetre CAD
normally uses the default `0.001` described below.

`model.import_stl(...)` supplies reference geometry for inspection and supported
clearance checks, without stiffness. Structural imported solids require closed
STEP volumes, a material and explicit analysis interfaces.

## Author the solid and continuation

Gmsh normalizes declared STEP units to **millimetres** before selection. Interface
positions, radii and CAD face selectors use that source-local basis, before
placement. The default `unit_scale_to_m=0.001` converts it once to model metres.
Port coordinates, placement origins, pipe dimensions and requested mesh sizes use
**metres**. Placement rotations use a unit quaternion in `wxyz` order.

This `model.py` assumes a hollow spool extending from X=0 to X=200 mm, with outer
radius 50 mm and bore radius 40 mm. Adjust the selectors to your CAD; ambiguous or
unmatched selections fail rather than choosing another face.

```python
from pathlib import Path
from tuba import Model

PROJECT = Path(__file__).resolve().parent
PIPE_LENGTH_M = 1.0
model = Model("STEP cantilever")
model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0)
model.add_pipe_section("DN100", OD=0.10, WT=0.01)
model.import_step(
    PROJECT / "geometry" / "spool.step",
    id="spool", material="Steel", unit_scale_to_m=0.001,
    interfaces={
        "base": {"position": [0, 0, 0], "axis": [-1, 0, 0], "radius": 50},
        "outlet": {"position": [200, 0, 0], "axis": [1, 0, 0], "radius": 50},
    },
    fixed_interfaces=["base"],
)
assert abs(model.ports["spool_outlet"].position[0] - 0.2) < 1e-9
with model.pipe(section="DN100", material="Steel") as pipe:
    pipe.start(list(model.ports["spool_outlet"].position)).run(PIPE_LENGTH_M)
extension = model.get_element(pipe.created_element_ids[-1])
model.connect_pipe_to_port(
    pipe=f"element:{extension.id}", node=f"node:{extension.n1}", port="port:spool_outlet",
)
model.define_load_case("Bending", gravity=False, pressure=0.0).add_nodal_force(
    extension.n2, force=[0, 100, 0],
)
model.set_mesh_size(0.008)
model.add_mesh_refinement(
    "connection_detail", target="port:spool_outlet", size_m=0.004,
    influence_distance_m=0.005, transition_distance_m=0.04,
)
model.validate()
```

Explicit `interfaces` create confirmed named faces. Auto-detected circular faces
remain candidates: inspect them and reauthor the import with explicit selectors
before connecting or solving. Pressure requires explicit `pressure_surfaces`
selectors for each solid region. A face cannot be both fixed and coupled.
`connect_beam_to_port` serves a beam continuation; a support or reference node
alone does not attach a solid face. Use `add_rigid_patch` for an explicit
face-to-reference connection. The
[mixed-structure contract](https://github.com/jgwagenfeld/Tuba_v4/blob/main/docs/architecture/step-mixed-code-aster.md)
details these assumptions and the supported straight pipe chains, planar shells
and scalar elastic materials. Unsupported requests fail explicitly.

Global sizing, `set_mesh_size(size_m, region="spool_solid")` and named refinements
resolve through one policy. Refine an element, group, solid/shell region, component,
confirmed port, CAD face or spatial sphere/box. The smallest applicable request
wins. CAD face targets stay scoped to their component. `remove_mesh_refinement(id)`
removes a rule; `set_mesh_size_factor(factor)` scales requested sizes while
retaining geometry and target extents. See the [API reference](reference/public-api.md).

## Generate diagnostic cells without Studio

Install the `mixed` extra for MED reading (`pip install 'tuba[mixed]'`), then use
an activated Tuba environment on Windows or Linux:

```bash
python -m tuba.project.mesh mesh "/path/to/project" --output "/path/to/new-mesh-output"
```

The command executes trusted project Python and uses Studio's native worker,
study formulations and artifact validator. It prints JSON identifying the job
directory, `result_status="mesh_only"` and geometric quality. Each **new** output
folder contains one job directory with `mesh.med` or `mesh.mail`,
`analysis_mesh.json`, checksummed receipts and `worker.log`. Existing outputs are
refused. Jobs hold the project execution claim, reject source changes during
generation and retain diagnostics on failure.

For direct Python use, `model.mesh("/path/to/mesh.med")` generates supported
STEP/shell/native mixed cells and a sibling `.mesh.json` without a load case.
The project command additionally follows `study.py` and supports native line
studies and `VOLUME_EXPORT` like Studio. Save geometry or sizing changes in Python,
regenerate the mesh and run Code_Aster for current results. Positive geometric
quality does not establish engineering accuracy.

## Run Code_Aster convergence

Add this `study.py` for the example above:

```python
from tuba.project.study import build_study_review

LOAD_CASES = ("Bending",)
SOLVER_OPTIONS = {"pipe_modelization": "TUYAU_3M"}
MESH_CONVERGENCE = {"scales": [1.0, 0.75], "relative_tolerance": 0.03}


def build_review(namespace, output, *, artifact_dir=None, force=False):
    return build_study_review(
        namespace, output, artifact_dir=artifact_dir, force=force,
        scene_id="scene:step-cantilever", title="STEP cantilever",
    )
```

```bash
python -m tuba.project.mesh convergence "/path/to/project" --output "/path/to/new-comparison-output"
```

Convergence requires exactly one operation, the shared project verification gate
and a configured Code_Aster runtime supporting owned process cleanup. Missing or
unsupported runtimes fail with their setup requirement. Each level executes real
Code_Aster and is independently reverified before returning a comparison.
Requested sizes scale; dimensions, loads, materials and target extents stay fixed.
Explicit `line_segments` cannot be combined with convergence sizing.

Completing solves and meeting tolerance are separate outcomes. Inspect
`comparison.json` for actual counts, measured changes, unavailable fields and
unchanged meshes. These levels retain their own results and do not replace ordinary
project `evidence/` or publish an ordinary solved review. Use **Solve** or the
[project solve workflow](workflow.md) for that. Ctrl+C cancels owned execution;
unverified cleanup retains the project claim and requires retrying cleanup through
Studio. A mesh comparison does not certify accuracy or code compliance.

For the ordinary Code_Aster solve and processed web-scene review, run
`python -m tuba.project "/path/to/project" --output "/path/to/review"`.
Open the resulting `review_scene/` with
`python -m tuba.visualization.viewer "/path/to/review/review_scene" --open`.

## Use MCP against the same project

```text
init_session(file_path="/path/to/project/model.py", load_existing=True)
inspect_model()
generate_mesh(output_dir="/path/to/new-mesh-output")
run_mesh_convergence(output_dir="/path/to/new-comparison-output")
```

Inspection includes `cad_assets`, `ports`, `analysis_regions`, `couplings`,
`mesh_groups`, `mesh_settings` and `mesh_refinements`, with source links where
available. Edit authored Python to change selections and sizing, then inspect
again. These tools preserve authoring files and share the same execution claim
as Studio and `solve_model`.

Before opening a received ZIP/TGZ, use
`inspect_project_package(file_path="/path/to/shared.tgz")` to verify its manifest
and every checksum without extraction, Python execution or a bound session.
`open_project_package` extracts and executes the trusted project. Verify a moved
project can import its CAD; source-only packing cannot discover every computed
path or dynamic dependency.
