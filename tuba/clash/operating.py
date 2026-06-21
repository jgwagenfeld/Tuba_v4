"""Operating-state clash detection built from deformed envelopes."""

from __future__ import annotations

from typing import Iterable

import numpy as np

from tuba.analysis.mesh import AnalysisMesh
from tuba.analysis.results import ResultState
from tuba.analysis.states import GeometryState
from tuba.clash.engine import _segment_aabb_distance
from tuba.clash.types import ClashResult
from tuba.geometry.deformed import DeformedEnvelope, build_deformed_envelopes
from tuba.geometry.spatial import Bounds, SpatialIndex, union_bounds
from tuba.model import Element, TubaModel
from tuba.refs import EntityRef


def check_operating_state(
    model: TubaModel,
    *,
    cold_state: GeometryState,
    operating_state: GeometryState,
    result_state: ResultState,
    envelope_type: str = "insulation",
    clearance_m: float = 0.0,
    analysis_mesh: AnalysisMesh | None = None,
) -> list[ClashResult]:
    if operating_state.purpose == "visualization":
        raise ValueError("Visualization GeometryState cannot drive engineering operating clash checks.")
    if cold_state.state_type != "cold":
        raise ValueError("cold_state must have state_type='cold'.")

    operating_envelopes = build_deformed_envelopes(
        model=model,
        result_state=result_state,
        geometry_state=operating_state,
        envelope_type=envelope_type,
        clearance_m=clearance_m,
        analysis_mesh=analysis_mesh,
    )
    elements_by_id = {element.id: element for element in model.elements}
    envelopes_by_element_id = {envelope.entity.id: envelope for envelope in operating_envelopes}
    obstacles_by_id = {
        _obstacle_id(obstacle, index): obstacle
        for index, obstacle in enumerate(model.obstacles)
        if _obstacle_bounds(obstacle) is not None
    }
    candidate_pairs = candidate_obstacle_pairs_for_envelopes(model=model, envelopes=operating_envelopes)
    clashes: list[ClashResult] = []
    for element_id, obstacle_id in candidate_pairs:
        envelope = envelopes_by_element_id.get(element_id)
        obstacle = obstacles_by_id.get(obstacle_id)
        if envelope is None or obstacle is None:
            continue
        element = elements_by_id.get(envelope.entity.id)
        if element is None:
            continue
        clashes.extend(
            _check_envelope_obstacle(
                model=model,
                element=element,
                envelope=envelope,
                obstacle=obstacle,
                operating_state=operating_state,
                result_state=result_state,
                envelope_type=envelope_type,
            )
        )
    return clashes


def candidate_obstacle_pairs_for_envelopes(
    *,
    model: TubaModel,
    envelopes: tuple[DeformedEnvelope, ...],
) -> list[tuple[str, str]]:
    obstacle_index = _obstacle_spatial_index(model.obstacles)
    elements_by_id = {element.id: element for element in model.elements}
    query_bounds: list[tuple[str, Bounds]] = []
    for envelope in envelopes:
        element = elements_by_id.get(envelope.entity.id)
        bounds = envelope.bounds
        if element is not None:
            bounds = union_bounds(bounds, _cold_polyline_bounds(model, element, envelope.radius_m))
        query_bounds.append((envelope.entity.id, bounds))
    return obstacle_index.candidate_pairs(query_bounds)


