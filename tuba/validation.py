"""Validation helpers for Tuba models."""

from __future__ import annotations

from collections import Counter

import numpy as np

from tuba.attributes import coerce_entity_ref
from tuba.model import BarSection, CableSection, IBeamSection, PipeSection, RectangularSection, TubaModel
from tuba.placements import placement_frame_id, resolve_placement_frame
from tuba.refs import resolve_entity_ref


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
