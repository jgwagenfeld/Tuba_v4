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


def test_project_load_settings_is_the_one_loader():
    project = load_project(EXAMPLES / "support-rack-review")

    settings = project.load_settings()

    assert settings.operations == ("Operating",)
    assert callable(settings.build_review)
    assert settings.solver().line_segments == 8


def test_a_project_without_a_study_loads_empty_settings(tmp_path):
    (tmp_path / "model.py").write_text("from tuba import Model\nmodel = Model('Empty')\n", encoding="utf-8")
    project = load_project(tmp_path)

    assert project.load_settings() == StudySettings((), {}, None)


def test_settings_carry_the_review_builder_artifact_dir_and_check():
    def build_review(namespace, output, *, artifact_dir=None):
        return Path(output)

    def check(solved):
        return True

    study = SimpleNamespace(
        LOAD_CASES=("Hot",),
        build_review=build_review,
        ARTIFACT_DIR=Path("evidence/Hot"),
        check=check,
    )

    settings = study_settings(study)

    assert settings.build_review is build_review
    assert settings.check is check
    assert settings.artifact_dir == Path("evidence/Hot")
    assert settings.solver().timeout_seconds == 7200


def test_the_settings_are_the_study_names():
    beam = SimpleNamespace(LOAD_CASES=["Hot", "Cold"], SOLVER_OPTIONS={"line_segments": 4, "timeout_seconds": 14400})
    volume = SimpleNamespace(LOAD_CASES=("Pressure",), SOLVER_OPTIONS={}, VOLUME_EXPORT=VOLUME)

    assert study_settings(beam) == StudySettings(("Hot", "Cold"), {"line_segments": 4, "timeout_seconds": 14400}, None)
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
        ({"SOLVER_OPTIONS": {"work_dir": "scratch", "docker_image": "tuba/aster"}}, "runs on this machine: docker_image, work_dir"),
        ({"SOLVER_OPTIONS": {"line_segment": 4}}, "line_segment'"),
        ({"SOLVER_OPTIONS": {"line_segments": 0}}, "line_segments must be a positive integer"),
        ({"VOLUME_EXPORT": {"element_ids": ("pipe_0",)}}, "needs max_element_size"),
        ({"VOLUME_EXPORT": {**VOLUME, "export_tensor_stress": True}}, "cannot set export_tensor_stress"),
        ({"VOLUME_EXPORT": {**VOLUME, "mesh_size": 0.01}}, "cannot set mesh_size"),
        ({"SOLVER_OPTIONS": {"pipe_modelization": "POU_D_T", "load_path": ["Hot", "Cold"]}, "VOLUME_EXPORT": VOLUME}, "load_path"),
        ({"build_review": 3}, "build_review must be callable"),
        ({"check": "no"}, "check must be callable"),
    ],
)
def test_a_study_that_cannot_be_solved_as_written_is_refused_when_it_loads(names, error):
    with pytest.raises(ValueError, match=error):
        study_settings(SimpleNamespace(**names))
