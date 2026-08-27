"""Parse Code_Aster 3D pipe-volume result tables."""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Iterator

import numpy as np

from tuba.analysis import AnalysisMesh, AnalysisStudy
from tuba.model import TubaModel
from tuba.solver.base import ElementResult, FEAResults, NodeResult


def parse_volume_result_artifacts(
    model: TubaModel,
    work_dir: str | Path,
    analysis_mesh: AnalysisMesh,
    study: AnalysisStudy,
) -> FEAResults:
    root = Path(work_dir)
    results = FEAResults(solver_name="Code_Aster", load_case=study.load_case)
    results._model = model
    rmed_path = root / "study.rmed"
    if rmed_path.is_file():
        results.result_file = rmed_path

    for row in _rows(root / "study_depl.csv"):
        node_id = _volume_node_id(row.get("NOEUD", ""))
        if node_id not in analysis_mesh.nodes:
            continue
        results.analysis_node_results[node_id] = NodeResult(
            node_id=node_id,
            displacement=np.asarray([*_components(row, ("DX", "DY", "DZ")), np.nan, np.nan, np.nan]),
        )
    missing = sorted(set(analysis_mesh.nodes) - set(results.analysis_node_results))
    if missing:
        raise RuntimeError(
            f"Code_Aster volume output is missing displacement for {len(missing)} analysis nodes."
        )

    anchored_nodes = _anchored_volume_nodes(model, analysis_mesh, study)
    for row in _rows(root / "study_reac.csv"):
        node_id = _volume_node_id(row.get("NOEUD", ""))
        node_result = results.analysis_node_results.get(node_id)
        if node_result is not None and node_id in anchored_nodes:
            node_result.reaction_force = np.asarray(
                [*_components(row, ("DX", "DY", "DZ")), np.nan, np.nan, np.nan]
            )

    surface_mesh = analysis_mesh.surface_mesh or {}
    surface_nodes = set(surface_mesh.get("node_ids", []))
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    maximum = -math.inf
    for row in _rows(root / "study_sieq.csv"):
        value = _finite(row, "VMIS")
        maximum = max(maximum, value)
        node_id = _volume_node_id(row.get("NOEUD", ""))
        if node_id in surface_nodes:
            sums[node_id] = sums.get(node_id, 0.0) + value
            counts[node_id] = counts.get(node_id, 0) + 1
    if not math.isfinite(maximum):
        raise RuntimeError("Code_Aster volume output contains no finite SIEQ_ELNO VMIS values.")
    results.volume_von_mises = {node_id: sums[node_id] / counts[node_id] for node_id in sums}
    missing_surface = sorted(surface_nodes - set(results.volume_von_mises))
    if missing_surface:
        raise RuntimeError(
            f"Code_Aster volume output is missing VMIS for {len(missing_surface)} surface nodes."
        )

    for element_id in study.metadata["compiler_inputs"]["element_ids"]:
        results.element_results[element_id] = ElementResult(
            element_id=element_id,
            forces_n1=np.full(6, np.nan),
            forces_n2=np.full(6, np.nan),
            max_von_mises=maximum,
        )
    return results


def _anchored_volume_nodes(
    model: TubaModel,
    analysis_mesh: AnalysisMesh,
    study: AnalysisStudy,
) -> set[str]:
    selected_ids = set(study.metadata["compiler_inputs"]["element_ids"])
    anchor_ids = {support.node for support in model.supports if support.type == "anchor"}
    planes: list[tuple[np.ndarray, np.ndarray, float]] = []
    for element_id in selected_ids:
        element = model.get_element(element_id)
        for anchor_id, other_id in ((element.n1, element.n2), (element.n2, element.n1)):
            if anchor_id not in anchor_ids:
                continue
            origin = np.asarray(model.nodes[anchor_id].coords, dtype=float)
            if element.type == "pipe_bend" and element.bend_geometry is not None:
                tangent = (
                    element.bend_geometry.start_tangent
                    if anchor_id == element.n1
                    else element.bend_geometry.end_tangent
                )
                inward = np.asarray(tangent, dtype=float) * (1.0 if anchor_id == element.n1 else -1.0)
                length = element.bend_geometry.radius * math.radians(element.bend_geometry.angle)
            else:
                inward = np.asarray(model.nodes[other_id].coords, dtype=float) - origin
                length = float(np.linalg.norm(inward))
            planes.append((origin, inward / np.linalg.norm(inward), max(length * 1.0e-7, 1.0e-9)))
    return {
        node_id
        for node_id, coords in analysis_mesh.nodes.items()
        if any(
            abs(float(np.dot(np.asarray(coords, dtype=float) - origin, normal))) <= tolerance
            for origin, normal, tolerance in planes
        )
    }


def _rows(path: Path) -> Iterator[dict[str, str]]:
    if not path.is_file():
        raise RuntimeError(f"Code_Aster volume result table is missing: {path.name}.")
    with path.open(encoding="utf-8", errors="replace", newline="") as stream:
        data_lines = (
            line for line in stream if line.strip() and not line.lstrip().startswith("#")
        )
        yield from csv.DictReader(data_lines)


def _volume_node_id(label: str) -> str:
    try:
        return f"VN{int(label.strip())}"
    except ValueError as exc:
        raise RuntimeError(f"Invalid Code_Aster volume node label {label!r}.") from exc


def _components(row: dict[str, str], names: tuple[str, ...]) -> list[float]:
    return [_finite(row, name) for name in names]


def _finite(row: dict[str, str], name: str) -> float:
    try:
        value = float(row.get(name, "").strip())
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"Invalid Code_Aster volume result component {name}={row.get(name)!r}.") from exc
    if not math.isfinite(value):
        raise RuntimeError(f"Non-finite Code_Aster volume result component {name}={value!r}.")
    return value
