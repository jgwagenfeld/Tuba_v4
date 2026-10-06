"""Reference surfaces use actual triangles and closed-shell containment."""

import math

import pytest

from tuba import Model
from tuba.clash import ClashEngine

from test_stl_reference import write_ascii


def cube_triangles(scale=1):
    points = [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],
              [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]]
    faces = [[0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7],
             [0, 1, 5], [0, 5, 4], [3, 7, 6], [3, 6, 2],
             [0, 4, 7], [0, 7, 3], [1, 2, 6], [1, 6, 5]]
    return [[[scale*v for v in points[i]] for i in face] for face in faces]


def reference_model(tmp_path, p1, p2, *, triangles=None, scale=1, placement=None):
    from tuba.geometry.stl_reference import import_stl_reference

    model = Model(project_name="clearance")
    model.add_material("Steel", E=2e11, nu=.3)
    model.add_pipe_section("Pipe", OD=.1, WT=.01)
    n1, n2 = model.add_node(p1), model.add_node(p2)
    model.add_element(id="member", type="pipe_straight", n1=n1, n2=n2,
                      section="Pipe", material="Steel")
    import_stl_reference(model, write_ascii(tmp_path / "vessel.stl", triangles or cube_triangles()),
                         id="vessel", unit_scale_to_m=scale, placement=placement)
    return model


@pytest.mark.parametrize("p1,p2,enclosed", [([-1, .5, .5], [2, .5, .5], False),
    ([.2, .5, .5], [.8, .5, .5], True)])
def test_crossing_and_wholly_enclosed_member_are_hard_clashes(tmp_path, p1, p2, enclosed):
    model = reference_model(tmp_path, p1, p2)
    result, = ClashEngine().check_model(model)
    assert str(result.right) == "component:vessel"
    assert result.severity == "hard"
    assert result.distance_m == pytest.approx(0)
    assert result.metadata["enclosed"] is enclosed
    assert model.cad_assets["vessel_asset"].metadata["inspection"]["closed_surface"]


def test_clear_and_clearance_only_member_use_true_surface_distance(tmp_path):
    model = reference_model(tmp_path, [-.5, 1.055, .5], [1.5, 1.055, .5])
    assert ClashEngine().check_model(model) == []
    clash, = ClashEngine().check_model(model, clearance_m=.01)
    assert clash.severity == "clearance"
    assert clash.distance_m == pytest.approx(.055)
    assert clash.penetration_m == pytest.approx(.005)


def test_local_scale_and_rotation_apply_once_to_clearance(tmp_path):
    model = reference_model(tmp_path, [0, 3.5, .5], [3, 3.5, .5],
        triangles=cube_triangles(1000), scale=.001,
        placement={"origin": [2, 3, 0], "rotation": [math.sqrt(.5), 0, 0, math.sqrt(.5)]})
    clash, = ClashEngine().check_model(model)
    assert clash.severity == "hard"


def test_missing_reference_geometry_fails_coverage_explicitly(tmp_path):
    model = reference_model(tmp_path, [-1, .5, .5], [2, .5, .5])
    model.cad_assets["vessel_asset"].metadata.clear()
    with pytest.raises(ValueError, match="clearance.*unavailable"):
        ClashEngine().check_all(model)


def test_declared_port_join_excludes_only_its_local_surface(tmp_path):
    plane = [[[0, -.2, -.2], [0, .2, -.2], [0, .2, .2]],
             [[0, -.2, -.2], [0, .2, .2], [0, -.2, .2]]]
    model = reference_model(tmp_path, [0, 0, 0], [1, 0, 0], triangles=plane)
    assert len(ClashEngine().check_model(model)) == 1
    port = model.add_port(id="join", owner="component:vessel", kind="circular_face", position=[0, 0, 0],
                         axis=[1, 0, 0], radius=.3, status="confirmed")
    model.add_coupling(id="join", kind="pipe_to_solid_port", source="element:member",
        source_node=f"node:{model.elements[0].n1}", target=f"port:{port.id}",
        code_aster_keyword="LIAISON_ELEM", code_aster_option="3D_TUYAU")
    assert ClashEngine().check_model(model) == []
    # A second surface is separate from the named planar interface.
    asset = model.cad_assets["vessel_asset"]
    vertices = asset.metadata["mesh_vertices_local"]
    offset = len(vertices)
    vertices.extend([[.5, -.2, -.2], [.5, .2, -.2], [.5, .2, .2]])
    asset.metadata["mesh_faces"].append([offset, offset+1, offset+2])
    clash, = ClashEngine().check_model(model)
    assert clash.location[0] == pytest.approx(.5)


