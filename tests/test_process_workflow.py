"""Portable coupling gate tests; fixture values are not engineering evidence."""

import json
from pathlib import Path

import pytest

from examples.process_network.model import build_model, process_inputs
from examples.process_network.run import structural_checks
from tests.test_process_modelica import install_execution_fixture
from tuba.process.review import attach_process_review
from tuba.process.structural import WALL_TEMPERATURE_MODEL
from tuba.process.workflow import evaluate_process_candidate
from tuba.project.study import StudySettings
from tuba.search.artifacts import ArtifactStore
from tuba.search.contracts import Candidate
from tuba.search.export import write_candidate_review
from tuba.search.history import History
from tuba.visualization import SceneRequest, build_visualization_scene


def setup_case(tmp_path):
    model = build_model({"size": "small", "offset_m": 1.0})
    bound = process_inputs(model)
    archive = ArtifactStore(tmp_path / "archive")
    source_ref = archive.capture_files(Path(__file__).parents[1] / "examples/process_network", ("model.py",))
    history = History.create(archive.path("history.sqlite3"),
                             {"schema": "tuba.search.history.v1", "run_id": "Test",
                              "settings": {"operations": ["WaterOperating"], "volume_export": None},
                              "scope": "Portable fixture only", "source_manifest_ref": source_ref})
    candidate = Candidate("Small", (), {}, "Portable hydraulic rejection fixture")
    history.record_candidate(candidate)
    return model, bound, archive, history, candidate


def evaluate(model, bound, archive, history, candidate, backend):
    return evaluate_process_candidate(candidate, model, bound, backend=backend,
        archive=archive, history=history,
        settings=StudySettings(("WaterOperating",), {}, None),
        structural_checks=structural_checks(model, "WaterOperating"),
        wall_temperature_model=WALL_TEMPERATURE_MODEL)


def test_fluid_rejection_retains_raw_evidence_and_never_solves_structure(tmp_path, monkeypatch):
    model, bound, archive, history, candidate = setup_case(tmp_path)
    backend, _ = install_execution_fixture(tmp_path, monkeypatch, bound)
    monkeypatch.setattr(StudySettings, "solver", lambda *args: pytest.fail("Hydraulic rejection must prevent FEA"))
    with history:
        evaluation, decision = evaluate(model, bound, archive, history, candidate, backend)
        assert decision.outcome == "rejected_constraint"
        assert evaluation.status == "not_started"
        assert evaluation.completed_operations == () and not model.operations
        failures = [check for check in evaluation.checks if check.verdict == "fail"]
        assert failures and all(check.basis == "openmodelica" for check in failures)
        assert all(check.measured_value > 3 for check in failures)
        inventory = archive.verify_inventory(evaluation.evidence_manifest_ref,
                                              expected_sha256=evaluation.evidence_manifest_sha256)
        files = [entry["path"] for entry in inventory["files"]]
        assert any(path.endswith("_res.csv") for path in files)
        assert not any(path.endswith(".rmed") for path in files)
        payload = json.loads(archive.path(f"attempts/{evaluation.attempt_id}/process_review.json").read_text())
        scene = build_visualization_scene(SceneRequest(model))
        attach_process_review(scene, payload)
        assert len(scene.result_fields) == 4
        assert all(field.label.startswith("OpenModelica:") for field in scene.result_fields)
        assert all(overlay.kind != "result_state" for overlay in scene.overlays)
        assert all(value > 3 for value in scene.overlays[-4].data["values"].values())
        review_path = write_candidate_review(archive.root, candidate.id, tmp_path / "review")
        review = json.loads(review_path.read_text())
        assert review["search"]["result_status"] == "openmodelica_results"
        for check in review["search"]["checks"]:
            if check["basis"] == "openmodelica":
                assert all((review_path.parent / ref).is_file() for ref in check["evidence_refs"])
        with pytest.raises(ValueError, match="new Candidate ID"):
            evaluate(model, bound, archive, history, candidate, backend)
        csv_path = archive.path(next(path for path in files if path.endswith("_res.csv")))
        csv_path.write_text("altered evidence", encoding="utf-8")
        with pytest.raises(ValueError, match="integrity"):
            archive.verify_inventory(evaluation.evidence_manifest_ref)


def test_fluid_runtime_failure_is_recorded_and_sealed(tmp_path, monkeypatch):
    model, bound, archive, history, candidate = setup_case(tmp_path)
    class MissingRuntime:
        def solve(self, bound, output):
            output.mkdir()
            (output / "failure.log").write_text("runtime unavailable")
            raise RuntimeError("OpenModelica runtime unavailable")
    monkeypatch.setattr(StudySettings, "solver", lambda *args: pytest.fail("Missing flow result must prevent FEA"))
    with history:
        evaluation, decision = evaluate(model, bound, archive, history, candidate, MissingRuntime())
        assert evaluation.status == "failed"
        assert decision.outcome == "evaluation_failed"
        assert not evaluation.completed_operations
        assert any(check.constraint_id.startswith("flow.") and check.verdict == "unknown"
                   for check in evaluation.checks)
        inventory = archive.verify_inventory(evaluation.evidence_manifest_ref)
        assert any(entry["path"].endswith("failure.log") for entry in inventory["files"])
        assert any(event["kind"] == "evaluation.diagnostic" for event in history.events())


def test_geometry_edit_during_fluid_solve_cannot_publish_a_stale_rejection(tmp_path, monkeypatch):
    model, bound, archive, history, candidate = setup_case(tmp_path)
    backend, _ = install_execution_fixture(tmp_path, monkeypatch, bound)
    class EditDuringSolve:
        def solve(self, association, output):
            result = backend.solve(association, output)
            model.sections["WaterPipe"].WT *= 1.1
            return result
    monkeypatch.setattr(StudySettings, "solver", lambda *args: pytest.fail("Stale geometry must prevent FEA"))
    with history:
        evaluation, decision = evaluate(model, bound, archive, history, candidate, EditDuringSolve())
        assert decision.outcome == "evaluation_failed"
        assert not archive.path(f"attempts/{evaluation.attempt_id}/process_review.json").exists()
        archive.verify_inventory(evaluation.evidence_manifest_ref)


def test_scene_rejects_missing_pipe_associations():
    model = build_model({"size": "larger", "offset_m": 1.0})
    scene = build_visualization_scene(SceneRequest(model))
    with pytest.raises(ValueError, match="cover"):
        attach_process_review(scene, {"schema": "tuba.process.review.v1", "basis": "openmodelica", "segments": []})


def test_preparation_cannot_relax_a_declared_required_failure(tmp_path, monkeypatch):
    from tuba.search.contracts import CheckSpec, CheckResult, EvaluationContext
    from tuba.search.evaluate import evaluate_candidate

    model, bound, archive, history, candidate = setup_case(tmp_path)
    spec = CheckSpec("flow.required", "design_requirement", True, (), (), 3, "m/s", {})
    failed = CheckResult(spec.id, "fail", False, "fixture", "too_fast", "Portable test",
                         measured_value=4, limit=3, unit="m/s", comparator="max")
    monkeypatch.setattr(StudySettings, "solver", lambda *args: pytest.fail("Required failure must gate FEA"))
    with history:
        result = evaluate_candidate(candidate, model,
            EvaluationContext({}, StudySettings(("WaterOperating",), {}, None), (spec,), None),
            archive=archive, history=history, prepare_attempt=lambda _: (failed,))
        assert result.status == "not_started"
        assert result.completed_operations == ()
