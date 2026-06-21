"""3D occupancy grid for pipe autorouting."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np

from tuba.model import TubaModel
from tuba.routing.types import GridIndex, PipeRouteRequest, Point3D, RoutingConstraints, RoutingGridSpec


_ORTHOGONAL_DIRS: tuple[GridIndex, ...] = (
    (1, 0, 0),
    (-1, 0, 0),
    (0, 1, 0),
    (0, -1, 0),
    (0, 0, 1),
    (0, 0, -1),
)
_DIAGONAL_DIRS: tuple[GridIndex, ...] = tuple(
    (dx, dy, dz)
    for dx in (-1, 0, 1)
    for dy in (-1, 0, 1)
    for dz in (-1, 0, 1)
    if (dx, dy, dz) != (0, 0, 0)
)


@dataclass
class RoutingGrid:
    origin: np.ndarray
    cell_size: float
    occupancy: np.ndarray
    penalties: np.ndarray
    directions: tuple[GridIndex, ...] = _ORTHOGONAL_DIRS

    @classmethod
    def from_model(
        cls,
        model: TubaModel,
        request: PipeRouteRequest,
        grid_spec: RoutingGridSpec,
    ) -> "RoutingGrid":
        if grid_spec.cell_size <= 0:
            raise ValueError("Routing grid cell_size must be positive.")

        bounds_min, bounds_max = _compute_bounds(model, request, grid_spec)
        _ensure_point_in_bounds("start endpoint", request.start.point, bounds_min, bounds_max)
        _ensure_point_in_bounds("goal endpoint", request.goal.point, bounds_min, bounds_max)
        span = bounds_max - bounds_min
        shape = np.floor(span / grid_spec.cell_size + 1e-9).astype(int) + 1
        shape = np.maximum(shape, 1)
        total_cells = int(np.prod(shape))
        if total_cells > grid_spec.max_cells:
            raise ValueError(
                f"Routing grid has {total_cells} cells, exceeding max_cells={grid_spec.max_cells}."
            )

        grid = cls(
            origin=bounds_min,
            cell_size=grid_spec.cell_size,
            occupancy=np.zeros(tuple(shape), dtype=bool),
            penalties=np.zeros(tuple(shape), dtype=float),
            directions=_DIAGONAL_DIRS if grid_spec.allow_diagonal else _ORTHOGONAL_DIRS,
        )
        envelope = _clearance_envelope(model, request)

        if request.constraints.avoid_obstacles:
            for obs in model.obstacles:
                grid._mark_obstacle(obs, envelope)

        if request.constraints.avoid_existing_pipes:
            for elem in model.elements:
                section = model.sections[elem.section]
                radius = section.OD / 2.0 + request.constraints.insulation_thickness + request.constraints.clearance
                p1 = model.nodes[elem.n1].coords
                p2 = model.nodes[elem.n2].coords
                grid._mark_segment(p1, p2, radius)

        # Connection cells must remain usable even when tying into existing pipe.
        grid.unblock(grid.world_to_index(request.start.point))
        grid.unblock(grid.world_to_index(request.goal.point))
        return grid

    @property
    def shape(self) -> tuple[int, int, int]:
        return self.occupancy.shape

    def world_to_index(self, point: Sequence[float]) -> GridIndex:
        raw = (np.asarray(point, dtype=float) - self.origin) / self.cell_size
        idx = np.rint(raw).astype(int)
        return (
            int(np.clip(idx[0], 0, self.shape[0] - 1)),
            int(np.clip(idx[1], 0, self.shape[1] - 1)),
            int(np.clip(idx[2], 0, self.shape[2] - 1)),
        )

    def index_to_world(self, index: GridIndex) -> Point3D:
        coord = self.origin + np.asarray(index, dtype=float) * self.cell_size
        return (float(coord[0]), float(coord[1]), float(coord[2]))

    def is_blocked(self, index: GridIndex) -> bool:
        return bool(self.occupancy[index])

    def unblock(self, index: GridIndex) -> None:
        self.occupancy[index] = False

    def penalty(self, index: GridIndex) -> float:
        return float(self.penalties[index])

    def neighbors(
        self,
        index: GridIndex,
        constraints: RoutingConstraints,
    ) -> Iterable[GridIndex]:
        dirs = constraints.allowed_directions or self.directions
        x, y, z = index
        for dx, dy, dz in dirs:
            nxt = (x + dx, y + dy, z + dz)
            if not self._in_bounds(nxt):
                continue
            if self.is_blocked(nxt):
                continue
            yield nxt

    def validate_polyline(self, points: Sequence[Point3D], label: str = "route") -> list[str]:
        """Return diagnostics for route segments crossing blocked grid cells."""
        diagnostics: list[str] = []
        for seg_idx, (start, end) in enumerate(zip(points, points[1:])):
            a = np.asarray(start, dtype=float)
            b = np.asarray(end, dtype=float)
            length = float(np.linalg.norm(b - a))
            if length <= 1e-12:
                continue
            samples = max(int(math.ceil(length / (self.cell_size * 0.5))), 1)
            for sample_idx in range(samples + 1):
                t = sample_idx / samples
                point = a + (b - a) * t
                idx = self.world_to_index(point)
                if self.is_blocked(idx):
                    diagnostics.append(
                        f"{label} segment {seg_idx} crosses blocked cell {idx} near {self.index_to_world(idx)}."
                    )
                    break
        return diagnostics

    def _in_bounds(self, index: GridIndex) -> bool:
        return (
            0 <= index[0] < self.shape[0]
            and 0 <= index[1] < self.shape[1]
            and 0 <= index[2] < self.shape[2]
        )

    def _mark_obstacle(self, obs: dict, envelope: float) -> None:
        obs_type = obs.get("type")
        if obs_type in ("cuboid", "cylinder"):
            min_pt = np.asarray(obs["min_point"], dtype=float) - envelope
            max_pt = np.asarray(obs["max_point"], dtype=float) + envelope
            self._mark_box(min_pt, max_pt)
        elif obs_type == "mesh":
            # Conservative phase-1 fallback: use a provided bounds-like envelope
            # if available; exact mesh voxelization remains a later refinement.
            min_pt = obs.get("min_point")
            max_pt = obs.get("max_point")
            if min_pt is not None and max_pt is not None:
                self._mark_box(np.asarray(min_pt) - envelope, np.asarray(max_pt) + envelope)

    def _mark_box(self, min_pt: np.ndarray, max_pt: np.ndarray) -> None:
        lo = self.world_to_index(min_pt)
        hi = self.world_to_index(max_pt)
        xs = slice(min(lo[0], hi[0]), max(lo[0], hi[0]) + 1)
        ys = slice(min(lo[1], hi[1]), max(lo[1], hi[1]) + 1)
        zs = slice(min(lo[2], hi[2]), max(lo[2], hi[2]) + 1)
        self.occupancy[xs, ys, zs] = True

    def _mark_segment(self, p1: np.ndarray, p2: np.ndarray, radius: float) -> None:
        lo = np.minimum(p1, p2) - radius
        hi = np.maximum(p1, p2) + radius
        idx_lo = self.world_to_index(lo)
        idx_hi = self.world_to_index(hi)
        v = p2 - p1
        denom = float(np.dot(v, v))
        for ix in range(min(idx_lo[0], idx_hi[0]), max(idx_lo[0], idx_hi[0]) + 1):
            for iy in range(min(idx_lo[1], idx_hi[1]), max(idx_lo[1], idx_hi[1]) + 1):
                for iz in range(min(idx_lo[2], idx_hi[2]), max(idx_lo[2], idx_hi[2]) + 1):
                    p = np.asarray(self.index_to_world((ix, iy, iz)))
                    if denom <= 1e-12:
                        dist = np.linalg.norm(p - p1)
                    else:
                        t = float(np.clip(np.dot(p - p1, v) / denom, 0.0, 1.0))
                        closest = p1 + t * v
                        dist = np.linalg.norm(p - closest)
                    if dist <= radius + self.cell_size * 0.5:
                        self.occupancy[ix, iy, iz] = True


def _compute_bounds(
    model: TubaModel,
    request: PipeRouteRequest,
    grid_spec: RoutingGridSpec,
) -> tuple[np.ndarray, np.ndarray]:
    if grid_spec.bounds_min is not None and grid_spec.bounds_max is not None:
        return np.asarray(grid_spec.bounds_min, dtype=float), np.asarray(grid_spec.bounds_max, dtype=float)

    points: list[np.ndarray] = [
        np.asarray(request.start.point, dtype=float),
        np.asarray(request.goal.point, dtype=float),
    ]
    points.extend(node.coords for node in model.nodes.values())
    for obs in model.obstacles:
        if obs.get("min_point") is not None:
            points.append(np.asarray(obs["min_point"], dtype=float))
        if obs.get("max_point") is not None:
            points.append(np.asarray(obs["max_point"], dtype=float))
    if not points:
        points = [np.zeros(3)]

    arr = np.vstack(points)
    bounds_min = arr.min(axis=0) - grid_spec.margin
    bounds_max = arr.max(axis=0) + grid_spec.margin
    cell = grid_spec.cell_size
    bounds_min = np.floor(bounds_min / cell) * cell
    bounds_max = np.ceil(bounds_max / cell) * cell
    return bounds_min, bounds_max


def _clearance_envelope(model: TubaModel, request: PipeRouteRequest) -> float:
    section = model.sections[request.section]
    return (
        section.OD / 2.0
        + request.constraints.insulation_thickness
        + request.constraints.clearance
    )


def _ensure_point_in_bounds(
    label: str,
    point: Point3D,
    bounds_min: np.ndarray,
    bounds_max: np.ndarray,
) -> None:
    p = np.asarray(point, dtype=float)
    if np.any(p < bounds_min - 1e-9) or np.any(p > bounds_max + 1e-9):
        raise ValueError(
            f"{label} {point!r} is outside routing grid bounds "
            f"{tuple(bounds_min.tolist())} - {tuple(bounds_max.tolist())}."
        )
