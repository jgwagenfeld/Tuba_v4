"""Static load balance: calculated inputs against imported Code_Aster reactions."""

from __future__ import annotations

import math

import numpy as np

from tuba.physical import _fluid_density_by_element, _physical_properties_for_element
from tuba.reporting.model import ReportColumn, ReportTable
from tuba.solver.aster_loads import resolve_line_load_groups


def build_equilibrium_table(model, studies_by_id, result_states, analysis_meshes=()):
    """Six global components about (0, 0, 0), only when the full load basis is known.

    The applied column is calculated input, not solver output. Thermal eigenstrain
    has no external resultant in these small-displacement 1D studies. Pressure,
    wind, contact, spring, cable and volume studies need additional load/reaction
    recovery; their balance is explicitly unavailable rather than partial.
    """
    meshes = {mesh.id: mesh for mesh in analysis_meshes}
    rows = []
    for state in result_states:
        study = studies_by_id[state.study_id]
        identity = dict(solver_name=state.solver_name, study_id=study.id,
                        result_state_id=state.id, load_case=state.load_case)
        try:
            applied, reactions = _resultants(model, study, state, meshes.get(state.mesh_id))
        except (ValueError, KeyError) as exc:
            rows.append({**identity, "status": "not_evaluated", "note": str(exc)})
            continue
        for index, (component, unit) in enumerate(zip(
            ("FX", "FY", "FZ", "MX", "MY", "MZ"), ("N", "N", "N", "N*m", "N*m", "N*m")
        )):
            load = math.fsum(vector[index] for vector in applied)
            reaction = math.fsum(vector[index] for vector in reactions)
            scale = max(math.fsum(abs(vector[index]) for vector in applied),
                        math.fsum(abs(vector[index]) for vector in reactions))
            tolerance = 1e-3 + 1e-5 * scale
            residual = load + reaction
            rows.append({**identity, "component": component, "applied": load,
                         "reaction": reaction, "residual": residual, "tolerance": tolerance,
                         "unit": unit, "status": "within_tolerance" if abs(residual) <= tolerance
                         else "outside_tolerance", "note": "Global axes; moments about (0, 0, 0) m. "
                         "Applied = calculated inputs; reaction = Code_Aster REAC_NODA. "
                         "Residual = applied + reaction; tolerance = 0.001 + 1e-5 * component scale."})
    return ReportTable(
        id="equilibrium", title="Equilibrium checks", source="result_state",
        columns=tuple(ReportColumn(key, label) for key, label in (
            ("solver_name", "Solver"), ("study_id", "Study ID"),
            ("result_state_id", "Result state ID"), ("load_case", "Load case"),
            ("component", "Component"), ("applied", "Calculated applied load"),
            ("reaction", "Solver reaction"), ("residual", "Residual"),
            ("tolerance", "Numerical tolerance"), ("unit", "Unit"),
            ("status", "Balance status"), ("note", "Basis / unavailable reason"))),
        rows=tuple(rows),
    )


