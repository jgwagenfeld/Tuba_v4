"""Prioritized multi-pipe routing."""

from __future__ import annotations

import copy
import math

import numpy as np

from tuba.model import TubaModel
from tuba.routing.adapter import apply_candidate_to_model
from tuba.routing.astar import GridRouter
from tuba.routing.types import (
    NetworkRouteRequest,
    NetworkRouteResult,
    PipeRouteCandidate,
    PipeRouteRequest,
    PipeRouteResult,
    RoutingGridSpec,
)


class NetworkRouter:
    def __init__(
        self,
        single_router: GridRouter | None = None,
        grid_spec: RoutingGridSpec | None = None,
    ) -> None:
        self.single_router = single_router or GridRouter(grid_spec=grid_spec)

    def route_network(
        self,
        model: TubaModel,
        request: NetworkRouteRequest,
    ) -> NetworkRouteResult:
        working = copy.deepcopy(model)
        pipe_results: dict[str, PipeRouteResult] = {}
        accepted: dict[str, PipeRouteCandidate] = {}
        diagnostics: list[str] = []
        ordered_requests = self._order_requests(model, request)
        request_by_id = {pipe_request.id: pipe_request for pipe_request in ordered_requests}

        for pipe_request in ordered_requests:
            result = self.single_router.route(working, pipe_request)
            pipe_results[pipe_request.id] = result
            if result.selected is None:
                diagnostics.append(f"No route accepted for {pipe_request.id}.")
                continue
            accepted[pipe_request.id] = result.selected
            apply_candidate_to_model(working, result.selected, pipe_request)

        unresolved = detect_candidate_conflicts(
            accepted,
            model=model,
            requests=request_by_id,
        )
        if unresolved and request.max_reroute_attempts > 0:
            unresolved = self._repair_conflicts(
                model=model,
                request=request,
                ordered_requests=ordered_requests,
                request_by_id=request_by_id,
                pipe_results=pipe_results,
                accepted=accepted,
                unresolved=unresolved,
                diagnostics=diagnostics,
            )
        for conflict in unresolved:
            p1, p2 = conflict["pipes"]
            if conflict.get("type") == "reserved_envelope":
                diagnostics.append(
                    f"unresolved reserved envelope conflict between {p1} and {p2}: "
                    f"route {conflict['route_id']} segment {conflict['route_segment']} intrudes into "
                    f"{conflict['reserved_envelope_owner']} reserved envelope."
                )
            else:
                diagnostics.append(
                    f"unresolved route conflict between {p1} and {p2}: "
                    f"distance {conflict['distance']:.6g} < required {conflict['required_clearance']:.6g}."
                )

        return NetworkRouteResult(
            request=request,
            pipe_results=pipe_results,
            accepted_candidates=accepted,
            unresolved_conflicts=unresolved,
            diagnostics=diagnostics,
        )

    @staticmethod
    def _order_requests(model: TubaModel, request: NetworkRouteRequest) -> list[PipeRouteRequest]:
        requests = list(request.pipe_requests)
        if request.order_strategy == "given":
            return requests
        if request.order_strategy == "large_bore_first":
            return sorted(
                requests,
                key=lambda r: model.sections[r.section].OD if r.section in model.sections else 0.0,
                reverse=True,
            )
        if request.order_strategy == "critical_first":
            return sorted(requests, key=lambda r: bool(r.metadata.get("critical")), reverse=True)
        if request.order_strategy == "least_flexible_first":
            return sorted(requests, key=lambda r: _endpoint_distance(r))
        return requests

    def _repair_conflicts(
        self,
        *,
        model: TubaModel,
        request: NetworkRouteRequest,
        ordered_requests: list[PipeRouteRequest],
        request_by_id: dict[str, PipeRouteRequest],
        pipe_results: dict[str, PipeRouteResult],
        accepted: dict[str, PipeRouteCandidate],
        unresolved: list[dict],
        diagnostics: list[str],
    ) -> list[dict]:
        ordered_ids = [pipe_request.id for pipe_request in ordered_requests]
        for attempt in range(request.max_reroute_attempts):
            repaired_any = False
            for conflict in list(unresolved):
                target_id = conflict["pipes"][1]
                if target_id not in accepted:
                    continue
                pipe_request = request_by_id[target_id]
                repair_model = copy.deepcopy(model)
                for other_id in ordered_ids:
                    if other_id == target_id or other_id not in accepted:
                        continue
                    apply_candidate_to_model(repair_model, accepted[other_id], request_by_id[other_id])

                result = self.single_router.route(repair_model, pipe_request)
                pipe_results[target_id] = result
                if result.selected is None:
                    continue
                if result.selected.points == accepted[target_id].points:
                    continue

                trial = dict(accepted)
                trial[target_id] = result.selected
                trial_unresolved = detect_candidate_conflicts(
                    trial,
                    model=model,
                    requests=request_by_id,
                )
                if len(trial_unresolved) > len(unresolved):
                    continue

                accepted[target_id] = result.selected
                unresolved = trial_unresolved
                diagnostics.append(f"rerouted {target_id} on network repair attempt {attempt + 1}.")
                repaired_any = True
                if not unresolved:
                    return []
            if not repaired_any:
                break
        return unresolved


