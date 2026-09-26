"""Strict IFC reference extraction and selected straight-pipe conversion."""

from __future__ import annotations

import hashlib
import io
import math
import re
import tempfile
import zipfile
from pathlib import Path

import numpy as np


def require_ifc():
    try:
        import ifcopenshell
        import ifcopenshell.geom
        import ifcopenshell.util.element
        import ifcopenshell.util.placement
        import ifcopenshell.util.unit
    except ImportError as exc:
        raise ImportError("IfcOpenShell unavailable; pip install 'tuba[ifc]'") from exc
    return ifcopenshell


def safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_. -]", "_", name.replace("/", "_").replace("\\", "_"))[:80].strip(" .") or "reference.ifc"


def open_bytes(data: bytes):
    if not data or not data.lstrip().startswith(b"ISO-10303-21"):
        raise ValueError("Invalid IFC STEP file")
    ifc = require_ifc()
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "source.ifc"
        path.write_bytes(data)
        try:
            file = ifc.open(str(path))
        except Exception as exc:
            raise ValueError("Invalid IFC STEP file") from exc
    if file is None or not file.by_type("IfcProject"):
        raise ValueError("IFC project is missing")
    return file


def _axis(file, product, scale):
    if not product.is_a("IfcPipeSegment") or product.Representation is None:
        return None, "Only straight IfcPipeSegment axes are convertible"
    axes = [item for rep in product.Representation.Representations
            if rep.RepresentationIdentifier == "Axis" for item in rep.Items]
    if len(axes) != 1 or not axes[0].is_a("IfcPolyline") or len(axes[0].Points) != 2:
        return None, "A single two-point IfcPolyline Axis is required"
    bodies = [item for rep in product.Representation.Representations
              if rep.RepresentationIdentifier == "Body" for item in rep.Items]
    if (len(bodies) != 1 or not bodies[0].is_a("IfcSweptDiskSolid")
            or not bodies[0].Directrix.is_a("IfcPolyline")
            or len(bodies[0].Directrix.Points) != 2):
        return None, "A straight swept-disk Body is required"
    try:
        matches = all(np.allclose(a.Coordinates, b.Coordinates, rtol=0, atol=1e-8)
                      for a, b in zip(axes[0].Points, bodies[0].Directrix.Points))
        valid_radius = math.isfinite(float(bodies[0].Radius)) and float(bodies[0].Radius) > 0
    except (ValueError, TypeError):
        matches = valid_radius = False
    if not matches or not valid_radius:
        return None, "Body does not match the straight pipe Axis"
    try:
        transform = (require_ifc().util.placement.get_local_placement(product.ObjectPlacement)
                     if product.ObjectPlacement else np.eye(4))
        points = []
        for point in axes[0].Points:
            raw = np.asarray(point.Coordinates, dtype=float)
            if raw.shape != (3,) or not np.isfinite(raw).all():
                raise ValueError()
            world = (transform @ np.r_[raw, 1.0])[:3] * scale
            if not np.isfinite(world).all():
                raise ValueError()
            points.append(world)
        if np.linalg.norm(points[1] - points[0]) <= 1e-9:
            raise ValueError()
        return [p.tolist() for p in points], None
    except (ValueError, TypeError, AttributeError):
        return None, "Invalid or unresolved pipe axis placement"


def _unit_scale(file):
    project = file.by_type("IfcProject")[0]
    units = getattr(project.UnitsInContext, "Units", ()) if project.UnitsInContext else ()
    if not any(getattr(unit, "UnitType", None) == "LENGTHUNIT" for unit in units):
        raise ValueError("IFC length unit is not declared")
    scale = float(require_ifc().util.unit.calculate_unit_scale(file))
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError("Invalid IFC length unit")
    return scale


def _unit_name(file):
    units = file.by_type("IfcProject")[0].UnitsInContext.Units
    unit = next(unit for unit in units if unit.UnitType == "LENGTHUNIT")
    if unit.is_a("IfcSIUnit"):
        return f"{(unit.Prefix or '').lower()}metre"
    return str(unit.Name or "declared IFC length unit")


def _json_safe(value):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items() if key != "id"}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return str(value)


def extract(data: bytes, name: str = "reference.ifc") -> tuple[dict, dict]:
    ifc = require_ifc()
    file = open_bytes(data)
    scale = _unit_scale(file)
    settings = ifc.geom.settings()
    settings.set(settings.USE_WORLD_COORDS, True)
    products, warnings, meshes, seen = [], [], {}, set()
    for product in file.by_type("IfcProduct"):
        if not product.GlobalId:
            continue
        guid = product.GlobalId
        if guid in seen:
            raise ValueError(f"Duplicate IFC GUID: {guid}")
        seen.add(guid)
        axis, reason = _axis(file, product, scale)
        vertices, faces, bounds = [], [], None
        if product.Representation is not None:
            try:
                shape = ifc.geom.create_shape(settings, product)
                # Default IfcOpenShell tessellation already returns SI metres.
                vertices = np.asarray(shape.geometry.verts, dtype=float).reshape((-1, 3)).tolist()
                faces = np.asarray(shape.geometry.faces, dtype=int).reshape((-1, 3)).tolist()
                if vertices and faces and np.isfinite(vertices).all():
                    coords = np.asarray(vertices)
                    bounds = np.r_[coords.min(axis=0), coords.max(axis=0)].tolist()
                    meshes[guid] = {"vertices": vertices, "faces": faces, "bounds_m": bounds}
            except Exception:
                pass
        if bounds is None:
            warnings.append({"guid": guid, "reason": "No supported tessellated geometry"})
        if reason:
            warnings.append({"guid": guid, "reason": reason})
        props = _json_safe(ifc.util.element.get_psets(product))
        products.append({"guid": guid, "ifc_class": product.is_a(), "name": product.Name or "",
                         "bounds_m": bounds, "properties": props, "convertible": axis is not None,
                         "reason": reason})
    all_bounds = [m["bounds_m"] for m in meshes.values()]
    bounds = (np.r_[np.min(np.array(all_bounds)[:, :3], axis=0),
                    np.max(np.array(all_bounds)[:, 3:], axis=0)].tolist() if all_bounds else None)
    preview = {"name": safe_name(name), "sha256": hashlib.sha256(data).hexdigest(),
               "length_unit": _unit_name(file),
               "metres_per_unit": scale, "bounds_m": bounds, "products": products, "warnings": warnings}
    return preview, meshes


