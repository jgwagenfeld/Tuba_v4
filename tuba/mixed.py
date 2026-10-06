"""Mixed CAD/analysis records for STEP-backed Code_Aster studies."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any

import numpy as np

from tuba.attributes import coerce_entity_ref
from tuba.codelink import script_lines
from tuba.refs import EntityRef, resolve_entity_ref


@dataclass(frozen=True)
class CadAsset:
    id: str
    source_path: str
    source_format: str = "STEP"
    unit_scale_to_m: float = 1.0
    placement: dict[str, Any] = field(default_factory=dict)
    content_digest: str | None = None
    importer: str = "gmsh-occ"
    metadata: dict[str, Any] = field(default_factory=dict)
    source_line: int | None = field(default_factory=lambda: script_lines()[0], compare=False, repr=False)
    source_call_line: int | None = field(default_factory=lambda: script_lines()[1], compare=False, repr=False)

    def __post_init__(self) -> None:
        _require_id(self.id, "CadAsset id")
        if not self.source_path:
            raise ValueError("CadAsset source_path must not be empty.")
        if not math.isfinite(self.unit_scale_to_m) or self.unit_scale_to_m <= 0.0:
            raise ValueError("CadAsset unit_scale_to_m must be finite and positive.")
        object.__setattr__(self, "placement", normalize_placement(self.placement))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        data = {
            "id": self.id,
            "source_path": self.source_path,
            "source_format": self.source_format,
            "unit_scale_to_m": self.unit_scale_to_m,
            "placement": dict(self.placement),
            "importer": self.importer,
            "metadata": dict(self.metadata),
        }
        if self.content_digest is not None:
            data["content_digest"] = self.content_digest
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CadAsset":
        return cls(
            id=data["id"],
            source_path=data["source_path"],
            source_format=data.get("source_format", "STEP"),
            unit_scale_to_m=float(data.get("unit_scale_to_m", 1.0)),
            placement=dict(data.get("placement", {})),
            content_digest=data.get("content_digest"),
            importer=data.get("importer", "gmsh-occ"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class ImportedComponent:
    id: str
    asset: EntityRef | str | dict[str, str]
    name: str
    role: str = "equipment"
    status: str = "reviewed"
    metadata: dict[str, Any] = field(default_factory=dict)
    source_line: int | None = field(default_factory=lambda: script_lines()[0], compare=False, repr=False)
    source_call_line: int | None = field(default_factory=lambda: script_lines()[1], compare=False, repr=False)

    def __post_init__(self) -> None:
        _require_id(self.id, "ImportedComponent id")
        object.__setattr__(self, "asset", _coerce_ref(self.asset))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "asset": str(self.asset),
            "name": self.name,
            "role": self.role,
            "status": self.status,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ImportedComponent":
        return cls(
            id=data["id"],
            asset=data["asset"],
            name=data.get("name", data["id"]),
            role=data.get("role", "equipment"),
            status=data.get("status", "reviewed"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class AnalysisRegion:
    id: str
    owner: EntityRef | str | dict[str, str]
    role: str
    code_aster_modelisation: str
    material: str
    mesh_group: str
    element_order: int = 2
    status: str = "reviewed"
    metadata: dict[str, Any] = field(default_factory=dict)
    source_line: int | None = field(default_factory=lambda: script_lines()[0], compare=False, repr=False)
    source_call_line: int | None = field(default_factory=lambda: script_lines()[1], compare=False, repr=False)

    def __post_init__(self) -> None:
        _require_id(self.id, "AnalysisRegion id")
        object.__setattr__(self, "owner", _coerce_ref(self.owner))
        if self.element_order < 1:
            raise ValueError("AnalysisRegion element_order must be positive.")
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "owner": str(self.owner),
            "role": self.role,
            "code_aster_modelisation": self.code_aster_modelisation,
            "material": self.material,
            "mesh_group": self.mesh_group,
            "element_order": self.element_order,
            "status": self.status,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AnalysisRegion":
        return cls(
            id=data["id"],
            owner=data["owner"],
            role=data["role"],
            code_aster_modelisation=data["code_aster_modelisation"],
            material=data["material"],
            mesh_group=data["mesh_group"],
            element_order=int(data.get("element_order", 2)),
            status=data.get("status", "reviewed"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class Port:
    id: str
    owner: EntityRef | str | dict[str, str]
    kind: str
    position: tuple[float, float, float]
    axis: tuple[float, float, float]
    radius: float
    face_group: str | None = None
    edge_group: str | None = None
    status: str = "detected"
    metadata: dict[str, Any] = field(default_factory=dict)
    source_line: int | None = field(default_factory=lambda: script_lines()[0], compare=False, repr=False)
    source_call_line: int | None = field(default_factory=lambda: script_lines()[1], compare=False, repr=False)

    def __post_init__(self) -> None:
        _require_id(self.id, "Port id")
        object.__setattr__(self, "owner", _coerce_ref(self.owner))
        object.__setattr__(self, "position", _float_tuple(self.position, 3, "Port position"))
        axis = _float_tuple(self.axis, 3, "Port axis")
        length = math.sqrt(sum(value * value for value in axis))
        if length <= 1e-12:
            raise ValueError("Port axis must be non-zero.")
        object.__setattr__(self, "axis", tuple(value / length for value in axis))
        if not math.isfinite(self.radius) or self.radius <= 0.0:
            raise ValueError("Port radius must be finite and positive.")
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        data = {
            "id": self.id,
            "owner": str(self.owner),
            "kind": self.kind,
            "position": list(self.position),
            "axis": list(self.axis),
            "radius": self.radius,
            "status": self.status,
            "metadata": dict(self.metadata),
        }
        if self.face_group is not None:
            data["face_group"] = self.face_group
        if self.edge_group is not None:
            data["edge_group"] = self.edge_group
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Port":
        return cls(
            id=data["id"],
            owner=data["owner"],
            kind=data["kind"],
            position=tuple(data["position"]),
            axis=tuple(data["axis"]),
            radius=float(data["radius"]),
            face_group=data.get("face_group"),
            edge_group=data.get("edge_group"),
            status=data.get("status", "detected"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class MeshGroup:
    id: str
    owner: EntityRef | str | dict[str, str]
    solver_name: str
    dimension: int
    members: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    source_line: int | None = field(default_factory=lambda: script_lines()[0], compare=False, repr=False)
    source_call_line: int | None = field(default_factory=lambda: script_lines()[1], compare=False, repr=False)

    def __post_init__(self) -> None:
        _require_id(self.id, "MeshGroup id")
        object.__setattr__(self, "owner", _coerce_ref(self.owner))
        if not self.solver_name:
            raise ValueError("MeshGroup solver_name must not be empty.")
        if self.dimension not in (0, 1, 2, 3):
            raise ValueError("MeshGroup dimension must be 0, 1, 2, or 3.")
        members = tuple(str(member) for member in self.members)
        if any(not member for member in members):
            raise ValueError("MeshGroup members must not contain empty ids.")
        object.__setattr__(self, "members", members)
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "owner": str(self.owner),
            "solver_name": self.solver_name,
            "dimension": self.dimension,
            "members": list(self.members),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MeshGroup":
        return cls(
            id=data["id"],
            owner=data["owner"],
            solver_name=data["solver_name"],
            dimension=int(data["dimension"]),
            members=tuple(data.get("members", ())),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class CouplingSpec:
    id: str
    kind: str
    source: EntityRef | str | dict[str, str]
    source_node: EntityRef | str | dict[str, str]
    target: EntityRef | str | dict[str, str]
    code_aster_keyword: str
    code_aster_option: str
    status: str = "reviewed"
    metadata: dict[str, Any] = field(default_factory=dict)
    source_line: int | None = field(default_factory=lambda: script_lines()[0], compare=False, repr=False)
    source_call_line: int | None = field(default_factory=lambda: script_lines()[1], compare=False, repr=False)

    def __post_init__(self) -> None:
        _require_id(self.id, "CouplingSpec id")
        object.__setattr__(self, "source", _coerce_ref(self.source))
        object.__setattr__(self, "source_node", _coerce_ref(self.source_node))
        object.__setattr__(self, "target", _coerce_ref(self.target))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "source": str(self.source),
            "source_node": str(self.source_node),
            "target": str(self.target),
            "code_aster_keyword": self.code_aster_keyword,
            "code_aster_option": self.code_aster_option,
            "status": self.status,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CouplingSpec":
        return cls(
            id=data["id"],
            kind=data["kind"],
            source=data["source"],
            source_node=data["source_node"],
            target=data["target"],
            code_aster_keyword=data["code_aster_keyword"],
            code_aster_option=data["code_aster_option"],
            status=data.get("status", "reviewed"),
            metadata=dict(data.get("metadata", {})),
        )


def _coerce_ref(value: EntityRef | str | dict[str, str]) -> EntityRef:
    if isinstance(value, EntityRef):
        return value
    if isinstance(value, str):
        return EntityRef.parse(value)
    if isinstance(value, dict):
        return EntityRef.from_dict(value)
    raise TypeError(f"Cannot convert {type(value).__name__} to EntityRef.")


def _float_tuple(values: object, length: int, label: str) -> tuple[float, ...]:
    data = tuple(float(value) for value in values)  # type: ignore[arg-type]
    if len(data) != length:
        raise ValueError(f"{label} must contain {length} values.")
    if not all(math.isfinite(value) for value in data):
        raise ValueError(f"{label} must contain finite values.")
    return data  # type: ignore[return-value]


def _require_id(value: str, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must not be empty.")


def shell_panel_geometry(polygon, thickness, mesh_size="auto"):
    """Validate a simple planar polygon authored in metres, without FEM nodes."""
    try:
        points = np.asarray(polygon, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError("Shell polygon requires at least three finite 3D vertices.") from exc
    if points.ndim != 2 or points.shape[0] < 3 or points.shape[1] != 3 or not np.isfinite(points).all():
        raise ValueError("Shell polygon requires at least three finite 3D vertices.")
    span = float(np.max(np.ptp(points, axis=0)))
    tolerance = max(1e-12, span * 1e-9)
    if any(np.linalg.norm(a-b) <= tolerance for i, a in enumerate(points) for b in points[i+1:]):
        raise ValueError("Shell polygon vertices must be distinct; omit a repeated closing vertex.")
    local = points-points[0]
    normal = np.sum(np.cross(local, np.roll(local, -1, axis=0)), axis=0)
    area2 = float(np.linalg.norm(normal))
    if area2 <= tolerance * max(span, tolerance):
        raise ValueError("Shell polygon must have nonzero area.")
    normal /= area2
    if np.max(np.abs((points-points[0]) @ normal)) > tolerance:
        raise ValueError("Shell polygon vertices must lie in one plane.")
    # Project to the most stable coordinate plane and reject crossing/touching edges.
    projected = np.delete(points, int(np.argmax(np.abs(normal))), axis=1)
    def side(a, b, c):
        return float((b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0]))
    def on_segment(a, b, c):
        return abs(side(a, b, c)) <= tolerance*max(span, tolerance) and np.all(c >= np.minimum(a,b)-tolerance) and np.all(c <= np.maximum(a,b)+tolerance)
    for i in range(len(points)):
        a, b = projected[i], projected[(i+1) % len(points)]
        for j in range(i+1, len(points)):
            if j == i+1 or (i == 0 and j == len(points)-1):
                continue
            c, d = projected[j], projected[(j+1) % len(points)]
            if (side(a,b,c)*side(a,b,d) < 0 and side(c,d,a)*side(c,d,b) < 0) or any((on_segment(a,b,c), on_segment(a,b,d), on_segment(c,d,a), on_segment(c,d,b))):
                raise ValueError("Shell polygon must be simple, without intersecting edges.")
    for value, label in ((thickness, "Shell thickness"),):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"{label} must be positive and finite in metres.")
    if mesh_size != "auto" and (isinstance(mesh_size, bool) or not isinstance(mesh_size, (int, float)) or not math.isfinite(mesh_size) or mesh_size <= 0):
        raise ValueError("Shell mesh_size must be 'auto' or positive and finite in metres.")
    return points.tolist(), float(thickness), mesh_size


def add_shell_panel(model, *, id, polygon, thickness, material, mesh_size="auto"):
    """Register one authored DKT panel; Gmsh creates its analysis nodes later."""
    _require_id(id, "Shell panel id")
    if id in model.groups or id in model.analysis_regions or id in model.mesh_groups:
        raise ValueError(f"Shell panel id {id!r} already exists.")
    if material not in model.materials:
        raise ValueError(f"Shell panel references missing material {material!r}.")
    polygon, thickness, mesh_size = shell_panel_geometry(polygon, thickness, mesh_size)
    region = AnalysisRegion(id=id, owner=EntityRef("group", id), role="shell_2d",
        code_aster_modelisation="DKT", material=material, mesh_group=f"G_{id}_SHELL", element_order=1,
        metadata={"polygon_m": polygon, "thickness_m": thickness, "mesh_size": mesh_size})
    group = MeshGroup(id=id, owner=region.owner, solver_name=region.mesh_group, dimension=2)
    model.groups[id] = {"nodes": [], "elements": [], "metadata": {"kind": "shell_panel"}}
    model.analysis_regions[id] = region
    model.mesh_groups[id] = group
    return region


def add_reference_point(model, *, id, position, material=""):
    """Create a massless DIS_TR carrier and return its native node id."""
    _require_id(id, "Reference point id")
    if id in model.analysis_regions or id in model.mesh_groups:
        raise ValueError(f"Reference point id {id!r} already exists.")
    if material and material not in model.materials:
        raise ValueError(f"Reference point references missing material {material!r}.")
    if any(isinstance(v,(bool,np.bool_)) for v in position):
        raise ValueError("Reference position requires three finite numeric values.")
    position = _float_tuple(position, 3, "Reference position")
    node_id = model.add_node(position)
    owner = EntityRef("node", node_id)
    region = AnalysisRegion(id=id, owner=owner, role="reference", code_aster_modelisation="DIS_TR",
        material=material, mesh_group=f"G_{id}_REF", element_order=1, metadata={"reference_id": id})
    model.analysis_regions[id] = region
    model.mesh_groups[id] = MeshGroup(id=id, owner=owner, solver_name=region.mesh_group, dimension=0)
    return node_id


def _typed_ref(value, kind):
    ref = EntityRef(kind, value) if isinstance(value, str) and ":" not in value else _coerce_ref(value)
    if ref.kind != kind:
        raise ValueError(f"Expected a {kind} reference, got {ref.kind!r}.")
    return ref


def validate_rigid_patch(model, coupling):
    """Validate stable patch selections; CAD tags are resolved only when meshing."""
    from tuba.geometry.step_analysis_importer import StepAnalysisImporter, StepImportError
    if coupling.code_aster_keyword != "LIAISON_SOLIDE" or coupling.code_aster_option != "RIGID_PATCH":
        raise ValueError("Rigid patch must use LIAISON_SOLIDE and RIGID_PATCH.")
    reference = coupling.source_node
    if coupling.source != reference or reference.kind != "node" or reference.id not in model.nodes:
        raise ValueError("Rigid patch source and source_node must name the same existing reference node.")
    if not any(r.role == "reference" and r.owner == reference for r in model.analysis_regions.values()):
        raise ValueError("Rigid patch requires an authored DIS_TR reference point.")
    data = coupling.metadata
    if not isinstance(data.get("mesh_node_group"), str) or not data["mesh_node_group"]:
        raise ValueError("Rigid patch requires a nonempty mesh_node_group.")
    selection = data.get("selection")
    if "node_filter" in data:
        if selection != "component_faces":
            raise ValueError("Patch node_filter requires component faces.")
        normalize_patch_node_filter(data["node_filter"])
    if selection == "component_faces":
        if coupling.target.kind != "component" or coupling.target.id not in model.imported_components:
            raise ValueError("Rigid patch faces require an existing component.")
        if not any(r.role == "solid_3d" and r.owner == coupling.target for r in model.analysis_regions.values()):
            raise ValueError("Rigid patch component requires a solid_3d region.")
        faces = data.get("face_selectors")
        if not isinstance(faces, list) or not faces:
            raise ValueError("Rigid patch requires nonempty face selectors.")
        for selector in faces:
            try:
                StepAnalysisImporter.validate_face_selector(selector)
            except StepImportError as exc:
                raise ValueError(f"Rigid patch has an invalid face selector: {exc}") from exc
    elif selection in {"shell_vertices", "shell_edges"}:
        region = next((r for r in model.analysis_regions.values() if r.role == "shell_2d" and r.owner == coupling.target), None)
        if region is None:
            raise ValueError("Rigid patch requires an existing shell panel group.")
        vertices = data.get("vertices" if selection == "shell_vertices" else "edges")
        if not isinstance(vertices, list) or not vertices or len(set(vertices)) != len(vertices) or any(isinstance(i,bool) or not isinstance(i,int) or i < 0 or i >= len(region.metadata["polygon_m"]) for i in vertices):
            raise ValueError("Rigid patch shell vertices or edges must be distinct bounded polygon indices.")
    elif selection == "nodes":
        nodes = data.get("nodes")
        if coupling.target != reference or not isinstance(nodes,list) or not nodes or len(set(nodes)) != len(nodes) or any(n not in model.nodes or n == reference.id for n in nodes):
            raise ValueError("Rigid patch nodes must be distinct existing physical nodes, excluding the reference.")
    else:
        raise ValueError("Rigid patch requires component_faces, shell_vertices or nodes selection.")


def normalize_patch_node_filter(node_filter):
    """Validate a coordinate half-space in the STEP source's millimetres."""
    keys = {"coordinate_frame", "axis", "comparison", "threshold"}
    if not isinstance(node_filter, dict) or set(node_filter) != keys:
        raise ValueError("Patch node_filter requires coordinate_frame, axis, comparison and threshold.")
    if node_filter["coordinate_frame"] != "source-local mm":
        raise ValueError("Patch node_filter coordinate_frame must be 'source-local mm'.")
    if node_filter["axis"] not in ("x", "y", "z") or node_filter["comparison"] not in ("<=", ">="):
        raise ValueError("Patch node_filter requires axis x/y/z and comparison <= or >=.")
    value = node_filter["threshold"]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Patch node_filter threshold must be finite source-local millimetres.")
    return {**node_filter, "threshold": float(value)}


