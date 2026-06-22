"""Code_Aster sidecar helpers for traceable Tuba solver exports."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable


MAX_ASTER_NAME_LEN = 24


class SolverNameMap:
    def __init__(self, mapping: dict[str, str] | None = None):
        self.mapping = dict(mapping or {})

    def __call__(self, name: str) -> str:
        return self.mapping.get(name, name)


def build_solver_name_map(names: Iterable[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    used: set[str] = set()
    for name in names:
        if len(name) <= MAX_ASTER_NAME_LEN and name not in used:
            mapped = name
        else:
            digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:8].upper()
            mapped = f"G_{digest}"
            suffix = 1
            while mapped in used:
                mapped = f"G_{digest[:6]}_{suffix:02d}"
                suffix += 1
        mapping[name] = mapped
        used.add(mapped)
    return mapping


def dump_solver_sidecar(
    path: str | Path,
    *,
    solver_name: str,
    load_case: str,
    analysis_mesh_id: str,
    name_map: dict[str, str],
    lineage: dict[str, str],
) -> None:
    payload = {
        "schema_version": 1,
        "solver_name": solver_name,
        "load_case": load_case,
        "analysis_mesh_id": analysis_mesh_id,
        "name_map": dict(sorted(name_map.items())),
        "lineage": dict(sorted(lineage.items())),
    }
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
