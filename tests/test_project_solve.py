"""Project solve: reuse, force, staging and promotion through the solver port (spec decisions 11-13, 18, 20)."""

import json
import os
import shutil
from pathlib import Path

import pytest

from tests.project_replay import ReplaySolver
from tuba.project import evidence, load_project
from tuba.project.claim import SolveBusy, claim_solve, solve_claimed
from tuba.project.solve import solve_project
from tuba.solver.code_aster_runtime import load_code_aster_execution_attestation

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
RACK = EXAMPLES / "support-rack-review"
PROFILE = EXAMPLES / "profile-orientation-review"
TEE = EXAMPLES / "pipe-tee-volume-review"
VOLUME_MODEL = """from tuba import Model

model = Model("ProjectVolume")
model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0)
model.add_pipe_section("Pipe", OD=0.1, WT=0.01)
n0 = model.add_node([0.0, 0.0, 0.0])
n1 = model.add_node([0.2, 0.0, 0.0])
model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="Pipe", material="Steel")
model.add_support(n0, type="anchor")
model.define_load_case("Pressure", gravity=False, pressure=1.0e6)
"""
VOLUME_STUDY = """LOAD_CASES = ("Pressure",)
SOLVER_OPTIONS = {}
VOLUME_EXPORT = {"element_ids": ("pipe_0",), "max_element_size": 0.005}
"""


def _copy(tmp_path: Path, source: Path, *, evidence: bool = True):
    """A project copied into *tmp_path*, with or without its committed evidence."""
    root = tmp_path / source.name
    shutil.copytree(source, root, ignore=None if evidence else shutil.ignore_patterns("evidence"))
    return load_project(root)


def _files(folder: Path) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in folder.iterdir() if path.is_file()}


class _Exported(Exception):
    pass


class _RefuseToSolve:
    def solve_exported_study(self, model, study):
        raise _Exported(study)


def test_a_solve_lands_the_evidence_a_real_run_attested(tmp_path):
    project = _copy(tmp_path, RACK, evidence=False)
    solver = ReplaySolver(RACK / "evidence")

    outcome = solve_project(project, solver=solver)

    assert (outcome.solved, outcome.reused, outcome.unverified) == (("Operating",), (), ())
    assert solver.solved == ["Operating"]
    landed = project.root / "evidence" / "Operating"
    committed = RACK / "evidence" / "Operating"
    attested = load_code_aster_execution_attestation(committed)["artifacts"]
    assert set(_files(landed)) == {*attested, "study_execution.json"}
    assert all((landed / name).read_bytes() == (committed / name).read_bytes() for name in attested)
    run = outcome.runs["Operating"]
    assert run.result_state.metadata["result_trust"] == "verified"
    assert Path(run.study.work_dir).resolve() == landed.resolve()
    assert not (project.root / ".tuba" / "staging").exists()
    assert not solve_claimed(project.root)


def test_matching_evidence_is_reused_and_force_solves_again(tmp_path):
    project = _copy(tmp_path, RACK)
    solver = ReplaySolver(RACK / "evidence")

    reused = solve_project(project, solver=solver)
    assert (reused.solved, reused.reused, solver.solved) == ((), ("Operating",), [])
    assert reused.runs["Operating"].result_state.metadata["result_trust"] == "verified"

    forced = solve_project(project, solver=solver, force=True)
    assert (forced.solved, forced.reused, solver.solved) == (("Operating",), (), ["Operating"])


