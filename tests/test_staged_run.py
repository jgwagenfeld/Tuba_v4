"""Staging an Analysis run's Evidence into a review bundle (spec decisions 14 and 22)."""

import shutil
from pathlib import Path

import pytest

from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts
from tuba.analysis.staged_run import operation_folder_name, stage_runs
from tuba.project import load_project

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def _run(tmp_path, example, operation):
    """One committed Evidence folder, copied out of the repository and imported."""
    source = EXAMPLES / example / "evidence" / operation
    work_dir = tmp_path / "evidence" / operation
    shutil.copytree(source, work_dir)
    model = load_project(EXAMPLES / example).run_model()["model"]
    return import_code_aster_artifacts(model=model, work_dir=work_dir)


def test_a_run_lands_in_the_folder_its_operation_names(tmp_path):
    run = _run(tmp_path, "support-rack-review", "Operating")
    bundle = tmp_path / "bundle"

    staged = stage_runs({"Operating": run}, bundle)

    folder = bundle / "artifacts" / "Operating"
    attested = set(run.result_state.metadata["solve_attestation"]["artifacts"])
    assert {path.name for path in folder.iterdir()} == attested | {"study_execution.json"}
    assert staged["Operating"].study.work_dir is None
    assert staged["Operating"].result_state.files["execution"] == "artifacts/Operating/study_execution.json"
    # Unattested files stay behind: the solver's own listing and its logs.
    assert not (folder / "study.resu").exists()


def test_every_operation_gets_its_own_folder(tmp_path):
    runs = {case: _run(tmp_path, "profile-orientation-review", case) for case in ("global", "local")}
    bundle = tmp_path / "bundle"

    staged = stage_runs(runs, bundle)

    assert sorted(path.name for path in (bundle / "artifacts").iterdir()) == ["global", "local"]
    for case in ("global", "local"):
        assert staged[case].result_state.files["mess"] == f"artifacts/{case}/study.mess"


def test_a_key_that_is_not_the_runs_operation_is_refused(tmp_path):
    run = _run(tmp_path, "support-rack-review", "Operating")

    with pytest.raises(ValueError, match="Operating"):
        stage_runs({"Hot": run}, tmp_path / "bundle")


@pytest.mark.parametrize("name", ["", "a/b", "Hot:Cold", "CON", "Hot ", "x" * 256])
def test_an_operation_that_cannot_name_a_folder_is_refused(name):
    with pytest.raises(ValueError, match="cannot name"):
        operation_folder_name(name)
