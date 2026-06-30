"""Validation helpers for Tuba models."""

from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np

from tuba.attributes import coerce_entity_ref
from tuba.model import BarSection, CableSection, IBeamSection, PipeSection, RectangularSection, TubaModel
from tuba.placements import placement_frame_id, resolve_placement_frame
from tuba.refs import resolve_entity_ref


_PIPE_TO_PORT_OPTIONS = {"3D_TUYAU", "3D_POU", "COQ_TUYAU", "COQ_POU"}


class ModelValidationError(ValueError):
    """Raised when a model violates structural invariants."""


def validate_model(model: TubaModel) -> None:
    errors: list[str] = []

    for node_id, node in model.nodes.items():
        coords = np.asarray(node.coords, dtype=float)
        if coords.shape != (3,) or not np.all(np.isfinite(coords)):
            errors.append(f"Node {node_id!r} has invalid coordinates.")

    element_ids = [elem.id for elem in model.elements]
    for elem_id, count in Counter(element_ids).items():
        if count > 1:
            errors.append(f"Duplicate element id {elem_id!r}.")

    for elem in model.elements:
        if elem.n1 not in model.nodes:
            errors.append(f"Element {elem.id!r} references missing node {elem.n1!r}.")
        if elem.n2 not in model.nodes:
            errors.append(f"Element {elem.id!r} references missing node {elem.n2!r}.")
        if elem.section not in model.sections:
            errors.append(f"Element {elem.id!r} references missing section {elem.section!r}.")
        if elem.material not in model.materials:
            errors.append(f"Element {elem.id!r} references missing material {elem.material!r}.")
        if elem.n1 == elem.n2:
            errors.append(f"Element {elem.id!r} has identical start and end nodes.")

    for support in model.supports:
        if support.node not in model.nodes:
            errors.append(f"Support references missing node {support.node!r}.")

    for name, section in model.sections.items():
        _validate_section(name, section, errors)

    for group_name, group in getattr(model, "groups", {}).items():
        for node_id in group.get("nodes", []):
            if node_id not in model.nodes:
                errors.append(f"Group {group_name!r} references missing node {node_id!r}.")
        for element_id in group.get("elements", []):
            if element_id not in element_ids:
                errors.append(f"Group {group_name!r} references missing element {element_id!r}.")

    _validate_placement_frames(model, errors)
    _validate_placement_assignments(model, errors)

    for assignment in getattr(model, "attributes", []):
        try:
            resolve_entity_ref(model, assignment.target)
        except KeyError:
            errors.append(
                f"Attribute {assignment.key!r} references missing "
                f"{assignment.target.kind} {assignment.target.id!r}."
            )
        if assignment.key == "insulation" and assignment.value not in model.specs.get("insulation", {}):
            errors.append(f"Attribute 'insulation' references missing spec {assignment.value!r}.")

    _validate_mixed_records(model, errors)

    if errors:
        raise ModelValidationError("\n".join(errors))


def _validate_placement_frames(model: TubaModel, errors: list[str]) -> None:
    frames = getattr(model, "placement_frames", {})
    for frame_id, frame in frames.items():
        if frame_id != frame.id:
            errors.append(f"Placement frame key {frame_id!r} does not match id {frame.id!r}.")
        try:
            frame.to_coordinate_system()
        except Exception as exc:  # noqa: BLE001 - collect all validation errors
            errors.append(f"Placement frame {frame_id!r} is invalid: {exc}")
        parent_id = placement_frame_id(frame.parent)
        if parent_id is not None and parent_id not in frames:
            errors.append(f"Placement frame {frame_id!r} references missing parent {parent_id!r}.")

    for frame_id in frames:
        try:
            resolve_placement_frame(frame_id, frames)
        except Exception as exc:  # noqa: BLE001 - collect all validation errors
            errors.append(f"Placement frame cycle or resolution error at {frame_id!r}: {exc}")


def _validate_placement_assignments(model: TubaModel, errors: list[str]) -> None:
    frames = getattr(model, "placement_frames", {})
    seen: set[tuple[str, str | None]] = set()
    for assignment in getattr(model, "placement_assignments", []):
        frame_id = placement_frame_id(assignment.frame)
        if frame_id not in frames:
            errors.append(f"Placement assignment references missing frame {assignment.frame!r}.")
        try:
            resolve_entity_ref(model, coerce_entity_ref(assignment.target))
        except Exception:  # noqa: BLE001 - collect all validation errors
            errors.append(f"Placement assignment references missing target {assignment.target!r}.")
        if assignment.role == "object_placement":
            key = (assignment.target, assignment.source)
            if key in seen:
                errors.append(f"Duplicate object placement assignment for {assignment.target!r}.")
            seen.add(key)


