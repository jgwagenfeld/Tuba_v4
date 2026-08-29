"""Scene bundle export for browser-oriented visualization."""

from __future__ import annotations

import json
import re
import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from tuba.visualization.scene import VisualizationScene


@dataclass(frozen=True)
class SceneBundle:
    root: Path
    scene_path: Path
    metadata_dir: Path
    geometry_dir: Path


def write_scene_bundle(
    scene: VisualizationScene,
    path: str | Path,
    *,
    source: str | Path | None = None,
) -> SceneBundle:
    """Write a browser-loadable semantic scene bundle.

    The first implementation writes deterministic JSON geometry payloads. Later
    renderer adapters can replace those payloads with GLB/XKT/Fragments assets
    while keeping the same scene and metadata contract.

    ``source`` copies the authoring Tuba script beside the scene as
    ``source.py`` and records it as ``source_uri``, so a reviewer can read the
    code that produced the geometry. It is a provenance record, not solver
    evidence, and not necessarily a standalone reproducer.
    """
    root = Path(path)
    metadata_dir = root / "metadata"
    geometry_dir = root / "geometry"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    geometry_dir.mkdir(parents=True, exist_ok=True)

    scene_payload = scene.to_dict()
    scene_payload["geometry_assets"] = []
    # Always resolve the source, including the absent case: a re-export into an
    # existing root would otherwise leave the previous run's script in place,
    # silently mislabelled as this scene's origin.
    staged_source = _stage_source(root, source)
    if staged_source is not None:
        scene_payload["source_uri"] = staged_source

    for asset in scene.geometry_assets:
        asset_payload = asset.to_dict()
        asset_payload["uri"] = _relative_geometry_uri(asset.id)
        asset_payload["generation_config"] = _manifest_generation_config(asset_payload)
        geometry_payload = {
            "asset_id": asset.id,
            "format": asset.format,
            "bounds": list(asset.bounds),
            "object_ids": list(asset.object_ids),
            "generation_config": dict(asset.generation_config),
        }
        asset_hash = _content_hash(geometry_payload)
        asset_payload["hash"] = asset_hash
        geometry_payload["hash"] = asset_hash
        scene_payload["geometry_assets"].append(asset_payload)
        # Per-asset geometry payloads are machine-only point clouds (a tuyau
        # subpoint asset holds ~24k glyphs); write them compact. The content hash
        # above is computed over the canonical compact form, so dropping the
        # indentation changes neither the data nor the hash.
        _write_json(root / asset_payload["uri"], geometry_payload, compact=True)

    # Validate the payload that consumers will actually read.
    VisualizationScene.from_dict(scene_payload).validate()

    _write_json(metadata_dir / "objects.json", scene_payload["objects"])
    _write_json(metadata_dir / "object_map.json", _object_map(scene_payload["objects"]))
    _write_json(metadata_dir / "overlays.json", scene_payload["overlays"])
    _write_json(metadata_dir / "issues.json", scene_payload["issues"])
    _write_json(metadata_dir / "route_reviews.json", scene_payload["route_reviews"])
    _write_json(metadata_dir / "agent_proposals.json", scene_payload["agent_proposals"])
    _write_json(metadata_dir / "scene_diffs.json", scene_payload["scene_diffs"])
    _write_json(geometry_dir / "geometry_assets.json", scene_payload["geometry_assets"])
    # Publish scene.json last so live viewers do not reload a half-written bundle.
    _write_json(root / "scene.json", scene_payload)

    return SceneBundle(
        root=root,
        scene_path=root / "scene.json",
        metadata_dir=metadata_dir,
        geometry_dir=geometry_dir,
    )


def _stage_source(root: Path, source: str | Path | None) -> str | None:
    """Place the authoring script beside the scene, or clear a stale one."""
    staged = root / "source.py"
    if source is None:
        staged.unlink(missing_ok=True)
        return None
    origin = Path(source)
    if not origin.is_file():
        raise ValueError(f"Scene source script does not exist: {origin}")
    # A byte copy, not a text round trip: reading and rewriting as text
    # rewrites line endings to the publisher's platform, which would make the
    # published script differ between a Windows and a Linux build of the same
    # bundle. It also refuses to write through a symlink.
    staged.unlink(missing_ok=True)
    shutil.copyfile(origin, staged)
    return staged.name


def _relative_geometry_uri(asset_id: str) -> str:
    return f"geometry/{_safe_filename(asset_id)}.json"


def _manifest_generation_config(asset_payload: dict[str, Any]) -> dict[str, Any]:
    config = dict(asset_payload.get("generation_config", {}))
    if asset_payload.get("format") != "tuyau_subpoint_glyphs":
        return config
    return {
        "source": config.get("source"),
        "count": len(config.get("starts", [])) if isinstance(config.get("starts"), list) else 0,
        "range": config.get("range"),
        "position_source": config.get("position_source"),
        "payload_uri": asset_payload.get("uri"),
    }


def _safe_filename(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return safe or "asset"


def _object_map(objects: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for obj in objects:
        result[obj["id"]] = {
            "entity_ref": obj.get("entity_ref"),
            "kind": obj.get("kind", ""),
            "geometry_asset_id": obj.get("geometry_asset_id"),
        }
    return result


def _write_json(path: Path, data: Any, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if compact:
        text = json.dumps(data, separators=(",", ":"), sort_keys=True)
    else:
        text = json.dumps(data, indent=2, sort_keys=True)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _content_hash(data: Any) -> str:
    payload = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"