def _resultants(model, study, state, mesh):
    inputs = study.metadata.get("compiler_inputs") or {}
    if study.metadata.get("volume_analysis") or study.metadata.get("mixed_analysis"):
        raise ValueError("Volume/mixed studies require a solver-assembled applied-load resultant.")
    if inputs.get("load_path") or state.contact_results or any(e.type == "cable" for e in model.elements):
        raise ValueError("Contact/load-path/cable studies require complete external reactions and deformed load positions.")
    if any(s.attached_to or s.type in {"rest", "spring", "hanger"}
           or any(s.restraint().spring_stiffness) for s in model.supports):
        raise ValueError("Attached/contact/spring supports require external ground reactions; nodal reactions alone are incomplete.")
    _, case = model.resolve_load_case(state.load_case)
    if case.internal_pressure or any(f.quantity == "pressure" and f.value for f in case.fields):
        raise ValueError("Pressure studies require the solver-assembled pressure-load resultant.")
    if any(f.quantity == "wind" for f in case.fields):
        raise ValueError("Wind studies require the solver's orientation-dependent wind-load resultant.")
    if any(f.quantity not in {"pressure", "temperature", "fluid_density", "line_load"} for f in case.fields):
        raise ValueError("This operation contains a load field without a complete resultant recovery.")
    support_nodes = {s.node for s in model.supports}
    missing = sorted(support_nodes - set(state.node_reactions))
    if missing or not support_nodes:
        raise ValueError(f"Complete support reactions are required; missing nodes: {missing or 'all' }.")
    reactions = []
    for node in sorted(support_nodes):
        values = state.node_reactions[node]
        if any(value is None for value in values):
            raise ValueError(f"Support node {node!r} has unavailable reaction components.")
        reactions.append(_about_origin(model.nodes[node].coords, values))
    applied = [_about_origin(model.nodes[force.node].coords, force.components) for force in case.nodal_forces]
    line_loads = {}
    for ids, fx, fy, fz in resolve_line_load_groups(model, case):
        for element_id in ids:
            line_loads[element_id] = np.array([fx, fy, fz])
    densities = _fluid_density_by_element(model, case)
    for element in model.elements:
        per_metre = line_loads.get(element.id, np.zeros(3)).copy()
        if case.gravity:
            props = _physical_properties_for_element(model, element, densities.get(element.id, 0.0))
            per_metre[2] -= 9.81 * props.mass_kg_per_m
        if np.any(per_metre):
            for weight, point in _line_quadrature(model, element, mesh, inputs):
                applied.append(_about_origin(point, [*(per_metre * weight), 0, 0, 0]))
    if case.gravity:
        for support in model.supports:
            if support.mass:
                applied.append(_about_origin(model.nodes[support.node].coords,
                                             [0, 0, -9.81 * support.mass, 0, 0, 0]))
    return applied, reactions


def _about_origin(point, values):
    force = np.asarray(values[:3], dtype=float)
    moment = np.asarray(values[3:], dtype=float) + np.cross(point, force)
    vector = np.concatenate((force, moment))
    if not np.isfinite(vector).all():
        raise ValueError("Load/reaction components and positions must be finite.")
    return vector


def _line_quadrature(model, element, mesh, inputs):
    """Integrate the exported SEG2/SEG3 geometry, including curved TUYAU midsides."""
    if mesh is None:
        if element.type == "pipe_bend":
            raise ValueError("Bend gravity/line loads require the authoritative analysis mesh.")
        a, b = (model.nodes[node].coords for node in (element.n1, element.n2))
        return [(float(np.linalg.norm(b - a)), (a + b) / 2)]
    # ponytail: per-element mesh scans; index by source if large meshes make reports slow.
    segments = [(key, nodes) for key, nodes in mesh.elements.items()
                if key in mesh.element_sources
                and mesh.element_sources[key].source_ref.kind == "element"
                and mesh.element_sources[key].source_ref.id == element.id]
    if not segments:
        raise ValueError(f"Analysis mesh has no load geometry for element {element.id!r}.")
    midsides = {source.segment_index or 0: np.asarray(mesh.nodes[node])
                for node, source in mesh.node_sources.items()
                if source.source_ref.kind == "element" and source.source_ref.id == element.id
                and source.role in {"generated_bend_mid_node", "generated_pipe_mid_node"}}
    quadratic = element.type.startswith("pipe_") and inputs.get("pipe_modelization", "TUYAU_3M") == "TUYAU_3M"
    samples = []
    for key, nodes in segments:
        a, b = (np.asarray(mesh.nodes[node]) for node in nodes[:2])
        if not quadratic:
            samples.append((float(np.linalg.norm(b - a)), (a + b) / 2))
            continue
        index = mesh.element_sources[key].segment_index or 0
        if index not in midsides:
            raise ValueError(f"Analysis mesh is missing a TUYAU midside for element {element.id!r}.")
        middle = midsides[index]
        for t, weight in zip(*np.polynomial.legendre.leggauss(5)):
            point = t * (t - 1) / 2 * a + t * (t + 1) / 2 * b + (1 - t*t) * middle
            tangent = (t - 0.5) * a + (t + 0.5) * b - 2*t * middle
            samples.append((float(weight * np.linalg.norm(tangent)), point))
    return samples