def _validate_section(name: str, section, errors: list[str]) -> None:
    if isinstance(section, PipeSection):
        if section.OD <= 0.0:
            errors.append(f"Pipe section {name!r} OD must be positive.")
        if section.WT <= 0.0:
            errors.append(f"Pipe section {name!r} WT must be positive.")
        if section.WT * 2.0 >= section.OD:
            errors.append(f"Pipe section {name!r} WT is too large for OD.")
    elif isinstance(section, BarSection):
        if section.OD <= 0.0:
            errors.append(f"Bar section {name!r} OD must be positive.")
    elif isinstance(section, CableSection):
        if section.radius <= 0.0:
            errors.append(f"Cable section {name!r} radius must be positive.")
    elif isinstance(section, RectangularSection):
        if section.height_y <= 0.0 or section.height_z <= 0.0:
            errors.append(f"Rectangular section {name!r} dimensions must be positive.")
    elif isinstance(section, IBeamSection):
        if not section.profile_name:
            errors.append(f"I-beam section {name!r} profile_name must not be empty.")
    else:
        errors.append(f"Section {name!r} has unsupported type {type(section).__name__}.")


def _validate_mixed_records(model: TubaModel, errors: list[str]) -> None:
    _validate_record_keys_and_ids("cad_assets", model.cad_assets, errors)
    _validate_record_keys_and_ids("imported_components", model.imported_components, errors)
    _validate_record_keys_and_ids("analysis_regions", model.analysis_regions, errors)
    _validate_record_keys_and_ids("ports", model.ports, errors)
    _validate_record_keys_and_ids("mesh_groups", model.mesh_groups, errors)
    _validate_record_keys_and_ids("couplings", model.couplings, errors)

    _validate_imported_components(model, errors)
    _validate_analysis_regions(model, errors)
    _validate_ports(model, errors)
    _validate_mesh_groups(model, errors)
    _validate_couplings(model, errors)


def _validate_record_keys_and_ids(record_name: str, records: dict[str, Any], errors: list[str]) -> None:
    for key, record in records.items():
        if key != getattr(record, "id", None):
            errors.append(
                f"{record_name} key {key!r} does not match record id {getattr(record, 'id', None)!r}."
            )


def _validate_imported_components(model: TubaModel, errors: list[str]) -> None:
    for component_id, component in model.imported_components.items():
        if component.asset.kind != "cad_asset":
            errors.append(
                f"Imported component {component_id!r} references non-cad asset {component.asset!r}."
            )
        try:
            resolve_entity_ref(model, component.asset)
        except KeyError:
            errors.append(
                f"Imported component {component_id!r} references missing cad asset {component.asset!r}."
            )


def _validate_analysis_regions(model: TubaModel, errors: list[str]) -> None:
    for region_id, region in model.analysis_regions.items():
        if region.owner.kind != "component":
            errors.append(
                f"Analysis region {region_id!r} owner must be a component, got {region.owner.kind!r}."
            )
        elif region.owner.id not in model.imported_components:
            errors.append(
                f"Analysis region {region_id!r} references missing owner {region.owner!r}."
            )

        if region.material not in model.materials:
            errors.append(
                f"Analysis region {region_id!r} references missing material {region.material!r}."
            )

        if region.role == "solid_3d" and region.code_aster_modelisation != "3D":
            errors.append(
                f"Analysis region {region_id!r} is solid_3d but has modelisation "
                f"{region.code_aster_modelisation!r}."
            )


def _validate_ports(model: TubaModel, errors: list[str]) -> None:
    for port_id, port in model.ports.items():
        if port.owner.kind != "component":
            errors.append(f"Port {port_id!r} owner must be a component, got {port.owner.kind!r}.")
        elif port.owner.id not in model.imported_components:
            errors.append(f"Port {port_id!r} references missing owner {port.owner!r}.")

        if port.status == "confirmed" and not port.face_group:
            errors.append(f"Port {port_id!r} is confirmed but missing face_group.")


