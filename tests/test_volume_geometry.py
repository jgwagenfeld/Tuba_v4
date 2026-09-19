"""The pipe-volume solid is one record: geometry, mesh, and identity pin it."""

import pytest

from tuba import Model
from tuba.geometry.volume import (
    CylinderSolid,
    VolumeGeometry,
    build_volume_geometry,
)
from tuba.model import make_bend_geometry
from tuba.solver.aster_volume import volume_study_inputs


def _straight_pipe_model(*, od=0.1, wt=0.01, length=0.2):
    model = Model("StraightVolumeGeometry")
    model.add_material("Steel", E=2.1e11, nu=0.3)
    model.add_pipe_section("Pipe", OD=od, WT=wt)
    n0 = model.add_node([0.0, 0.0, 0.0])
    n1 = model.add_node([length, 0.0, 0.0])
    model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="Pipe", material="Steel")
    model.define_load_case("Pressure", pressure=1.0e6)
    return model, n0, n1


def _tee_model(*, branch_od=0.1):
    model = Model("TeeVolumeGeometry")
    model.add_material("Steel", E=2.1e11, nu=0.3)
    model.add_pipe_section("Header", OD=0.1, WT=0.01)
    branch_section = "Header"
    if branch_od != 0.1:
        branch_section = "Branch"
        model.add_pipe_section(branch_section, OD=branch_od, WT=0.008)
    junction = model.add_node([0.0, 0.0, 0.0])
    ends = (
        model.add_node([-0.12, 0.0, 0.0]),
        model.add_node([0.12, 0.0, 0.0]),
        model.add_node([0.0, 0.12, 0.0]),
    )
    for element_id, end, section in zip(
        ("left", "right", "branch"),
        ends,
        ("Header", "Header", branch_section),
    ):
        model.add_element(
            id=element_id,
            type="pipe_straight",
            n1=junction,
            n2=end,
            section=section,
            material="Steel",
        )
    model.define_tee(junction)
    model.define_load_case("Pressure", pressure=1.0e6)
    return model, junction, ends


def _bend_pipe_model():
    model = Model("BendVolumeGeometry")
    model.add_material("Steel", E=2.1e11, nu=0.3)
    model.add_pipe_section("Pipe", OD=0.1, WT=0.01)
    n0 = model.add_node([0.0, 0.0, 0.0])
    n1 = model.add_node([0.1, 0.1, 0.0])
    geometry = make_bend_geometry(
        start=model.nodes[n0].coords,
        end=model.nodes[n1].coords,
        radius=0.1,
        angle=90.0,
        normal=[0.0, 0.0, 1.0],
        start_tangent=[1.0, 0.0, 0.0],
        end_tangent=[0.0, 1.0, 0.0],
        generation_mode="bend",
    )
    model.add_element(
        id="bend_0",
        type="pipe_bend",
        n1=n0,
        n2=n1,
        section="Pipe",
        material="Steel",
        bend_radius=geometry.radius,
        bend_angle=geometry.angle,
        bend_geometry=geometry,
    )
    model.define_load_case("Pressure", pressure=1.0e6)
    return model, n0, n1


def test_straight_geometry_is_one_outer_and_one_inner_cylinder():
    model, n0, n1 = _straight_pipe_model()

    geometry = build_volume_geometry(model, ["pipe_0"])

    assert geometry.kind == "straight"
    assert geometry.element_ids == ("pipe_0",)
    assert geometry.material == "Steel"
    assert geometry.outer == (CylinderSolid((0.0, 0.0, 0.0), (0.2, 0.0, 0.0), 0.05),)
    assert geometry.inner == (CylinderSolid((0.0, 0.0, 0.0), (0.2, 0.0, 0.0), 0.04),)
    assert geometry.wall_thickness_m == pytest.approx(0.01)
    assert [(terminal.node_id, terminal.role) for terminal in geometry.terminals] == [
        (n0, "run"),
        (n1, "run"),
    ]


