"""Apply selected route candidates to a Tuba model."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np

from tuba.model import BendGeometry, TubaModel, make_bend_geometry, sample_bend_geometry
from tuba.patches import AddElement, AddNode, AddSupport, ModelPatch, ModelTransaction
from tuba.routing.types import PipeRouteCandidate, PipeRouteRequest, Point3D, RouteSegment


@dataclass(frozen=True)
class _CandidateGeometry:
    kind: Literal["straight", "bend"]
    start: Point3D
    end: Point3D
    bend_radius: float | None = None
    bend_angle: float | None = None
    bend_geometry: BendGeometry | None = None


def _candidate_geometry(
    model: TubaModel,
    candidate: PipeRouteCandidate,
    request: PipeRouteRequest,
) -> list[_CandidateGeometry]:
    if len(candidate.points) < 2:
        return []

    geometry: list[_CandidateGeometry] = []
    current = np.asarray(candidate.points[0], dtype=float)
    for idx in range(1, len(candidate.points) - 1):
        corner = np.asarray(candidate.points[idx], dtype=float)
        nxt = np.asarray(candidate.points[idx + 1], dtype=float)
        in_vec = corner - current
        out_vec = nxt - corner
        in_len = float(np.linalg.norm(in_vec))
        out_len = float(np.linalg.norm(out_vec))
        if in_len <= 1e-9 or out_len <= 1e-9:
            continue

        in_dir = in_vec / in_len
        out_dir = out_vec / out_len
        angle = _turn_angle_degrees(in_dir, out_dir)
        if angle <= 1e-6:
            continue

        radius = _bend_radius(model, request, _bend_segment_for_corner(candidate.segments, candidate.points[idx]))
        tangent = radius * math.tan(math.radians(angle) / 2.0)
        if tangent >= in_len - 1e-9 or tangent >= out_len - 1e-9:
            raise ValueError(
                f"Route bend at {candidate.points[idx]!r} needs tangent length "
                f"{tangent:.6g}, but adjacent straight lengths are {in_len:.6g} and {out_len:.6g}."
            )

        entry = corner - in_dir * tangent
        exit = corner + out_dir * tangent
        geometry.append(_CandidateGeometry("straight", _as_point(current), _as_point(entry)))
        geometry.append(
            _CandidateGeometry(
                "bend",
                _as_point(entry),
                _as_point(exit),
                bend_radius=radius,
                bend_angle=angle,
                bend_geometry=make_bend_geometry(
                    start=entry,
                    end=exit,
                    radius=radius,
                    angle=angle,
                    normal=np.cross(in_dir, out_dir),
                    start_tangent=in_dir,
                    end_tangent=out_dir,
                    generation_mode="autoroute",
                ),
            )
        )
        current = exit

    geometry.append(_CandidateGeometry("straight", _as_point(current), candidate.points[-1]))
    return geometry


def candidate_render_points(
    model: TubaModel,
    request: PipeRouteRequest | None,
    candidate: PipeRouteCandidate,
) -> list[Point3D]:
    """Expand a candidate into explicit bend geometry for route rendering."""
    if len(candidate.points) < 3:
        return list(candidate.points)
    if request is None:
        raise ValueError("Route visualization requires a PipeRouteRequest for bend geometry.")

    rendered: list[Point3D] = []
    for segment in _candidate_geometry(model, candidate, request):
        if not rendered:
            rendered.append(segment.start)
        if segment.kind == "straight":
            if np.linalg.norm(np.asarray(rendered[-1]) - np.asarray(segment.end)) > 1e-9:
                rendered.append(segment.end)
            continue
        if segment.bend_geometry is None:
            raise ValueError("Route visualization requires explicit bend geometry.")
        arc_points = sample_bend_geometry(
            segment.start,
            segment.bend_geometry,
            n_segments=max(6, int(np.ceil(segment.bend_angle / 10.0))),
        )
        rendered.extend(_as_point(point) for point in arc_points[1:])
    return rendered


def build_candidate_patch(
    model: TubaModel,
    candidate: PipeRouteCandidate,
    request: PipeRouteRequest,
    *,
    add_supports: bool = False,
    support_spacing: float | None = None,
) -> ModelPatch:
    """Build a mutation patch for a route candidate without mutating model."""
    if len(candidate.points) < 2:
        return ModelPatch(provenance={"request_id": request.id, "candidate_points": len(candidate.points)})

    operations = []
    current_point = np.asarray(candidate.points[0], dtype=float)
    current_name = "route_node_0"
    operations.append(AddNode(local_id=current_name, coords=candidate.points[0]))

    element_index = 0
    node_index = 1
    spacing = support_spacing if add_supports and support_spacing and support_spacing > 0.0 else None
    distance_since_support = 0.0
    station = 0.0

    def next_node_name() -> str:
        nonlocal node_index

        name = f"route_node_{node_index}"
        node_index += 1
        return name

    def add_straight_span(target_point: Point3D, target_name: str) -> None:
        nonlocal current_point, current_name, distance_since_support, element_index, station

        target = np.asarray(target_point, dtype=float)
        span = target - current_point
        length = float(np.linalg.norm(span))
        if length <= 1e-9:
            return

        direction = span / length
        segment_start_name = current_name
        distance_along = 0.0
        remaining = length

        while spacing is not None:
            distance_to_support = spacing - distance_since_support
            if distance_to_support <= 1e-9:
                distance_to_support = spacing
            if distance_to_support >= remaining - 1e-9:
                break

            distance_along += distance_to_support
            support_point = current_point + direction * distance_along
            support_name = next_node_name()
            operations.append(AddNode(local_id=support_name, coords=_as_point(support_point)))
            operations.append(
                AddElement(
                    local_id=f"route_element_{element_index}",
                    type="pipe_straight",
                    n1=segment_start_name,
                    n2=support_name,
                    section=request.section,
                    material=request.material,
                    route_id=request.id,
                    station_start=station,
                    station_end=station + distance_to_support,
                    id_prefix="pipe_str",
                )
            )
            element_index += 1
            station += distance_to_support
            operations.append(AddSupport(node=support_name, type="rest"))
            segment_start_name = support_name
            remaining = length - distance_along
            distance_since_support = 0.0

        operations.append(AddNode(local_id=target_name, coords=_as_point(target)))
        operations.append(
            AddElement(
                local_id=f"route_element_{element_index}",
                type="pipe_straight",
                n1=segment_start_name,
                n2=target_name,
                section=request.section,
                material=request.material,
                route_id=request.id,
                station_start=station,
                station_end=station + remaining,
                id_prefix="pipe_str",
            )
        )
        element_index += 1
        station += remaining
        distance_since_support += remaining
        if spacing is not None and distance_since_support >= spacing - 1e-9:
            distance_since_support = 0.0
        current_point = target
        current_name = target_name

    for segment in _candidate_geometry(model, candidate, request):
        if segment.kind == "straight":
            add_straight_span(segment.end, next_node_name())
            continue

        if segment.bend_radius is None or segment.bend_angle is None or segment.bend_geometry is None:
            raise ValueError("Route bends require explicit bend radius and geometry.")
        exit_name = next_node_name()
        operations.append(AddNode(local_id=exit_name, coords=segment.end))
        operations.append(
            AddElement(
                local_id=f"route_element_{element_index}",
                type="pipe_bend",
                n1=current_name,
                n2=exit_name,
                section=request.section,
                material=request.material,
                bend_radius=segment.bend_radius,
                bend_angle=segment.bend_angle,
                bend_geometry=segment.bend_geometry,
                route_id=request.id,
                station_start=station,
                station_end=station + segment.bend_radius * math.radians(abs(segment.bend_angle)),
                id_prefix="pipe_bend",
            )
        )
        element_index += 1
        station += segment.bend_radius * math.radians(abs(segment.bend_angle))
        current_point = np.asarray(segment.end, dtype=float)
        current_name = exit_name
        if spacing is not None:
            distance_since_support = 0.0

    return ModelPatch(
        operations=operations,
        provenance={"request_id": request.id, "candidate_points": len(candidate.points)},
    )


def apply_candidate_to_model(
    model: TubaModel,
    candidate: PipeRouteCandidate,
    request: PipeRouteRequest,
    *,
    add_supports: bool = False,
    support_spacing: float | None = None,
) -> list[str]:
    """Mutate *model* by adding the selected route and return created element ids."""
    patch = build_candidate_patch(
        model,
        candidate,
        request,
        add_supports=add_supports,
        support_spacing=support_spacing,
    )
    result = ModelTransaction(model).apply(patch)
    created = list(result.element_ids.values())
    candidate.metadata["created_element_ids"] = created
    return created


def _bend_segment_for_corner(segments: list[RouteSegment], point: Point3D) -> RouteSegment | None:
    target = np.asarray(point, dtype=float)
    for segment in segments:
        if segment.kind == "bend" and np.allclose(np.asarray(segment.start), target, atol=1e-6):
            return segment
    return None


def _bend_radius(
    model: TubaModel,
    request: PipeRouteRequest,
    bend_segment: RouteSegment | None,
) -> float:
    if bend_segment and bend_segment.bend_radius is not None:
        return bend_segment.bend_radius
    if request.constraints.min_bend_radius is not None:
        return request.constraints.min_bend_radius
    raise ValueError(
        "Route bends require an explicit bend radius. "
        "Set request.constraints.min_bend_radius or provide bend_radius on the bend segment."
    )


def _turn_angle_degrees(in_dir: np.ndarray, out_dir: np.ndarray) -> float:
    cosang = float(np.clip(np.dot(in_dir, out_dir), -1.0, 1.0))
    return round(math.degrees(math.acos(cosang)), 6)


def _as_point(point: np.ndarray) -> Point3D:
    return (float(point[0]), float(point[1]), float(point[2]))
