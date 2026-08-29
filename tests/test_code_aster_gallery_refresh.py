import hashlib
from dataclasses import replace
from importlib import import_module
import json
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

from scripts import refresh_code_aster_gallery


_SOLVER_OUTPUT_FILES = (
    "study.mess",
    "study.rmed",
    "study_depl.csv",
    "study_effo.csv",
    "study_reac.csv",
    "study_sieq.csv",
    "study_execution.json",
)
_DEFAULT_ATTESTATION = object()


def _set_refresh_producer(monkeypatch, gallery_id, producer):
    galleries = import_module("scripts.official_gallery").OFFICIAL_GALLERIES
    monkeypatch.setattr(
        refresh_code_aster_gallery,
        "OFFICIAL_GALLERIES",
        tuple(
            replace(gallery, refresh_producer=producer)
            if gallery.id == gallery_id
            else gallery
            for gallery in galleries
        ),
    )


def test_refresh_cli_starts_from_the_scripts_directory():
    script = Path(__file__).resolve().parents[1] / "scripts" / "refresh_code_aster_gallery.py"

    completed = subprocess.run([sys.executable, str(script), "--help"], capture_output=True, text=True)

    assert completed.returncode == 0, completed.stderr


def test_official_gallery_records_own_refresh_metadata():
    galleries = import_module("scripts.official_gallery").OFFICIAL_GALLERIES
    engineering = tuple(gallery for gallery in galleries if gallery.refresh_producer is not None)
    non_refreshable = tuple(gallery for gallery in galleries if gallery.refresh_producer is None)

    assert tuple(gallery.id for gallery in engineering) == (
        "autorouted-expansion-loop",
        "code-aster-review",
        "elements-supports-review",
        "pipe-tee-volume-review",
        "support-rack-review",
    )
    assert all(gallery.artifact_dir is not None for gallery in engineering)
    assert tuple(gallery.id for gallery in non_refreshable) == (
        "gmsh-tee-mesh-review",
        "imported_component_mixed_demo",
    )
    assert all(gallery.artifact_dir is None for gallery in non_refreshable)
    assert [gallery.id for gallery in galleries if gallery.volume_export] == [
        "pipe-tee-volume-review"
    ]


def test_refresh_all_galleries_uses_record_owned_artifact_directories(monkeypatch):
    galleries = import_module("scripts.official_gallery").OFFICIAL_GALLERIES
    calls = []

    def refresh(output, *, gallery):
        calls.append((Path(output), gallery))
        return gallery

    monkeypatch.setattr(refresh_code_aster_gallery, "refresh_gallery", refresh)

    refreshed = refresh_code_aster_gallery.refresh_all_galleries()

    engineering = tuple(gallery for gallery in galleries if gallery.refresh_producer is not None)
    assert calls == [(gallery.artifact_dir, gallery.id) for gallery in engineering]
    assert tuple(refreshed) == tuple(gallery.id for gallery in engineering)


def test_refresh_all_rejects_refreshable_gallery_without_canonical_directory(monkeypatch):
    galleries = import_module("scripts.official_gallery").OFFICIAL_GALLERIES
    broken = replace(galleries[0], artifact_dir=None)
    monkeypatch.setattr(
        refresh_code_aster_gallery,
        "OFFICIAL_GALLERIES",
        (broken, *galleries[1:]),
    )

    with pytest.raises(ValueError, match="canonical artifact directory"):
        refresh_code_aster_gallery.refresh_all_galleries()


def test_refresh_rejects_the_model_only_gallery(tmp_path):
    with pytest.raises(ValueError, match="not refreshable"):
        refresh_code_aster_gallery.refresh_gallery(
            tmp_path,
            gallery="imported_component_mixed_demo",
        )


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["--all", "--gallery", "code-aster-review"], "--all cannot be combined"),
        (["--all", "--output", "artifacts"], "--all cannot be combined"),
        (["--gallery", "code-aster-review"], "single-gallery mode requires --output"),
        (
            ["--gallery", "imported_component_mixed_demo", "--output", "artifacts"],
            "Official gallery 'imported_component_mixed_demo' is not refreshable.",
        ),
    ],
)
def test_refresh_cli_rejects_invalid_mode_combinations(arguments, message, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["refresh_code_aster_gallery.py", *arguments])

    with pytest.raises(SystemExit) as raised:
        refresh_code_aster_gallery.main()

    assert raised.value.code == 2
    assert message in capsys.readouterr().err


