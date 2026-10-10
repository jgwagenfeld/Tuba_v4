from dataclasses import replace
from pathlib import Path
import shutil

import pytest

from tests.project_replay import ReplaySolver
from tuba.project import load_project
from tuba.search.artifacts import ArtifactStore
from tuba.search.contracts import Candidate, CheckSpec, LoadedSearch, SearchDefinition, decide
from tuba.search.evaluate import evaluate_candidate
from tuba.search.history import History

RACK = Path(__file__).resolve().parents[1] / "examples/support-rack-review"


def setup(tmp_path, *, evaluator=None):
    root = tmp_path / "project"
    root.mkdir()
    for name in ("model.py", "study.py"):
        shutil.copyfile(RACK / name, root / name)
    for folder in (root / "evidence/Operating", root / ".tuba/staging"):
        folder.mkdir(parents=True)
        (folder / "sentinel").write_text("preserve")
    project = load_project(root)
    namespace = project.run_model()
    specs = (CheckSpec("cold.model", "cold_model", True, (), (), None, None, {}),
             CheckSpec("evidence.Operating", "evidence_verified", True, ("Operating",), (), None, None, {}))
    loaded = LoadedSearch(project, namespace, project.load_settings(),
                          SearchDefinition({"x": (1,)}, ("pipe_length_m",), 1, 2), specs,
                          lambda p: project.run_model()["model"], evaluator)
    store = ArtifactStore(tmp_path / "run")
    history = History.create(store.root / "history.sqlite3", {"schema": "tuba.search.history.v1", "run_id": "R"})
    candidate = Candidate("C", (), {}, "Test committed real evidence")
    history.record_candidate(candidate)
    return candidate, namespace["model"], loaded, store, history