def patch_node_filter_contains(point, node_filter):
    """Test source-local coordinates, including the half-space boundary."""
    value = point[("x", "y", "z").index(node_filter["axis"])]
    if math.isclose(value, node_filter["threshold"], rel_tol=1e-12, abs_tol=1e-8):
        return True
    return value <= node_filter["threshold"] if node_filter["comparison"] == "<=" else value >= node_filter["threshold"]


def add_rigid_patch(model, *, id, reference, component=None, faces=None, node_filter=None, shell=None, vertices=None, edges=None, nodes=None):
    """Tie selected CAD face or shell/native nodes rigidly to a reference point."""
    _require_id(id, "Rigid patch id")
    if id in model.couplings or id in model.mesh_groups:
        raise ValueError(f"Rigid patch id {id!r} already exists.")
    reference = _typed_ref(reference, "node")
    if sum(value is not None for value in (component, shell, nodes)) != 1:
        raise ValueError("Rigid patch requires exactly one of component, shell or nodes.")
    metadata = {"mesh_node_group": f"G_{id}_PATCH"}
    if node_filter is not None:
        if component is None:
            raise ValueError("Patch node_filter requires component faces.")
        metadata["node_filter"] = normalize_patch_node_filter(node_filter)
    if component is not None:
        if vertices is not None or edges is not None or nodes is not None:
            raise ValueError("Component face patches do not take shell vertices or native nodes.")
        from tuba.geometry.step_analysis_importer import StepAnalysisImporter, StepImportError
        target = _typed_ref(component, "component")
        try:
            selectors = [StepAnalysisImporter.validate_face_selector(s) for s in (faces or [])]
        except StepImportError as exc:
            raise ValueError(f"Rigid patch has an invalid face selector: {exc}") from exc
        metadata.update(selection="component_faces", face_selectors=selectors)
    elif shell is not None:
        if faces is not None:
            raise ValueError("Shell patches do not take CAD face selectors.")
        if (vertices is None) == (edges is None):
            raise ValueError("Shell patches require exactly one of vertices or edges.")
        target = _typed_ref(shell, "group")
        metadata.update(selection="shell_vertices" if vertices is not None else "shell_edges")
        metadata["vertices" if vertices is not None else "edges"] = list(vertices if vertices is not None else edges)
    else:
        if faces is not None or vertices is not None or edges is not None:
            raise ValueError("Native node patches do not take CAD faces or shell vertices.")
        target = reference
        metadata.update(selection="nodes", nodes=[_typed_ref(n, "node").id for n in nodes])
    coupling = CouplingSpec(id=id, kind="rigid_patch", source=reference, source_node=reference,
        target=target, code_aster_keyword="LIAISON_SOLIDE", code_aster_option="RIGID_PATCH", metadata=metadata)
    validate_rigid_patch(model, coupling)
    model.couplings[id] = coupling
    model.mesh_groups[id] = MeshGroup(id=id, owner=EntityRef("coupling",id), solver_name=metadata["mesh_node_group"], dimension=0)
    return coupling


