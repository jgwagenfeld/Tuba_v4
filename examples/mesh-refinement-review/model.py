"""Authored STEP spool and pipe cantilever with a named outlet refinement.

Geometry and engineering inputs stay in Python. A diagnostic mesh is unsolved;
study.py configures the authentic Code_Aster comparison.
"""
from pathlib import Path

from tuba import Model

SPOOL_LENGTH = 0.2
PIPE_LENGTH = 1.0
OUTER_DIAMETER = 0.10
WALL_THICKNESS = 0.01
YOUNGS_MODULUS = 2.1e11
POISSON_RATIO = 0.3
TIP_FORCE_Y = 100.0
BASE_SIZE = 0.008
DETAIL_SIZE = 0.004
INFLUENCE_DISTANCE = 0.005
TRANSITION_DISTANCE = 0.04
SOURCE = Path(__file__).resolve().parent / "geometry" / "spool.step"


def build_model():
    """Build the shipped 0.2 m annular spool and its 1.0 m pipe continuation."""
    model = Model("Mesh refinement review: STEP spool cantilever")
    model.add_material("Steel", E=YOUNGS_MODULUS, nu=POISSON_RATIO, rho=7850.0)
    model.add_pipe_section("DN100", OD=OUTER_DIAMETER, WT=WALL_THICKNESS)
    model.import_step(
        SOURCE, id="spool", material="Steel", unit_scale_to_m=1.0,
        interfaces={
            "base": {"position": [0, 0, 0], "axis": [-1, 0, 0], "radius": OUTER_DIAMETER / 2},
            "outlet": {"position": [SPOOL_LENGTH, 0, 0], "axis": [1, 0, 0], "radius": OUTER_DIAMETER / 2},
        },
        fixed_interfaces=["base"],
    )
    with model.pipe(section="DN100", material="Steel") as pipe:
        pipe.start(list(model.ports["spool_outlet"].position)).run(PIPE_LENGTH)
    extension = model.get_element(pipe.created_element_ids[-1])
    model.connect_pipe_to_port(
        pipe=f"element:{extension.id}", node=f"node:{extension.n1}", port="port:spool_outlet",
    )
    model.define_load_case("Bending", gravity=False, pressure=0.0).add_nodal_force(
        extension.n2, force=[0, TIP_FORCE_Y, 0],
    )
    model.set_mesh_size(BASE_SIZE)
    model.add_mesh_refinement(
        "connection_detail", target="port:spool_outlet", size_m=DETAIL_SIZE,
        influence_distance_m=INFLUENCE_DISTANCE, transition_distance_m=TRANSITION_DISTANCE,
    )
    return model


model = build_model()
