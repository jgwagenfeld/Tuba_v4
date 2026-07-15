"""Build renderer-independent engineering review packages."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

from tuba.analysis.results import ResultState
from tuba.analysis.study import AnalysisStudy
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
    studies: Iterable[AnalysisStudy] = (),
    result_states: Iterable[ResultState] = (),
    compliance_reports: Iterable[ComplianceReport] = (),
    package_id: str | None = None,
    created_at: str | None = None,
) -> EngineeringReviewPackage:
    """Build a review package from supplied authoritative records.

    This function never invokes a solver. Result tables are emitted only after
    the supplied study/result lineage has been validated as Code_Aster output.
    """
    study_records = tuple(studies)
    state_records = tuple(result_states)
    compliance_records = tuple(compliance_reports)
    _validate_lineage(model, study_records, state_records, compliance_records)

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
        provenance=build_provenance(study_records, state_records),
        diagnostics=diagnostics,
    )


def _validate_lineage(
    model: TubaModel,
    studies: tuple[AnalysisStudy, ...],
    result_states: tuple[ResultState, ...],
    compliance_reports: tuple[ComplianceReport, ...],
) -> None:
    model_revision = int(getattr(model, "revision", 0))
    studies_by_id: dict[str, AnalysisStudy] = {}
    for study in studies:
        if study.id in studies_by_id:
            raise EngineeringReviewError(f"Duplicate supplied study {study.id!r}.")
        studies_by_id[study.id] = study
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
    for state in result_states:
        if state.id in result_ids:
            raise EngineeringReviewError(f"Duplicate result state {state.id!r}.")
        result_ids.add(state.id)
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

        unknown_displacements = set(state.node_displacements) - model_node_ids
        unknown_reactions = set(state.node_reactions) - model_node_ids
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
    for state in sorted(result_states, key=lambda record: record.id):
        metadata = dict(state.metadata)
        metadata.update(
            {
                "mesh_id": state.mesh_id,
                "model_revision": state.model_revision,
                "study_id": state.study_id,
            }
        )
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


def _default_package_id(model: TubaModel) -> str:
    return f"review:{model.project_name}:r{int(getattr(model, 'revision', 0))}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
