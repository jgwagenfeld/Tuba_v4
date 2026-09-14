"""Mixed CAD/analysis records for STEP-backed Code_Aster studies."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tuba.refs import EntityRef


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

    def __post_init__(self) -> None:
        _require_id(self.id, "CadAsset id")
        if not self.source_path:
            raise ValueError("CadAsset source_path must not be empty.")
        if self.unit_scale_to_m <= 0.0:
            raise ValueError("CadAsset unit_scale_to_m must be positive.")
        object.__setattr__(self, "placement", dict(self.placement))
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

    def __post_init__(self) -> None:
        _require_id(self.id, "Port id")
        object.__setattr__(self, "owner", _coerce_ref(self.owner))
        object.__setattr__(self, "position", _float_tuple(self.position, 3, "Port position"))
        object.__setattr__(self, "axis", _float_tuple(self.axis, 3, "Port axis"))
        if self.radius <= 0.0:
            raise ValueError("Port radius must be positive.")
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
    return data  # type: ignore[return-value]


def _require_id(value: str, label: str) -> None:
    if not value:
        raise ValueError(f"{label} must not be empty.")
