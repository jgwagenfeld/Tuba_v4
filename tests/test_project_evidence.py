"""Evidence folders, and how a solve lands in them (spec decisions 10 and 12)."""

import os
import shutil
from pathlib import Path

import pytest

from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts
from tuba.project import evidence, load_project
from tuba.project.evidence import evidence_dir, promote_evidence, study_artifact_dir
from tuba.solver.code_aster_runtime import load_code_aster_execution_attestation

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
RACK = EXAMPLES / "support-rack-review" / "evidence" / "Operating"
PROFILE = EXAMPLES / "profile-orientation-review" / "evidence"


def _files(folder: Path) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in folder.iterdir() if path.is_file()}


def test_each_operation_has_one_evidence_folder_named_after_it(tmp_path):
    assert evidence_dir(tmp_path, "Operating") == tmp_path / "evidence" / "Operating"
    assert evidence_dir(tmp_path, "Load case 1") == tmp_path / "evidence" / "Load case 1"
    assert evidence_dir(tmp_path, "x" * 255) == tmp_path / "evidence" / ("x" * 255)
    for name in (
        "", ".", "..", "a/b", "a\\b", "Hot:Cold", "Hot?", "CON", "nul.txt", "Hot ", "Hot.", "tab\there",
        # The rest of Windows' device names, and a name over Linux's limit of 255 bytes (not characters).
        "COM0", "lpt0", "COM¹", "LPT³.log", "CONIN$", "conout$", "é" * 128,
    ):
        with pytest.raises(ValueError, match="cannot name an evidence folder"):
            evidence_dir(tmp_path, name)


def test_a_study_imports_its_operation_folder_or_the_evidence_folder_holding_several(tmp_path):
    assert study_artifact_dir(tmp_path, ("Operating",)) == tmp_path / "evidence" / "Operating"
    assert study_artifact_dir(tmp_path, ("global", "local")) == tmp_path / "evidence"


def test_promotion_keeps_only_attested_files_and_lands_the_attestation_last(tmp_path, monkeypatch):
    staged, target = tmp_path / "staged", tmp_path / "evidence" / "Operating"
    shutil.copytree(RACK, staged)
    target.mkdir(parents=True)
    shutil.copy2(RACK / "study_execution.json", target / "study_execution.json")
    (target / "study_sigm.csv").write_text("left by an older solve", encoding="utf-8")
    attested = set(load_code_aster_execution_attestation(RACK)["artifacts"])
    moved = []
    real_replace = os.replace

    def replace(source, destination):
        moved.append(Path(destination).name)
        real_replace(source, destination)

    monkeypatch.setattr(evidence.os, "replace", replace)

    promote_evidence({staged: target})

    assert moved[-1] == "study_execution.json"
    assert sorted(moved[:-1]) == sorted(attested)
    # The committed folder's unattested study.resu stays behind, and the stale table is gone.
    assert set(_files(target)) == attested | {"study_execution.json"}
    assert all((target / name).read_bytes() == (RACK / name).read_bytes() for name in attested)
    model = load_project(EXAMPLES / "support-rack-review").run_model()["model"]
    run = import_code_aster_artifacts(model=model, work_dir=target)
    assert run.result_state.metadata["result_trust"] == "verified"


def test_one_damaged_operation_promotes_none(tmp_path):
    moves = {}
    for case in ("global", "local"):
        staged, target = tmp_path / "staged" / case, tmp_path / "evidence" / case
        shutil.copytree(PROFILE / case, staged)
        shutil.copytree(PROFILE / case, target)
        moves[staged] = target
    (tmp_path / "staged" / "local" / "study.mess").write_text("damaged", encoding="utf-8")
    before = {target: _files(target) for target in moves.values()}

    with pytest.raises(ValueError, match="does not match"):
        promote_evidence(moves)

    assert {target: _files(target) for target in moves.values()} == before
