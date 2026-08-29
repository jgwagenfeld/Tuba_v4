"""Visualization convenience adapter for engineering review export."""

from __future__ import annotations

from pathlib import Path

from tuba.reporting import (
    EngineeringReviewOutput,
    EngineeringReviewPackage,
    write_engineering_review,
)
from tuba.visualization.scene import VisualizationScene
from tuba.visualization.web_export import write_scene_bundle


def write_engineering_review_with_scene(
    review: EngineeringReviewPackage,
    path: str | Path,
    *,
    scene: VisualizationScene | None = None,
    title: str | None = None,
    source: str | Path | None = None,
) -> EngineeringReviewOutput:
    """Write a review archive, optionally including an existing web scene.

    Use :func:`tuba.reporting.write_engineering_review` when no visualization
    integration is needed. This adapter preserves the established scene-bundle
    layout when a scene is supplied. ``source`` is forwarded to
    :func:`write_scene_bundle` to publish the authoring script.
    """

    def write_scene(root: Path) -> str:
        assert scene is not None
        write_scene_bundle(scene, root, source=source)
        return "scene.json"

    return write_engineering_review(
        review,
        path,
        title=title,
        scene_writer=write_scene if scene is not None else None,
    )
