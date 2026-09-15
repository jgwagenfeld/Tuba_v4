"""A study's settings are checked once, when the study loads (spec decisions 10, 19 and 23)."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from tuba.project import load_project
from tuba.project.study import StudySettings, study_settings

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
VOLUME = {"element_ids": ("pipe_0",), "max_element_size": 0.005}


@pytest.mark.parametrize("script", sorted(EXAMPLES.glob("*/*study.py")), ids=lambda path: f"{path.parent.name}/{path.name}")
def test_every_gallery_study_loads(script):
    study = load_project(script.parent).load_study(script.name)

    assert study_settings(study).operations == tuple(study.LOAD_CASES)


def test_a_missing_study_or_name_takes_its_default():
    assert study_settings(None) == study_settings(SimpleNamespace()) == StudySettings((), {}, None)


def test_the_settings_are_the_study_names():
    beam = SimpleNamespace(LOAD_CASES=["Hot", "Cold"], SOLVER_OPTIONS={"line_segments": 4})
    volume = SimpleNamespace(LOAD_CASES=("Pressure",), SOLVER_OPTIONS={}, VOLUME_EXPORT=VOLUME)

    assert study_settings(beam) == StudySettings(("Hot", "Cold"), {"line_segments": 4}, None)
    assert study_settings(volume) == StudySettings(("Pressure",), {}, VOLUME)


@pytest.mark.parametrize(
    ("names", "error"),
    [
        ({"LOAD_CASES": "Operating"}, "tuple of operation names"),
        ({"LOAD_CASES": ("Operating", 2)}, "tuple of operation names"),
        ({"LOAD_CASES": ("CON",)}, "cannot name an evidence folder"),
        ({"LOAD_CASES": ("Hot", "Hot")}, "twice"),
        ({"LOAD_CASES": ("Hot", "hot")}, "twice"),
        ({"SOLVER_OPTIONS": {"exec_method": "docker"}}, "runs on this machine: exec_method"),
        ({"SOLVER_OPTIONS": {"work_dir": "scratch", "timeout_seconds": 60}}, "runs on this machine: timeout_seconds, work_dir"),
        ({"SOLVER_OPTIONS": {"line_segment": 4}}, "line_segment'"),
        ({"SOLVER_OPTIONS": {"line_segments": 0}}, "line_segments must be a positive integer"),
        ({"VOLUME_EXPORT": {"element_ids": ("pipe_0",)}}, "needs max_element_size"),
        ({"VOLUME_EXPORT": {**VOLUME, "export_tensor_stress": True}}, "cannot set export_tensor_stress"),
        ({"VOLUME_EXPORT": {**VOLUME, "mesh_size": 0.01}}, "cannot set mesh_size"),
        ({"SOLVER_OPTIONS": {"pipe_modelization": "POU_D_T", "load_path": ["Hot", "Cold"]}, "VOLUME_EXPORT": VOLUME}, "load_path"),
    ],
)
def test_a_study_that_cannot_be_solved_as_written_is_refused_when_it_loads(names, error):
    with pytest.raises(ValueError, match=error):
        study_settings(SimpleNamespace(**names))
