"""Verified steady-fluid pressure, wall temperature and filled-contents mapping.

This is a one-way operating-load transfer, not a flow-induced-stress model.
Code_Aster's existing pressure formulation receives the pressure once; this
adapter adds no momentum, bend thrust, wall-friction or equipment forces.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from tuba.model import Operation, TubaModel
from tuba.validation import operation_fields_problem

from .modelica import HydraulicResults
from .network import BoundProcessNetwork

WALL_TEMPERATURE_MODEL = "bulk-fluid-equals-wall-steady"


@dataclass(frozen=True)
class StructuralLoadMapping:
    """The updated structural model, new operation and serializable provenance."""

    model: TubaModel
    operation: Operation
    evidence: dict[str, Any]


def apply_fluid_loads(
    model: TubaModel,
    bound: BoundProcessNetwork,
    hydraulics: HydraulicResults,
    *,
    operation_name: str,
    wall_temperature_model: str,
) -> StructuralLoadMapping:
    """Apply a verified filled-liquid steady case without replacing existing cases.

    The caller must explicitly choose the supported bulk-fluid-equals-wall
    approximation. Pressure is the arithmetic mean of each element's evaluated
    absolute inlet/outlet pressures, less scenario external pressure. It is a
    piecewise-constant differential-pressure idealization, not a resolved wall
    traction or external-pressure/collapse assessment. Subdivide and reevaluate
    the physical route when pressure variation needs finer resolution.

    Temperature is kelvin converted to Celsius, relative to the scenario's
    mechanical reference temperature. Different wall temperatures at a shared
    structural node require a thermal model and are refused. Every structural
    pipe element must occur exactly once; fixed hydraulic losses must remain
    explicitly outside the mechanical study boundary.
    """
    if not isinstance(bound, BoundProcessNetwork) or not isinstance(hydraulics, HydraulicResults):
        raise TypeError("Fluid-load mapping requires a bound process network and verified HydraulicResults.")
    if not isinstance(operation_name, str) or not operation_name.strip():
        raise ValueError("operation_name must be a nonempty name.")
    if operation_name in model.operations or operation_name in model.load_cases:
        raise ValueError(f"Operation/load-case name {operation_name!r} already exists.")
    if wall_temperature_model != WALL_TEMPERATURE_MODEL:
        raise ValueError(f"wall_temperature_model must explicitly be {WALL_TEMPERATURE_MODEL!r}.")
    model.validate()
    bound.verify_for(model)
    hydraulics.verify_for(bound)

    scenario = bound.scenario
    external_pressure = float(scenario.external_pressure_pa)
    reference_k = float(scenario.mechanical_reference_temperature_k)
    if not math.isfinite(external_pressure) or external_pressure < 0:
        raise ValueError("External absolute pressure must be finite and nonnegative.")
    if not math.isfinite(reference_k) or reference_k <= 0:
        raise ValueError("Mechanical reference temperature must be finite positive kelvin.")
    reference_c = reference_k - 273.15
    operation = Operation(
        name=operation_name, gravity=True, internal_pressure=0.0,
        temperature=reference_c, ref_temperature=reference_c,
    )
    result_segments = {segment.segment_id: segment for segment in hydraulics.segments}
    if len(result_segments) != len(hydraulics.segments):
        raise ValueError("Hydraulic results contain duplicate segment identities.")
    if set(result_segments) != {segment.segment_id for segment in bound.segments}:
        raise ValueError("Hydraulic result coverage must include every bound pipe and external loss segment exactly once.")
    pipe_ids = {element.id for element in model.elements if element.type in {"pipe_straight", "pipe_bend"}}
    covered: set[str] = set()
    wall_temperatures: dict[str, float] = {}
    mapped_elements: list[dict[str, Any]] = []
    external_losses: list[dict[str, str]] = []
    for segment in bound.segments:
        fluid = result_segments[segment.segment_id]
        if fluid.element_id != segment.element_id or fluid.component_id != segment.component_id:
            raise ValueError(f"Hydraulic segment {segment.segment_id!r} has mismatched element/component association.")
        values = (fluid.pressure_in_pa, fluid.pressure_out_pa, fluid.mass_flow_kg_s,
                  fluid.temperature_k, fluid.density_kg_m3)
        if not all(math.isfinite(value) for value in values):
            raise ValueError(f"Hydraulic segment {segment.segment_id!r} contains nonfinite operating values.")
        if fluid.mass_flow_kg_s <= 0:
            raise ValueError("Zero or reversed flow is unsupported by the steady fluid-load mapping.")
        if fluid.temperature_k <= 0 or fluid.density_kg_m3 <= 0:
            raise ValueError("Fluid temperature and filled-liquid density must be positive.")
        if min(fluid.pressure_in_pa, fluid.pressure_out_pa) <= 0:
            raise ValueError("Fluid pressures must be positive absolute pressures in Pa.")
        if segment.element_id is None:
            external_losses.append({
                "segment_id": segment.segment_id, "component_id": segment.component_id,
                "mechanical_domain": "external",
                "scope": "hydraulic loss only; equipment mass, stiffness and nozzle loads are outside this structural study",
            })
            continue
        element_id = segment.element_id
        if element_id not in pipe_ids or element_id in covered:
            raise ValueError(f"Structural pipe coverage contains unsupported or duplicate element {element_id!r}.")
        covered.add(element_id)
        p_in = fluid.pressure_in_pa - external_pressure
        p_out = fluid.pressure_out_pa - external_pressure
        if min(p_in, p_out) < 0:
            raise ValueError("Negative differential pressure is unsupported; external-pressure/collapse loading needs qualification.")
        pressure = p_in / 2.0 + p_out / 2.0
        wall_c = fluid.temperature_k - 273.15
        element = model.get_element(element_id)
        for node_id in (element.n1, element.n2):
            if node_id in wall_temperatures and not math.isclose(wall_temperatures[node_id], wall_c, abs_tol=1e-8, rel_tol=0):
                raise ValueError(f"Conflicting bulk-as-wall temperatures at shared node {node_id!r}; provide a thermal model.")
            wall_temperatures[node_id] = wall_c
        bore_area = math.pi / 4.0 * segment.bore_m**2
        contents_mass_per_m = fluid.density_kg_m3 * bore_area
        if not math.isfinite(contents_mass_per_m):
            raise ValueError(f"Element {element_id!r} filled-contents mass must be finite.")
        operation.add_field("pressure", pressure, element_ids=[element_id])
        operation.add_field("fluid_density", fluid.density_kg_m3, element_ids=[element_id])
        mapped_elements.append({
            "segment_id": segment.segment_id, "component_id": segment.component_id,
            "element_id": element_id, "route_id": segment.route_id,
            "pressure_in_absolute_pa": fluid.pressure_in_pa,
            "pressure_out_absolute_pa": fluid.pressure_out_pa,
            "pressure_differential_mean_pa": pressure,
            "wall_temperature_c": wall_c, "fluid_temperature_k": fluid.temperature_k,
            "fluid_density_kg_m3": fluid.density_kg_m3,
            "contents_mass_kg_per_m": contents_mass_per_m,
        })
    if covered != pipe_ids:
        raise ValueError(f"Structural pipe coverage is incomplete; missing {sorted(pipe_ids - covered)!r}.")
    for node_id, wall_c in wall_temperatures.items():
        operation.add_field("temperature", wall_c, node_ids=[node_id])
    problems = operation_fields_problem(operation.fields, model)
    if problems:
        raise ValueError("Fluid-load operation is invalid: " + "; ".join(problems))
    evidence = {
        "schema_version": 1, "scenario_id": scenario.id,
        "bound_fingerprint": bound.fingerprint,
        "geometry_fingerprint": bound.geometry_fingerprint,
        "hydraulic_evidence": hydraulics.to_dict(),
        "wall_temperature_model": wall_temperature_model,
        "mechanical_reference_temperature_k": reference_k,
        "mechanical_reference_temperature_c": reference_c,
        "external_pressure_absolute_pa": external_pressure,
        "pressure_discretization": "per-element arithmetic inlet/outlet mean minus external pressure; piecewise constant",
        "temperature_discretization": "uniform bulk-as-wall per fluid segment at physical end nodes; existing solver-node interpolation",
        "contents_model": "filled bore; evaluated liquid density under structural gravity",
        "elements": mapped_elements, "external_loss_components": external_losses,
        "scope": "one-way steady pressure, wall temperature and filled-contents operating loads",
        "omitted_effects": [
            "flow momentum, wall shear/friction and separate bend/nozzle/equipment forces",
            "equipment mass/stiffness and loss components outside the mechanical study boundary",
            "wall thermal inertia/gradients, transient flow, two-phase or partial-fill contents",
            "external-pressure collapse, flow-induced vibration, comprehensive flow-induced-stress and piping-code qualification",
        ],
        "structural_status": "loads mapped; Code_Aster evaluation required",
    }
    operation.metadata["fluid_load_mapping"] = evidence
    model.operations[operation_name] = operation
    return StructuralLoadMapping(model, operation, evidence)