def normalize_placement(placement: dict[str, Any] | None) -> dict[str, Any]:
    """Validate a translation in metres and a wxyz orientation quaternion."""
    data = dict(placement or {})
    origin = _float_tuple(data.get("origin", [0, 0, 0]), 3, "Placement origin")
    rotation = _float_tuple(data.get("rotation", [1, 0, 0, 0]), 4, "Placement rotation")
    norm = math.hypot(*rotation)
    if not math.isfinite(norm) or norm <= 1e-12:
        raise ValueError("Placement rotation must be a non-zero quaternion.")
    return {"origin": list(origin), "rotation": [value / norm for value in rotation]}


def transform_axis(axis, placement: dict[str, Any]) -> list[float]:
    """Rotate a source-local vector using a validated wxyz placement."""
    w, x, y, z = placement["rotation"]
    a, b, c = axis
    return [
        (1 - 2 * (y*y + z*z))*a + 2*(x*y - z*w)*b + 2*(x*z + y*w)*c,
        2*(x*y + z*w)*a + (1 - 2*(x*x + z*z))*b + 2*(y*z - x*w)*c,
        2*(x*z - y*w)*a + 2*(y*z + x*w)*b + (1 - 2*(x*x + y*y))*c,
    ]


def transform_point(point, unit_scale_to_m: float, placement: dict[str, Any]) -> list[float]:
    rotated = transform_axis([value * unit_scale_to_m for value in point], placement)
    return [origin + value for origin, value in zip(placement["origin"], rotated)]