def test_refresh_cli_all_uses_the_registry_loop(monkeypatch):
    calls = []
    monkeypatch.setattr(sys, "argv", ["refresh_code_aster_gallery.py", "--all"])
    monkeypatch.setattr(
        refresh_code_aster_gallery,
        "refresh_all_galleries",
        lambda: calls.append("all") or {},
        raising=False,
    )

    assert refresh_code_aster_gallery.main() == 0
    assert calls == ["all"]


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


def _write_solver_outputs(output: Path, *, prefix: str, missing: str | None = None) -> None:
    for filename in _SOLVER_OUTPUT_FILES:
        if filename != missing:
            (output / filename).write_text(f"{prefix} {filename}", encoding="utf-8")


def test_refresh_accepts_native_command_artifact_chain(tmp_path):
    artifact = _artifact()
    artifact.result_state.metadata["solve_attestation"]["execution_method"] = "command"
    _write_solver_outputs(tmp_path, prefix="native")

    refresh_code_aster_gallery._validate_gallery_artifact_chain(tmp_path, artifact)


def test_refresh_exports_solves_imports_and_requires_real_attested_artifacts(tmp_path, monkeypatch):
    calls = []
    scratch_paths = []
    artifact = _artifact()

    class FakeSolver:
        def __init__(self, *, work_dir):
            self.work_dir = work_dir

        def export_analysis_study(self, model, load_case, output):
            calls.append(("export", model, load_case, output))
            return artifact.study

        def solve_exported_study(self, model, study):
            calls.append(("solve", model, study))
            assert not any((tmp_path / filename).exists() for filename in _SOLVER_OUTPUT_FILES)
            _write_solver_outputs(tmp_path, prefix="fresh")

    model = object()
    _set_refresh_producer(
        monkeypatch,
        "code-aster-review",
        lambda scratch: scratch_paths.append(Path(scratch)) or (model, "Operating"),
    )
    monkeypatch.setattr(refresh_code_aster_gallery, "CodeAsterSolver", FakeSolver)
    monkeypatch.setattr(
        refresh_code_aster_gallery,
        "import_code_aster_artifacts",
        lambda **kwargs: calls.append(("import", kwargs)) or artifact,
    )
    _write_solver_outputs(tmp_path, prefix="stale")

    refreshed = refresh_code_aster_gallery.refresh_gallery(tmp_path)

    assert refreshed is artifact
    assert [call[0] for call in calls] == ["export", "solve", "import"]
    assert calls[0][2:] == ("Operating", tmp_path)
    assert all((tmp_path / filename).read_text(encoding="utf-8").startswith("fresh") for filename in _SOLVER_OUTPUT_FILES)
    assert len(scratch_paths) == 1
    assert not scratch_paths[0].exists()


def test_refresh_uses_native_volume_export_for_the_tee_gallery(tmp_path, monkeypatch):
    calls = []
    artifact = _artifact()
    artifact.study.metadata = {"volume_analysis": True}

    class FakeSolver:
        def __init__(self, *, work_dir):
            self.work_dir = work_dir

        def export_volume_study(self, model, load_case, output, **kwargs):
            calls.append(("export_volume", model, load_case, output, kwargs))
            return artifact.study

        def solve_exported_study(self, model, study):
            calls.append(("solve", model, study))
            for filename in refresh_code_aster_gallery._VOLUME_SOLVER_OUTPUT_FILES:
                (tmp_path / filename).write_text(filename, encoding="utf-8")

    model = object()
    _set_refresh_producer(
        monkeypatch,
        "pipe-tee-volume-review",
        lambda scratch: (model, "Operating"),
    )
    monkeypatch.setattr(refresh_code_aster_gallery, "CodeAsterSolver", FakeSolver)
    monkeypatch.setattr(refresh_code_aster_gallery, "import_code_aster_artifacts", lambda **kwargs: artifact)

    refreshed = refresh_code_aster_gallery.refresh_gallery(
        tmp_path,
        gallery="pipe-tee-volume-review",
    )

    assert refreshed is artifact
    assert calls[0][0] == "export_volume"
    assert calls[0][4]["element_ids"] == refresh_code_aster_gallery.TEE_VOLUME_ELEMENT_IDS
    assert calls[0][4]["max_element_size"] == refresh_code_aster_gallery.TEE_VOLUME_MAX_ELEMENT_SIZE
    assert calls[0][4]["export_tensor_stress"] is False


