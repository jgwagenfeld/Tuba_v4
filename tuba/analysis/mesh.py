"""Traceable solver analysis mesh records."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tuba.analysis.provenance import SolverInputIdentity

from tuba.refs import EntityRef


@dataclass(frozen=True)
class MeshNodeSource:
    node_id: str
    source_ref: EntityRef | str | dict[str, str]
    role: str
    parametric_t: float | None = None
    segment_index: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.node_id:
            raise ValueError("MeshNodeSource node_id must not be empty.")
        if not self.role:
            raise ValueError("MeshNodeSource role must not be empty.")
        object.__setattr__(self, "source_ref", _coerce_entity_ref(self.source_ref))
        if self.parametric_t is not None and not 0.0 <= self.parametric_t <= 1.0:
            raise ValueError("MeshNodeSource parametric_t must be between 0.0 and 1.0.")
        if self.segment_index is not None and self.segment_index < 0:
            raise ValueError("MeshNodeSource segment_index must be non-negative.")
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "node_id": self.node_id,
            "source_ref": self.source_ref.to_dict(),
            "role": self.role,
        }
        if self.parametric_t is not None:
            data["parametric_t"] = self.parametric_t
        if self.segment_index is not None:
            data["segment_index"] = self.segment_index
        if self.metadata:
            data["metadata"] = dict(self.metadata)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MeshNodeSource":
        return cls(
            node_id=data["node_id"],
            source_ref=EntityRef.from_dict(data["source_ref"]),
            role=data["role"],
            parametric_t=data.get("parametric_t"),
            segment_index=data.get("segment_index"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class MeshElementSource:
    element_id: str
    source_ref: EntityRef | str | dict[str, str]
    role: str
    segment_index: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.element_id:
            raise ValueError("MeshElementSource element_id must not be empty.")
        if not self.role:
            raise ValueError("MeshElementSource role must not be empty.")
        object.__setattr__(self, "source_ref", _coerce_entity_ref(self.source_ref))
        if self.segment_index is not None and self.segment_index < 0:
            raise ValueError("MeshElementSource segment_index must be non-negative.")
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "element_id": self.element_id,
            "source_ref": self.source_ref.to_dict(),
            "role": self.role,
        }
        if self.segment_index is not None:
            data["segment_index"] = self.segment_index
        if self.metadata:
            data["metadata"] = dict(self.metadata)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MeshElementSource":
        return cls(
            element_id=data["element_id"],
            source_ref=EntityRef.from_dict(data["source_ref"]),
            role=data["role"],
            segment_index=data.get("segment_index"),
            metadata=dict(data.get("metadata", {})),
        )


#: Code_Aster ``MODELISATION`` -> (topological dimension, result support).
#:
#: ``TUYAU_3M`` is the one that surprises people: it is topologically a 1D mesh
#: (SEG3/SEG4) whose stress recovery lives at circumferential sub-points, so the
#: mesh is 1D while the results are effectively 2.5D.
MODELISATION_INFO: dict[str, tuple[int, str]] = {
    "TUYAU_3M": (1, "subpoint"),
    "POU_D_T": (1, "cell"),
    "POU_D_E": (1, "cell"),
    "BARRE": (1, "cell"),
    "CABLE": (1, "cell"),
    "DIS_TR": (0, "node"),
    "DIS_T": (0, "node"),
    "DKT": (2, "cell"),
    "COQUE_3D": (2, "cell"),
    "3D": (3, "gauss"),
}


def modelisation_info(modelisation: str) -> tuple[int, str]:
    """Return ``(topological_dim, result_support)`` for a ``MODELISATION``.

    Unknown modelisations report ``(-1, "unknown")`` rather than raising: the
    viewer must be able to render a mesh badge for a modelisation Tuba does not
    model yet without the whole scene build failing.
    """
    return MODELISATION_INFO.get(modelisation, (-1, "unknown"))


@dataclass(frozen=True)
class AnalysisMesh:
    id: str
    model_revision: int
    solver_name: str
    nodes: dict[str, tuple[float, float, float]]
    elements: dict[str, tuple[str, ...]]
    groups: dict[str, tuple[str, ...]]
    node_sources: dict[str, MeshNodeSource]
    element_sources: dict[str, MeshElementSource]
    files: dict[str, str] = field(default_factory=dict)
    #: ``GROUP_MA`` name -> Code_Aster ``MODELISATION``, mirroring ``AFFE_MODELE``.
    modelisations: dict[str, str] = field(default_factory=dict)
    solver_input_identity: SolverInputIdentity | None = None
    surface_mesh: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        _require_nonempty(self.id, "AnalysisMesh id")
        _require_nonempty(self.solver_name, "AnalysisMesh solver_name")
        if self.model_revision < 0:
            raise ValueError("AnalysisMesh model_revision must be non-negative.")
        nodes = {key: _float_tuple(value, 3, f"AnalysisMesh node {key}") for key, value in self.nodes.items()}
        elements = {key: tuple(value) for key, value in self.elements.items()}
        groups = {key: tuple(value) for key, value in self.groups.items()}
        node_sources = {
            key: source if isinstance(source, MeshNodeSource) else MeshNodeSource.from_dict(source)
            for key, source in self.node_sources.items()
        }
        element_sources = {
            key: source if isinstance(source, MeshElementSource) else MeshElementSource.from_dict(source)
            for key, source in self.element_sources.items()
        }
        for element_id, node_ids in elements.items():
            for node_id in node_ids:
                if node_id not in nodes:
                    raise ValueError(f"AnalysisMesh element {element_id!r} references missing node {node_id!r}.")
        for node_id, source in node_sources.items():
            if node_id not in nodes:
                raise ValueError(f"AnalysisMesh node source {node_id!r} does not match a mesh node.")
            if source.node_id != node_id:
                raise ValueError(f"AnalysisMesh node source key {node_id!r} does not match source node_id {source.node_id!r}.")
        for element_id, source in element_sources.items():
            if element_id not in elements:
                raise ValueError(f"AnalysisMesh element source {element_id!r} does not match a mesh element.")
            if source.element_id != element_id:
                raise ValueError(
                    f"AnalysisMesh element source key {element_id!r} does not match source element_id {source.element_id!r}."
                )
        object.__setattr__(self, "nodes", nodes)
        object.__setattr__(self, "elements", elements)
        object.__setattr__(self, "groups", groups)
        object.__setattr__(self, "node_sources", node_sources)
        object.__setattr__(self, "element_sources", element_sources)
        object.__setattr__(self, "files", dict(self.files))
        modelisations = {str(key): str(value) for key, value in self.modelisations.items()}
        for group_name, modelisation in modelisations.items():
            if not group_name or not modelisation:
                raise ValueError("AnalysisMesh modelisations must map non-empty group names to non-empty values.")
        # Group existence is deliberately not checked: POI1 groups for discrete
        # springs/masses (``DIS_<node>``) are created by CREA_MAILLAGE inside the
        # .comm, so they are named in AFFE_MODELE without existing in `groups`.
        object.__setattr__(self, "modelisations", modelisations)
        if self.surface_mesh is not None:
            vertices = [
                list(_float_tuple(vertex, 3, "AnalysisMesh surface vertex"))
                for vertex in self.surface_mesh.get("vertices", [])
            ]
            faces = [list(int(index) for index in face) for face in self.surface_mesh.get("faces", [])]
            if not vertices or not faces or any(len(face) != 3 for face in faces):
                raise ValueError("AnalysisMesh surface_mesh requires non-empty triangular vertices and faces.")
            if any(index < 0 or index >= len(vertices) for face in faces for index in face):
                raise ValueError("AnalysisMesh surface_mesh face index is outside its vertex array.")
            object.__setattr__(self, "surface_mesh", {"vertices": vertices, "faces": faces})

    def to_dict(self) -> dict[str, Any]:
        data = {
            "id": self.id,
            "model_revision": self.model_revision,
            "solver_name": self.solver_name,
            "nodes": {key: list(value) for key, value in self.nodes.items()},
            "elements": {key: list(value) for key, value in self.elements.items()},
            "groups": {key: list(value) for key, value in self.groups.items()},
            "node_sources": {key: value.to_dict() for key, value in self.node_sources.items()},
            "element_sources": {key: value.to_dict() for key, value in self.element_sources.items()},
            "files": dict(self.files),
            "modelisations": dict(self.modelisations),
        }
        if self.solver_input_identity is not None:
            data["solver_input_identity"] = self.solver_input_identity.to_dict()
        if self.surface_mesh is not None:
            data["surface_mesh"] = {
                "vertices": [list(vertex) for vertex in self.surface_mesh["vertices"]],
                "faces": [list(face) for face in self.surface_mesh["faces"]],
            }
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AnalysisMesh":
        return cls(
            id=data["id"],
            model_revision=data["model_revision"],
            solver_name=data["solver_name"],
            nodes={key: tuple(value) for key, value in data.get("nodes", {}).items()},
            elements={key: tuple(value) for key, value in data.get("elements", {}).items()},
            groups={key: tuple(value) for key, value in data.get("groups", {}).items()},
            node_sources={key: MeshNodeSource.from_dict(value) for key, value in data.get("node_sources", {}).items()},
            element_sources={
                key: MeshElementSource.from_dict(value) for key, value in data.get("element_sources", {}).items()
            },
            files=dict(data.get("files", {})),
            modelisations=dict(data.get("modelisations", {})),
            solver_input_identity=(
                SolverInputIdentity.from_dict(data["solver_input_identity"])
                if data.get("solver_input_identity") is not None
                else None
            ),
            surface_mesh=(dict(data["surface_mesh"]) if data.get("surface_mesh") is not None else None),
        )


def _coerce_entity_ref(value: EntityRef | str | dict[str, str]) -> EntityRef:
    if isinstance(value, EntityRef):
        return value
    if isinstance(value, str):
        return EntityRef.parse(value)
    if isinstance(value, dict):
        return EntityRef.from_dict(value)
    raise TypeError(f"Cannot convert {type(value).__name__} to EntityRef.")


def _float_tuple(values: Any, length: int, label: str) -> tuple[float, ...]:
    data = tuple(float(value) for value in values)
    if len(data) != length:
        raise ValueError(f"{label} must have {length} values.")
    return data


def _require_nonempty(value: str, label: str) -> None:
    if not value:
        raise ValueError(f"{label} must not be empty.")