def _check_envelope_obstacle(
    *,
    model: TubaModel,
    element: Element,
    envelope: DeformedEnvelope,
    obstacle: dict,
    operating_state: GeometryState,
    result_state: ResultState,
    envelope_type: str,
) -> Iterable[ClashResult]:
    if obstacle.get("type") not in ("cuboid", "cylinder"):
        return []
    if obstacle.get("min_point") is None or obstacle.get("max_point") is None:
        return []

    lo = np.asarray(obstacle["min_point"], dtype=float)
    hi = np.asarray(obstacle["max_point"], dtype=float)
    radius = envelope.radius_m
    cold_polyline = _cold_polyline(model, element)
    cold_distance, _cold_location = _polyline_aabb_distance(cold_polyline, lo, hi)
    operating_distance, operating_location = _polyline_aabb_distance(envelope.polyline, lo, hi)

    cold_overlaps = cold_distance < radius
    operating_overlaps = operating_distance < radius
    if not cold_overlaps and not operating_overlaps:
        return []

    severity = _classify(cold_overlaps, operating_overlaps, envelope_type)
    penetration = max(radius - operating_distance, 0.0)
    obstacle_id = obstacle.get("id", "obstacle")
    return [
        ClashResult(
            left=EntityRef("element", element.id),
            right=EntityRef("obstacle", obstacle_id),
            severity=severity,
            distance_m=operating_distance,
            penetration_m=penetration,
            location=tuple(float(value) for value in operating_location),
            diagnostics=list(envelope.diagnostics),
            metadata={
                "geometry_state": operating_state.id,
                "load_case": operating_state.load_case,
                "result_state_id": result_state.id,
                "displacement_source": result_state.id,
                "envelope_type": envelope_type,
                "cold_distance_m": cold_distance,
                "operating_distance_m": operating_distance,
                "introduced_by_deformation": (not cold_overlaps) and operating_overlaps,
                "safety_factor": operating_state.safety_factor,
            },
        )
    ]


def _classify(cold_overlaps: bool, operating_overlaps: bool, envelope_type: str) -> str:
    suffix = "clearance" if envelope_type == "clearance" else "hard"
    if operating_overlaps and not cold_overlaps:
        return f"operating_only_{suffix}"
    if operating_overlaps:
        return f"operating_{suffix}"
    return "resolved_in_operating"


def _cold_polyline(model: TubaModel, element: Element) -> tuple[tuple[float, float, float], ...]:
    p1 = tuple(float(value) for value in model.nodes[element.n1].coords)
    p2 = tuple(float(value) for value in model.nodes[element.n2].coords)
    return (p1, p2)


def _cold_polyline_bounds(model: TubaModel, element: Element, radius: float) -> Bounds:
    points = np.asarray(_cold_polyline(model, element), dtype=float)
    lo = points.min(axis=0) - radius
    hi = points.max(axis=0) + radius
    return tuple(float(value) for value in (*lo, *hi))


def _obstacle_spatial_index(obstacles: list[dict]) -> SpatialIndex[str]:
    items: list[tuple[str, Bounds]] = []
    for index, obstacle in enumerate(obstacles):
        bounds = _obstacle_bounds(obstacle)
        if bounds is not None:
            items.append((_obstacle_id(obstacle, index), bounds))
    return SpatialIndex.from_bounds(items)


def _obstacle_bounds(obstacle: dict) -> Bounds | None:
    if obstacle.get("type") not in ("cuboid", "cylinder"):
        return None
    if obstacle.get("min_point") is None or obstacle.get("max_point") is None:
        return None
    lo = np.asarray(obstacle["min_point"], dtype=float)
    hi = np.asarray(obstacle["max_point"], dtype=float)
    lower = np.minimum(lo, hi)
    upper = np.maximum(lo, hi)
    return tuple(float(value) for value in (*lower, *upper))


def _obstacle_id(obstacle: dict, index: int) -> str:
    return str(obstacle.get("id") or f"obstacle_{index}")


def _polyline_aabb_distance(
    polyline: tuple[tuple[float, float, float], ...],
    lo: np.ndarray,
    hi: np.ndarray,
) -> tuple[float, np.ndarray]:
    best_distance = float("inf")
    best_location = np.asarray(polyline[0], dtype=float)
    for start, end in zip(polyline, polyline[1:]):
        distance, location = _segment_aabb_distance(np.asarray(start, dtype=float), np.asarray(end, dtype=float), lo, hi)
        if distance < best_distance:
            best_distance = distance
            best_location = location
    return best_distance, best_location
