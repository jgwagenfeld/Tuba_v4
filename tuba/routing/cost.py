"""Cost functions for grid-based pipe routing."""

from __future__ import annotations

import math

import numpy as np

from tuba.model import TubaModel
from tuba.routing.cost_model import RouteCostModel
from tuba.routing.grid import RoutingGrid
from tuba.routing.types import GridIndex, PipeRouteCandidate, PipeRouteRequest


def transition_cost(
    grid: RoutingGrid,
    previous: GridIndex | None,
    current: GridIndex,
    nxt: GridIndex,
    request: PipeRouteRequest,
) -> float:
    move = np.asarray(nxt) - np.asarray(current)
    length = float(np.linalg.norm(move) * grid.cell_size)
    cost = length * request.costs.length + grid.penalty(nxt)
    if move[2] != 0:
        cost += abs(move[2]) * grid.cell_size * request.costs.vertical
    if previous is not None:
        prev_move = np.asarray(current) - np.asarray(previous)
        if not np.array_equal(prev_move, move):
            cost += request.costs.bend
    return cost


def score_candidate(
    candidate: PipeRouteCandidate,
    model: TubaModel,
    request: PipeRouteRequest,
) -> PipeRouteCandidate:
    breakdown = RouteCostModel.from_routing_weights(request.costs).evaluate_candidate(model, request, candidate)
    candidate.cost_breakdown.update(breakdown.to_legacy_dict())
    candidate.cost = breakdown.total
    return candidate
