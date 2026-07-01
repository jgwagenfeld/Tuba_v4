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


def _hashed_solver_name(name: str, *, max_length: int, used: set[str]) -> str:
    if max_length < 2:
        raise ValueError("max_length must allow at least a prefix and one digest character.")
    prefix = "G_" if max_length >= 10 else "G"
    digest_chars = max_length - len(prefix)
    attempt = 0
    while True:
        seed = name if attempt == 0 else f"{name}:{attempt}"
        digest = hashlib.sha1(seed.encode("utf-8")).hexdigest().upper()
        mapped = f"{prefix}{digest[:digest_chars]}"
        if mapped not in used:
            return mapped
        attempt += 1


def build_solver_name_map(names: Iterable[str], *, max_length: int = MAX_ASTER_NAME_LEN) -> dict[str, str]:
    mapping: dict[str, str] = {}
    used: set[str] = set()
    for name in names:
        if len(name) <= max_length and name not in used:
            mapped = name
        else:
            mapped = _hashed_solver_name(name, max_length=max_length, used=used)
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
    mixed_analysis: dict | None = None,
) -> None:
    payload = {
        "schema_version": 1,
        "solver_name": solver_name,
        "load_case": load_case,
        "analysis_mesh_id": analysis_mesh_id,
        "name_map": dict(sorted(name_map.items())),
        "lineage": dict(sorted(lineage.items())),
    }
    if mixed_analysis is not None:
        payload["mixed_analysis"] = mixed_analysis
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
