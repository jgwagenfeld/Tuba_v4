"""Reading linear buckling results back out of a solved Code_Aster study.

Two artifacts, both produced only when the load case declared ``buckling=``:

* ``study_buckling.json`` - the critical load factors, written from the interpreter
  embedded in the comm because ``CHAR_CRIT`` is a result *parameter* and
  ``CREA_TABLE`` only extracts fields.
* ``study_buckling_modes.csv`` - the mode shapes, in the same column layout as a
  static ``DEPL`` table so the standard displacement reader applies unchanged.

Both are read strictly. A study that asked for buckling and produced no factors is
an error, not an empty result: silently returning "no instability found" for a
failed eigen-solve is precisely the fabrication the product contract forbids.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping

from tuba.analysis.buckling import BucklingMode, BucklingResult
from tuba.solver.parse_tables import parse_csv_table

BUCKLING_FACTORS_FILE = "study_buckling.json"
BUCKLING_MODES_FILE = "study_buckling_modes.csv"

_MODE_DISPLACEMENT_COMPONENTS = ("DX", "DY", "DZ", "DRX", "DRY", "DRZ")


def _mode_shapes_by_mode(
    work_dir: Path, node_label_map: Mapping[str, str]
) -> dict[int, dict[str, tuple[float, ...]]]:
    """Group the mode-shape table by mode number, keyed back to model node ids."""
    path = Path(work_dir) / BUCKLING_MODES_FILE
    if not path.exists():
        return {}
    shapes: dict[int, dict[str, tuple[float, ...]]] = {}
    for row in parse_csv_table(path):
        order = row.get("NUME_ORDRE") or row.get("NUME_MODE")
        label = row.get("NOEUD")
        if not order or not label:
            continue
        try:
            mode = int(float(order))
        except (TypeError, ValueError):
            continue
        values = []
        for component in _MODE_DISPLACEMENT_COMPONENTS:
            raw = row.get(component)
            if raw in (None, ""):
                values = []
                break
            try:
                value = float(raw)
            except (TypeError, ValueError):
                values = []
                break
            if not math.isfinite(value):
                values = []
                break
            values.append(value)
        if not values:
            continue
        # NOEUD is the solver-safe label; map it back to the model node id.
        node_id = node_label_map.get(label, label)
        shapes.setdefault(mode, {})[str(node_id)] = tuple(values)
    return shapes


def parse_buckling(
    work_dir: str | Path,
    node_label_map: Mapping[str, str],
    *,
    requested_modes: int = 0,
    method: str = "TRI_DIAG",
) -> BucklingResult:
    """Read the buckling artifacts of a solved study.

    Raises when the factors are absent, unreadable, or non-finite. Returns a result
    with no modes only when the JSON is genuinely empty, which Code_Aster writes
    when the search found nothing.
    """
    root = Path(work_dir)
    path = root / BUCKLING_FACTORS_FILE
    if not path.exists():
        raise RuntimeError(
            f"Code_Aster study {root} was compiled with buckling= but produced no "
            f"{BUCKLING_FACTORS_FILE}. The buckling eigenproblem did not complete; "
            "refusing to report an absent instability as a stable structure. "
            "Inspect study.mess for solver errors."
        )
    try:
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Buckling results {path} are not readable JSON: {exc}. Refusing to report "
            "the structure as unbuckled on an unreadable artifact."
        ) from exc
    if not isinstance(payload, Mapping):
        raise RuntimeError(
            f"Buckling results {path} must be a JSON object, got {type(payload).__name__}."
        )
    entries = payload.get("modes")
    if entries is None:
        entries = []
    if not isinstance(entries, list):
        raise RuntimeError(f"Buckling results {path}: 'modes' must be a list.")

    shapes = _mode_shapes_by_mode(root, node_label_map)
    notes: list[str] = []
    modes: list[BucklingMode] = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise RuntimeError(f"Buckling results {path}: every mode must be an object.")
        mode_number = int(entry["mode"])
        raw = float(entry["raw_eigenvalue"])
        factor = abs(float(entry.get("critical_factor", raw)))
        if not math.isfinite(factor) or factor <= 0.0:
            raise RuntimeError(
                f"Buckling results {path}: mode {mode_number} has a non-physical critical "
                f"factor {factor!r}. Refusing to report it."
            )
        modes.append(
            BucklingMode(
                mode=mode_number,
                critical_factor=factor,
                raw_eigenvalue=raw,
                node_displacements=shapes.get(mode_number, {}),
            )
        )
    if requested_modes and len(modes) < requested_modes:
        notes.append(
            f"solver returned {len(modes)} of {requested_modes} requested critical charges; "
            "the structure may have fewer than were asked for"
        )
    return BucklingResult(
        modes=tuple(modes),
        requested_modes=int(requested_modes),
        method=str(method),
        notes=tuple(notes),
    )
