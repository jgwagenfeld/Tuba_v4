"""Hybrid routing that combines grid and expansion-loop candidates."""

from __future__ import annotations

from dataclasses import dataclass

from tuba.model import TubaModel
from tuba.routing.astar import GridRouter
from tuba.routing.cost import score_candidate
from tuba.routing.expansion import ExpansionLoopGenerator
from tuba.routing.types import PipeRouteCandidate, PipeRouteRequest, PipeRouteResult


@dataclass(frozen=True)
class ExpansionAwareRouter:
    base_router: GridRouter
    loop_generator: ExpansionLoopGenerator

    def route(self, model: TubaModel, request: PipeRouteRequest) -> PipeRouteResult:
        base_result = self.base_router.route(model, request)
        candidates = list(base_result.candidates)

        for candidate in candidates:
            candidate.metadata.setdefault("route_family", "grid")

        for candidate in self.loop_generator.generate(model, request):
            score_candidate(candidate, model, request)
            candidates.append(candidate)

        return PipeRouteResult(
            request=request,
            candidates=candidates,
            selected_index=_best_valid_candidate_index(candidates),
            diagnostics=_scoped_base_diagnostics(base_result.diagnostics),
        )


def _best_valid_candidate_index(candidates: list[PipeRouteCandidate]) -> int | None:
    valid = [(idx, candidate.cost) for idx, candidate in enumerate(candidates) if candidate.is_valid]
    if not valid:
        return None
    return min(valid, key=lambda item: (item[1], item[0]))[0]


def _scoped_base_diagnostics(diagnostics: list[str]) -> list[str]:
    return [f"Grid router: {diagnostic}" for diagnostic in diagnostics]
