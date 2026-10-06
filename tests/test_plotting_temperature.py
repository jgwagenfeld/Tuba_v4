"""The model surface mapper shows applied temperature, separately from results."""

import numpy as np
import pytest

from tuba import Model
from tuba.model import OperationField
from tuba.plotting import pipeline
from tuba.solver.base import FEAResults


pytest.importorskip("pyvista")


def _model(*, bend=False):
    model = Model(project_name="Applied temperature display")
    model.add_material("Steel", E=2e11, nu=0.3, alpha=1.2e-5)
    model.add_pipe_section("Pipe", OD=0.1, WT=0.01)
    with model.pipe("Pipe", "Steel", route="P-100") as route:
        route.start([0, 0, 0]).run(1)
        if bend:
            route.bend(radius=0.2, angle=90, plane="XY")
        else:
            route.run(1)
    return model


def _at_x(mesh, x):
    return mesh.point_data["TEMP"][np.isclose(mesh.points[:, 0], x)]


@pytest.mark.parametrize("scope", ["route", "elements"])
def test_local_temperature_overrides_the_case_default(scope):
    model = _model()
    operating = model.define_operation("Operating", temperature=20)
    selector = {"route_id": "P-100"} if scope == "route" else {"element_ids": [model.elements[0].id]}
    operating.add_field("temperature", 120, **selector)
    results = FEAResults(solver_name="Code_Aster", load_case="Operating")

    mesh = pipeline.build_3d_mesh_from_model(model, results)

    np.testing.assert_array_equal(_at_x(mesh, 0), 120)
    np.testing.assert_array_equal(_at_x(mesh, 2), 120 if scope == "route" else 20)
    assert mesh.field_data["TEMP_source"].tolist() == ["applied_input"]
    assert mesh.field_data["TEMP_operation"].tolist() == ["Operating"]
    for field in ["DEPL", "VMIS", "FORC_NODA"]:
        assert np.isnan(mesh.point_data[field]).all(), field


def test_geometry_only_merge_retains_distinct_element_inputs_at_shared_ends():
    model = _model()
    model.define_operation("Operating", temperature=20).add_field(
        "temperature", 120, element_ids=[model.elements[0].id]
    )

    mesh = pipeline.build_3d_mesh_from_model(model)

    assert set(_at_x(mesh, 1)) == {20, 120}
    assert "DEPL" not in mesh.point_data


def test_linear_route_field_shows_the_compilers_constant_element_midpoints():
    model = _model()
    model.define_operation("Operating", temperature=20).add_field(
        "temperature", 120, route_id="P-100", station_start=0, station_end=2, profile="linear"
    )

    mesh = pipeline.build_3d_mesh_from_model(model)

    np.testing.assert_array_equal(_at_x(mesh, 0), 45)
    np.testing.assert_array_equal(_at_x(mesh, 2), 95)
    assert set(_at_x(mesh, 1)) == {45, 95}


def test_node_temperatures_map_straight_ends_and_leave_uncovered_ends_at_default():
    model = _model()
    first, second = model.elements
    operating = model.define_operation("Operating", temperature=20)
    operating.add_field("temperature", 100, node_ids=[first.n1])
    operating.add_field("temperature", 180, node_ids=[first.n2])

    mesh = pipeline.build_3d_mesh_from_model(model)

    np.testing.assert_array_equal(_at_x(mesh, 0), 100)
    np.testing.assert_array_equal(_at_x(mesh, 1), 180)
    np.testing.assert_array_equal(_at_x(mesh, 2), 20)
    assert second.n1 == first.n2


def test_node_temperature_uses_the_neighbour_element_field_at_its_other_end():
    model = _model()
    first, second = model.elements
    operating = model.define_operation("Operating", temperature=20)
    operating.add_field("temperature", 60, node_ids=[first.n1])
    operating.add_field("temperature", 140, element_ids=[second.id])

    mesh = pipeline.build_3d_mesh_from_model(model)

    np.testing.assert_array_equal(_at_x(mesh, 0), 60)
    np.testing.assert_array_equal(_at_x(mesh, 1), 140)
    np.testing.assert_array_equal(_at_x(mesh, 2), 140)


