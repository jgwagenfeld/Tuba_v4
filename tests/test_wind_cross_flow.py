"""The wind rule Code_Aster applies with FORCE_POUTRE(TYPE_CHARGE='VENT'), reproduced for TUYAU_3M."""
import math

import numpy as np
import pytest

from tuba.solver.aster_loads import cross_flow_formula, cross_flow_line_load


def evaluate(texts, point):
    """Evaluate FORMULE text the way Code_Aster sees it: X, Y, Z and math's sqrt."""
    scope = {"X": float(point[0]), "Y": float(point[1]), "Z": float(point[2]), "sqrt": math.sqrt}
    return tuple(eval(compile(text, "<FORMULE>", "eval"), {"__builtins__": {}}, scope) for text in texts)


def test_head_on_wind_is_carried_in_full():
    assert cross_flow_line_load([0.0, 1000.0, 0.0], [1.0, 0.0, 0.0]) == pytest.approx((0.0, 1000.0, 0.0))


def test_wind_along_the_axis_carries_nothing():
    assert cross_flow_line_load([1000.0, 0.0, 0.0], [2.0, 0.0, 0.0]) == pytest.approx((0.0, 0.0, 0.0))


def test_oblique_wind_matches_the_solved_vent_straight():
    # Solved on POU_D_T with VENT: 1000 N/m at 30 degrees over 4 m gave 1000 N across the axis.
    angle = math.radians(30.0)
    carried = cross_flow_line_load([1000.0 * math.cos(angle), 1000.0 * math.sin(angle), 0.0], [1.0, 0.0, 0.0])
    assert carried == pytest.approx((0.0, 250.0, 0.0))


def test_no_wind_gives_no_load():
    assert cross_flow_line_load([0.0, 0.0, 0.0], [1.0, 0.0, 0.0]) == (0.0, 0.0, 0.0)
    assert cross_flow_formula([0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 1.0]) == ("0.0", "0.0", "0.0")


def test_bend_formula_equals_the_point_rule_on_a_tilted_bend():
    axis = np.array([1.0, 1.0, 1.0]) / math.sqrt(3.0)
    center = np.array([2.0, -1.0, 0.5])
    start = np.array([1.0, -1.0, 0.0]) / math.sqrt(2.0)
    across = np.cross(axis, start)
    wind = (300.0, -1000.0, 200.0)
    texts = cross_flow_formula(wind, center, axis)
    for phi in np.linspace(0.0, math.pi / 2.0, 7):
        point = center + 0.5 * (math.cos(phi) * start + math.sin(phi) * across)
        tangent = np.cross(axis, point - center)
        assert evaluate(texts, point) == pytest.approx(cross_flow_line_load(wind, tangent), abs=1e-9)


def test_bend_formula_integrates_to_the_solved_vent_elbow():
    # Solved on POU_D_T with VENT: a 90 degree, 0.5 m elbow under 1000 N/m in -Y gave
    # reactions (-166.7, +333.3) N, so the elbow carried (R/3, -2R/3) x 1000 N.
    radius = 0.5
    texts = cross_flow_formula((0.0, -1000.0, 0.0), (0.0, radius, 0.0), (0.0, 0.0, 1.0))
    steps = 400
    total = np.zeros(3)
    for i in range(steps):
        phi = (i + 0.5) * (math.pi / 2.0) / steps
        point = (radius * math.sin(phi), radius - radius * math.cos(phi), 0.0)
        total += np.array(evaluate(texts, point)) * radius * (math.pi / 2.0) / steps
    assert tuple(total) == pytest.approx((1000.0 * radius / 3.0, -2000.0 * radius / 3.0, 0.0), rel=1e-5, abs=1e-6)
