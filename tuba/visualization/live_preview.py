"""Live preview helpers for trusted Python scripts and JSON model patches."""

from __future__ import annotations

import runpy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tuba.model import TubaModel
from tuba.patches import ModelPatch
from tuba.visualization.builders import build_visualization_scene
from tuba.visualization.scene import SceneDiagnostic, SceneDiff, VisualizationScene


@dataclass
class LivePreviewResult:
    scene: VisualizationScene | None = None
    scene_diff: SceneDiff | None = None
    diagnostics: list[SceneDiagnostic] = field(default_factory=list)
    messages: list[dict[str, Any]] = field(default_factory=list)


def preview_json_patch(model: TubaModel, patch_payload: dict[str, Any] | ModelPatch) -> LivePreviewResult:
    """Dry-run a JSON patch and return a scene diff message."""
    try:
        patch = patch_payload if isinstance(patch_payload, ModelPatch) else ModelPatch.from_dict(patch_payload)
        scene = build_visualization_scene(
            model,
            agent_proposals=[
                {
                    "proposal_id": "live_preview",
                    "agent_id": "live_preview",
                    "goal": "preview patch",
                    "rationale": "dry-run patch preview",
                    "model_patch": patch,
                }
            ],
        )
        diff = scene.scene_diffs[0] if scene.scene_diffs else None
        return LivePreviewResult(
            scene=scene,
            scene_diff=diff,
            messages=[{"type": "scene_diff", "diff_id": diff.diff_id, "payload": diff.to_dict()}] if diff else [],
        )
    except Exception as exc:
        diagnostic = SceneDiagnostic(
            severity="error",
            code="visualization.live_preview.invalid_patch",
            message=str(exc),
            source="visualization.live_preview",
        )
        return LivePreviewResult(diagnostics=[diagnostic], messages=[{"type": "diagnostic", "payload": diagnostic.to_dict()}])


def preview_python_script(model: TubaModel, script_path: str | Path) -> LivePreviewResult:
    """Execute a trusted local script with ``build_patch(model)`` and preview its patch."""
    try:
        namespace = runpy.run_path(str(script_path))
        build_patch = namespace.get("build_patch")
        if build_patch is None:
            raise ValueError("Trusted preview script must define build_patch(model).")
        patch = build_patch(model)
        return preview_json_patch(model, patch)
    except Exception as exc:
        diagnostic = SceneDiagnostic(
            severity="error",
            code="visualization.live_preview.python_error",
            message=str(exc),
            source="visualization.live_preview",
        )
        return LivePreviewResult(diagnostics=[diagnostic], messages=[{"type": "diagnostic", "payload": diagnostic.to_dict()}])
