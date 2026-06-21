"""Path simplification and route-segment construction."""

from __future__ import annotations

import math

import numpy as np

from tuba.routing.types import Point3D, RouteSegment, RoutingConstraints


def simplify_grid_path(points: list[Point3D]) -> list[Point3D]:
    """Remove collinear intermediate points from a grid path."""
    if len(points) <= 2:
        return list(points)
    simplified = [points[0]]
    prev_dir = _direction(points[0], points[1])
    for idx in range(1, len(points) - 1):
        next_dir = _direction(points[idx], points[idx + 1])
        if next_dir != prev_dir:
            simplified.append(points[idx])
        prev_dir = next_dir
    simplified.append(points[-1])
    return simplified


def validate_bend_geometry(points: list[Point3D], constraints: RoutingConstraints) -> list[str]:
    diagnostics: list[str] = []
    if constraints.max_length is not None and _path_length(points) > constraints.max_length:
        diagnostics.append(f"Route exceeds max_length={constraints.max_length}.")
    if constraints.max_bends is not None:
        bends = max(len(points) - 2, 0)
        if bends > constraints.max_bends:
            diagnostics.append(f"Route has {bends} bends, exceeding max_bends={constraints.max_bends}.")
    if constraints.min_bend_radius is not None:
        for idx in range(1, len(points) - 1):
            angle = _turn_angle(points[idx - 1], points[idx], points[idx + 1])
            if angle <= 1e-6:
                continue
            tangent = constraints.min_bend_radius * math.tan(math.radians(angle) / 2.0)
            before = _distance(points[idx - 1], points[idx])
            after = _distance(points[idx], points[idx + 1])
            if tangent >= before - 1e-9 or tangent >= after - 1e-9:
                diagnostics.append(
                    "Insufficient straight length for bend tangent at "
                    f"{points[idx]}: needs {tangent:.6g}, has {before:.6g} and {after:.6g}."
                )
    if constraints.min_straight_between_bends > 0:
        for a, b in zip(points, points[1:]):
            if _distance(a, b) < constraints.min_straight_between_bends:
                diagnostics.append("Route contains a straight segment shorter than min_straight_between_bends.")
                break
    return diagnostics


def build_segments(points: list[Point3D], constraints: RoutingConstraints) -> list[RouteSegment]:
    """Build straight segments with zero-length bend markers at direction changes."""
    if len(points) < 2:
        return []
    segments: list[RouteSegment] = []
    bend_radius = constraints.min_bend_radius
    for idx in range(len(points) - 1):
        if idx > 0:
            angle = _turn_angle(points[idx - 1], points[idx], points[idx + 1])
            if angle > 1e-6:
                segments.append(
                    RouteSegment(
                        start=points[idx],
                        end=points[idx],
                        kind="bend",
                        bend_radius=bend_radius,
                        bend_angle=angle,
                    )
                )
        segments.append(RouteSegment(start=points[idx], end=points[idx + 1], kind="straight"))
    return segments


def _direction(a: Point3D, b: Point3D) -> tuple[int, int, int]:
    vec = np.asarray(b) - np.asarray(a)
    norm = np.linalg.norm(vec)
    if norm <= 1e-12:
        return (0, 0, 0)
    unit = vec / norm
    return tuple(int(round(v)) for v in unit)


def _turn_angle(a: Point3D, b: Point3D, c: Point3D) -> float:
    v1 = np.asarray(b) - np.asarray(a)
    v2 = np.asarray(c) - np.asarray(b)
    n1 = np.linalg.norm(v1)
    n2 = np.linalg.norm(v2)
    if n1 <= 1e-12 or n2 <= 1e-12:
        return 0.0
    cosang = float(np.clip(np.dot(v1 / n1, v2 / n2), -1.0, 1.0))
    return round(math.degrees(math.acos(cosang)), 6)


def _distance(a: Point3D, b: Point3D) -> float:
    return float(np.linalg.norm(np.asarray(b) - np.asarray(a)))


def _path_length(points: list[Point3D]) -> float:
    return sum(_distance(a, b) for a, b in zip(points, points[1:]))
