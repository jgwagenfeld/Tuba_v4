"""Native member envelopes against placed STL reference surfaces."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from tuba.clash.types import ClashResult
from tuba.geometry.spatial import SpatialIndex
from tuba.geometry.stl_reference import _mesh_inspection
from tuba.mixed import transform_point
from tuba.refs import EntityRef


@dataclass(frozen=True)
class ReferenceSurface:
    component_id: str
    triangles: np.ndarray
    index: SpatialIndex
    closed: bool


def stl_reference_surfaces(model) -> tuple[ReferenceSurface, ...]:
    """Validate stored surfaces once per check; missing coverage is an error."""
    surfaces = []
    for component in model.imported_components.values():
        asset = model.cad_assets.get(component.asset.id)
        if asset is None or asset.source_format.upper() != "STL":
            continue
        try:
            vertices = np.asarray(asset.metadata["mesh_vertices_local"], dtype=float)
            faces = np.asarray(asset.metadata["mesh_faces"])
            if (vertices.ndim != 2 or vertices.shape[1] != 3 or not len(vertices)
                    or not np.isfinite(vertices).all() or faces.ndim != 2 or faces.shape[1] != 3
                    or not len(faces) or faces.dtype.kind not in "iu"
                    or faces.min() < 0 or faces.max() >= len(vertices)):
                raise ValueError("invalid triangle vertices/connectivity")
            placed = np.asarray([transform_point(p, asset.unit_scale_to_m, asset.placement) for p in vertices])
            if not np.isfinite(placed).all():
                raise ValueError("nonfinite placed coordinates")
            triangles = placed[faces]
            closed = _mesh_inspection(vertices, faces, vertices[faces])["closed_surface"]
            bounds = np.concatenate([triangles.min(axis=1), triangles.max(axis=1)], axis=1)
            index = SpatialIndex(ids=tuple(range(len(triangles))), bounds=bounds)
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise ValueError(f"STL reference {component.id!r} clearance coverage unavailable: {exc}") from exc
        surfaces.append(ReferenceSurface(component.id, triangles, index, closed))
    return tuple(surfaces)


def check_reference_polyline(model, element, polyline, *, hard_radius: float,
                             clearance_radius: float, surfaces) -> list[ClashResult]:
    """Exact segment/triangle distance for the existing circular member envelope.

    Closed manifold shells additionally detect enclosed centerlines. Open surfaces
    have surface-only coverage. Only triangles fully within a confirmed port's
    planar disk may be excluded for that port's explicitly connected element.
    """
    clashes = []
    for surface in surfaces:
        best_distance, best_location, enclosed = reference_polyline_distance(model, element, polyline, surface)
        if best_distance >= clearance_radius:
            continue
        clashes.append(ClashResult(left=EntityRef("element", element.id),
            right=EntityRef("component", surface.component_id),
            severity="hard" if best_distance < hard_radius else "clearance",
            distance_m=float(best_distance), penetration_m=max(clearance_radius-best_distance, 0.0),
            location=tuple(float(v) for v in best_location),
            diagnostics=["Placed STL surface and member envelope checked" +
                         ("; centerline is enclosed by the closed reference shell." if enclosed else ".")],
            metadata={"check": "imported_reference", "source_format": "STL", "enclosed": enclosed,
                "closed_surface": surface.closed, "envelope": "circular_member",
                "clearance_m": max(clearance_radius-hard_radius, 0.0)}))
    return clashes


def reference_polyline_distance(model, element, polyline, surface):
    """Nearest permitted surface distance, or zero inside a closed shell."""
    points = np.asarray(polyline, dtype=float)
    excluded = _local_join_faces(model, element, surface)
    if surface.closed:
        for point in points:
            if _inside_closed_surface(point, surface.triangles):
                return 0.0, point, True
    first = next((i for i in range(len(surface.triangles)) if i not in excluded), None)
    best, location = float("inf"), points[0]
    if first is None:
        return best, location, False
    for p1, p2 in zip(points, points[1:]):
        # One real facet gives an upper bound; AABB culling then retains every
        # facet that could improve it, including when the member is clear.
        distance, candidate = _segment_triangle_distance(p1, p2, surface.triangles[first])
        if distance < best:
            best, location = distance, candidate
        lo, hi = np.minimum(p1, p2)-best, np.maximum(p1, p2)+best
        for face in surface.index.query([*lo, *hi]):
            if face in excluded:
                continue
            distance, candidate = _segment_triangle_distance(p1, p2, surface.triangles[face])
            if distance < best:
                best, location = distance, candidate
    return best, location, False


def _local_join_faces(model, element, surface) -> set[int]:
    excluded = set()
    for coupling in model.couplings.values():
        if (coupling.kind != "pipe_to_solid_port" or coupling.code_aster_keyword != "LIAISON_ELEM"
                or coupling.code_aster_option not in ("3D_TUYAU", "3D_POU")
                or coupling.source.kind != "element" or coupling.source.id != element.id
                or coupling.target.kind != "port" or coupling.source_node is None):
            continue
        port = model.ports.get(coupling.target.id)
        if (port is None or port.owner.kind != "component" or port.owner.id != surface.component_id
                or port.status != "confirmed" or coupling.source_node.id not in (element.n1, element.n2)):
            continue
        center, axis = np.asarray(port.position), np.asarray(port.axis)
        tol = max(1e-10, port.radius*1e-7)
        if np.linalg.norm(model.nodes[coupling.source_node.id].coords-center) > tol:
            continue
        offsets = surface.triangles-center
        normal_distance = np.abs(offsets @ axis)
        radial = np.linalg.norm(offsets - (offsets @ axis)[..., None]*axis, axis=2)
        selected = np.all(normal_distance <= tol, axis=1) & np.all(radial <= port.radius+tol, axis=1)
        excluded.update(int(i) for i in np.flatnonzero(selected))
    return excluded


def _project_in_triangle(point, triangle, normal):
    norm_squared = float(normal @ normal)
    if norm_squared == 0:
        return None
    projected = point - normal * float((point-triangle[0]) @ normal) / norm_squared
    tests = [float(np.cross(triangle[(i+1) % 3]-triangle[i], projected-triangle[i]) @ normal)
             for i in range(3)]
    return projected if min(tests) >= -1e-12*norm_squared else None


def _segment_triangle_distance(p1, p2, triangle):
    from tuba.clash.engine import _segment_segment_distance

    normal = np.cross(triangle[1]-triangle[0], triangle[2]-triangle[0])
    denom = float((p2-p1) @ normal)
    if denom != 0:
        fraction = float((triangle[0]-p1) @ normal) / denom
        if 0 <= fraction <= 1:
            hit = p1 + fraction*(p2-p1)
            if _project_in_triangle(hit, triangle, normal) is not None:
                return 0.0, hit
    best, location = float("inf"), p1
    for point in (p1, p2):
        projected = _project_in_triangle(point, triangle, normal)
        if projected is not None:
            distance = float(np.linalg.norm(point-projected))
            if distance < best:
                best, location = distance, point
    for i in range(3):
        distance, c1, _, _, _ = _segment_segment_distance(p1, p2, triangle[i], triangle[(i+1) % 3])
        if distance < best:
            best, location = distance, c1
    return best, location


def _inside_closed_surface(point, triangles):
    # Three oblique rays avoid depending on STL normal orientation or a ray
    # coinciding with a triangulated face edge. Duplicate edge hits count once.
    inside = []
    a, edge1, edge2 = triangles[:, 0], triangles[:, 1]-triangles[:, 0], triangles[:, 2]-triangles[:, 0]
    span = max(float(np.ptp(triangles.reshape(-1, 3), axis=0).max()), 1e-12)
    for direction in (np.array([1., .371, .529]), np.array([.217, 1., .613]), np.array([.433, .293, 1.])):
        h = np.cross(direction, edge2)
        determinant = np.sum(edge1*h, axis=1)
        usable = np.abs(determinant) > 1e-12*np.linalg.norm(edge1, axis=1)*np.linalg.norm(edge2, axis=1)
        indices = np.flatnonzero(usable)
        inverse = 1/determinant[indices]
        offsets = point-a[indices]
        u = inverse*np.sum(offsets*h[indices], axis=1)
        q = np.cross(offsets, edge1[indices])
        v = inverse*np.sum(direction*q, axis=1)
        t = inverse*np.sum(edge2[indices]*q, axis=1)
        hits = (u >= -1e-12) & (v >= -1e-12) & (u+v <= 1+1e-12)
        if np.any(hits & (np.abs(t) <= span*1e-10)):
            return False
        distances = np.sort(t[hits & (t > span*1e-10)])
        count = int(np.count_nonzero(np.diff(distances) > span*1e-10)) + int(len(distances) > 0)
        inside.append(count % 2 == 1)
    return sum(inside) >= 2
