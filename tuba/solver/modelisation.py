"""Code_Aster ``MODELISATION`` assignment, shared by the mesh and the .comm.

``AFFE_MODELE`` assigns a modelisation per ``GROUP_MA``. Two places need that
same mapping: :mod:`tuba.solver.aster_comm` writes it into the command file, and
:mod:`tuba.solver.aster_mesh` records it on the :class:`~tuba.analysis.mesh.AnalysisMesh`
so the visualization scene can say what kind of mesh was actually solved.

They used to derive it independently from the element-type partition of the
model, which is exactly the sort of duplication that drifts. This module owns it.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids a solver->model import cycle
    from tuba.model import Support, TubaModel


class PipeModelization(str, Enum):
    """Engineer-selectable pipe idealization."""

    TUYAU_3M = "TUYAU_3M"
    SOLID_3D = "3D"


def discrete_support_group(node: str) -> str:
    """``GROUP_MA`` name for the POI1 element carrying a discrete spring/mass."""
    return f"DIS_{node}"


def needs_discrete_element(support: "Support") -> bool:
    """True when a support is realised as a POI1 discrete element."""
    is_discrete_spring = support.type == "spring" and (
        support.stiffness_matrix is not None or support.stiffness is not None
    )
    return is_discrete_spring or support.mass > 0.0


def modelisation_assignments(model: "TubaModel") -> dict[str, str]:
    """Return ``{GROUP_MA name: MODELISATION}`` in ``AFFE_MODELE`` order.

    Group names are the raw Tuba names. Callers that write a .comm apply their
    own ``name_map`` on top; the ``AnalysisMesh`` stores them unmapped.
    """
    by_type: dict[str, bool] = {}
    for element in model.elements:
        by_type[element.type] = True

    assignments: dict[str, str] = {}
    if by_type.get("pipe_straight") or by_type.get("pipe_bend"):
        assignments["AllPipes"] = "TUYAU_3M"
    if by_type.get("beam"):
        assignments["G_TUBE"] = "POU_D_T"
    if by_type.get("bar"):
        assignments["G_BAR"] = "BARRE"
    if by_type.get("cable"):
        assignments["G_CABLE"] = "CABLE"
    for support in model.supports:
        if needs_discrete_element(support):
            assignments[discrete_support_group(support.node)] = "DIS_TR"
    return assignments
