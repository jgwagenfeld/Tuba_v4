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


_SOLVER_ACCEPTANCE_DIAGNOSTIC_PREFIX = "Solver acceptance failed:"
_SOLVER_ACCEPTANCE_RESTORE_VALID_ATTR = "_solver_acceptance_restore_valid"


@dataclass
class SolverLoopConfig:
    run_solver: bool = False
    export_study: bool = True
    max_solver_candidates: int = 3
    work_root: str | Path = "routing_studies"
    load_case: str | None = None
    strict: bool = False
    exec_method: str = "auto"
    wsl_distro: str | None = None
    docker_image: str | None = None


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

        for candidate in ranked:
            _reset_solver_result_metadata(candidate)

        for idx, candidate in enumerate(ranked[: config.max_solver_candidates]):
            study_dir = Path(config.work_root) / request.id / f"candidate_{idx}"
            candidate.metadata["solver"] = (
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
                solver = self._make_solver(study_dir, config)
                if hasattr(solver, "export_study"):
                    solver.export_study(temp_model, config.load_case, study_dir)
                if config.run_solver:
                    results = solver.solve(temp_model, config.load_case)
                    candidate.metadata["solver"]["solver_ran"] = True
                    candidate.metadata["solver"]["solver_name"] = results.solver_name
                    _attach_solver_result_metadata(
                        candidate,
                        temp_model,
                        results,
                        self.compliance_evaluator,
                        request.solver_acceptance,
                    )
            except Exception as exc:  # noqa: BLE001 - diagnostics should survive failed candidates
                candidate.diagnostics.append(f"Solver loop failed: {exc}")
                if config.strict:
                    raise
        if any("solver_acceptance" in candidate.metadata for candidate in ranked):
            ranked.sort(key=lambda c: (not c.is_valid, c.cost))
        return ranked

    def _make_solver(self, study_dir: Path, config: SolverLoopConfig):
        kwargs = {
            "exec_method": config.exec_method,
        }
        if config.wsl_distro is not None:
            kwargs["wsl_distro"] = config.wsl_distro
        if config.docker_image is not None:
            kwargs["docker_image"] = config.docker_image
        if kwargs == {"exec_method": "auto"}:
            return self.solver_factory(str(study_dir))
        try:
            return self.solver_factory(str(study_dir), **kwargs)
        except TypeError:
            return self.solver_factory(str(study_dir))


def _attach_solver_result_metadata(
    candidate: PipeRouteCandidate,
    model: TubaModel,
    results: FEAResults,
    evaluator: ASMEB313Evaluator,
    criteria=None,
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
    _attach_solver_acceptance(candidate, criteria)


def _attach_solver_acceptance(candidate: PipeRouteCandidate, criteria) -> None:
    _clear_solver_acceptance(candidate)

    if criteria is None:
        return

    compliance = candidate.metadata.get("compliance", {})
    failed: list[str] = []
    if compliance.get("worst_expansion_ratio", 0.0) > criteria.max_expansion_ratio:
        failed.append("expansion_ratio")
    if compliance.get("worst_sustained_ratio", 0.0) > criteria.max_sustained_ratio:
        failed.append("sustained_ratio")

    max_reaction = 0.0
    for vector in candidate.metadata.get("reactions", {}).values():
        force = vector[:3]
        max_reaction = max(max_reaction, float(sum(component * component for component in force) ** 0.5))
    if max_reaction > criteria.max_anchor_reaction_n:
        failed.append("anchor_reaction")

    candidate.metadata["solver_acceptance"] = {
        "accepted": not failed,
        "failed_checks": failed,
        "max_reaction_n": max_reaction,
    }
    if failed:
        setattr(candidate, _SOLVER_ACCEPTANCE_RESTORE_VALID_ATTR, candidate.is_valid)
        candidate.is_valid = False
        candidate.diagnostics.append(f"{_SOLVER_ACCEPTANCE_DIAGNOSTIC_PREFIX} " + ", ".join(failed))


def _reset_solver_result_metadata(candidate: PipeRouteCandidate) -> None:
    _clear_solver_acceptance(candidate)
    for key in ("solver", "compliance", "reactions", "displacements"):
        candidate.metadata.pop(key, None)


def _clear_solver_acceptance(candidate: PipeRouteCandidate) -> None:
    restored_valid = getattr(candidate, _SOLVER_ACCEPTANCE_RESTORE_VALID_ATTR, None)
    if restored_valid is not None:
        candidate.is_valid = bool(restored_valid)
        delattr(candidate, _SOLVER_ACCEPTANCE_RESTORE_VALID_ATTR)
    candidate.metadata.pop("solver_acceptance", None)
    candidate.metadata.pop("_solver_acceptance_restore_valid", None)
    candidate.diagnostics = [
        diagnostic
        for diagnostic in candidate.diagnostics
        if not diagnostic.startswith(_SOLVER_ACCEPTANCE_DIAGNOSTIC_PREFIX)
    ]


def _vector_to_list(vector) -> list[float]:
    return [float(item) for item in vector]
