"""Freshness: whether a project's evidence still belongs to its model and study (spec decision 15).

A review is stale when, for any operation it was solved for, the identity a solve would attest now
differs from the attested one. "Now" means the current model plus the study's current solver options,
computed by the same code the Code_Aster exporters run, so a study-option change also makes it stale.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tuba.analysis.provenance import SolverInputIdentity
from tuba.model import TubaModel

if TYPE_CHECKING:
    from tuba.analysis.study import AnalysisStudy
    from tuba.solver.aster import CodeAsterSolver


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


def attested_identities(review_bundle: str | Path) -> list[SolverInputIdentity]:
    """The solver input identities a review bundle was built from, read from its ``scene.json``.

    A review without solver evidence (a model-only review) has none, so it is never stale.
    """
    try:
        scene = json.loads((Path(review_bundle) / "scene.json").read_text(encoding="utf-8"))
    except FileNotFoundError:  # no review yet, or a bundle being swapped
        return []
    return [SolverInputIdentity.from_dict(record) for record in scene.get("solver_input_identities", [])]


def export_study(
    solver: CodeAsterSolver,
    model: TubaModel,
    operation: str,
    output_dir: str | Path,
    volume_export: Mapping[str, Any] | None,
) -> AnalysisStudy:
    """Export what a solve of *operation* compiles into *output_dir*, choosing as :func:`_identity` does.

    A study with a volume export compiles 3D solids without the tensor-stress table (spec decision 19);
    every other study compiles its beams and pipes. Solves and the studio's command preview share this choice.
    """
    if volume_export:
        return solver.export_volume_study(model, operation, output_dir, **dict(volume_export), export_tensor_stress=False)
    return solver.export_analysis_study(model, operation, output_dir)


def _identity(
    solver: CodeAsterSolver,
    model: TubaModel,
    operation: str,
    volume_export: Mapping[str, Any] | None,
) -> SolverInputIdentity:
    if volume_export:
        return solver.volume_study_inputs(model, operation, **dict(volume_export)).solver_input_identity
    return solver.analysis_study_inputs(model, operation).solver_input_identity
