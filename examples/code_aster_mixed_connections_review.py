"""Author solid/pipe/frame/shell connections, solve, and publish a web review.

This is an explicit new reference design, not the unavailable original header
disks. The guide intentionally reproduces V3 global DOF equalities across a
10 mm gap: DX, DY and all rotations held; DZ released. That joint convention
does not include eccentric rigid-body terms. Materials use scalar elasticity.
Exported meshes and commands alone are incomplete engineering evaluation.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from tuba import Model
from tuba.analysis.staged_run import stage_runs
from tuba.visualization import SceneRequest, build_visualization_scene, write_scene_bundle


def shell_strip(model, *, name, start, end, width, thickness, material,
                mesh_size, start_reference, end_reference):
    """Build a planar X-directed strip and tie its full end edges to references.

    Coordinates, width, thickness and mesh size are metres; reference arguments
    are native model node ids. Both references lie at their edge midpoints.
    """
    if width <= 0 or thickness <= 0 or end <= start:
        raise ValueError("Expected positive strip width/thickness and end > start.")
    model.add_shell_panel(
        name, polygon=[[start, -width / 2, 0], [end, -width / 2, 0],
                       [end, width / 2, 0], [start, width / 2, 0]],
        thickness=thickness, material=material, mesh_size=mesh_size,
    )
    model.add_rigid_patch(f"{name}_base", reference=start_reference, shell=name, edges=[3])
    model.add_rigid_patch(f"{name}_tip", reference=end_reference, shell=name, edges=[1])


def build_shell_reference(*, length=0.4, width=0.04, thickness=0.008,
                          mesh_size=0.02, E=7e10, alpha=1.2e-5):
    """A Poisson-zero cantilever strip for an independent beam-limit check."""
    model = Model("New shell cantilever reference")
    model.add_material("Panel", E=E, nu=0.0, alpha=alpha, rho=2700.0)
    base = model.add_reference_point("base", position=[0, 0, 0])
    tip = model.add_reference_point("tip", position=[length, 0, 0])
    shell_strip(model, name="panel", start=0, end=length, width=width,
                thickness=thickness, material="Panel", mesh_size=mesh_size,
                start_reference=base, end_reference=tip)
    model.add_support(base, "anchor")
    return model, {"base": base, "tip": tip}


def build_model(source=None, *, solid_mesh_size=0.015, shell_mesh_size=0.02,
                shell_length=0.4, shell_width=0.04, shell_thickness=0.008,
                frame_gap=0.01, frame_depth=0.06, frame_wall=0.006,
                pipe_length=1.0, pipe_outer=0.05, pipe_inner=0.04,
                solid_E=2.1e11, pipe_E=1.9e11, frame_E=2.1e11, shell_E=7e10):
    """Compose a new reference with named connections and four FE families.

    The supplied STEP is a 0.2 m annular spool; its selectors must be changed
    together with its CAD file. All geometry parameters are metres. Changing
    pipe radii does not alter the supplied STEP and therefore fails continuity
    validation unless a matching source is supplied.
    """
    source = Path(source) if source is not None else Path(__file__).resolve().parent / "assets" / "imported_spool.step"
    if not 0 < frame_gap < shell_length:
        raise ValueError("Expected 0 < frame_gap < shell_length.")
    model = Model("New mixed solid/pipe/frame/shell reference")
    for name, E, nu, rho in (("Solid", solid_E, 0.3, 7850.0),
                             ("Pipe", pipe_E, 0.3, 7850.0),
                             ("Frame", frame_E, 0.3, 7850.0),
                             ("Panel", shell_E, 0.0, 2700.0)):
        model.add_material(name, E=E, nu=nu, rho=rho, alpha=1.2e-5)
    model.add_pipe_section("Annulus", OD=2 * pipe_outer, WT=pipe_outer - pipe_inner)
    model.add_rectangular_section("FrameRHS", height_y=frame_depth, height_z=frame_depth,
                                  thickness_y=frame_wall, thickness_z=frame_wall)
    base = model.add_reference_point("base", position=[-shell_length, 0, 0])
    interface = model.add_reference_point("spool_base", position=[0, 0, 0])
    shell_strip(model, name="panel", start=-shell_length, end=0, width=shell_width,
                thickness=shell_thickness, material="Panel", mesh_size=shell_mesh_size,
                start_reference=base, end_reference=interface)
    frame_top = model.add_node([-frame_gap, 0, 0])
    model.add_element(id="frame", type="beam", n1=base, n2=frame_top,
                      section="FrameRHS", material="Frame")
    model.add_support(interface, "custom", attached_to=frame_top,
                      blocked_dof=[1, 1, 0, 1, 1, 1], attachment_mode="dof_equality")
    model.add_support(base, "anchor")
    model.import_step(
        source, id="spool", material="Solid", mesh_size=solid_mesh_size,
        unit_scale_to_m=1.0,
        interfaces={"outlet": {"position": [0.2, 0, 0], "axis": [1, 0, 0],
                                "radius": pipe_outer}},
    )
    # Selectors use the file's normalized source coordinates. This supplied
    # test asset has radius 0.05 in that basis; explicit scale 1.0 maps it to
    # radius 0.05 m. A millimetre engineering CAD file normally uses scale .001.
    model.add_rigid_patch(
        "spool_mount", reference=interface, component="spool",
        faces=[{"shape": "annular_face", "position": [0, 0, 0], "axis": [-1, 0, 0],
                "radius": pipe_outer, "inner_radius": pipe_inner}],
    )
    with model.pipe(section="Annulus", material="Pipe", route="continuation") as route:
        route.start(list(model.ports["spool_outlet"].position)).run(pipe_length)
    pipe = model.get_element(route.created_element_ids[-1])
    model.connect_pipe_to_port(pipe=f"element:{pipe.id}", node=f"node:{pipe.n1}",
                               port="port:spool_outlet", id="outlet_continuity")
    return model, {"base": base, "interface": interface, "frame_top": frame_top,
                   "nozzle": pipe.n1, "tip": pipe.n2, "pipe": pipe.id}


def run_example(output_dir, *, source=None):
    """Publish only real imported Code_Aster results in the existing web path."""
    output = Path(output_dir)
    model, nodes = build_model(source)
    model.define_load_case("Combined", gravity=False).add_nodal_force(
        nodes["tip"], force=[1000, 0, 100], moment=[10, 0, 0])
    run = model.solve("Combined", work_dir=output / "solve",
                      exec_method=os.environ.get("TUBA_CODE_ASTER_EXEC_METHOD", "auto"))
    run = stage_runs({"Combined": run}, output / "review")["Combined"]
    scene = build_visualization_scene(SceneRequest(model, analysis_runs=[run]))
    return write_scene_bundle(scene, output / "review")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--output", type=Path, default=Path(".build/mixed-connections-review"))
    args = parser.parse_args()
    run_example(args.output, source=args.source)
