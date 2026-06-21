"""Scene bundle export for browser-oriented visualization."""

from __future__ import annotations

import json
import re
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tuba.visualization.scene import VisualizationScene


@dataclass(frozen=True)
class SceneBundle:
    root: Path
    scene_path: Path
    metadata_dir: Path
    geometry_dir: Path


def write_scene_bundle(scene: VisualizationScene, path: str | Path) -> SceneBundle:
    """Write a browser-loadable semantic scene bundle.

    The first implementation writes deterministic JSON geometry payloads. Later
    renderer adapters can replace those payloads with GLB/XKT/Fragments assets
    while keeping the same scene and metadata contract.
    """
    root = Path(path)
    metadata_dir = root / "metadata"
    geometry_dir = root / "geometry"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    geometry_dir.mkdir(parents=True, exist_ok=True)

    scene_payload = scene.to_dict()
    scene_payload["geometry_assets"] = []

    for asset in scene.geometry_assets:
        asset_payload = asset.to_dict()
        asset_payload["uri"] = _relative_geometry_uri(asset.id)
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
        _write_json(root / asset_payload["uri"], geometry_payload)

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


def _relative_geometry_uri(asset_id: str) -> str:
    return f"geometry/{_safe_filename(asset_id)}.json"


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


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, sort_keys=True)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return
    path.write_text(text, encoding="utf-8")


def _content_hash(data: Any) -> str:
    payload = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"
