"""Bounded geometry upload inspection and explicit authored-Python handoff."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from urllib.parse import unquote

from tuba.mixed import normalize_placement, transform_point


MAX_GEOMETRY_BYTES = 16 * 1024 * 1024


def upload_options(name: str, options: str):
    """Validate the client headers before reading or parsing geometry."""
    if len(name) > 1024 or len(options) > 4096:
        raise ValueError("Geometry upload headers are too long.")
    name = unquote(name, encoding="utf-8", errors="strict")
    if (not name or name in {".", ".."} or any(c in name for c in '/\\:\x00')
            or any(ord(c) < 32 for c in name)):
        raise ValueError("Geometry name must be a filename without path components.")
    suffix = Path(name).suffix.lower()
    if suffix not in {".stl", ".step", ".stp"}:
        raise ValueError("Geometry must be an STL, STEP or STP file.")
    data = json.loads(options)
    if not isinstance(data, dict) or set(data) - {"id", "unit_scale_to_m", "placement"}:
        raise ValueError("Expected geometry id, unit_scale_to_m and optional placement.")
    identity = data.get("id")
    if not isinstance(identity, str) or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]{0,63}", identity) is None:
        raise ValueError("Geometry id must be a name of at most 64 ASCII letters, digits, underscores, dots or hyphens.")
    scale = data.get("unit_scale_to_m")
    if isinstance(scale, bool) or not isinstance(scale, (int, float)) or not math.isfinite(scale) or scale <= 0:
        raise ValueError("An explicit finite positive unit_scale_to_m is required.")
    placement = data.get("placement")
    if placement is not None:
        if not isinstance(placement, dict) or set(placement) - {"origin", "rotation"}:
            raise ValueError("Placement accepts origin and rotation only.")
        for key, count in (("origin", 3), ("rotation", 4)):
            values = placement.get(key, [0, 0, 0] if key == "origin" else [1, 0, 0, 0])
            if (not isinstance(values, list) or len(values) != count
                    or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values)):
                raise ValueError(f"Placement {key} requires {count} finite numbers.")
    return name, suffix, identity, float(scale), normalize_placement(placement)


def _inspection(metadata):
    if "inspection" in metadata:
        return metadata["inspection"]
    vertices, faces = metadata["mesh_vertices_local"], metadata["mesh_faces"]
    edges = Counter()
    degenerate = 0
    for face in faces:
        a, b, c = (vertices[i] for i in face)
        u, v = ([b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)])
        cross = [u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0]]
        degenerate += sum(x*x for x in cross) == 0
        edges.update(tuple(sorted(pair)) for pair in ((face[0],face[1]),(face[1],face[2]),(face[2],face[0])))
    boundary = sum(count == 1 for count in edges.values())
    nonmanifold = sum(count > 2 for count in edges.values())
    return {"triangle_count": len(faces), "vertex_count": len(vertices), "boundary_edges": boundary,
            "nonmanifold_edges": nonmanifold, "degenerate_faces": degenerate,
            "closed_surface": not (boundary or nonmanifold or degenerate)}


def geometry_upload(project_root, output_root, route, body, options):
    """Inspect actual bytes and optionally store them; never mutate a model script."""
    name, suffix, identity, scale, placement = options
    if route not in {"preview", "store"} or not isinstance(body, bytes) or not body:
        raise ValueError("Expected a nonempty geometry upload.")
    if len(body) > MAX_GEOMETRY_BYTES:
        raise ValueError("Geometry upload exceeds 16 MiB.")
    output_root = Path(output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(body).hexdigest()
    with TemporaryDirectory(prefix="geometry-preview-", dir=output_root) as temporary:
        source = Path(temporary) / ("source" + suffix)
        source.write_bytes(body)
        if suffix == ".stl":
            from tuba.geometry.stl_reference import inspect_stl_reference

            metadata = inspect_stl_reference(source)
            ports = []
        else:
            from tuba import Model
            from tuba.geometry.step_analysis_importer import StepAnalysisImporter

            model = Model("Studio geometry inspection")
            component = StepAnalysisImporter().import_component(
                model, source, id=identity, unit_scale_to_m=scale, placement=placement,
            )
            metadata = dict(model.cad_assets[component.asset.id].metadata)
            ports = [port.to_dict() for port in model.ports.values()]
        vertices = metadata["mesh_vertices_local"]
        faces = metadata["mesh_faces"]
        if not vertices or not faces or len(faces) > 200000:
            raise ValueError("Geometry preview requires actual bounded triangle geometry (at most 200000 triangles).")
        placed = [transform_point(point, scale, placement) for point in vertices]
        if any(not math.isfinite(value) for point in placed for value in point):
            raise ValueError("Placed geometry coordinates must remain finite.")
        if len({tuple(point) for point in placed}) < len({tuple(point) for point in vertices}):
            raise ValueError("Scale/placement collapses distinct geometry vertices; use a representable placement.")
        inspection = _inspection(metadata)
        metadata = {**metadata, "inspection": inspection}
        diagnostics = []
        if not inspection["closed_surface"]:
            diagnostics.append({"severity": "warning", "code": "geometry.open_surface",
                                "message": "The preview contains open, degenerate or nonmanifold triangles; review the source topology."})
        result = {"ok": True, "name": name, "format": "STL" if suffix == ".stl" else "STEP",
                  "component_id": identity, "role": "reference" if suffix == ".stl" else "review",
                  "unit_scale_to_m": scale, "placement": placement, "content_digest": "sha256:" + digest,
                  "size_bytes": len(body), "metadata": metadata, "ports": ports, "diagnostics": diagnostics,
                  "bounds_m": [min(point[i] for point in placed) for i in range(3)]
                              + [max(point[i] for point in placed) for i in range(3)]}
        if route == "store":
            project_root = Path(project_root).resolve()
            directory = project_root / "geometry"
            if directory.is_symlink() or (directory.exists() and directory.resolve().parent != project_root):
                raise ValueError("Project geometry directory must remain inside the project.")
            directory.mkdir(exist_ok=True)
            target = directory / (digest + suffix)
            if target.is_symlink() or target.resolve().parent != directory.resolve():
                raise ValueError("Geometry target must remain inside the project geometry directory.")
            try:
                with target.open("xb") as file:
                    file.write(body)
            except FileExistsError:
                if target.stat().st_size != len(body) or target.read_bytes() != body:
                    raise ValueError("Stored geometry digest does not match its immutable source bytes.")
            relative = target.relative_to(project_root).as_posix()
            method = "import_stl" if suffix == ".stl" else "import_step"
            result.update(path=relative, python=(
                "from pathlib import Path\n"
                f"model.{method}(str(Path(__file__).resolve().parent / {relative!r}), "
                f"id={identity!r}, unit_scale_to_m={scale!r}, placement={placement!r})"
            ))
        return result
