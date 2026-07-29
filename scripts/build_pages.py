"""Build the two portable, validated official viewer example bundles."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from examples.code_aster_artifact_review import run_example
from examples.imported_component_mixed_system import run_demo
from scripts import prepare_release
from tuba.solver.code_aster_runtime import load_code_aster_execution_attestation


_WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:[\\/]")
_UNC = re.compile(r"^\\\\")
_TRAVERSAL = re.compile(r"(?:^|[\\/])\.\.(?:[\\/]|$)")
_IDENTITY_FIELDS = ("fingerprint", "load_case", "schema_id", "compiler_id")


def _build_code_aster_review(destination: Path, artifacts: Path | None) -> None:
    with TemporaryDirectory(prefix="tuba-official-code-aster-") as temporary:
        produced = Path(temporary) / "code-aster-review"
        run_example(produced, artifact_dir=artifacts)
        _replace_tree(produced / "review_scene", destination)


def _build_model_review(destination: Path, _artifacts: Path | None) -> None:
    with TemporaryDirectory(prefix="tuba-official-model-review-") as temporary:
        produced = Path(temporary) / "imported-component"
        run_demo(
            Path("examples/assets/imported_component_demo.stl"),
            output_root=produced,
            export_study=False,
        )
        _replace_tree(produced / "review_scene", destination)


OFFICIAL_EXAMPLES: tuple[tuple[str, Callable[[Path, Path | None], None], frozenset[str], str], ...] = (
    ("code-aster-review", _build_code_aster_review, frozenset({"dev", "pages"}), "engineering-review"),
    ("imported_component_mixed_demo", _build_model_review, frozenset({"dev", "pages"}), "model-review"),
)
PAGES_BUNDLE_IDS = ("code-aster-review", "imported_component_mixed_demo")
_PAGES_REQUIRED_FILES = frozenset(
    {
        "index.html",
        "setup.html",
        "tutorial.html",
        "reference/public-api.html",
        "architecture/visualization.html",
        "commands.html",
        "overview.html",
        "viewer/index.html",
        "viewer/bundles.json",
        "viewer/code-aster-review/scene.json",
        "viewer/imported_component_mixed_demo/scene.json",
        "notebooks/10_interactive_postprocessor.ipynb",
        ".nojekyll",
    }
)


def assemble_pages(output: Path, *, code_aster_artifacts: Path | None = None) -> Path:
    """Build and atomically replace one complete deployable Pages tree."""
    output = Path(output).resolve()
    _validate_pages_output(output)
    if output.exists() and not output.is_dir():
        raise ValueError(f"Pages output must be a directory: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)

    prepare_release.main()
    uv = shutil.which("uv") or "uv"
    subprocess.run(
        [uv, "run", "--group", "docs", "zensical", "build", "--clean", "--strict"],
        cwd=ROOT,
        check=True,
    )

    with TemporaryDirectory(prefix=f".{output.name}.staging-", dir=output.parent) as temporary:
        staged = Path(temporary)
        shutil.copytree(ROOT / ".build" / "zensical-site", staged, dirs_exist_ok=True)
        viewer_root = staged / "viewer"
        shutil.copytree(ROOT / "tuba" / "visualization" / "_viewer", viewer_root)
        bundle_ids = build_examples(
            viewer_root,
            audience="pages",
            code_aster_artifacts=code_aster_artifacts,
        )
        write_bundle_catalog(viewer_root, bundle_ids)

        notebooks = staged / "notebooks"
        notebooks.mkdir()
        shutil.copy2(
            ROOT / "notebooks" / "10_interactive_postprocessor.ipynb",
            notebooks / "10_interactive_postprocessor.ipynb",
        )
        (staged / ".nojekyll").touch()
        _write_redirect(staged / "commands.html", "reference/index.html")
        _write_redirect(staged / "overview.html", "architecture/index.html")
        validate_pages_tree(staged)
        _replace_pages_output(staged, output)
    return output


def validate_pages_tree(root: Path) -> None:
    """Reject incomplete, over-cataloged, or package-contaminating Pages output."""
    files = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }
    missing = sorted(_PAGES_REQUIRED_FILES - files)
    if missing:
        raise ValueError(f"Pages tree is incomplete; missing: {', '.join(missing)}")

    catalog = json.loads((root / "viewer" / "bundles.json").read_text(encoding="utf-8"))
    if catalog != list(PAGES_BUNDLE_IDS):
        raise ValueError(f"Pages catalog must contain exactly {list(PAGES_BUNDLE_IDS)!r}.")
    bundle_directories = sorted(
        path.name
        for path in (root / "viewer").iterdir()
        if path.is_dir() and path.name != "assets"
    )
    if bundle_directories != list(PAGES_BUNDLE_IDS):
        raise ValueError("Pages viewer directories must match its official catalog exactly.")

    package_catalog = json.loads(
        (ROOT / "tuba" / "visualization" / "_viewer" / "bundles.json").read_text(encoding="utf-8")
    )
    if package_catalog != []:
        raise ValueError("The packaged viewer shell catalog must remain empty.")


def _validate_pages_output(output: Path) -> None:
    protected = {
        ROOT.resolve(),
        Path.home().resolve(),
        Path(output.anchor).resolve(),
        (ROOT / "docs" / "content").resolve(),
        (ROOT / "viewer" / "public").resolve(),
    }
    if output in protected:
        raise ValueError(f"Refusing to replace protected Pages output: {output}")


def _write_redirect(path: Path, target: str) -> None:
    path.write_text(
        "<!doctype html>\n"
        '<html lang="en"><head>\n'
        f'<meta http-equiv="refresh" content="0; url={target}">\n'
        f'<link rel="canonical" href="{target}">\n'
        f'<title>Redirecting</title></head><body><a href="{target}">Continue</a></body></html>\n',
        encoding="utf-8",
    )


def _replace_pages_output(staged: Path, output: Path) -> None:
    if not output.exists():
        os.replace(staged, output)
        return
    with TemporaryDirectory(prefix=f".{output.name}.backup-", dir=output.parent) as reserved:
        backup = Path(reserved)
        backup.rmdir()
        os.replace(output, backup)
        try:
            os.replace(staged, output)
        except BaseException:
            os.replace(backup, output)
            raise
        shutil.rmtree(backup)


def build_examples(
    output: Path,
    *,
    audience: str,
    code_aster_artifacts: Path | None = None,
) -> tuple[str, ...]:
    """Materialize only catalog entries allowed for ``audience`` and validate them."""
    if audience not in {"dev", "pages"}:
        raise ValueError("audience must be 'dev' or 'pages'.")
    output.mkdir(parents=True, exist_ok=True)
    artifact_dir = code_aster_artifacts or ROOT / "notebooks" / "code_aster_results" / "viz_gallery_operating"
    bundle_ids: list[str] = []
    for bundle_id, producer, audiences, profile in OFFICIAL_EXAMPLES:
        if audience not in audiences:
            continue
        destination = output / bundle_id
        producer(destination, artifact_dir)
        validate_official_bundle(destination, profile)
        bundle_ids.append(bundle_id)
    return tuple(sorted(bundle_ids))


def write_bundle_catalog(viewer_root: Path, bundle_ids: tuple[str, ...]) -> Path:
    """Write the viewer's deliberately small official-bundle catalog."""
    target = viewer_root / "bundles.json"
    target.write_text(json.dumps(list(bundle_ids), indent=2) + "\n", encoding="utf-8")
    return target


