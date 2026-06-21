"""Subprocess worker for trusted visualization preview scripts."""

from __future__ import annotations

import json
import runpy
import sys
import traceback
from pathlib import Path

from tuba.visualization.preview import (
    PREVIEW_SOURCE,
    _consume_output_capture,
    _diagnostic,
    _output_from_namespace,
    _reset_output_capture,
    _scene_from_output,
)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        print("Usage: python -m tuba.visualization.preview._worker SCRIPT RESULT_JSON", file=sys.stderr)
        return 2

    script_path = Path(args[0])
    result_path = Path(args[1])
    result_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        _reset_output_capture()
        namespace = runpy.run_path(str(script_path), run_name="__main__")
        outputs = _consume_output_capture()
        output = outputs[-1] if outputs else _output_from_namespace(namespace)
        scene = _scene_from_output(output, namespace)
        _write_result(result_path, {"ok": True, "scene": scene.to_dict(), "diagnostics": []})
        return 0
    except Exception as exc:
        diagnostic = _diagnostic(
            "visualization.preview.python_error",
            str(exc),
            target=str(script_path),
        )
        payload = diagnostic.to_dict()
        payload["traceback"] = traceback.format_exc()
        payload["source"] = PREVIEW_SOURCE
        _write_result(result_path, {"ok": False, "diagnostics": [payload]})
        return 1


def _write_result(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
