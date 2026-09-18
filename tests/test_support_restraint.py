"""Support restraint states: one record the solver, the scene and the viewer read."""

import pytest

from tuba import Model
from tuba.model import Support
from tuba.solver.aster_comm import _held_dofs, _spring_stiffness
from tuba.visualization import SceneRequest, build_visualization_scene


def _model():
    model = Model("Restraint")
    model.add_material("Steel", E=2.1e11, nu=0.3)
    model.add_pipe_section("DN", OD=0.1, WT=0.01)
    n0 = model.add_node([0.0, 0.0, 0.0])
    n1 = model.add_node([1.0, 0.0, 0.0])
    model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="DN", material="Steel")
    model.define_load_case("Hot", gravity=False)
    return model, n0, n1


def test_an_anchor_fixes_every_axis():
    restraint = Support(node="N0", type="anchor").restraint()

    assert restraint.states == ("fixed",) * 6
    assert restraint.spring_stiffness == (0.0,) * 6


def test_a_guide_fixes_only_its_direction():
    restraint = Support(node="N0", type="guide", direction=[0.0, 1.0, 0.0]).restraint()

    assert restraint.states == ("free", "fixed", "free", "free", "free", "free")


def test_a_rest_acts_one_way_on_its_axis():
    assert Support(node="N0", type="rest").restraint().states == (
        "free", "free", "one-way", "free", "free", "free",
    )
    assert Support(node="N0", type="rest", direction=[1.0, 0.0, 0.0]).restraint().states == (
        "one-way", "free", "free", "free", "free", "free",
    )


def test_a_spring_matrix_springs_its_nonzero_axes():
    restraint = Support(node="N0", type="spring", stiffness_matrix=[0.0, 0.0, 1.0e5, 0.0, 0.0, 0.0]).restraint()

    assert restraint.states == ("free", "free", "spring", "free", "free", "free")
    assert restraint.spring_stiffness == (0.0, 0.0, 1.0e5, 0.0, 0.0, 0.0)


def test_a_scalar_spring_needs_a_direction():
    restraint = Support(node="N7", type="spring", stiffness=1.0e6, direction=[0.0, 0.0, 1.0]).restraint()
    assert restraint.states == ("free", "free", "spring", "free", "free", "free")
    assert restraint.spring_stiffness == (0.0, 0.0, 1.0e6, 0.0, 0.0, 0.0)

    with pytest.raises(ValueError, match="uses scalar stiffness without direction"):
        Support(node="N7", type="spring", stiffness=1.0e6).restraint()


def test_an_explicit_blocked_dof_list_wins_and_springs_fill_the_rest():
    restraint = Support(
        node="N0",
        type="anchor",
        blocked_dof=[False, True, False, False, False, False],
        stiffness_matrix=[1.0, 0.0, 3.0, 0.0, 0.0, 0.0],
    ).restraint()

    assert restraint.states == ("spring", "fixed", "spring", "free", "free", "free")
    assert restraint.spring_stiffness == (1.0, 0.0, 3.0, 0.0, 0.0, 0.0)


def test_solver_projections_read_the_record():
    guide = Support(node="N0", type="guide", direction=[0.0, 1.0, 0.0])
    spring = Support(node="N0", type="spring", stiffness_matrix=[0.0, 0.0, 1.0e5, 0.0, 0.0, 0.0])

    assert _held_dofs(guide) == ["DY"]
    assert _spring_stiffness(spring) == [0.0, 0.0, 1.0e5, 0.0, 0.0, 0.0]


def test_the_scene_carries_the_restraint_states():
    model, n0, n1 = _model()
    model.add_support(n0, "anchor", id="anchor")
    model.add_support(n1, "rest", id="shoe")

    scene = build_visualization_scene(SceneRequest(model))
    supports = {obj.name: obj.metadata for obj in scene.objects if obj.kind == "support"}

    assert supports["anchor"]["dof_states"] == ["fixed"] * 6
    assert supports["shoe"]["dof_states"] == ["free", "free", "one-way", "free", "free", "free"]