@pytest.mark.parametrize(
    ("script", "old", "new"),
    [
        ("model.py", "(-2.0, -1.0, 3.0)", "(-2.5, -1.0, 3.0)"),
        ("study.py", "SOLVER_OPTIONS: dict = {}", 'SOLVER_OPTIONS: dict = {"line_segments": 4}'),
    ],
)
def test_a_changed_model_or_study_solves_again_and_a_failed_solve_writes_nothing(tmp_path, script, old, new):
    project = _copy(tmp_path, RACK)
    path = project.root / script
    path.write_text(path.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")
    before = _files(project.root / "evidence" / "Operating")

    # No committed run attests the changed input, so the replay refuses: the solve was attempted, and it failed.
    with pytest.raises(LookupError, match="No committed evidence"):
        solve_project(project, solver=ReplaySolver(RACK / "evidence"))

    assert _files(project.root / "evidence" / "Operating") == before
    assert not (project.root / ".tuba" / "staging").exists()
    assert not solve_claimed(project.root)


def test_every_operation_of_a_study_lands(tmp_path):
    project = _copy(tmp_path, PROFILE, evidence=False)

    outcome = solve_project(project, solver=ReplaySolver(PROFILE / "evidence"))

    assert outcome.solved == ("global", "local")
    for case in ("global", "local"):
        assert load_code_aster_execution_attestation(project.root / "evidence" / case) is not None
        assert outcome.runs[case].result_state.metadata["result_trust"] == "verified"


def test_an_unverified_run_is_written_and_reported(tmp_path):
    project = _copy(tmp_path, RACK, evidence=False)

    outcome = solve_project(project, solver=ReplaySolver(RACK / "evidence", execution_method="docker"))

    assert outcome.unverified == ("Operating",)
    written = project.root / "evidence" / "Operating" / "study_execution.json"
    assert json.loads(written.read_text(encoding="utf-8"))["execution_method"] == "docker"


def test_an_unverified_run_is_solved_again_rather_than_reused(tmp_path):
    project = _copy(tmp_path, RACK, evidence=False)
    solve_project(project, solver=ReplaySolver(RACK / "evidence", execution_method="docker"))

    verified = ReplaySolver(RACK / "evidence")
    outcome = solve_project(project, solver=verified)

    assert (outcome.solved, outcome.reused, outcome.unverified) == (("Operating",), (), ())
    assert verified.solved == ["Operating"]


def test_a_project_another_solve_claims_is_busy(tmp_path):
    project = _copy(tmp_path, RACK, evidence=False)

    with claim_solve(project.root):
        with pytest.raises(SolveBusy):
            solve_project(project, solver=ReplaySolver(RACK / "evidence"))

    assert not (project.root / "evidence").exists()


def test_a_study_without_operations_has_nothing_to_solve(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    shutil.copy2(RACK / "model.py", root / "model.py")
    (root / "study.py").write_text("LOAD_CASES = ()\n", encoding="utf-8")

    with pytest.raises(ValueError, match="no study operations"):
        solve_project(load_project(root))


def test_a_study_naming_one_operation_twice_is_refused_before_the_model_runs(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "model.py").write_text('raise AssertionError("model.py must not run")\n', encoding="utf-8")
    (root / "study.py").write_text('LOAD_CASES = ("Operating", "operating")\n', encoding="utf-8")

    # Both names would share one evidence folder on Windows: nothing runs, is claimed or is written.
    with pytest.raises(ValueError, match="twice"):
        solve_project(load_project(root), solver=_RefuseToSolve())

    assert sorted(path.name for path in root.iterdir()) == ["model.py", "study.py"]


def test_a_volume_study_exports_its_solids_without_the_tensor_stress_table(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "model.py").write_text(VOLUME_MODEL, encoding="utf-8")
    (root / "study.py").write_text(VOLUME_STUDY, encoding="utf-8")

    with pytest.raises(_Exported) as exported:
        solve_project(load_project(root), solver=_RefuseToSolve())

    study = exported.value.args[0]
    assert study.metadata["volume_analysis"]
    assert study.metadata["compiler_inputs"]["export_tensor_stress"] is False
    assert not (root / "evidence").exists()
    assert not (root / ".tuba" / "staging").exists()


def test_a_volume_project_reuses_its_committed_evidence_without_exporting(tmp_path):
    project = _copy(tmp_path, TEE)

    outcome = solve_project(project, solver=_RefuseToSolve())

    assert (outcome.solved, outcome.reused, outcome.unverified) == ((), ("Operating",), ())
    assert outcome.runs["Operating"].study.metadata["volume_analysis"]


def test_an_interrupted_promotion_leaves_the_operation_unsolved_and_the_next_solve_repeats_it(tmp_path, monkeypatch):
    project = _copy(tmp_path, RACK)
    solver = ReplaySolver(RACK / "evidence")
    real_replace = os.replace
    moves = []

    def refuse_the_first_move(source, destination):
        moves.append(destination)
        if len(moves) == 1:
            raise PermissionError("study.rmed is open in another program")
        real_replace(source, destination)

    monkeypatch.setattr(evidence.os, "replace", refuse_the_first_move)
    with pytest.raises(PermissionError):
        solve_project(project, solver=solver, force=True)
    monkeypatch.setattr(evidence.os, "replace", real_replace)

    assert not (project.root / ".tuba" / "staging").exists()
    assert load_code_aster_execution_attestation(project.root / "evidence" / "Operating") is None
    assert not solve_claimed(project.root)
    assert solve_project(project, solver=solver).solved == ("Operating",)


def test_a_failing_study_check_keeps_the_solve_out_of_the_evidence(tmp_path):
    project = _copy(tmp_path, RACK, evidence=False)
    study = project.root / "study.py"
    study.write_text(
        study.read_text(encoding="utf-8") + '\n\ndef check(solved):\n    raise RuntimeError(f"rejected {sorted(solved.runs)}")\n',
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match=r"rejected \['Operating'\]"):
        solve_project(project, solver=ReplaySolver(RACK / "evidence"))

    assert not (project.root / "evidence").exists()
    assert not (project.root / ".tuba" / "staging").exists()
    assert not solve_claimed(project.root)


def test_the_study_check_sees_the_model_its_script_globals_and_every_run(tmp_path):
    project = _copy(tmp_path, RACK)
    study = project.root / "study.py"
    study.write_text(
        study.read_text(encoding="utf-8")
        + "\n\ndef check(solved):\n"
        + "    import json\n"
        + "    record = {'model': solved.model.project_name, 'script': Path(solved.namespace['__file__']).name, 'runs': sorted(solved.runs)}\n"
        + "    (Path(__file__).parent / 'checked.json').write_text(json.dumps(record), encoding='utf-8')\n",
        encoding="utf-8",
    )

    solve_project(project, solver=ReplaySolver(RACK / "evidence"))

    assert json.loads((project.root / "checked.json").read_text(encoding="utf-8")) == {
        "model": "SupportRackReview",
        "script": "model.py",
        "runs": ["Operating"],
    }
