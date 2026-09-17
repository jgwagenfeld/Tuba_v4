"""Test suite for the Green Hydrogen Production & Storage Facility layout project."""

from __future__ import annotations

import json
from pathlib import Path

from tuba.clash import ClashEngine
from tuba.project import load_project
from tuba.visualization import build_visualization_scene, write_scene_bundle

PROJECT_ROOT = Path(__file__).resolve().parents[1] / "examples" / "hydrogen-plant-layout"


def test_hydrogen_plant_model_loads_and_validates():
    """Verify that the model script loads through load_project and passes validation."""
    project = load_project(PROJECT_ROOT)
    globals_dict = project.run_model()
    model = globals_dict["model"]

    # Basic entity presence
    assert len(model.nodes) > 40
    assert len(model.elements) > 40
    assert len(model.supports) >= 15

    # Materials and sections
    assert "P265GH" in model.materials
    assert "SS316L" in model.materials
    assert "StructuralSteel" in model.materials

    assert "DN150_SCH40" in model.sections
    assert "DN80_SCH80" in model.sections
    assert "IPE200" in model.sections
    assert "IPE180" in model.sections
    assert "IPE140" in model.sections

    # Analytical obstacles (buildings and storage vessels)
    obstacle_ids = {obs["id"] for obs in model.obstacles}
    expected_obstacles = {
        "electrolyzer_building",
        "compressor_station",
        "purification_building",
        "h2_storage_bullet_1",
        "h2_storage_bullet_2",
        "substation_control_room",
    }
    assert expected_obstacles.issubset(obstacle_ids)

    # Rack assembly groups
    for bay in range(4):
        assert f"main_rack{bay}" in model.groups

    # Operating load case
    assert "Operating" in model.load_cases
    op = model.load_cases["Operating"]
    assert op.internal_pressure == 3.0e6
    assert op.temperature == 65.0
    assert op.gravity is True


def test_hydrogen_plant_has_zero_clashes():
    """Verify that the full cold-model check reports zero collisions.

    ``check_all`` is what Tuba Studio runs on the live model
    (element vs obstacle, element vs element without a topological connection,
    and near-duplicate nodes). Checking obstacles alone missed the routed HP-H2
    loop folding back onto its own outbound run.
    """
    project = load_project(PROJECT_ROOT)
    model = project.run_model()["model"]

    clashes = list(ClashEngine().check_all(model))
    assert len(clashes) == 0, f"Expected 0 clashes, found {len(clashes)}: {clashes}"


def test_hydrogen_plant_routes_terminate_at_their_equipment():
    """Verify each process line ends pointing at the equipment it feeds.

    The routes stop one metre short of the obstacle face, the same standoff the
    nozzle anchors use, so the end node is a reviewable nozzle stub rather than
    a run that overshoots into (or turns away from) the building.
    """
    project = load_project(PROJECT_ROOT)
    model = project.run_model()["model"]

    def route_end(route_id: str):
        routed = [element for element in model.elements if element.route_id == route_id]
        return model.nodes[routed[-1].n2].coords

    # HP-H2 lands on the storage bullet 1 centreline, 1.0 m off its west face.
    assert [round(float(value), 3) for value in route_end("HP_H2")] == [33.0, -3.25, 1.5]
    # LP-H2 lands on the Purification inlet line, 1.0 m off its south face.
    assert [round(float(value), 3) for value in route_end("LP_H2")] == [16.5, 7.0, 1.5]


def test_hydrogen_plant_supports_and_shoes():
    """Verify that structural shoes correctly connect pipe nodes to rack beam midpoints."""
    project = load_project(PROJECT_ROOT)
    model = project.run_model()["model"]

    # Rack friction rest shoes
    rest_shoes = [s for s in model.supports if s.type == "rest"]
    assert len(rest_shoes) == 5  # Station 0..4

    for shoe in rest_shoes:
        assert shoe.friction_coefficient == 0.3
        assert shoe.attached_to is not None
        pipe_node = model.nodes[shoe.node]
        beam_node = model.nodes[shoe.attached_to]

        # Shoes must be aligned in X and Y, with pipe 0.25 m above beam level
        assert abs(pipe_node.coords[0] - beam_node.coords[0]) < 1e-6
        assert abs(pipe_node.coords[1] - beam_node.coords[1]) < 1e-6
        assert abs(pipe_node.coords[2] - (beam_node.coords[2] + 0.25)) < 1e-6

    # Equipment nozzle and rack foot anchors
    anchors = [s for s in model.supports if s.type == "anchor"]
    assert len(anchors) >= 12  # 10 rack foot anchors + 4 equipment nozzle anchors


def test_hydrogen_plant_scene_bundle_export(tmp_path: Path):
    """Verify that the model exports an interactive 3D reviewable scene bundle."""
    project = load_project(PROJECT_ROOT)
    model = project.run_model()["model"]

    scene = build_visualization_scene(model, scene_id="scene:hydrogen_plant_test")
    study = project.load_study("study.py")
    study._add_obstacle_labels(scene, model)
    bundle = write_scene_bundle(scene, tmp_path / "bundle", source=project.model_path)

    assert bundle.scene_path.is_file()
    assert (bundle.metadata_dir / "objects.json").is_file()
    assert (bundle.metadata_dir / "object_map.json").is_file()
    assert (bundle.geometry_dir / "geometry_assets.json").is_file()

    with open(bundle.scene_path, encoding="utf-8") as f:
        payload = json.load(f)

    assert payload["scene_id"] == "scene:hydrogen_plant_test"
    assert len(payload["objects"]) > 50

    # Ensure semantic objects appear in the visual scene
    kinds = {obj["kind"] for obj in payload["objects"]}
    assert "obstacle" in kinds
    assert "pipe" in kinds
    assert "rack_member" in kinds
    assert "support" in kinds
    assert "support_link" in kinds

    # Every analytical obstacle is named in the scene, not just in metadata.
    labelled = {
        obj["name"]
        for obj in payload["objects"]
        if obj["kind"] == "scene_label"
    }
    assert labelled == {
        "Electrolyzer Hall",
        "Compressor Station",
        "Purification & DeOxo",
        "HP H2 Storage Bullet 1",
        "HP H2 Storage Bullet 2",
        "Substation & Control Room",
    }