def test_bend_geometry_is_one_swept_annulus():
    model, n0, n1 = _bend_pipe_model()

    geometry = build_volume_geometry(model, ["bend_0"])

    assert geometry.kind == "bend"
    assert geometry.outer == () and geometry.inner == ()
    annulus = geometry.swept_annulus
    assert annulus is not None
    assert annulus.outer_radius == pytest.approx(0.05)
    assert annulus.inner_radius == pytest.approx(0.04)
    assert annulus.angle_deg == pytest.approx(90.0)
    assert annulus.center == pytest.approx((0.0, 0.1, 0.0))
    assert [(terminal.node_id, terminal.role) for terminal in geometry.terminals] == [
        (n0, "run"),
        (n1, "run"),
    ]


def test_tee_geometry_fuses_header_and_branch_and_roles_every_terminal():
    model, junction, ends = _tee_model(branch_od=0.06)

    geometry = build_volume_geometry(model, ["left", "right", "branch"])

    assert geometry.kind == "tee"
    assert geometry.tee_node == junction
    assert geometry.element_ids == ("branch", "left", "right")
    assert geometry.header_element_ids == ("left", "right")
    assert geometry.branch_element_id == "branch"
    assert [solid.radius for solid in geometry.outer] == pytest.approx([0.05, 0.03])
    assert [solid.radius for solid in geometry.inner] == pytest.approx([0.04, 0.022])
    assert geometry.wall_thickness_m == pytest.approx(0.008)
    assert {(terminal.node_id, terminal.role) for terminal in geometry.terminals} == {
        (ends[0], "header"),
        (ends[1], "header"),
        (ends[2], "branch"),
    }


def test_fingerprint_is_stable_and_selection_order_independent():
    model, _junction, _ends = _tee_model()

    first = build_volume_geometry(model, ["left", "right", "branch"])
    again = build_volume_geometry(model, ["right", "left", "branch"])
    reordered = build_volume_geometry(model, ["branch", "right", "left"])

    assert first.fingerprint == again.fingerprint == reordered.fingerprint
    assert first.id == reordered.id
    assert first.id.startswith("volume_geometry:")


def test_fingerprint_moves_when_the_solid_changes():
    model, _n0, _n1 = _straight_pipe_model()
    original = build_volume_geometry(model, ["pipe_0"])

    model.sections["Pipe"].OD = 0.12
    changed = build_volume_geometry(model, ["pipe_0"])

    assert changed.fingerprint != original.fingerprint
    assert changed.outer[0].radius == pytest.approx(0.06)


def test_geometry_round_trips_through_its_dict():
    model, _junction, _ends = _tee_model(branch_od=0.06)
    geometry = build_volume_geometry(model, ["left", "right", "branch"])

    restored = VolumeGeometry.from_dict(geometry.to_dict())

    assert restored == geometry
    assert restored.fingerprint == geometry.fingerprint


def test_volume_study_identity_pins_the_geometry_definition():
    model, _n0, _n1 = _straight_pipe_model()

    inputs = volume_study_inputs(model, "Pressure", element_ids=["pipe_0"], max_element_size=0.005)

    assert inputs.compiler_inputs["volume_geometry"] == inputs.geometry.to_dict()
    assert inputs.solver_input_identity.fingerprint
    assert inputs.geometry.element_ids == ("pipe_0",)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda model: model.get_element("pipe_0").__setattr__("type", "pipe_bend"), "explicit bend_geometry"),
        (lambda model: model.sections.__setitem__("Pipe", model.sections["Pipe"].__class__(
            name="Pipe", OD=0.1, WT=0.06
        )), "positive bore"),
    ],
)
def test_rejects_unmeshable_runs(mutate, message):
    model, _n0, _n1 = _straight_pipe_model()
    mutate(model)

    with pytest.raises(ValueError, match=message):
        build_volume_geometry(model, ["pipe_0"])


def test_rejects_an_undeclared_tee():
    model, junction, _ends = _tee_model()
    del model.tees[junction]

    with pytest.raises(ValueError, match="explicit tee"):
        build_volume_geometry(model, ["left", "right", "branch"])