def connect_pipe_to_port(
    model,
    *,
    pipe: str | EntityRef,
    node: str | EntityRef,
    port: str | EntityRef,
    method: str = "3D_TUYAU",
    id: str | None = None,
) -> CouplingSpec:
    """Connect a TUYAU pipe endpoint to a confirmed matching solid cut face."""
    return _connect_1d_to_port(model, element=pipe, node=node, port=port, method=method, id=id)


def connect_beam_to_port(model, *, beam, node, port, id: str | None = None) -> CouplingSpec:
    """Connect a beam endpoint to a named solid face using 3D_POU."""
    return _connect_1d_to_port(model, element=beam, node=node, port=port, method="3D_POU", id=id)


def _connect_1d_to_port(model, *, element, node, port, method, id) -> CouplingSpec:
    pipe = element
    pipe_ref = coerce_entity_ref(pipe)
    node_ref = coerce_entity_ref(node)
    port_ref = coerce_entity_ref(port)

    if pipe_ref.kind != "element":
        raise ValueError(f"pipe reference must target an element, got {pipe_ref.kind!r}.")
    if node_ref.kind != "node":
        raise ValueError(f"node reference must target a node, got {node_ref.kind!r}.")
    if port_ref.kind != "port":
        raise ValueError(f"port reference must target a port, got {port_ref.kind!r}.")

    if method not in {"3D_TUYAU", "3D_POU"}:
        raise ValueError(f"Unsupported coupling method {method!r}.")

    try:
        element = resolve_entity_ref(model, pipe_ref)
    except KeyError as exc:
        raise ValueError(f"Unknown pipe element {pipe_ref!r}.") from exc
    try:
        port_entity = resolve_entity_ref(model, port_ref)
    except KeyError as exc:
        raise ValueError(f"Unknown port {port_ref!r}.") from exc

    validate_port_connection(model, element, node_ref.id, port_entity, method)

    coupling_id = id or f"coupling_{len(model.couplings)}"
    return model.add_coupling(
        id=coupling_id,
        kind="pipe_to_solid_port",
        source=pipe_ref,
        source_node=node_ref,
        target=port_ref,
        code_aster_keyword="LIAISON_ELEM",
        code_aster_option=method,
    )


