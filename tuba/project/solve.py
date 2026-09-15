"""Project solve: bring a project's evidence up to date with its model and study.

Spec decision 13: evidence whose attested solver input matches what the model and study would compile now
is reused, unless the solve is forced. Decision 11: the rest is solved and lands in ``evidence/<operation>/``
(decision 12: all operations or none). Decision 18: an unverified run is written and reported. Decision 20:
the solve holds the project's claim throughout.
"""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts
from tuba.analysis.provenance import SolverInputIdentity
from tuba.analysis.run import AnalysisRun
from tuba.analysis.study import AnalysisStudy
from tuba.model import TubaModel
from tuba.project import STUDY_SCRIPT, Project
from tuba.project.claim import claim_solve
from tuba.project.evidence import evidence_dir, promote_evidence
from tuba.project.freshness import expected_identity
from tuba.solver.aster import CodeAsterSolver
from tuba.solver.code_aster_runtime import load_code_aster_execution_attestation

STAGING = Path(".tuba") / "staging"


class Solver(Protocol):
    """The solver port: solve the study exported in ``study.work_dir`` and return the run imported from there.

    ``CodeAsterSolver`` is the production adapter; tests replay committed real evidence.
    """

    def solve_exported_study(self, model: TubaModel, study: AnalysisStudy) -> AnalysisRun: ...


@dataclass(frozen=True)
class ProjectSolve:
    """What a project solve did. ``runs`` holds every operation's run, imported from its evidence folder."""

    runs: dict[str, AnalysisRun]
    solved: tuple[str, ...]
    reused: tuple[str, ...]
    unverified: tuple[str, ...]


def solve_project(
    project: Project,
    namespace: Mapping[str, Any] | None = None,
    *,
    study_file: str = STUDY_SCRIPT,
    force: bool = False,
    solver: Solver | None = None,
) -> ProjectSolve:
    """Solve the study's operations whose evidence no longer matches the model and study, or all with *force*.

    *namespace* is the model script's globals, ``project.run_model()`` when omitted; a caller that already ran
    the script passes that snapshot. *study_file* picks the study, as :meth:`Project.load_study` does.
    *solver* defaults to Code_Aster. Nothing reaches ``evidence/`` before every solve has finished, so a
    solve that raises leaves the evidence as it was.
    """
    study = project.load_study(study_file)
    operations = tuple(getattr(study, "LOAD_CASES", None) or ())
    if not operations:
        raise ValueError(f"{project.name} has no study operations to solve.")
    namespace = project.run_model() if namespace is None else namespace
    model = namespace["model"]
    options = dict(getattr(study, "SOLVER_OPTIONS", None) or {})
    volume_export = getattr(study, "VOLUME_EXPORT", None) or None
    folders = {operation: evidence_dir(project.root, operation) for operation in operations}
    exporter = CodeAsterSolver(**options)  # options the solver rejects raise here, before anything is claimed
    with claim_solve(project.root):
        solve = operations if force else tuple(
            operation
            for operation in operations
            if not _evidence_attests(
                folders[operation],
                expected_identity(model, operation, solver_options=options, volume_export=volume_export),
            )
        )
        staging = project.root / STAGING
        shutil.rmtree(staging, ignore_errors=True)
        try:
            port = solver or exporter
            for operation in solve:
                folder = staging / operation
                folder.mkdir(parents=True)
                exported = (
                    exporter.export_volume_study(model, operation, folder, **dict(volume_export), export_tensor_stress=False)
                    if volume_export
                    else exporter.export_analysis_study(model, operation, folder)
                )
                port.solve_exported_study(model, exported)
            promote_evidence({staging / operation: folders[operation] for operation in solve})
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        runs = {operation: import_code_aster_artifacts(model=model, work_dir=folders[operation]) for operation in operations}
    return ProjectSolve(
        runs=runs,
        solved=solve,
        reused=tuple(operation for operation in operations if operation not in solve),
        unverified=tuple(
            operation for operation, run in runs.items() if run.result_state.metadata.get("result_trust") != "verified"
        ),
    )


def _evidence_attests(folder: Path, identity: SolverInputIdentity) -> bool:
    """Whether *folder* holds intact evidence attesting *identity*. Damaged evidence is solved again, not trusted."""
    try:
        attestation = load_code_aster_execution_attestation(folder)
    except ValueError:
        return False
    return attestation is not None and SolverInputIdentity.from_dict(attestation["solver_input_identity"]) == identity
