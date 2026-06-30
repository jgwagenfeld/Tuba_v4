"""Stable references to model entities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


ENTITY_REF_KINDS = frozenset(
    {
        "node",
        "element",
        "support",
        "obstacle",
        "group",
        "assembly",
        "route",
        "material",
        "section",
        "load_case",
        "placement_frame",
        "cad_asset",
        "component",
        "analysis_region",
        "port",
        "mesh_group",
        "coupling",
    }
)


@dataclass(frozen=True)
class EntityRef:
    """Stable reference to an entity in or beside a Tuba model."""

    kind: str
    id: str

    def __post_init__(self) -> None:
        if self.kind not in ENTITY_REF_KINDS:
            raise ValueError(f"Unknown entity ref kind {self.kind!r}.")
        if not self.id:
            raise ValueError("Entity ref id must not be empty.")

    @classmethod
    def parse(cls, text: str) -> "EntityRef":
        if ":" not in text:
            raise ValueError(f"Entity ref {text!r} must use '<kind>:<id>' format.")
        kind, entity_id = text.split(":", 1)
        return cls(kind=kind, id=entity_id)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EntityRef":
        return cls(kind=data["kind"], id=data["id"])

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "id": self.id}

    def __str__(self) -> str:
        return f"{self.kind}:{self.id}"


def resolve_entity_ref(model: Any, ref: EntityRef) -> Any:
    """Resolve an entity ref against a model-like object."""
    if ref.kind == "node":
        return _lookup_mapping(model.nodes, ref)
    if ref.kind == "material":
        return _lookup_mapping(model.materials, ref)
    if ref.kind == "section":
        return _lookup_mapping(model.sections, ref)
    if ref.kind == "load_case":
        return _lookup_mapping(model.load_cases, ref)
    if ref.kind == "group":
        return _lookup_mapping(model.groups, ref)
    if ref.kind == "element":
        for element in model.elements:
            if element.id == ref.id:
                return element
        raise KeyError(str(ref))
    if ref.kind == "support":
        for support in model.supports:
            if support.id == ref.id:
                return support
        raise KeyError(str(ref))
    if ref.kind == "obstacle":
        for obstacle in model.obstacles:
            if obstacle.get("id") == ref.id:
                return obstacle
        raise KeyError(str(ref))
    if ref.kind == "assembly":
        assemblies = getattr(model, "assemblies", {})
        return _lookup_mapping(assemblies, ref)
    if ref.kind == "route":
        routes = getattr(model, "routes", {})
        return _lookup_mapping(routes, ref)
    if ref.kind == "placement_frame":
        placement_frames = getattr(model, "placement_frames", {})
        return _lookup_mapping(placement_frames, ref)
    if ref.kind == "cad_asset":
        return _lookup_mapping(getattr(model, "cad_assets", {}), ref)
    if ref.kind == "component":
        return _lookup_mapping(getattr(model, "imported_components", {}), ref)
    if ref.kind == "analysis_region":
        return _lookup_mapping(getattr(model, "analysis_regions", {}), ref)
    if ref.kind == "port":
        return _lookup_mapping(getattr(model, "ports", {}), ref)
    if ref.kind == "mesh_group":
        return _lookup_mapping(getattr(model, "mesh_groups", {}), ref)
    if ref.kind == "coupling":
        return _lookup_mapping(getattr(model, "couplings", {}), ref)
    raise KeyError(str(ref))


def _lookup_mapping(mapping: dict[str, Any], ref: EntityRef) -> Any:
    try:
        return mapping[ref.id]
    except KeyError as exc:
        raise KeyError(str(ref)) from exc
