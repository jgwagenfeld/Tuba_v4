"""Neutral pipe-junction topology used by compliance and solid meshing."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from tuba.model import PipeSection, TubaModel


@dataclass(frozen=True)
class TeeJunction:
    node_id: str
    header_element_ids: tuple[str, str]
    branch_element_id: str
    directions: dict[str, tuple[float, float, float]]


def classify_tee_junction(
    model: TubaModel,
    node_id: str,
    *,
    element_ids: list[str] | tuple[str, ...] | set[str] | None = None,
) -> TeeJunction:
    """Return the most-opposed header pair and remaining branch at *node_id*."""
    if node_id not in model.nodes:
        raise ValueError(f"Tee node {node_id!r} does not exist.")
    selected = None if element_ids is None else set(element_ids)
    connected = [
        element
        for element in model.elements
        if (element.n1 == node_id or element.n2 == node_id)
        and element.type.startswith("pipe")
        and (selected is None or element.id in selected)
    ]
    if len(connected) != 3:
        raise ValueError(
            f"Tee node {node_id!r} requires exactly three connected pipe elements; "
            f"found {len(connected)}."
        )

    directions: dict[str, tuple[float, float, float]] = {}
    junction = model.nodes[node_id].coords
    for element in connected:
        section = model.sections[element.section]
        if not isinstance(section, PipeSection):
            raise ValueError(
                f"Tee element {element.id!r} requires a circular PipeSection; "
                f"got {type(section).__name__}."
            )
        other_node = element.n2 if element.n1 == node_id else element.n1
        direction = np.asarray(model.nodes[other_node].coords, dtype=float) - junction
        norm = float(np.linalg.norm(direction))
        if norm <= 1.0e-12:
            raise ValueError(f"Tee element {element.id!r} has a zero-length direction at {node_id!r}.")
        directions[element.id] = tuple(float(value) for value in direction / norm)

    pairs = [
        (float(np.dot(directions[left.id], directions[right.id])), left.id, right.id)
        for index, left in enumerate(connected)
        for right in connected[index + 1 :]
    ]
    pairs.sort(key=lambda item: item[0])
    if abs(pairs[1][0] - pairs[0][0]) <= 1.0e-8:
        raise ValueError(f"Tee node {node_id!r} has ambiguous header directions.")

    header_ids = (pairs[0][1], pairs[0][2])
    branch_id = next(element.id for element in connected if element.id not in header_ids)
    return TeeJunction(
        node_id=node_id,
        header_element_ids=header_ids,
        branch_element_id=branch_id,
        directions=directions,
    )
