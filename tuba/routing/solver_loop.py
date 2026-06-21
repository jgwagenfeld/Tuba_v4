"""Solver-in-the-loop candidate scoring for routed pipes."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from tuba.compliance.asme_b313 import ASMEB313Evaluator
from tuba.model import TubaModel
from tuba.routing.adapter import apply_candidate_to_model
from tuba.routing.cost import score_candidate
from tuba.routing.types import PipeRouteCandidate, PipeRouteRequest
from tuba.solver.base import FEAResults
from tuba.solver.aster import CodeAsterSolver


@dataclass
class SolverLoopConfig:
    run_solver: bool = False
    export_study: bool = True
    max_solver_candidates: int = 3
    work_root: str | Path = "routing_studies"
    load_case: str | None = None
    strict: bool = False


class SolverLoopScorer:
    def __init__(
        self,
        solver_factory: Callable[[str], object] | None = None,
        compliance_evaluator: ASMEB313Evaluator | None = None,
    ) -> None:
        self.solver_factory = solver_factory or CodeAsterSolver
        self.compliance_evaluator = compliance_evaluator or ASMEB313Evaluator()

    def score_candidates(
        self,
        model: TubaModel,
        request: PipeRouteRequest,
        candidates: list[PipeRouteCandidate],
        config: SolverLoopConfig,
    ) -> list[PipeRouteCandidate]:
        ranked = [score_candidate(candidate, model, request) for candidate in candidates]
        ranked.sort(key=lambda c: c.cost)

        for idx, candidate in enumerate(ranked[: config.max_solver_candidates]):
            study_dir = Path(config.work_root) / request.id / f"candidate_{idx}"
            candidate.metadata.setdefault("solver", {})
            candidate.metadata["solver"].update(
                {
                    "study_dir": str(study_dir),
                    "solver_ran": False,
                    "load_case": config.load_case,
                }
            )
            if not config.export_study and not config.run_solver:
                continue

            temp_model = copy.deepcopy(model)
            apply_candidate_to_model(temp_model, candidate, request)
            try:
                solver = self.solver_factory(str(study_dir))
                if hasattr(solver, "export_study"):
                    solver.export_study(temp_model, config.load_case, study_dir)
                if config.run_solver:
                    results = solver.solve(temp_model, config.load_case)
                    candidate.metadata["solver"]["solver_ran"] = True
                    candidate.metadata["solver"]["solver_name"] = results.solver_name
                    _attach_solver_result_metadata(candidate, temp_model, results, self.compliance_evaluator)
            except Exception as exc:  # noqa: BLE001 - diagnostics should survive failed candidates
                candidate.diagnostics.append(f"Solver loop failed: {exc}")
                if config.strict:
                    raise
        return ranked


def _attach_solver_result_metadata(
    candidate: PipeRouteCandidate,
    model: TubaModel,
    results: FEAResults,
    evaluator: ASMEB313Evaluator,
) -> None:
    report = evaluator.evaluate(model, results)
    candidate.metadata["compliance"] = {
        "overall_pass": report.overall_pass,
        "worst_sustained_ratio": report.worst_sustained_ratio,
        "worst_expansion_ratio": report.worst_expansion_ratio,
        "results_count": len(report.results),
    }
    candidate.metadata["reactions"] = {
        node_id: _vector_to_list(node.reaction_force)
        for node_id, node in results.node_results.items()
        if node.reaction_force is not None
    }
    candidate.metadata["displacements"] = {
        node_id: _vector_to_list(node.displacement)
        for node_id, node in results.node_results.items()
    }


def _vector_to_list(vector) -> list[float]:
    return [float(item) for item in vector]
