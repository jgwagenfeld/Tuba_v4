"""Unit and integration tests for Tuba MCP Server and Studio Live Bridge."""

from __future__ import annotations

import json
import time
from pathlib import Path
import pytest

from tuba.mcp.server import (
    add_material,
    add_pipe_section,
    apply_model_patch,
    build_pipe_run,
    configure_load_case,
    export_python_script,
    get_active_model,
    init_session,
    inspect_model,
    solve_model,
)
from tuba.model import TubaModel
from tuba.project import run_model_script
from tuba.project.script import same_model
import tuba.mcp.server as mcp_server


def test_init_and_inspect(tmp_path: Path):
    model_file = tmp_path / "rig" / "model.py"
    init_res = init_session(
        project_name="Test Rig",
        standard="ASME B31.3",
        file_path=str(model_file),
        load_existing=False,
    )
    assert init_res["status"] == "initialized"
    assert model_file.is_file()

    info = inspect_model()
    assert info["project_name"] == "Test Rig"
    assert "P265GH" in info["materials"]
    assert "DN100_SCH40" in info["sections"]


def test_build_pipe_run_procedural(tmp_path: Path):
    model_file = tmp_path / "pipe" / "model.py"
    init_session(project_name="Pipe Run Test", file_path=str(model_file), load_existing=False)

    steps = [
        {"op": "start", "point": [0.0, 0.0, 0.0], "support": "anchor"},
        {"op": "run", "length": 4.0},
        {"op": "bend", "radius": 0.1524, "angle": 90.0, "plane": "XY"},
        {"op": "run", "length": 3.0},
        {"op": "end", "point": [4.1524, 3.0, 0.0], "support": "guide"},
    ]
    res = build_pipe_run(section="DN100_SCH40", material="P265GH", steps=steps)
    assert res["status"] == "success"
    assert len(res["created_element_ids"]) >= 2
    assert model_file.is_file()

    info = inspect_model()
    assert len(info["nodes"]) >= 3
    assert len(info["elements"]) >= 2
    assert len(info["supports"]) == 2


def test_a_built_pipe_run_is_saved_as_its_steps_through_a_reload_and_a_patch(tmp_path: Path):
    model_file = tmp_path / "vectors" / "model.py"
    init_session(project_name="Vectors", file_path=str(model_file), load_existing=False)
    build_pipe_run(
        section="DN100_SCH40",
        material="P265GH",
        steps=[
            {"op": "start", "point": [0.0, 0.0, 0.0], "support": "anchor"},
            {"op": "run", "length": 5.0},
            {"op": "bend", "radius": 0.1524, "angle": 90.0, "plane": "XY"},
            {"op": "run", "length": 3.0},
        ],
    )
    block = "\n".join(
        [
            "with model.pipe(section='DN100_SCH40', material='P265GH') as builder:",
            "    builder.start([0.0, 0.0, 0.0], support='anchor')",
            "    builder.run(5.0)",
            "    builder.bend(radius=0.1524, angle=90.0, plane='XY')",
            "    builder.run(3.0)",
        ]
    )
    assert block in model_file.read_text(encoding="utf-8")

    assert init_session(file_path=str(model_file))["status"] == "loaded"
    apply_model_patch(
        [
            {"op": "add_node", "local_id": "extra", "coords": [9.0, 0.0, 0.0]},
            {"op": "add_support", "node": "extra", "type": "anchor"},
        ]
    )

    text = model_file.read_text(encoding="utf-8")
    assert block in text
    assert "model.add_node([9.0, 0.0, 0.0])" in text
    assert same_model(run_model_script(model_file)["model"], get_active_model())


def test_configure_load_case_and_forces(tmp_path: Path):
    model_file = tmp_path / "lc" / "model.py"
    init_session(project_name="Load Case Test", file_path=str(model_file), load_existing=False)

    build_pipe_run(
        section="DN100_SCH40",
        material="P265GH",
        steps=[
            {"op": "start", "point": [0.0, 0.0, 0.0], "support": "anchor"},
            {"op": "run", "length": 2.0},
            {"op": "end"},
        ],
    )

    lc_res = configure_load_case(
        name="Operating_Hot",
        internal_pressure_mpa=3.5,
        temperature_celsius=180.0,
        gravity=True,
        nodal_forces=[{"node": "N0", "force": [0.0, 1000.0, 0.0]}],
    )
    assert lc_res["status"] == "success"
    assert lc_res["internal_pressure_mpa"] == 3.5

    info = inspect_model()
    assert "Operating_Hot" in info["load_cases"]
    assert info["load_cases"]["Operating_Hot"]["temperature_celsius"] == 180.0
    assert info["load_cases"]["Operating_Hot"]["nodal_forces_count"] == 1


