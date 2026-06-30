"""Reusable local-coordinate model fragments."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from tuba.coordinates import CoordinateSystem
from tuba.model import TubaModel
from tuba.patches import AddElement, AddNode, AddSupport, ModelPatch, ModelTransaction
from tuba.placements import PlacementAssignment, PlacementFrame


@dataclass
class ModelFragment:
    """A reusable local-coordinate model subassembly."""

    name: str
    model: TubaModel = field(default_factory=lambda: TubaModel(project_name="Fragment"))
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.model.project_name = self.name

    def pipe(self, section: str, material: str):
        return self.model.pipe(section=section, material=material)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "metadata": self.metadata,
            "model": self.model.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ModelFragment":
        return cls(
            name=data["name"],
            model=TubaModel.from_dict(data["model"]),
            metadata=data.get("metadata", {}),
        )


@dataclass
class PlacementResult:
    group_name: str
    node_ids: dict[str, str]
    element_ids: dict[str, str]


def place_fragment(
    model: TubaModel,
    fragment: ModelFragment,
    coordinate_system: CoordinateSystem,
    *,
    name: str,
) -> PlacementResult:
    """Place a local-coordinate fragment into a parent model."""
    snapshot = model.to_dict()
    start_support_count = len(model.supports)
    try:
        if name in model.groups:
            raise ValueError(f"Group placement {name!r} already exists.")
        _copy_missing_catalog_entries(model, fragment)
        patch = build_fragment_patch(fragment, coordinate_system, name=name)
        result = ModelTransaction(model).apply(patch)
        model.groups[name] = {
            "name": name,
            "fragment": fragment.name,
            "coordinate_system": coordinate_system.to_dict(),
            "nodes": list(result.node_ids.values()),
            "elements": list(result.element_ids.values()),
            "supports": list(range(start_support_count, start_support_count + result.support_count)),
            "metadata": copy.deepcopy(fragment.metadata),
        }
        model.placement_frames[name] = PlacementFrame.from_coordinate_system(
            name,
            coordinate_system,
            frame_type="assembly",
            source="fragment",
            metadata={"fragment": fragment.name},
        )
        model.placement_assignments.append(
            PlacementAssignment(
                target=f"group:{name}",
                frame=f"placement_frame:{name}",
                role="object_placement",
                source="fragment",
            )
        )
        model.validate()
        return PlacementResult(group_name=name, node_ids=result.node_ids, element_ids=result.element_ids)
    except Exception:
        restored = TubaModel.from_dict(snapshot)
        model.__dict__.clear()
        model.__dict__.update(restored.__dict__)
        raise


def build_fragment_patch(
    fragment: ModelFragment,
    coordinate_system: CoordinateSystem,
    *,
    name: str,
) -> ModelPatch:
    operations = []

    for local_node_id, node in fragment.model.nodes.items():
        operations.append(
            AddNode(
                local_id=local_node_id,
                coords=coordinate_system.to_global_point(node.coords).tolist(),
            )
        )

    for elem in fragment.model.elements:
        operations.append(
            AddElement(
                local_id=elem.id,
                type=elem.type,
                n1=elem.n1,
                n2=elem.n2,
                section=elem.section,
                material=elem.material,
                bend_radius=elem.bend_radius,
                bend_angle=elem.bend_angle,
                twist_angle=elem.twist_angle,
                id_prefix=_prefix_from_id(elem.id),
            )
        )

    for support in fragment.model.supports:
        direction = (
            coordinate_system.to_global_vector(support.direction).tolist()
            if support.direction is not None
            else None
        )
        operations.append(
            AddSupport(
                node=support.node,
                type=support.type,
                direction=direction,
                stiffness=support.stiffness,
                imposed_displacement=support.imposed_displacement,
                stiffness_matrix=support.stiffness_matrix,
                blocked_dof=support.blocked_dof,
                mass=support.mass,
                friction_coefficient=support.friction_coefficient,
            )
        )

    return ModelPatch(
        operations=operations,
        provenance={"fragment": fragment.name, "placement": name},
    )


def _copy_missing_catalog_entries(model: TubaModel, fragment: ModelFragment) -> None:
    for material_name, material in fragment.model.materials.items():
        if material_name in model.materials:
            if model.materials[material_name] != material:
                raise ValueError(
                    f"Material {material_name!r} conflicts with fragment {fragment.name!r}."
                )
            continue
        model.materials[material_name] = copy.deepcopy(material)

    for section_name, section in fragment.model.sections.items():
        if section_name in model.sections:
            if model.sections[section_name] != section:
                raise ValueError(
                    f"Section {section_name!r} conflicts with fragment {fragment.name!r}."
                )
            continue
        model.sections[section_name] = copy.deepcopy(section)


def _prefix_from_id(element_id: str) -> str:
    if "_" not in element_id:
        return "elem"
    return element_id.rsplit("_", 1)[0]
