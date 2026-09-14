"""Small AABB spatial index helpers used by clash and routing workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence, TypeVar

import numpy as np


Bounds = tuple[float, float, float, float, float, float]
T = TypeVar("T")


@dataclass(frozen=True)
class SpatialIndex:
    """Vectorized axis-aligned bounding-box index with a pure-Python surface."""

    ids: tuple[T, ...]
    bounds: np.ndarray

    def __post_init__(self) -> None:
        array = np.asarray(self.bounds, dtype=float)
        if array.size == 0:
            array = np.empty((0, 6), dtype=float)
        if array.ndim != 2 or array.shape[1] != 6:
            raise ValueError("SpatialIndex bounds must have shape (n, 6).")
        if len(self.ids) != array.shape[0]:
            raise ValueError("SpatialIndex ids length must match bounds length.")
        object.__setattr__(self, "bounds", array)

    @classmethod
    def from_bounds(cls, items: Iterable[tuple[T, Sequence[float]]]) -> "SpatialIndex[T]":
        ids: list[T] = []
        bounds: list[Bounds] = []
        for item_id, item_bounds in items:
            ids.append(item_id)
            bounds.append(coerce_bounds(item_bounds))
        return cls(ids=tuple(ids), bounds=np.asarray(bounds, dtype=float))

    def __len__(self) -> int:
        return len(self.ids)

    def query(self, bounds: Sequence[float], *, tolerance: float = 0.0) -> list[T]:
        if len(self) == 0:
            return []
        query_bounds = coerce_bounds(bounds)
        lower = np.asarray(query_bounds[:3], dtype=float) - float(tolerance)
        upper = np.asarray(query_bounds[3:], dtype=float) + float(tolerance)
        item_lower = self.bounds[:, :3]
        item_upper = self.bounds[:, 3:]
        mask = np.all((item_upper >= lower) & (item_lower <= upper), axis=1)
        return [self.ids[int(index)] for index in np.nonzero(mask)[0]]

    def candidate_pairs(
        self,
        left_bounds: Iterable[tuple[T, Sequence[float]]],
        *,
        tolerance: float = 0.0,
    ) -> list[tuple[T, T]]:
        pairs: list[tuple[T, T]] = []
        for left_id, bounds in left_bounds:
            pairs.extend((left_id, right_id) for right_id in self.query(bounds, tolerance=tolerance))
        return pairs


def bounds_overlap(left: Sequence[float], right: Sequence[float], *, tolerance: float = 0.0) -> bool:
    left_bounds = coerce_bounds(left)
    right_bounds = coerce_bounds(right)
    return all(
        left_bounds[axis + 3] + tolerance >= right_bounds[axis]
        and right_bounds[axis + 3] + tolerance >= left_bounds[axis]
        for axis in range(3)
    )


def coerce_bounds(bounds: Sequence[float]) -> Bounds:
    values = tuple(float(value) for value in bounds)
    if len(values) != 6:
        raise ValueError("AABB bounds must contain six values.")
    lower = tuple(min(values[axis], values[axis + 3]) for axis in range(3))
    upper = tuple(max(values[axis], values[axis + 3]) for axis in range(3))
    return (*lower, *upper)


def union_bounds(*bounds: Sequence[float]) -> Bounds:
    if not bounds:
        raise ValueError("union_bounds requires at least one bounds sequence.")
    normalized = np.asarray([coerce_bounds(item) for item in bounds], dtype=float)
    lower = normalized[:, :3].min(axis=0)
    upper = normalized[:, 3:].max(axis=0)
    return tuple(float(value) for value in (*lower, *upper))