@pytest.mark.parametrize(
    ("missing", "artifact", "message"),
    [
        ("study.rmed", _artifact(), "study.rmed"),
        ("study_depl.csv", _artifact(), "study_depl.csv"),
        ("study_effo.csv", _artifact(), "study_effo.csv"),
        ("study_reac.csv", _artifact(), "study_reac.csv"),
        ("study_sieq.csv", _artifact(), "study_sieq.csv"),
        ("study_execution.json", _artifact(), "study_execution.json"),
        (None, _mismatched_identity_artifact(), "identity"),
        (None, _artifact(attestation=None), "attestation"),
        (None, _artifact(attestation={"solver_version": ""}), "solver_version"),
        (None, _artifact(attestation={"solver_version": "18.0.12", "execution_method": ""}), "execution_method"),
        (None, _artifact(attestation={"solver_version": "18.0.12", "execution_method": "docker"}), "execution_method"),
        (
            None,
            _artifact(
                attestation={
                    "solver_name": "",
                    "solver_version": "18.0.12",
                    "execution_method": "wsl",
                    "solved_at": "2026-07-29T12:00:00Z",
                    "solver_input_identity": {"fingerprint": "gallery-input"},
                }
            ),
            "Code_Aster",
        ),
        (
            None,
            _artifact(
                attestation={
                    "solver_name": "Code_Aster",
                    "solver_version": "18.0.12",
                    "execution_method": "wsl",
                    "solved_at": "",
                    "solver_input_identity": {"fingerprint": "gallery-input"},
                }
            ),
            "solved_at",
        ),
    ],
)
def test_refresh_rejects_incomplete_artifact_chain(tmp_path, monkeypatch, missing, artifact, message):
    class FakeSolver:
        def __init__(self, *, work_dir):
            pass

        def export_analysis_study(self, model, load_case, output):
            return artifact.study

        def solve_exported_study(self, model, study):
            _write_solver_outputs(tmp_path, prefix="fresh", missing=missing)
            return None

    _set_refresh_producer(
        monkeypatch,
        "code-aster-review",
        lambda scratch: (object(), "Operating"),
    )
    monkeypatch.setattr(refresh_code_aster_gallery, "CodeAsterSolver", FakeSolver)
    monkeypatch.setattr(refresh_code_aster_gallery, "import_code_aster_artifacts", lambda **kwargs: artifact)
    _write_solver_outputs(tmp_path, prefix="stale")

    with pytest.raises(ValueError, match=message):
        refresh_code_aster_gallery.refresh_gallery(tmp_path)


def test_refresh_accepts_a_non_wsl_execution_method(tmp_path):
    artifact = _artifact(
        attestation={
            "solver_name": "Code_Aster",
            "solver_version": "18.0.12",
            "execution_method": "native-python-runtime",
            "solved_at": "2026-07-29T12:00:00Z",
            "solver_input_identity": {"fingerprint": "gallery-input"},
        }
    )
    _write_solver_outputs(tmp_path, prefix="fresh")

    refresh_code_aster_gallery._validate_gallery_artifact_chain(tmp_path, artifact)


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


@pytest.mark.skipif(sys.platform != "win32", reason="Windows process-search regression")
def test_bend_export_preserves_windows_executable_search(tmp_path):
    executable = shutil.which("git")
    if executable is None:
        pytest.skip("git is unavailable")

    from examples.code_aster_artifact_review import build_model
    from tuba.solver.aster import CodeAsterSolver

    CodeAsterSolver(work_dir=tmp_path).export_analysis_study(
        build_model(),
        "Operating",
        tmp_path,
    )

    completed = subprocess.run(["git", "--version"], capture_output=True, text=True)

    assert completed.returncode == 0, completed.stderr