def snapshot(root):
    return {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_native_replay_keeps_project_and_permanent_evidence(tmp_path):
    c, model, loaded, store, h = setup(tmp_path)
    before = snapshot(loaded.project.root)
    with h:
        result = evaluate_candidate(c, model, loaded, archive=store, history=h, solver=ReplaySolver(RACK / "evidence"))
        assert result.status == "complete"
        assert result.completed_operations == ("Operating",)
        assert decide(result, loaded.check_specs, loaded.settings.operations).outcome == "feasible_retained"
        inventory = store.verify_inventory(result.evidence_manifest_ref)
        assert any(f["path"].endswith("study_execution.json") for f in inventory["files"])
        assert h.events()[-1]["kind"] == "evaluation.completed"
    assert snapshot(loaded.project.root) == before


def test_cold_validation_rejects_without_solver(tmp_path):
    c, model, loaded, store, h = setup(tmp_path)
    next(iter(model.materials.values())).E = -1
    class Refuse:
        def solve_exported_study(self, *args):
            pytest.fail("Cold-invalid model must not reach solver")
    with h:
        result = evaluate_candidate(c, model, loaded, archive=store, history=h, solver=Refuse())
        assert decide(result, loaded.check_specs, loaded.settings.operations).outcome == "rejected_constraint"
        assert result.completed_operations == ()
        store.verify_inventory(result.evidence_manifest_ref)


def test_second_operation_failure_retains_first_and_partial_output(tmp_path):
    c, model, loaded, store, h = setup(tmp_path)
    loaded = replace(loaded, settings=replace(loaded.settings, operations=("Operating", "Other")))
    model.define_load_case("Other", gravity=False)
    replay = ReplaySolver(RACK / "evidence")
    class FailSecond:
        def solve_exported_study(self, m, study):
            if study.load_case == "Other":
                (Path(study.work_dir) / "failure.txt").write_text("solver diagnostic")
                raise RuntimeError("second operation failed")
            return replay.solve_exported_study(m, study)
    with h:
        result = evaluate_candidate(c, model, loaded, archive=store, history=h, solver=FailSecond())
        assert result.status == "failed"
        assert result.completed_operations == ("Operating",)
        assert decide(result, loaded.check_specs, loaded.settings.operations).outcome == "evaluation_failed"
        paths = [entry["path"] for entry in store.verify_inventory(result.evidence_manifest_ref)["files"]]
        assert any("Operating/study_execution.json" in p for p in paths)
        assert any("Other/failure.txt" in p for p in paths)


def test_checker_exception_happens_after_solver_inventory_is_sealed(tmp_path):
    def checker(context):
        inventories = list((tmp_path / "run/attempts").glob("*/inventory.json"))
        assert len(inventories) == 1
        raise ValueError("authored checker failed")
    c, model, loaded, store, h = setup(tmp_path, evaluator=checker)
    with h:
        result = evaluate_candidate(c, model, loaded, archive=store, history=h, solver=ReplaySolver(RACK / "evidence"))
        assert result.error_kind == "checker:ValueError"
        assert store.verify_inventory(result.evidence_manifest_ref)["status"] == "complete"
        assert result.completed_operations == ("Operating",)


@pytest.mark.parametrize("error", [KeyboardInterrupt(), RuntimeError("Code_Aster runtime unavailable"), ValueError("import failed")])
def test_failure_and_cancellation_preserve_exports(tmp_path, error):
    c, model, loaded, store, h = setup(tmp_path)
    class Fail:
        def solve_exported_study(self, m, study):
            raise error
    with h:
        if isinstance(error, KeyboardInterrupt):
            with pytest.raises(KeyboardInterrupt):
                evaluate_candidate(c, model, loaded, archive=store, history=h, solver=Fail())
            record = h.events()[-1]["payload"]
            assert record["status"] == "interrupted"
        else:
            record = evaluate_candidate(c, model, loaded, archive=store, history=h, solver=Fail()).to_dict()
            assert record["status"] == "failed"
        assert any(f["path"].endswith(".comm") for f in store.verify_inventory(record["evidence_manifest_ref"])["files"])


def test_recorder_failure_stops_and_preserves_operation_output(tmp_path, monkeypatch):
    c, model, loaded, store, h = setup(tmp_path)
    append = h.append
    def fail(kind, *args, **kwargs):
        if kind == "operation.completed":
            raise OSError("recorder failed")
        return append(kind, *args, **kwargs)
    monkeypatch.setattr(h, "append", fail)
    with h, pytest.raises(OSError, match="recorder failed"):
        evaluate_candidate(c, model, loaded, archive=store, history=h, solver=ReplaySolver(RACK / "evidence"))
    assert list((store.root / "attempts").rglob("study_execution.json"))


def test_unverified_native_artifacts_remain_incomplete_and_retained(tmp_path):
    c, model, loaded, store, h = setup(tmp_path)
    with h:
        result = evaluate_candidate(c, model, loaded, archive=store, history=h,
                                    solver=ReplaySolver(RACK / "evidence", execution_method="docker"))
        assert result.completed_operations == ()
        assert result.error_kind is None
        assert decide(result, loaded.check_specs, loaded.settings.operations).outcome == "incomplete"
        assert any(f["path"].endswith("study_execution.json") for f in store.verify_inventory(result.evidence_manifest_ref)["files"])


def test_cold_checker_exception_is_recorded_and_sealed(tmp_path, monkeypatch):
    c, model, loaded, store, h = setup(tmp_path)
    def fail_verify(**kwargs):
        raise ValueError("Native reference coverage unavailable")
    monkeypatch.setattr(model, "verify", fail_verify)
    with h:
        result = evaluate_candidate(c, model, loaded, archive=store, history=h)
        assert result.error_kind == "verification:ValueError"
        assert decide(result, loaded.check_specs, loaded.settings.operations).outcome == "evaluation_failed"
        assert store.verify_inventory(result.evidence_manifest_ref)["status"] == "failed"
        assert h.events()[-1]["kind"] == "evaluation.failed"
