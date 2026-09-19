"""The MCP build_rack tool erects centred pipe-rack rows with shoes in one call."""

from __future__ import annotations

from pathlib import Path

import pytest

from tuba.mcp.server import (
    add_ibeam_section,
    add_material,
    build_pipe_run,
    build_rack,
    build_rack_corner,
    check_clashes,
    configure_load_case,
    get_active_model,
    init_session,
    inspect_model,
)


def _steel_session(model_file: Path):
    init_session(project_name="Rack Tool", file_path=str(model_file), load_existing=False)
    add_material(name="Steel", E=2.1e11, nu=0.3, rho=7850.0, alpha=1.2e-5)
    add_ibeam_section(name="Col", profile_name="IPE160")
    add_ibeam_section(name="Long", profile_name="IPE140")
    add_ibeam_section(name="Cross", profile_name="IPE100")


def test_add_ibeam_section_registers_a_catalog_profile(tmp_path: Path):
    _steel_session(tmp_path / "demo" / "model.py")
    res = add_ibeam_section(name="Beam", profile_name="IPE100")
    assert res == {"status": "success", "section": "Beam", "profile": "IPE100"}
    assert "Beam" in get_active_model().sections


def test_add_ibeam_section_rejects_an_unknown_profile(tmp_path: Path):
    _steel_session(tmp_path / "demo" / "model.py")
    with pytest.raises(ValueError):
        add_ibeam_section(name="Beam", profile_name="NO_SUCH_PROFILE")


def test_build_rack_centres_shoes_on_the_midpoints(tmp_path: Path):
    model_file = tmp_path / "demo" / "model.py"
    _steel_session(model_file)
    built = build_pipe_run(
        section="DN100_SCH40",
        material="P265GH",
        steps=[
            {"op": "start", "point": [-4.0, 1.0, 0.0], "support": "anchor"},
            {"op": "run", "length": 2.0},
            {"op": "run", "length": 2.0},
            {"op": "end", "support": "anchor"},
        ],
    )
    pipe_ids = built["created_node_ids"]  # N0..N2 at x=-4,-2,0

    res = build_rack(
        material="Steel",
        section="Long",
        name_prefix="rack_A",
        origin=[-4.0, 0.0, -3.0],
        direction="X",
        bays=2,
        column_section="Col",
        longitudinal_section="Long",
        transverse_section="Cross",
        shoes=[{"node": pipe_ids[1], "station": 1}],
        zone="yard",
    )
    assert res["status"] == "success"
    assert res["bays"] == ["rack_A0", "rack_A1"]
    assert res["stations"][1] == [-2.0, 1.0, -0.25]
    assert res["shoe_count"] == 1

    model = get_active_model()
    shoe = next(s for s in model.supports if s.type == "rest")
    pipe_node, beam_node = model.nodes[shoe.node], model.nodes[shoe.attached_to]
    assert abs(pipe_node.coords[0] - beam_node.coords[0]) < 1e-9
    assert abs(pipe_node.coords[1] - beam_node.coords[1]) < 1e-9
    assert abs(pipe_node.coords[2] - beam_node.coords[2] - 0.25) < 1e-9
    assert "rack_A0" in model.groups and "rack_A1" in model.groups


def test_build_rack_refuses_an_off_centre_pipe_without_changing_anything(tmp_path: Path):
    model_file = tmp_path / "demo" / "model.py"
    _steel_session(model_file)
    built = build_pipe_run(
        section="DN100_SCH40",
        material="P265GH",
        steps=[
            {"op": "start", "point": [-2.0, 0.0, 0.0], "support": "anchor"},
            {"op": "run", "length": 2.0},
            {"op": "end", "support": "anchor"},
        ],
    )
    before_nodes = len(inspect_model()["nodes"])
    before_text = model_file.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="centreline"):
        build_rack(
            material="Steel",
            section="Long",
            origin=[-2.0, 0.0, -3.0],
            direction="X",
            bays=1,
            shoes=[{"node": built["created_node_ids"][1], "station": 1}],
        )
    assert len(inspect_model()["nodes"]) == before_nodes
    assert model_file.read_text(encoding="utf-8") == before_text


