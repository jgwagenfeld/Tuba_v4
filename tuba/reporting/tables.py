"""Pure report-table builders for authoritative :class:`TubaModel` inputs."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from typing import Any

from tuba.analysis.results import ResultState
from tuba.analysis.study import AnalysisStudy
from tuba.compliance.asme_b313 import ComplianceReport
from tuba.model import (
    BarSection,
    CableSection,
    Element,
    IBeamSection,
    LoadCase,
    Operation,
    OperationField,
    PipeSection,
    RectangularSection,
    TubaModel,
)
from tuba.reporting.model import (
    EngineeringReviewError,
    ReportColumn,
    ReportTable,
    ReviewDiagnostic,
)


SOLVER_COLUMNS = (
    ReportColumn("solver_name", "Solver"),
    ReportColumn("study_id", "Study ID"),
    ReportColumn("result_state_id", "Result state ID"),
    ReportColumn("load_case", "Load case"),
)

FE_STRESS_BASIS = "FE Von Mises (not piping-code stress)"


def build_project_summary_table(
    model: TubaModel,
    *,
    analysis_status: str = "not_solved",
) -> ReportTable:
    """Summarize authoritative model identity and input-record counts."""
    return ReportTable(
        id="project_summary",
        title="Project summary",
        source="model",
        columns=(
            ReportColumn("project_name", "Project"),
            ReportColumn("model_standard", "Design standard"),
            ReportColumn("model_revision", "Model revision"),
            ReportColumn("analysis_status", "Analysis status"),
            ReportColumn("node_count", "Nodes"),
            ReportColumn("element_count", "Elements"),
            ReportColumn("section_count", "Sections"),
            ReportColumn("material_count", "Materials"),
            ReportColumn("support_count", "Supports"),
            ReportColumn("load_case_count", "Load cases and operations"),
        ),
        rows=(
            {
                "project_name": model.project_name,
                "model_standard": model.standard,
                "model_revision": int(getattr(model, "revision", 0)),
                "analysis_status": analysis_status,
                "node_count": len(model.nodes),
                "element_count": len(model.elements),
                "section_count": len(model.sections),
                "material_count": len(model.materials),
                "support_count": len(model.supports),
                "load_case_count": len(model.load_cases) + len(model.operations),
            },
        ),
    )


def build_nodes_table(model: TubaModel) -> ReportTable:
    """List model nodes in stable identifier order."""
    rows = tuple(
        {
            "node_id": node_id,
            "x_m": float(model.nodes[node_id].coords[0]),
            "y_m": float(model.nodes[node_id].coords[1]),
            "z_m": float(model.nodes[node_id].coords[2]),
        }
        for node_id in sorted(model.nodes)
    )
    return ReportTable(
        id="nodes",
        title="Nodes",
        source="model",
        columns=(
            ReportColumn("node_id", "Node"),
            ReportColumn("x_m", "X", unit="m"),
            ReportColumn("y_m", "Y", unit="m"),
            ReportColumn("z_m", "Z", unit="m"),
        ),
        rows=rows,
    )


def build_line_list_table(model: TubaModel) -> ReportTable:
    """List full element definitions and geometry-derived lengths."""
    rows = tuple(
        {
            "element_id": element.id,
            "element_type": element.type,
            "start_node": element.n1,
            "end_node": element.n2,
            "section": element.section,
            "material": element.material,
            "length_m": _element_length_m(model, element),
            "route_id": element.route_id,
            "station_start_m": element.station_start,
            "station_end_m": element.station_end,
            "bend_radius_m": element.bend_radius,
            "bend_angle_deg": element.bend_angle,
            "bend_geometry": (
                element.bend_geometry.to_dict() if element.bend_geometry is not None else None
            ),
            "twist_angle_deg": element.twist_angle,
        }
        for element in sorted(model.elements, key=lambda record: record.id)
    )
    return ReportTable(
        id="line_list",
        title="Line list",
        source="model",
        columns=(
            ReportColumn("element_id", "Element"),
            ReportColumn("element_type", "Type"),
            ReportColumn("start_node", "Start node"),
            ReportColumn("end_node", "End node"),
            ReportColumn("section", "Section"),
            ReportColumn("material", "Material"),
            ReportColumn("length_m", "Length", unit="m"),
            ReportColumn("route_id", "Route"),
            ReportColumn("station_start_m", "Start station", unit="m"),
            ReportColumn("station_end_m", "End station", unit="m"),
            ReportColumn("bend_radius_m", "Bend radius", unit="m"),
            ReportColumn("bend_angle_deg", "Bend angle", unit="deg"),
            ReportColumn("bend_geometry", "Bend geometry"),
            ReportColumn("twist_angle_deg", "Twist angle", unit="deg"),
        ),
        rows=rows,
    )


def build_section_schedule_table(model: TubaModel) -> ReportTable:
    """List section definitions with quantities derived from model elements."""
    rows = []
    for section_name in sorted(model.sections):
        section = model.sections[section_name]
        elements = [element for element in model.elements if element.section == section_name]
        rows.append(
            {
                "section": section_name,
                "section_type": _section_type(section),
                **_section_definition(section),
                "area_m2": _section_area_m2(section),
                "element_count": len(elements),
                "total_length_m": _section_total_length_m(model, elements),
                "total_mass_kg": _section_total_mass_kg(model, section, elements),
            }
        )
    return ReportTable(
        id="section_schedule",
        title="Section schedule",
        source="model",
        columns=(
            ReportColumn("section", "Section"),
            ReportColumn("section_type", "Type"),
            ReportColumn("outer_diameter_m", "Outer diameter", unit="m"),
            ReportColumn("wall_thickness_m", "Wall thickness", unit="m"),
            ReportColumn("corrosion_allowance_m", "Corrosion allowance", unit="m"),
            ReportColumn("radius_m", "Radius", unit="m"),
            ReportColumn("pretension_n", "Pretension", unit="N"),
            ReportColumn("height_y_m", "Y height", unit="m"),
            ReportColumn("height_z_m", "Z height", unit="m"),
            ReportColumn("thickness_y_m", "Y thickness", unit="m"),
            ReportColumn("thickness_z_m", "Z thickness", unit="m"),
            ReportColumn("profile_name", "Profile"),
            ReportColumn("properties", "Profile properties"),
            ReportColumn("area_m2", "Area", unit="m^2"),
            ReportColumn("element_count", "Elements"),
            ReportColumn(
                "total_length_m",
                "Total length",
                unit="m",
                description="Sum of node-to-node straight lengths and radius-times-angle bend arcs.",
            ),
            ReportColumn(
                "total_mass_kg",
                "Total mass",
                unit="kg",
                description="Sum of section area times element length times material density.",
            ),
        ),
        rows=tuple(rows),
    )


def build_materials_table(model: TubaModel) -> ReportTable:
    """List full material inputs, including temperature-dependent allowables."""
    rows = tuple(
        {
            "material": name,
            "youngs_modulus_pa": float(material.E),
            "poisson_ratio": float(material.nu),
            "density_kg_m3": float(material.rho),
            "thermal_expansion_1_k": float(material.alpha),
            "allowable_stress": [
                {
                    "temperature_c": float(temperature),
                    "allowable_stress_pa": float(material.allowable_stress[temperature]),
                }
                for temperature in sorted(material.allowable_stress)
            ],
        }
        for name, material in sorted(model.materials.items())
    )
    return ReportTable(
        id="materials",
        title="Materials",
        source="model",
        columns=(
            ReportColumn("material", "Material"),
            ReportColumn("youngs_modulus_pa", "Young's modulus", unit="Pa"),
            ReportColumn("poisson_ratio", "Poisson ratio"),
            ReportColumn("density_kg_m3", "Density", unit="kg/m^3"),
            ReportColumn("thermal_expansion_1_k", "Thermal expansion", unit="1/K"),
            ReportColumn(
                "allowable_stress",
                "Allowable stress schedule",
                description="Temperature in degrees Celsius and allowable stress in pascals.",
            ),
        ),
        rows=rows,
    )


def build_supports_table(model: TubaModel) -> ReportTable:
    """List every defining support input without filling absent values."""
    supports = sorted(
        model.supports,
        key=lambda support: (
            support.id is None,
            support.id or "",
            support.node,
            support.type,
        ),
    )
    rows = tuple(
        {
            "support_id": support.id,
            "node": support.node,
            "support_type": support.type,
            "direction": _optional_list(support.direction),
            "stiffness_n_m": support.stiffness,
            "imposed_displacement_m": _optional_list(support.imposed_displacement),
            "stiffness_matrix": _optional_list(support.stiffness_matrix),
            "blocked_dof": _optional_list(support.blocked_dof),
            "mass_kg": support.mass,
            "friction_coefficient": support.friction_coefficient,
        }
        for support in supports
    )
    return ReportTable(
        id="supports",
        title="Supports",
        source="model",
        columns=(
            ReportColumn("support_id", "Support"),
            ReportColumn("node", "Node"),
            ReportColumn("support_type", "Type"),
            ReportColumn("direction", "Direction"),
            ReportColumn("stiffness_n_m", "Stiffness", unit="N/m"),
            ReportColumn("imposed_displacement_m", "Imposed displacement", unit="m"),
            ReportColumn("stiffness_matrix", "Stiffness matrix"),
            ReportColumn("blocked_dof", "Blocked degrees of freedom"),
            ReportColumn("mass_kg", "Mass", unit="kg"),
            ReportColumn("friction_coefficient", "Friction coefficient"),
        ),
        rows=rows,
    )


def build_load_cases_table(model: TubaModel) -> ReportTable:
    """Summarize load definitions while retaining their nested input records."""
    definitions: list[tuple[str, str, LoadCase | Operation]] = [
        (name, "load_case", load_case) for name, load_case in model.load_cases.items()
    ]
    definitions.extend(
        (name, "operation", operation) for name, operation in model.operations.items()
    )
    rows = tuple(
        {
            "load_case": name,
            "definition_type": definition_type,
            "gravity": definition.gravity,
            "internal_pressure_pa": definition.internal_pressure,
            "temperature_c": definition.temperature,
            "reference_temperature_c": definition.ref_temperature,
            "nodal_load_count": len(definition.nodal_forces),
            "field_count": len(definition.fields),
            "nodal_forces": [force.to_dict() for force in definition.nodal_forces],
            "fields": [_operation_field_dict(field) for field in definition.fields],
            "metadata": (
                _sorted_mapping(definition.metadata)
                if isinstance(definition, Operation)
                else {}
            ),
        }
        for name, definition_type, definition in sorted(
            definitions, key=lambda item: (item[0], item[1])
        )
    )
    return ReportTable(
        id="load_cases",
        title="Load cases and operations",
        source="model",
        columns=(
            ReportColumn("load_case", "Load case"),
            ReportColumn("definition_type", "Definition type"),
            ReportColumn("gravity", "Gravity"),
            ReportColumn("internal_pressure_pa", "Internal pressure", unit="Pa"),
            ReportColumn("temperature_c", "Temperature", unit="degC"),
            ReportColumn("reference_temperature_c", "Reference temperature", unit="degC"),
            ReportColumn("nodal_load_count", "Nodal loads"),
            ReportColumn("field_count", "Operation fields"),
            ReportColumn("nodal_forces", "Nodal force definitions"),
            ReportColumn("fields", "Operation field definitions"),
            ReportColumn("metadata", "Operation metadata"),
        ),
        rows=rows,
    )


MODEL_TABLE_BUILDERS = (
    build_project_summary_table,
    build_nodes_table,
    build_line_list_table,
    build_section_schedule_table,
    build_materials_table,
    build_supports_table,
    build_load_cases_table,
)


def build_model_tables(
    model: TubaModel,
    *,
    analysis_status: str = "not_solved",
) -> tuple[ReportTable, ...]:
    """Build the stable model/input table registry for an engineering review."""
    return tuple(
        builder(model, analysis_status=analysis_status)
        if builder is build_project_summary_table
        else builder(model)
        for builder in MODEL_TABLE_BUILDERS
    )


def build_studies_table(studies: Iterable[AnalysisStudy]) -> ReportTable:
    """List caller-supplied solver studies without inferring solve status."""
    rows = tuple(
        {
            "study_id": study.id,
            "solver_name": study.solver_name,
            "load_case": study.load_case,
            "model_revision": study.model_revision,
            "mesh_id": study.mesh_id,
            "work_dir": study.work_dir,
            "input_files": _sorted_mapping(study.input_files),
            "metadata": _sorted_mapping(study.metadata),
        }
        for study in sorted(studies, key=lambda record: record.id)
    )
    return ReportTable(
        id="studies",
        title="Analysis studies",
        source="study",
        columns=(
            ReportColumn("study_id", "Study ID"),
            ReportColumn("solver_name", "Solver"),
            ReportColumn("load_case", "Load case"),
            ReportColumn("model_revision", "Model revision"),
            ReportColumn("mesh_id", "Mesh ID"),
            ReportColumn("work_dir", "Work directory"),
            ReportColumn("input_files", "Input artifacts"),
            ReportColumn("metadata", "Metadata"),
        ),
        rows=rows,
    )


def build_result_tables(
    model: TubaModel,
    studies: Iterable[AnalysisStudy],
    result_states: Iterable[ResultState],
    *,
    compliance_reports: Iterable[ComplianceReport] = (),
) -> tuple[ReportTable, ...]:
    """Build Code_Aster-derived tables after the caller validates lineage."""
    study_by_id = {study.id: study for study in studies}
    states = tuple(sorted(result_states, key=lambda record: (record.load_case, record.id)))
    for state in states:
        if state.study_id not in study_by_id:
            raise EngineeringReviewError(
                f"Result state {state.id!r} does not reference a supplied study."
            )
    return (
        build_result_summary_table(
            model,
            study_by_id,
            states,
            compliance_reports=compliance_reports,
        ),
        build_displacements_table(study_by_id, states),
        build_reactions_table(model, study_by_id, states),
        build_element_forces_table(model, study_by_id, states),
        build_fe_stress_table(study_by_id, states),
    )


def build_displacements_table(
    studies_by_id: Mapping[str, AnalysisStudy],
    result_states: Iterable[ResultState],
) -> ReportTable:
    rows = tuple(_displacement_rows(studies_by_id, result_states))
    return ReportTable(
        id="displacements",
        title="Node displacements",
        source="result_state",
        columns=SOLVER_COLUMNS
        + (
            ReportColumn("entity_ref", "Entity reference"),
            ReportColumn("location_kind", "Location kind"),
            ReportColumn("node_id", "Node"),
            ReportColumn("dx", "DX", unit="m"),
            ReportColumn("dy", "DY", unit="m"),
            ReportColumn("dz", "DZ", unit="m"),
            ReportColumn("drx", "DRX", unit="rad"),
            ReportColumn("dry", "DRY", unit="rad"),
            ReportColumn("drz", "DRZ", unit="rad"),
            ReportColumn("translation_magnitude", "Translation magnitude", unit="m"),
            ReportColumn("rotation_magnitude", "Rotation magnitude", unit="rad"),
        ),
        rows=rows,
    )


def build_reactions_table(
    model: TubaModel,
    studies_by_id: Mapping[str, AnalysisStudy],
    result_states: Iterable[ResultState],
) -> ReportTable:
    rows = tuple(_reaction_rows(model, studies_by_id, result_states))
    return ReportTable(
        id="reactions",
        title="Support reactions",
        source="result_state",
        columns=SOLVER_COLUMNS
        + (
            ReportColumn("entity_ref", "Entity reference"),
            ReportColumn("location_kind", "Location kind"),
            ReportColumn("node_id", "Node"),
            ReportColumn("support_ids", "Supports"),
            ReportColumn("fx", "FX", unit="N"),
            ReportColumn("fy", "FY", unit="N"),
            ReportColumn("fz", "FZ", unit="N"),
            ReportColumn("mx", "MX", unit="N*m"),
            ReportColumn("my", "MY", unit="N*m"),
            ReportColumn("mz", "MZ", unit="N*m"),
            ReportColumn("force_magnitude", "Force magnitude", unit="N"),
            ReportColumn("moment_magnitude", "Moment magnitude", unit="N*m"),
        ),
        rows=rows,
    )


def build_element_forces_table(
    model: TubaModel,
    studies_by_id: Mapping[str, AnalysisStudy],
    result_states: Iterable[ResultState],
) -> ReportTable:
    rows = tuple(_element_force_rows(model, studies_by_id, result_states))
    return ReportTable(
        id="element_forces",
        title="Element end forces",
        source="result_state",
        columns=SOLVER_COLUMNS
        + (
            ReportColumn("entity_ref", "Entity reference"),
            ReportColumn("element_id", "Element"),
            ReportColumn("element_end", "Element end"),
            ReportColumn("node_id", "Node"),
            ReportColumn("fx", "FX", unit="N"),
            ReportColumn("fy", "FY", unit="N"),
            ReportColumn("fz", "FZ", unit="N"),
            ReportColumn("mx", "MX", unit="N*m"),
            ReportColumn("my", "MY", unit="N*m"),
            ReportColumn("mz", "MZ", unit="N*m"),
            ReportColumn("force_magnitude", "Force magnitude", unit="N"),
            ReportColumn("moment_magnitude", "Moment magnitude", unit="N*m"),
        ),
        rows=rows,
    )


def build_fe_stress_table(
    studies_by_id: Mapping[str, AnalysisStudy],
    result_states: Iterable[ResultState],
) -> ReportTable:
    rows = tuple(_fe_stress_rows(studies_by_id, result_states))
    return ReportTable(
        id="fe_stress",
        title="Finite-element Von Mises stress",
        source="result_state",
        columns=SOLVER_COLUMNS
        + (
            ReportColumn("entity_ref", "Entity reference"),
            ReportColumn("element_id", "Element"),
            ReportColumn("von_mises_n1_pa", "Von Mises at N1", unit="Pa"),
            ReportColumn("von_mises_n2_pa", "Von Mises at N2", unit="Pa"),
            ReportColumn("max_von_mises_pa", "Maximum Von Mises", unit="Pa"),
            ReportColumn("result_basis", "Result basis"),
        ),
        rows=rows,
    )


def build_result_summary_table(
    model: TubaModel,
    studies_by_id: Mapping[str, AnalysisStudy],
    result_states: Iterable[ResultState],
    *,
    compliance_reports: Iterable[ComplianceReport] = (),
) -> ReportTable:
    states = tuple(result_states)
    rows: list[dict[str, Any]] = []
    for state in states:
        study = studies_by_id[state.study_id]
        identity = _solver_identity(study, state)
        displacement_rows = list(_displacement_rows(studies_by_id, (state,)))
        if displacement_rows:
            governing = max(
                displacement_rows,
                key=lambda row: (row["translation_magnitude"], row["entity_ref"]),
            )
            rows.append(
                _summary_row(
                    identity,
                    result_type="translation_magnitude",
                    maximum_value=governing["translation_magnitude"],
                    unit="m",
                    result_basis="Code_Aster nodal displacement",
                    governing_entity_ref=governing["entity_ref"],
                    governing_location=governing["node_id"],
                )
            )
        reaction_rows = list(_reaction_rows(model, studies_by_id, (state,)))
        if reaction_rows:
            governing = max(
                reaction_rows,
                key=lambda row: (row["force_magnitude"], row["entity_ref"]),
            )
            rows.append(
                _summary_row(
                    identity,
                    result_type="reaction_force_magnitude",
                    maximum_value=governing["force_magnitude"],
                    unit="N",
                    result_basis="Code_Aster nodal reaction",
                    governing_entity_ref=governing["entity_ref"],
                    governing_location=governing["node_id"],
                )
            )
        force_rows = [
            row
            for row in _element_force_rows(model, studies_by_id, (state,))
            if row["force_magnitude"] is not None
        ]
        if force_rows:
            governing = max(
                force_rows,
                key=lambda row: (
                    row["force_magnitude"],
                    row["entity_ref"],
                    row["element_end"],
                ),
            )
            rows.append(
                _summary_row(
                    identity,
                    result_type="element_force_magnitude",
                    maximum_value=governing["force_magnitude"],
                    unit="N",
                    result_basis="Code_Aster element end force",
                    governing_entity_ref=governing["entity_ref"],
                    governing_location=governing["element_end"],
                )
            )
        stress_rows = list(_fe_stress_rows(studies_by_id, (state,)))
        if stress_rows:
            governing = max(
                stress_rows,
                key=lambda row: (row["max_von_mises_pa"], row["entity_ref"]),
            )
            rows.append(
                _summary_row(
                    identity,
                    result_type="fe_von_mises",
                    maximum_value=governing["max_von_mises_pa"],
                    unit="Pa",
                    result_basis=FE_STRESS_BASIS,
                    governing_entity_ref=governing["entity_ref"],
                )
            )
    states_by_load_case = {state.load_case: state for state in states}
    for report in compliance_reports:
        state = states_by_load_case[report.load_case]
        identity = _solver_identity(studies_by_id[state.study_id], state)
        if not report.results:
            continue
        sustained = max(
            report.results,
            key=lambda result: (
                result.sustained_ratio,
                result.element_id,
                result.node_id,
            ),
        )
        rows.append(
            _summary_row(
                identity,
                result_type="sustained_code_utilization",
                maximum_value=sustained.sustained_ratio,
                unit="ratio",
                result_basis=f"{report.code_name}-{report.code_edition} sustained code check",
                governing_entity_ref=f"element:{sustained.element_id}",
                governing_location=sustained.node_id,
            )
        )
        expansion = max(
            report.results,
            key=lambda result: (
                result.expansion_ratio,
                result.element_id,
                result.node_id,
            ),
        )
        rows.append(
            _summary_row(
                identity,
                result_type="expansion_code_utilization",
                maximum_value=expansion.expansion_ratio,
                unit="ratio",
                result_basis=f"{report.code_name}-{report.code_edition} expansion code check",
                governing_entity_ref=f"element:{expansion.element_id}",
                governing_location=expansion.node_id,
            )
        )
    return ReportTable(
        id="result_summary",
        title="Governing result summary",
        source="result_state",
        columns=SOLVER_COLUMNS
        + (
            ReportColumn("result_type", "Result type"),
            ReportColumn("maximum_value", "Maximum value"),
            ReportColumn("unit", "Unit"),
            ReportColumn("result_basis", "Result basis"),
            ReportColumn("governing_entity_ref", "Governing entity"),
            ReportColumn("governing_location", "Governing location"),
        ),
        rows=tuple(rows),
    )


def build_code_compliance_table(
    studies: Iterable[AnalysisStudy],
    result_states: Iterable[ResultState],
    compliance_reports: Iterable[ComplianceReport],
) -> ReportTable:
    """Build authoritative piping-code checks from compliance reports only."""
    studies_by_id = {study.id: study for study in studies}
    states_by_load_case = {state.load_case: state for state in result_states}
    rows: list[dict[str, Any]] = []
    for report in compliance_reports:
        state = states_by_load_case[report.load_case]
        identity = _solver_identity(studies_by_id[state.study_id], state)
        for result in report.results:
            rows.append(
                {
                    **identity,
                    "code_name": report.code_name,
                    "code_edition": report.code_edition,
                    "entity_ref": f"element:{result.element_id}",
                    "element_id": result.element_id,
                    "node_id": result.node_id,
                    "sustained_stress_pa": result.sustained_stress,
                    "sustained_allowable_pa": result.sustained_allowable,
                    "sustained_ratio": result.sustained_ratio,
                    "sustained_pass": result.sustained_pass,
                    "expansion_stress_pa": result.expansion_stress,
                    "expansion_allowable_pa": result.expansion_allowable,
                    "expansion_ratio": result.expansion_ratio,
                    "expansion_pass": result.expansion_pass,
                    "pressure": result.pressure,
                    "Do": result.Do,
                    "t": result.t,
                    "Z": result.Z,
                    "i_i": result.i_i,
                    "i_o": result.i_o,
                    "k": result.k,
                    "h": result.h,
                    "M_i": result.M_i,
                    "M_o": result.M_o,
                    "M_t": result.M_t,
                    "moment_basis": result.moment_basis,
                    "S_h": result.S_h,
                    "S_c": result.S_c,
                    "f": result.f,
                }
            )
    return ReportTable(
        id="code_compliance",
        title="Piping code compliance",
        source="compliance_report",
        columns=SOLVER_COLUMNS
        + (
            ReportColumn("code_name", "Code"),
            ReportColumn("code_edition", "Edition"),
            ReportColumn("entity_ref", "Entity reference"),
            ReportColumn("element_id", "Element"),
            ReportColumn("node_id", "Node"),
            ReportColumn("sustained_stress_pa", "Sustained stress", unit="Pa"),
            ReportColumn("sustained_allowable_pa", "Sustained allowable", unit="Pa"),
            ReportColumn("sustained_ratio", "Sustained code utilization"),
            ReportColumn("sustained_pass", "Sustained pass"),
            ReportColumn("expansion_stress_pa", "Expansion stress", unit="Pa"),
            ReportColumn("expansion_allowable_pa", "Expansion allowable", unit="Pa"),
            ReportColumn("expansion_ratio", "Expansion code utilization"),
            ReportColumn("expansion_pass", "Expansion pass"),
            ReportColumn("pressure", "Pressure", unit="Pa"),
            ReportColumn("Do", "Outer diameter", unit="m"),
            ReportColumn("t", "Corroded wall thickness", unit="m"),
            ReportColumn("Z", "Section modulus", unit="m^3"),
            ReportColumn("i_i", "In-plane SIF"),
            ReportColumn("i_o", "Out-of-plane SIF"),
            ReportColumn("k", "Flexibility factor"),
            ReportColumn("h", "Flexibility characteristic"),
            ReportColumn("M_i", "In-plane moment", unit="N*m"),
            ReportColumn("M_o", "Out-of-plane moment", unit="N*m"),
            ReportColumn("M_t", "Torsional moment", unit="N*m"),
            ReportColumn("moment_basis", "Moment basis"),
            ReportColumn("S_h", "Hot allowable", unit="Pa"),
            ReportColumn("S_c", "Cold allowable", unit="Pa"),
            ReportColumn("f", "Stress-range reduction factor"),
        ),
        rows=tuple(rows),
    )


def build_diagnostics(result_states: Iterable[ResultState]) -> tuple[ReviewDiagnostic, ...]:
    diagnostics: list[ReviewDiagnostic] = []
    for state in sorted(result_states, key=lambda record: (record.load_case, record.id)):
        for entry in state.metadata.get("parser_diagnostics", ()):
            target = f"result_state:{state.id}"
            if isinstance(entry, Mapping):
                diagnostics.append(
                    ReviewDiagnostic(
                        severity=str(entry.get("severity", "warning")),
                        code=str(entry.get("code", "SOLVER_PARSER_DIAGNOSTIC")),
                        source=str(entry.get("source", target)),
                        message=str(entry.get("message", entry)),
                        target=str(entry.get("target", target)),
                    )
                )
            else:
                diagnostics.append(
                    ReviewDiagnostic(
                        severity="warning",
                        code="SOLVER_PARSER_DIAGNOSTIC",
                        source=target,
                        message=str(entry),
                        target=target,
                    )
                )
    return tuple(diagnostics)


def build_diagnostics_table(
    diagnostics: Iterable[ReviewDiagnostic],
    *,
    studies: Iterable[AnalysisStudy] = (),
    result_states: Iterable[ResultState] = (),
) -> ReportTable:
    diagnostic_records = tuple(diagnostics)
    studies_by_id = {study.id: study for study in studies}
    identities = tuple(_parser_diagnostic_identities(studies_by_id, result_states))
    if identities and len(identities) != len(diagnostic_records):
        raise EngineeringReviewError(
            "Parser diagnostic lineage does not match the package diagnostics."
        )
    rows = tuple(
        {
            **(identities[index] if identities else {}),
            **diagnostic.to_dict(),
        }
        for index, diagnostic in enumerate(diagnostic_records)
    )
    return ReportTable(
        id="diagnostics",
        title="Review diagnostics",
        source="diagnostics",
        columns=SOLVER_COLUMNS
        + (
            ReportColumn("severity", "Severity"),
            ReportColumn("code", "Code"),
            ReportColumn("source", "Source"),
            ReportColumn("target", "Target"),
            ReportColumn("message", "Message"),
        ),
        rows=rows,
    )


def _parser_diagnostic_identities(
    studies_by_id: Mapping[str, AnalysisStudy],
    result_states: Iterable[ResultState],
) -> Iterable[dict[str, str]]:
    for state in sorted(result_states, key=lambda record: (record.load_case, record.id)):
        study = studies_by_id[state.study_id]
        identity = _solver_identity(study, state)
        for _entry in state.metadata.get("parser_diagnostics", ()):
            yield identity


def _solver_identity(study: AnalysisStudy, state: ResultState) -> dict[str, str]:
    return {
        "solver_name": state.solver_name,
        "study_id": study.id,
        "result_state_id": state.id,
        "load_case": state.load_case,
    }


def _displacement_rows(
    studies_by_id: Mapping[str, AnalysisStudy],
    result_states: Iterable[ResultState],
) -> Iterable[dict[str, Any]]:
    for state in result_states:
        identity = _solver_identity(studies_by_id[state.study_id], state)
        for node_id, values in sorted(state.node_displacements.items()):
            dx, dy, dz, drx, dry, drz = values
            entity_ref, location_kind = _node_location(state, node_id)
            yield {
                **identity,
                "entity_ref": entity_ref,
                "location_kind": location_kind,
                "node_id": node_id,
                "dx": dx,
                "dy": dy,
                "dz": dz,
                "drx": drx,
                "dry": dry,
                "drz": drz,
                "translation_magnitude": math.sqrt(dx * dx + dy * dy + dz * dz),
                "rotation_magnitude": math.sqrt(drx * drx + dry * dry + drz * drz),
            }


def _reaction_rows(
    model: TubaModel,
    studies_by_id: Mapping[str, AnalysisStudy],
    result_states: Iterable[ResultState],
) -> Iterable[dict[str, Any]]:
    support_ids_by_node: dict[str, list[str]] = {}
    for support in model.supports:
        if support.id is not None:
            support_ids_by_node.setdefault(support.node, []).append(support.id)
    for support_ids in support_ids_by_node.values():
        support_ids.sort()

    for state in result_states:
        identity = _solver_identity(studies_by_id[state.study_id], state)
        for node_id, values in sorted(state.node_reactions.items()):
            fx, fy, fz, mx, my, mz = values
            entity_ref, location_kind = _node_location(state, node_id)
            yield {
                **identity,
                "entity_ref": entity_ref,
                "location_kind": location_kind,
                "node_id": node_id,
                "support_ids": list(support_ids_by_node.get(node_id, ())),
                "fx": fx,
                "fy": fy,
                "fz": fz,
                "mx": mx,
                "my": my,
                "mz": mz,
                "force_magnitude": math.sqrt(fx * fx + fy * fy + fz * fz),
                "moment_magnitude": math.sqrt(mx * mx + my * my + mz * mz),
            }


def _node_location(state: ResultState, node_id: str) -> tuple[str, str]:
    analysis_node_ids = set(state.metadata.get("analysis_node_ids", ()))
    if node_id in analysis_node_ids:
        return f"analysis_node:{node_id}", "analysis_node"
    return f"node:{node_id}", "model_node"


def _element_force_rows(
    model: TubaModel,
    studies_by_id: Mapping[str, AnalysisStudy],
    result_states: Iterable[ResultState],
) -> Iterable[dict[str, Any]]:
    elements_by_id = {element.id: element for element in model.elements}
    for state in result_states:
        identity = _solver_identity(studies_by_id[state.study_id], state)
        for element_id, result in sorted(state.element_results.items()):
            element = elements_by_id[element_id]
            for element_end, node_id, key in (
                ("n1", element.n1, "forces_n1"),
                ("n2", element.n2, "forces_n2"),
            ):
                fx, fy, fz, mx, my, mz = _required_vector(
                    result, key, state_id=state.id, element_id=element_id
                )
                yield {
                    **identity,
                    "entity_ref": f"element:{element_id}",
                    "element_id": element_id,
                    "element_end": element_end,
                    "node_id": node_id,
                    "fx": fx,
                    "fy": fy,
                    "fz": fz,
                    "mx": mx,
                    "my": my,
                    "mz": mz,
                    "force_magnitude": _optional_magnitude(fx, fy, fz),
                    "moment_magnitude": _optional_magnitude(mx, my, mz),
                }


def _fe_stress_rows(
    studies_by_id: Mapping[str, AnalysisStudy],
    result_states: Iterable[ResultState],
) -> Iterable[dict[str, Any]]:
    for state in result_states:
        identity = _solver_identity(studies_by_id[state.study_id], state)
        for element_id, result in sorted(state.element_results.items()):
            if not any(key in result for key in ("von_mises_n1", "von_mises_n2", "max_von_mises")):
                continue
            yield {
                **identity,
                "entity_ref": f"element:{element_id}",
                "element_id": element_id,
                "von_mises_n1_pa": _required_float(
                    result, "von_mises_n1", state_id=state.id, element_id=element_id
                ),
                "von_mises_n2_pa": _required_float(
                    result, "von_mises_n2", state_id=state.id, element_id=element_id
                ),
                "max_von_mises_pa": _required_float(
                    result, "max_von_mises", state_id=state.id, element_id=element_id
                ),
                "result_basis": FE_STRESS_BASIS,
            }


def _summary_row(
    identity: Mapping[str, str],
    *,
    result_type: str,
    maximum_value: float,
    unit: str,
    result_basis: str,
    governing_entity_ref: str,
    governing_location: str | None = None,
) -> dict[str, Any]:
    if not governing_entity_ref:
        raise EngineeringReviewError(
            f"Summary maximum {result_type!r} has no governing entity reference."
        )
    return {
        **identity,
        "result_type": result_type,
        "maximum_value": maximum_value,
        "unit": unit,
        "result_basis": result_basis,
        "governing_entity_ref": governing_entity_ref,
        "governing_location": governing_location,
    }


def _required_vector(
    result: Mapping[str, Any],
    key: str,
    *,
    state_id: str,
    element_id: str,
) -> tuple[float | None, float | None, float | None, float | None, float | None, float | None]:
    if key not in result:
        raise EngineeringReviewError(
            f"Result state {state_id!r} element {element_id!r} is missing solver value {key!r}."
        )
    try:
        values = tuple(None if value is None else float(value) for value in result[key])
    except (TypeError, ValueError) as error:
        raise EngineeringReviewError(
            f"Result state {state_id!r} element {element_id!r} has invalid solver value {key!r}."
        ) from error
    if len(values) != 6:
        raise EngineeringReviewError(
            f"Result state {state_id!r} element {element_id!r} solver value {key!r} "
            "must contain six components."
        )
    return values  # type: ignore[return-value]


def _optional_magnitude(*values: float | None) -> float | None:
    if any(value is None for value in values):
        return None
    return math.sqrt(sum(value * value for value in values if value is not None))


def _required_float(
    result: Mapping[str, Any],
    key: str,
    *,
    state_id: str,
    element_id: str,
) -> float:
    if key not in result:
        raise EngineeringReviewError(
            f"Result state {state_id!r} element {element_id!r} is missing solver value {key!r}."
        )
    try:
        return float(result[key])
    except (TypeError, ValueError) as error:
        raise EngineeringReviewError(
            f"Result state {state_id!r} element {element_id!r} has invalid solver value {key!r}."
        ) from error


def _element_length_m(model: TubaModel, element: Element) -> float | None:
    """Return chord length for straight elements or ``radius * radians(angle)`` for bends."""
    if element.type == "pipe_bend":
        radius = element.bend_radius
        angle = element.bend_angle
        if radius is None and element.bend_geometry is not None:
            radius = element.bend_geometry.radius
        if angle is None and element.bend_geometry is not None:
            angle = element.bend_geometry.angle
        if radius is None or angle is None:
            return None
        return abs(float(radius) * math.radians(float(angle)))

    try:
        start = model.nodes[element.n1].coords
        end = model.nodes[element.n2].coords
    except KeyError:
        return None
    return math.dist(start, end)


def _section_type(section: Any) -> str:
    names = {
        PipeSection: "pipe",
        BarSection: "bar",
        CableSection: "cable",
        RectangularSection: "rectangular",
        IBeamSection: "ibeam",
    }
    return names.get(type(section), type(section).__name__)


def _section_definition(section: Any) -> dict[str, Any]:
    definition = {
        "outer_diameter_m": None,
        "wall_thickness_m": None,
        "corrosion_allowance_m": None,
        "radius_m": None,
        "pretension_n": None,
        "height_y_m": None,
        "height_z_m": None,
        "thickness_y_m": None,
        "thickness_z_m": None,
        "profile_name": None,
        "properties": None,
    }
    if isinstance(section, PipeSection):
        definition.update(
            outer_diameter_m=section.OD,
            wall_thickness_m=section.WT,
            corrosion_allowance_m=section.corrosion_allowance,
        )
    elif isinstance(section, BarSection):
        definition.update(
            outer_diameter_m=section.OD,
            wall_thickness_m=section.WT,
        )
    elif isinstance(section, CableSection):
        definition.update(radius_m=section.radius, pretension_n=section.pretension)
    elif isinstance(section, RectangularSection):
        definition.update(
            height_y_m=section.height_y,
            height_z_m=section.height_z,
            thickness_y_m=section.thickness_y,
            thickness_z_m=section.thickness_z,
        )
    elif isinstance(section, IBeamSection):
        definition.update(
            profile_name=section.profile_name,
            properties=_sorted_mapping(section.properties),
        )
    return definition


def _section_area_m2(section: Any) -> float | None:
    if isinstance(section, IBeamSection):
        area = section.properties.get("A")
        return float(area) if area is not None else None
    area = getattr(section, "area", None)
    return float(area) if area is not None else None


def _section_total_length_m(
    model: TubaModel,
    elements: list[Element],
) -> float | None:
    lengths = [_element_length_m(model, element) for element in elements]
    if any(length is None for length in lengths):
        return None
    return sum(length for length in lengths if length is not None)


def _section_total_mass_kg(
    model: TubaModel,
    section: Any,
    elements: list[Element],
) -> float | None:
    """Sum ``area * geometric length * material density`` for section elements."""
    area = _section_area_m2(section)
    if not elements:
        return 0.0
    if area is None:
        return None

    total = 0.0
    for element in elements:
        length = _element_length_m(model, element)
        material = model.materials.get(element.material)
        if length is None or material is None:
            return None
        total += length * area * float(material.rho)
    return total


def _operation_field_dict(field: OperationField) -> dict[str, Any]:
    return {
        "quantity": field.quantity,
        "value": field.value,
        "direction": _optional_list(field.direction),
        "scope": field.scope,
        "profile": field.profile,
        "group": field.group,
        "route_id": field.route_id,
        "station_start": field.station_start,
        "station_end": field.station_end,
        "element_ids": list(field.element_ids),
    }


def _sorted_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value[key] for key in sorted(value)}


def _optional_list(value: list[Any] | None) -> list[Any] | None:
    return None if value is None else list(value)
