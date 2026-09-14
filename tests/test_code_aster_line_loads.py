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


def straight_model(name: str) -> tuple[Model, tuple[str, str]]:
    """A 4 m straight along X, anchored at both ends."""
    model = Model(project_name=name)
    model.add_material("Steel", E=2.0e11, nu=0.3, rho=7850.0, alpha=1.2e-5)
    model.add_pipe_section("Pipe", OD=0.1, WT=0.01)
    start = model.add_node([0.0, 0.0, 0.0])
    end = model.add_node([RUN_LENGTH, 0.0, 0.0])
    model.add_element(id="run", type="pipe_straight", n1=start, n2=end, section="Pipe", material="Steel")
    model.add_support(start, "anchor")
    model.add_support(end, "anchor")
    return model, (start, end)


def solve_wind(build, name: str, direction: list[float], modelization: str) -> list[float]:
    model, anchors = build(f"{name} {modelization}")
    # 10 kPa on the 0.1 m pipe is 1000 N/m head-on.
    model.define_operation("Wind", gravity=False).add_field("wind", 10000.0, direction=direction)
    root = Path(f".build/line-load-references/{name}-{modelization}").resolve()
    run = model.solve("Wind", pipe_modelization=modelization, work_dir=str(root), force=True)
    return reaction_total(run, anchors)


def test_tuyau_wind_matches_beam_vent_on_an_oblique_straight():
    angle = math.radians(30.0)
    direction = [math.cos(angle), math.sin(angle), 0.0]
    tuyau = solve_wind(straight_model, "wind-oblique", direction, "TUYAU_3M")
    beam = solve_wind(straight_model, "wind-oblique", direction, "POU_D_T")
    # Across the axis only, scaled once more by sin(30): 1000 * 0.25 * 4 m = 1000 N in +Y.
    expected = [0.0, -1000.0, 0.0]
    print(f"oblique wind: TUYAU {tuyau}, POU_D_T {beam}, expected {expected}")
    assert beam == pytest.approx(expected, abs=1.0)
    assert tuyau == pytest.approx(expected, abs=1.0)


def test_tuyau_wind_matches_beam_vent_along_an_elbow():
    tuyau = solve_wind(elbow_model, "wind-elbow", [0.0, -1.0, 0.0], "TUYAU_3M")
    beam = solve_wind(elbow_model, "wind-elbow", [0.0, -1.0, 0.0], "POU_D_T")
    # The 4 m run takes 1000 N/m head-on; the elbow carries (R/3, -2R/3) x 1000 N.
    expected = [-1000.0 * BEND_RADIUS / 3.0, 1000.0 * (RUN_LENGTH + 2.0 * BEND_RADIUS / 3.0), 0.0]
    print(f"elbow wind: TUYAU {tuyau}, POU_D_T {beam}, expected {expected}")
    assert beam == pytest.approx(expected, rel=2e-3, abs=1.0)
    assert tuyau == pytest.approx(beam, rel=2e-3, abs=1.0)


def test_wind_and_line_load_on_one_elbow_add_up():
    model, anchors = elbow_model("wind-plus-line-load TUYAU_3M")
    operation = model.define_operation("Both", gravity=False)
    operation.add_field("wind", 10000.0, direction=[0.0, -1.0, 0.0])
    operation.add_field("line_load", 1000.0, direction=[0.0, 0.0, -1.0])
    root = Path(".build/line-load-references/wind-plus-line-load-TUYAU_3M").resolve()
    run = model.solve("Both", pipe_modelization="TUYAU_3M", work_dir=str(root), force=True)
    observed = reaction_total(run, anchors)
    expected = [
        -1000.0 * BEND_RADIUS / 3.0,
        1000.0 * (RUN_LENGTH + 2.0 * BEND_RADIUS / 3.0),
        1000.0 * (RUN_LENGTH + BEND_LENGTH),
    ]
    print(f"wind + line load: reactions {observed}, expected {expected}")
    assert observed == pytest.approx(expected, rel=2e-3, abs=1.0)


def tilted_elbow_model(name: str) -> tuple[Model, tuple[str, str]]:
    """The elbow model rotated 30 degrees about X, so the bend axis is not along X, Y or Z."""
    tilt = math.radians(30.0)
    c, s = math.cos(tilt), math.sin(tilt)
    model = Model(project_name=name)
    model.add_material("Steel", E=2.0e11, nu=0.3, rho=7850.0, alpha=1.2e-5)
    model.add_pipe_section("Pipe", OD=0.1, WT=0.01)
    start = model.add_node([0.0, 0.0, 0.0])
    corner = model.add_node([RUN_LENGTH, 0.0, 0.0])
    end = model.add_node([RUN_LENGTH + BEND_RADIUS, BEND_RADIUS * c, BEND_RADIUS * s])
    model.add_element(id="run", type="pipe_straight", n1=start, n2=corner, section="Pipe", material="Steel")
    model.add_element(
        id="elbow", type="pipe_bend", n1=corner, n2=end, section="Pipe", material="Steel",
        bend_radius=BEND_RADIUS, bend_angle=90,
        bend_geometry=BendGeometry(
            center=[RUN_LENGTH, BEND_RADIUS * c, BEND_RADIUS * s], normal=[0.0, -s, c], radius=BEND_RADIUS,
            angle=90, start_tangent=[1.0, 0.0, 0.0], end_tangent=[0.0, c, s],
        ),
    )
    model.add_support(start, "anchor")
    model.add_support(end, "anchor")
    return model, (start, end)


def test_tuyau_wind_matches_beam_vent_on_a_tilted_elbow():
    # The bend axis is (0, -sin 30, cos 30), so the bend FORMULE text carries full-precision numbers.
    tuyau = solve_wind(tilted_elbow_model, "wind-tilted-elbow", [0.0, -1.0, 0.0], "TUYAU_3M")
    beam = solve_wind(tilted_elbow_model, "wind-tilted-elbow", [0.0, -1.0, 0.0], "POU_D_T")
    print(f"tilted elbow wind: TUYAU {tuyau}, POU_D_T {beam}")
    assert tuyau == pytest.approx(beam, rel=2e-3, abs=1.0)