def validate_port_connection(model, element, node_id: str, port, method: str) -> None:
    """Shared geometric checks for authored and deserialized 1D/solid couplings."""
    expected = "3D_POU" if element.type == "beam" else "3D_TUYAU"
    if element.type not in {"pipe_straight", "pipe_bend", "beam"} or method != expected:
        raise ValueError(f"Element {element.id!r} type {element.type!r} is not valid for pipe-port coupling {method!r}; expected {expected}.")
    if node_id not in {element.n1, element.n2}:
        raise ValueError(f"Node {node_id!r} is not an endpoint of element {element.id!r}.")
    if not port.face_group:
        raise ValueError(f"Port {port.id!r} must define a face_group.")
    # Confirmation remains a model validation gate, allowing review of candidates.
    endpoint = _float_tuple(model.nodes[node_id].coords, 3, "Coupling endpoint")
    tolerance = max(1e-8, port.radius * 1e-5)
    if math.dist(endpoint, port.position) > tolerance:
        raise ValueError(f"Endpoint {node_id!r} must coincide with port {port.id!r} centre.")
    if element.type == "pipe_bend":
        if element.bend_geometry is None:
            raise ValueError("A bend port connection requires explicit tangent geometry.")
        tangent = element.bend_geometry.start_tangent if node_id == element.n1 else element.bend_geometry.end_tangent
    else:
        tangent = [b - a for a, b in zip(model.nodes[element.n1].coords, model.nodes[element.n2].coords)]
    tangent = _float_tuple(tangent, 3, "Coupling tangent")
    length = math.sqrt(sum(value * value for value in tangent))
    if length <= 1e-12 or abs(sum(a*b for a, b in zip(tangent, port.axis))) / length < 1 - 1e-6:
        raise ValueError(f"Element {element.id!r} must align with port {port.id!r} axis.")
    if element.type == "beam":
        return
    if port.kind not in {"circular_face", "annular_face"}:
        raise ValueError("A pipe connection requires a circular or annular cut face.")
    section = model.sections.get(element.section)
    if section is None or not hasattr(section, "OD"):
        raise ValueError(f"Section {element.section!r} does not define an OD for diameter comparison.")
    radius = float(section.OD) / 2
    if abs(radius - port.radius) > max(1e-8, radius * 0.02):
        raise ValueError("Port diameter mismatch: pipe section OD and port radius differ beyond tolerance.")
    if port.kind == "annular_face" and "inner_radius_m" in port.metadata:
        inner = radius - float(section.WT)
        if abs(inner - port.metadata["inner_radius_m"]) > max(1e-8, radius * 0.02):
            raise ValueError("Port wall thickness mismatch: pipe bore and solid cut face differ.")