@pytest.mark.parametrize("last_temperature", [140, 220])
def test_node_interpolation_keeps_the_compilers_last_neighbour_field_at_a_junction(last_temperature):
    model = _model()
    first, second = model.elements
    tip = model.add_node([1, 1, 0])
    model.add_element(id="branch", type="pipe_straight", n1=first.n2, n2=tip, section="Pipe", material="Steel")
    operating = model.define_operation("Operating", temperature=20)
    operating.add_field("temperature", 60, node_ids=[first.n1])
    assignments = [(second.id, 140), ("branch", 220)]
    if last_temperature == 140:
        assignments.reverse()
    for element_id, value in assignments:
        operating.add_field("temperature", value, element_ids=[element_id])

    mesh = pipeline.build_3d_mesh_from_model(model)

    # Selecting cells adjacent to x=0 isolates the first member, including
    # its opposite end, even though all three members meet at x=1.
    np.testing.assert_array_equal(_at_x(mesh, 0), 60)
    first_surface = mesh.extract_points(np.isclose(mesh.points[:, 0], 0), adjacent_cells=True)
    shared_end = _at_x(first_surface, 1)
    assert len(shared_end) > 0
    np.testing.assert_array_equal(shared_end, last_temperature)


def test_node_temperatures_interpolate_at_each_bend_display_station():
    model = _model(bend=True)
    bend = model.elements[-1]
    operating = model.define_operation("Operating", temperature=20)
    operating.add_field("temperature", 40, node_ids=[bend.n1])
    operating.add_field("temperature", 200, node_ids=[bend.n2])

    mesh = pipeline.build_3d_mesh_from_model(model)

    # The straight keeps 20 at its free end and 40 at the shared bend end.
    # Each of the bend's 17 cross-sections gets one temperature at arc fraction t.
    np.testing.assert_allclose(np.unique(mesh.point_data["TEMP"]), [20, *np.linspace(40, 200, 17)])
    bend_end = np.asarray(model.nodes[bend.n2].coords)
    at_end = np.isclose(mesh.points[:, 1], bend_end[1])
    np.testing.assert_array_equal(mesh.point_data["TEMP"][at_end], 200)


def test_result_operation_selects_its_own_inputs_and_metadata_survives_vtp(tmp_path):
    model = _model()
    model.define_operation("First", temperature=120)
    model.define_operation("Selected", temperature=60)

    mesh = pipeline.build_3d_mesh_from_model(model, FEAResults(solver_name="Code_Aster", load_case="Selected"))
    np.testing.assert_array_equal(mesh.point_data["TEMP"], 60)
    assert mesh.field_data["TEMP_operation"].tolist() == ["Selected"]
    # An applied-input-only preview avoids unrelated VTK NaN result-array
    # range metadata while exercising the same persisted provenance fields.
    pipeline.build_3d_mesh_from_model(model).save(tmp_path / "applied-temperature.vtp")
    reloaded = pipeline.pv.read(tmp_path / "applied-temperature.vtp")

    np.testing.assert_array_equal(reloaded.point_data["TEMP"], 120)
    assert reloaded.field_data["TEMP_source"].tolist() == ["applied_input"]
    assert reloaded.field_data["TEMP_operation"].tolist() == ["First"]


def test_legacy_load_case_fields_use_the_same_temperature_resolution():
    model = _model()
    model.define_load_case("Legacy", temperature=20, fields=[
        OperationField("temperature", 120, scope="route", route_id="P-100")
    ])

    mesh = pipeline.build_3d_mesh_from_model(model, FEAResults(solver_name="Code_Aster", load_case="Legacy"))

    np.testing.assert_array_equal(mesh.point_data["TEMP"], 120)


def test_no_selected_operation_does_not_invent_temperature():
    model = _model()
    assert "TEMP" not in pipeline.build_3d_mesh_from_model(model).point_data
    model.define_operation("Operating", temperature=120)
    assert "TEMP" not in pipeline.build_3d_mesh_from_model(model, FEAResults(solver_name="Code_Aster")).point_data
    with pytest.raises(ValueError, match="Cannot map temperature for result load case 'Missing'"):
        pipeline.build_3d_mesh_from_model(model, FEAResults(solver_name="Code_Aster", load_case="Missing"))


def test_invalid_field_fails_instead_of_falling_back_to_the_case_default():
    model = _model()
    operating = model.define_operation("Operating", temperature=20)
    operating.fields.append(OperationField("temperature", 120, scope="route", route_id="Missing"))
    with pytest.raises(ValueError, match="selects no pipe elements"):
        pipeline.build_3d_mesh_from_model(model)
