"""Real Code_Aster references for supports: what each support carries, and where."""
import math
import os
from pathlib import Path

import numpy as np
import pytest

from tuba import Model
from tuba.assemblies import RackBay
from tuba.patches import ModelTransaction

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


def rack_with_pipe_on_top(name):
    """The support-rack bay, whole model at 180 C, pipe on its own nodes 0.25 m above the attachment nodes."""
    model = Model(project_name=name)
    model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0, alpha=1.2e-5)
    model.add_ibeam_section("RackColumnIPE", "IPE160")
    model.add_ibeam_section("RackLongIPE", "IPE140")
    model.add_ibeam_section("RackCrossIPE", "IPE100")
    model.add_pipe_section("DN100", OD=0.1143, WT=0.00602)
    ModelTransaction(model).apply(RackBay(
        name="rack_A", origin=(0.0, -1.0, 0.0), length=4.0, width=2.0, height=3.0, levels=(3.0,),
        section="RackLongIPE", material="Steel", column_section="RackColumnIPE",
        longitudinal_section="RackLongIPE", transverse_section="RackCrossIPE",
    ).to_patch())
    rack = model.groups["rack_A"]
    for node_id in rack["nodes"]:
        if abs(float(model.nodes[node_id].coords[2])) < 1e-9:
            model.add_support(node_id, "anchor")
    points = rack["metadata"]["attachment_points"]
    rack_left = points["level_1_left"].split(":", 1)[1]
    rack_right = points["level_1_right"].split(":", 1)[1]
    start = model.add_node((-2.0, -1.0, 3.25))
    on_left = model.add_node((0.0, -1.0, 3.25))
    on_right = model.add_node((4.0, -1.0, 3.25))
    end = model.add_node((6.0, -1.0, 3.25))
    for element_id, n1, n2 in (("pipe_inlet", start, on_left), ("pipe_rack_span", on_left, on_right), ("pipe_outlet", on_right, end)):
        model.add_element(id=element_id, type="pipe_straight", n1=n1, n2=n2, section="DN100", material="Steel")
    model.add_support(start, "anchor")
    model.add_support(end, "anchor")
    model.define_load_case("Operating", gravity=True, pressure=1.5e6, temperature=180.0, ref_temperature=20.0)
    return model, (on_left, rack_left), (on_right, rack_right)


def post_and_pipe(name, attached):
    """A 2 m post anchored at its base carries a 3 m pipe anchored at its far end."""
    model = Model(project_name=name)
    model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0, alpha=1.2e-5)
    model.add_pipe_section("DN100", OD=0.1143, WT=0.006)
    model.add_rectangular_section("Post", height_y=0.1, height_z=0.1, thickness_y=0.01, thickness_z=0.01)
    base = model.add_node([0.0, 0.0, 0.0])
    top = model.add_node([0.0, 0.0, 2.0])
    far = model.add_node([3.0, 0.0, 2.0])
    model.add_element(id="post", type="beam", n1=base, n2=top, section="Post", material="Steel")
    pipe_start = model.add_node([0.0, 0.0, 2.0]) if attached else top
    model.add_element(id="pipe", type="pipe_straight", n1=pipe_start, n2=far, section="DN100", material="Steel")
    model.add_support(base, "anchor")
    model.add_support(far, "anchor")
    if attached:
        model.add_support(pipe_start, "anchor", attached_to=top)
    model.define_load_case("Hot", gravity=True, pressure=0.0, temperature=120.0, ref_temperature=20.0)
    return model, top


def test_rack_shoe_slides_with_coulomb_friction_under_pressure():
    model, left, right = rack_with_pipe_on_top("RackShoes")
    for index, (pipe_node, rack_node) in enumerate((left, right)):
        model.add_support(pipe_node, "rest", attached_to=rack_node, friction_coefficient=0.3, id=f"shoe_{index}")
    run = solve(model, "Operating", "rack-shoes")
    for index, (pipe_node, rack_node) in enumerate((left, right)):
        contact = run.results.contact_results[f"shoe_{index}"]
        assert contact.status == "sliding"
        assert contact.normal_force == pytest.approx(2728.0, rel=0.02)
        assert float(np.linalg.norm(contact.tangential_force)) == pytest.approx(0.3 * contact.normal_force, rel=0.001)
        slide = run.results.node_results[rack_node].displacement[0] - run.results.node_results[pipe_node].displacement[0]
        assert abs(slide) == pytest.approx(3.83e-3, rel=0.02)
        assert contact.gap < 1e-9
        assert contact.relative_displacement[0] == pytest.approx(-slide)


def test_attached_anchor_between_coincident_nodes_matches_a_shared_node():
    # POU_D_T on both sides: a TUYAU_3M anchor also restrains warping, which a shared node does not.
    shared, shared_top = post_and_pipe("SharedNode", attached=False)
    tied, tied_top = post_and_pipe("TiedNode", attached=True)
    shared_run = solve(shared, "Hot", "shared-node", pipe_modelization="POU_D_T")
    tied_run = solve(tied, "Hot", "tied-node", pipe_modelization="POU_D_T")
    np.testing.assert_allclose(
        tied_run.results.node_results[tied_top].displacement[:3],
        shared_run.results.node_results[shared_top].displacement[:3],
        atol=1e-6,
    )


def test_attached_spring_moves_by_force_over_stiffness():
    model, left, right = rack_with_pipe_on_top("RackSprings")
    for index, (pipe_node, rack_node) in enumerate((left, right)):
        model.add_support(pipe_node, "spring", attached_to=rack_node,
                          stiffness_matrix=[0.0, 0.0, 1.0e7, 0.0, 0.0, 0.0], id=f"spring_{index}")
    run = solve(model, "Operating", "rack-springs")
    for pipe_node, rack_node in (left, right):
        force = run.results.node_results[rack_node].reaction_force[2]
        relative = run.results.node_results[rack_node].displacement[2] - run.results.node_results[pipe_node].displacement[2]
        assert abs(force) == pytest.approx(2629.4, rel=0.02)
        assert relative == pytest.approx(abs(force) / 1.0e7, rel=0.01)
