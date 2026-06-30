"""IFC-style placement frames for local coordinate systems."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

import numpy as np

from tuba.coordinates import CoordinateSystem


@dataclass(frozen=True)
class PlacementFrame:
    """Named local frame using IFC Axis2Placement3D semantics."""

    id: str
    origin: tuple[float, float, float]
    axis: tuple[float, float, float] = (0.0, 0.0, 1.0)
    ref_direction: tuple[float, float, float] = (1.0, 0.0, 0.0)
    parent: str | None = None
    frame_type: str = "generic"
    source: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_coordinate_system(self) -> CoordinateSystem:
        origin = _vector(self.origin, "origin")
        z_axis = _unit(self.axis, "axis")
        raw_x = _unit(self.ref_direction, "ref_direction")
        x_axis = raw_x - z_axis * float(np.dot(raw_x, z_axis))
        x_norm = float(np.linalg.norm(x_axis))
        if x_norm <= 1e-12:
            raise ValueError("PlacementFrame ref_direction must not be colinear with axis.")
        x_axis = x_axis / x_norm
        y_axis = np.cross(z_axis, x_axis)
        return CoordinateSystem(
            origin=_tuple3(origin),
            x_axis=_tuple3(x_axis),
            y_axis=_tuple3(y_axis),
            z_axis=_tuple3(z_axis),
        )

    @classmethod
    def from_coordinate_system(
        cls,
        id: str,
        coordinate_system: CoordinateSystem,
        *,
        parent: str | None = None,
        frame_type: str = "generic",
        source: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "PlacementFrame":
        return cls(
            id=id,
            origin=_tuple3(coordinate_system.origin),
            axis=_tuple3(coordinate_system.z_axis),
            ref_direction=_tuple3(coordinate_system.x_axis),
            parent=parent,
            frame_type=frame_type,
            source=source,
            metadata=dict(metadata or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "origin": list(self.origin),
            "axis": list(self.axis),
            "ref_direction": list(self.ref_direction),
            "frame_type": self.frame_type,
            "metadata": self.metadata,
        }
        if self.parent is not None:
            data["parent"] = self.parent
        if self.source is not None:
            data["source"] = self.source
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PlacementFrame":
        return cls(
            id=str(data["id"]),
            origin=_tuple3(data["origin"]),
            axis=_tuple3(data.get("axis", (0.0, 0.0, 1.0))),
            ref_direction=_tuple3(data.get("ref_direction", (1.0, 0.0, 0.0))),
            parent=data.get("parent"),
            frame_type=str(data.get("frame_type", "generic")),
            source=data.get("source"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class PlacementAssignment:
    """Assignment from a model entity to a placement frame."""

    target: str
    frame: str
    role: str = "object_placement"
    source: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "target": self.target,
            "frame": self.frame,
            "role": self.role,
            "metadata": self.metadata,
        }
        if self.source is not None:
            data["source"] = self.source
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PlacementAssignment":
        return cls(
            target=str(data["target"]),
            frame=str(data["frame"]),
            role=str(data.get("role", "object_placement")),
            source=data.get("source"),
            metadata=dict(data.get("metadata", {})),
        )


def resolve_placement_frame(frame_id: str, frames: Mapping[str, PlacementFrame]) -> CoordinateSystem:
    """Resolve a frame and its parents into a model-global coordinate system."""
    ordered: list[PlacementFrame] = []
    seen: set[str] = set()
    current_id: str | None = _ref_id(frame_id)
    while current_id is not None:
        if current_id in seen:
            raise ValueError(f"Placement frame cycle detected at {current_id!r}.")
        seen.add(current_id)
        try:
            frame = frames[current_id]
        except KeyError as exc:
            raise KeyError(f"Unknown placement frame {current_id!r}.") from exc
        ordered.append(frame)
        current_id = _ref_id(frame.parent)

    cs = CoordinateSystem.identity()
    for frame in reversed(ordered):
        local = frame.to_coordinate_system()
        cs = CoordinateSystem(
            origin=cs.to_global_point(local.origin),
            x_axis=cs.to_global_vector(local.x_axis),
            y_axis=cs.to_global_vector(local.y_axis),
            z_axis=cs.to_global_vector(local.z_axis),
        )
    return cs


def placement_frame_id(ref: str | None) -> str | None:
    """Return a bare placement frame id from a string ref."""
    return _ref_id(ref)


def _ref_id(ref: str | None) -> str | None:
    if ref is None:
        return None
    if ref.startswith("placement_frame:"):
        return ref.split(":", 1)[1]
    return ref


def _vector(value: Any, name: str) -> np.ndarray:
    arr = np.asarray(value, dtype=float)
    if arr.shape != (3,) or not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must contain three finite values.")
    return arr


def _unit(value: Any, name: str) -> np.ndarray:
    arr = _vector(value, name)
    norm = float(np.linalg.norm(arr))
    if norm <= 1e-12:
        raise ValueError(f"{name} must not be the zero vector.")
    return arr / norm


def _tuple3(value: Any) -> tuple[float, float, float]:
    arr = _vector(value, "value")
    return tuple(float(item) for item in arr)
