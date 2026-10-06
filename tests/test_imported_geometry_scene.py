"""Actual imported surfaces and authored mixed connection intent in review scenes."""

import math

import pytest

from tuba import Model
from tuba.visualization.builders._imported import _build_imported_component_scene


def scene_channels(model):
    scene = _build_imported_component_scene(model)
    return scene.objects, scene.assets, scene.diagnostics


def component_model(*, source_format="STEP", metadata=None):
    model = Model("Imported scene")
    model.add_material("Steel", E=2e11, nu=.3)
    model.add_cad_asset(id="part_asset", source_path="fixture.step", source_format=source_format,
        unit_scale_to_m=.001, placement={"origin": [10, 20, 30], "rotation": [math.sqrt(.5), 0, 0, math.sqrt(.5)]},
        metadata=metadata or {"mesh_vertices_local": [[0, 0, 0], [1000, 0, 0], [0, 2000, 0]],
                             "mesh_faces": [[0, 1, 2]], "local_bounds": [0, 0, 0, 1000, 2000, 0]})
    model.add_imported_component(id="part", asset="cad_asset:part_asset", name="Part", role="reference" if source_format == "STL" else "equipment")
    return model


def test_surface_geometry_retains_triangles_and_applies_scale_placement_once():
    model = component_model(source_format="STL")
    objects, assets, diagnostics = scene_channels(model)
    obj = next(obj for obj in objects if obj.kind == "imported_component")
    asset = next(asset for asset in assets if asset.id == obj.geometry_asset_id)
    assert asset.format == "mesh"
    assert asset.generation_config["faces"] == [[0, 1, 2]]
    assert asset.bounds == pytest.approx([8, 20, 30, 10, 21, 30])
    assert asset.generation_config["vertices"][1] == pytest.approx([10, 21, 30])
    assert obj.metadata["geometry_representation"] == "source_surface"
    assert obj.metadata["placed_bounds_m"] == asset.bounds
    assert obj.metadata["analysis_regions"] == []
    assert obj.metadata["role"] == "reference"
    assert not diagnostics
    assert model.cad_assets["part_asset"].metadata["mesh_vertices_local"][1] == [1000, 0, 0]


def test_missing_actual_import_surface_is_an_error_and_legacy_envelope_is_explicit():
    broken = {"analysis_import_version": 1, "local_bounds": [0, 0, 0, 1, 1, 1],
              "mesh_vertices_local": [[0, 0, 0], [1, 0, 0], [0, 1, 0]], "mesh_faces": [[0, 1, 3]]}
    objects, assets, diagnostics = scene_channels(component_model(metadata=broken))
    assert not objects and not assets
    assert [(d.severity, d.code) for d in diagnostics] == [("error", "imported_component.missing_surface")]
    objects, _, diagnostics = scene_channels(component_model(metadata={"local_bounds": [0, 0, 0, 1, 1, 1]}))
    assert next(obj for obj in objects if obj.kind == "imported_component").metadata["geometry_representation"] == "bounds_envelope"
    assert diagnostics[0].severity == "warning"
    assert "only its declared bounds envelope" in diagnostics[0].message


@pytest.mark.parametrize("selection, expected", [("vertices", [[0, 0, 0], [1, 0, 0]]),
    ("edges", [[0, 0, 0], [1, 0, 0]]), ("nodes", [[0, 0, 0], [1, 0, 0]])])
