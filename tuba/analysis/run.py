"""Provenance-bearing analysis run record."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tuba.analysis.mesh import AnalysisMesh
from tuba.analysis.results import ResultState
from tuba.analysis.study import AnalysisStudy
from tuba.solver.base import FEAResults


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
