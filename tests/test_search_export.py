import json
from pathlib import Path

import pytest

from tests.project_replay import ReplaySolver
from tests.test_search_run import RACK, author
from tuba.analysis.staged_run import read_staged_runs
from tuba.project.study import StudySettings
from tuba.search.export import export_history, inspect_history, write_candidate_review
from tuba.search.run import run_search


def completed(tmp_path):
    project = author(tmp_path)
    run = tmp_path / "run"
    run_search(project, run, solver=ReplaySolver(RACK / "evidence"))
    return run


def test_inspection_and_export_are_read_only_and_need_no_solver(tmp_path, monkeypatch):
    run = completed(tmp_path)
    before = {p.relative_to(run): p.read_bytes() for p in run.rglob("*") if p.is_file()}
    def unavailable(*args, **kwargs):
        pytest.fail("Read-only export cannot request a solver")
    monkeypatch.setattr(StudySettings, "solver", unavailable)
    assert inspect_history(run)["candidates"][0]["outcome"] == "selected"
    manifest = export_history(run, tmp_path / "export")
    payload = json.loads(manifest.read_text())
    assert payload["schema"] == "tuba.search.replay.v1"
    assert payload["self_contained"] is False
    assert payload["candidates"][1]["outcome"] == "feasible_not_selected"
    assert len(payload["candidates"][0]["decisions"]) == 2
    events = [json.loads(line) for line in (manifest.parent / "events.jsonl").read_text().splitlines()]
    assert events == payload["events"]
    assert before == {p.relative_to(run): p.read_bytes() for p in run.rglob("*") if p.is_file()}


def test_repeated_native_states_remain_candidate_and_attempt_scoped(tmp_path, monkeypatch):
    from tuba.search.run import EvidenceCache
    monkeypatch.setattr(EvidenceCache, "find", lambda *args: None)
    run = completed(tmp_path)
    payload = json.loads(export_history(run, tmp_path / "export").read_text())
    checks = [row["evaluations"][0]["scoped_checks"][-1] for row in payload["candidates"]]
    assert checks[0]["scope"]["result_state_id"] == checks[1]["scope"]["result_state_id"]
    assert checks[0]["scope"]["candidate_id"] != checks[1]["scope"]["candidate_id"]
    assert checks[0]["scope"]["attempt_id"] != checks[1]["scope"]["attempt_id"]
    assert checks[0]["evidence"][0]["path"] != checks[1]["evidence"][0]["path"]
    assert all(check["evidence"][0]["sha256"] for check in checks)


def test_missing_artifacts_are_explicit_but_review_refuses_them(tmp_path):
    run = completed(tmp_path)
    missing = next((run / "attempts").rglob("study_reac.csv"))
    missing.unlink()
    payload = json.loads(export_history(run, tmp_path / "export").read_text())
    assert payload["availability_diagnostics"]
    assert any(f["availability"] == "missing" for inventory in payload["inventories"] for f in inventory["files"])
    with pytest.raises(ValueError, match="integrity"):
        write_candidate_review(run, "C0001", tmp_path / "review")


def test_native_review_is_a_complete_bundle_and_preserves_solver_scope(tmp_path, monkeypatch):
    run = completed(tmp_path)
    monkeypatch.setattr(StudySettings, "solver", lambda *a, **k: pytest.fail("Review cannot solve"))
    scene_path = write_candidate_review(run, "C0002", tmp_path / "review")
    scene = json.loads(scene_path.read_text())
    assert scene["search"]["candidate_id"] == "C0002"
    assert scene["search"]["solved_operations"] == ["Operating"]
    assert scene["result_fields"]
    assert read_staged_runs(scene_path.parent)[0].operation == "Operating"
    assert (scene_path.parent / "source.py").is_file()


def test_unsolved_candidate_review_has_geometry_and_no_solver_overlays(tmp_path):
    project = author(tmp_path, values=(100.0,), budget=0)
    run = tmp_path / "run"
    run_search(project, run)
    path = write_candidate_review(run, "C0001", tmp_path / "review")
    scene = json.loads(path.read_text())
    assert scene["objects"] and scene["search"]["solved_operations"] == []
    assert scene["search"]["result_status"] == "unsolved_preview"
    assert scene["result_fields"] == []


def test_output_conflict_and_unknown_candidate_are_refused(tmp_path):
    run = completed(tmp_path)
    output = tmp_path / "export"
    output.mkdir()
    (output / "sentinel").write_text("preserve")
    with pytest.raises(FileExistsError):
        export_history(run, output)
    assert (output / "sentinel").read_text() == "preserve"
    with pytest.raises(ValueError, match="candidate"):
        write_candidate_review(run, "absent", tmp_path / "review")


def test_changed_archived_geometry_is_diagnosed_and_cannot_be_reviewed(tmp_path):
    run = completed(tmp_path)
    row = inspect_history(run, "C0001")["candidates"][0]
    path = run / row["build"]["model_ref"]
    data = json.loads(path.read_text())
    data["name"] = "changed archived geometry"
    path.write_text(json.dumps(data))
    payload = json.loads(export_history(run, tmp_path / "export").read_text())
    assert payload["candidates"][0]["model_artifact"]["availability"] == "damaged"
    assert any(d["path"] == row["build"]["model_ref"] for d in payload["availability_diagnostics"])
    with pytest.raises(ValueError, match="geometry integrity"):
        write_candidate_review(run, "C0001", tmp_path / "review")


def test_earlier_failed_attempt_review_keeps_its_own_outcome(tmp_path):
    project = author(tmp_path, values=(100.0,), budget=2)
    run = tmp_path / "run"
    class Unavailable:
        def solve_exported_study(self, model, study):
            raise RuntimeError("Code_Aster runtime unavailable")
    run_search(project, run, solver=Unavailable())
    old_attempt = inspect_history(run)["candidates"][0]["evaluations"][0]["attempt_id"]
    run_search(project, run, resume=True, solver=ReplaySolver(RACK / "evidence"))
    scene = json.loads(write_candidate_review(run, "C0001", tmp_path / "review", attempt_id=old_attempt).read_text())
    assert scene["search"]["outcome"] == "evaluation_failed"
    assert scene["search"]["current_candidate_outcome"] == "selected"
    assert scene["search"]["solved_operations"] == []
