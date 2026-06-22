"""Shared IFC mapping helpers for Tuba exchange adapters."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Iterable

import ifcopenshell.guid


@dataclass
class IfcGuidRegistry:
    """Deterministic IFC GUID registry keyed by stable Tuba refs."""

    namespace: str = "tuba"
    _cache: dict[str, str] = field(default_factory=dict)

    def guid_for(self, ref: str) -> str:
        key = f"{self.namespace}:{ref}"
        if key not in self._cache:
            digest = hashlib.md5(key.encode("utf-8")).hexdigest()
            self._cache[key] = ifcopenshell.guid.compress(digest)
        return self._cache[key]


def ifc_property(ifc_file: Any, name: str, value: Any) -> Any:
    if isinstance(value, bool):
        nominal = ifc_file.create_entity("IfcBoolean", bool(value))
    elif isinstance(value, int):
        nominal = ifc_file.create_entity("IfcInteger", int(value))
    elif isinstance(value, float):
        nominal = ifc_file.create_entity("IfcReal", float(value))
    else:
        nominal = ifc_file.create_entity("IfcLabel", "" if value is None else str(value))
    return ifc_file.create_entity("IfcPropertySingleValue", Name=name, NominalValue=nominal)


def add_property_set(ifc_file: Any, product: Any, name: str, properties: Iterable[Any]) -> Any:
    pset = ifc_file.create_entity(
        "IfcPropertySet",
        GlobalId=ifcopenshell.guid.new(),
        Name=name,
        HasProperties=list(properties),
    )
    ifc_file.create_entity(
        "IfcRelDefinesByProperties",
        GlobalId=ifcopenshell.guid.new(),
        RelatedObjects=[product],
        RelatingPropertyDefinition=pset,
    )
    return pset
