"""Plain section loops and straight-member surface meshes."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from tuba.geometry.profiles import profile_for_section


@dataclass(frozen=True)
class SurfaceMesh:
    vertices: tuple[tuple[float, float, float], ...]
    faces: tuple[tuple[int, int, int], ...]


def section_loops(section, *, n_sides: int = 16) -> tuple[tuple[tuple[float, float], ...], ...]:
    """Return the outer section loop followed by an optional inner void."""
    if n_sides < 3:
        raise ValueError("Circular section meshes require at least three sides.")
    profile = profile_for_section(section)
    dimensions = profile.dimensions

    if profile.kind == "pipe":
        loops = [_circle(float(dimensions["OD"]) / 2.0, n_sides)]
        inner_radius = float(dimensions["ID"]) / 2.0
        if inner_radius > 0.0:
            loops.append(_circle(inner_radius, n_sides))
    elif profile.kind == "bar":
        outer_radius = float(dimensions["OD"]) / 2.0
        loops = [_circle(outer_radius, n_sides)]
        wall = float(dimensions["WT"])
        if 0.0 < wall < outer_radius:
            loops.append(_circle(outer_radius - wall, n_sides))
    elif profile.kind == "cable":
        loops = [_circle(float(dimensions["radius"]), n_sides)]
    elif profile.kind == "rectangular":
        height_y = float(dimensions["height_y"])
        height_z = float(dimensions["height_z"])
        loops = [_rectangle(height_y, height_z)]
        inner_y = height_y - 2.0 * float(dimensions["thickness_y"])
        inner_z = height_z - 2.0 * float(dimensions["thickness_z"])
        if inner_y < height_y and inner_z < height_z and inner_y > 0.0 and inner_z > 0.0:
            loops.append(_rectangle(inner_y, inner_z))
    elif profile.kind == "ibeam":
        height = float(dimensions["H"])
        width = float(dimensions["B"])
        web = float(dimensions["Tw"])
        flange = float(dimensions["Tf"])
        loops = [[
            (-height / 2.0, -width / 2.0),
            (-height / 2.0, width / 2.0),
            (-height / 2.0 + flange, width / 2.0),
            (-height / 2.0 + flange, web / 2.0),
            (height / 2.0 - flange, web / 2.0),
            (height / 2.0 - flange, width / 2.0),
            (height / 2.0, width / 2.0),
            (height / 2.0, -width / 2.0),
            (height / 2.0 - flange, -width / 2.0),
            (height / 2.0 - flange, -web / 2.0),
            (-height / 2.0 + flange, -web / 2.0),
            (-height / 2.0 + flange, -width / 2.0),
        ]]
        loops[0] = _without_duplicate_neighbors(loops[0])
    else:  # pragma: no cover - profile_for_section owns the supported set
        raise ValueError(f"Unsupported section profile kind {profile.kind!r}.")

    normalized = []
    for loop in loops:
        if _signed_area(loop) < 0.0:
            loop = list(reversed(loop))
        normalized.append(tuple((float(y), float(z)) for y, z in loop))
    return tuple(normalized)


def straight_section_surface_mesh(
    section,
    start,
    end,
    *,
    twist_angle_deg: float = 0.0,
    n_sides: int = 16,
) -> SurfaceMesh:
    """Extrude a section between two points as a closed triangular surface."""
    start_point = np.asarray(start, dtype=float)
    end_point = np.asarray(end, dtype=float)
    axis = end_point - start_point
    length = float(np.linalg.norm(axis))
    if start_point.shape != (3,) or end_point.shape != (3,) or not np.isfinite([*start_point, *end_point]).all() or length <= 1.0e-12:
        raise ValueError("Section extrusion requires two distinct finite endpoints.")

    local_x = axis / length
    if abs(abs(float(local_x[2])) - 1.0) < 1.0e-6:
        local_y = np.array([0.0, 1.0, 0.0])
    else:
        local_y = np.cross(np.array([0.0, 0.0, 1.0]), local_x)
        local_y /= np.linalg.norm(local_y)
    local_z = np.cross(local_x, local_y)

    if twist_angle_deg:
        angle = math.radians(float(twist_angle_deg))
        twisted_y = local_y * math.cos(angle) + local_z * math.sin(angle)
        twisted_z = local_z * math.cos(angle) - local_y * math.sin(angle)
        local_y, local_z = twisted_y, twisted_z

    loops = section_loops(section, n_sides=n_sides)
    if len(loops) > 2:
        raise ValueError("Section meshes support at most one inner loop.")
    loop_sizes = [len(loop) for loop in loops]
    loop_offsets = np.cumsum([0, *loop_sizes[:-1]]).tolist()
    points_per_end = sum(loop_sizes)

    vertices = []
    for point in (start_point, end_point):
        for loop in loops:
            vertices.extend(
                tuple(float(value) for value in point + y * local_y + z * local_z)
                for y, z in loop
            )

    faces: list[tuple[int, int, int]] = []
    for loop_index, (offset, size) in enumerate(zip(loop_offsets, loop_sizes)):
        for index in range(size):
            following = (index + 1) % size
            a = offset + index
            b = offset + following
            c = points_per_end + offset + following
            d = points_per_end + offset + index
            if loop_index == 0:
                faces.extend(((a, b, c), (a, c, d)))
            else:
                faces.extend(((a, d, c), (a, c, b)))

    if len(loops) == 1:
        cap_faces = _triangulate_polygon(loops[0])
        faces.extend((c, b, a) for a, b, c in cap_faces)
        faces.extend(
            (points_per_end + a, points_per_end + b, points_per_end + c)
            for a, b, c in cap_faces
        )
    else:
        outer_size, inner_size = loop_sizes
        if outer_size != inner_size:
            raise ValueError("Hollow section meshes require matching outer and inner loop sizes.")
        inner_offset = loop_offsets[1]
        for index in range(outer_size):
            following = (index + 1) % outer_size
            outer = index
            outer_next = following
            inner = inner_offset + index
            inner_next = inner_offset + following
            faces.extend(((outer_next, outer, inner), (outer_next, inner, inner_next)))
            faces.extend((
                (points_per_end + outer, points_per_end + outer_next, points_per_end + inner_next),
                (points_per_end + outer, points_per_end + inner_next, points_per_end + inner),
            ))

    return SurfaceMesh(vertices=tuple(vertices), faces=tuple(faces))


def _circle(radius: float, n_sides: int) -> list[tuple[float, float]]:
    return [
        (radius * math.cos(angle), radius * math.sin(angle))
        for angle in np.linspace(0.0, 2.0 * math.pi, n_sides, endpoint=False)
    ]


def _rectangle(height_y: float, height_z: float) -> list[tuple[float, float]]:
    return [
        (-height_y / 2.0, -height_z / 2.0),
        (height_y / 2.0, -height_z / 2.0),
        (height_y / 2.0, height_z / 2.0),
        (-height_y / 2.0, height_z / 2.0),
    ]


def _without_duplicate_neighbors(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    result = []
    for point in points:
        if not result or point != result[-1]:
            result.append(point)
    if len(result) > 1 and result[0] == result[-1]:
        result.pop()
    return result


def _signed_area(points) -> float:
    return 0.5 * sum(
        y * points[(index + 1) % len(points)][1] - points[(index + 1) % len(points)][0] * z
        for index, (y, z) in enumerate(points)
    )


def _triangulate_polygon(points) -> list[tuple[int, int, int]]:
    remaining = list(range(len(points)))
    triangles: list[tuple[int, int, int]] = []
    while len(remaining) > 3:
        for position, current in enumerate(remaining):
            previous = remaining[position - 1]
            following = remaining[(position + 1) % len(remaining)]
            a = np.asarray(points[previous])
            b = np.asarray(points[current])
            c = np.asarray(points[following])
            cross = _cross_2d(b - a, c - b)
            if cross <= 1.0e-12:
                continue
            if any(
                _point_in_triangle(np.asarray(points[index]), a, b, c)
                for index in remaining
                if index not in {previous, current, following}
            ):
                continue
            triangles.append((previous, current, following))
            del remaining[position]
            break
        else:
            raise ValueError("Section profile could not be triangulated.")
    triangles.append(tuple(remaining))
    return triangles


def _point_in_triangle(point, a, b, c) -> bool:
    ab = b - a
    bc = c - b
    ca = a - c
    return (
        _cross_2d(ab, point - a) >= -1.0e-12
        and _cross_2d(bc, point - b) >= -1.0e-12
        and _cross_2d(ca, point - c) >= -1.0e-12
    )


def _cross_2d(left, right) -> float:
    return float(left[0] * right[1] - left[1] * right[0])
