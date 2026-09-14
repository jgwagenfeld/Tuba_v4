"""Validation helpers for semantic visualization scene payloads."""

from __future__ import annotations

from typing import Any


class SceneValidationError(ValueError):
    """Raised when a visualization scene payload is internally inconsistent."""


def validate_scene_dict(data: dict[str, Any]):
    """Validate a serialized visualization scene and return the parsed scene."""
    from tuba.visualization.scene import VisualizationScene

    scene = VisualizationScene.from_dict(data)
    scene.validate()
    return scene