def _validate_mesh_groups(model: TubaModel, errors: list[str]) -> None:
    for group_id, mesh_group in model.mesh_groups.items():
        try:
            resolve_entity_ref(model, mesh_group.owner)
        except KeyError:
            errors.append(
                f"Mesh group {group_id!r} references missing owner {mesh_group.owner!r}."
            )


def _validate_couplings(model: TubaModel, errors: list[str]) -> None:
    element_ids = {element.id for element in model.elements}
    for coupling_id, coupling in model.couplings.items():
        if coupling.kind == "pipe_to_solid_port":
            if coupling.code_aster_keyword != "LIAISON_ELEM":
                errors.append(
                    f"Coupling {coupling_id!r} pipe_to_solid_port must use Code_Aster keyword "
                    "'LIAISON_ELEM'."
                )
            if coupling.code_aster_option not in _PIPE_TO_PORT_OPTIONS:
                errors.append(
                    f"Coupling {coupling_id!r} has unsupported pipe-to-port option "
                    f"{coupling.code_aster_option!r}."
                )

        if coupling.source.kind != "element":
            errors.append(
                f"Coupling {coupling_id!r} source must be an element, got {coupling.source.kind!r}."
            )
        elif coupling.source.id not in element_ids:
            errors.append(
                f"Coupling {coupling_id!r} references missing source element {coupling.source.id!r}."
            )

        if coupling.source_node.kind != "node":
            errors.append(
                f"Coupling {coupling_id!r} source node must be a node, got {coupling.source_node.kind!r}."
            )
        elif coupling.source_node.id not in model.nodes:
            errors.append(
                f"Coupling {coupling_id!r} references missing source node {coupling.source_node.id!r}."
            )

        if coupling.target.kind != "port":
            errors.append(f"Coupling {coupling_id!r} target must be a port, got {coupling.target.kind!r}.")
        else:
            try:
                port = resolve_entity_ref(model, coupling.target)
            except KeyError:
                errors.append(
                    f"Coupling {coupling_id!r} references missing target port {coupling.target.id!r}."
                )
            else:
                if port.status != "confirmed":
                    errors.append(
                        f"Coupling {coupling_id!r} target port {coupling.target.id!r} is not confirmed."
                    )

        if (
            coupling.kind == "pipe_to_solid_port"
            and coupling.code_aster_keyword == "LIAISON_ELEM"
            and coupling.code_aster_option == "3D_TUYAU"
        ):
            _validate_pipe_to_solid_port(model, coupling_id, coupling, errors)


def _validate_pipe_to_solid_port(
    model: TubaModel,
    coupling_id: str,
    coupling: Any,
    errors: list[str],
) -> None:
    if (
        coupling.source.kind != "element"
        or coupling.source_node.kind != "node"
        or coupling.target.kind != "port"
    ):
        return

    try:
        source = resolve_entity_ref(model, coupling.source)
    except KeyError:
        return
    source_node_id = coupling.source_node.id
    if source.type not in {"pipe_straight", "pipe_bend"}:
        errors.append(
            f"Coupling {coupling_id!r} source element {source.id!r} must be pipe_straight or pipe_bend "
            f"for 3D_TUYAU."
        )

    if source_node_id not in {source.n1, source.n2}:
        errors.append(
            f"Coupling {coupling_id!r} source node {source_node_id!r} must be endpoint of element {source.id!r}."
        )

    try:
        port = resolve_entity_ref(model, coupling.target)
    except KeyError:
        return

    has_solid_region = any(
        region.owner == port.owner and region.role == "solid_3d"
        for region in model.analysis_regions.values()
    )
    if not has_solid_region:
        errors.append(
            f"Coupling {coupling_id!r} target port {coupling.target.id!r} has no solid_3d analysis region owner."
        )

    section = model.sections.get(source.section)
    if section is None:
        return
    if not hasattr(section, "OD"):
        errors.append(
            f"Coupling {coupling_id!r} source section {source.section!r} has no OD for diameter comparison."
        )
        return

    pipe_radius = float(section.OD) / 2.0
    tolerance = max(0.001, pipe_radius * 0.02)
    if abs(pipe_radius - port.radius) > tolerance:
        errors.append(
            f"Coupling {coupling_id!r} pipe/port diameter mismatch for "
            f"{source.id!r} and {port.id!r}."
        )
