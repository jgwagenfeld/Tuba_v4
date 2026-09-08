"""World-anchored labels for web visualization scenes."""

from __future__ import annotations

from math import isfinite
from typing import Sequence

from tuba.visualization.scene import GeometryAsset, SceneLayer, SceneObject, VisualizationScene
from tuba.visualization.schema import SceneValidationError

LABEL_LAYER_ID = "annotations:labels"


def add_scene_label(scene: VisualizationScene, text: str, position: Sequence[float], *, label_id: str, height: float = 0.18) -> SceneObject:
    """Add a camera-facing text label at a world position."""
    if not isinstance(text, str) or not text.strip():
        raise SceneValidationError("Scene label text must be a non-empty string.")
    if not isinstance(label_id, str) or not label_id.strip():
        raise SceneValidationError("Scene label id must be a non-empty string.")
    try:
        point = [float(value) for value in position]
    except (TypeError, ValueError):
        raise SceneValidationError("Scene label position must contain three finite numbers.") from None
    if len(point) != 3 or not all(isfinite(value) for value in point):
        raise SceneValidationError("Scene label position must contain three finite numbers.")
    if isinstance(height, bool) or not isinstance(height, (int, float)) or not isfinite(height) or height <= 0:
        raise SceneValidationError("Scene label height must be a positive finite number.")

    object_id = f"label:{label_id}"
    asset_id = f"geometry:label:{label_id}"
    if any(obj.id == object_id for obj in scene.objects) or any(asset.id == asset_id for asset in scene.geometry_assets):
        raise SceneValidationError(f"Scene label id {label_id!r} is already in use.")
    if not any(layer.id == LABEL_LAYER_ID for layer in scene.layers):
        scene.layers.append(SceneLayer(id=LABEL_LAYER_ID, category="annotations", label="Labels"))

    obj = SceneObject(id=object_id, kind="scene_label", name=text, geometry_asset_id=asset_id, layer_ids=[LABEL_LAYER_ID], metadata={"text": text, "position": point})
    scene.objects.append(obj)
    scene.geometry_assets.append(GeometryAsset(id=asset_id, format="label", bounds=[*point, *point], object_ids=[object_id], generation_config={"text": text, "position": point, "height": float(height)}))
    return obj
