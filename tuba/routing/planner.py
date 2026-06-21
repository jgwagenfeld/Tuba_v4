"""Planner interfaces for replaceable pipe routing algorithms."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from tuba.model import TubaModel
from tuba.routing.astar import GridRouter
from tuba.routing.types import GridIndex, PipeRouteRequest, PipeRouteResult, RoutingGridSpec


@dataclass(frozen=True)
class SearchState:
    cell: GridIndex
    incoming: GridIndex | None = None
    straight_run_m: float = 0.0


@runtime_checkable
class PipePlanner(Protocol):
    def plan_pipe(self, model: TubaModel, request: PipeRouteRequest) -> PipeRouteResult:
        ...


class AStarPipePlanner:
    """Pipe planner adapter backed by the existing grid A* router."""

    def __init__(
        self,
        grid_spec: RoutingGridSpec | None = None,
        *,
        max_expansions: int = 250_000,
        candidate_count: int = 1,
    ) -> None:
        self.router = GridRouter(
            grid_spec=grid_spec,
            max_expansions=max_expansions,
            candidate_count=candidate_count,
        )

    def plan_pipe(self, model: TubaModel, request: PipeRouteRequest) -> PipeRouteResult:
        return self.router.route(model, request)

    def route(self, model: TubaModel, request: PipeRouteRequest) -> PipeRouteResult:
        return self.plan_pipe(model, request)