def test_rigid_patch_shows_selected_physical_geometry_and_exact_released_node_link(selection, expected):
    model = Model("Patch scene")
    model.add_material("Steel", E=2e11, nu=.3)
    model.add_shell_panel("panel", polygon=[[0, 0, 0], [1, 0, 0], [0, 1, 0]], thickness=.01, material="Steel")
    reference = model.add_reference_point("ref", position=[0, 0, 1])
    frame = model.add_node([.01, 0, 1])
    model.add_support(reference, "custom", attached_to=frame, blocked_dof=[1, 1, 0, 1, 1, 1], attachment_mode="dof_equality")
    if selection == "nodes":
        model.add_rigid_patch("patch", reference=reference, nodes=[model.add_node(point) for point in expected])
    else:
        model.add_rigid_patch("patch", reference=reference, shell="panel", **{selection: [0, 1] if selection == "vertices" else [0]})
    objects, assets, diagnostics = scene_channels(model)
    patch = next(obj for obj in objects if obj.kind == "mixed_coupling")
    asset = next(asset for asset in assets if asset.id == patch.geometry_asset_id)
    assert asset.format == "polyline"
    assert asset.generation_config["points"] == [[0, 0, 1], expected[0], [0, 0, 1], expected[1], [0, 0, 1]]
    assert patch.metadata["attachments"][0]["held_dof"] == ["DX", "DY", "DRX", "DRY", "DRZ"]
    assert patch.metadata["attachments"][0]["released_dof"] == ["DZ"]
    assert patch.metadata["attachments"][0]["offset_m"] == pytest.approx([-.01, 0, 0])
    assert patch.metadata["attachments"][0]["attachment_mode"] == "dof_equality"
    assert patch.layer_ids == ["imported_components", "mixed_couplings"]
    assert not diagnostics


def test_component_patch_positions_are_source_local_and_beam_ports_share_existing_scene_contract():
    model = component_model()
    model.add_analysis_region(id="part_solid", owner="component:part", role="solid_3d", code_aster_modelisation="3D", material="Steel", mesh_group="G_PART_SOLID")
    reference = model.add_reference_point("ref", position=[10, 21, 31])
    model.add_rigid_patch("face_patch", reference=reference, component="part", faces=[{"position": [1000, 0, 0]}])
    model.add_rectangular_section("Frame", height_y=.1, height_z=.1)
    a, b = model.add_node([9, 21, 30]), model.add_node([10, 21, 30])
    model.add_element(id="frame", type="beam", n1=a, n2=b, section="Frame", material="Steel")
    model.add_port(id="cut", owner="component:part", kind="circular_face", position=[10, 21, 30], axis=[1, 0, 0], radius=.1, face_group="G_CUT", status="confirmed")
    model.add_port(id="candidate", owner="component:part", kind="circular_face", position=[10, 22, 30], axis=[1, 0, 0], radius=.1, status="detected")
    model.connect_beam_to_port(beam="element:frame", node=f"node:{b}", port="port:cut", id="beam_cut")
    objects, assets, _ = scene_channels(model)
    by_ref = {str(obj.entity_ref): obj for obj in objects if obj.kind != "local_coordinate_axis"}
    by_asset = {asset.id: asset for asset in assets}
    patch = by_ref["coupling:face_patch"]
    assert by_asset[patch.geometry_asset_id].generation_config["points"][1] == pytest.approx([10, 21, 30])
    beam = by_ref["coupling:beam_cut"]
    assert beam.kind == "mixed_coupling"
    assert beam.metadata["continuation_family"] == "frame"
    assert beam.metadata["code_aster_option"] == "3D_POU"
    assert by_asset[by_ref["port:cut"].geometry_asset_id].generation_config["color"] != by_asset[by_ref["port:candidate"].geometry_asset_id].generation_config["color"]
    component = by_ref["component:part"]
    assert [record["id"] for record in component.metadata["couplings"]] == ["face_patch", "beam_cut"]
    assert component.metadata["analysis_regions"][0]["code_aster_modelisation"] == "3D"


def test_support_on_a_patch_reference_reports_the_patch_extent_for_its_glyph():
    # A lug support drives a rigid patch and touches no element: without this the
    # viewer sized it by the model span and drew it larger than the part it holds.
    from tuba.visualization.builders._objects import _build_support_object
    model = Model("Patch support")
    model.add_material("Steel", E=2e11, nu=.3)
    reference = model.add_reference_point("ref", position=[0, 0, 1])
    frame = model.add_node([.01, 0, 1])
    model.add_support(reference, "custom", attached_to=frame, blocked_dof=[1, 1, 0, 1, 1, 1], attachment_mode="dof_equality")
    model.add_rigid_patch("patch", reference=reference, nodes=[model.add_node(point) for point in ([0, 0, 0], [1, 0, 0])])
    support = next(iter(model.supports.values())) if isinstance(model.supports, dict) else model.supports[-1]
    _, asset = _build_support_object(model, support)
    assert asset.generation_config["body_extent_m"] == pytest.approx(1.0)
    assert "radius_m" not in asset.generation_config
