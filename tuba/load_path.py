"""Support-to-rack load-path association and reaction rollup."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tuba.analysis.results import ResultState
from tuba.assemblies import rack_assemblies
from tuba.model import TubaModel
from tuba.refs import EntityRef


@dataclass(frozen=True)
class SupportRackAssociation:
    support: EntityRef
    rack: EntityRef
    #: The rack node the support is attached to.
    node: EntityRef
    #: That node's attachment-point name on the rack, or "" for another rack node.
    attachment_point: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "support": self.support.to_dict(),
            "rack": self.rack.to_dict(),
            "node": self.node.to_dict(),
            "attachment_point": self.attachment_point,
        }


@dataclass(frozen=True)
class GroundedSupportLoad:
    """A grounded support and the load it delivers to foundation."""

    support: EntityRef
    #: The support's own node, where Code_Aster reports its reaction.
    node: EntityRef
    #: The reaction at that node; None until a result state supplies it.
    force_n: tuple[float, float, float] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "support": self.support.to_dict(),
            "node": self.node.to_dict(),
            "force_n": list(self.force_n) if self.force_n is not None else None,
        }


@dataclass(frozen=True)
class LoadPathReport:
    associations: list[SupportRackAssociation] = field(default_factory=list)
    rack_loads: dict[str, dict[str, float]] = field(default_factory=dict)
    grounded_loads: list[GroundedSupportLoad] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "associations": [association.to_dict() for association in self.associations],
            "rack_loads": {rack: dict(loads) for rack, loads in self.rack_loads.items()},
            "grounded_loads": [load.to_dict() for load in self.grounded_loads],
            "diagnostics": list(self.diagnostics),
        }


def analyze_load_paths(
    model: TubaModel,
    *,
    node_reactions: dict[str, tuple[float, float, float]] | None = None,
    result_state: ResultState | None = None,
) -> LoadPathReport:
    """Associate attached supports with racks and sum the reactions at their attached nodes.

    Code_Aster reports a tie's force on the structure as REAC_NODA on the attached node,
    so a rack's load is the sum over its distinct attached nodes. A grounded support
    stands on a point fixed in space: its load goes to foundation as the reaction at
    its own node, never to a rack, and being grounded is by design, not a diagnostic.
    Diagnostics are reserved for an attached support whose node belongs to no rack.
    """
    reactions = _node_reactions_from_result_state(model, result_state) if result_state is not None else {}
    reactions.update(node_reactions or {})
    racks = _rack_nodes(model)
    associations: list[SupportRackAssociation] = []
    grounded_loads: list[GroundedSupportLoad] = []
    diagnostics: list[str] = []
    for support in model.supports:
        if support.attached_to is None:
            reaction = reactions.get(support.node)
            grounded_loads.append(
                GroundedSupportLoad(
                    support=EntityRef("support", support.id),
                    node=EntityRef("node", support.node),
                    force_n=(
                        None
                        if reaction is None
                        else (float(reaction[0]), float(reaction[1]), float(reaction[2]))
                    ),
                )
            )
            continue
        matches = racks.get(support.attached_to, [])
        if not matches:
            diagnostics.append(
                f"Support {support.id!r} is attached to node {support.attached_to!r}, which belongs to no rack."
            )
            continue
        for rack_name, point_name in matches:
            associations.append(
                SupportRackAssociation(
                    support=EntityRef("support", support.id),
                    rack=EntityRef("group", rack_name),
                    node=EntityRef("node", support.attached_to),
                    attachment_point=point_name,
                )
            )
    return LoadPathReport(
        associations=associations,
        rack_loads=_rack_loads(associations, reactions),
        grounded_loads=grounded_loads,
        diagnostics=diagnostics,
    )


def _rack_nodes(model: TubaModel) -> dict[str, list[tuple[str, str]]]:
    racks: dict[str, list[tuple[str, str]]] = {}
    for rack in rack_assemblies(model):
        names = {node_id: point_name for point_name, node_id in rack.attachment_points.items()}
        for node_id in rack.nodes:
            racks.setdefault(node_id, []).append((rack.group_name, names.get(node_id, "")))
    return racks


def _rack_loads(
    associations: list[SupportRackAssociation],
    node_reactions: dict[str, tuple[float, float, float]],
) -> dict[str, dict[str, float]]:
    loads: dict[str, dict[str, float]] = {}
    counted: set[tuple[str, str]] = set()
    for association in associations:
        entry = loads.setdefault(
            association.rack.id,
            {"support_count": 0, "force_x_n": 0.0, "force_y_n": 0.0, "force_z_n": 0.0},
        )
        entry["support_count"] += 1
        key = (association.rack.id, association.node.id)
        reaction = node_reactions.get(association.node.id)
        if reaction is None or key in counted:
            continue
        counted.add(key)
        entry["force_x_n"] += float(reaction[0])
        entry["force_y_n"] += float(reaction[1])
        entry["force_z_n"] += float(reaction[2])
    return loads


def _node_reactions_from_result_state(
    model: TubaModel,
    result_state: ResultState,
) -> dict[str, tuple[float, float, float]]:
    model_revision = int(getattr(model, "revision", 0))
    if result_state.model_revision != model_revision:
        raise ValueError(
            f"Cannot analyze load paths for model revision {model_revision}; result state uses {result_state.model_revision}."
        )
    return {
        node_id: (float(reaction[0]), float(reaction[1]), float(reaction[2]))
        for node_id, reaction in result_state.node_reactions.items()
        if all(component is not None for component in reaction[:3])
    }
