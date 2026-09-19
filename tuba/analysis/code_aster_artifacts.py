"""Import existing Code_Aster result artifacts into Tuba result state."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

from tuba.analysis.results import ResultState, result_state_from_fea_results
from tuba.analysis.run import AnalysisRun
from tuba.analysis.study import AnalysisStudy
from tuba.solver.aster_sidecar import load_and_attest_artifact_chain
from tuba.solver.code_aster_runtime import (
    execution_trust,
)
from tuba.analysis.provenance import SolverInputIdentity


def import_code_aster_artifacts(
    *,
    model: Any,
    work_dir: str | Path,
    study: AnalysisStudy | None = None,
    allow_unverified: bool = False,
) -> AnalysisRun:
    """Import Code_Aster results; historical unattested data requires explicit opt-in."""
    root = Path(work_dir)
    diagnostics: list[dict[str, Any]] = []
    loaded_study, analysis_mesh, _, attestation = load_and_attest_artifact_chain(model, root, study=study)
    if attestation is None and not allow_unverified:
        raise ValueError(
            "Code_Aster artifact import requires a validated solve attestation; "
            "pass allow_unverified=True only for explicit historical inspection."
        )
    if loaded_study.metadata.get("volume_analysis"):
        if analysis_mesh is None:
            raise ValueError("Code_Aster volume artifact import requires its analysis mesh.")
        from tuba.solver.aster_volume_results import parse_volume_result_artifacts

        results = parse_volume_result_artifacts(model, root, analysis_mesh, loaded_study)
    else:
        from tuba.solver import parse_tables
        results = parse_tables.parse_result_artifacts_after_validation(model, root, loaded_study.load_case)
    history_results = []
    if loaded_study.metadata.get('compiler_inputs', {}).get('contact_law'):
        from tuba.solver.contact_results import read_contact_history
        history_results = read_contact_history(model, root, loaded_study)
        results = history_results[-1]
    result_state = result_state_from_fea_results(
        model=model,
        study=loaded_study,
        results=results,
        analysis_mesh=analysis_mesh,
    )
    result_state = _with_artifact_files(result_state, _artifact_files(root, loaded_study))
    metadata = {**result_state.metadata, "result_trust": execution_trust(attestation)}
    if attestation is not None:
        metadata["solve_attestation"] = attestation
    result_state = replace(result_state, metadata=metadata)
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
    history_states = []
    history_frames = list(history_results)
    for index, frame in enumerate(history_frames):
        frame_state = result_state_from_fea_results(model=model, study=loaded_study, results=frame, analysis_mesh=analysis_mesh)
        # One frame means a single-operation study, so keep the plain state id:
        # ':step:0' names a load path's unloaded reference frame to the reports and the viewer.
        frame_id = result_state.id if len(history_frames) == 1 else f'{result_state.id}:step:{index}'
        frame_state = replace(frame_state, id=frame_id, files=result_state.files,
                              metadata={**result_state.metadata, **frame_state.metadata,
                                        'runtime_version': attestation.get('solver_version') if attestation else None})
        history_states.append(frame_state)
    if history_states:
        result_state = history_states[-1]
    return AnalysisRun(
        study=loaded_study,
        analysis_mesh=analysis_mesh,
        results=results,
        result_state=result_state,
        diagnostics=diagnostics,
        result_states=tuple(history_states),
    )


def _artifact_files(work_dir: Path, study: AnalysisStudy) -> dict[str, str]:
    files = dict(study.input_files)
    for key, filename in (
        ("execution", "study_execution.json"),
        ("contact", "study_contact.json"),
        ("manifest", "study_manifest.json"),
        ("depl", "study_depl.csv"),
        ("effo", "study_effo.csv"),
        ("reac", "study_reac.csv"),
        ("sieq", "study_sieq.csv"),
        ("sigm", "study_sigm.csv"),
        ("tuyau_subpoints", "study_sieq.csv"),
        ("rmed", "study.rmed"),
        ("mess", "study.mess"),
        ("stdout", "stdout.log"),
        ("stderr", "stderr.log"),
    ):
        path = work_dir / filename
        if path.exists():
            files[key] = str(path)
    return files


def _with_artifact_files(result_state: ResultState, files: dict[str, str]) -> ResultState:
    return replace(
        result_state,
        files={**result_state.files, **files},
        metadata={**result_state.metadata, "source": "code_aster_artifact_tables"},
    )


def _diagnostic(code: str, message: str, target: str, *, severity: str = "error") -> dict[str, Any]:
    return {
        "severity": severity,
        "code": code,
        "message": message,
        "target": target,
        "source": "tuba.analysis.code_aster_artifacts",
    }
