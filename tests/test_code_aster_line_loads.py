"""Real Code_Aster references: authored distributed loads reach the pipe in full.

A statics check needs no stiffness: the support reactions of a loaded pipe
must add up to minus the applied load, whatever the modelization.
"""
import math
import os
from pathlib import Path

import pytest

from tuba import Model
from tuba.model import BendGeometry

pytestmark = pytest.mark.skipif(
    os.environ.get("TUBA_RUN_CODE_ASTER_INTEGRATION") != "1",
    reason="set TUBA_RUN_CODE_ASTER_INTEGRATION=1 to run the real Code_Aster line-load references",
)

RUN_LENGTH = 4.0
BEND_RADIUS = 0.5
BEND_LENGTH = BEND_RADIUS * math.pi / 2.0


def elbow_model(name: str) -> tuple[Model, tuple[str, str]]:
    """A 4 m straight along X into a 90 degree elbow turning to Y, anchored at both ends."""
    model = Model(project_name=name)
    model.add_material("Steel", E=2.0e11, nu=0.3, rho=7850.0, alpha=1.2e-5)
    model.add_pipe_section("Pipe", OD=0.1, WT=0.01)
    start = model.add_node([0.0, 0.0, 0.0])
    corner = model.add_node([RUN_LENGTH, 0.0, 0.0])
    end = model.add_node([RUN_LENGTH + BEND_RADIUS, BEND_RADIUS, 0.0])
    model.add_element(id="run", type="pipe_straight", n1=start, n2=corner, section="Pipe", material="Steel")
    model.add_element(
        id="elbow", type="pipe_bend", n1=corner, n2=end, section="Pipe", material="Steel",
        bend_radius=BEND_RADIUS, bend_angle=90,
        bend_geometry=BendGeometry(
            center=[RUN_LENGTH, BEND_RADIUS, 0.0], normal=[0.0, 0.0, 1.0], radius=BEND_RADIUS, angle=90,
            start_tangent=[1.0, 0.0, 0.0], end_tangent=[0.0, 1.0, 0.0],
        ),
    )
    model.add_support(start, "anchor")
    model.add_support(end, "anchor")
    return model, (start, end)


def reaction_total(run, nodes) -> list[float]:
    return [sum(float(run.results.node_results[node].reaction_force[i]) for node in nodes) for i in range(3)]


@pytest.mark.parametrize("modelization", ["TUYAU_3M", "POU_D_T"])
def test_line_load_reaches_straight_and_elbow_in_full(modelization):
    model, anchors = elbow_model(f"LineLoad {modelization}")
    model.define_operation("Load", gravity=False).add_field("line_load", 1000.0, direction=[1.0, 0.0, -1.0])
    root = Path(f".build/line-load-references/line-load-{modelization}").resolve()
    run = model.solve("Load", pipe_modelization=modelization, work_dir=str(root), force=True)
    # The load is not projected: every metre of straight and elbow carries the full 1000 N/m.
    total = 1000.0 * (RUN_LENGTH + BEND_LENGTH) / math.sqrt(2.0)
    expected = [-total, 0.0, total]
    observed = reaction_total(run, anchors)
    print(f"line load {modelization}: reactions {observed}, expected {expected}")
    assert observed == pytest.approx(expected, rel=1e-3, abs=1.0)
