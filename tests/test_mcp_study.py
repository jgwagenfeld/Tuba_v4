"""The MCP session keeps a managed study.py beside model.py for the studio."""

from __future__ import annotations

from pathlib import Path

import pytest

from tuba.mcp.server import (
    configure_load_case,
    init_session,
)
from tuba.project import load_project
from tuba.project.study import STUDY_MARKER


def test_init_scaffolds_a_managed_study_and_reports_the_studio(tmp_path: Path):
    model_file = tmp_path / "demo" / "model.py"
    res = init_session(project_name="Study Demo", file_path=str(model_file), load_existing=False)

    study_file = model_file.parent / "study.py"
    assert study_file.is_file()
    text = study_file.read_text(encoding="utf-8")
    assert STUDY_MARKER in text
    assert "LOAD_CASES = ()" in text

    assert res["study"] == {"exists": True, "managed": True, "load_cases": [], "missing_cases": []}
    assert res["studio"]["cmd"] == f"python -m tuba.cli_studio {model_file.parent}"
    assert "bundle=build" in res["studio"]["viewer_url"]

    assert load_project(model_file.parent).load_study() is not None


def test_configure_load_case_syncs_managed_study_cases(tmp_path: Path):
    model_file = tmp_path / "demo" / "model.py"
    init_session(project_name="Study Demo", file_path=str(model_file), load_existing=False)

    res = configure_load_case(name="Operating", internal_pressure_mpa=1.5, temperature_celsius=180.0)
    assert res["study"]["load_cases"] == ["Operating"]
    assert "LOAD_CASES = ('Operating',)" in (model_file.parent / "study.py").read_text(encoding="utf-8")

    configure_load_case(name="Hydrotest", internal_pressure_mpa=2.0, temperature_celsius=20.0)
    text = (model_file.parent / "study.py").read_text(encoding="utf-8")
    assert "LOAD_CASES = ('Operating', 'Hydrotest')" in text


def test_sync_preserves_hand_edits_to_a_managed_study(tmp_path: Path):
    model_file = tmp_path / "demo" / "model.py"
    init_session(project_name="Study Demo", file_path=str(model_file), load_existing=False)

    study_file = model_file.parent / "study.py"
    text = study_file.read_text(encoding="utf-8")
    study_file.write_text(text.replace('title="Study Demo review",', 'title="Study Demo review",\n        include_load_paths=True,'), encoding="utf-8")

    configure_load_case(name="Operating", internal_pressure_mpa=1.5, temperature_celsius=180.0)
    synced = study_file.read_text(encoding="utf-8")
    assert "include_load_paths=True," in synced  # the hand edit survived
    assert "LOAD_CASES = ('Operating',)" in synced


def test_a_user_owned_study_is_reported_never_rewritten(tmp_path: Path):
    model_file = tmp_path / "demo" / "model.py"
    init_session(project_name="Study Demo", file_path=str(model_file), load_existing=False)

    study_file = model_file.parent / "study.py"
    owned = 'LOAD_CASES = ("Whatever",)\n'
    study_file.write_text(owned, encoding="utf-8")
    assert STUDY_MARKER not in owned

    res = configure_load_case(name="Operating", internal_pressure_mpa=1.5, temperature_celsius=180.0)
    assert study_file.read_text(encoding="utf-8") == owned
    assert res["study"]["managed"] is False
    assert res["study"]["missing_cases"] == ["Operating"]


def test_loading_an_old_model_only_project_heals_the_missing_study(tmp_path: Path):
    model_file = tmp_path / "demo" / "model.py"
    init_session(project_name="Study Demo", file_path=str(model_file), load_existing=False)
    configure_load_case(name="Operating", internal_pressure_mpa=1.5, temperature_celsius=180.0)
    (model_file.parent / "study.py").unlink()  # a project from before study scaffolding

    res = init_session(file_path=str(model_file))
    assert res["status"] == "loaded"
    assert res["study"]["load_cases"] == ["Operating"]
    assert "LOAD_CASES = ('Operating',)" in (model_file.parent / "study.py").read_text(encoding="utf-8")


def test_init_loads_authored_model_script(tmp_path: Path):
    model_file = tmp_path / "authored_demo" / "model.py"
    model_file.parent.mkdir(parents=True, exist_ok=True)
    authored_code = (
        'from tuba import Model\n\n'
        'model = Model("Authored Bridge", standard="ASME B31.3")\n'
        'model.add_material("Steel", E=2.1e11, nu=0.3)\n'
        'model.add_node([0.0, 0.0, 0.0])\n'
        'model.define_load_case("Operating", pressure=1e6, temperature=120.0)\n'
    )
    model_file.write_text(authored_code, encoding="utf-8")

    # When load_existing=False, it refuses to overwrite the authored file
    with pytest.raises(ValueError, match="holds hand-written code"):
        init_session(project_name="New Proj", file_path=str(model_file), load_existing=False)

    # When load_existing=True, it loads it cleanly for inspection and solving
    res = init_session(file_path=str(model_file), load_existing=True)
    assert res["status"] == "loaded"
    assert res["authored"] is True
    assert res["project_name"] == "Authored Bridge"
    assert res["nodes_count"] == 1
    assert model_file.read_text(encoding="utf-8") == authored_code

