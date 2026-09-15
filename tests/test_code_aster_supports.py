"""Real Code_Aster references for supports: what each support carries, and where."""
import math
import os
from pathlib import Path

import pytest

from tuba import Model

pytestmark = pytest.mark.skipif(
    os.environ.get("TUBA_RUN_CODE_ASTER_INTEGRATION") != "1",
    reason="set TUBA_RUN_CODE_ASTER_INTEGRATION=1 to run the real Code_Aster support references",
)

ROOT = Path(".build/support-references")
SPAN_WEIGHT_N = 7850.0 * math.pi * (0.1143 - 0.006) * 0.006 * 9.81 * 6.0


def cantilever(name):
    """A 6 m DN100 pipe along X, anchored at x = 0."""
    model = Model(project_name=name)
    model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0, alpha=1.2e-5)
    model.add_pipe_section("DN100", OD=0.1143, WT=0.006)
    root = model.add_node([0.0, 0.0, 0.0])
    tip = model.add_node([6.0, 0.0, 0.0])
    model.add_element(id="pipe", type="pipe_straight", n1=root, n2=tip, section="DN100", material="Steel")
    model.add_support(root, "anchor", id="anchor")
    return model, root, tip


def solve(model, case, name, **options):
    return model.solve(case, work_dir=str((ROOT / name).resolve()), force=True, **options)


def test_ground_spring_acts_on_its_own_node():
    model, _root, tip = cantilever("GroundSpring")
    model.add_support(tip, "spring", stiffness_matrix=[0.0, 0.0, 1.0e5, 0.0, 0.0, 0.0], id="spring")
    model.define_load_case("Hot", gravity=True, pressure=0.0, temperature=120.0, ref_temperature=20.0)
    run = solve(model, "Hot", "ground-spring")
    # Hand theory: the tip spring carries 325 N and the tip sags 3.25 mm. Unsupported it would sag 40.5 mm.
    assert run.results.node_results[tip].displacement[2] == pytest.approx(-3.25e-3, rel=0.01)


@pytest.mark.parametrize("modelization", ["TUYAU_3M", "POU_D_T"])
def test_rest_carries_three_eighths_of_the_span_weight(modelization):
    model, _root, tip = cantilever(f"Rest {modelization}")
    model.add_support(tip, "rest", id="rest")
    model.define_load_case("Gravity", gravity=True, pressure=0.0, temperature=20.0, ref_temperature=20.0)
    run = solve(model, "Gravity", f"rest-{modelization}", pipe_modelization=modelization)
    tip_result = run.results.node_results[tip]
    assert tip_result.reaction_force[2] == pytest.approx(3.0 / 8.0 * SPAN_WEIGHT_N, rel=0.01)
    assert abs(tip_result.displacement[2]) < 1.0e-5


def test_rest_lifts_off_under_uplift():
    model, _root, tip = cantilever("RestUplift")
    model.add_support(tip, "rest", id="rest")
    case = model.define_load_case("Uplift", gravity=True, pressure=0.0, temperature=20.0, ref_temperature=20.0)
    case.add_nodal_force(tip, force=[0.0, 0.0, 2000.0])
    run = solve(model, "Uplift", "rest-uplift")
    contact = run.results.contact_results["rest"]
    assert contact.status == "open"
    assert abs(contact.normal_force) < 1.0
    assert run.results.node_results[tip].displacement[2] > 0.0
