from __future__ import annotations

from pathlib import Path

import json

from examples.imported_component_mixed_system import build_model, local_to_global_point, run_demo
from tuba import Model


def _write_tiny_stl(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "solid equipment",
                "facet normal 0 0 1",
                "outer loop",
                "vertex 0 0 0",
                "vertex 1 0 0",
                "vertex 0 1 0",
                "endloop",
                "endfacet",
                "endsolid equipment",
            ]
        ),
        encoding="utf-8",
    )


def test_stl_component_is_connected_but_not_exported_as_solver_results(tmp_path: Path):
    stl_path = tmp_path / "equipment.stl"
    _write_tiny_stl(stl_path)

    summary = run_demo(stl_path, output_root=tmp_path / "out")
    model = Model.from_json(summary["model_path"])

    assert summary["source_format"] == "STL"
    assert Path(summary["scene_dir"], "scene.json").exists()
    assert summary["study_dir"] is None
    assert summary["result_status"] == "model_connected_only"
    assert "STEP/STP volume asset" in summary["runtime_blocker"]
    assert model.cad_assets["cad_asset_custom_equipment"].source_format == "STL"
    assert model.imported_components["component_custom_equipment"].asset.id == "cad_asset_custom_equipment"
    assert model.ports["port_equipment_nozzle_a"].status == "confirmed"
    assert model.couplings["coupling_pipe_to_equipment_a"].target.id == "port_equipment_nozzle_a"

    scene = json.loads(Path(summary["scene_dir"], "scene.json").read_text(encoding="utf-8"))
    kinds = {obj["kind"] for obj in scene["objects"]}
    assert "imported_component" in kinds
    assert "imported_port" in kinds
    assert "mixed_coupling" in kinds
    assert "local_coordinate_axis" in kinds


def test_step_component_can_be_modeled_without_forcing_export(tmp_path: Path):
    step_path = tmp_path / "equipment.step"
    step_path.write_text("ISO-10303-21;\nEND-ISO-10303-21;\n", encoding="utf-8")

    model = build_model(step_path)
    summary = run_demo(step_path, output_root=tmp_path / "out", export_study=False)

    assert model.cad_assets["cad_asset_custom_equipment"].source_format == "STEP"
    assert "coupling_pipe_to_equipment_a" in model.couplings
    assert summary["source_format"] == "STEP"
    assert summary["study_dir"] is None


def test_asset_local_coordinates_are_transformed_to_global_port(tmp_path: Path):
    stl_path = tmp_path / "equipment.stl"
    _write_tiny_stl(stl_path)
    placement = {"origin": [2.0, 0.75, 0.25], "rotation": [1.0, 0.0, 0.0, 0.0]}

    model = build_model(
        stl_path,
        asset_origin=placement["origin"],
        asset_rotation=placement["rotation"],
        local_port_position=[0.0, 0.0, 0.0],
    )

    port = model.ports["port_equipment_nozzle_a"]
    assert list(port.position) == local_to_global_point([0.0, 0.0, 0.0], placement)
    assert list(model.nodes["N1"].coords) == list(port.position)
    assert model.cad_assets["cad_asset_custom_equipment"].placement == placement
