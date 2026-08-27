"""Internal clash detection engines."""

from __future__ import annotations

from typing import Iterable

import numpy as np

from tuba.clash.types import ClashResult
from tuba.model import TubaModel
from tuba.analysis.mesh import AnalysisMesh
from tuba.analysis.results import ResultState
from tuba.analysis.states import GeometryState
from tuba.physical import physical_properties_for_element
from tuba.refs import EntityRef


class ClashEngine:
    """Analytic clash engine for model elements against cuboid/cylinder obstacles.

    This is the default clash engine used across rules, routing, and
    visualization. It computes segment-vs-AABB distances analytically and
    returns structured :class:`ClashResult` objects, so it has no trimesh / IFC
    / viewer dependency.

    Model clash checks cover analytic cuboid/cylinder obstacles; operating
    checks use the current result and geometry states. Other obstacle types are
    intentionally outside this review path.
    """

    def check_model(self, model: TubaModel, *, clearance_m: float = 0.0) -> list[ClashResult]:
        clashes: list[ClashResult] = []
        for elem in model.elements:
            try:
                props = physical_properties_for_element(model, elem)
            except ValueError:
                continue
            p1 = model.nodes[elem.n1].coords
            p2 = model.nodes[elem.n2].coords
            for obs in model.obstacles:
                clashes.extend(
                    self._check_element_obstacle(
                        elem_id=elem.id,
                        p1=p1,
                        p2=p2,
                        hard_radius=props.effective_radius_m,
                        clearance_radius=props.effective_radius_m + clearance_m,
                        obstacle=obs,
                    )
                )
        return clashes

    def check_operating_state(
        self,
        model: TubaModel,
        *,
        cold_state: GeometryState,
        operating_state: GeometryState,
        result_state: ResultState,
        envelope_type: str = "insulation",
        clearance_m: float = 0.0,
        analysis_mesh: AnalysisMesh | None = None,
    ) -> list[ClashResult]:
        from tuba.clash.operating import check_operating_state

        return check_operating_state(
            model,
            cold_state=cold_state,
            operating_state=operating_state,
            result_state=result_state,
            envelope_type=envelope_type,
            clearance_m=clearance_m,
            analysis_mesh=analysis_mesh,
        )

    def _check_element_obstacle(
        self,
        *,
        elem_id: str,
        p1: np.ndarray,
        p2: np.ndarray,
        hard_radius: float,
        clearance_radius: float,
        obstacle: dict,
    ) -> Iterable[ClashResult]:
        obs_type = obstacle.get("type")
        obs_id = obstacle.get("id", "obstacle")
        if obs_type not in ("cuboid", "cylinder"):
            return []
        if obstacle.get("min_point") is None or obstacle.get("max_point") is None:
            return []

        lo = np.asarray(obstacle["min_point"], dtype=float)
        hi = np.asarray(obstacle["max_point"], dtype=float)
        distance, location = _segment_aabb_distance(p1, p2, lo, hi)
        if distance >= clearance_radius:
            return []

        severity = "hard" if distance < hard_radius else "clearance"
        penetration = max(clearance_radius - distance, 0.0)
        return [
            ClashResult(
                left=EntityRef("element", elem_id),
                right=EntityRef("obstacle", obs_id),
                severity=severity,
                distance_m=distance,
                penetration_m=penetration,
                location=tuple(float(value) for value in location),
            )
        ]


def _segment_aabb_distance(
    p1: np.ndarray,
    p2: np.ndarray,
    lo: np.ndarray,
    hi: np.ndarray,
) -> tuple[float, np.ndarray]:
    lower = np.minimum(lo, hi)
    upper = np.maximum(lo, hi)
    lo = lower
    hi = upper
    if _segment_intersects_aabb(p1, p2, lo, hi):
        return 0.0, (p1 + p2) / 2.0

    direction = p2 - p1
    left = 0.0
    right = 1.0
    for _ in range(72):
        m1 = left + (right - left) / 3.0
        m2 = right - (right - left) / 3.0
        d1 = _point_aabb_distance(p1 + direction * m1, lo, hi)
        d2 = _point_aabb_distance(p1 + direction * m2, lo, hi)
        if d1 < d2:
            right = m2
        else:
            left = m1
    t = (left + right) / 2.0
    point = p1 + direction * t
    return _point_aabb_distance(point, lo, hi), point


def _segment_intersects_aabb(p1: np.ndarray, p2: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> bool:
    t_min = 0.0
    t_max = 1.0
    direction = p2 - p1
    for axis in range(3):
        if abs(direction[axis]) < 1e-12:
            if p1[axis] < lo[axis] or p1[axis] > hi[axis]:
                return False
            continue
        inv = 1.0 / direction[axis]
        t1 = (lo[axis] - p1[axis]) * inv
        t2 = (hi[axis] - p1[axis]) * inv
        t_low = min(t1, t2)
        t_high = max(t1, t2)
        t_min = max(t_min, t_low)
        t_max = min(t_max, t_high)
        if t_min > t_max:
            return False
    return True


def _point_aabb_distance(point: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> float:
    below = np.maximum(lo - point, 0.0)
    above = np.maximum(point - hi, 0.0)
    return float(np.linalg.norm(below + above))
