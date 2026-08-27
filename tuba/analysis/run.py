"""Provenance-bearing analysis run record."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
import re
from typing import Any

from tuba.analysis.mesh import AnalysisMesh
from tuba.analysis.provenance import SolverInputIdentity
from tuba.analysis.results import ResultState
from tuba.analysis.study import AnalysisStudy
from tuba.solver.base import FEAResults


_ATTESTATION_FIELDS = frozenset(
    {
        "schema_version",
        "solver_name",
        "solver_version",
        "execution_method",
        "solved_at",
        "solver_input_identity",
        "artifacts",
    }
)
_IDENTITY_FIELDS = frozenset({"fingerprint", "load_case", "schema_id", "compiler_id"})
_ARTIFACT_FIELDS = frozenset({"size_bytes", "sha256"})


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
        _validate_attestation(self.result_state.metadata.get("solve_attestation"), identity)


def _validate_attestation(value: Any, identity: SolverInputIdentity) -> None:
    if not isinstance(value, Mapping) or set(value) != _ATTESTATION_FIELDS:
        raise ValueError("AnalysisRun solve attestation is structurally invalid.")
    if value["schema_version"] != "tuba.code_aster_execution.v1":
        raise ValueError("AnalysisRun solve attestation schema is invalid.")
    if value["solver_name"] != "Code_Aster":
        raise ValueError("AnalysisRun solve attestation must name Code_Aster.")
    for field_name in ("solver_version", "execution_method"):
        if not isinstance(value[field_name], str) or not value[field_name]:
            raise ValueError(f"AnalysisRun solve attestation {field_name} is required.")
    solved_at = value["solved_at"]
    if not isinstance(solved_at, str) or not solved_at.endswith("Z"):
        raise ValueError("AnalysisRun solve attestation solved_at must be a UTC timestamp.")
    try:
        datetime.fromisoformat(f"{solved_at[:-1]}+00:00")
    except ValueError as exc:
        raise ValueError("AnalysisRun solve attestation solved_at is invalid.") from exc

    identity_payload = value["solver_input_identity"]
    if (
        not isinstance(identity_payload, Mapping)
        or set(identity_payload) != _IDENTITY_FIELDS
        or any(not isinstance(identity_payload[field], str) or not identity_payload[field] for field in _IDENTITY_FIELDS)
    ):
        raise ValueError("AnalysisRun solve attestation solver input identity is invalid.")
    if SolverInputIdentity.from_dict(dict(identity_payload)) != identity:
        raise ValueError("AnalysisRun solve attestation solver input identity does not match.")

    artifacts = value["artifacts"]
    if not isinstance(artifacts, Mapping) or not artifacts:
        raise ValueError("AnalysisRun solve attestation artifact inventory is invalid.")
    for filename, record in artifacts.items():
        if not isinstance(filename, str) or not filename or not isinstance(record, Mapping):
            raise ValueError("AnalysisRun solve attestation artifact inventory is invalid.")
        if set(record) != _ARTIFACT_FIELDS:
            raise ValueError(f"AnalysisRun solve attestation artifact {filename!r} is invalid.")
        size_bytes = record["size_bytes"]
        if isinstance(size_bytes, bool) or not isinstance(size_bytes, int) or size_bytes < 0:
            raise ValueError(f"AnalysisRun solve attestation artifact {filename!r} size is invalid.")
        if not isinstance(record["sha256"], str) or re.fullmatch(r"[0-9a-f]{64}", record["sha256"]) is None:
            raise ValueError(f"AnalysisRun solve attestation artifact {filename!r} hash is invalid.")
