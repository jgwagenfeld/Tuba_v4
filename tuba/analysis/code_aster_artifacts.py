"""Import existing Code_Aster result artifacts into Tuba result state."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from tuba.analysis.mesh import AnalysisMesh
from tuba.analysis.results import ResultState, result_state_from_fea_results
from tuba.analysis.study import AnalysisStudy
from tuba.analysis.provenance import (
    CODE_ASTER_COMPILER_ID,
    MIXED_CODE_ASTER_COMPILER_ID,
    SolverInputIdentity,
    require_matching_solver_input_identities,
    validate_solver_input_identity,
)
from tuba.solver.aster import CodeAsterSolver
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
    manifest_study, analysis_mesh = _load_manifest_records(root)
    loaded_study = study or manifest_study
    if loaded_study is None:
        manifest_path = root / "study_manifest.json"
        raise FileNotFoundError(
            f"Code_Aster artifact import requires {manifest_path}; refusing to synthesize solver lineage."
        )
    compiler_id = (
        MIXED_CODE_ASTER_COMPILER_ID
        if loaded_study.metadata.get("mixed_analysis")
        else CODE_ASTER_COMPILER_ID
    )
    sidecar, sidecar_identity = _load_sidecar(root)
    _validate_import_identities(
        model=model,
        study=loaded_study,
        manifest_study=manifest_study,
        analysis_mesh=analysis_mesh,
        sidecar=sidecar,
        sidecar_identity=sidecar_identity,
        compiler_id=compiler_id,
    )
    results = CodeAsterSolver().parse_result_artifacts(model, root, loaded_study.load_case)
    result_state = result_state_from_fea_results(
        model=model,
        study=loaded_study,
        results=results,
        analysis_mesh=analysis_mesh,
    )
    result_state = _with_artifact_files(result_state, _artifact_files(root, loaded_study))
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
    return CodeAsterArtifactImport(
        study=loaded_study,
        analysis_mesh=analysis_mesh,
        results=results,
        result_state=result_state,
        diagnostics=diagnostics,
    )


def _load_manifest_records(work_dir: Path) -> tuple[AnalysisStudy | None, AnalysisMesh | None]:
    manifest_path = work_dir / "study_manifest.json"
    if not manifest_path.exists():
        return None, None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return AnalysisStudy.from_dict(manifest["study"]), AnalysisMesh.from_dict(manifest["analysis_mesh"])
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Invalid Code_Aster study manifest {manifest_path}: {exc}") from exc


def _load_sidecar(work_dir: Path) -> tuple[dict[str, Any] | None, SolverInputIdentity | None]:
    sidecar_path = work_dir / "study_tuba_fem.json"
    if not sidecar_path.exists():
        return None, None
    try:
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        identity_data = sidecar.get("solver_input_identity")
        identity = SolverInputIdentity.from_dict(identity_data) if identity_data is not None else None
        return sidecar, identity
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Invalid Code_Aster sidecar {sidecar_path}: {exc}") from exc


def _validate_import_identities(
    *,
    model: Any,
    study: AnalysisStudy,
    manifest_study: AnalysisStudy | None,
    analysis_mesh: AnalysisMesh | None,
    sidecar: dict[str, Any] | None,
    sidecar_identity: SolverInputIdentity | None,
    compiler_id: str,
) -> None:
    identities: list[tuple[str, SolverInputIdentity | None]] = [
        (f"Code_Aster study {study.id!r}", study.solver_input_identity),
    ]
    if manifest_study is not None:
        if manifest_study.load_case != study.load_case:
            raise ValueError(
                f"Code_Aster manifest study load case {manifest_study.load_case!r} does not "
                f"match imported study load case {study.load_case!r}."
            )
        if manifest_study.mesh_id != study.mesh_id:
            raise ValueError(
                f"Code_Aster manifest study mesh {manifest_study.mesh_id!r} does not "
                f"match imported study mesh {study.mesh_id!r}."
            )
        identities.append(("Code_Aster manifest study", manifest_study.solver_input_identity))
    if analysis_mesh is not None:
        if analysis_mesh.id != study.mesh_id:
            raise ValueError(
                f"Code_Aster manifest analysis mesh {analysis_mesh.id!r} does not "
                f"match imported study mesh {study.mesh_id!r}."
            )
        identities.append(("Code_Aster manifest analysis mesh", analysis_mesh.solver_input_identity))
    if sidecar is not None:
        if sidecar.get("load_case") != study.load_case:
            raise ValueError(
                f"Code_Aster sidecar load case {sidecar.get('load_case')!r} does not "
                f"match imported study load case {study.load_case!r}."
            )
        if sidecar.get("analysis_mesh_id") != study.mesh_id:
            raise ValueError(
                f"Code_Aster sidecar mesh {sidecar.get('analysis_mesh_id')!r} does not "
                f"match imported study mesh {study.mesh_id!r}."
            )
        if sidecar_identity is None and any(identity is not None for _context, identity in identities):
            raise ValueError(
                "Code_Aster sidecar is missing a solver input identity alongside an "
                "identity-bearing study or manifest; refusing to trust its name_map."
            )
        identities.append(("Code_Aster sidecar", sidecar_identity))

    for context, identity in identities:
        validate_solver_input_identity(
            model,
            identity,
            context=context,
            expected_load_case=study.load_case,
            expected_compiler_id=compiler_id,
        )
    for index, (left_context, left_identity) in enumerate(identities):
        for right_context, right_identity in identities[index + 1 :]:
            require_matching_solver_input_identities(
                left_identity,
                right_identity,
                context=f"{left_context} and {right_context}",
            )


def _artifact_files(work_dir: Path, study: AnalysisStudy) -> dict[str, str]:
    files = dict(study.input_files)
    for key, filename in (
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