def test_apply_model_patch_transaction(tmp_path: Path):
    model_file = tmp_path / "patch" / "model.py"
    init_session(project_name="Patch Test", file_path=str(model_file), load_existing=False)

    patch_ops = [
        {"op": "add_node", "local_id": "n_extra", "coords": [10.0, 0.0, 0.0]},
        {"op": "add_support", "node": "n_extra", "type": "anchor"},
    ]
    patch_res = apply_model_patch(patch_ops)
    assert patch_res["status"] == "success"
    assert "n_extra" in patch_res["created_node_ids"]
    assert patch_res["support_count"] == 1

    canonical_id = patch_res["created_node_ids"]["n_extra"]
    info = inspect_model()
    assert canonical_id in info["nodes"]
    assert same_model(run_model_script(model_file)["model"], get_active_model())


def test_export_python_script(tmp_path: Path):
    model_file = tmp_path / "session" / "model.py"
    script_file = tmp_path / "line" / "model.py"  # the folder doesn't exist yet
    init_session(project_name="Export Test's '''quotes'''", file_path=str(model_file), load_existing=False)

    build_pipe_run(
        section="DN100_SCH40",
        material="P265GH",
        steps=[
            {"op": "start", "point": [0.0, 0.0, 0.0], "support": "anchor"},
            {"op": "run", "length": 1.5},
            {"op": "end"},
        ],
    )

    configure_load_case(name="Operating", internal_pressure_mpa=1.5, temperature_celsius=180.0)

    res = export_python_script(str(script_file))
    assert res["status"] == "success"
    assert script_file.is_file()
    content = script_file.read_text(encoding="utf-8")
    assert "TubaModel" in content
    assert "DN100_SCH40" in content

    exported = run_model_script(script_file)["model"]  # must load as a project model.py
    assert same_model(exported, get_active_model())  # the whole model, not just counts

    deck = script_file.parent / "code_aster" / "Operating"
    assert res["code_aster_inputs"]["Operating"]["comm"] == str(deck / "study.comm")
    assert "MECA_STATIQUE" in (deck / "study.comm").read_text(encoding="utf-8")  # the simulation, not an empty file
    assert (deck / "study.mail").is_file() and (deck / "study.export").is_file()


LINE = [
    {"op": "start", "point": [0.0, 0.0, 0.0], "support": "anchor"},
    {"op": "run", "length": 2.0},
    {"op": "end", "support": "anchor"},
]


def test_a_model_py_session_keeps_a_running_studio_live(tmp_path: Path):
    from tuba.visualization.preview.server import ProjectStudioServer

    script = tmp_path / "line" / "model.py"
    init_session(project_name="Live Line", file_path=str(script), load_existing=False)
    studio = ProjectStudioServer(script.parent, tmp_path / "studio", port=0, poll_interval_s=0.05, debounce_s=0.05)
    studio.start()
    try:
        build_pipe_run(section="DN100_SCH40", material="P265GH", steps=LINE)

        deadline = time.time() + 10
        while len(studio.model.elements) != len(get_active_model().elements) and time.time() < deadline:
            time.sleep(0.05)
        assert len(studio.model.elements) == len(get_active_model().elements) > 0
    finally:
        studio.stop()


def test_a_model_py_session_refuses_a_hand_written_script(tmp_path: Path):
    script = tmp_path / "model.py"
    hand_written = 'from tuba import Model\n\nmodel = Model("Hand written")\n'
    script.write_text(hand_written, encoding="utf-8")

    with pytest.raises(ValueError, match="generated"):
        init_session(file_path=str(script))
    assert script.read_text(encoding="utf-8") == hand_written


def test_a_session_takes_over_a_model_py_generated_before_tuba_project_script(tmp_path: Path):
    script = tmp_path / "model.py"
    snapshot = json.dumps(TubaModel(project_name="Old session").to_dict())
    script.write_text(  # the shape the server's JSON-snapshot generator wrote before Plan 2
        '"""Tuba v4 procedural pipeline script generated by Tuba MCP."""\n\nimport json\n\n'
        "from tuba.model import TubaModel\n\n"
        f"model = TubaModel.from_dict(json.loads(r'''{snapshot}'''))\n",
        encoding="utf-8",
    )

    assert init_session(file_path=str(script))["status"] == "loaded"
    add_pipe_section(name="DN50", OD=0.0603, WT=0.00391)
    assert same_model(run_model_script(script)["model"], get_active_model())


def test_a_model_py_session_stops_rather_than_overwrite_edits_made_elsewhere(tmp_path: Path):
    script = tmp_path / "model.py"
    init_session(project_name="Shared", file_path=str(script), load_existing=False)
    edited = script.read_text(encoding="utf-8") + "\n# edited in the studio\n"
    script.write_text(edited, encoding="utf-8")

    with pytest.raises(RuntimeError, match="init_session"):
        build_pipe_run(section="DN100_SCH40", material="P265GH", steps=LINE)
    assert script.read_text(encoding="utf-8") == edited

    assert init_session(file_path=str(script))["status"] == "loaded"  # continue from the edited file
    build_pipe_run(section="DN100_SCH40", material="P265GH", steps=LINE)
    assert len(run_model_script(script)["model"].elements) == len(get_active_model().elements) > 0


