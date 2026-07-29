import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

from scripts import refresh_code_aster_gallery


_REQUIRED_FILES = (
    "study.rmed",
    "study_depl.csv",
    "study_effo.csv",
    "study_reac.csv",
    "study_sieq.csv",
)
_DEFAULT_ATTESTATION = object()


def test_refresh_cli_starts_from_the_scripts_directory():
    script = Path(__file__).resolve().parents[1] / "scripts" / "refresh_code_aster_gallery.py"

    completed = subprocess.run([sys.executable, str(script), "--help"], capture_output=True, text=True)

    assert completed.returncode == 0, completed.stderr


def _artifact(identity="gallery-input", *, attestation=_DEFAULT_ATTESTATION):
    identity = SimpleNamespace(fingerprint=identity)
    return SimpleNamespace(
        study=SimpleNamespace(solver_input_identity=identity),
        analysis_mesh=SimpleNamespace(solver_input_identity=identity),
        result_state=SimpleNamespace(
            solver_input_identity=identity,
            metadata={
                "solve_attestation": (
                    {
                        "solver_name": "Code_Aster",
                        "solver_version": "18.0.12",
                        "execution_method": "wsl",
                        "solved_at": "2026-07-29T12:00:00Z",
                        "solver_input_identity": {"fingerprint": identity.fingerprint},
                    }
                    if attestation is _DEFAULT_ATTESTATION
                    else attestation
                )
            },
        ),
    )


def _mismatched_identity_artifact():
    artifact = _artifact()
    artifact.result_state.solver_input_identity = SimpleNamespace(fingerprint="different")
    return artifact


def _write_required_artifacts(output: Path) -> None:
    for filename in (*_REQUIRED_FILES, "study_execution.json"):
        (output / filename).write_text(filename, encoding="utf-8")


def test_refresh_exports_solves_imports_and_requires_real_attested_artifacts(tmp_path, monkeypatch):
    calls = []
    artifact = _artifact()

    class FakeSolver:
        def __init__(self, *, work_dir):
            self.work_dir = work_dir

        def export_analysis_study(self, model, load_case, output):
            calls.append(("export", model, load_case, output))
            return artifact.study

        def solve_exported_study(self, model, study):
            calls.append(("solve", model, study))

    model = object()
    monkeypatch.setattr(refresh_code_aster_gallery, "build_model", lambda: model)
    monkeypatch.setattr(refresh_code_aster_gallery, "CodeAsterSolver", FakeSolver)
    monkeypatch.setattr(
        refresh_code_aster_gallery,
        "import_code_aster_artifacts",
        lambda **kwargs: calls.append(("import", kwargs)) or artifact,
    )
    _write_required_artifacts(tmp_path)

    refreshed = refresh_code_aster_gallery.refresh_gallery(tmp_path)

    assert refreshed is artifact
    assert [call[0] for call in calls] == ["export", "solve", "import"]
    assert calls[0][2:] == ("Operating", tmp_path)


@pytest.mark.parametrize(
    ("missing", "artifact", "message"),
    [
        ("study.rmed", _artifact(), "study.rmed"),
        ("study_depl.csv", _artifact(), "study_depl.csv"),
        (None, _mismatched_identity_artifact(), "identity"),
        (None, _artifact(attestation=None), "attestation"),
        (None, _artifact(attestation={"solver_version": ""}), "solver_version"),
        (None, _artifact(attestation={"solver_version": "18.0.12", "execution_method": "docker"}), "execution_method"),
    ],
)
def test_refresh_rejects_incomplete_or_non_wsl_artifact_chain(tmp_path, monkeypatch, missing, artifact, message):
    class FakeSolver:
        def __init__(self, *, work_dir):
            pass

        def export_analysis_study(self, model, load_case, output):
            return artifact.study

        def solve_exported_study(self, model, study):
            return None

    monkeypatch.setattr(refresh_code_aster_gallery, "build_model", object)
    monkeypatch.setattr(refresh_code_aster_gallery, "CodeAsterSolver", FakeSolver)
    monkeypatch.setattr(refresh_code_aster_gallery, "import_code_aster_artifacts", lambda **kwargs: artifact)
    _write_required_artifacts(tmp_path)
    if missing:
        (tmp_path / missing).unlink()

    with pytest.raises(ValueError, match=message):
        refresh_code_aster_gallery.refresh_gallery(tmp_path)


def test_artifact_review_uses_the_observed_solve_timestamp(tmp_path):
    from examples.code_aster_artifact_review import build_model, run_example
    from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts
    from tuba.solver.aster import CodeAsterSolver
    from tuba.solver.code_aster_runtime import ATTESTED_CODE_ASTER_FILES

    source = Path(__file__).resolve().parents[1] / "notebooks" / "code_aster_results" / "viz_gallery_operating"
    artifact_dir = tmp_path / "artifact"
    shutil.copytree(source, artifact_dir)
    study = CodeAsterSolver(work_dir=artifact_dir).export_analysis_study(build_model(), "Operating", artifact_dir)
    identity = study.solver_input_identity.to_dict()
    solved_at = "2026-07-29T12:00:00Z"
    (artifact_dir / "study_execution.json").write_text(
        json.dumps(
            {
                "schema_version": "tuba.code_aster_execution.v1",
                "solver_name": "Code_Aster",
                "solver_version": "18.0.12",
                "execution_method": "wsl",
                "solved_at": solved_at,
                "solver_input_identity": identity,
                "artifacts": {
                    filename: {
                        "size_bytes": (artifact_dir / filename).stat().st_size,
                        "sha256": hashlib.sha256((artifact_dir / filename).read_bytes()).hexdigest(),
                    }
                    for filename in ATTESTED_CODE_ASTER_FILES
                },
            }
        ),
        encoding="utf-8",
    )

    artifact = import_code_aster_artifacts(model=build_model(), work_dir=artifact_dir, study=study)
    summary = run_example(tmp_path / "review", artifact_dir=artifact_dir)
    scene = json.loads(Path(summary["scene"]).read_text(encoding="utf-8"))
    review = json.loads((Path(summary["bundle_root"]) / "review.json").read_text(encoding="utf-8"))

    assert scene["created_at"] == review["created_at"] == solved_at
    assert {
        artifact.study.solver_input_identity.fingerprint,
        artifact.analysis_mesh.solver_input_identity.fingerprint,
        artifact.result_state.solver_input_identity.fingerprint,
    } == {identity["fingerprint"]}
    assert "2026-06-" not in json.dumps({"scene": scene, "review": review})
