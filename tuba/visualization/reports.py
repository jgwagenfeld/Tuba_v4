"""Legacy tabular reports derived from a :class:`VisualizationScene`.

Line list, cross-section schedule, load-case summary, and per-load-case stress /
reaction / displacement tables remain available for scene-bundle compatibility.
They are scene-derived convenience views, not authoritative engineering-review
records or piping-code compliance results. Each report function remains pure:
scene in, list-of-row-dicts out.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any, Callable

from tuba.visualization.scene import Overlay, VisualizationScene


def line_list(scene: VisualizationScene) -> list[dict[str, Any]]:
    """One row per piping element: geometry, section, material, mass."""
    rows: list[dict[str, Any]] = []
    for obj in scene.objects:
        if not _is_element(obj):
            continue
        phys, qty, meta = obj.physical, obj.quantities, obj.metadata
        nodes = meta.get("nodes") or []
        rows.append(
            {
                "id": obj.id,
                "name": obj.name,
                "type": meta.get("element_type", obj.kind),
                "from_node": nodes[0] if nodes else "",
                "to_node": nodes[-1] if nodes else "",
                "length_m": qty.get("length_m"),
                "od_m": phys.get("bare_od_m") or phys.get("effective_od_m"),
                "metal_area_m2": phys.get("metal_area_m2"),
                "section": meta.get("section") or phys.get("section"),
                "material": meta.get("material") or phys.get("material"),
                "insulation_thickness_m": phys.get("insulation_thickness_m"),
                "mass_kg": qty.get("total_mass_kg") or qty.get("pipe_mass_kg"),
            }
        )
    return rows


def section_schedule(scene: VisualizationScene) -> list[dict[str, Any]]:
    """One row per unique (section, material): representative props + totals."""
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for obj in scene.objects:
        if not _is_element(obj):
            continue
        phys, qty, meta = obj.physical, obj.quantities, obj.metadata
        section = meta.get("section") or phys.get("section") or ""
        material = meta.get("material") or phys.get("material") or ""
        row = groups.setdefault(
            (section, material),
            {
                "section": section,
                "material": material,
                "od_m": phys.get("bare_od_m") or phys.get("effective_od_m"),
                "metal_area_m2": phys.get("metal_area_m2"),
                "mass_kg_per_m": phys.get("mass_kg_per_m"),
                "count": 0,
                "total_length_m": 0.0,
                "total_mass_kg": 0.0,
            },
        )
        row["count"] += 1
        row["total_length_m"] += float(qty.get("length_m") or 0.0)
        row["total_mass_kg"] += float(qty.get("total_mass_kg") or qty.get("pipe_mass_kg") or 0.0)
    return list(groups.values())


def load_case_summary(scene: VisualizationScene) -> list[dict[str, Any]]:
    """Summarize scene FE overlays; utilization is not piping-code compliance."""
    cases: dict[str, dict[str, Any]] = {}
    for overlay in scene.overlays:
        data = overlay.data or {}
        load_case = data.get("load_case")
        if not load_case:
            continue
        row = cases.setdefault(
            load_case,
            {
                "load_case": load_case,
                "max_von_mises_pa": None,
                "max_utilization": None,
                "max_reaction_n": None,
                "max_displacement_m": None,
            },
        )
        if overlay.kind == "solver_result" and data.get("result_type") == "stress":
            for value in (data.get("values") or {}).values():
                row["max_von_mises_pa"] = _running_max(row["max_von_mises_pa"], value)
            for value in (data.get("utilization_values") or {}).values():
                row["max_utilization"] = _running_max(row["max_utilization"], value)
        if overlay.kind == "result_state":
            for dof in (data.get("node_reactions") or {}).values():
                row["max_reaction_n"] = _running_max(row["max_reaction_n"], _magnitude(dof[:3]))
            for dof in (data.get("node_displacements") or {}).values():
                row["max_displacement_m"] = _running_max(row["max_displacement_m"], _magnitude(dof[:3]))
    return list(cases.values())


def stress_report(scene: VisualizationScene) -> list[dict[str, Any]]:
    """Return scene FE Von Mises rows, not piping-code stress checks."""
    names = {obj.id: obj.name for obj in scene.objects}
    rows: list[dict[str, Any]] = []
    for overlay in _overlays(scene, kind="solver_result", result_type="stress"):
        data = overlay.data or {}
        thresholds = (data.get("legend") or {}).get("thresholds", {})
        warn = float(thresholds.get("warning", 0.8) or 0.8)
        crit = float(thresholds.get("critical", 1.0) or 1.0)
        utilization = data.get("utilization_values") or {}
        for object_id, value in (data.get("values") or {}).items():
            util = utilization.get(object_id)
            rows.append(
                {
                    "load_case": data.get("load_case", ""),
                    "id": object_id,
                    "name": names.get(object_id, object_id),
                    "von_mises_pa": value,
                    "unit": data.get("unit", ""),
                    "utilization": util,
                    "status": _status(util, warn, crit),
                }
            )
    return rows


def reaction_report(scene: VisualizationScene) -> list[dict[str, Any]]:
    """One row per (restrained node, load case): 6-DOF support reactions."""
    supports = _node_support_map(scene)
    rows: list[dict[str, Any]] = []
    for overlay in _overlays(scene, kind="result_state"):
        load_case = (overlay.data or {}).get("load_case", "")
        for node, dof in (overlay.data.get("node_reactions") or {}).items():
            dof = _pad6(dof)
            rows.append(
                {
                    "load_case": load_case,
                    "node": node,
                    "support": supports.get(node, ""),
                    "fx_n": dof[0],
                    "fy_n": dof[1],
                    "fz_n": dof[2],
                    "mx_nm": dof[3],
                    "my_nm": dof[4],
                    "mz_nm": dof[5],
                    "magnitude_n": _magnitude(dof[:3]),
                }
            )
    return rows


def displacement_report(scene: VisualizationScene) -> list[dict[str, Any]]:
    """One row per (node, load case): 6-DOF nodal displacements."""
    rows: list[dict[str, Any]] = []
    for overlay in _overlays(scene, kind="result_state"):
        load_case = (overlay.data or {}).get("load_case", "")
        for node, dof in (overlay.data.get("node_displacements") or {}).items():
            dof = _pad6(dof)
            rows.append(
                {
                    "load_case": load_case,
                    "node": node,
                    "dx_m": dof[0],
                    "dy_m": dof[1],
                    "dz_m": dof[2],
                    "rx_rad": dof[3],
                    "ry_rad": dof[4],
                    "rz_rad": dof[5],
                    "magnitude_m": _magnitude(dof[:3]),
                }
            )
    return rows


REPORTS: dict[str, Callable[[VisualizationScene], list[dict[str, Any]]]] = {
    "line_list": line_list,
    "section_schedule": section_schedule,
    "load_case_summary": load_case_summary,
    "stress": stress_report,
    "reactions": reaction_report,
    "displacements": displacement_report,
}


def build_reports(scene: VisualizationScene) -> dict[str, list[dict[str, Any]]]:
    """Return every report keyed by name (empty lists included)."""
    return {name: report(scene) for name, report in REPORTS.items()}


def write_report_csvs(scene: VisualizationScene, directory: str | Path) -> list[Path]:
    """Write one CSV per non-empty report into ``directory``; return the paths."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, rows in build_reports(scene).items():
        if not rows:
            continue
        path = directory / f"{name}.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        written.append(path)
    return written


