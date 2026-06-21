"""Semantic attributes that can affect downstream analysis without changing geometry."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tuba.refs import EntityRef


@dataclass(frozen=True)
class InsulationSpec:
    """Typed insulation definition assigned to elements, groups, or future assemblies."""

    id: str
    material: str
    thickness_m: float
    density_kg_m3: float = 0.0
    cost_per_m: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("InsulationSpec id must not be empty.")
        if not self.material:
            raise ValueError("InsulationSpec material must not be empty.")
        if self.thickness_m < 0.0:
            raise ValueError("InsulationSpec thickness_m must be non-negative.")
        if self.density_kg_m3 < 0.0:
            raise ValueError("InsulationSpec density_kg_m3 must be non-negative.")
        if self.cost_per_m < 0.0:
            raise ValueError("InsulationSpec cost_per_m must be non-negative.")

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "material": self.material,
            "thickness_m": self.thickness_m,
            "density_kg_m3": self.density_kg_m3,
            "cost_per_m": self.cost_per_m,
        }
        if self.metadata:
            data["metadata"] = dict(self.metadata)
        return data

    @classmethod
    def from_dict(cls, id: str, data: dict[str, Any]) -> "InsulationSpec":
        return cls(
            id=id,
            material=data["material"],
            thickness_m=data["thickness_m"],
            density_kg_m3=data.get("density_kg_m3", 0.0),
            cost_per_m=data.get("cost_per_m", 0.0),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class AttributeAssignment:
    """A semantic value attached to a model entity reference."""

    target: EntityRef
    key: str
    value: Any
    source: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "target", coerce_entity_ref(self.target))
        if not self.key:
            raise ValueError("AttributeAssignment key must not be empty.")

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "target": self.target.to_dict(),
            "key": self.key,
            "value": self.value,
        }
        if self.source is not None:
            data["source"] = self.source
        if self.metadata:
            data["metadata"] = dict(self.metadata)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AttributeAssignment":
        return cls(
            target=EntityRef.from_dict(data["target"]),
            key=data["key"],
            value=data.get("value"),
            source=data.get("source"),
            metadata=dict(data.get("metadata", {})),
        )


def coerce_entity_ref(value: EntityRef | str | dict[str, str]) -> EntityRef:
    if isinstance(value, EntityRef):
        return value
    if isinstance(value, str):
        return EntityRef.parse(value)
    if isinstance(value, dict):
        return EntityRef.from_dict(value)
    raise TypeError(f"Cannot convert {type(value).__name__} to EntityRef.")