def validate_official_bundle(root: Path, profile: str) -> None:
    """Reject a bundle that is not portable and complete for its official profile."""
    if profile not in {"engineering-review", "model-review"}:
        raise ValueError(f"Unknown official profile {profile!r}.")
    scene = _read_json(root / "scene.json")
    _reject_unsafe_references(scene)
    _validate_geometry(root, scene)
    _reject_error_diagnostics(scene)

    if profile == "model-review":
        if scene.get("result_fields"):
            raise ValueError("Model-review bundles must not contain solver result fields.")
        diagnostics = scene.get("diagnostics", [])
        if not any(
            entry.get("code") == "publication.model_review.no_solver_results"
            for entry in diagnostics
            if isinstance(entry, dict)
        ) or "no solver results" not in json.dumps(scene).lower():
            raise ValueError("Model-review bundles must explicitly state that they have no solver results.")
        if (root / "review.json").exists():
            raise ValueError("Model-review bundles must not publish an engineering review.")
        return

    review = _read_json(root / "review.json")
    _reject_unsafe_references(review)
    _reject_error_diagnostics(review)
    if review.get("analysis_status") != "solved":
        raise ValueError("Engineering-review bundles require analysis_status == 'solved'.")
    if {layer.get("category") for layer in scene.get("layers", [])} != {
        "design", "analysis_mesh", "results", "annotations"
    }:
        raise ValueError("Engineering-review bundles require all four layer categories.")
    _validate_engineering_result_fields(scene)
    identity = _validate_engineering_provenance(scene, review)
    _validate_execution_attestation(root, identity)
    _validate_portable_provenance_files(root, review)
    _validate_embedded_portability(root)