def test_arbitrary_coupling_is_not_authority_to_skip_interface(tmp_path):
    model = reference_model(tmp_path, [0, .2, .2], [-1, .2, .2])
    port = model.add_port(id="join", kind="circular_face", owner="component:vessel",
                         position=[0, .2, .2], axis=[-1, 0, 0], radius=2, status="confirmed")
    model.add_coupling(id="other", kind="unrelated", source="element:member",
        source_node=f"node:{model.elements[0].n1}", target=f"port:{port.id}",
        code_aster_keyword="unrelated", code_aster_option="unrelated")
    clash, = ClashEngine().check_model(model)
    assert clash.severity == "hard"


def test_triangle_bounds_do_not_substitute_for_triangle_surface(tmp_path):
    model = reference_model(tmp_path, [.9, .9, -.5], [.9, .9, .5],
        triangles=[[[0, 0, 0], [1, 0, 0], [0, 1, 0]]])
    assert ClashEngine().check_model(model) == []


def test_duplicate_surface_does_not_enclose_clear_member(tmp_path):
    triangle = [[0, 0, 0], [1, 0, 0], [0, 1, 0]]
    model = reference_model(tmp_path, [.1, .1, -.3], [.2, .1, -.3], triangles=[triangle, triangle])
    assert ClashEngine().check_model(model) == []


def test_cold_bend_does_not_claim_chord_is_covered(tmp_path):
    model = reference_model(tmp_path, [-1, .5, .5], [2, .5, .5])
    model.elements[0].type = "pipe_bend"
    with pytest.raises(ValueError, match="coverage unavailable for pipe_bend"):
        ClashEngine().check_model(model)


@pytest.mark.parametrize("cold_y,dy,severity,enclosed", [(1.2, -.7, "operating_only_hard", True),
    (1.08, -.08, "operating_only_hard", False), (.5, 1.5, "resolved_in_operating", False)])
def test_operating_reference_checks_actual_deformed_polyline(tmp_path, cold_y, dy, severity, enclosed):
    # Portable deterministic ResultState fixture; this is not native solve evidence.
    from tuba.analysis import ResultState
    from tuba.analysis.states import create_cold_geometry_state, create_operating_geometry_state

    model = reference_model(tmp_path, [.2, cold_y, .5], [.8, cold_y, .5])
    state = ResultState(id=f"fixture_{cold_y}", study_id="portable_fixture", model_revision=0,
        solver_name="Code_Aster", load_case="Hot", mesh_id=None,
        node_displacements={n: (0, dy, 0, 0, 0, 0) for n in model.nodes},
        node_reactions={}, element_results={})
    result, = ClashEngine().check_operating_state(model, cold_state=create_cold_geometry_state(model),
        operating_state=create_operating_geometry_state(model=model, result_state=state),
        result_state=state, envelope_type="bare")
    assert str(result.right) == "component:vessel"
    assert result.severity == severity
    assert result.metadata["operating_enclosed"] is enclosed
    assert math.isfinite(result.metadata["cold_distance_m"])
    assert math.isfinite(result.metadata["operating_distance_m"])
    assert result.metadata["introduced_by_deformation"] is (severity == "operating_only_hard")


def test_operating_bend_requires_generated_centerline_nodes(tmp_path):
    from tuba.analysis import ResultState
    from tuba.analysis.states import create_cold_geometry_state, create_operating_geometry_state

    model = reference_model(tmp_path, [-1, .5, .5], [2, .5, .5])
    model.elements[0].type = "pipe_bend"
    state = ResultState(id="bend_fixture", study_id="portable_fixture", model_revision=0,
        solver_name="Code_Aster", load_case="Hot", mesh_id=None,
        node_displacements={n: (0, 0, 0, 0, 0, 0) for n in model.nodes},
        node_reactions={}, element_results={})
    with pytest.raises(ValueError, match="STL.*bend.*centerline"):
        ClashEngine().check_operating_state(model, cold_state=create_cold_geometry_state(model),
            operating_state=create_operating_geometry_state(model=model, result_state=state),
            result_state=state)
