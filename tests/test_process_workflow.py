"""Portable coupling gate tests; fixture values are not engineering evidence."""

from dataclasses import replace
import hashlib
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


def evaluate(model, bound, archive, history, candidate, backend, process_import=None):
    return evaluate_process_candidate(candidate, model, bound, backend=backend,
        archive=archive, history=history,
        settings=StudySettings(("WaterOperating",), {}, None),
        structural_checks=structural_checks(model, "WaterOperating"),
        wall_temperature_model=WALL_TEMPERATURE_MODEL, process_import=process_import)


class ImportFixture:
    """Workflow fixture; the DEXPI parser has its own source-profile tests."""
    source_xml = b'<Fixture id="source-pipe" />'

    def __init__(self, network):
        self.network = network

    def verify_for(self, network):
        if network != self.network:
            raise ValueError("Import graph does not match the bound process network")

    def to_dict(self):
        return {"network": self.network.to_dict(),
                "source_sha256": hashlib.sha256(self.source_xml).hexdigest(),
                "dexpi_version": "portable-fixture", "profile": "workflow-fixture",
                "source_attribution": "Portable workflow fixture; no external dataset",
                "source_associations": {"pipe_id": "source-pipe", "route_id": "L-101"},
                "study_assumptions": {"layout": "Authored offset; P&ID graphics are not 3-D routing",
                                      "losses": "Explicit portable-test bend and terminal-loss inputs"}}


class UnavailableFlow:
    def solve(self, bound, output):
        raise RuntimeError("OpenModelica runtime unavailable")


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


def test_import_is_retained_before_runtime_failure_and_review_is_self_contained(tmp_path, monkeypatch):
    model, bound, archive, history, candidate = setup_case(tmp_path)
    imported = ImportFixture(bound.network)
    class CheckRetainedBeforeFailure:
        def solve(self, association, output):
            assert (output.parent / "process_input.xml").read_bytes() == imported.source_xml
            assert json.loads((output.parent / "process_import.json").read_text())["bound"] == bound.to_dict()
            raise RuntimeError("OpenModelica runtime unavailable")
    monkeypatch.setattr(StudySettings, "solver", lambda *args: pytest.fail("Unavailable flow must prevent FEA"))
    with history:
        evaluation, decision = evaluate(model, bound, archive, history, candidate,
                                        CheckRetainedBeforeFailure(), imported)
        assert decision.outcome == "evaluation_failed" and evaluation.status == "failed"
        assert not evaluation.completed_operations
        archive.verify_inventory(evaluation.evidence_manifest_ref)
        assert not archive.path(f"attempts/{evaluation.attempt_id}/hydraulics/network.json").exists()
        review_path = write_candidate_review(archive.root, candidate.id, tmp_path / "review")
    scene = json.loads(review_path.read_text())
    assert scene["search"]["result_status"] == "unsolved_preview"
    assert not scene["result_fields"] and "process" not in scene
    retained = scene["process_import"]
    assert retained["source"] == imported.to_dict()
    assert retained["bound_fingerprint"] == bound.fingerprint
    assert scene["search"]["process_source_refs"] == retained["source_refs"]
    for reference in retained["source_refs"].values():
        assert (review_path.parent / reference).is_file()
    assert (review_path.parent / retained["source_refs"]["xml"]).read_bytes() == imported.source_xml
    report = json.loads((review_path.parent / "review.json").read_text())
    table = report["tables"]["process_import"]
    assert any(row["item"] == "Study assumption: layout" for row in table["rows"])
    assert any(row == {"item": "Source attribution", "value": imported.to_dict()["source_attribution"]}
               for row in table["rows"])
    assert "P&amp;ID graphics are not 3-D routing" in (review_path.parent / "index.html").read_text()


def test_hydraulic_rejection_review_keeps_import_links_and_fluid_basis(tmp_path, monkeypatch):
    model, bound, archive, history, candidate = setup_case(tmp_path)
    backend, _ = install_execution_fixture(tmp_path, monkeypatch, bound)
    monkeypatch.setattr(StudySettings, "solver", lambda *args: pytest.fail("Hydraulic rejection must prevent FEA"))
    with history:
        evaluation, decision = evaluate(model, bound, archive, history, candidate,
                                        backend, ImportFixture(bound.network))
        assert decision.outcome == "rejected_constraint"
        scene_path = write_candidate_review(archive.root, candidate.id, tmp_path / "review")
    scene = json.loads(scene_path.read_text())
    assert scene["process"]["source_refs"] == scene["process_import"]["source_refs"]
    assert scene["search"]["result_status"] == "openmodelica_results"
    assert all(field["label"].startswith("OpenModelica:") for field in scene["result_fields"])


def test_import_graph_mismatch_prevents_attempt_or_backend_execution(tmp_path):
    model, bound, archive, history, candidate = setup_case(tmp_path)
    imported = ImportFixture(replace(bound.network, id="DifferentSourceGraph"))
    class NeverSolve:
        def solve(self, *args):
            pytest.fail("Mismatched import graph must prevent backend execution")
    with history, pytest.raises(ValueError, match="Import graph"):
        evaluate(model, bound, archive, history, candidate, NeverSolve(), imported)
    assert not archive.path("attempts").exists()


@pytest.mark.parametrize("target", ["raw_xml", "inventory"])
def test_import_review_refuses_changed_raw_xml_or_sealed_inventory(tmp_path, target):
    model, bound, archive, history, candidate = setup_case(tmp_path)
    with history:
        evaluation, _ = evaluate(model, bound, archive, history, candidate,
                                 UnavailableFlow(), ImportFixture(bound.network))
    reference = (f"attempts/{evaluation.attempt_id}/process_input.xml" if target == "raw_xml"
                 else evaluation.evidence_manifest_ref)
    path = archive.path(reference)
    path.write_bytes(path.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="integrity"):
        write_candidate_review(archive.root, candidate.id, tmp_path / "review")


def test_review_refuses_unsealed_import_pair(tmp_path):
    model, bound, archive, history, candidate = setup_case(tmp_path)
    with history:
        evaluation, _ = evaluate(model, bound, archive, history, candidate, UnavailableFlow())
    folder = archive.path(f"attempts/{evaluation.attempt_id}")
    (folder / "process_input.xml").write_bytes(ImportFixture.source_xml)
    (folder / "process_import.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="sealed XML and association pair"):
        write_candidate_review(archive.root, candidate.id, tmp_path / "review")
