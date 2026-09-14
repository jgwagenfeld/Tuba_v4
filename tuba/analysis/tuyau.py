"""Code_Aster ``TUYAU`` sub-point indexing - one source of truth.

``TUYAU_3M`` is topologically a 1D mesh, but its stress recovery lives at
sub-points arranged around and through the pipe wall. Code_Aster numbers those
sub-points in a single flat sequence, and turning that number back into a place
in the wall is the step everything downstream depends on: the solver reader
places its display glyphs with it, and the scene builder names where a peak sits.

The convention, from ``AFFE_CARA_ELEM`` / ``TUYAU`` (u3.11.01):

* ``NSEC`` circumferential divisions give ``2 * NSEC + 1`` angular stations,
* ``NCOU`` through-thickness layers give ``2 * NCOU + 1`` radial stations,
* sub-points run angle-fastest, one-based.

Sector 0 sits on the *generatrice* - the reference direction that fixes where
"angle zero" points. :data:`DISPLAY_GENERATRICE` is the vector Tuba's sub-point
display-position formula measures from. It describes where the glyphs are drawn;
it is not a read-back of the ``GENE_TUYAU`` value the ``.comm`` emits for a
given model.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

#: Through-thickness layers Tuba requests from Code_Aster.
CODE_ASTER_TUYAU_NCOU = 3

#: Circumferential divisions Tuba requests from Code_Aster.
CODE_ASTER_TUYAU_NSEC = 16

#: Reference direction the sub-point display-position formula measures angles
#: from. See the module docstring: a display convention, not a solved value.
DISPLAY_GENERATRICE: tuple[float, float, float] = (0.0, 0.0, 1.0)


def sectors_per_layer(nsec: int = CODE_ASTER_TUYAU_NSEC) -> int:
    """Angular stations on one layer: ``2 * NSEC + 1``."""
    return 2 * int(nsec) + 1


def layers_through_wall(ncou: int = CODE_ASTER_TUYAU_NCOU) -> int:
    """Radial stations through the wall: ``2 * NCOU + 1``, inner to outer."""
    return 2 * int(ncou) + 1


@dataclass(frozen=True)
class SubpointStation:
    """Where one sub-point sits in the wall."""

    sector_index: int  # 0 .. 2*NSEC, around the circumference from the generatrice
    layer_index: int  # 0 .. 2*NCOU, inner wall (0) to outer wall
    angle_fraction: float  # sector_index / (2*NSEC), one full turn at 1.0
    radius_fraction: float  # layer_index / (2*NCOU), 0.0 at the bore, 1.0 at the OD

    @property
    def angle_deg(self) -> float:
        return self.angle_fraction * 360.0

    @property
    def angle_rad(self) -> float:
        return self.angle_fraction * 2.0 * math.pi


def subpoint_station(
    subpoint_index: int,
    *,
    nsec: int = CODE_ASTER_TUYAU_NSEC,
    ncou: int = CODE_ASTER_TUYAU_NCOU,
) -> SubpointStation | None:
    """Decode a one-based Code_Aster ``SOUS_POINT`` index into a wall position.

    Returns ``None`` for anything that is not a positive integer index, so a
    malformed solver row degrades to "position unknown" instead of taking the
    read down.
    """
    if not isinstance(subpoint_index, int) or isinstance(subpoint_index, bool) or subpoint_index < 1:
        return None
    if nsec < 1 or ncou < 1:
        return None
    stride = sectors_per_layer(nsec)
    zero_based = subpoint_index - 1
    sector_index = zero_based % stride
    layer_index = zero_based // stride
    return SubpointStation(
        sector_index=sector_index,
        layer_index=layer_index,
        angle_fraction=sector_index / (2.0 * nsec),
        radius_fraction=layer_index / (2.0 * ncou),
    )


def section_profile(
    nsec: int = CODE_ASTER_TUYAU_NSEC,
    ncou: int = CODE_ASTER_TUYAU_NCOU,
) -> dict[str, object]:
    """Scene-ready description of the sub-point grid on one element node."""
    sectors = sectors_per_layer(nsec)
    layers = layers_through_wall(ncou)
    return {
        "nsec": int(nsec),
        "ncou": int(ncou),
        "sectors": sectors,
        "layers": layers,
        "subpoints_per_node": sectors * layers,
        "display_generatrice": list(DISPLAY_GENERATRICE),
    }
