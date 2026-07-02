"""Trusted local preview package.

The preview HTTP/WebSocket server, one-shot runners, and JSON-patch preview all
live in :mod:`tuba.visualization.preview.server` (the subprocess entrypoint is
:mod:`tuba.visualization.preview._runner`). This package root keeps only the
trusted-script output-capture API that preview scripts import
(``show_model`` / ``show_scene`` / ``show_patch``) and re-exports the server
surface so ``from tuba.visualization.preview import PreviewServer`` keeps working.
"""

from __future__ import annotations

from typing import Any

from tuba.model import TubaModel
from tuba.patches import ModelPatch
from tuba.visualization.scene import VisualizationScene

from tuba.visualization.preview.server import (
    PatchPreviewServer,
    PreviewRunResult,
    PreviewServer,
    execute_patch_preview,
    execute_preview_script,
    run_patch_preview_once,
    run_preview_once,
)

# Trusted preview scripts call show_*(...) to declare their output; the runner
# subprocess (_runner) drains these via _consume_output_capture().
_CAPTURED_OUTPUTS: list[dict[str, Any]] = []


def show_model(model: TubaModel, **scene_kwargs: Any) -> None:
    """Capture a model from a trusted preview script."""
    _CAPTURED_OUTPUTS.append({"kind": "model", "value": model, "scene_kwargs": dict(scene_kwargs)})


def show_scene(scene: VisualizationScene | dict[str, Any]) -> None:
    """Capture a scene from a trusted preview script."""
    _CAPTURED_OUTPUTS.append({"kind": "scene", "value": scene, "scene_kwargs": {}})


def show_patch(patch: ModelPatch | dict[str, Any], *, model: TubaModel | None = None, **scene_kwargs: Any) -> None:
    """Capture a model patch from a trusted preview script."""
    _CAPTURED_OUTPUTS.append({"kind": "patch", "value": patch, "model": model, "scene_kwargs": dict(scene_kwargs)})


def _reset_output_capture() -> None:
    _CAPTURED_OUTPUTS.clear()


def _consume_output_capture() -> list[dict[str, Any]]:
    outputs = list(_CAPTURED_OUTPUTS)
    _CAPTURED_OUTPUTS.clear()
    return outputs


__all__ = [
    "PatchPreviewServer",
    "PreviewRunResult",
    "PreviewServer",
    "execute_patch_preview",
    "execute_preview_script",
    "run_patch_preview_once",
    "run_preview_once",
    "show_model",
    "show_patch",
    "show_scene",
]