def _is_element(obj: Any) -> bool:
    return bool(obj.physical.get("element_id") or obj.metadata.get("element_type"))


def _overlays(scene: VisualizationScene, *, kind: str, result_type: str | None = None) -> list[Overlay]:
    return [
        overlay
        for overlay in scene.overlays
        if overlay.kind == kind and (result_type is None or (overlay.data or {}).get("result_type") == result_type)
    ]


def _node_support_map(scene: VisualizationScene) -> dict[str, str]:
    return {
        obj.metadata["node"]: obj.name
        for obj in scene.objects
        if obj.kind == "support" and obj.metadata.get("node")
    }


def _pad6(dof: Any) -> list[float]:
    values = [float(component) for component in (dof or [])]
    return (values + [0.0, 0.0, 0.0, 0.0, 0.0, 0.0])[:6]


def _magnitude(vector: Any) -> float:
    return math.sqrt(sum(float(component) ** 2 for component in (vector or [])))


def _running_max(current: float | None, value: Any) -> float | None:
    if value is None:
        return current
    value = float(value)
    return value if current is None else max(current, value)


def _status(utilization: Any, warn: float, crit: float) -> str:
    if utilization is None:
        return ""
    utilization = float(utilization)
    if utilization >= crit:
        return "critical"
    if utilization >= warn:
        return "warning"
    return "ok"