def validate_assignment(payload: dict) -> tuple[list[str], dict, dict]:
    if not isinstance(payload, dict) or set(payload) != {"reference_id", "guids", "material", "section"}:
        raise ValueError("Expected reference_id, guids, material and section")
    guids, material, section = payload["guids"], payload["material"], payload["section"]
    if not isinstance(guids, list) or not guids or any(not isinstance(g, str) or not g for g in guids) or len(set(guids)) != len(guids):
        raise ValueError("Select distinct IFC GUIDs")
    for obj, keys in ((material, {"name", "E_pa", "nu", "rho_kg_m3"}),
                      (section, {"name", "outer_diameter_m", "wall_thickness_m"})):
        if not isinstance(obj, dict) or set(obj) != keys or not isinstance(obj["name"], str) or not obj["name"].strip():
            raise ValueError("Explicit material and section properties are required")
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
               for k, v in obj.items() if k != "name"):
            raise ValueError("Engineering values must be finite numbers")
    if not (material["E_pa"] > 0 and -1 < material["nu"] < 0.5 and material["rho_kg_m3"] > 0
            and section["outer_diameter_m"] > 0 and 0 < section["wall_thickness_m"] < section["outer_diameter_m"] / 2):
        raise ValueError("Engineering values are out of range")
    return guids, material, section


def convert_pipes(source: str | Path, guids: list[str], material: dict, section: dict):
    """Build a fresh unsolved model from selected, validated IFC axes."""
    from tuba.model import TubaModel
    file = open_bytes(Path(source).read_bytes())
    scale = _unit_scale(file)
    model = TubaModel(project_name=Path(source).stem)
    model.add_material(material["name"], E=material["E_pa"], nu=material["nu"], rho=material["rho_kg_m3"])
    model.add_pipe_section(section["name"], OD=section["outer_diameter_m"], WT=section["wall_thickness_m"])
    for index, guid in enumerate(guids):
        try:
            product = file.by_guid(guid)
        except RuntimeError:
            product = None
        if product is None:
            raise KeyError(f"Unknown IFC GUID: {guid}")
        axis, reason = _axis(file, product, scale)
        if axis is None:
            raise ValueError(f"{guid}: {reason}")
        nodes = [model.find_node_by_point(point) or model.add_node(point) for point in axis]
        model.add_element(id=f"IFC_PIPE_{index}", type="pipe_straight", n1=nodes[0], n2=nodes[1],
                          section=section["name"], material=material["name"])
    return model


def conversion_zip(data: bytes, guids: list[str], material: dict, section: dict) -> bytes:
    with tempfile.TemporaryDirectory() as folder:
        source = Path(folder) / "source.ifc"
        source.write_bytes(data)
        convert_pipes(source, guids, material, section)
    script = ("from pathlib import Path\nfrom tuba.external.ifc_reference import convert_pipes\n\n"
              f"model = convert_pipes(Path(__file__).with_name('source.ifc'), {guids!r}, {material!r}, {section!r})\n")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("model.py", script)
        archive.writestr("source.ifc", data)
        archive.writestr("README.md", "Unsolved IFC pipe geometry. Add supports and loads before Code_Aster evaluation.\n")
    return buffer.getvalue()


def merge_reference(scene, reference_id: str, manifest: dict):
    from tuba.visualization.scene import GeometryAsset, SceneLayer, SceneObject
    layer = f"ifc:{reference_id}"
    scene.layers.append(SceneLayer(id=layer, category="design", label=manifest["preview"]["name"]))
    for product in manifest["preview"]["products"]:
        guid = product["guid"]
        mesh = manifest["meshes"].get(guid)
        if mesh is None:
            continue
        object_id = f"{layer}:{guid}"
        asset_id = f"{object_id}:mesh"
        scene.objects.append(SceneObject(id=object_id, kind="ifc_reference", name=product["name"] or guid,
                                         geometry_asset_id=asset_id, layer_ids=[layer],
                                         metadata={"ifc_class": product["ifc_class"], "properties": product["properties"]},
                                         source={"ifc_guid": guid, "reference_id": reference_id}))
        scene.geometry_assets.append(GeometryAsset(id=asset_id, format="mesh", bounds=mesh["bounds_m"],
                                                   object_ids=[object_id], generation_config={"vertices": mesh["vertices"], "faces": mesh["faces"]}))
