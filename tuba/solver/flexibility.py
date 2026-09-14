"""Elbow flexibility for beam-idealised pipe bends.

A bend is more flexible in bending than a straight beam of the same section,
because the wall ovalises. Code_Aster takes that as ``COEF_FLEX`` on a COUDE
beam element, which divides the section inertia by ``k``.

This is a solver input, not a code check. It shares the flexibility
characteristic ``h = tR/r_m^2`` with the piping codes' stress intensification
factors, and the two must not be confused: an SIF amplifies an already
computed stress afterwards, and applying one as a flexibility - or a
flexibility as an SIF - miscounts the same effect twice. Tuba no longer
calculates SIFs at all; see docs/architecture/b31j-compliance-migration.md.

The formulae are the classical bend relations (``h = tR/r_m^2``,
``k = 1.65/h``), numerically identical across B31.3 Appendix D and B31J.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from tuba.model import Element, TubaModel


@dataclass(frozen=True)
class ElbowFlexibility:
    """Flexibility characteristic and factor for one bend."""

    h: float
    k: float


def elbow_flexibility(element: "Element", model: "TubaModel") -> Optional[ElbowFlexibility]:
    """Return the bend's flexibility, or None when the element is not a bend."""
    if element.type != "pipe_bend" or element.bend_radius is None:
        return None

    section = model.sections[element.section]
    t = section.corroded_WT
    R = element.bend_radius
    r_m = section.mean_radius
    if t <= 0 or R <= 0 or r_m <= 0:
        raise ValueError(
            f"Bend {element.id!r} needs positive wall, bend radius and mean radius: "
            f"t={t}, R={R}, r_m={r_m}."
        )

    h = t * R / (r_m**2)
    return ElbowFlexibility(h=h, k=1.65 / h)
