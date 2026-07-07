"""Import existing Code_Aster result artifacts into Tuba result state."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from tuba.analysis.mesh import AnalysisMesh
from tuba.analysis.results import ResultState, result_state_from_fea_results
from tuba.analysis.study import AnalysisStudy
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
    load_case: str | None = None,
) -> CodeAsterArtifactImport:
    """Import an existing Code_Aster result directory without executing Code_Aster."""
    root = Path(work_dir)
    diagnostics: list[dict[str, Any]] = []
    loaded_study, analysis_mesh = _load_study_and_mesh(
        model=model,
        work_dir=root,
        explicit_study=study,
        load_case=load_case,
        diagnostics=diagnostics,
    )
    results = CodeAsterSolver().parse_result_artifacts(model, root, loaded_study.load_case)
    result_state = result_state_from_fea_results(model=model, study=loaded_study, results=results)
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


def _load_study_and_mesh(
    *,
    model: Any,
    work_dir: Path,
    explicit_study: AnalysisStudy | None,
    load_case: str | None,
    diagnostics: list[dict[str, Any]],
) -> tuple[AnalysisStudy, AnalysisMesh | None]:
    if explicit_study is not None:
        return explicit_study, _load_manifest_mesh(work_dir, diagnostics)

    manifest_path = work_dir / "study_manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            return AnalysisStudy.from_dict(manifest["study"]), AnalysisMesh.from_dict(manifest["analysis_mesh"])
        except Exception as exc:  # noqa: BLE001
            diagnostics.append(_diagnostic("visualization.code_aster_artifacts.invalid_manifest", str(exc), str(manifest_path)))

    resolved_load_case = load_case or _default_load_case(model)
    study = AnalysisStudy(
        id=f"analysis_study:{resolved_load_case}",
        model_revision=int(getattr(model, "revision", 0)),
        solver_name=CodeAsterSolver.SOLVER_NAME,
        load_case=resolved_load_case,
        work_dir=str(work_dir),
        input_files=_existing_input_files(work_dir),
        mesh_id=f"analysis_mesh:{resolved_load_case}",
        metadata={"source": "code_aster_artifacts_without_manifest"},
    )
    diagnostics.append(
        _diagnostic(
            "visualization.code_aster_artifacts.missing_manifest",
            "No study_manifest.json was found; imported result tables without analysis mesh provenance.",
            str(work_dir),
            severity="warning",
        )
    )
    return study, None


def _load_manifest_mesh(work_dir: Path, diagnostics: list[dict[str, Any]]) -> AnalysisMesh | None:
    manifest_path = work_dir / "study_manifest.json"
    if not manifest_path.exists():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return AnalysisMesh.from_dict(manifest["analysis_mesh"])
    except Exception as exc:  # noqa: BLE001
        diagnostics.append(_diagnostic("visualization.code_aster_artifacts.invalid_manifest", str(exc), str(manifest_path)))
        return None


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
    )


def _existing_input_files(work_dir: Path) -> dict[str, str]:
    return {
        key: str(work_dir / filename)
        for key, filename in (("mail", "study.mail"), ("comm", "study.comm"), ("export", "study.export"))
        if (work_dir / filename).exists()
    }


def _default_load_case(model: Any) -> str:
    load_cases = getattr(model, "load_cases", {})
    if load_cases:
        return str(next(iter(load_cases)))
    return "default"


def _diagnostic(code: str, message: str, target: str, *, severity: str = "error") -> dict[str, Any]:
    return {
        "severity": severity,
        "code": code,
        "message": message,
        "target": target,
        "source": "tuba.analysis.code_aster_artifacts",
    }