def _endpoint_distance(request: PipeRouteRequest) -> float:
    a = request.start.point
    b = request.goal.point
    return math.sqrt(sum((b[i] - a[i]) ** 2 for i in range(3)))


def detect_candidate_conflicts(
    candidates: dict[str, PipeRouteCandidate],
    *,
    clearance: float = 0.0,
    model: TubaModel | None = None,
    requests: dict[str, PipeRouteRequest] | None = None,
) -> list[dict]:
    """Detect centerline conflicts between accepted route candidates."""
    conflicts: list[dict] = []
    items = list(candidates.items())
    for left_idx in range(len(items)):
        id_a, cand_a = items[left_idx]
        for right_idx in range(left_idx + 1, len(items)):
            id_b, cand_b = items[right_idx]
            required = _required_clearance(id_a, id_b, clearance, model, requests)
            pair_conflict = False
            for seg_a_idx, (a0, a1) in enumerate(zip(cand_a.points, cand_a.points[1:])):
                for seg_b_idx, (b0, b1) in enumerate(zip(cand_b.points, cand_b.points[1:])):
                    dist, pa, pb = _segment_distance(
                        np.asarray(a0, dtype=float),
                        np.asarray(a1, dtype=float),
                        np.asarray(b0, dtype=float),
                        np.asarray(b1, dtype=float),
                    )
                    if dist >= required - 1e-9:
                        continue
                    if _is_shared_endpoint_only(np.asarray(a0), np.asarray(a1), np.asarray(b0), np.asarray(b1), pa, pb):
                        continue
                    conflicts.append(
                        {
                            "pipes": (id_a, id_b),
                            "segments": (seg_a_idx, seg_b_idx),
                            "distance": float(dist),
                            "required_clearance": float(required),
                            "point_a": (float(pa[0]), float(pa[1]), float(pa[2])),
                            "point_b": (float(pb[0]), float(pb[1]), float(pb[2])),
                        }
                    )
                    pair_conflict = True
                    break
                if pair_conflict:
                    break
            if pair_conflict:
                continue
            reserved_conflict = _reserved_envelope_conflict(id_a, cand_a, id_b, cand_b)
            if reserved_conflict is not None:
                conflicts.append(reserved_conflict)
    return conflicts


def _reserved_envelope_conflict(
    id_a: str,
    cand_a: PipeRouteCandidate,
    id_b: str,
    cand_b: PipeRouteCandidate,
) -> dict | None:
    conflict = _route_intrudes_reserved_envelope(id_a, cand_a, id_b, cand_b)
    if conflict is not None:
        return conflict
    return _route_intrudes_reserved_envelope(id_b, cand_b, id_a, cand_a)


def _route_intrudes_reserved_envelope(
    envelope_owner_id: str,
    envelope_owner: PipeRouteCandidate,
    route_id: str,
    route: PipeRouteCandidate,
) -> dict | None:
    envelope = envelope_owner.metadata.get("reserved_envelope")
    bounds = _reserved_envelope_bounds(envelope)
    if bounds is None:
        return None

    min_point, max_point = bounds
    for segment_idx, (start, end) in enumerate(zip(route.points, route.points[1:])):
        start_arr = np.asarray(start, dtype=float)
        end_arr = np.asarray(end, dtype=float)
        if not _segment_intrudes_aabb(start_arr, end_arr, min_point, max_point):
            continue
        return {
            "type": "reserved_envelope",
            "pipes": (envelope_owner_id, route_id),
            "segments": (None, segment_idx),
            "reserved_envelope_owner": envelope_owner_id,
            "route_id": route_id,
            "route_segment": segment_idx,
            "envelope": {
                "min_point": _point_tuple(min_point),
                "max_point": _point_tuple(max_point),
            },
            "segment_start": _point_tuple(start_arr),
            "segment_end": _point_tuple(end_arr),
        }
    return None


