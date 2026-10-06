"""Import a STEP spool, connect a pipe, solve with Code_Aster, and review results.

The supplied STEP is a hollow 0.2 m spool (OD 0.10 m, wall 0.01 m).
Replace the file and source-local interface selectors together for other CAD.
Mesh export alone is not a completed engineering evaluation.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from tuba import Model
from tuba.analysis.staged_run import stage_runs
from tuba.visualization import SceneRequest, build_visualization_scene, write_scene_bundle


SOURCE = Path(__file__).resolve().parent / "assets" / "imported_spool.step"


def build_model(
    source: str | Path = SOURCE, *, mesh_size: float | str = "auto",
    interface_mesh_sizes: dict[str, float] | None = None,
):
    model = Model("Imported STEP spool with pipe continuation")
    model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0)
    model.add_pipe_section("DN100", OD=0.10, WT=0.01)
    model.import_step(
        source, id="spool", material="Steel", mesh_size=mesh_size,
        interface_mesh_sizes=interface_mesh_sizes,
        unit_scale_to_m=1.0,
        interfaces={
            "base": {"position": [0, 0, 0], "axis": [-1, 0, 0], "radius": 0.05},
            "outlet": {"position": [0.2, 0, 0], "axis": [1, 0, 0], "radius": 0.05},
        },
        fixed_interfaces=["base"],
    )
    with model.pipe(section="DN100", material="Steel") as pipe:
        pipe.start(list(model.ports["spool_outlet"].position)).run(1.0)
    element = model.get_element(pipe.created_element_ids[-1])
    model.connect_pipe_to_port(
        pipe=f"element:{element.id}", node=f"node:{element.n1}", port="port:spool_outlet",
    )
    model.define_load_case("Bending", gravity=False).add_nodal_force(element.n2, force=[0, 100, 0])
    return model


def run_example(output_dir: str | Path, *, source: str | Path = SOURCE):
    """Publish only after the real solver completes and its artifacts are imported."""
    output = Path(output_dir)
    model = build_model(source)
    run = model.solve(
        "Bending", work_dir=output / "solve",
        exec_method=os.environ.get("TUBA_CODE_ASTER_EXEC_METHOD", "auto"),
    )
    run = stage_runs({"Bending": run}, output / "review")["Bending"]
    scene = build_visualization_scene(SceneRequest(model, analysis_runs=[run]))
    return write_scene_bundle(scene, output / "review")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path, default=Path(".build/step-component-review"))
    args = parser.parse_args()
    run_example(args.output, source=args.source)