def test_a_failed_reload_leaves_the_edited_script_alone(tmp_path: Path):
    script = tmp_path / "model.py"
    init_session(project_name="Reload", file_path=str(script), load_existing=False)
    build_pipe_run(section="DN100_SCH40", material="P265GH", steps=LINE)
    broken = script.read_text(encoding="utf-8") + "\nundefined_name\n"
    script.write_text(broken, encoding="utf-8")

    with pytest.raises(RuntimeError, match="init_session"):
        add_pipe_section(name="DN50", OD=0.0603, WT=0.00391)
    with pytest.raises(NameError):
        init_session(file_path=str(script))
    with pytest.raises(RuntimeError, match="init_session"):
        add_pipe_section(name="DN50", OD=0.0603, WT=0.00391)
    assert script.read_text(encoding="utf-8") == broken


def test_a_refused_save_leaves_the_session_model_unchanged(tmp_path: Path):
    script = tmp_path / "model.py"
    init_session(project_name="Refused", file_path=str(script), load_existing=False)
    script.write_text(script.read_text(encoding="utf-8") + "\n# edited in the studio\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="init_session"):
        build_pipe_run(section="DN100_SCH40", material="P265GH", steps=LINE)
    assert inspect_model()["elements"] == []


def test_a_save_is_refused_when_another_edit_landed_while_its_change_ran(tmp_path: Path):
    script = tmp_path / "model.py"
    init_session(project_name="Overlap", file_path=str(script), load_existing=False)

    def change(model):
        add_pipe_section(name="DN50", OD=0.0603, WT=0.00391)  # another edit lands while this change runs
        model.add_pipe_section("DN65", OD=0.0761, WT=0.0036)

    with pytest.raises(RuntimeError, match="init_session"):
        mcp_server._edit(change)
    sections = inspect_model()["sections"]
    assert "DN50" in sections and "DN65" not in sections
    assert same_model(run_model_script(script)["model"], get_active_model())


def test_a_deleted_model_py_is_written_again_by_the_next_change(tmp_path: Path):
    script = tmp_path / "model.py"
    init_session(project_name="Deleted", file_path=str(script), load_existing=False)
    build_pipe_run(section="DN100_SCH40", material="P265GH", steps=LINE)
    script.unlink()  # no edit to lose, and the session's model is now the only copy

    add_pipe_section(name="DN50", OD=0.0603, WT=0.00391)
    assert script.is_file()
    assert same_model(run_model_script(script)["model"], get_active_model())
    assert get_active_model().elements and "DN50" in get_active_model().sections  # nothing was lost


def test_a_failing_build_step_leaves_the_session_model_and_script_unchanged(tmp_path: Path):
    script = tmp_path / "model.py"
    init_session(project_name="Failing step", file_path=str(script), load_existing=False)
    before = script.read_text(encoding="utf-8")

    with pytest.raises(AttributeError):
        build_pipe_run(section="DN100_SCH40", material="P265GH", steps=[*LINE[:2], {"op": "no_such_step"}])
    assert inspect_model()["nodes"] == {}
    assert script.read_text(encoding="utf-8") == before


def test_export_refuses_to_overwrite_an_authored_script(tmp_path: Path):
    init_session(project_name="Export guard", file_path=str(tmp_path / "session" / "model.py"), load_existing=False)
    authored = tmp_path / "other" / "model.py"
    authored.parent.mkdir()
    text = 'from tuba import Model\n\nmodel = Model("Hand written")\n'
    authored.write_text(text, encoding="utf-8")

    with pytest.raises(ValueError, match="authored"):
        export_python_script(str(authored))
    assert authored.read_text(encoding="utf-8") == text


def test_a_session_saves_to_a_model_py_only(tmp_path: Path):
    model_json = tmp_path / "model.json"

    with pytest.raises(ValueError, match="model.py"):
        init_session(file_path=str(model_json), load_existing=False)
    assert not model_json.exists()
    with pytest.raises(ValueError, match="model.py"):
        init_session(file_path=str(tmp_path / "loop.py"), load_existing=False)
    assert not (tmp_path / "loop.py").exists()


def test_tools_need_a_session(monkeypatch):
    monkeypatch.setattr(mcp_server, "_ACTIVE_MODEL", None)
    monkeypatch.setattr(mcp_server, "_ACTIVE_PATH", None)

    with pytest.raises(RuntimeError, match="init_session"):
        inspect_model()

