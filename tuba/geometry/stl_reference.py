"""Bounded STL surface import for inspection and clearance, without solver regions."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
import struct

import numpy as np

from tuba.mixed import normalize_placement, transform_point


MAX_STL_BYTES = 16 * 1024 * 1024
MAX_STL_TRIANGLES = 200_000


def inspect_stl_reference(file_path) -> dict:
    """Read real ASCII/binary triangles in source units; never truncate or substitute.

    ``local_bounds`` has the shared [xmin,ymin,zmin,xmax,ymax,zmax] shape.
    Open/nonmanifold/degenerate surfaces retain their diagnostics; only a closed
    manifold without degenerate faces supports enclosure clearance checks.
    Malformed, nonfinite and over-limit inputs raise ``ValueError``.
    """
    return _inspect_payload(_read_payload(Path(file_path)))


def import_stl_reference(model, file_path, *, id: str, unit_scale_to_m: float,
                         placement=None):
    """Register an inspected reference surface with an explicit source-unit scale.

    Placement origin is in metres and rotation is a wxyz quaternion. This creates
    no analysis region, material assignment or automatically confirmed port.
    """
    if (isinstance(unit_scale_to_m, bool) or not isinstance(unit_scale_to_m, (int, float))
            or not math.isfinite(unit_scale_to_m) or unit_scale_to_m <= 0):
        raise ValueError("STL unit scale must be finite and positive.")
    if not isinstance(id, str) or not id.strip():
        raise ValueError("STL component id must be a nonempty string.")
    asset_id = f"{id}_asset"
    if asset_id in model.cad_assets or id in model.imported_components:
        raise ValueError("STL asset/component id already exists; use a new id.")
    normalized = normalize_placement(placement)
    path = Path(file_path)
    payload = _read_payload(path)
    metadata = _inspect_payload(payload)
    placed = np.asarray([transform_point(point, float(unit_scale_to_m), normalized)
                         for point in metadata["mesh_vertices_local"]])
    if not np.isfinite(placed).all() or len(np.unique(placed, axis=0)) != len(placed):
        raise ValueError("STL scale/placement must preserve finite, distinct mesh vertices.")
    asset = model.add_cad_asset(id=asset_id, source_path=str(path), source_format="STL",
        unit_scale_to_m=float(unit_scale_to_m), placement=normalized,
        content_digest=hashlib.sha256(payload).hexdigest(), importer="stl-reference", metadata=metadata)
    return model.add_imported_component(id=id, asset=f"cad_asset:{asset.id}",
                                       name=id, role="reference", status="reviewed")


def _read_payload(path: Path) -> bytes:
    if path.stat().st_size > MAX_STL_BYTES:
        raise ValueError(f"STL byte limit is {MAX_STL_BYTES}; the file is too large.")
    with path.open("rb") as source:
        payload = source.read(MAX_STL_BYTES + 1)
    if len(payload) > MAX_STL_BYTES:
        raise ValueError(f"STL byte limit is {MAX_STL_BYTES}; the file is too large.")
    if not payload:
        raise ValueError("STL has no triangles.")
    return payload


def _inspect_payload(payload: bytes) -> dict:
    # Binary STL may start with 'solid'; the exact record length takes precedence.
    count = struct.unpack_from("<I", payload, 80)[0] if len(payload) >= 84 else None
    if count is not None and len(payload) == 84 + 50 * count:
        triangles = _binary_triangles(payload, count)
    elif b"\0" in payload or not payload.lstrip().lower().startswith(b"solid"):
        raise ValueError("Binary STL triangle count/record length is invalid or truncated.")
    else:
        triangles = _ascii_triangles(payload)
    if not np.isfinite(triangles).all():
        raise ValueError("STL triangle coordinates and normals must be finite.")
    vertices, inverse = np.unique(triangles.reshape(-1, 3), axis=0, return_inverse=True)
    faces = inverse.reshape(-1, 3)
    return {
        "mesh_vertices_local": vertices.tolist(), "mesh_faces": faces.tolist(),
        "local_bounds": [*vertices.min(axis=0).tolist(), *vertices.max(axis=0).tolist()],
        "inspection": _mesh_inspection(vertices, faces, triangles),
    }


def _mesh_inspection(vertices, faces, triangles) -> dict:
    """One topology classification shared by inspection and clearance."""
    try:
        with np.errstate(over="raise", invalid="raise"):
            edges_a, edges_b = triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]
            normals = np.cross(edges_a, edges_b)
            area_squared = np.sum(normals**2, axis=1)
            edge_squared = np.maximum(np.sum(edges_a**2, axis=1), np.sum(edges_b**2, axis=1))
            valid = area_squared > (edge_squared * 1e-14)**2
            degenerate = int(np.count_nonzero(~valid))
            nonplanar = False
            if valid.any():
                first = int(np.flatnonzero(valid)[0])
                normal = normals[first]
                tolerance = np.linalg.norm(normal)*np.ptp(vertices, axis=0).max()*1e-12
                nonplanar = bool(np.any(np.abs((vertices-triangles[first, 0]) @ normal) > tolerance))
    except FloatingPointError as exc:
        raise ValueError("STL coordinate magnitude cannot be inspected safely.") from exc
    edges = np.sort(np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]]), axis=1)
    _, edge_counts = np.unique(edges, axis=0, return_counts=True)
    boundary = int(np.count_nonzero(edge_counts == 1))
    nonmanifold = int(np.count_nonzero(edge_counts > 2))
    duplicate_faces = len(np.unique(np.sort(faces, axis=1), axis=0)) != len(faces)
    return {"triangle_count": len(faces), "vertex_count": len(vertices),
        "boundary_edges": boundary, "nonmanifold_edges": nonmanifold,
        "degenerate_faces": degenerate,
        "closed_surface": bool(nonplanar and not (boundary or nonmanifold or degenerate or duplicate_faces))}


def _binary_triangles(payload: bytes, count: int) -> np.ndarray:
    if not 0 < count <= MAX_STL_TRIANGLES:
        raise ValueError(f"STL triangle limit is {MAX_STL_TRIANGLES}; expected at least one triangle.")
    dtype = np.dtype([("normal", "<f4", (3,)), ("vertices", "<f4", (3, 3)), ("attribute", "<u2")])
    records = np.frombuffer(payload, dtype=dtype, count=count, offset=84)
    if not np.isfinite(records["normal"]).all():
        raise ValueError("STL facet normals must be finite.")
    return records["vertices"].astype(float)


def _ascii_triangles(payload: bytes) -> np.ndarray:
    try:
        lines = [line.strip() for line in payload.decode("ascii").splitlines() if line.strip()]
    except UnicodeDecodeError as exc:
        raise ValueError("STL is neither valid binary nor ASCII.") from exc
    if len(lines) < 2 or lines[0].split()[0].lower() != "solid" or lines[-1].split()[0].lower() != "endsolid":
        raise ValueError("ASCII STL requires solid/endsolid and complete facets.")
    triangles = []
    index = 1
    while index < len(lines) - 1:
        if len(triangles) >= MAX_STL_TRIANGLES:
            raise ValueError(f"STL triangle limit is {MAX_STL_TRIANGLES}.")
        if index + 6 >= len(lines) - 1:
            raise ValueError("ASCII STL has a truncated facet.")
        normal = lines[index].split()
        if len(normal) != 5 or [v.lower() for v in normal[:2]] != ["facet", "normal"]:
            raise ValueError("ASCII STL expected a facet normal.")
        try:
            if not all(math.isfinite(float(value)) for value in normal[2:]):
                raise ValueError("STL facet normal must be finite.")
            if lines[index + 1].lower().split() != ["outer", "loop"]:
                raise ValueError("ASCII STL expected outer loop.")
            triangle = []
            for line in lines[index + 2:index + 5]:
                tokens = line.split()
                if len(tokens) != 4 or tokens[0].lower() != "vertex":
                    raise ValueError("ASCII STL expected three vertices per facet.")
                triangle.append([float(value) for value in tokens[1:]])
        except (ValueError, OverflowError) as exc:
            raise ValueError(f"Invalid ASCII STL facet: {exc}") from exc
        if lines[index + 5].lower() != "endloop" or lines[index + 6].lower() != "endfacet":
            raise ValueError("ASCII STL expected endloop/endfacet.")
        triangles.append(triangle)
        index += 7
    if not triangles:
        raise ValueError("STL has no triangles.")
    return np.asarray(triangles, dtype=float)
