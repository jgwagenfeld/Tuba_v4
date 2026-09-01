"""Official viewer publication contracts."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
import subprocess
import sys

import pytest

from scripts import build_pages
from scripts.build_pages import build_examples, validate_official_bundle, write_bundle_catalog
from tuba.analysis import AnalysisRun
from tuba.analysis.code_aster_artifacts import stage_code_aster_artifact_evidence
from tuba.analysis.mesh import AnalysisMesh
from tuba.analysis.provenance import SolverInputIdentity
from tuba.analysis.results import ResultState
from tuba.analysis.study import AnalysisStudy
from tuba.solver.base import FEAResults
from tuba.solver.code_aster_runtime import ATTESTED_CODE_ASTER_FILES


OFFICIAL_BUNDLES = (
    "autorouted-expansion-loop",
    "code-aster-review",
    "elements-supports-review",
    "gmsh-tee-mesh-review",
    "imported_component_mixed_demo",
    "pipe-tee-volume-review",
    "support-rack-review",
)
PAGES_BUNDLES = tuple(bundle for bundle in OFFICIAL_BUNDLES if bundle != "gmsh-tee-mesh-review")


def test_gmsh_mesh_viewer_recipe_builds_an_unsolved_scene() -> None:
    from examples.gmsh_tee_mesh_review import build

    scene = build()

    assert scene.extra["publication_status"] == "mesh_only_unsolved"
    assert not scene.result_fields
    assert any(obj.kind == "analysis_mesh_surface" for obj in scene.objects)
    assert not any(asset.generation_config.get("source") == "tuba.element" for asset in scene.geometry_assets)
    assert not any(layer.category == "results" for layer in scene.layers)


def _assert_thermal_clearance_clash(scene: dict) -> None:
    """Pin the published clash to the one state the publication gate allows.

    The autorouted line clears its cable tray cold and only reaches it once it
    expands, so the margin is millimetres. A re-solve that shifts the
    displacement field could turn this into a hard clash, which
    ``_reject_error_diagnostics`` would refuse to publish, or into no clash at
    all, which would silently drop the capability from the gallery.
    """
    markers = [obj for obj in scene["objects"] if obj["kind"] == "clash_marker"]
    assert markers, "Autorouted gallery must publish operating-state clash markers."
    for marker in markers:
        metadata = marker["metadata"]
        clash = metadata["clash_metadata"]
        assert metadata["severity"] == "operating_only_clearance"
        assert clash["introduced_by_deformation"] is True
        # Magnitudes, not just flags. The flags above are fixed by the authored
        # geometry and would still hold if the solve moved the line ten times
        # as far, or barely at all; these bounds are what a re-solve can break.
        # Cold clear of the 144.45 mm envelope, hot inside it, by millimetres.
        assert clash["cold_distance_m"] > 0.1445, "Cold gap must clear the clearance envelope."
        assert 0.130 < clash["operating_distance_m"] < 0.1445, "Hot gap must fall inside it."
        assert 0.002 < marker["metadata"]["penetration_m"] < 0.020, (
            "Published penetration left its expected millimetre band; re-check the tray "
            "placement against the current displacement field before republishing."
        )
    assert all(issue["severity"] != "error" for issue in scene["issues"])


def test_pages_catalog_contains_the_validated_official_bundles(tmp_path: Path) -> None:
    """Catches a publisher that omits an official example or its catalog."""
    bundle_ids = build_examples(tmp_path, audience="pages")

    write_bundle_catalog(tmp_path, bundle_ids)

    assert bundle_ids == PAGES_BUNDLES
    catalog = json.loads((tmp_path / "bundles.json").read_text(encoding="utf-8"))
    assert [entry["id"] for entry in catalog] == list(bundle_ids)
    # A card cannot be published without the narrative it renders.
    assert all(
        entry["title"] and entry["question"] and entry["summary"] and entry["evidence"]
        for entry in catalog
    )

    engineering = json.loads((tmp_path / "code-aster-review" / "scene.json").read_text(encoding="utf-8"))
    assert len(engineering["result_fields"]) == 5
    assert {
        next(overlay for overlay in engineering["overlays"] if overlay["id"] == field["overlay_id"])["data"]["result_type"]
        for field in engineering["result_fields"]
    } == {"stress", "displacement", "reaction_force", "reaction_moment", "tuyau_subpoints"}
    assert {layer["category"] for layer in engineering["layers"]} == {
        "design", "analysis_mesh", "results", "annotations"
    }
    for bundle_id in ("autorouted-expansion-loop", "support-rack-review"):
        scene = json.loads((tmp_path / bundle_id / "scene.json").read_text(encoding="utf-8"))
        review = json.loads((tmp_path / bundle_id / "review.json").read_text(encoding="utf-8"))
        assert len(scene["result_fields"]) == 5
        # Both galleries carry an optional ASME B31.3 layer, which is what
        # 'compliance_complete' records. It is not a higher grade of evidence
        # than 'solved' -- the solver evidence is identical either way.
        assert review["analysis_status"] == "compliance_complete"
        compliance = review["tables"]["code_compliance"]
        assert compliance["rows"]
        assert all(
            row["sustained_pass"] is True and row["expansion_pass"] is True
            for row in compliance["rows"]
        )

    autorouted = json.loads(
        (tmp_path / "autorouted-expansion-loop" / "scene.json").read_text(encoding="utf-8")
    )
    assert autorouted["route_reviews"]
    _assert_thermal_clearance_clash(autorouted)
    assert {"physical_envelope", "cost_heatmap", "quantity_summary"} <= {
        overlay["kind"] for overlay in autorouted["overlays"]
    }
    rack = json.loads((tmp_path / "support-rack-review" / "scene.json").read_text(encoding="utf-8"))
    assert any(overlay["kind"] == "rack_assembly" for overlay in rack["overlays"])
    assert any(overlay["kind"] == "load_path" for overlay in rack["overlays"])
    assert any(overlay["kind"] == "rule_violation" for overlay in rack["overlays"])
    assert any(obj["kind"] == "rule_marker" for obj in rack["objects"])
    tee = json.loads((tmp_path / "pipe-tee-volume-review" / "scene.json").read_text(encoding="utf-8"))
    tee_fields = {
        next(overlay for overlay in tee["overlays"] if overlay["id"] == field["overlay_id"])["data"]["result_type"]
        for field in tee["result_fields"]
    }
    assert tee_fields == {"stress", "displacement", "reaction_force", "reaction_moment"}
    assert any(obj["kind"] == "analysis_mesh_surface" for obj in tee["objects"])
    assert any(obj["kind"] == "volume_stress_field" for obj in tee["objects"])
    assert "visualization_only_not_asme_code_stress" in json.dumps(tee)

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
    assert {"stdout", "stderr"}.isdisjoint(result_provenance["files"])
    assert result_provenance["files"]["execution"] == "artifacts/study_execution.json"
    assert result_provenance["files"]["mess"] == "artifacts/study.mess"
    assert (tmp_path / "code-aster-review" / result_provenance["files"]["execution"]).is_file()
    assert {
        path.name for path in (tmp_path / "code-aster-review" / "artifacts").iterdir()
        if path.is_file()
    } == {*ATTESTED_CODE_ASTER_FILES, "study_execution.json"}
    assert result_provenance["metadata"]["file_sha256"]["rmed"]
    assert result_provenance["metadata"]["file_sizes"]["rmed"] > 0
    assert all(
        ".log" not in path.read_text(encoding="utf-8")
        for path in (tmp_path / "code-aster-review").rglob("*.json")
    )


def test_examples_cli_runs_directly_from_the_repository_root(tmp_path: Path) -> None:
    """Catches the script-only import path that breaks the documented CLI."""
    completed = subprocess.run(
        [sys.executable, "scripts/build_pages.py", "examples", "--output", str(tmp_path), "--audience", "pages"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert [
        entry["id"]
        for entry in json.loads((tmp_path / "bundles.json").read_text(encoding="utf-8"))
    ] == [*PAGES_BUNDLES]


def test_official_bundles_are_generated_from_source_only(tmp_path: Path) -> None:
    """Keep generated examples out of Git while retaining the smoke fixture."""
    root = Path(__file__).resolve().parents[1]
    official = OFFICIAL_BUNDLES
    tracked = set(
        subprocess.check_output(
            ["git", "ls-files", "--", "viewer/public"], cwd=root, text=True
        ).splitlines()
    )

    assert not any(
        path.startswith(f"viewer/public/{bundle_id}/")
        for bundle_id in official
        for path in tracked
    )
    assert "viewer/public/bundles.json" not in tracked
    assert "viewer/public/smoke-scene/scene.json" in tracked
    for bundle_id in official:
        assert subprocess.run(
            ["git", "check-ignore", "--no-index", f"viewer/public/{bundle_id}/scene.json"],
            cwd=root,
            capture_output=True,
        ).returncode == 0
    assert subprocess.run(
        ["git", "check-ignore", "--no-index", "viewer/public/bundles.json"],
        cwd=root,
        capture_output=True,
    ).returncode == 0
    assert subprocess.run(
        ["git", "check-ignore", "--no-index", "viewer/public/smoke-scene/scene.json"],
        cwd=root,
        capture_output=True,
    ).returncode == 1

    bundle_ids = build_examples(tmp_path, audience="dev")

    assert bundle_ids == official
    assert sorted(path.name for path in tmp_path.iterdir() if path.is_dir()) == sorted(official)


@pytest.mark.parametrize(
    "artifact_root",
    [
        Path("notebooks/code_aster_results/autorouted_expansion_hot"),
        Path("notebooks/code_aster_results/support_rack_operating"),
        Path("notebooks/code_aster_results/tee_volume_operating"),
        Path("notebooks/code_aster_results/viz_gallery_operating"),
    ],
)
def test_committed_gallery_artifact_bytes_match_the_execution_attestation(
    artifact_root: Path,
) -> None:
    root = Path(__file__).resolve().parents[1]
    attestation = json.loads((root / artifact_root / "study_execution.json").read_text(encoding="utf-8"))

    for filename, expected in attestation["artifacts"].items():
        path = (artifact_root / filename).as_posix()
        content = subprocess.check_output(["git", "show", f":{path}"], cwd=root)
        assert len(content) == expected["size_bytes"], filename
        assert sha256(content).hexdigest() == expected["sha256"], filename


def test_evidence_staging_requires_a_validated_solve_attestation(tmp_path: Path) -> None:
    """Catches official publication synthesizing hashes for unattested files."""
    source = tmp_path / "source"
    source.mkdir()
    (source / "study.comm").write_text("comm", encoding="utf-8")
    artifact = _artifact_with_files({"comm": str(source / "study.comm")}, work_dir=source)

    with pytest.raises(ValueError, match="attestation"):
        stage_code_aster_artifact_evidence(artifact, tmp_path / "bundle")


def test_engineering_profile_rejects_missing_portable_provenance_file(tmp_path: Path) -> None:
    """Catches a publisher that leaves a review reference dangling after staging."""
    _write_engineering_bundle(tmp_path, evidence=True)
    scene, review = _scene(tmp_path), _review(tmp_path)
    next(
        record for record in review["provenance"] if record["kind"] == "analysis_mesh"
    )["files"]["missing"] = "artifacts/missing.csv"
    _save_bundle(tmp_path, scene, review)

    with pytest.raises(ValueError, match="Referenced bundle file is missing"):
        validate_official_bundle(tmp_path, "engineering-review")


@pytest.mark.parametrize(
    ("mutate", "error"),
    [
        (lambda scene, review: review["provenance"][0]["files"].update(result="C:\\escape.csv"), "non-portable"),
        (lambda scene, review: review["provenance"][0]["files"].update(result="../escape.csv"), "non-portable"),
        (lambda scene, review: scene.update(geometry_assets=[{"id": "mesh", "uri": "geometry/missing.json", "hash": "sha256:x"}]), "missing"),
        (lambda scene, review: scene["result_fields"].__setitem__(-1, {"id": "other", "label": "other", "overlay_id": "overlay:test", "components": ["magnitude"]}), "result-field"),
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


def test_engineering_profile_requires_the_exact_attested_artifact_inventory(tmp_path: Path) -> None:
    """Catches an execution envelope that omits required study.mess evidence."""
    _write_engineering_bundle(tmp_path, evidence=True)
    execution_path = tmp_path / "artifacts" / "study_execution.json"
    execution = json.loads(execution_path.read_text(encoding="utf-8"))
    execution["artifacts"].pop("study.mess")
    execution_path.write_text(json.dumps(execution), encoding="utf-8")

    with pytest.raises(ValueError, match="artifact inventory"):
        validate_official_bundle(tmp_path, "engineering-review")


def test_engineering_profile_cross_checks_attestation_identity(tmp_path: Path) -> None:
    """Catches a valid-looking solve envelope detached from scene provenance."""
    _write_engineering_bundle(tmp_path, evidence=True)
    execution_path = tmp_path / "artifacts" / "study_execution.json"
    execution = json.loads(execution_path.read_text(encoding="utf-8"))
    execution["solver_input_identity"]["fingerprint"] = "b" * 64
    execution_path.write_text(json.dumps(execution), encoding="utf-8")

    with pytest.raises(ValueError, match="identity"):
        validate_official_bundle(tmp_path, "engineering-review")


@pytest.mark.parametrize(
    ("relative_path", "contents"),
    [
        ("artifacts/hidden.json", '{"source": "C:\\\\Users\\\\alice\\\\study.rmed"}'),
        ("index.html", '<html><body data-source="C:\\\\Users\\\\alice\\\\study.rmed"></body></html>'),
    ],
)
def test_engineering_profile_scans_artifact_json_and_html_for_unsafe_paths(
    tmp_path: Path,
    relative_path: str,
    contents: str,
) -> None:
    """Catches unreferenced machine paths hidden outside scene/review JSON."""
    _write_engineering_bundle(tmp_path, evidence=True)
    path = tmp_path / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")

    with pytest.raises(ValueError, match="non-portable"):
        validate_official_bundle(tmp_path, "engineering-review")


@pytest.mark.parametrize("kind", ("missing", "collision", "symlink"))
def test_evidence_staging_rejects_unsafe_or_ambiguous_sources(tmp_path: Path, kind: str) -> None:
    """Catches evidence staging that could publish an untraceable source file."""
    source = tmp_path / "source"
    source.mkdir()
    first = source / "study.comm"
    first.write_text("first", encoding="utf-8")
    files = {"comm": str(first)}
    if kind == "missing":
        files = {"comm": str(source / "missing" / "study.comm")}
    elif kind == "collision":
        second = tmp_path / "other" / "study.comm"
        second.parent.mkdir()
        second.write_text("second", encoding="utf-8")
        files["other_comm"] = str(second)
    else:
        linked = source / "linked" / "study.comm"
        linked.parent.mkdir()
        try:
            linked.symlink_to(first)
        except OSError as error:
            pytest.skip(f"symlink creation unavailable: {error.winerror}")
        files = {"comm": str(linked)}
    artifact = _artifact_with_files(files, work_dir=source, attested=True)

    with pytest.raises(ValueError, match="missing|collision|symlinks"):
        stage_code_aster_artifact_evidence(artifact, tmp_path / "bundle")


def test_evidence_staging_resolves_committed_windows_relative_paths_from_the_evidence_root(tmp_path: Path) -> None:
    """Catches POSIX publication treating a committed Windows path as one filename."""
    evidence_root = tmp_path / "evidence"
    evidence_root.mkdir()
    (evidence_root / "study.comm").write_text("comm", encoding="utf-8")
    (evidence_root / "inputs").mkdir()
    (evidence_root / "inputs" / "study.comm").write_text("comm", encoding="utf-8")
    artifact = _artifact_with_files(
        {"comm": "inputs\\study.comm"}, work_dir=evidence_root, attested=True
    )

    staged = stage_code_aster_artifact_evidence(artifact, tmp_path / "bundle")

    assert staged.study.input_files["comm"] == "artifacts/study.comm"


def test_evidence_staging_rejects_a_symlinked_parent_directory(tmp_path: Path) -> None:
    """Catches a safe terminal file reached through a symlinked evidence directory."""
    real = tmp_path / "real"
    real.mkdir()
    (real / "study.comm").write_text("comm", encoding="utf-8")
    linked = tmp_path / "linked"
    try:
        linked.symlink_to(real, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"symlink creation unavailable: {error.winerror}")
    artifact = _artifact_with_files(
        {"comm": str(linked / "study.comm")}, work_dir=real, attested=True
    )

    with pytest.raises(ValueError, match="symlinks"):
        stage_code_aster_artifact_evidence(artifact, tmp_path / "bundle")


@pytest.mark.parametrize("unsafe", ("\\\\server\\share\\file", "/tmp/file"))
def test_engineering_profile_rejects_unc_and_posix_absolute_references(tmp_path: Path, unsafe: str) -> None:
    """Catches portable profiles accepting absolute paths outside the bundle."""
    _write_engineering_bundle(tmp_path, evidence=True)
    scene, review = _scene(tmp_path), _review(tmp_path)
    review["provenance"][0]["files"]["result"] = unsafe
    _save_bundle(tmp_path, scene, review)

    with pytest.raises(ValueError, match="non-portable"):
        validate_official_bundle(tmp_path, "engineering-review")


@pytest.mark.parametrize("unsafe", ("C:\\escaped", "../escaped"))
def test_geometry_payload_rejects_rehashed_unsafe_references(tmp_path: Path, unsafe: str) -> None:
    """Catches payload-only paths that would survive a valid geometry hash."""
    _write_engineering_bundle(tmp_path, evidence=True)
    payload = {
        "asset_id": "mesh", "format": "point", "bounds": [], "object_ids": [],
        "generation_config": {"source_path": unsafe},
    }
    payload["hash"] = _geometry_hash(payload)
    (tmp_path / "geometry").mkdir()
    (tmp_path / "geometry" / "mesh.json").write_text(json.dumps(payload), encoding="utf-8")
    scene, review = _scene(tmp_path), _review(tmp_path)
    scene["geometry_assets"] = [{"id": "mesh", "uri": "geometry/mesh.json", "hash": payload["hash"]}]
    _save_bundle(tmp_path, scene, review)

    with pytest.raises(ValueError, match="non-portable"):
        validate_official_bundle(tmp_path, "engineering-review")


def test_geometry_payload_rejects_an_error_diagnostic_after_rehash(tmp_path: Path) -> None:
    """Catches payload diagnostics hidden behind a valid content hash."""
    _write_engineering_bundle(tmp_path, evidence=True)
    payload = {
        "asset_id": "mesh", "format": "point", "bounds": [], "object_ids": [],
        "generation_config": {}, "diagnostics": [{"severity": "error", "code": "payload.bad"}],
    }
    payload["hash"] = _geometry_hash(payload)
    (tmp_path / "geometry").mkdir()
    (tmp_path / "geometry" / "mesh.json").write_text(json.dumps(payload), encoding="utf-8")
    scene, review = _scene(tmp_path), _review(tmp_path)
    scene["geometry_assets"] = [{"id": "mesh", "uri": "geometry/mesh.json", "hash": payload["hash"]}]
    _save_bundle(tmp_path, scene, review)

    with pytest.raises(ValueError, match="error diagnostic"):
        validate_official_bundle(tmp_path, "engineering-review")


def test_engineering_profile_requires_all_three_record_identities(tmp_path: Path) -> None:
    """Catches a result-state provenance record without a real solver identity."""
    _write_engineering_bundle(tmp_path, evidence=True)
    scene, review = _scene(tmp_path), _review(tmp_path)
    next(record for record in review["provenance"] if record["kind"] == "result_state")["metadata"].pop("solver_input_identity")
    _save_bundle(tmp_path, scene, review)

    with pytest.raises(ValueError, match="result_state identity"):
        validate_official_bundle(tmp_path, "engineering-review")


def test_engineering_profile_requires_structurally_matching_identities(tmp_path: Path) -> None:
    """Catches equal fingerprints with conflicting solver-input fields."""
    _write_engineering_bundle(tmp_path, evidence=True)
    scene, review = _scene(tmp_path), _review(tmp_path)
    next(record for record in review["provenance"] if record["kind"] == "analysis_mesh")["metadata"]["solver_input_identity"]["load_case"] = "Cold"
    _save_bundle(tmp_path, scene, review)

    with pytest.raises(ValueError, match="matching non-null"):
        validate_official_bundle(tmp_path, "engineering-review")


def test_engineering_profile_requires_scene_identity_to_match_provenance(tmp_path: Path) -> None:
    """Catches a scene identity that diverged from its reviewed solver records."""
    _write_engineering_bundle(tmp_path, evidence=True)
    scene, review = _scene(tmp_path), _review(tmp_path)
    scene["solver_input_identities"][0]["compiler_id"] = "other"
    _save_bundle(tmp_path, scene, review)

    with pytest.raises(ValueError, match="scene identity"):
        validate_official_bundle(tmp_path, "engineering-review")


def test_engineering_profile_rejects_deceptive_result_labels_without_matching_overlays(tmp_path: Path) -> None:
    """Catches family names present only in labels rather than solver overlays."""
    _write_engineering_bundle(tmp_path, evidence=True)
    scene, review = _scene(tmp_path), _review(tmp_path)
    scene["overlays"][-1]["data"]["result_type"] = "not_tuyau"
    _save_bundle(tmp_path, scene, review)

    with pytest.raises(ValueError, match="result-field"):
        validate_official_bundle(tmp_path, "engineering-review")


def test_examples_main_does_not_create_or_overwrite_catalog_when_validation_fails(tmp_path: Path, monkeypatch) -> None:
    """Catches the CLI writing a catalog after strict bundle validation fails."""
    from scripts.official_gallery import OfficialGallery

    def produce_invalid(destination: Path, _artifacts: Path | None) -> None:
        destination.mkdir(parents=True)
        (destination / "scene.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        build_pages,
        "OFFICIAL_GALLERIES",
        (
            OfficialGallery(
                id="invalid",
                audiences=frozenset({"pages"}),
                profile="engineering-review",
                bundle_producer=produce_invalid,
                title="Invalid",
                question="Does a broken bundle stop the publisher?",
                summary="A deliberately invalid bundle used to prove the gate holds.",
            ),
        ),
    )
    catalog = tmp_path / "bundles.json"
    catalog.write_text('["previous"]\n', encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        ["build_pages.py", "examples", "--output", str(tmp_path), "--audience", "pages"],
    )

    with pytest.raises(ValueError):
        build_pages.main()

    assert catalog.read_text(encoding="utf-8") == '["previous"]\n'


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
        for filename in ATTESTED_CODE_ASTER_FILES:
            contents = (
                "Version 18.0.12"
                if filename == "study.mess"
                else "{}" if filename.endswith(".json") else filename
            )
            (root / "artifacts" / filename).write_text(contents, encoding="utf-8")
        _write_study_manifest(root / "artifacts" / "study_manifest.json", identity)
        artifacts = {
            filename: {
                "sha256": sha256((root / "artifacts" / filename).read_bytes()).hexdigest(),
                "size_bytes": (root / "artifacts" / filename).stat().st_size,
            }
            for filename in ATTESTED_CODE_ASTER_FILES
        }
        (root / "artifacts" / "study_execution.json").write_text(json.dumps({
            "schema_version": "tuba.code_aster_execution.v1",
            "solver_name": "Code_Aster",
            "solver_version": "18.0.12",
            "execution_method": "wsl",
            "solved_at": "2026-07-29T12:00:00Z",
            "solver_input_identity": identity,
            "artifacts": artifacts,
        }), encoding="utf-8")
    result_files = (
        {
            "execution": "artifacts/study_execution.json",
            "mess": "artifacts/study.mess",
            "rmed": "artifacts/study.rmed",
            "depl": "artifacts/study_depl.csv",
            "effo": "artifacts/study_effo.csv",
            "reac": "artifacts/study_reac.csv",
            "sieq": "artifacts/study_sieq.csv",
        }
        if evidence
        else {"result": "artifacts/missing.csv"}
    )
    file_metadata = {}
    if evidence:
        file_metadata = {
            "file_sha256": {
                role: sha256((root / uri).read_bytes()).hexdigest()
                for role, uri in result_files.items()
            },
            "file_sizes": {
                role: (root / uri).stat().st_size
                for role, uri in result_files.items()
            },
        }
    (root / "scene.json").write_text(json.dumps({
        "scene_id": "scene:test", "model_id": "model:test", "geometry_assets": [], "diagnostics": [],
        "layers": [{"id": category, "category": category, "label": category} for category in ("design", "analysis_mesh", "results", "annotations")],
        "overlays": [
            {
                "id": f"overlay:solver_result:{family}:result_state:Operating",
                "kind": "solver_result",
                "data": {"result_type": family, "result_state_id": "result_state:Operating", "load_case": "Operating", "values": {"N0": 1.0}},
            }
            for family in ("stress", "displacement", "reaction_force", "reaction_moment", "tuyau_subpoints")
        ],
        "result_fields": [
            {
                "id": f"field:solver_result:{family}:result_state:Operating",
                "label": family,
                "overlay_id": f"overlay:solver_result:{family}:result_state:Operating",
                "result_state_id": "result_state:Operating",
                "load_case": "Operating",
                "components": ["magnitude"],
            }
            for family in ("stress", "displacement", "reaction_force", "reaction_moment", "tuyau_subpoints")
        ],
        "solver_input_identities": [identity],
    }), encoding="utf-8")
    (root / "review.json").write_text(json.dumps({
        "analysis_status": "solved", "diagnostics": [],
        "provenance": [{"kind": kind, "solver_name": "Code_Aster", "files": result_files, "metadata": {"solver_input_identity": identity, **(file_metadata if kind in {"study", "result_state"} else {})}} for kind in ("study", "analysis_mesh", "result_state")],
    }), encoding="utf-8")


def _artifact_with_files(
    files: dict[str, str],
    *,
    work_dir: Path | str = "unsafe",
    attested: bool = False,
) -> AnalysisRun:
    identity = SolverInputIdentity(
        schema_id="tuba.model.v4",
        compiler_id="tuba.code_aster.v1",
        load_case="Operating",
        fingerprint="a" * 64,
    )
    study_files = dict(files)
    result_files: dict[str, str] = {}
    metadata = {}
    analysis_mesh = None
    if attested:
        root = Path(work_dir)
        root.mkdir(parents=True, exist_ok=True)
        for filename in ATTESTED_CODE_ASTER_FILES:
            path = root / filename
            if not path.exists():
                contents = (
                    "Version 18.0.12"
                    if filename == "study.mess"
                    else "{}" if filename.endswith(".json") else filename
                )
                path.write_text(contents, encoding="utf-8")
        for value in files.values():
            source = Path(value.replace("\\", "/"))
            if not source.is_absolute():
                source = root / source
            if source.is_file() and source.name in ATTESTED_CODE_ASTER_FILES:
                target = root / source.name
                if source.resolve() != target.resolve():
                    target.write_bytes(source.read_bytes())
        _write_study_manifest(root / "study_manifest.json", identity.to_dict())
        defaults = {
            role: str(root / filename)
            for role, filename in (
                ("mail", "study.mail"),
                ("comm", "study.comm"),
                ("export", "study.export"),
                ("manifest", "study_manifest.json"),
                ("sidecar", "study_tuba_fem.json"),
            )
        }
        study_files = {**defaults, **files}
        result_files = {
            role: str(root / filename)
            for role, filename in (
                ("execution", "study_execution.json"),
                ("mess", "study.mess"),
                ("rmed", "study.rmed"),
                ("depl", "study_depl.csv"),
                ("effo", "study_effo.csv"),
                ("reac", "study_reac.csv"),
                ("sieq", "study_sieq.csv"),
            )
        }
        artifacts = {
            filename: {
                "sha256": sha256((root / filename).read_bytes()).hexdigest(),
                "size_bytes": (root / filename).stat().st_size,
            }
            for filename in ATTESTED_CODE_ASTER_FILES
        }
        envelope = {
            "schema_version": "tuba.code_aster_execution.v1",
            "solver_name": "Code_Aster",
            "solver_version": "18.0.12",
            "execution_method": "wsl",
            "solved_at": "2026-07-29T12:00:00Z",
            "solver_input_identity": identity.to_dict(),
            "artifacts": artifacts,
        }
        (root / "study_execution.json").write_text(json.dumps(envelope), encoding="utf-8")
        metadata = {"solve_attestation": envelope}
        analysis_mesh = AnalysisMesh(
            id="mesh:test", model_revision=0, solver_name="Code_Aster",
            nodes={}, elements={}, groups={}, node_sources={}, element_sources={},
            files={"mail": study_files["mail"]}, solver_input_identity=identity,
        )
    study = AnalysisStudy(
        id="study:test", model_revision=0, solver_name="Code_Aster", load_case="Operating",
        work_dir=str(work_dir), input_files=study_files, mesh_id="mesh:test",
        solver_input_identity=identity if attested else None,
    )
    state = ResultState(
        id="result:test", study_id=study.id, model_revision=0, solver_name="Code_Aster", load_case="Operating",
        mesh_id=study.mesh_id, node_displacements={}, node_reactions={}, element_results={}, files=result_files,
        metadata=metadata, solver_input_identity=identity if attested else None,
    )
    return AnalysisRun(
        study=study, analysis_mesh=analysis_mesh,
        results=FEAResults("Code_Aster", "Operating"), result_state=state,
    )


def _scene(root: Path) -> dict:
    return json.loads((root / "scene.json").read_text(encoding="utf-8"))


def _review(root: Path) -> dict:
    return json.loads((root / "review.json").read_text(encoding="utf-8"))


def _save_bundle(root: Path, scene: dict, review: dict) -> None:
    for name, value in (("scene.json", scene), ("review.json", review)):
        (root / name).write_text(json.dumps(value), encoding="utf-8")


def _geometry_hash(payload: dict) -> str:
    value = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{sha256(value).hexdigest()}"


def _write_study_manifest(path: Path, identity: dict[str, str]) -> None:
    path.write_text(
        json.dumps({"study": {"metadata": {}, "solver_input_identity": identity}}),
        encoding="utf-8",
    )
