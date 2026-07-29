"""Import existing Code_Aster result artifacts into Tuba result state."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from tuba.analysis.mesh import AnalysisMesh
from tuba.analysis.results import ResultState, result_state_from_fea_results
from tuba.analysis.study import AnalysisStudy
from tuba.solver.aster import CodeAsterSolver
from tuba.solver.aster_sidecar import load_and_validate_artifact_chain
from tuba.solver.code_aster_runtime import validate_code_aster_execution_attestation
from tuba.analysis.provenance import SolverInputIdentity
from tuba.solver.base import FEAResults


@dataclass(frozen=True)
class CodeAsterArtifactImport:
    study: AnalysisStudy
    results: FEAResults
    result_state: ResultState
    analysis_mesh: AnalysisMesh | None = None
    diagnostics: list[dict[str, Any]] = field(default_factory=list)


def import_code_aster_artifacts(
    *,
    model: Any,
    work_dir: str | Path,
    study: AnalysisStudy | None = None,
) -> CodeAsterArtifactImport:
    """Import an existing Code_Aster result directory without executing Code_Aster."""
    root = Path(work_dir)
    diagnostics: list[dict[str, Any]] = []
    loaded_study, _, analysis_mesh, sidecar = load_and_validate_artifact_chain(
        model,
        root,
        study=study,
    )
    sidecar_identity = (
        None if sidecar is None or sidecar.get("solver_input_identity") is None
        else SolverInputIdentity.from_dict(sidecar["solver_input_identity"])
    )
    attestation = validate_code_aster_execution_attestation(
        root,
        study_identity=loaded_study.solver_input_identity,
        mesh_identity=None if analysis_mesh is None else analysis_mesh.solver_input_identity,
        sidecar_identity=sidecar_identity,
    )
    results = CodeAsterSolver().parse_result_artifacts(
        model,
        root,
        loaded_study.load_case,
        study=loaded_study,
    )
    result_state = result_state_from_fea_results(
        model=model,
        study=loaded_study,
        results=results,
        analysis_mesh=analysis_mesh,
    )
    result_state = _with_artifact_files(result_state, _artifact_files(root, loaded_study))
    if attestation is not None:
        result_state = replace(
            result_state,
            metadata={**result_state.metadata, "solve_attestation": attestation},
        )
    rmed_path = root / "study.rmed"
    if rmed_path.exists():
        try:
            from tuba.analysis.rmed import read_rmed_mesh_summary

            result_state = replace(
                result_state,
                metadata={**result_state.metadata, "rmed_summary": read_rmed_mesh_summary(rmed_path)},
            )
        except ImportError as exc:
            diagnostics.append(
                _diagnostic(
                    "visualization.code_aster_artifacts.rmed_optional_dependency",
                    str(exc),
                    str(rmed_path),
                    severity="warning",
                )
            )
        except Exception as exc:  # noqa: BLE001
            diagnostics.append(
                _diagnostic(
                    "visualization.code_aster_artifacts.rmed_read_failed",
                    str(exc),
                    str(rmed_path),
                    severity="warning",
                )
            )
    existing = list(result_state.metadata.get("parser_diagnostics", ()))
    combined: list[Any] = []
    seen: set[Any] = set()
    for item in [*existing, *diagnostics]:
        identity = (
            tuple(item.get(key) for key in ("severity", "code", "source", "message", "target"))
            if isinstance(item, Mapping)
            else item
        )
        if identity not in seen:
            combined.append(item)
            seen.add(identity)
    if combined:
        result_state = replace(
            result_state,
            metadata={**result_state.metadata, "parser_diagnostics": combined},
        )
    return CodeAsterArtifactImport(
        study=loaded_study,
        analysis_mesh=analysis_mesh,
        results=results,
        result_state=result_state,
        diagnostics=diagnostics,
    )


def _artifact_files(work_dir: Path, study: AnalysisStudy) -> dict[str, str]:
    files = dict(study.input_files)
    for key, filename in (
        ("execution", "study_execution.json"),
        ("manifest", "study_manifest.json"),
        ("depl", "study_depl.csv"),
        ("effo", "study_effo.csv"),
        ("reac", "study_reac.csv"),
        ("sieq", "study_sieq.csv"),
        ("tuyau_subpoints", "study_sieq.csv"),
        ("rmed", "study.rmed"),
        ("stdout", "stdout.log"),
        ("stderr", "stderr.log"),
    ):
        path = work_dir / filename
        if path.exists():
            files[key] = str(path)
    return files


def _with_artifact_files(result_state: ResultState, files: dict[str, str]) -> ResultState:
    return ResultState(
        id=result_state.id,
        study_id=result_state.study_id,
        model_revision=result_state.model_revision,
        solver_name=result_state.solver_name,
        load_case=result_state.load_case,
        mesh_id=result_state.mesh_id,
        node_displacements=result_state.node_displacements,
        node_reactions=result_state.node_reactions,
        element_results=result_state.element_results,
        files={**result_state.files, **files},
        metadata={**result_state.metadata, "source": "code_aster_artifact_tables"},
        solver_input_identity=result_state.solver_input_identity,
    )


def _diagnostic(code: str, message: str, target: str, *, severity: str = "error") -> dict[str, Any]:
    return {
        "severity": severity,
        "code": code,
        "message": message,
        "target": target,
        "source": "tuba.analysis.code_aster_artifacts",
    }
