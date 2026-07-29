"""Official viewer publication contracts."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.build_pages import build_examples, validate_official_bundle, write_bundle_catalog
from tuba.analysis.code_aster_artifacts import CodeAsterArtifactImport, stage_code_aster_artifact_evidence
from tuba.analysis.results import ResultState
from tuba.analysis.study import AnalysisStudy
from tuba.solver.base import FEAResults


def test_pages_catalog_contains_the_two_validated_official_bundles(tmp_path: Path) -> None:
    """Catches a publisher that omits either official example or its catalog."""
    bundle_ids = build_examples(tmp_path, audience="pages")

    write_bundle_catalog(tmp_path, bundle_ids)

    assert bundle_ids == ("code-aster-review", "imported_component_mixed_demo")
    assert json.loads((tmp_path / "bundles.json").read_text(encoding="utf-8")) == list(bundle_ids)

    engineering = json.loads((tmp_path / "code-aster-review" / "scene.json").read_text(encoding="utf-8"))
    assert len(engineering["result_fields"]) == 4
    assert {layer["category"] for layer in engineering["layers"]} == {
        "design", "analysis_mesh", "results", "annotations"
    }

    model_review = json.loads(
        (tmp_path / "imported_component_mixed_demo" / "scene.json").read_text(encoding="utf-8")
    )
    assert model_review["result_fields"] == []
    assert "no solver results" in json.dumps(model_review).lower()
    review = json.loads((tmp_path / "code-aster-review" / "review.json").read_text(encoding="utf-8"))
    study_provenance = next(item for item in review["provenance"] if item["kind"] == "study")
    assert "work_dir" not in study_provenance["metadata"]
    result_provenance = next(item for item in review["provenance"] if item["kind"] == "result_state")
    assert all(value.startswith("artifacts/") for value in result_provenance["files"].values())
    assert result_provenance["metadata"]["file_sha256"]["rmed"]
    assert result_provenance["metadata"]["file_sizes"]["rmed"] > 0


def test_examples_cli_runs_directly_from_the_repository_root(tmp_path: Path) -> None:
    """Catches the script-only import path that breaks the documented CLI."""
    completed = subprocess.run(
        [sys.executable, "scripts/build_pages.py", "examples", "--output", str(tmp_path), "--audience", "pages"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads((tmp_path / "bundles.json").read_text(encoding="utf-8")) == [
        "code-aster-review", "imported_component_mixed_demo"
    ]


def test_engineering_profile_rejects_missing_portable_provenance_file(tmp_path: Path) -> None:
    """Catches a publisher that leaves a review reference dangling after staging."""
    _write_engineering_bundle(tmp_path)

    with pytest.raises(ValueError, match="Referenced bundle file is missing"):
        validate_official_bundle(tmp_path, "engineering-review")


@pytest.mark.parametrize(
    ("mutate", "error"),
    [
        (lambda scene, review: review["provenance"][0]["files"].update(result="C:\\escape.csv"), "non-portable"),
        (lambda scene, review: review["provenance"][0]["files"].update(result="../escape.csv"), "non-portable"),
        (lambda scene, review: scene.update(geometry_assets=[{"id": "mesh", "uri": "geometry/missing.json", "hash": "sha256:x"}]), "missing"),
        (lambda scene, review: scene["result_fields"].__setitem__(-1, {"id": "other", "label": "other", "overlay_id": "overlay:test", "components": ["magnitude"]}), "missing tuyau"),
        (lambda scene, review: review["provenance"][0]["metadata"].update(source="fixture"), "non-fixture"),
        (lambda scene, review: scene.update(diagnostics=[{"severity": "error", "code": "bad"}]), "error diagnostic"),
    ],
)
def test_engineering_profile_rejects_unsafe_or_incomplete_contracts(
    tmp_path: Path,
    mutate,
    error: str,
) -> None:
    """Catches profile validation weakened around portability or engineering proof."""
    _write_engineering_bundle(tmp_path, evidence=True)
    scene, review = _scene(tmp_path), _review(tmp_path)
    mutate(scene, review)
    _save_bundle(tmp_path, scene, review)

    with pytest.raises(ValueError, match=error):
        validate_official_bundle(tmp_path, "engineering-review")


def test_engineering_profile_rejects_tampered_geometry_hash(tmp_path: Path) -> None:
    """Catches geometry JSON changed after its scene manifest was written."""
    _write_engineering_bundle(tmp_path, evidence=True)
    geometry = {"asset_id": "mesh", "format": "point", "bounds": [], "object_ids": [], "generation_config": {}, "hash": "sha256:bad"}
    (tmp_path / "geometry").mkdir()
    (tmp_path / "geometry" / "mesh.json").write_text(json.dumps(geometry), encoding="utf-8")
    scene, review = _scene(tmp_path), _review(tmp_path)
    scene["geometry_assets"] = [{"id": "mesh", "uri": "geometry/mesh.json", "hash": "sha256:bad"}]
    _save_bundle(tmp_path, scene, review)

    with pytest.raises(ValueError, match="Geometry hash"):
        validate_official_bundle(tmp_path, "engineering-review")


@pytest.mark.parametrize("kind", ("missing", "collision", "symlink"))
def test_evidence_staging_rejects_unsafe_or_ambiguous_sources(tmp_path: Path, kind: str) -> None:
    """Catches evidence staging that could publish an untraceable source file."""
    source = tmp_path / "source"
    source.mkdir()
    first = source / "evidence.dat"
    first.write_text("first", encoding="utf-8")
    files = {"study": str(first)}
    if kind == "missing":
        files = {"study": str(source / "missing.dat")}
    elif kind == "collision":
        second = tmp_path / "other" / "evidence.dat"
        second.parent.mkdir()
        second.write_text("second", encoding="utf-8")
        files["result"] = str(second)
    else:
        linked = source / "linked.dat"
        try:
            linked.symlink_to(first)
        except OSError as error:
            pytest.skip(f"symlink creation unavailable: {error.winerror}")
        files = {"study": str(linked)}
    artifact = _artifact_with_files(files)

    with pytest.raises(ValueError, match="missing|collision|symlinks"):
        stage_code_aster_artifact_evidence(artifact, tmp_path / "bundle")


def _write_engineering_bundle(root: Path, *, evidence: bool = False) -> None:
    identity = {
        "schema_id": "tuba.model.v4",
        "compiler_id": "tuba.code_aster.v1",
        "load_case": "Operating",
        "fingerprint": "a" * 64,
    }
    root.mkdir(exist_ok=True)
    if evidence:
        (root / "artifacts").mkdir()
        (root / "artifacts" / "result.csv").write_text("result", encoding="utf-8")
    result_file = root / "artifacts" / "result.csv"
    file_metadata = (
        {"file_sha256": {"result": sha256(result_file.read_bytes()).hexdigest()}, "file_sizes": {"result": result_file.stat().st_size}}
        if evidence
        else {}
    )
    (root / "scene.json").write_text(json.dumps({
        "scene_id": "scene:test", "model_id": "model:test", "geometry_assets": [], "diagnostics": [],
        "layers": [{"id": category, "category": category, "label": category} for category in ("design", "analysis_mesh", "results", "annotations")],
        "result_fields": [{"id": family, "label": family, "overlay_id": "overlay:test", "components": ["magnitude"]} for family in ("stress", "displacement", "reaction", "tuyau")],
        "solver_input_identities": [identity],
    }), encoding="utf-8")
    (root / "review.json").write_text(json.dumps({
        "analysis_status": "solved", "diagnostics": [],
        "provenance": [{"kind": kind, "solver_name": "Code_Aster", "files": {"result": "artifacts/result.csv" if evidence else "artifacts/missing.csv"}, "metadata": {"solver_input_identity": identity, **(file_metadata if kind in {"study", "result_state"} else {})}} for kind in ("study", "analysis_mesh", "result_state")],
    }), encoding="utf-8")


def _artifact_with_files(files: dict[str, str]) -> CodeAsterArtifactImport:
    study = AnalysisStudy(
        id="study:test", model_revision=0, solver_name="Code_Aster", load_case="Operating",
        work_dir="unsafe", input_files=files, mesh_id="mesh:test",
    )
    state = ResultState(
        id="result:test", study_id=study.id, model_revision=0, solver_name="Code_Aster", load_case="Operating",
        mesh_id=study.mesh_id, node_displacements={}, node_reactions={}, element_results={}, files={},
    )
    return CodeAsterArtifactImport(study=study, results=FEAResults("Code_Aster", "Operating"), result_state=state)


def _scene(root: Path) -> dict:
    return json.loads((root / "scene.json").read_text(encoding="utf-8"))


def _review(root: Path) -> dict:
    return json.loads((root / "review.json").read_text(encoding="utf-8"))


def _save_bundle(root: Path, scene: dict, review: dict) -> None:
    for name, value in (("scene.json", scene), ("review.json", review)):
        (root / name).write_text(json.dumps(value), encoding="utf-8")