def _replace_tree(source: Path, destination: Path) -> None:
    if not source.is_dir():
        raise ValueError(f"Producer did not create a review scene: {source}")
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"Required official bundle file is missing: {path.name}.")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Official bundle JSON must be an object: {path.name}.")
    return data


def _validate_geometry(root: Path, scene: dict[str, Any]) -> None:
    for asset in scene.get("geometry_assets", []):
        if not isinstance(asset, dict) or not isinstance(asset.get("uri"), str):
            raise ValueError("Geometry asset is missing its URI.")
        payload_path = _bundle_path(root, asset["uri"])
        payload = _read_json(payload_path)
        _reject_unsafe_references(payload)
        _reject_error_diagnostics(payload)
        expected = _geometry_hash({key: value for key, value in payload.items() if key != "hash"})
        if payload.get("hash") != expected or asset.get("hash") != expected:
            raise ValueError(f"Geometry hash does not match payload for {asset.get('id', '<unknown>')!r}.")


def _validate_engineering_result_fields(scene: dict[str, Any]) -> None:
    fields = scene.get("result_fields", [])
    overlays = scene.get("overlays", [])
    expected = {
        "stress": "solver_result",
        "displacement": "solver_result",
        "reaction": "solver_result",
        "tuyau_subpoints": "solver_result",
    }
    if not isinstance(fields, list) or len(fields) != len(expected):
        raise ValueError("Engineering-review bundles require four result fields.")
    overlays_by_id = {
        overlay.get("id"): overlay
        for overlay in overlays
        if isinstance(overlay, dict) and isinstance(overlay.get("id"), str)
    }
    found: set[str] = set()
    for field in fields:
        if not isinstance(field, dict):
            raise ValueError("Engineering-review result-field records must be objects.")
        overlay_id = field.get("overlay_id")
        overlay = overlays_by_id.get(overlay_id)
        if not isinstance(overlay, dict) or field.get("id") != str(overlay_id).replace("overlay:", "field:", 1):
            raise ValueError("Engineering-review result-field must match its overlay.")
        data = overlay.get("data")
        family = data.get("result_type") if isinstance(data, dict) else None
        if family not in expected or overlay.get("kind") != expected[family]:
            raise ValueError("Engineering-review result-field overlay family is invalid.")
        if family in found or not isinstance(data.get("values"), Mapping) or not data["values"]:
            raise ValueError("Engineering-review result-field overlay values are invalid.")
        if (
            field.get("result_state_id") != data.get("result_state_id")
            or not field.get("result_state_id")
            or field.get("load_case") != data.get("load_case")
            or not field.get("load_case")
            or not field.get("components")
        ):
            raise ValueError("Engineering-review result-field provenance is invalid.")
        found.add(family)
    if found != set(expected):
        raise ValueError("Engineering-review result-field families are incomplete.")


def _validate_engineering_provenance(
    scene: dict[str, Any], review: dict[str, Any]
) -> dict[str, Any]:
    provenance = review.get("provenance", [])
    if not isinstance(provenance, list) or any("fixture" in json.dumps(item).lower() for item in provenance):
        raise ValueError("Engineering-review provenance must be non-fixture Code_Aster evidence.")
    identities: dict[str, dict[str, Any]] = {}
    for kind in ("study", "analysis_mesh", "result_state"):
        records = [record for record in provenance if isinstance(record, dict) and record.get("kind") == kind]
        if len(records) != 1:
            raise ValueError(f"Engineering-review provenance requires one {kind} identity.")
        metadata = records[0].get("metadata")
        identity = metadata.get("solver_input_identity") if isinstance(metadata, dict) else None
        if not isinstance(identity, dict) or any(not identity.get(key) for key in _IDENTITY_FIELDS):
            raise ValueError(f"Engineering-review provenance requires a non-null {kind} identity.")
        identities[kind] = {key: identity[key] for key in _IDENTITY_FIELDS}
    reference = identities["study"]
    if any(identity != reference for identity in identities.values()):
        raise ValueError("Engineering-review provenance requires matching non-null solver identities.")
    scene_identities = scene.get("solver_input_identities")
    if (
        not isinstance(scene_identities, list)
        or not scene_identities
        or any(
            not isinstance(identity, dict)
            or any(not identity.get(key) for key in _IDENTITY_FIELDS)
            or {key: identity[key] for key in _IDENTITY_FIELDS} != reference
            for identity in scene_identities
        )
    ):
        raise ValueError("Engineering-review scene identity must match provenance.")
    if any(value.get("solver_name") != "Code_Aster" for value in provenance if isinstance(value, dict)):
        raise ValueError("Engineering-review provenance must identify Code_Aster.")
    return reference


