"""Provenance-bearing analysis run record."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
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
    result_states: tuple[ResultState, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "result_states", tuple(self.result_states))
        if self.result_states and self.result_states[-1] != self.result_state:
            raise ValueError("AnalysisRun final history entry must equal result_state.")
        states = self.result_states or (self.result_state,)
        for state in states:
            if state.study_id != self.study.id:
                raise ValueError("AnalysisRun result state does not belong to its study.")
            if state.mesh_id != self.study.mesh_id:
                raise ValueError("AnalysisRun result state mesh does not match its study.")
        if self.analysis_mesh is not None and self.analysis_mesh.id != self.study.mesh_id:
            raise ValueError("AnalysisRun analysis mesh does not match its study.")
        if self.result_states:
            previous_time = -math.inf
            previous_stage = -1
            stage_labels: dict[int, str] = {}
            ids: set[str] = set()
            for state in states:
                stage = state.metadata.get("stage_index")
                label = state.metadata.get("stage_label")
                time = state.metadata.get("pseudo_time")
                if isinstance(stage, bool) or not isinstance(stage, int) or stage < previous_stage or stage < 0:
                    raise ValueError("AnalysisRun history requires non-negative, ordered stage_index values.")
                if not isinstance(label, str) or not label.strip():
                    raise ValueError("AnalysisRun history requires a stage_label.")
                if stage in stage_labels and stage_labels[stage] != label:
                    raise ValueError("AnalysisRun history stage_label must be consistent within a stage.")
                if isinstance(time, bool) or not isinstance(time, (int, float)) or not math.isfinite(time) or time <= previous_time:
                    raise ValueError("AnalysisRun history requires finite, strictly increasing pseudo_time values.")
                if state.id in ids:
                    raise ValueError("AnalysisRun history requires distinct result state IDs.")
                ids.add(state.id)
                stage_labels[stage] = label
                previous_stage, previous_time = stage, time

    def validate_for_publication(self, model: Any) -> None:
        """Require verified Code_Aster lineage for every published increment."""
        for state in self.result_states or (self.result_state,):
            self._validate_state_for_publication(model, state)

    def _validate_state_for_publication(self, model: Any, state: ResultState) -> None:
        model_revision = int(getattr(model, "revision", 0))
        revision_records = [
            ("study", self.study.model_revision),
            ("result state", state.model_revision),
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
            ("result state", state.solver_name),
        ]
        if self.analysis_mesh is not None:
            solver_records.append(("analysis mesh", self.analysis_mesh.solver_name))
        for label, solver_name in solver_records:
            if solver_name != "Code_Aster":
                raise ValueError(f"AnalysisRun {label} must name Code_Aster as its solver.")

        load_cases = {
            self.study.load_case,
            self.results.load_case,
            state.load_case,
        }
        if len(load_cases) != 1:
            raise ValueError("AnalysisRun study, raw results, and result state load cases do not match.")

        identity = self.study.solver_input_identity
        if identity is None or state.solver_input_identity is None:
            raise ValueError("AnalysisRun study and result state require a solver input identity.")
        if state.solver_input_identity != identity:
            raise ValueError("AnalysisRun study and result state solver input identities do not match.")
        if self.analysis_mesh is not None:
            if self.analysis_mesh.solver_input_identity is None:
                raise ValueError("AnalysisRun analysis mesh requires a solver input identity.")
            if self.analysis_mesh.solver_input_identity != identity:
                raise ValueError("AnalysisRun analysis mesh solver input identity does not match.")

        if state.metadata.get("result_trust") != "verified":
            raise ValueError("AnalysisRun result state requires result_trust == 'verified'.")
        attestation_identity = validate_code_aster_execution_attestation_payload(
            state.metadata.get("solve_attestation"),
            expected_artifacts=expected_code_aster_artifact_files(
                self.study.metadata,
                compiler_id=identity.compiler_id,
            ),
        )
        if attestation_identity != identity:
            raise ValueError("AnalysisRun solve attestation solver input identity does not match.")
