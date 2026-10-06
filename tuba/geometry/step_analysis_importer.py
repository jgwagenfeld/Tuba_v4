"""STEP solids with source-local geometric selections and global SI ports."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from numbers import Real
from typing import Any

from tuba.meshing._gmsh import gmsh_model
from tuba.mixed import CadAsset, ImportedComponent, Port, normalize_placement, transform_axis, transform_point

try:
    import gmsh  # type: ignore
except ImportError:  # pragma: no cover
    gmsh = None


class StepImportError(RuntimeError):
    """A STEP source or its requested engineering interfaces cannot be imported."""


class StepAnalysisImporter:
    def import_component(
        self, model, file_path: str | Path, *, id: str, asset_id: str | None = None,
        role: str = "equipment", unit_scale_to_m: float = 1.0,
        placement: dict[str, Any] | None = None, material: str | None = None,
        mesh_size: float | str | None = None, interfaces: dict[str, dict[str, Any]] | None = None,
        interface_mesh_sizes: dict[str, float] | None = None,
        pressure_surfaces: list[dict[str, Any]] | None = None,
        fixed_interfaces: list[str] | None = None,
    ) -> ImportedComponent:
        """Import a solid; selectors use OCC coordinates normalized to MM.

        Gmsh converts the declared STEP units to MM before inspection.
        unit_scale_to_m converts that local basis to model metres once;
        placement and mesh sizes use model metres.

        interfaces={'inlet': {'position': [x,y,z], 'axis': [nx,ny,nz], 'radius': r}}
        names a unique planar face. Named interfaces are confirmed selections;
        automatically detected circular faces remain candidates.
        mesh_size='auto' (or None) chooses a starting size at mesh time;
        interface_mesh_sizes={'inlet': h} requests local refinement in metres.
        """
        path = Path(file_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"STEP file not found: {path}")
        if path.suffix.lower() not in {".step", ".stp"}:
            raise StepImportError("Expected a STEP/STP file for solid CAD import.")
        asset_id = asset_id or f"{id}_asset"
        placement = normalize_placement(placement)
        CadAsset(id=asset_id, source_path=str(path), unit_scale_to_m=unit_scale_to_m, placement=placement)
        mesh_size = "auto" if mesh_size is None else mesh_size
        if mesh_size != "auto":
            if isinstance(mesh_size, bool) or not isinstance(mesh_size, (int, float)) or not math.isfinite(mesh_size) or mesh_size <= 0:
                raise ValueError("mesh_size must be 'auto' or finite and positive in metres.")
            mesh_size = float(mesh_size)
        if interfaces is not None and not isinstance(interfaces, dict):
            raise ValueError("interfaces must map string names to geometric selectors.")
        if interface_mesh_sizes is not None and not isinstance(interface_mesh_sizes, dict):
            raise ValueError("interface_mesh_sizes must map explicitly selected interface names to sizes in metres.")
        local_sizes = dict(interface_mesh_sizes or {})
        for name, size in local_sizes.items():
            if name not in (interfaces or {}):
                raise ValueError(f"interface_mesh_sizes name {name!r} must name an explicitly selected interface.")
            if isinstance(size, bool) or not isinstance(size, (int, float)) or not math.isfinite(size) or size <= 0:
                raise ValueError(f"interface_mesh_sizes[{name!r}] must be finite and positive in metres.")
            local_sizes[name] = float(size)
        if material is not None and material not in model.materials:
            raise ValueError(f"Unknown solid material {material!r}.")
        if (pressure_surfaces or fixed_interfaces) and material is None:
            raise ValueError("Pressure/fixed surfaces require a solid material.")
        fixed_names = list(fixed_interfaces or [])
        if any(name not in (interfaces or {}) for name in fixed_names):
            raise ValueError("fixed_interfaces must name explicitly selected interfaces.")
        reserved_groups = {f"G_{id}_SOLID", f"G_SKIN_{id}_solid", f"G_PRESSURE_{id}_solid", "G_TUBE"}
        reserved_groups.update(f"G_NODE_{node_id}" for node_id in model.nodes)
        reserved_groups.update(group.solver_name for group in model.mesh_groups.values())
        reserved_groups.update(region.mesh_group for region in model.analysis_regions.values())
        reserved_groups.update(port.face_group for port in model.ports.values() if port.face_group)
        for name in interfaces or {}:
            if not isinstance(name, str) or not name.strip():
                raise ValueError("Interface name must be a nonempty string.")
            port_id = f"{id}_{name}"
            if port_id == f"{id}_solid" or port_id in model.mesh_groups or port_id in model.ports or f"G_{id}_{name}" in reserved_groups:
                raise ValueError(f"Interface {name!r} collides with a reserved or existing STEP id/group.")
        if material is not None and (f"{id}_solid" in model.analysis_regions or f"{id}_solid" in model.mesh_groups):
            raise ValueError("STEP analysis region/group id already exists.")
        if gmsh is None:
            raise StepImportError("gmsh is required to import STEP files for mixed analysis.")

        digest = self._compute_digest(path)
        with gmsh_model(gmsh, f"tuba_step_{id}", options={
            "Geometry.OCCTargetUnit": "MM", "Mesh.ElementOrder": 1, "Mesh.RecombineAll": 0,
        }):
            imported = gmsh.model.occ.importShapes(str(path))
            gmsh.model.occ.synchronize()
            if not any(dim == 3 for dim, _ in imported):
                raise StepImportError("STEP import contains no closed solid volume.")
            faces = self._describe_faces(imported)
            ports = []
            if interfaces is not None:
                for name, selector in interfaces.items():
                    face = self._select_face(faces, selector)
                    if face["type"] != "Plane":
                        raise StepImportError(f"Interface {name!r} must select a planar face.")
                    ports.append(self._port_payload(face, f"{id}_{name}", f"G_{id}_{name}", "confirmed"))
            else:
                for face in faces:
                    if face["shape"] in {"circular_face", "annular_face"}:
                        index = len(ports)
                        ports.append(self._port_payload(face, f"{id}_port_candidate_{index}", f"G_{id}_PORT_{index}", "detected"))
            pressure_faces = [self._select_face(faces, selector) for selector in pressure_surfaces or []]
            if len({face["gmsh_face_tag"] for face in pressure_faces}) != len(pressure_faces):
                raise StepImportError("Pressure surface selections must not repeat a face.")
            pressure = [self._selector(face) for face in pressure_faces]
            if any(port["id"] in model.mesh_groups for port in ports if port["status"] == "confirmed"):
                raise ValueError("STEP interface mesh group id already exists.")
            metadata = self._tessellate(faces)
            metadata["analysis_import_version"] = 1
            metadata["mesh_size"] = mesh_size
            metadata["interface_mesh_sizes"] = local_sizes
            for port in ports:
                port["position"] = transform_point(port["position"], unit_scale_to_m, placement)
                port["axis"] = transform_axis(port["axis"], placement)
                port["radius"] *= unit_scale_to_m
                port["metadata"]["inner_radius_m"] *= unit_scale_to_m

        if self._compute_digest(path) != digest:
            raise StepImportError("STEP source changed during import; retry with a stable source file.")
        component = self.record_component_from_metadata(
            model, source_path=path, component_id=id, asset_id=asset_id, role=role,
            unit_scale_to_m=unit_scale_to_m, placement=placement,
            content_digest=digest, metadata=metadata, ports=ports,
            status="reviewed" if material is not None and interfaces is not None else "review",
        )
        if material is not None:
            group = f"G_{id}_SOLID"
            model.add_analysis_region(
                id=f"{id}_solid", owner=f"component:{id}", role="solid_3d",
                code_aster_modelisation="3D", material=material, mesh_group=group,
                element_order=2, metadata={"pressure_surfaces": pressure,
                    "fixed_interfaces": [f"{id}_{name}" for name in fixed_names]},
            )
            model.add_mesh_group(id=f"{id}_solid", owner=f"component:{id}", solver_name=group, dimension=3)
        for port in ports:
            if port["status"] == "confirmed":
                model.add_mesh_group(id=port["id"], owner=f"port:{port['id']}", solver_name=port["face_group"], dimension=2,
                    metadata={"face_selector": port["metadata"]["face_selector"]})
        return component

    def record_component_from_metadata(
        self, model, *, source_path: str | Path, component_id: str, asset_id: str,
        role: str = "equipment", source_format: str = "STEP", unit_scale_to_m: float = 1.0,
        status: str = "review",
        placement: dict[str, Any] | None = None, content_digest: str | None = None,
        importer: str = "gmsh-occ", metadata: dict[str, Any] | None = None,
        ports: list[dict[str, Any]] | None = None,
    ) -> ImportedComponent:
        """Record externally supplied global SI ports without activating a solver."""
        payloads = [self._normalize_port_candidate(port) for port in ports or []]
        asset = CadAsset(id=asset_id, source_path=str(source_path), source_format=source_format.upper(),
            unit_scale_to_m=unit_scale_to_m, placement=placement or {}, content_digest=content_digest,
            importer=importer, metadata=dict(metadata or {}))
        component = ImportedComponent(id=component_id, asset=f"cad_asset:{asset_id}", name=component_id, role=role, status=status)
        port_records = [Port(id=str(port.get("id", f"{component_id}_port_{index}")), owner=f"component:{component_id}",
            kind=port.get("kind", "circular_face"), position=port["position"], axis=port.get("axis", [1, 0, 0]),
            radius=float(port["radius"]), face_group=port.get("face_group"), edge_group=port.get("edge_group"),
            status=port.get("status", "detected"), metadata=dict(port.get("metadata", {})))
            for index, port in enumerate(payloads)]
        if asset.id in model.cad_assets or component.id in model.imported_components:
            raise ValueError("STEP asset/component id already exists; use a new id.")
        port_ids = [port.id for port in port_records]
        if len(set(port_ids)) != len(port_ids) or any(port_id in model.ports for port_id in port_ids):
            raise ValueError("STEP port id already exists or is repeated.")
        model.cad_assets[asset.id] = asset
        model.imported_components[component.id] = component
        model.ports.update({port.id: port for port in port_records})
        return component

    def _describe_faces(self, imported) -> list[dict[str, Any]]:
        faces = []
        seen = set()
        for dim, tag in imported or []:
            if dim != 3:
                continue
            solid_center = gmsh.model.occ.getCenterOfMass(dim, tag)
            for face_dim, raw_tag in gmsh.model.getBoundary([(dim, tag)], oriented=False):
                face_tag = abs(int(raw_tag))
                if face_dim != 2 or face_tag in seen:
                    continue
                seen.add(face_tag)
                kind = gmsh.model.getType(2, face_tag)
                position = list(gmsh.model.occ.getCenterOfMass(2, face_tag))
                area = float(gmsh.model.occ.getMass(2, face_tag))
                if not math.isfinite(area) or area <= 0:
                    raise StepImportError("STEP face has invalid area.")
                circles = (self._circular_boundaries(face_tag) if kind == "Plane"
                           else self._circular_boundaries(face_tag, require_closed=False))
                radius = max((circle[1] for circle in circles), default=math.sqrt(area / math.pi))
                inner = 0.0
                shape = "surface"
                axis = None
                if kind == "Plane":
                    shape = "planar_face"
                    axis = self._outward_face_axis(face_tag, position, solid_center)
                    if axis is None:
                        continue
                    if 1 <= len(circles) <= 2 and all(math.dist(center, position) <= max(1e-8, radius*1e-6) for center, _ in circles):
                        inner = min(circle[1] for circle in circles) if len(circles) == 2 else 0.0
                        if math.isclose(area, math.pi*(radius*radius-inner*inner), rel_tol=1e-6, abs_tol=1e-12):
                            shape = "annular_face" if inner else "circular_face"
                faces.append({"gmsh_face_tag": face_tag, "type": kind, "position": position,
                    "axis": axis, "area": area, "radius": radius, "inner_radius": inner, "shape": shape,
                    "tolerance": max(1e-8, radius*1e-6)})
        return faces

    @staticmethod
    def _circular_boundaries(face_tag, *, require_closed=True) -> list[tuple[list[float], float]]:
        """Recover circles from arcs; planar ports require complete pure circle loops."""
        circles = []
        for dim, raw_tag in gmsh.model.getBoundary([(2, face_tag)], oriented=False):
            tag = abs(int(raw_tag))
            if dim != 1 or gmsh.model.getType(1, tag) != "Circle":
                if require_closed:
                    return []
                continue
            minimum, maximum = gmsh.model.getParametrizationBounds(1, tag)
            parameter = [(float(minimum[0]) + float(maximum[0])) / 2]
            curvature = float(gmsh.model.getCurvature(1, tag, parameter)[0])
            second = [float(value) for value in gmsh.model.getSecondDerivative(1, tag, parameter)]
            norm = math.sqrt(sum(value*value for value in second))
            length = float(gmsh.model.occ.getMass(1, tag))
            if not all(math.isfinite(value) and value > 0 for value in (curvature, norm, length)):
                return []
            radius = 1 / curvature
            point = gmsh.model.getValue(1, tag, parameter)
            center = [float(value) + direction*radius/norm for value, direction in zip(point, second)]
            if len(center) != 3 or not all(math.isfinite(value) for value in center):
                return []
            tolerance = max(1e-8, radius*1e-6)
            group = next((circle for circle in circles if math.dist(circle[0], center) <= tolerance
                          and math.isclose(circle[1], radius, rel_tol=1e-6, abs_tol=tolerance)), None)
            if group is None:
                circles.append([center, radius, length])
            else:
                group[2] += length
        if require_closed and any(not math.isclose(length, 2*math.pi*radius, rel_tol=1e-6, abs_tol=1e-8)
                                  for _, radius, length in circles):
            return []
        return [(center, radius) for center, radius, _ in circles]

    @classmethod
    def resolve_face_selector(cls, imported, selector: dict[str, Any]) -> int:
        """Re-identify one CAD face from local geometry after each source import."""
        return int(cls._select_face(cls()._describe_faces(imported), selector)["gmsh_face_tag"])

    @staticmethod
    def validate_face_selector(selector: dict[str, Any]) -> dict[str, Any]:
        """Validate a stable source-local geometric selector without importing CAD."""
        if not isinstance(selector, dict) or "position" not in selector:
            raise StepImportError("Face selector requires a source-local position.")
        unknown = set(selector) - {"position", "axis", "area", "radius", "inner_radius", "type", "shape", "tolerance"}
        if unknown:
            raise StepImportError(f"Unsupported face selector fields: {sorted(unknown, key=str)!r}.")
        position = selector["position"]
        def numeric(value):
            return isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(value)
        if not isinstance(position, (list, tuple)) or len(position) != 3 or not all(numeric(value) for value in position):
            raise StepImportError("Face selector position requires three finite values.")
        tolerance = selector.get("tolerance", 1e-7)
        if not numeric(tolerance) or tolerance <= 0:
            raise StepImportError("Face selector tolerance must be finite and positive.")
        for key in ("area", "radius", "inner_radius"):
            if key in selector and (not numeric(selector[key]) or selector[key] < 0):
                raise StepImportError(f"Face selector {key} must be finite and non-negative.")
        for key in ("type", "shape"):
            if key in selector and (not isinstance(selector[key],str) or not selector[key].strip()):
                raise StepImportError(f"Face selector {key} must be a nonempty string.")
        axis = selector.get("axis")
        if axis is not None:
            if not isinstance(axis,(list,tuple)) or len(axis) != 3 or not all(numeric(value) for value in axis) or math.dist(axis, [0, 0, 0]) <= 1e-12:
                raise StepImportError("Face selector axis requires three finite non-zero values.")
            norm = math.sqrt(sum(value*value for value in axis))
            axis = [value/norm for value in axis]
        result = {**selector,"position":[float(v) for v in position]}
        for key in ("area","radius","inner_radius","tolerance"):
            if key in result:
                result[key] = float(result[key])
        if axis is not None:
            result["axis"] = axis
        return result

    @classmethod
    def _select_face(cls, faces, selector: dict[str, Any]) -> dict[str, Any]:
        selector = cls.validate_face_selector(selector)
        position = selector["position"]
        tolerance = float(selector.get("tolerance", 1e-7))
        axis = selector.get("axis")
        matches = [face for face in faces if face["type"] == selector.get("type", "Plane")
            and ("shape" not in selector or face["shape"] == selector["shape"])
            and math.dist(face["position"], position) <= tolerance
            and all(math.isclose(face[key], selector[key], rel_tol=1e-6, abs_tol=tolerance*tolerance if key == "area" else tolerance)
                for key in ("area", "radius", "inner_radius") if key in selector)
            and (axis is None or (face["axis"] is not None and sum(a*b for a,b in zip(axis, face["axis"])) >= 1-1e-6))]
        if len(matches) != 1:
            raise StepImportError(f"Face selector must match exactly one face; matched {len(matches)}.")
        return matches[0]

    @staticmethod
    def _selector(face) -> dict[str, Any]:
        return {key: value for key, value in face.items() if key != "gmsh_face_tag" and value is not None}

    @classmethod
    def _port_payload(cls, face, id, group, status):
        return {"id": id, "kind": face["shape"], "position": list(face["position"]), "axis": list(face["axis"]),
            "radius": face["radius"], "face_group": group, "status": status,
            "metadata": {"face_selector": cls._selector(face), "inner_radius_m": face["inner_radius"]}}

    def _detect_port_candidates(self, imported):
        return [self._port_payload(face, f"port_candidate_{index}", f"G_PORT_CANDIDATE_{index}", "detected")
            for index, face in enumerate(face for face in self._describe_faces(imported) if face["shape"] in {"circular_face", "annular_face"})]

    @staticmethod
    def _tessellate(cad_faces) -> dict[str, Any]:
        gmsh.model.mesh.generate(2)
        tags, coordinates, _ = gmsh.model.mesh.getNodes()
        points = [list(map(float, coordinates[index:index+3])) for index in range(0, len(coordinates), 3)]
        index_by_tag = {int(tag): index for index, tag in enumerate(tags)}
        faces = []
        face_index_by_tag = {}
        for element_type, element_tags, nodes in zip(*gmsh.model.mesh.getElements(2)):
            _, dim, _, count, _, primary = gmsh.model.mesh.getElementProperties(element_type)
            if dim != 2 or primary != 3:
                raise StepImportError("STEP display tessellation must contain triangular faces.")
            for index, element_tag in enumerate(element_tags):
                face_index_by_tag[int(element_tag)] = len(faces)
                faces.append([index_by_tag[int(tag)] for tag in nodes[index*count:index*count+3]])
        if not faces:
            raise StepImportError("STEP import produced no display triangles.")
        partitions = [{"selector": StepAnalysisImporter._selector(face),
            "face_indices": [face_index_by_tag[int(tag)]
                             for block in gmsh.model.mesh.getElements(2, face["gmsh_face_tag"])[1]
                             for tag in block]} for face in cad_faces]
        bounds = [min(point[axis] for point in points) for axis in range(3)] + [max(point[axis] for point in points) for axis in range(3)]
        return {"mesh_vertices_local": points, "mesh_faces": faces, "local_bounds": bounds,
                "local_coordinate_unit": "MM", "display_face_partitions": partitions}

    @staticmethod
    def _outward_face_axis(face_tag, face_center, solid_center):
        try:
            minimum, maximum = gmsh.model.getParametrizationBounds(2, face_tag)
            normal = [float(value) for value in gmsh.model.getNormal(face_tag, [(float(a)+float(b))/2 for a,b in zip(minimum, maximum)])]
        except Exception:
            return None
        length = math.sqrt(sum(value*value for value in normal))
        if not math.isfinite(length) or length <= 1e-12:
            return None
        normal = [value/length for value in normal]
        # ponytail: centroid orientation; use an OCC inside/outside probe for concave equipment.
        if solid_center is not None and sum(n*(p-s) for n,p,s in zip(normal, face_center, solid_center)) < 0:
            normal = [-value for value in normal]
        return normal

    @staticmethod
    def _normalize_port_candidate(candidate):
        if not isinstance(candidate, dict):
            raise StepImportError("Port candidate must be a mapping.")
        for key in ("position", "radius"):
            if key not in candidate:
                raise StepImportError(f"Port candidate is missing required field {key!r}.")
        return dict(candidate)

    @staticmethod
    def _compute_digest(path: Path) -> str:
        return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"
