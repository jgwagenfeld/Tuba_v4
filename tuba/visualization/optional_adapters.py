"""Optional visualization adapter boundaries.

This module records future renderer/export adapter interfaces without importing
their optional browser-side dependencies.  The core viewer remains the plain
VisualizationScene consumer; large BIM/scientific engines can plug in later at
this registry boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


_MISSING_DEPENDENCY_CODE = "visualization.optional_adapter.missing_dependency"
_UNKNOWN_ADAPTER_CODE = "visualization.optional_adapter.unknown_adapter"


@dataclass(frozen=True)
class OptionalAdapterSpec:
    adapter_id: str
    display_name: str
    purpose: str
    dependency_names: tuple[str, ...]
    capabilities: tuple[str, ...]
    artifact_formats: tuple[str, ...]
    boundary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "display_name": self.display_name,
            "purpose": self.purpose,
            "dependency_names": list(self.dependency_names),
            "capabilities": list(self.capabilities),
            "artifact_formats": list(self.artifact_formats),
            "boundary": self.boundary,
        }


@dataclass(frozen=True)
class OptionalAdapterStatus:
    adapter_id: str
    available: bool
    status: str
    diagnostics: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "available": self.available,
            "status": self.status,
            "diagnostics": [dict(diagnostic) for diagnostic in self.diagnostics],
        }


_OPTIONAL_ADAPTERS: tuple[OptionalAdapterSpec, ...] = (
    OptionalAdapterSpec(
        adapter_id="vtkjs_dense",
        display_name="vtk.js dense mesh/scalar adapter",
        purpose="Scientific result review for dense finite-element meshes and scalar/vector fields.",
        dependency_names=("vtk.js",),
        capabilities=("dense mesh", "scalar", "vector field", "time/state overlays"),
        artifact_formats=("VTK.js scene", "VTU/VTP-derived JSON"),
        boundary="Consumes VisualizationScene result references and external mesh artifacts; it must not replace the scene contract.",
    ),
    OptionalAdapterSpec(
        adapter_id="thatopen_fragments",
        display_name="That Open Fragments IFC context adapter",
        purpose="Large IFC context review through worker-friendly fragment models.",
        dependency_names=("@thatopen/fragments", "@thatopen/components"),
        capabilities=("IFC context", "fragment streaming", "BIM metadata", "external coordination context"),
        artifact_formats=("IFC", "Fragments"),
        boundary="Uses IFC/fragments as exchange context only; TubaModel and VisualizationScene remain authoritative.",
    ),
    OptionalAdapterSpec(
        adapter_id="xeokit_xkt",
        display_name="xeokit XKT context adapter",
        purpose="Metadata-heavy BIM context viewing for large coordination models.",
        dependency_names=("@xeokit/xeokit-sdk", "xeokit-gltf-to-xkt"),
        capabilities=("BIM context", "metadata lookup", "large model navigation", "selection context"),
        artifact_formats=("XKT", "glTF-to-XKT"),
        boundary="Maps external BIM object identifiers into scene object/context metadata without mutating Tuba visualization state.",
    ),
)

_ADAPTERS_BY_ID = {adapter.adapter_id: adapter for adapter in _OPTIONAL_ADAPTERS}


def list_optional_adapters() -> list[OptionalAdapterSpec]:
    """Return registered optional adapter boundaries in stable documentation order."""

    return list(_OPTIONAL_ADAPTERS)


def get_optional_adapter(adapter_id: str) -> OptionalAdapterSpec:
    """Return a registered adapter spec.

    Raises:
        KeyError: if the adapter id is not registered.
    """

    return _ADAPTERS_BY_ID[adapter_id]


def check_optional_adapter(adapter_id: str) -> OptionalAdapterStatus:
    """Return adapter availability without importing optional renderer packages."""

    spec = _ADAPTERS_BY_ID.get(adapter_id)
    if spec is None:
        return OptionalAdapterStatus(
            adapter_id=adapter_id,
            available=False,
            status="unknown",
            diagnostics=(
                {
                    "severity": "error",
                    "code": _UNKNOWN_ADAPTER_CODE,
                    "message": f"Unknown optional visualization adapter {adapter_id!r}.",
                    "target": adapter_id,
                    "source": "tuba.visualization.optional_adapters",
                },
            ),
        )

    dependency_list = ", ".join(spec.dependency_names)
    return OptionalAdapterStatus(
        adapter_id=adapter_id,
        available=False,
        status="missing",
        diagnostics=(
            {
                "severity": "info",
                "code": _MISSING_DEPENDENCY_CODE,
                "message": (
                    f"{spec.display_name} is an optional adapter boundary. "
                    f"Install and wire {dependency_list} in a dedicated adapter package before using it."
                ),
                "target": adapter_id,
                "source": "tuba.visualization.optional_adapters",
                "dependencies": list(spec.dependency_names),
            },
        ),
    )


def adapter_capability_matrix() -> list[dict[str, Any]]:
    """Return a JSON-serializable matrix for docs and diagnostics."""

    return [adapter.to_dict() for adapter in _OPTIONAL_ADAPTERS]
