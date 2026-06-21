"""Transactional model patches."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Sequence

import numpy as np

from tuba.attributes import coerce_entity_ref
from tuba.model import TubaModel
from tuba.validation import validate_model


@dataclass(frozen=True)
class AddNode:
    local_id: str
    coords: Sequence[float]
    reuse_existing: bool = True
    tolerance: float = 1e-6


@dataclass(frozen=True)
class AddElement:
    local_id: str
    type: str
    n1: str
    n2: str
    section: str
    material: str
    bend_radius: float | None = None
    bend_angle: float | None = None
    twist_angle: float = 0.0
    id_prefix: str | None = None


@dataclass(frozen=True)
class AddSupport:
    node: str
    type: str
    direction: list[float] | None = None
    stiffness: float | None = None
    imposed_displacement: list[float] | None = None
    stiffness_matrix: list[float] | None = None
    blocked_dof: list[Any] | None = None
    mass: float = 0.0
    friction_coefficient: float = 0.0


@dataclass(frozen=True)
class AddInsulationSpec:
    id: str
    material: str
    thickness_m: float
    density_kg_m3: float = 0.0
    cost_per_m: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CreateGroup:
    name: str
    nodes: list[str] = field(default_factory=list)
    elements: list[str] = field(default_factory=list)
    supports: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AssignAttribute:
    target: str | dict[str, str]
    key: str
    value: Any
    source: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


PatchOperation = AddNode | AddElement | AddSupport | AddInsulationSpec | CreateGroup | AssignAttribute
KNOWN_ELEMENT_TYPES = {"pipe_straight", "pipe_bend", "beam", "bar", "cable"}


@dataclass(frozen=True)
class ModelPatch:
    operations: list[PatchOperation] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the patch into an agent/GUI-friendly payload."""
        return {
            "operations": [_operation_to_dict(operation) for operation in self.operations],
            "provenance": _json_ready(self.provenance),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModelPatch":
        """Reconstruct a patch from an agent/GUI payload."""
        from tuba.schema import validate_patch_dict

        validate_patch_dict(data)
        operations = []
        for item in data.get("operations", []):
            operation_type = item["op"]
            payload = {key: value for key, value in item.items() if key != "op"}
            if operation_type == "add_node":
                operations.append(AddNode(**payload))
            elif operation_type == "add_element":
                operations.append(AddElement(**payload))
            elif operation_type == "add_support":
                operations.append(AddSupport(**payload))
            elif operation_type == "add_insulation_spec":
                operations.append(AddInsulationSpec(**payload))
            elif operation_type == "create_group":
                operations.append(CreateGroup(**payload))
            elif operation_type == "assign_attribute":
                operations.append(AssignAttribute(**payload))
            else:
                raise ValueError(f"Unsupported patch operation {operation_type!r}.")
        return cls(operations=operations, provenance=data.get("provenance", {}))


@dataclass
class PatchResult:
    node_ids: dict[str, str] = field(default_factory=dict)
    element_ids: dict[str, str] = field(default_factory=dict)
    support_count: int = 0
    spec_count: int = 0
    attribute_count: int = 0
    group_names: list[str] = field(default_factory=list)


class ModelTransaction:
    """Apply patches atomically to a TubaModel."""

    def __init__(self, model: TubaModel):
        self.model = model

    def apply(self, patch: ModelPatch, *, validate: bool = True) -> PatchResult:
        snapshot = self.model.to_dict()
        result = PatchResult()
        try:
            for operation in patch.operations:
                if isinstance(operation, AddNode):
                    node_id = self._apply_add_node(operation)
                    result.node_ids[operation.local_id] = node_id
                elif isinstance(operation, AddElement):
                    elem_id = self._apply_add_element(operation, result.node_ids)
                    result.element_ids[operation.local_id] = elem_id
                elif isinstance(operation, AddSupport):
                    self._apply_add_support(operation, result.node_ids)
                    result.support_count += 1
                elif isinstance(operation, AddInsulationSpec):
                    self._apply_add_insulation_spec(operation)
                    result.spec_count += 1
                elif isinstance(operation, CreateGroup):
                    self._apply_create_group(operation, result)
                    result.group_names.append(operation.name)
                elif isinstance(operation, AssignAttribute):
                    self._apply_assign_attribute(operation, result)
                    result.attribute_count += 1
                else:
                    raise TypeError(f"Unsupported patch operation {type(operation).__name__}.")
            if validate:
                validate_model(self.model)
            return result
        except Exception:
            restored = TubaModel.from_dict(snapshot)
            self.model.__dict__.clear()
            self.model.__dict__.update(restored.__dict__)
            raise

    def _apply_add_node(self, operation: AddNode) -> str:
        if operation.reuse_existing:
            existing = _node_for_point(self.model, operation.coords, operation.tolerance)
            if existing is not None:
                return existing
        return self.model.add_node(operation.coords)

    def _apply_add_element(self, operation: AddElement, node_ids: dict[str, str]) -> str:
        n1 = node_ids.get(operation.n1, operation.n1)
        n2 = node_ids.get(operation.n2, operation.n2)
        prefix = operation.id_prefix or _prefix_for_element_type(operation.type)
        elem_id = self.model.next_element_id(prefix)
        self.model.add_element(
            id=elem_id,
            type=operation.type,
            n1=n1,
            n2=n2,
            section=operation.section,
            material=operation.material,
            bend_radius=operation.bend_radius,
            bend_angle=operation.bend_angle,
            twist_angle=operation.twist_angle,
        )
        return elem_id

    def _apply_add_support(self, operation: AddSupport, node_ids: dict[str, str]) -> None:
        node = node_ids.get(operation.node, operation.node)
        self.model.add_support(
            node=node,
            type=operation.type,
            direction=operation.direction,
            stiffness=operation.stiffness,
            imposed_displacement=operation.imposed_displacement,
            stiffness_matrix=operation.stiffness_matrix,
            blocked_dof=operation.blocked_dof,
            mass=operation.mass,
            friction_coefficient=operation.friction_coefficient,
        )

    def _apply_add_insulation_spec(self, operation: AddInsulationSpec) -> None:
        self.model.add_insulation_spec(
            id=operation.id,
            material=operation.material,
            thickness_m=operation.thickness_m,
            density_kg_m3=operation.density_kg_m3,
            cost_per_m=operation.cost_per_m,
            metadata=operation.metadata,
        )

    def _apply_create_group(self, operation: CreateGroup, result: PatchResult) -> None:
        if operation.name in self.model.groups:
            raise ValueError(f"Group {operation.name!r} already exists.")
        self.model.groups[operation.name] = {
            "name": operation.name,
            "nodes": [_resolve_node_id(node, result.node_ids) for node in operation.nodes],
            "elements": [_resolve_element_id(element, result.element_ids) for element in operation.elements],
            "supports": list(operation.supports),
            "metadata": _resolve_metadata_refs(operation.metadata, result),
        }

    def _apply_assign_attribute(self, operation: AssignAttribute, result: PatchResult) -> None:
        target = _resolve_target_ref(operation.target, result)
        if operation.key == "insulation":
            self.model.assign_insulation(
                target,
                operation.value,
                source=operation.source,
                metadata=operation.metadata,
            )
            return
        self.model.assign_attribute(
            target,
            operation.key,
            operation.value,
            source=operation.source,
            metadata=operation.metadata,
        )


def _prefix_for_element_type(element_type: str) -> str:
    if element_type == "pipe_straight":
        return "pipe_str"
    if element_type == "pipe_bend":
        return "pipe_bend"
    if element_type == "beam":
        return "beam"
    if element_type == "bar":
        return "bar"
    if element_type == "cable":
        return "cable"
    raise ValueError(f"Unknown element type {element_type!r}.")


def _node_for_point(model: TubaModel, coords: Sequence[float], tol: float) -> str | None:
    if hasattr(model, "find_node_by_point"):
        return model.find_node_by_point(coords, tol=tol)
    target = np.asarray(coords, dtype=float)
    for node_id, node in model.nodes.items():
        if np.allclose(node.coords, target, atol=tol):
            return node_id
    return None


def _operation_to_dict(operation: PatchOperation) -> dict[str, Any]:
    if isinstance(operation, AddNode):
        operation_type = "add_node"
    elif isinstance(operation, AddElement):
        operation_type = "add_element"
    elif isinstance(operation, AddSupport):
        operation_type = "add_support"
    elif isinstance(operation, AddInsulationSpec):
        operation_type = "add_insulation_spec"
    elif isinstance(operation, CreateGroup):
        operation_type = "create_group"
    elif isinstance(operation, AssignAttribute):
        operation_type = "assign_attribute"
    else:
        raise TypeError(f"Unsupported patch operation {type(operation).__name__}.")

    data = {"op": operation_type}
    for key, value in asdict(operation).items():
        if value is not None:
            data[key] = _json_ready(value)
    return data


def _resolve_target_ref(target: str | dict[str, str], result: PatchResult) -> str:
    ref = coerce_entity_ref(target)
    if ref.kind == "node":
        return f"node:{_resolve_node_id(ref.id, result.node_ids)}"
    if ref.kind == "element":
        return f"element:{_resolve_element_id(ref.id, result.element_ids)}"
    return str(ref)


def _resolve_node_id(node_id: str, node_ids: dict[str, str]) -> str:
    return node_ids.get(node_id, node_id)


def _resolve_element_id(element_id: str, element_ids: dict[str, str]) -> str:
    return element_ids.get(element_id, element_id)


def _resolve_metadata_refs(value: Any, result: PatchResult) -> Any:
    if isinstance(value, str):
        if value.startswith("node:"):
            return f"node:{_resolve_node_id(value.split(':', 1)[1], result.node_ids)}"
        if value.startswith("element:"):
            return f"element:{_resolve_element_id(value.split(':', 1)[1], result.element_ids)}"
        return value
    if isinstance(value, list):
        return [_resolve_metadata_refs(item, result) for item in value]
    if isinstance(value, tuple):
        return [_resolve_metadata_refs(item, result) for item in value]
    if isinstance(value, dict):
        return {key: _resolve_metadata_refs(item, result) for key, item in value.items()}
    return _json_ready(value)


def _json_ready(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    return value
