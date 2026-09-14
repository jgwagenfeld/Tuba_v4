"""Small benchmark-summary helpers for generated model workflows."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from tuba.model import TubaModel

_DEFAULT_BENCHMARK_DIRECTORY = ".build/benchmarks"


def write_model_benchmark_summary(
    model: TubaModel,
    *,
    directory: str | Path = _DEFAULT_BENCHMARK_DIRECTORY,
) -> str:
    output_dir = Path(directory)
    output_dir.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {
        "project_name": model.project_name,
        "nodes": len(model.nodes),
        "elements": len(model.elements),
        "supports": len(model.supports),
        "groups": len(model.groups),
        "node_index_entries": len(getattr(model, "_node_point_index", {})),
        "element_index_entries": len(getattr(model, "_element_ids", set())),
        "timestamp": time.time(),
    }
    path = output_dir / f"model_benchmark_{model.project_name}.json"
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return str(path)
