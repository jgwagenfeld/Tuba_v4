"""High-level autorouting orchestration harness."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from tuba.model import TubaModel
from tuba.routing.adapter import apply_candidate_to_model
from tuba.routing.astar import GridRouter
from tuba.routing.report import write_route_report
from tuba.routing.solver_loop import SolverLoopConfig, SolverLoopScorer
from tuba.routing.types import PipeRouteRequest, PipeRouteResult


@dataclass
class AutoroutingRun:
    result: PipeRouteResult
    created_element_ids: list[str]
    report_path: Path


class AutoroutingAgent:
    """Coordinate route generation, study export, model application, and reporting."""

    def __init__(
        self,
        *,
        router: GridRouter | None = None,
        scorer: SolverLoopScorer | None = None,
        solver_config: SolverLoopConfig | None = None,
        output_root: str | Path = "routing_reports",
    ) -> None:
        self.router = router or GridRouter(candidate_count=3)
        self.scorer = scorer or SolverLoopScorer()
        self.solver_config = solver_config or SolverLoopConfig(run_solver=False, export_study=True)
        self.output_root = Path(output_root)

    def route_pipe(
        self,
        model: TubaModel,
        request: PipeRouteRequest,
        *,
        apply: bool = False,
        add_supports: bool = False,
        support_spacing: float | None = None,
    ) -> AutoroutingRun:
        result = self.router.route(model, request)
        route_dir = self.output_root / request.id
        if result.candidates:
            solver_config = replace(self.solver_config, work_root=route_dir / "studies")
            ranked = self.scorer.score_candidates(model, request, result.candidates, solver_config)
            selected_index = _first_valid_index(ranked)
            result = PipeRouteResult(
                request=result.request,
                candidates=ranked,
                selected_index=selected_index,
                diagnostics=result.diagnostics,
            )

        created: list[str] = []
        if apply and result.selected is not None:
            created = apply_candidate_to_model(
                model,
                result.selected,
                request,
                add_supports=add_supports,
                support_spacing=support_spacing,
            )

        report_path = write_route_report(result, route_dir, model=model)
        return AutoroutingRun(result=result, created_element_ids=created, report_path=report_path)


def _first_valid_index(result_candidates) -> int | None:
    for idx, candidate in enumerate(result_candidates):
        if candidate.is_valid:
            return idx
    return None
