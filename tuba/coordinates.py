"""Coordinate-system utilities for reusable model fragments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np


VectorLike = Sequence[float] | np.ndarray


@dataclass(frozen=True)
class CoordinateSystem:
    """Right-handed local coordinate system embedded in global coordinates."""

    origin: VectorLike
    x_axis: VectorLike = (1.0, 0.0, 0.0)
    y_axis: VectorLike = (0.0, 1.0, 0.0)
    z_axis: VectorLike = (0.0, 0.0, 1.0)
    tolerance: float = 1e-9

    def __post_init__(self) -> None:
        origin = _as_vector(self.origin, "origin")
        x_axis = _unit(self.x_axis, "x_axis")
        y_axis = _unit(self.y_axis, "y_axis")
        z_axis = _unit(self.z_axis, "z_axis")

        if abs(float(np.dot(x_axis, y_axis))) > self.tolerance:
            raise ValueError("CoordinateSystem axes must be orthogonal: x_axis dot y_axis is not zero.")
        if abs(float(np.dot(x_axis, z_axis))) > self.tolerance:
            raise ValueError("CoordinateSystem axes must be orthogonal: x_axis dot z_axis is not zero.")
        if abs(float(np.dot(y_axis, z_axis))) > self.tolerance:
            raise ValueError("CoordinateSystem axes must be orthogonal: y_axis dot z_axis is not zero.")

        handedness = float(np.dot(np.cross(x_axis, y_axis), z_axis))
        if handedness <= 0.0:
            raise ValueError("CoordinateSystem axes must form a right-handed basis.")

        object.__setattr__(self, "origin", origin)
        object.__setattr__(self, "x_axis", x_axis)
        object.__setattr__(self, "y_axis", y_axis)
        object.__setattr__(self, "z_axis", z_axis)

    @classmethod
    def identity(cls) -> "CoordinateSystem":
        return cls(origin=(0.0, 0.0, 0.0))

    @property
    def basis(self) -> np.ndarray:
        return np.column_stack([self.x_axis, self.y_axis, self.z_axis])

    def to_global_point(self, point: VectorLike) -> np.ndarray:
        local = _as_vector(point, "point")
        return np.asarray(self.origin, dtype=float) + self.basis @ local

    def to_global_vector(self, vector: VectorLike) -> np.ndarray:
        local = _as_vector(vector, "vector")
        return self.basis @ local

    def to_local_point(self, point: VectorLike) -> np.ndarray:
        global_point = _as_vector(point, "point")
        return self.basis.T @ (global_point - np.asarray(self.origin, dtype=float))

    def to_dict(self) -> dict:
        return {
            "origin": np.asarray(self.origin, dtype=float).tolist(),
            "x_axis": np.asarray(self.x_axis, dtype=float).tolist(),
            "y_axis": np.asarray(self.y_axis, dtype=float).tolist(),
            "z_axis": np.asarray(self.z_axis, dtype=float).tolist(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CoordinateSystem":
        return cls(
            origin=data["origin"],
            x_axis=data.get("x_axis", (1.0, 0.0, 0.0)),
            y_axis=data.get("y_axis", (0.0, 1.0, 0.0)),
            z_axis=data.get("z_axis", (0.0, 0.0, 1.0)),
        )


def _as_vector(value: VectorLike, name: str) -> np.ndarray:
    arr = np.asarray(value, dtype=float)
    if arr.shape != (3,):
        raise ValueError(f"{name} must contain exactly three numeric values.")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must contain only finite numeric values.")
    return arr


def _unit(value: VectorLike, name: str) -> np.ndarray:
    arr = _as_vector(value, name)
    norm = float(np.linalg.norm(arr))
    if norm <= 1e-12:
        raise ValueError(f"{name} must not be the zero vector.")
    return arr / norm
