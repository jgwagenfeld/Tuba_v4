"""Real Code_Aster reference: node temperatures reach every solver node, generated ones included.

A cantilever held at one end expands freely, so its tip moves by
alpha * integral of (T - T_ref) t(s) ds along the centreline, with t the unit tangent.
That integral needs the temperature at every solver node. If the TUYAU midside of the
4 m run kept the 20 degree base, Simpson's rule over its three nodes would give the run
4/6 * (100 + 0 + 180) = 187 instead of 560 degree-metres, so the check would fail.
"""
import math
import os
from pathlib import Path

import numpy as np
import pytest

from tuba import Model
from tuba.model import BendGeometry
from tuba.sampling import field_from_function

pytestmark = pytest.mark.skipif(
    os.environ.get("TUBA_RUN_CODE_ASTER_INTEGRATION") != "1",
    reason="set TUBA_RUN_CODE_ASTER_INTEGRATION=1 to run the real Code_Aster node-temperature reference",
)

ALPHA = 1.2e-5
T_REF = 20.0
RUN_LENGTH = 4.0
BEND_RADIUS = 0.5


def cantilever(name: str) -> tuple[Model, str]:
    """A 4 m straight along X into a 90 degree elbow turning to Y, anchored at the start only."""
    model = Model(project_name=name)
    model.add_material("Steel", E=2.0e11, nu=0.3, rho=7850.0, alpha=ALPHA)
    model.add_pipe_section("Pipe", OD=0.1, WT=0.01)
    start = model.add_node([0.0, 0.0, 0.0])
    corner = model.add_node([RUN_LENGTH, 0.0, 0.0])
    tip = model.add_node([RUN_LENGTH + BEND_RADIUS, BEND_RADIUS, 0.0])
    model.add_element(id="run", type="pipe_straight", n1=start, n2=corner, section="Pipe", material="Steel")
    model.add_element(
        id="elbow", type="pipe_bend", n1=corner, n2=tip, section="Pipe", material="Steel",
        bend_radius=BEND_RADIUS, bend_angle=90,
        bend_geometry=BendGeometry(
            center=[RUN_LENGTH, BEND_RADIUS, 0.0], normal=[0.0, 0.0, 1.0], radius=BEND_RADIUS, angle=90,
            start_tangent=[1.0, 0.0, 0.0], end_tangent=[0.0, 1.0, 0.0],
        ),
    )
    model.add_support(start, "anchor")
    return model, tip


def temperature(x: float, y: float, z: float) -> float:
    """120 degrees at the anchor, 200 at the corner, 260 at the tip."""
    return 120.0 + 20.0 * x + 100.0 * y


def free_expansion(t_start: float, t_corner: float, t_tip: float) -> np.ndarray:
    """Tip displacement: alpha * integral of (T - T_ref) t(s) ds, with T linear along each element."""
    run = RUN_LENGTH * ((t_start + t_corner) / 2.0 - T_REF) * np.array([1.0, 0.0, 0.0])
    # Along the elbow theta runs 0 to pi/2, t = (cos theta, sin theta, 0) and T - T_ref = d + slope * theta.
    # The integral of (d + slope*theta) cos(theta) is d + slope*(pi/2 - 1); with sin(theta) it is d + slope.
    d, slope = t_corner - T_REF, (t_tip - t_corner) / (math.pi / 2.0)
    elbow = BEND_RADIUS * np.array([d + slope * (math.pi / 2.0 - 1.0), d + slope, 0.0])
    return ALPHA * (run + elbow)


@pytest.mark.parametrize("modelization", ["TUYAU_3M", "POU_D_T"])
def test_node_temperatures_expand_the_whole_cantilever(modelization):
    model, tip = cantilever(f"NodeTemperatures {modelization}")
    operation = model.define_operation("Hot", gravity=False, temperature=T_REF, ref_temperature=T_REF)
    written = field_from_function(model, operation, "temperature", temperature)
    assert [(field.node_ids, field.value) for field in written] == [(["N0"], 120.0), (["N1"], 200.0), (["N2"], 260.0)]

    root = Path(f".build/node-temperature-references/{modelization}").resolve()
    run = model.solve("Hot", pipe_modelization=modelization, work_dir=str(root), force=True)

    observed = np.asarray(run.results.node_results[tip].displacement[:3], dtype=float)
    expected = free_expansion(120.0, 200.0, 260.0)
    print(f"node temperatures {modelization}: tip {observed.tolist()}, expected {expected.tolist()}")
    assert float(np.linalg.norm(observed - expected)) <= 0.01 * float(np.linalg.norm(expected))
