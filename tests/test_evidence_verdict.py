"""The one verdict over evidence: verified, unverified, damaged, or missing, and whether it is reusable."""

import json
import shutil
from dataclasses import replace
from pathlib import Path

from tuba.project import run_model_script
from tuba.project.evidence import evidence_state, evidence_verdict, exported_study_matches
from tuba.project.freshness import expected_identity

SUPPORT_RACK = Path(__file__).resolve().parents[1] / "examples" / "support-rack-review"
EVIDENCE = SUPPORT_RACK / "evidence" / "Operating"


def _model():
    return run_model_script(SUPPORT_RACK / "model.py")["model"]


def _identity():
    return expected_identity(_model(), "Operating")


def _copied_evidence(tmp_path: Path) -> Path:
    target = tmp_path / "Operating"
    shutil.copytree(EVIDENCE, target)
    return target


def test_committed_evidence_is_verified_and_reusable():
    state = evidence_state(EVIDENCE)

    assert state.status == "verified"
    assert state.trust == "verified"
    assert state.attestation is not None
    assert evidence_verdict(EVIDENCE, _identity()).reusable


def test_a_folder_without_an_attestation_is_missing(tmp_path):
    state = evidence_state(tmp_path)

    assert state.status == "missing"
    assert state.attestation is None
    assert not evidence_verdict(tmp_path, _identity()).reusable


def test_a_tampered_artifact_is_damaged(tmp_path):
    folder = _copied_evidence(tmp_path)
    tampered = folder / "study_depl.csv"
    tampered.write_text(tampered.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    state = evidence_state(folder)

    assert state.status == "damaged"
    assert state.attestation is None
    assert "does not match" in state.reason
    assert not evidence_verdict(folder, _identity()).reusable


def test_a_docker_solve_is_unverified_and_not_reusable(tmp_path):
    folder = _copied_evidence(tmp_path)
    attestation_path = folder / "study_execution.json"
    payload = json.loads(attestation_path.read_text(encoding="utf-8"))
    payload["execution_method"] = "docker"
    attestation_path.write_text(json.dumps(payload), encoding="utf-8")

    state = evidence_state(folder)

    assert state.status == "unverified"
    assert state.attestation is not None
    assert not evidence_verdict(folder, _identity()).reusable
    # The trust-free reuse probe still reports the exported study as solved.
    assert exported_study_matches(folder, _identity())


def test_a_mismatched_identity_is_not_reusable():
    identity = replace(_identity(), fingerprint="0" * 64)

    verdict = evidence_verdict(EVIDENCE, identity)

    assert verdict.state.status == "verified"
    assert not verdict.identity_matches
    assert not verdict.reusable


def test_evidence_state_is_memoized_per_folder_content(tmp_path):
    folder = _copied_evidence(tmp_path)
    first = evidence_state(folder)
    tampered = folder / "study_reac.csv"
    tampered.write_text("not a reaction table\n", encoding="utf-8")

    second = evidence_state(folder)

    assert first.status == "verified"
    assert second.status == "damaged"