def test_build_rack_marches_along_y(tmp_path: Path):
    model_file = tmp_path / "demo" / "model.py"
    _steel_session(model_file)
    built = build_pipe_run(
        section="DN100_SCH40",
        material="P265GH",
        steps=[
            {"op": "start", "point": [1.0, 0.0, 0.0], "support": "anchor"},
            {"op": "set_direction", "direction": [0.0, 1.0, 0.0]},
            {"op": "run", "length": 2.0},
            {"op": "end", "support": "anchor"},
        ],
    )
    # A Y-row of width 2 from x=0 has its centreline at x=1: the pipe is centred.
    res = build_rack(
        material="Steel",
        section="Long",
        name_prefix="rack_B",
        origin=[0.0, 0.0, -3.0],
        direction="Y",
        bays=1,
        shoes=[{"node": built["created_node_ids"][1], "station": 1}],
    )
    assert res["stations"] == [[1.0, 0.0, -0.25], [1.0, 2.0, -0.25]]
    info = inspect_model()
    assert len(info["supports"]) == 2 + 4 + 1  # anchors, feet, shoe


def test_build_rack_without_shoes_is_a_plain_frame(tmp_path: Path):
    model_file = tmp_path / "demo" / "model.py"
    _steel_session(model_file)
    res = build_rack(material="Steel", section="Long", bays=1)
    assert res["shoe_count"] == 0
    assert all(s["type"] == "anchor" for s in inspect_model()["supports"])
    configure_load_case(name="Operating", internal_pressure_mpa=1.5, temperature_celsius=180.0)


def test_build_rack_reports_new_overlaps_inline(tmp_path: Path):
    model_file = tmp_path / "demo" / "model.py"
    _steel_session(model_file)
    first = build_rack(material="Steel", section="Long", name_prefix="rack_A", bays=2)
    assert first["clash_warnings"] == []

    # A second row hand-placed over the first row's end bay overlaps it: the
    # response says so immediately instead of waiting for a studio glance.
    second = build_rack(
        material="Steel",
        section="Long",
        name_prefix="rack_B",
        origin=[1.0, 0.0, 0.0],
        direction="Y",
        bays=2,
    )
    assert len(second["clash_warnings"]) > 0
    for warning in second["clash_warnings"]:
        pair = (warning["left"]["id"], warning["right"]["id"])
        assert any(element.startswith("rack_B_") for element in pair)
    report = check_clashes()
    assert report["counts"]["self"] == len(second["clash_warnings"])


def test_build_rack_corner_continues_cleanly(tmp_path: Path):
    model_file = tmp_path / "demo" / "model.py"
    _steel_session(model_file)
    build_rack(
        material="Steel",
        section="Long",
        name_prefix="rack_A",
        origin=[0.0, 0.0, -3.0],
        direction="X",
        bays=2,
        column_section="Col",
        longitudinal_section="Long",
        transverse_section="Cross",
    )
    res = build_rack_corner(
        material="Steel",
        section="Long",
        name_prefix="rack_B",
        first_origin=[0.0, 0.0, -3.0],
        first_direction="X",
        first_bays=2,
        first_width=2.0,
        turn="left",
        bays=1,
        column_section="Col",
        longitudinal_section="Long",
        transverse_section="Cross",
    )
    assert res["status"] == "success"
    assert res["corner_post"] == [4.0, 2.0, -3.0]
    assert res["direction"] == "Y"
    assert res["clash_warnings"] == []
    assert check_clashes()["passed"] is True


def test_build_rack_corner_refuses_a_missing_first_row(tmp_path: Path):
    model_file = tmp_path / "demo" / "model.py"
    _steel_session(model_file)
    with pytest.raises(ValueError, match="corner post"):
        build_rack_corner(
            material="Steel",
            section="Long",
            first_origin=[0.0, 0.0, -3.0],
            first_direction="X",
            first_bays=2,
            turn="left",
            bays=1,
        )


def test_inspect_model_maps_elements_to_groups_and_calls(tmp_path: Path):
    model_file = tmp_path / "demo" / "model.py"
    _steel_session(model_file)
    build_rack(material="Steel", section="Long", name_prefix="rack_A", bays=1)
    info = inspect_model()

    assert "rack_A0" in info["groups"]
    assert len(info["groups"]["rack_A0"]["elements"]) > 0
    element_id = info["groups"]["rack_A0"]["elements"][0]
    assert any(e["id"] == element_id for e in info["elements"])
    assert isinstance(info["assembly_calls"], list)
