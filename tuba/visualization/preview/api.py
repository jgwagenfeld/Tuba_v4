"""Trusted-script preview output helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PreviewOutput:
    kind: str
    value: Any


_COLLECTED_OUTPUTS: list[PreviewOutput] = []


def show_model(model: Any) -> Any:
    """Record a model as the current trusted-script preview output."""
    _COLLECTED_OUTPUTS.append(PreviewOutput("model", model))
    return model


def show_scene(scene: Any) -> Any:
    """Record a scene as the current trusted-script preview output."""
    _COLLECTED_OUTPUTS.append(PreviewOutput("scene", scene))
    return scene


def show_patch(patch: Any) -> Any:
    """Record a model patch as the current trusted-script preview output."""
    _COLLECTED_OUTPUTS.append(PreviewOutput("patch", patch))
    return patch


def clear_preview_outputs() -> None:
    _COLLECTED_OUTPUTS.clear()


def collected_preview_outputs() -> list[PreviewOutput]:
    return list(_COLLECTED_OUTPUTS)
