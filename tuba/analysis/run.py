"""Provenance-bearing analysis run record."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tuba.analysis.mesh import AnalysisMesh
from tuba.analysis.results import ResultState
from tuba.analysis.study import AnalysisStudy
from tuba.solver.base import FEAResults
from tuba.solver.code_aster_runtime import (
    expected_code_aster_artifact_files,
    validate_code_aster_execution_attestation_payload,
)


@dataclass(frozen=True)
class AnalysisRun:
    study: AnalysisStudy
    results: FEAResults
    result_state: ResultState
    analysis_mesh: AnalysisMesh | None = None
    diagnostics: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.result_state.study_id != self.study.id:
            raise ValueError("AnalysisRun result state does not belong to its study.")
        if self.result_state.mesh_id != self.study.mesh_id:
            raise ValueError("AnalysisRun result state mesh does not match its study.")
        if self.analysis_mesh is not None and self.analysis_mesh.id != self.study.mesh_id:
            raise ValueError("AnalysisRun analysis mesh does not match its study.")

    def validate_for_publication(self, model: Any) -> None:
        """Require verified Code_Aster lineage before publishing this run."""
        model_revision = int(getattr(model, "revision", 0))
        revision_records = [
            ("study", self.study.model_revision),
            ("result state", self.result_state.model_revision),
        ]
        if self.analysis_mesh is not None:
            revision_records.append(("analysis mesh", self.analysis_mesh.model_revision))
        for label, revision in revision_records:
            if revision != model_revision:
                raise ValueError(
                    f"AnalysisRun {label} model revision {revision} does not match "
                    f"current model revision {model_revision}."
                )

        solver_records = [
            ("study", self.study.solver_name),
            ("raw results", self.results.solver_name),
            ("result state", self.result_state.solver_name),
        ]
        if self.analysis_mesh is not None:
            solver_records.append(("analysis mesh", self.analysis_mesh.solver_name))
        for label, solver_name in solver_records:
            if solver_name != "Code_Aster":
                raise ValueError(f"AnalysisRun {label} must name Code_Aster as its solver.")

        load_cases = {
            self.study.load_case,
            self.results.load_case,
            self.result_state.load_case,
        }
        if len(load_cases) != 1:
            raise ValueError("AnalysisRun study, raw results, and result state load cases do not match.")

        identity = self.study.solver_input_identity
        if identity is None or self.result_state.solver_input_identity is None:
            raise ValueError("AnalysisRun study and result state require a solver input identity.")
        if self.result_state.solver_input_identity != identity:
            raise ValueError("AnalysisRun study and result state solver input identities do not match.")
        if self.analysis_mesh is not None:
            if self.analysis_mesh.solver_input_identity is None:
                raise ValueError("AnalysisRun analysis mesh requires a solver input identity.")
            if self.analysis_mesh.solver_input_identity != identity:
                raise ValueError("AnalysisRun analysis mesh solver input identity does not match.")

        if self.result_state.metadata.get("result_trust") != "verified":
            raise ValueError("AnalysisRun result state requires result_trust == 'verified'.")
        attestation_identity = validate_code_aster_execution_attestation_payload(
            self.result_state.metadata.get("solve_attestation"),
            expected_artifacts=expected_code_aster_artifact_files(self.study.metadata),
        )
        if attestation_identity != identity:
            raise ValueError("AnalysisRun solve attestation solver input identity does not match.")
