"""Support-to-rack load-path association and reaction rollup."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tuba.analysis.results import ResultState
from tuba.model import TubaModel
from tuba.refs import EntityRef


@dataclass(frozen=True)
class SupportRackAssociation:
    support: EntityRef
    rack: EntityRef
    node: EntityRef
    attachment_point: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "support": self.support.to_dict(),
            "rack": self.rack.to_dict(),
            "node": self.node.to_dict(),
            "attachment_point": self.attachment_point,
        }


@dataclass(frozen=True)
class LoadPathReport:
    associations: list[SupportRackAssociation] = field(default_factory=list)
    rack_loads: dict[str, dict[str, float]] = field(default_factory=dict)
    diagnostics: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "associations": [association.to_dict() for association in self.associations],
            "rack_loads": {rack: dict(loads) for rack, loads in self.rack_loads.items()},
            "diagnostics": list(self.diagnostics),
        }


def analyze_load_paths(
    model: TubaModel,
    *,
    support_reactions: dict[str, tuple[float, float, float]] | None = None,
    result_state: ResultState | None = None,
) -> LoadPathReport:
    resolved_reactions = _support_reactions_from_result_state(model, result_state) if result_state is not None else {}
    resolved_reactions.update(support_reactions or {})
    attachments = _rack_attachment_nodes(model)
    associations: list[SupportRackAssociation] = []
    diagnostics: list[str] = []

    for support in model.supports:
        match = attachments.get(support.node)
        if match is None:
            diagnostics.append(f"Support {support.id!r} is not associated with a rack attachment point.")
            continue
        rack_name, attachment_point = match
        associations.append(
            SupportRackAssociation(
                support=EntityRef("support", support.id),
                rack=EntityRef("group", rack_name),
                node=EntityRef("node", support.node),
                attachment_point=attachment_point,
            )
        )

    rack_loads = _rack_loads(associations, resolved_reactions)
    return LoadPathReport(associations=associations, rack_loads=rack_loads, diagnostics=diagnostics)


def _rack_attachment_nodes(model: TubaModel) -> dict[str, tuple[str, str]]:
    attachments: dict[str, tuple[str, str]] = {}
    for group_name, group in model.groups.items():
        metadata = group.get("metadata", {})
        if metadata.get("assembly_type") != "rack_bay":
            continue
        for point_name, node_ref in metadata.get("attachment_points", {}).items():
            if isinstance(node_ref, str) and node_ref.startswith("node:"):
                attachments[node_ref.split(":", 1)[1]] = (group_name, point_name)
    return attachments


def _rack_loads(
    associations: list[SupportRackAssociation],
    support_reactions: dict[str, tuple[float, float, float]],
) -> dict[str, dict[str, float]]:
    loads: dict[str, dict[str, float]] = {}
    for association in associations:
        rack_id = association.rack.id
        support_id = association.support.id
        entry = loads.setdefault(
            rack_id,
            {
                "support_count": 0,
                "force_x_n": 0.0,
                "force_y_n": 0.0,
                "force_z_n": 0.0,
            },
        )
        entry["support_count"] += 1
        reaction = support_reactions.get(support_id)
        if reaction is None:
            continue
        entry["force_x_n"] += float(reaction[0])
        entry["force_y_n"] += float(reaction[1])
        entry["force_z_n"] += float(reaction[2])
    return loads


def _support_reactions_from_result_state(
    model: TubaModel,
    result_state: ResultState,
) -> dict[str, tuple[float, float, float]]:
    model_revision = int(getattr(model, "revision", 0))
    if result_state.model_revision != model_revision:
        raise ValueError(
            f"Cannot analyze load paths for model revision {model_revision}; result state uses {result_state.model_revision}."
        )
    reactions: dict[str, tuple[float, float, float]] = {}
    for support in model.supports:
        if support.node not in result_state.node_reactions:
            continue
        reaction = result_state.node_reactions[support.node]
        reactions[support.id] = (float(reaction[0]), float(reaction[1]), float(reaction[2]))
    return reactions
