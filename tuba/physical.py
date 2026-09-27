"""Derived physical properties and quantities for model elements."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from tuba.geometry.profiles import profile_for_section
from tuba.model import Element, LoadCase, PipeSection, TubaModel
from tuba.refs import EntityRef


@dataclass(frozen=True)
class ElementPhysicalProperties:
    element_id: str
    section: str
    material: str
    bare_od_m: float
    bare_radius_m: float
    effective_radius_m: float
    effective_od_m: float
    metal_area_m2: float
    pipe_mass_kg_per_m: float
    insulation_spec_id: str | None
    insulation_thickness_m: float
    insulation_volume_m3_per_m: float
    insulation_mass_kg_per_m: float
    insulation_cost_per_m: float
    mass_kg_per_m: float
    wind_diameter_m: float
    surface_area_m2_per_m: float
    fluid_density_kg_m3: float = 0.0
    bore_area_m2: float = 0.0
    fluid_mass_kg_per_m: float = 0.0


@dataclass(frozen=True)
class ElementQuantities:
    element_id: str
    length_m: float
    mass_kg_per_m: float
    total_mass_kg: float
    pipe_mass_kg: float
    insulation_mass_kg: float
    insulation_volume_m3_per_m: float
    insulation_volume_m3: float
    insulation_cost: float
    surface_area_m2: float
    wind_projected_area_m2: float
    fluid_mass_kg: float = 0.0


def _fluid_density_by_element(model: TubaModel, case: LoadCase | None) -> dict[str, float]:
    """Resolve a case once, applying equal overlapping contents assignments once."""
    if case is None:
        return {}
    from tuba.validation import operation_fields_problem

    problems = operation_fields_problem(case.fields, model)
    if problems:
        raise ValueError(f"Operation {case.name!r}: " + "; ".join(problems))
    return {elem.id: float(field.value)
            for field in case.fields if field.quantity == "fluid_density"
            for elem in model.resolve_operation_field_elements(field)}


def physical_properties_for_element(
    model: TubaModel, element: Element | str | EntityRef, *, operation: str | None = None,
) -> ElementPhysicalProperties:
    """Physical inputs for a named case, or dry metal and insulation by default."""
    elem = _resolve_element(model, element)
    case = model.resolve_load_case(operation)[1] if operation is not None else None
    densities = _fluid_density_by_element(model, case)
    return _physical_properties_for_element(model, elem, densities.get(elem.id, 0.0))


def _physical_properties_for_element(
    model: TubaModel, elem: Element, fluid_density: float,
) -> ElementPhysicalProperties:
    section = model.sections[elem.section]
    material = model.materials[elem.material]
    profile = profile_for_section(section)
    bare_radius = profile.collision_radius_m
    bare_od = bare_radius * 2.0
    metal_area = profile.area_m2
    pipe_mass = metal_area * float(getattr(material, "rho", 0.0))

    insulation = model.get_insulation(EntityRef("element", elem.id))
    if insulation is None:
        insulation_spec_id = None
        insulation_thickness = 0.0
        insulation_density = 0.0
        insulation_cost = 0.0
    else:
        insulation_spec_id = insulation.id
        insulation_thickness = insulation.thickness_m
        insulation_density = insulation.density_kg_m3
        insulation_cost = insulation.cost_per_m

    effective_radius = bare_radius + insulation_thickness
    effective_od = effective_radius * 2.0
    insulation_volume = math.pi * max(effective_radius**2 - bare_radius**2, 0.0)
    insulation_mass = insulation_volume * insulation_density
    bore_area = 0.0
    if elem.type in {"pipe_straight", "pipe_bend"} and isinstance(section, PipeSection):
        try:
            bore_area = math.pi * (section.OD - 2 * section.WT)**2 / 4
        except OverflowError as exc:
            raise ValueError(f"Element {elem.id!r} fluid_density bore area must be finite.") from exc
    fluid_mass = fluid_density * bore_area
    mass = pipe_mass + insulation_mass + fluid_mass
    if not all(math.isfinite(value) for value in (bore_area, fluid_mass, mass)):
        raise ValueError(f"Element {elem.id!r} fluid_density derived mass must be finite.")

    return ElementPhysicalProperties(
        element_id=elem.id,
        section=elem.section,
        material=elem.material,
        bare_od_m=bare_od,
        bare_radius_m=bare_radius,
        effective_radius_m=effective_radius,
        effective_od_m=effective_od,
        metal_area_m2=metal_area,
        pipe_mass_kg_per_m=pipe_mass,
        insulation_spec_id=insulation_spec_id,
        insulation_thickness_m=insulation_thickness,
        insulation_volume_m3_per_m=insulation_volume,
        insulation_mass_kg_per_m=insulation_mass,
        insulation_cost_per_m=insulation_cost,
        mass_kg_per_m=mass,
        wind_diameter_m=effective_od,
        surface_area_m2_per_m=math.pi * effective_od,
        fluid_density_kg_m3=fluid_density,
        bore_area_m2=bore_area,
        fluid_mass_kg_per_m=fluid_mass,
    )


def element_quantities(
    model: TubaModel, element: Element | str | EntityRef, *, operation: str | None = None,
) -> ElementQuantities:
    elem = _resolve_element(model, element)
    props = physical_properties_for_element(model, elem, operation=operation)
    return _element_quantities(model, elem, props)


def _element_quantities(model: TubaModel, elem: Element, props: ElementPhysicalProperties) -> ElementQuantities:
    length = element_length(model, elem)
    if not math.isfinite(props.mass_kg_per_m * length):
        raise ValueError(f"Element {elem.id!r} fluid_density derived total mass must be finite.")
    return ElementQuantities(
        element_id=elem.id,
        length_m=length,
        mass_kg_per_m=props.mass_kg_per_m,
        total_mass_kg=props.mass_kg_per_m * length,
        pipe_mass_kg=props.pipe_mass_kg_per_m * length,
        insulation_mass_kg=props.insulation_mass_kg_per_m * length,
        insulation_volume_m3_per_m=props.insulation_volume_m3_per_m,
        insulation_volume_m3=props.insulation_volume_m3_per_m * length,
        insulation_cost=props.insulation_cost_per_m * length,
        surface_area_m2=props.surface_area_m2_per_m * length,
        wind_projected_area_m2=props.wind_diameter_m * length,
        fluid_mass_kg=props.fluid_mass_kg_per_m * length,
    )


def element_length(model: TubaModel, element: Element | str | EntityRef) -> float:
    elem = _resolve_element(model, element)
    if elem.type == "pipe_bend" and elem.bend_radius is not None and elem.bend_angle is not None:
        return abs(float(elem.bend_radius) * math.radians(float(elem.bend_angle)))
    p1 = model.nodes[elem.n1].coords
    p2 = model.nodes[elem.n2].coords
    return float(np.linalg.norm(p2 - p1))


def _resolve_element(model: TubaModel, element: Element | str | EntityRef) -> Element:
    if isinstance(element, Element):
        return element
    if isinstance(element, EntityRef):
        if element.kind != "element":
            raise ValueError(f"Expected element ref, got {element.kind!r}.")
        element_id = element.id
    elif isinstance(element, str):
        element_id = element.split(":", 1)[1] if element.startswith("element:") else element
    else:
        raise TypeError(f"Cannot resolve element from {type(element).__name__}.")

    for elem in model.elements:
        if elem.id == element_id:
            return elem
    raise KeyError(f"Unknown element {element_id!r}.")
