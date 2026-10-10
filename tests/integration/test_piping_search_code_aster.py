"""Opt-in qualification: fresh real Code_Aster solves, never replayed fixtures."""

import json
import os
from pathlib import Path

import pytest

from tuba.project.study import StudySettings
from tuba.search.export import export_history, inspect_history, write_candidate_review
from tuba.search.history import History
from tuba.search.run import run_search
from tuba.solver.code_aster_runtime import load_code_aster_execution_attestation

pytestmark = pytest.mark.skipif(os.environ.get("TUBA_RUN_CODE_ASTER_INTEGRATION") != "1",
                                reason="Set TUBA_RUN_CODE_ASTER_INTEGRATION=1 for real Code_Aster qualification")


def test_retained_hot_line_search_with_real_code_aster(tmp_path, monkeypatch):
    project = Path(__file__).resolve().parents[2] / "examples/piping-search"
    root = Path(os.environ.get("TUBA_SEARCH_QUALIFICATION_DIR", str(tmp_path / "qualified-search")))
    resumed = os.environ.get("TUBA_SEARCH_QUALIFICATION_RESUME") == "1"
    result = run_search(project, root, resume=resumed)
    assert not result["blocked"], result
    assert result["selected_candidate_id"] is not None, result
    with History.open(root / "history.sqlite3", readonly=True) as h:
        events, manifest = h.events(), h.manifest()
    evaluations = [e["payload"] for e in events if e["kind"] in {"evaluation.completed", "evaluation.failed"}]
    decisions = [e["payload"] for e in events if e["kind"] == "candidate.decision"]
    rejected = {d["candidate_id"] for d in decisions if d["outcome"] == "rejected_constraint"}
    assert any(e["candidate_id"] in rejected and not e["completed_operations"] for e in evaluations)
    assert any(e["candidate_id"] in rejected and e["status"] == "complete" and len(e["completed_operations"]) == 2 for e in evaluations)
    assert any(c["verdict"] == "fail" and c["reason_code"] in {"operating_overlap", "operating_clearance"}
               for e in evaluations for c in e["checks"])
    assert any(d["outcome"] == "feasible_not_selected" for d in decisions)
    versions, methods = set(), set()
    for event in events:
        if event["kind"] != "operation.completed":
            continue
        folder = root / event["payload"]["artifact_dir"]
        attestation = load_code_aster_execution_attestation(folder)
        assert attestation and attestation["solver_name"] == "Code_Aster"
        assert (folder / "study_depl.csv").is_file() and (folder / "study_reac.csv").is_file()
        versions.add(attestation["solver_version"])
        methods.add(attestation["execution_method"])
    selected = result["selected_candidate_id"]
    write_candidate_review(root, selected, root / "exports/selected-review")
    def unavailable(*args, **kwargs):
        raise AssertionError("Read-only history after restart cannot request a solver")
    monkeypatch.setattr(StudySettings, "solver", unavailable)
    assert inspect_history(root, selected)["candidates"][0]["outcome"] == "selected"
    exported = export_history(root, root / "exports/replay")
    assert json.loads(exported.read_text())["availability_diagnostics"] == []
    qualification = {"schema": "tuba.search.qualification.v1", **result,
                     "resumed": resumed,
                     "source_digest": manifest["source_digest"], "check_digest": manifest["check_digest"],
                     "runtime_versions": sorted(versions), "execution_methods": sorted(methods),
                     "operations": manifest["settings"]["operations"],
                     "evaluations": [{k: e[k] for k in ("candidate_id", "attempt_id", "status", "completed_operations", "evidence_manifest_ref")} for e in evaluations],
                     "scope": manifest["scope"]}
    (root / "qualification.json").write_text(json.dumps(qualification, indent=2, allow_nan=False), encoding="utf-8")
