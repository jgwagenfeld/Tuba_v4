"""Solver-in-the-loop candidate scoring for routed pipes."""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from numbers import Real
from pathlib import Path
from typing import Any, Callable

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
    add_supports: bool = False
    support_spacing: float | None = None
    anchor_endpoints: bool = False


class SolverLoopScorer:
    """Score solved routes; standards checks require a user-supplied evaluator."""

    def __init__(
        self,
        solver_factory: Callable[[str], object] | None = None,
        compliance_evaluator: Any = None,
    ) -> None:
        self.solver_factory = solver_factory or CodeAsterSolver
        self.compliance_evaluator = compliance_evaluator

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
            created = apply_candidate_to_model(
                temp_model,
                candidate,
                request,
                add_supports=config.add_supports,
                support_spacing=config.support_spacing,
            )
            if config.anchor_endpoints:
                _anchor_created_route_endpoints(temp_model, created)
            try:
                solver = self._make_solver(study_dir, config)
                if hasattr(solver, "export_study"):
                    solver.export_study(temp_model, config.load_case, study_dir)
                if config.run_solver:
                    solved = solver.solve(temp_model, config.load_case)
                    results = getattr(solved, "results", solved)
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
    evaluator: Any,
    criteria=None,
) -> None:
    if evaluator is not None:
        report = evaluator.evaluate(model, results)
        candidate.metadata["compliance"] = {
            "overall_pass": getattr(report, "overall_pass", None),
            "worst_sustained_ratio": getattr(report, "worst_sustained_ratio", None),
            "worst_expansion_ratio": getattr(report, "worst_expansion_ratio", None),
            "results_count": len(report.results),
        }
    candidate.metadata["reactions"] = {
        node_id: _vector_to_list(node.reaction_force)
        for node_id, node in results.node_results.items()
        if node.reaction_force is not None
    }
    support_nodes = {support.node for support in model.supports} | {
        support.attached_to for support in model.supports if support.attached_to is not None
    }
    for node_id in sorted(support_nodes):
        # Missing support evidence must not hide behind another node's real reaction.
        candidate.metadata["reactions"].setdefault(node_id, None)
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
    if compliance.get("overall_pass") is None:
        failed.append("compliance_unavailable")
    elif compliance.get("overall_pass") is not True:
        failed.append("compliance_failed")
    for check in ("expansion_ratio", "sustained_ratio"):
        value = compliance.get(f"worst_{check}")
        limit = getattr(criteria, f"max_{check}", None)
        if not _finite_number(limit) or limit < 0:
            failed.append(f"{check}_invalid_limit")
        if not _finite_number(value) or value < 0:
            failed.append(f"{check}_unavailable")
        elif _finite_number(limit) and value > limit:
            failed.append(check)

    max_reaction = None
    try:
        forces = [vector[:3] for vector in candidate.metadata.get("reactions", {}).values()]
        if forces and all(len(force) == 3 and all(_finite_number(value) for value in force) for force in forces):
            magnitude = max(math.hypot(*force) for force in forces)
            if math.isfinite(magnitude):
                max_reaction = magnitude
    except (AttributeError, TypeError, ValueError, OverflowError):
        pass  # Malformed force evidence remains unavailable.
    limit = getattr(criteria, "max_anchor_reaction_n", None)
    if not _finite_number(limit) or limit < 0:
        failed.append("anchor_reaction_invalid_limit")
    if max_reaction is None:
        failed.append("anchor_reaction_unavailable")
    elif _finite_number(limit) and max_reaction > limit:
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


def _finite_number(value) -> bool:
    if not isinstance(value, Real) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except (OverflowError, TypeError, ValueError):
        return False


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


def _anchor_created_route_endpoints(model: TubaModel, created_element_ids: list[str]) -> None:
    if not created_element_ids:
        return
    elements = {element.id: element for element in model.elements}
    first = elements[created_element_ids[0]]
    last = elements[created_element_ids[-1]]
    for node_id in (first.n1, last.n2):
        if not any(support.node == node_id for support in model.supports):
            model.add_support(node_id, "anchor")


def _vector_to_list(vector) -> list[float]:
    return [float(item) for item in vector]
