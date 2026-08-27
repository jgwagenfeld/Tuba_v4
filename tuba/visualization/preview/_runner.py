"""Subprocess entrypoint for trusted local preview scripts."""

from __future__ import annotations

import argparse
import json
import runpy
import sys
import traceback
from pathlib import Path
from typing import Any

from tuba.model import TubaModel
from tuba.patches import ModelPatch
from tuba.visualization.builders import build_visualization_scene
from tuba.visualization.live_preview import preview_json_patch
import tuba.visualization.preview as preview_package
from tuba.visualization.scene import SceneDiagnostic, VisualizationScene
from tuba.visualization.web_export import write_scene_bundle


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("script")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    payload = run_trusted_script(Path(args.script), Path(args.out))
    sys.stdout.write(json.dumps(payload, sort_keys=True))
    sys.stdout.flush()
    return 0 if payload.get("ok") else 1


def run_trusted_script(script_path: Path, out_dir: Path) -> dict[str, Any]:
    try:
        preview_package._reset_output_capture()
        namespace = runpy.run_path(str(script_path), run_name="__main__")
        outputs = preview_package._consume_output_capture()
        for kind in ("scene", "model", "patch"):
            if kind in namespace:
                outputs.append({"kind": kind, "value": namespace[kind]})
        return _materialize_outputs(outputs, out_dir)
    except Exception as exc:
        diagnostic = SceneDiagnostic(
            severity="error",
            code="visualization.preview.python_error",
            message=str(exc),
            source=str(script_path),
            extra={"traceback": traceback.format_exc(limit=5)},
        )
        return {"ok": False, "diagnostics": [diagnostic.to_dict()], "messages": [_diagnostic_event(diagnostic)]}


def _materialize_outputs(outputs: list[dict[str, Any]], out_dir: Path) -> dict[str, Any]:
    model: TubaModel | None = None
    patch: ModelPatch | dict[str, Any] | None = None
    scene: VisualizationScene | None = None

    for output in outputs:
        if output["kind"] == "model":
            model = output["value"]
        elif output["kind"] == "patch":
            patch = output["value"]
        elif output["kind"] == "scene":
            scene = _coerce_scene(output["value"])

    if scene is None and model is not None and patch is None:
        scene = build_visualization_scene(model)
    if scene is None and patch is not None:
        if model is None:
            diagnostic = SceneDiagnostic(
                severity="error",
                code="visualization.preview.patch_without_model",
                message="Preview scripts that output patch must also output model for RV13 live preview.",
                source="visualization.preview",
            )
            return {"ok": False, "diagnostics": [diagnostic.to_dict()], "messages": [_diagnostic_event(diagnostic)]}
        preview = preview_json_patch(model, patch)
        if preview.diagnostics:
            return {
                "ok": False,
                "diagnostics": [diagnostic.to_dict() for diagnostic in preview.diagnostics],
                "messages": list(preview.messages),
            }
        scene = preview.scene

    if scene is None:
        diagnostic = SceneDiagnostic(
            severity="error",
            code="visualization.preview.no_output",
            message="Trusted preview script must define or show model, scene, or patch.",
            source="visualization.preview",
        )
        return {"ok": False, "diagnostics": [diagnostic.to_dict()], "messages": [_diagnostic_event(diagnostic)]}

    write_scene_bundle(scene, out_dir)
    return {
        "ok": True,
        "diagnostics": [],
        "messages": [{"type": "scene_reloaded", "scene_uri": "scene.json"}],
        "scene_id": scene.scene_id,
    }


def _coerce_scene(value: Any) -> VisualizationScene:
    if isinstance(value, VisualizationScene):
        return value
    if isinstance(value, dict):
        return VisualizationScene.from_dict(value)
    raise TypeError(f"Unsupported scene preview output {type(value).__name__}.")


def _diagnostic_event(diagnostic: SceneDiagnostic) -> dict[str, Any]:
    return {"type": "diagnostic", "severity": diagnostic.severity, "message": diagnostic.message, "payload": diagnostic.to_dict()}


if __name__ == "__main__":
    raise SystemExit(main())
