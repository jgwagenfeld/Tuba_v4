"""Code_Aster ``MODELISATION`` assignment, shared by the mesh and the .comm.

``AFFE_MODELE`` assigns a modelisation per ``GROUP_MA``. Two places need that
same mapping: :mod:`tuba.solver.aster_comm` writes it into the command file, and
:mod:`tuba.solver.aster_mesh` records it on the :class:`~tuba.analysis.mesh.AnalysisMesh`
so the visualization scene can say what kind of mesh was actually solved.

They used to derive it independently from the element-type partition of the
model, which is exactly the sort of duplication that drifts. This module owns it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids a solver->model import cycle
    from tuba.model import Support, TubaModel


class PipeModelization(str, Enum):
    """Engineer-selectable pipe idealization."""

    TUYAU_3M = "TUYAU_3M"
    POU_D_T = "POU_D_T"
    SOLID_3D = "3D"


def discrete_support_group(node: str) -> str:
    """``GROUP_MA`` name for the POI1 element carrying a discrete spring/mass."""
    return f"DIS_{node}"


def needs_discrete_element(support: "Support") -> bool:
    """True when a support is realised as a POI1 discrete element."""
    is_discrete_spring = support.type == "spring" and support.attached_to is None and (
        support.stiffness_matrix is not None or support.stiffness is not None
    )
    return is_discrete_spring or support.mass > 0.0


@dataclass(frozen=True)
class SpringLink:
    """An attached spring: a SEG2 from a helper node to the support node, the helper tied to the attached node."""

    support: "Support"
    group: str
    helper: str


def spring_links(model: "TubaModel") -> list[SpringLink]:
    links = [
        SpringLink(support, f"SPRING_{index}", f"SPRHLP_{index}")
        for index, support in enumerate(model.supports)
        if support.type == "spring"
        and support.attached_to is not None
        and (support.stiffness_matrix is not None or support.stiffness is not None)
    ]
    authored = set(model.nodes) | {element.id for element in model.elements} | set(model.groups)
    collisions = authored.intersection(name for link in links for name in (link.group, link.helper))
    if collisions:
        raise ValueError(f"Attached spring helper names collide with authored names: {sorted(collisions)}.")
    return links


def modelisation_assignments(
    model: "TubaModel",
    pipe_modelization: PipeModelization | str = PipeModelization.TUYAU_3M,
    *,
    volume_element_ids: Sequence[str] | None = None,
) -> dict[str, str]:
    """Return ``{GROUP_MA name: MODELISATION}`` in ``AFFE_MODELE`` order.

    Group names are the raw Tuba names. Callers that write a .comm apply their
    own ``name_map`` on top; the ``AnalysisMesh`` stores them unmapped.
    """
    by_type: dict[str, bool] = {}
    for element in model.elements:
        by_type[element.type] = True

    assignments: dict[str, str] = {}
    pipe_mod = PipeModelization(pipe_modelization)
    if by_type.get("pipe_straight") or by_type.get("pipe_bend"):
        if pipe_mod == PipeModelization.SOLID_3D and volume_element_ids is not None:
            vol_set = set(volume_element_ids)
            pipe_elements = [e for e in model.elements if e.type in ("pipe_straight", "pipe_bend")]
            has_vol = any(e.id in vol_set for e in pipe_elements)
            has_pipe = any(e.id not in vol_set for e in pipe_elements)
            if has_vol:
                assignments["AllSolids"] = "3D"
            if has_pipe:
                assignments["AllPipes"] = "TUYAU_3M"
        else:
            assignments["AllPipes"] = pipe_mod.value
    if by_type.get("beam"):
        assignments["G_TUBE"] = "POU_D_T"
    if by_type.get("bar"):
        assignments["G_BAR"] = "BARRE"
    if by_type.get("cable"):
        assignments["G_CABLE"] = "CABLE"
    for support in model.supports:
        if needs_discrete_element(support):
            assignments[discrete_support_group(support.node)] = "DIS_TR"
    for link in spring_links(model):
        assignments[link.group] = "DIS_TR"
    from tuba.solver.aster_contact import shoes
    for shoe in shoes(model, pipe_modelization):
        assignments[shoe.group] = 'DIS_T'
    return assignments
