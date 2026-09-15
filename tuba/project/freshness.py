"""Freshness: whether a project's evidence still belongs to its model and study (spec decision 15).

A review is stale when, for any operation it was solved for, the identity a solve would attest now
differs from the attested one. "Now" means the current model plus the study's current solver options,
computed by the same code the Code_Aster exporters run, so a study-option change also makes it stale.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from tuba.analysis.provenance import SolverInputIdentity
from tuba.model import TubaModel


def expected_identity(
    model: TubaModel,
    operation: str,
    *,
    solver_options: Mapping[str, Any] | None = None,
    volume_export: Mapping[str, Any] | None = None,
) -> SolverInputIdentity:
    """The solver input identity a solve of *operation* would attest for the current model and study.

    *solver_options* and *volume_export* are the study's ``SOLVER_OPTIONS`` and ``VOLUME_EXPORT``.
    Nothing is written, meshed or solved.
    """
    from tuba.solver.aster import CodeAsterSolver

    return _identity(CodeAsterSolver(**dict(solver_options or {})), model, operation, volume_export)


def stale_operations(
    model: TubaModel,
    attested: Iterable[SolverInputIdentity],
    *,
    solver_options: Mapping[str, Any] | None = None,
    volume_export: Mapping[str, Any] | None = None,
) -> list[str]:
    """The attested operations whose identity no longer matches what the model and study would solve.

    An operation that can no longer be compiled counts as stale: a missing operation, a model that no
    longer validates, or a load path the model or study cannot run. Solver options the solver itself
    rejects (an unknown modelization, a line_segments below 1) raise instead.
    """
    from tuba.solver.aster import CodeAsterSolver

    solver = CodeAsterSolver(**dict(solver_options or {}))  # options the solver rejects raise here, not "stale"
    stale = set()
    for identity in attested:
        try:
            current = _identity(solver, model, identity.load_case, volume_export)
        except ValueError:  # the operation can no longer be compiled
            current = None
        if current != identity:
            stale.add(identity.load_case)
    return sorted(stale)


def _identity(solver: Any, model: TubaModel, operation: str, volume_export: Mapping[str, Any] | None) -> SolverInputIdentity:
    if volume_export:
        return solver.volume_study_inputs(model, operation, **dict(volume_export)).solver_input_identity
    return solver.analysis_study_inputs(model, operation).solver_input_identity
