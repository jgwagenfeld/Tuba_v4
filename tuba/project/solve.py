"""Project solve: bring a project's evidence up to date with its model and study.

Spec decision 13: evidence is reused only when its attested solver input matches what the model and study
would compile now and its run was verified, unless the solve is forced. Decision 11: the rest is solved and
lands in ``evidence/<operation>/`` (decision 12: nothing lands before every operation has solved and passed
the study's check, and an interrupted promotion leaves operations unsolved, never falsely attested).
Decision 18: an unverified run is written and reported. Decision 20: the solve holds the project's claim
throughout.
"""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Protocol

from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts
from tuba.analysis.run import AnalysisRun
from tuba.analysis.study import AnalysisStudy
from tuba.model import TubaModel
from tuba.project import STUDY_SCRIPT, Project
from tuba.project.claim import claim_solve
from tuba.project.evidence import evidence_dir, evidence_verdict, promote_evidence
from tuba.project.freshness import expected_identity, export_study

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
    *solver* defaults to Code_Aster. A study that cannot be solved as written raises ValueError before the
    model runs (:func:`tuba.project.study.study_settings`). Nothing reaches ``evidence/`` before every solve
    has finished and the study's ``check(solved)`` has passed, so a solve or check that raises leaves the
    evidence as it was; an interrupted promotion leaves the affected operations unsolved, never falsely
    attested.
    """
    settings = project.load_settings(study_file)
    operations, options, volume_export = settings.operations, settings.solver_options, settings.volume_export
    if not operations:
        raise ValueError(f"{project.name} has no study operations to solve.")
    namespace = project.run_model() if namespace is None else namespace
    model = namespace["model"]
    folders = {operation: evidence_dir(project.root, operation) for operation in operations}
    exporter = settings.solver()
    with claim_solve(project.root):
        solve = operations if force else tuple(
            operation
            for operation in operations
            if not evidence_verdict(
                folders[operation],
                expected_identity(model, operation, solver_options=options, volume_export=volume_export),
            ).reusable
        )
        staging = project.root / STAGING
        shutil.rmtree(staging, ignore_errors=True)
        try:
            port = solver if solver is not None else exporter
            runs = {}
            for operation in solve:
                folder = staging / operation
                folder.mkdir(parents=True)
                exported = export_study(exporter, model, operation, folder, volume_export)
                runs[operation] = port.solve_exported_study(model, exported)
            for operation in operations:
                if operation not in runs:
                    runs[operation] = import_code_aster_artifacts(model=model, work_dir=folders[operation])
            check = settings.check
            if check is not None:
                check(SimpleNamespace(model=model, namespace=namespace, runs={operation: runs[operation] for operation in operations}))
            promote_evidence({staging / operation: folders[operation] for operation in solve})
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        # A solved run was imported from staging, which is gone: read it again from its evidence folder.
        runs = {
            operation: import_code_aster_artifacts(model=model, work_dir=folders[operation]) if operation in solve else runs[operation]
            for operation in operations
        }
    return ProjectSolve(
        runs=runs,
        solved=solve,
        reused=tuple(operation for operation in operations if operation not in solve),
        unverified=tuple(
            operation for operation, run in runs.items() if run.result_state.metadata.get("result_trust") != "verified"
        ),
    )
