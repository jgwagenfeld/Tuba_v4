"""Derived physical properties and quantities for model elements."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from tuba.geometry.profiles import profile_for_section
from tuba.model import Element, TubaModel
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


def physical_properties_for_element(model: TubaModel, element: Element | str | EntityRef) -> ElementPhysicalProperties:
    elem = _resolve_element(model, element)
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
    mass = pipe_mass + insulation_mass

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
    )


def element_quantities(model: TubaModel, element: Element | str | EntityRef) -> ElementQuantities:
    elem = _resolve_element(model, element)
    props = physical_properties_for_element(model, elem)
    length = element_length(model, elem)
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
