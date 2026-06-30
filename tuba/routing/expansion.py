"""Expansion-loop route candidate generation."""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from tuba.model import TubaModel
from tuba.routing.postprocess import build_segments, validate_bend_geometry
from tuba.routing.thermal import ExpansionLoopSpec
from tuba.routing.types import PipeRouteCandidate, PipeRouteRequest, Point3D, RoutingConstraints


_PLANE_AXES = {
    "xy": (0, 1),
    "xz": (0, 2),
    "yz": (1, 2),
}


@dataclass(frozen=True)
class ExpansionLoopGenerator:
    loop_specs: tuple[ExpansionLoopSpec, ...]

    def generate(self, model: TubaModel, request: PipeRouteRequest) -> list[PipeRouteCandidate]:
        if request.thermal_requirements is None:
            return []

        candidates: list[PipeRouteCandidate] = []
        for spec in self.loop_specs:
            if spec.family == "u_loop":
                candidates.append(self._u_loop_candidate(model, request, spec))
        return candidates

    def _u_loop_candidate(
        self,
        model: TubaModel,
        request: PipeRouteRequest,
        spec: ExpansionLoopSpec,
    ) -> PipeRouteCandidate:
        start = np.asarray(request.start.point, dtype=float)
        goal = np.asarray(request.goal.point, dtype=float)
        axis = goal - start
        if np.linalg.norm(axis) <= 1e-12:
            raise ValueError("Expansion loop endpoints must be distinct.")

        effective_constraints = _effective_constraints(model, request)
        envelope_radius = _reserved_envelope_radius(model, request, spec)
        if _plane_projection_norm(axis, spec.plane) <= 1e-12:
            points = [_tuple(start), _tuple(goal)]
            return _candidate(
                request,
                spec,
                points,
                effective_constraints,
                envelope_radius,
                [
                    "Expansion loop plane/direction mismatch: "
                    f"endpoint direction has no usable projection in plane {spec.plane}."
                ],
            )

        width_axis, depth_axis = _loop_axes(axis, spec.plane)
        width_direction = 1.0 if axis[width_axis] >= 0.0 else -1.0
        mid = start + 0.5 * axis
        half_width = float(spec.width_m) / 2.0

        width_offset = np.zeros(3, dtype=float)
        width_offset[width_axis] = half_width * width_direction
        depth_offset = np.zeros(3, dtype=float)
        depth_offset[depth_axis] = float(spec.depth_m)

        p1 = mid - width_offset
        p2 = p1 + depth_offset
        p3 = mid + width_offset + depth_offset
        p4 = mid + width_offset

        points = [_tuple(start), _tuple(p1), _tuple(p2), _tuple(p3), _tuple(p4), _tuple(goal)]
        diagnostics = validate_bend_geometry(points, effective_constraints)
        return _candidate(request, spec, points, effective_constraints, envelope_radius, diagnostics)


def _candidate(
    request: PipeRouteRequest,
    spec: ExpansionLoopSpec,
    points: list[Point3D],
    constraints: RoutingConstraints,
    envelope_radius: float,
    diagnostics: list[str],
) -> PipeRouteCandidate:
    return PipeRouteCandidate(
        request_id=request.id,
        points=points,
        segments=build_segments(points, constraints),
        cost=0.0,
        cost_breakdown={},
        diagnostics=diagnostics,
        is_valid=not diagnostics,
        metadata={
            "route_family": spec.family,
            "expansion_loop": {
                "width_m": spec.width_m,
                "depth_m": spec.depth_m,
                "plane": spec.plane,
            },
            "reserved_envelope": _bounds(points, envelope_radius),
        },
    )


def _effective_constraints(model: TubaModel, request: PipeRouteRequest) -> RoutingConstraints:
    if request.constraints.min_bend_radius is not None:
        return request.constraints
    return replace(request.constraints, min_bend_radius=model.sections[request.section].OD * 1.5)


def _reserved_envelope_radius(model: TubaModel, request: PipeRouteRequest, spec: ExpansionLoopSpec) -> float:
    section = model.sections[request.section]
    return (
        float(section.OD) / 2.0
        + float(request.constraints.insulation_thickness)
        + float(request.constraints.clearance)
        + float(spec.min_clearance_m)
    )


def _loop_axes(axis: np.ndarray, plane: str) -> tuple[int, int]:
    plane_axes = _PLANE_AXES[plane]
    first, second = plane_axes
    if abs(axis[second]) > abs(axis[first]):
        return second, first
    return first, second


def _plane_projection_norm(axis: np.ndarray, plane: str) -> float:
    first, second = _PLANE_AXES[plane]
    return float(np.linalg.norm(axis[[first, second]]))


def _tuple(point: np.ndarray) -> Point3D:
    return (float(point[0]), float(point[1]), float(point[2]))


def _bounds(points: list[Point3D], clearance: float) -> dict[str, Point3D]:
    arr = np.asarray(points, dtype=float)
    lo = arr.min(axis=0) - float(clearance)
    hi = arr.max(axis=0) + float(clearance)
    return {"min_point": _tuple(lo), "max_point": _tuple(hi)}
