"""Named cold, operating, and visual geometry-state records."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


GEOMETRY_STATE_TYPES = frozenset({"cold", "operating", "deformed", "construction", "preview"})
GEOMETRY_STATE_PURPOSES = frozenset({"engineering", "visualization", "preview"})


@dataclass(frozen=True)
class GeometryState:
    id: str
    model_revision: int
    state_type: str
    load_case: str | None = None
    result_state_id: str | None = None
    displacement_scale: float = 1.0
    safety_factor: float = 1.0
    purpose: str = "engineering"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_nonempty(self.id, "GeometryState id")
        if self.model_revision < 0:
            raise ValueError("GeometryState model_revision must be non-negative.")
        if self.state_type not in GEOMETRY_STATE_TYPES:
            raise ValueError(f"Unknown GeometryState state_type {self.state_type!r}.")
        if self.purpose not in GEOMETRY_STATE_PURPOSES:
            raise ValueError(f"Unknown GeometryState purpose {self.purpose!r}.")
        if self.displacement_scale <= 0.0:
            raise ValueError("GeometryState displacement_scale must be positive.")
        if self.safety_factor <= 0.0:
            raise ValueError("GeometryState safety_factor must be positive.")
        if self.purpose == "engineering" and abs(self.displacement_scale - 1.0) > 1e-12:
            raise ValueError("Engineering GeometryState must use displacement_scale=1.0; use safety_factor for conservatism.")
        object.__setattr__(self, "displacement_scale", float(self.displacement_scale))
        object.__setattr__(self, "safety_factor", float(self.safety_factor))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "model_revision": self.model_revision,
            "state_type": self.state_type,
            "displacement_scale": self.displacement_scale,
            "safety_factor": self.safety_factor,
            "purpose": self.purpose,
        }
        if self.load_case is not None:
            data["load_case"] = self.load_case
        if self.result_state_id is not None:
            data["result_state_id"] = self.result_state_id
        if self.metadata:
            data["metadata"] = dict(self.metadata)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GeometryState":
        return cls(
            id=data["id"],
            model_revision=data["model_revision"],
            state_type=data["state_type"],
            load_case=data.get("load_case"),
            result_state_id=data.get("result_state_id"),
            displacement_scale=data.get("displacement_scale", 1.0),
            safety_factor=data.get("safety_factor", 1.0),
            purpose=data.get("purpose", "engineering"),
            metadata=dict(data.get("metadata", {})),
        )


def _require_nonempty(value: str, label: str) -> None:
    if not value:
        raise ValueError(f"{label} must not be empty.")


def create_cold_geometry_state(model: Any) -> GeometryState:
    return GeometryState(
        id="geometry_state:cold",
        model_revision=_model_revision(model),
        state_type="cold",
        purpose="engineering",
    )


def create_operating_geometry_state(
    *,
    model: Any,
    result_state: Any | None = None,
    result_state_id: str | None = None,
    load_case: str | None = None,
    safety_factor: float = 1.0,
) -> GeometryState:
    resolved_result_state_id = result_state_id or getattr(result_state, "id", None)
    resolved_load_case = load_case or getattr(result_state, "load_case", None)
    if not resolved_result_state_id:
        raise ValueError("Operating GeometryState requires result_state_id or result_state.")
    if not resolved_load_case:
        raise ValueError("Operating GeometryState requires load_case or result_state.load_case.")
    return GeometryState(
        id=f"geometry_state:{resolved_load_case}:physical",
        model_revision=_model_revision(model),
        state_type="operating",
        load_case=resolved_load_case,
        result_state_id=resolved_result_state_id,
        displacement_scale=1.0,
        safety_factor=safety_factor,
        purpose="engineering",
    )


def create_visual_deformed_geometry_state(
    *,
    model: Any,
    result_state: Any | None = None,
    result_state_id: str | None = None,
    load_case: str | None = None,
    visual_scale: float = 50.0,
) -> GeometryState:
    resolved_result_state_id = result_state_id or getattr(result_state, "id", None)
    resolved_load_case = load_case or getattr(result_state, "load_case", None)
    if not resolved_result_state_id:
        raise ValueError("Visual GeometryState requires result_state_id or result_state.")
    if not resolved_load_case:
        raise ValueError("Visual GeometryState requires load_case or result_state.load_case.")
    return GeometryState(
        id=f"geometry_state:{resolved_load_case}:visual_x{_format_scale(visual_scale)}",
        model_revision=_model_revision(model),
        state_type="deformed",
        load_case=resolved_load_case,
        result_state_id=resolved_result_state_id,
        displacement_scale=visual_scale,
        purpose="visualization",
    )


def _model_revision(model: Any) -> int:
    return int(getattr(model, "revision", 0))


def _format_scale(scale: float) -> str:
    value = float(scale)
    if value.is_integer():
        return str(int(value))
    return str(value).replace(".", "_")
