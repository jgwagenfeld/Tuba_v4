"""Pure report-table builders for authoritative :class:`TubaModel` inputs."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

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
from tuba.reporting.model import ReportColumn, ReportTable


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