def _validate_execution_attestation(root: Path, identity: dict[str, Any]) -> None:
    artifacts_root = root / "artifacts"
    attestation = load_code_aster_execution_attestation(artifacts_root)
    if attestation is None:
        raise ValueError("Engineering-review bundles require a validated Code_Aster execution attestation.")
    if attestation["solver_input_identity"] != identity:
        raise ValueError("Engineering-review execution attestation identity must match provenance.")


def _validate_embedded_portability(root: Path) -> None:
    artifacts_root = root / "artifacts"
    if not artifacts_root.is_dir():
        raise ValueError("Engineering-review bundles require staged artifact evidence.")
    for path in artifacts_root.rglob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid staged artifact JSON {path.name}: {exc}") from exc
        _reject_unsafe_references(payload)
    for path in root.rglob("*.html"):
        _reject_unsafe_references(path.read_text(encoding="utf-8"))


def _validate_portable_provenance_files(root: Path, review: dict[str, Any]) -> None:
    for record in review.get("provenance", []):
        if not isinstance(record, dict):
            continue
        files = record.get("files", {})
        if not isinstance(files, dict):
            raise ValueError("Engineering-review provenance files must be a mapping.")
        metadata = record.get("metadata", {})
        hashes = metadata.get("file_sha256", {}) if isinstance(metadata, dict) else {}
        sizes = metadata.get("file_sizes", {}) if isinstance(metadata, dict) else {}
        resolved: dict[str, Path] = {}
        for role, uri in files.items():
            if not isinstance(uri, str):
                raise ValueError("Engineering-review provenance files must be strings.")
            resolved[role] = _bundle_path(root, uri)
        if record.get("kind") in {"study", "result_state"} and (
            set(hashes) != set(files) or set(sizes) != set(files)
        ):
            raise ValueError("Engineering-review evidence must attest every provenance file.")
        for role, path in resolved.items():
            if hashes and hashes.get(role) != _file_hash(path):
                raise ValueError(f"Engineering-review evidence hash mismatch for {role!r}.")
            if sizes and sizes.get(role) != path.stat().st_size:
                raise ValueError(f"Engineering-review evidence size mismatch for {role!r}.")


def _reject_error_diagnostics(value: Any) -> None:
    for mapping in _mappings(value):
        if str(mapping.get("severity", "")).lower() == "error":
            raise ValueError(f"Official bundle contains an error diagnostic: {mapping.get('code', '<unknown>')}.")


def _reject_unsafe_references(value: Any) -> None:
    for text in _strings(value):
        if (
            _WINDOWS_ABSOLUTE.match(text)
            or _UNC.match(text)
            or re.search(r"(?:^|[\"'=\s])(?:[A-Za-z]:[\\/]|\\\\)", text)
            or text.startswith("/")
            or _TRAVERSAL.search(text)
        ):
            raise ValueError(f"Official bundle contains a non-portable path reference: {text!r}.")


def _bundle_path(root: Path, uri: str) -> Path:
    _reject_unsafe_references(uri)
    path = (root / uri).resolve()
    if path != root.resolve() and root.resolve() not in path.parents:
        raise ValueError(f"Bundle reference escapes its root: {uri!r}.")
    if not path.is_file():
        raise ValueError(f"Referenced bundle file is missing: {uri!r}.")
    return path


def _geometry_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _strings(value: Any):
    if isinstance(value, dict):
        for nested in value.values():
            yield from _strings(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _strings(nested)
    elif isinstance(value, str):
        yield value


def _mappings(value: Any):
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _mappings(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _mappings(nested)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    examples = subcommands.add_parser("examples")
    examples.add_argument("--output", type=Path, required=True)
    examples.add_argument("--audience", choices=("dev", "pages"), default="dev")
    examples.add_argument("--code-aster-artifacts", type=Path)
    pages = subcommands.add_parser("pages")
    pages.add_argument("--output", type=Path, required=True)
    pages.add_argument("--code-aster-artifacts", type=Path)
    args = parser.parse_args()
    if args.command == "pages":
        assemble_pages(args.output, code_aster_artifacts=args.code_aster_artifacts)
        return 0
    bundle_ids = build_examples(
        args.output,
        audience=args.audience,
        code_aster_artifacts=args.code_aster_artifacts,
    )
    write_bundle_catalog(args.output, bundle_ids)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
