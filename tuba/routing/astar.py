"""Deterministic A* pipe router over a 3D routing grid."""

from __future__ import annotations

import heapq
from dataclasses import replace

import numpy as np

from tuba.model import TubaModel
from tuba.routing.cost import score_candidate, transition_cost
from tuba.routing.grid import RoutingGrid
from tuba.routing.postprocess import build_segments, simplify_grid_path, validate_bend_geometry
from tuba.routing.types import (
    GridIndex,
    PipeRouteCandidate,
    PipeRouteRequest,
    PipeRouteResult,
    RoutingGridSpec,
)


class GridRouter:
    def __init__(
        self,
        grid_spec: RoutingGridSpec | None = None,
        max_expansions: int = 250_000,
        candidate_count: int = 1,
    ) -> None:
        self.grid_spec = grid_spec or RoutingGridSpec()
        self.max_expansions = max_expansions
        self.candidate_count = max(1, candidate_count)

    def route(
        self,
        model: TubaModel,
        request: PipeRouteRequest,
    ) -> PipeRouteResult:
        candidates: list[PipeRouteCandidate] = []
        diagnostics: list[str] = []
        blocked_alternatives: set[GridIndex] = set()

        for candidate_idx in range(self.candidate_count):
            adjusted_request = request
            if candidate_idx % 2 == 1:
                adjusted_request = replace(
                    request,
                    costs=replace(request.costs, bend=request.costs.bend * 1.5),
                )
            try:
                grid = RoutingGrid.from_model(model, adjusted_request, self.grid_spec)
            except ValueError as exc:
                return PipeRouteResult(request=request, candidates=[], selected_index=None, diagnostics=[str(exc)])

            for idx in blocked_alternatives:
                if idx not in (grid.world_to_index(request.start.point), grid.world_to_index(request.goal.point)):
                    grid.occupancy[idx] = True

            path = self._search(grid, adjusted_request)
            if path is None:
                if candidates:
                    diagnostics.append("No additional route found for request " + request.id)
                else:
                    diagnostics.append("No route found for request " + request.id)
                break

            raw_points = [grid.index_to_world(idx) for idx in path]
            raw_points[0] = request.start.point
            raw_points[-1] = request.goal.point
            points = simplify_grid_path(raw_points)
            diag = validate_bend_geometry(points, request.constraints)
            diag.extend(grid.validate_polyline(points, request.id))
            segments = build_segments(points, request.constraints)
            candidate = PipeRouteCandidate(
                request_id=request.id,
                points=points,
                segments=segments,
                cost=0.0,
                cost_breakdown={},
                diagnostics=diag,
                is_valid=not diag,
            )
            score_candidate(candidate, model, request)
            candidates.append(candidate)

            # Encourage alternative candidates by blocking interior cells.
            for idx in path[1:-1]:
                blocked_alternatives.add(idx)

        selected_index = _best_valid_candidate_index(candidates)
        if candidates and selected_index is None:
            diagnostics.append("No valid route candidates found for request " + request.id)
        return PipeRouteResult(
            request=request,
            candidates=candidates,
            selected_index=selected_index,
            diagnostics=diagnostics,
        )

    def _search(self, grid: RoutingGrid, request: PipeRouteRequest) -> list[GridIndex] | None:
        start = grid.world_to_index(request.start.point)
        goal = grid.world_to_index(request.goal.point)
        start_dir = _endpoint_grid_direction(request.start.direction)
        goal_dir = _endpoint_grid_direction(request.goal.direction)
        open_heap: list[tuple[float, int, GridIndex]] = []
        heapq.heappush(open_heap, (self._heuristic(start, goal), 0, start))
        came_from: dict[GridIndex, GridIndex | None] = {start: None}
        g_score: dict[GridIndex, float] = {start: 0.0}
        counter = 0
        expansions = 0

        while open_heap:
            _prio, _order, current = heapq.heappop(open_heap)
            if current == goal:
                return self._reconstruct(came_from, current)
            expansions += 1
            if expansions > self.max_expansions:
                return None

            previous = came_from[current]
            for nxt in grid.neighbors(current, request.constraints):
                move = _move(current, nxt)
                if not _respects_start_departure(
                    start,
                    current,
                    move,
                    start_dir,
                    request.start.min_straight,
                    grid.cell_size,
                ):
                    continue
                if nxt == goal and not _respects_goal_approach(
                    came_from,
                    current,
                    move,
                    goal_dir,
                    request.goal.min_straight,
                    grid.cell_size,
                ):
                    continue
                tentative = g_score[current] + transition_cost(grid, previous, current, nxt, request)
                if tentative >= g_score.get(nxt, float("inf")):
                    continue
                came_from[nxt] = current
                g_score[nxt] = tentative
                counter += 1
                priority = tentative + self._heuristic(nxt, goal)
                heapq.heappush(open_heap, (priority, counter, nxt))
        return None

    @staticmethod
    def _heuristic(a: GridIndex, b: GridIndex) -> float:
        return float(abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2]))

    @staticmethod
    def _reconstruct(came_from: dict[GridIndex, GridIndex | None], current: GridIndex) -> list[GridIndex]:
        path = [current]
        while came_from[current] is not None:
            current = came_from[current]  # type: ignore[assignment]
            path.append(current)
        path.reverse()
        return path


def _best_valid_candidate_index(candidates: list[PipeRouteCandidate]) -> int | None:
    valid = [(idx, candidate.cost) for idx, candidate in enumerate(candidates) if candidate.is_valid]
    if not valid:
        return None
    return min(valid, key=lambda item: (item[1], item[0]))[0]


def _move(current: GridIndex, nxt: GridIndex) -> GridIndex:
    return (nxt[0] - current[0], nxt[1] - current[1], nxt[2] - current[2])


def _endpoint_grid_direction(direction: tuple[float, float, float] | None) -> GridIndex | None:
    if direction is None:
        return None
    vec = np.asarray(direction, dtype=float)
    norm = float(np.linalg.norm(vec))
    if norm <= 1e-12:
        return None
    axis = int(np.argmax(np.abs(vec)))
    result = [0, 0, 0]
    result[axis] = 1 if vec[axis] > 0 else -1
    return (result[0], result[1], result[2])


def _respects_start_departure(
    start: GridIndex,
    current: GridIndex,
    move: GridIndex,
    start_dir: GridIndex | None,
    min_straight: float,
    cell_size: float,
) -> bool:
    if start_dir is None:
        return True
    if current == start:
        return move == start_dir
    if min_straight <= 0:
        return True

    delta = _move(start, current)
    axis_steps = [delta[i] * start_dir[i] for i in range(3) if start_dir[i] != 0]
    off_axis = any(delta[i] != 0 for i in range(3) if start_dir[i] == 0)
    if off_axis or not axis_steps or axis_steps[0] < 0:
        return True
    distance_from_start = axis_steps[0] * cell_size
    if distance_from_start + 1e-9 < min_straight:
        return move == start_dir
    return True


def _respects_goal_approach(
    came_from: dict[GridIndex, GridIndex | None],
    current: GridIndex,
    move: GridIndex,
    goal_dir: GridIndex | None,
    min_straight: float,
    cell_size: float,
) -> bool:
    if goal_dir is not None and move != goal_dir:
        return False
    if min_straight <= 0:
        return True

    run_length = cell_size
    cursor = current
    while came_from.get(cursor) is not None:
        previous = came_from[cursor]
        if previous is None:
            break
        if _move(previous, cursor) != move:
            break
        run_length += cell_size
        cursor = previous
    return run_length + 1e-9 >= min_straight
