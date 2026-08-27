"""Build renderer-independent engineering review packages."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

from tuba.analysis.mesh import AnalysisMesh
from tuba.analysis.results import ResultState
from tuba.analysis.run import AnalysisRun
from tuba.analysis.study import AnalysisStudy
from tuba.analysis.provenance import (
    CODE_ASTER_COMPILER_ID,
    MIXED_CODE_ASTER_COMPILER_ID,
    VOLUME_CODE_ASTER_COMPILER_ID,
    require_matching_solver_input_identities,
    validate_solver_input_identity,
)
from tuba.compliance.asme_b313 import ComplianceReport
from tuba.model import TubaModel
from tuba.reporting.model import (
    EngineeringReviewError,
    EngineeringReviewPackage,
    ReviewProvenance,
)
from tuba.reporting.tables import (
    build_code_compliance_table,
    build_diagnostics,
    build_diagnostics_table,
    build_model_tables,
    build_result_tables,
    build_studies_table,
)


def build_engineering_review(
    model: TubaModel,
    *,
    analysis_runs: Iterable[AnalysisRun] = (),
    studies: Iterable[AnalysisStudy] = (),
    analysis_meshes: Iterable[AnalysisMesh] = (),
    result_states: Iterable[ResultState] = (),
    compliance_reports: Iterable[ComplianceReport] = (),
    package_id: str | None = None,
    created_at: str | None = None,
) -> EngineeringReviewPackage:
    """Build a review package from supplied authoritative records.

    This function never invokes a solver. Result tables are emitted only after
    the supplied study/result lineage has been validated as Code_Aster output.
    """
    run_records = tuple(analysis_runs)
    study_records = tuple(studies)
    mesh_records = tuple(analysis_meshes)
    state_records = tuple(result_states)
    if run_records:
        if study_records or mesh_records or state_records:
            raise EngineeringReviewError(
                "analysis_runs cannot be mixed with lower-level studies, analysis_meshes, or result_states."
            )
        study_records = tuple(run.study for run in run_records)
        mesh_records = tuple(run.analysis_mesh for run in run_records if run.analysis_mesh is not None)
        state_records = tuple(run.result_state for run in run_records)
    compliance_records = tuple(compliance_reports)
    _validate_lineage(
        model,
        study_records,
        mesh_records,
        state_records,
        compliance_records,
    )

    status = _analysis_status(study_records, state_records, compliance_records)
    diagnostics = build_diagnostics(state_records)
    tables = list(build_model_tables(model, analysis_status=status))
    if study_records:
        tables.append(build_studies_table(study_records))
    if state_records:
        tables.extend(
            build_result_tables(
                model,
                study_records,
                state_records,
                compliance_reports=compliance_records,
            )
        )
    if compliance_records:
        tables.append(
            build_code_compliance_table(
                study_records,
                state_records,
                compliance_records,
            )
        )
    tables.append(
        build_diagnostics_table(
            diagnostics,
            studies=study_records,
            result_states=state_records,
        )
    )

    return EngineeringReviewPackage(
        package_id=package_id or _default_package_id(model),
        created_at=created_at or _utc_now(),
        project_name=model.project_name,
        model_standard=model.standard,
        model_revision=int(getattr(model, "revision", 0)),
        analysis_status=status,
        tables=tuple(tables),
        provenance=build_provenance(study_records, mesh_records, state_records),
        diagnostics=diagnostics,
    )


def _validate_lineage(
    model: TubaModel,
    studies: tuple[AnalysisStudy, ...],
    analysis_meshes: tuple[AnalysisMesh, ...],
    result_states: tuple[ResultState, ...],
    compliance_reports: tuple[ComplianceReport, ...],
) -> None:
    model_revision = int(getattr(model, "revision", 0))
    studies_by_id: dict[str, AnalysisStudy] = {}
    for study in studies:
        if study.id in studies_by_id:
            raise EngineeringReviewError(f"Duplicate supplied study {study.id!r}.")
        studies_by_id[study.id] = study
        compiler_id, compiler_inputs = _compiler_contract(study.metadata)
        _validate_solver_identity(
            model,
            study.solver_input_identity,
            f"Study {study.id!r}",
            expected_load_case=study.load_case,
            expected_compiler_id=compiler_id,
            compiler_inputs=compiler_inputs,
        )
        if study.model_revision != model_revision:
            raise EngineeringReviewError(
                f"Study {study.id!r} model revision {study.model_revision} does not "
                f"match current model revision {model_revision}."
            )

    result_ids: set[str] = set()
    result_load_cases: set[str] = set()
    result_load_case_counts: dict[str, int] = {}
    model_node_ids = set(model.nodes)
    model_element_ids = {element.id for element in model.elements}
    meshes_by_id = {mesh.id: mesh for mesh in analysis_meshes}
    for mesh in analysis_meshes:
        matching_studies = [study for study in studies if study.mesh_id == mesh.id]
        if mesh.solver_input_identity is not None and not matching_studies:
            raise EngineeringReviewError(
                f"Analysis mesh {mesh.id!r} has solver-input provenance but no supplied owning study."
            )
        for study in matching_studies:
            try:
                require_matching_solver_input_identities(
                    study.solver_input_identity,
                    mesh.solver_input_identity,
                    context=f"Study {study.id!r} and analysis mesh {mesh.id!r}",
                )
            except ValueError as exc:
                raise EngineeringReviewError(str(exc)) from exc
            compiler_id, compiler_inputs = _compiler_contract(study.metadata)
            _validate_solver_identity(
                model,
                mesh.solver_input_identity,
                f"Analysis mesh {mesh.id!r}",
                expected_load_case=study.load_case,
                expected_compiler_id=compiler_id,
                compiler_inputs=compiler_inputs,
            )
    for state in result_states:
        if state.id in result_ids:
            raise EngineeringReviewError(f"Duplicate result state {state.id!r}.")
        result_ids.add(state.id)
        compiler_id, compiler_inputs = _compiler_contract(state.metadata)
        _validate_solver_identity(
            model,
            state.solver_input_identity,
            f"Result state {state.id!r}",
            expected_load_case=state.load_case,
            expected_compiler_id=compiler_id,
            compiler_inputs=compiler_inputs,
        )
        if state.model_revision != model_revision:
            raise EngineeringReviewError(
                f"Result state {state.id!r} model revision {state.model_revision} does "
                f"not match current model revision {model_revision}."
            )
        study = studies_by_id.get(state.study_id)
        if study is None:
            raise EngineeringReviewError(
                f"Result state {state.id!r} does not reference a supplied study: "
                f"{state.study_id!r}."
            )
        if study.solver_name.casefold() != state.solver_name.casefold():
            raise EngineeringReviewError(
                f"Result state {state.id!r} solver {state.solver_name!r} does not "
                f"match study solver {study.solver_name!r}."
            )
        if state.solver_name.casefold() != "code_aster" or study.solver_name.casefold() != "code_aster":
            raise EngineeringReviewError(
                f"Production result state {state.id!r} requires Code_Aster lineage."
            )
        if study.load_case != state.load_case:
            raise EngineeringReviewError(
                f"Result state {state.id!r} load case {state.load_case!r} does not "
                f"match study load case {study.load_case!r}."
            )
        if study.mesh_id != state.mesh_id:
            raise EngineeringReviewError(
                f"Result state {state.id!r} mesh {state.mesh_id!r} does not match "
                f"study mesh {study.mesh_id!r}."
            )
        try:
            require_matching_solver_input_identities(
                study.solver_input_identity,
                state.solver_input_identity,
                context=f"Study {study.id!r} and result state {state.id!r}",
            )
            mesh = meshes_by_id.get(state.mesh_id or "")
            if mesh is not None:
                require_matching_solver_input_identities(
                    state.solver_input_identity,
                    mesh.solver_input_identity,
                    context=f"Result state {state.id!r} and analysis mesh {mesh.id!r}",
                )
        except ValueError as exc:
            raise EngineeringReviewError(str(exc)) from exc

        analysis_node_ids = _analysis_node_ids(state)
        if analysis_node_ids:
            _validate_analysis_node_lineage(
                state=state,
                study=study,
                analysis_node_ids=analysis_node_ids,
                analysis_meshes=analysis_meshes,
                model_node_ids=model_node_ids,
            )
        unknown_displacements = (
            set(state.node_displacements) - model_node_ids - analysis_node_ids
        )
        unknown_reactions = (
            set(state.node_reactions) - model_node_ids - analysis_node_ids
        )
        if unknown_displacements or unknown_reactions:
            unknown = sorted(unknown_displacements | unknown_reactions)
            raise EngineeringReviewError(
                f"Result state {state.id!r} references unknown model node(s): {unknown}."
            )
        unknown_elements = set(state.element_results) - model_element_ids
        if unknown_elements:
            raise EngineeringReviewError(
                f"Result state {state.id!r} references unknown model element(s): "
                f"{sorted(unknown_elements)}."
            )
        if not isinstance(state.metadata.get("solve_attestation"), dict):
            raise EngineeringReviewError(
                f"Result state {state.id!r} requires a verified Code_Aster solve attestation "
                "before it can enter an engineering review."
            )
        result_load_cases.add(state.load_case)
        result_load_case_counts[state.load_case] = (
            result_load_case_counts.get(state.load_case, 0) + 1
        )

    for report in compliance_reports:
        if report.load_case not in result_load_cases:
            raise EngineeringReviewError(
                f"Compliance load case {report.load_case!r} has no matching result state."
            )
        if result_load_case_counts[report.load_case] != 1:
            raise EngineeringReviewError(
                f"Compliance load case {report.load_case!r} matches multiple result states."
            )
        for result in report.results:
            element = model.get_element(result.element_id)
            if element is None:
                raise EngineeringReviewError(
                    f"Compliance result for load case {report.load_case!r} references "
                    f"unknown model element {result.element_id!r}."
                )
            if result.node_id not in model.nodes:
                raise EngineeringReviewError(
                    f"Compliance result for element {result.element_id!r} references "
                    f"unknown model node {result.node_id!r}."
                )
            if result.node_id not in {element.n1, element.n2}:
                raise EngineeringReviewError(
                    f"Compliance result node {result.node_id!r} is not an endpoint of "
                    f"model element {result.element_id!r}."
                )


def _analysis_node_ids(state: ResultState) -> set[str]:
    raw_ids = state.metadata.get("analysis_node_ids", ())
    if not isinstance(raw_ids, (list, tuple)) or not all(
        isinstance(node_id, str) and node_id for node_id in raw_ids
    ):
        raise EngineeringReviewError(
            f"Result state {state.id!r} analysis_node_ids metadata must be a list "
            "of non-empty strings."
        )
    return set(raw_ids)


def _validate_analysis_node_lineage(
    *,
    state: ResultState,
    study: AnalysisStudy,
    analysis_node_ids: set[str],
    analysis_meshes: tuple[AnalysisMesh, ...],
    model_node_ids: set[str],
) -> None:
    matches = [mesh for mesh in analysis_meshes if mesh.id == state.mesh_id]
    if len(matches) != 1:
        raise EngineeringReviewError(
            f"Result state {state.id!r} with declared analysis nodes requires "
            f"exactly one matching analysis mesh for {state.mesh_id!r}; "
            f"received {len(matches)}."
        )
    mesh = matches[0]
    if mesh.model_revision != state.model_revision:
        raise EngineeringReviewError(
            f"Analysis mesh {mesh.id!r} model revision {mesh.model_revision} does "
            f"not match result state revision {state.model_revision}."
        )
    if mesh.solver_name.casefold() != state.solver_name.casefold():
        raise EngineeringReviewError(
            f"Analysis mesh {mesh.id!r} solver {mesh.solver_name!r} does not match "
            f"result state solver {state.solver_name!r}."
        )
    if mesh.id != study.mesh_id:
        raise EngineeringReviewError(
            f"Analysis mesh {mesh.id!r} does not match study mesh {study.mesh_id!r}."
        )
    model_nodes_declared_as_analysis = analysis_node_ids & model_node_ids
    if model_nodes_declared_as_analysis:
        raise EngineeringReviewError(
            f"Result state {state.id!r} declares authoring-model nodes as analysis "
            f"nodes: {sorted(model_nodes_declared_as_analysis)}."
        )
    missing = analysis_node_ids - set(mesh.nodes)
    if missing:
        raise EngineeringReviewError(
            f"Result state {state.id!r} declares node IDs absent from the "
            f"authoritative analysis mesh {mesh.id!r}: {sorted(missing)}."
        )


def _analysis_status(
    studies: tuple[AnalysisStudy, ...],
    result_states: tuple[ResultState, ...],
    compliance_reports: tuple[ComplianceReport, ...],
) -> str:
    if not result_states:
        return "not_solved"

    solved_study_ids = {state.study_id for state in result_states}
    if any(study.id not in solved_study_ids for study in studies):
        return "partial"

    compliance_load_cases = {report.load_case for report in compliance_reports}
    result_load_cases = {state.load_case for state in result_states}
    if compliance_reports and result_load_cases <= compliance_load_cases:
        return "compliance_complete"
    return "solved"


def build_provenance(
    studies: Iterable[AnalysisStudy],
    analysis_meshes: Iterable[AnalysisMesh],
    result_states: Iterable[ResultState],
) -> tuple[ReviewProvenance, ...]:
    """Build stable provenance records without changing artifact paths."""
    records: list[ReviewProvenance] = []
    for study in sorted(studies, key=lambda record: record.id):
        metadata: dict[str, Any] = dict(study.metadata)
        metadata.update(
            {
                "mesh_id": study.mesh_id,
                "model_revision": study.model_revision,
            }
        )
        if study.work_dir is not None:
            metadata["work_dir"] = study.work_dir
        if study.solver_input_identity is not None:
            metadata["solver_input_identity"] = study.solver_input_identity.to_dict()
        records.append(
            ReviewProvenance(
                kind="study",
                id=study.id,
                solver_name=study.solver_name,
                load_case=study.load_case,
                files=dict(study.input_files),
                metadata=metadata,
            )
        )
    for mesh in sorted(analysis_meshes, key=lambda record: record.id):
        metadata = {
            "model_revision": mesh.model_revision,
            "node_count": len(mesh.nodes),
            "element_count": len(mesh.elements),
        }
        if mesh.solver_input_identity is not None:
            metadata["solver_input_identity"] = mesh.solver_input_identity.to_dict()
        records.append(
            ReviewProvenance(
                kind="analysis_mesh",
                id=mesh.id,
                solver_name=mesh.solver_name,
                load_case=(
                    mesh.solver_input_identity.load_case
                    if mesh.solver_input_identity is not None
                    else None
                ),
                files=dict(mesh.files),
                metadata=metadata,
            )
        )
    for state in sorted(result_states, key=lambda record: record.id):
        metadata = _compact_result_metadata(state)
        metadata.update(
            {
                "mesh_id": state.mesh_id,
                "model_revision": state.model_revision,
                "study_id": state.study_id,
            }
        )
        if state.solver_input_identity is not None:
            metadata["solver_input_identity"] = state.solver_input_identity.to_dict()
        records.append(
            ReviewProvenance(
                kind="result_state",
                id=state.id,
                solver_name=state.solver_name,
                load_case=state.load_case,
                files=dict(state.files),
                metadata=metadata,
            )
        )
    return tuple(records)


def _validate_solver_identity(
    model: TubaModel,
    identity: Any,
    context: str,
    *,
    expected_load_case: str,
    expected_compiler_id: str,
    compiler_inputs: dict[str, Any] | None = None,
) -> None:
    try:
        validate_solver_input_identity(
            model,
            identity,
            context=context,
            expected_load_case=expected_load_case,
            expected_compiler_id=expected_compiler_id,
            compiler_inputs=compiler_inputs,
        )
    except ValueError as exc:
        raise EngineeringReviewError(str(exc)) from exc


def _compact_result_metadata(state: ResultState) -> dict[str, Any]:
    metadata = dict(state.metadata)
    subpoints = metadata.pop("tuyau_subpoints", None)
    if isinstance(subpoints, list):
        metadata["tuyau_subpoint_count"] = len(subpoints)
        source_file = state.files.get("tuyau_subpoints") or state.files.get("sieq")
        if source_file:
            metadata["tuyau_subpoints_file"] = source_file
    volume_values = metadata.pop("volume_von_mises", None)
    if isinstance(volume_values, dict):
        metadata["volume_von_mises_count"] = len(volume_values)
        if state.files.get("sieq"):
            metadata["volume_von_mises_file"] = state.files["sieq"]
    return metadata


def _compiler_contract(metadata: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    if metadata.get("mixed_analysis"):
        return MIXED_CODE_ASTER_COMPILER_ID, metadata.get("compiler_inputs")
    if metadata.get("volume_analysis"):
        return VOLUME_CODE_ASTER_COMPILER_ID, metadata.get("compiler_inputs")
    return CODE_ASTER_COMPILER_ID, None


def _default_package_id(model: TubaModel) -> str:
    return f"review:{model.project_name}:r{int(getattr(model, 'revision', 0))}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