def _reserved_envelope_bounds(envelope: object) -> tuple[np.ndarray, np.ndarray] | None:
    if not isinstance(envelope, dict):
        return None
    try:
        min_point = np.asarray(envelope["min_point"], dtype=float)
        max_point = np.asarray(envelope["max_point"], dtype=float)
    except (KeyError, TypeError, ValueError):
        return None
    if min_point.shape != (3,) or max_point.shape != (3,):
        return None
    if not np.all(np.isfinite(min_point)) or not np.all(np.isfinite(max_point)):
        return None
    return np.minimum(min_point, max_point), np.maximum(min_point, max_point)


def _segment_intrudes_aabb(
    start: np.ndarray,
    end: np.ndarray,
    min_point: np.ndarray,
    max_point: np.ndarray,
) -> bool:
    eps = 1e-9
    inner_min = min_point + eps
    inner_max = max_point - eps
    if np.any(inner_min > inner_max):
        return False

    direction = end - start
    t_min = 0.0
    t_max = 1.0
    for axis in range(3):
        delta = float(direction[axis])
        if abs(delta) <= 1e-12:
            if start[axis] <= inner_min[axis] or start[axis] >= inner_max[axis]:
                return False
            continue
        t1 = float((inner_min[axis] - start[axis]) / delta)
        t2 = float((inner_max[axis] - start[axis]) / delta)
        axis_min = min(t1, t2)
        axis_max = max(t1, t2)
        t_min = max(t_min, axis_min)
        t_max = min(t_max, axis_max)
        if t_min > t_max:
            return False
    return t_min <= 1.0 and t_max >= 0.0


def _required_clearance(
    id_a: str,
    id_b: str,
    fallback: float,
    model: TubaModel | None,
    requests: dict[str, PipeRouteRequest] | None,
) -> float:
    if model is None or requests is None or id_a not in requests or id_b not in requests:
        if fallback <= 0.0:
            raise ValueError(
                "Candidate conflict detection requires model/request context or an explicit positive clearance."
            )
        return fallback
    req_a = requests[id_a]
    req_b = requests[id_b]
    sec_a = model.sections[req_a.section]
    sec_b = model.sections[req_b.section]
    return (
        sec_a.OD / 2.0
        + sec_b.OD / 2.0
        + req_a.constraints.insulation_thickness
        + req_b.constraints.insulation_thickness
        + req_a.constraints.clearance
        + req_b.constraints.clearance
    )


def _segment_distance(
    p1: np.ndarray,
    q1: np.ndarray,
    p2: np.ndarray,
    q2: np.ndarray,
) -> tuple[float, np.ndarray, np.ndarray]:
    u = q1 - p1
    v = q2 - p2
    w = p1 - p2
    a = float(np.dot(u, u))
    b = float(np.dot(u, v))
    c = float(np.dot(v, v))
    d = float(np.dot(u, w))
    e = float(np.dot(v, w))
    denom = a * c - b * b
    small = 1e-12

    if a <= small and c <= small:
        return float(np.linalg.norm(p1 - p2)), p1, p2
    if a <= small:
        t = float(np.clip(e / c, 0.0, 1.0))
        cp1 = p1
        cp2 = p2 + t * v
        return float(np.linalg.norm(cp1 - cp2)), cp1, cp2
    if c <= small:
        s = float(np.clip(-d / a, 0.0, 1.0))
        cp1 = p1 + s * u
        cp2 = p2
        return float(np.linalg.norm(cp1 - cp2)), cp1, cp2

    if denom <= small:
        s = 0.0
    else:
        s = float(np.clip((b * e - c * d) / denom, 0.0, 1.0))
    t = float(np.clip((b * s + e) / c, 0.0, 1.0))
    s = float(np.clip((b * t - d) / a, 0.0, 1.0))
    cp1 = p1 + s * u
    cp2 = p2 + t * v
    return float(np.linalg.norm(cp1 - cp2)), cp1, cp2


def _is_shared_endpoint_only(
    a0: np.ndarray,
    a1: np.ndarray,
    b0: np.ndarray,
    b1: np.ndarray,
    pa: np.ndarray,
    pb: np.ndarray,
) -> bool:
    if not np.allclose(pa, pb, atol=1e-9):
        return False
    shared = any(
        np.allclose(pa, endpoint, atol=1e-9)
        for endpoint in (a0, a1)
    ) and any(
        np.allclose(pb, endpoint, atol=1e-9)
        for endpoint in (b0, b1)
    )
    if not shared:
        return False
    da = _safe_unit(a1 - a0)
    db = _safe_unit(b1 - b0)
    return abs(float(np.dot(da, db))) < 0.999


def _safe_unit(vec: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vec))
    if norm <= 1e-12:
        return np.zeros(3)
    return vec / norm


def _point_tuple(point: np.ndarray) -> tuple[float, float, float]:
    return (float(point[0]), float(point[1]), float(point[2]))
