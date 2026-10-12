"""Authored project contracts; these checks do not claim solver qualification."""

import math
from pathlib import Path
import re
import shutil

import pytest

from tuba.process import BoundProcessNetwork
from tuba.project import load_project
from tuba.project.script import is_generated, require_model_script_style


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "examples" / "process_network"


def copy_project(tmp_path):
    """Use only the two authored files, without campaign data or old output."""
    for name in ("model.py", "study.py"):
        shutil.copy2(PROJECT / name, tmp_path / name)
    return load_project(tmp_path)


def test_standalone_authored_studio_project_has_bound_pid_and_no_fluid_loads(tmp_path):
    project = copy_project(tmp_path)
    source = project.model_path.read_text(encoding="utf-8")
    require_model_script_style(source)
    assert not is_generated(source)
    namespace = project.run_model()
    model, process = namespace["model"], namespace["process"]
    model.validate()
    assert isinstance(process, BoundProcessNetwork)
    process.verify_for(model)
    assert namespace["PIPE_SIZE"] == "larger"
    assert namespace["OFFSET_M"] == 1.0
    assert not model.operations and not model.load_cases
    assert len(model.elements) == 9
    assert {element.route_id for element in model.elements} == {"L-101"}
    assert {equipment.tag for equipment in process.network.pid.equipment} == {
        "TK-101", "TK-102", "FCV-101",
    }
    assert {instrument.tag for instrument in process.network.pid.instruments} == {
        "PT-101", "FT-101", "FIC-101",
    }
    assert namespace["__tuba_project_dependencies__"] == (project.model_path,)
    study = project.load_study()
    settings = project.load_settings()
    assert settings.operations == (process.scenario.id,) == ("WaterOperating",)
    assert settings.solver_options == {"pipe_modelization": "TUYAU_3M"}
    assert study.WALL_TEMPERATURE_MODEL == "bulk-fluid-equals-wall-steady"
    assert callable(settings.build_review)


@pytest.mark.parametrize("size, offset, bore", [
    ("small", 1.0, 0.05248),
    ("larger", 2.0, 0.07792),
])
def test_studio_source_edits_remeasure_bore_and_offset_without_changing_pid(tmp_path, size, offset, bore):
    project = copy_project(tmp_path)
    initial = project.run_model()["process"]
    source = project.model_path.read_text(encoding="utf-8")
    source = source.replace('PIPE_SIZE = "larger"', f'PIPE_SIZE = "{size}"')
    source = source.replace("OFFSET_M = 1.0", f"OFFSET_M = {offset}")
    project.model_path.write_text(source, encoding="utf-8")
    namespace = project.run_model()
    process = namespace["process"]
    process.verify_for(namespace["model"])
    pipe_segments = [segment for segment in process.segments if segment.element_id is not None]
    assert all(segment.bore_m == pytest.approx(bore) for segment in pipe_segments)
    assert sum(segment.length_m for segment in pipe_segments) == pytest.approx(
        6.0 + 2.0 * offset + 2.0 * math.pi * 0.3,
    )
    assert process.fingerprint != initial.fingerprint
    assert process.geometry_fingerprint != initial.geometry_fingerprint
    assert process.network.pid == initial.network.pid
    assert process.network.connections == initial.network.connections
    assert process.scenario == initial.scenario
    assert process.requirements == initial.requirements
    assert not namespace["model"].operations


def test_studio_guide_launches_the_shared_project_and_links_its_acceptance_plan():
    guide_path = ROOT / "docs" / "content" / "process-networks.md"
    guide = guide_path.read_text(encoding="utf-8")
    studio_section = guide.split("## Open the authored project in Studio", 1)[1].split(
        "## Run the retained-candidate campaign", 1,
    )[0]
    assert "python -m tuba.cli_studio examples/process_network" in studio_section
    assert "**P&ID**" in studio_section and "**Run hydraulics**" in studio_section
    assert "**Solve**" in studio_section and "**Review**" in studio_section
    assert "**Not evaluated**" in studio_section and "**Run model.py**" in studio_section
    assert 'PIPE_SIZE = "larger"' in studio_section and "OFFSET_M = 1.0" in studio_section
    assert "Code_Aster" in studio_section
    for target in re.findall(r"\]\(([^)]+)\)", studio_section):
        assert (guide_path.parent / target.split("#", 1)[0]).resolve().is_file(), target
    plan = (ROOT / "docs" / "architecture" / "studio-process-integration.md").read_text(encoding="utf-8")
    assert "real pandapipes and Code_Aster" in plan
