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
"angle zero" points. Tuba writes endpoint seeds for connected pipe chains to the ``.comm``
as ``CARA='GENE_TUYAU'`` (see ``_pipe_orientation_vector`` in
``tuba/solver/aster_comm.py``); :func:`read_gene_tuyau` reads that value back so
the glyphs land where the solver's sectors actually are.
:data:`DISPLAY_GENERATRICE` is what to use only when there is no ``.comm`` to
read - and a result that fell back to it says so, because the sector indices are
then rotated by an unknown amount relative to the ones Code_Aster computed.
"""

from __future__ import annotations

import ast
import math
from textwrap import dedent
from dataclasses import dataclass

#: Through-thickness layers Tuba requests from Code_Aster.
CODE_ASTER_TUYAU_NCOU = 3

#: Circumferential divisions Tuba requests from Code_Aster.
CODE_ASTER_TUYAU_NSEC = 16

#: Reference direction the sub-point display-position formula measures angles
#: from when the solved ``GENE_TUYAU`` is not available. A fallback, not a
#: solved value - see the module docstring and :data:`GENERATRICE_SOURCES`.
DISPLAY_GENERATRICE: tuple[float, float, float] = (0.0, 0.0, 1.0)

#: Where a result's generatrice came from, so the contract can say which.
GENERATRICE_SOLVED = "code_aster_gene_tuyau"
GENERATRICE_FALLBACK = "display_generatrice_fallback"

def read_gene_tuyau(comm_text: str) -> tuple[float, float, float] | None:
    """The ``GENE_TUYAU`` orientation Code_Aster was given, or ``None``.

    Reads the value Tuba itself wrote into the ``.comm``, so sector 0 on screen
    is sector 0 in the solver. Returns ``None`` for a file with no such entry,
    a malformed triplet, or a vector that is not a direction - the caller then
    falls back to :data:`DISPLAY_GENERATRICE` and records that it did.
    """
    try:
        tree = ast.parse(dedent(comm_text))
    except SyntaxError:
        return None
    for call in ast.walk(tree):
        if not isinstance(call, ast.Call):
            continue
        keywords = {item.arg: item.value for item in call.keywords}
        try:
            if ast.literal_eval(keywords.get("CARA")) != "GENE_TUYAU":
                continue
            vector = tuple(float(value) for value in ast.literal_eval(keywords.get("VALE")))
        except (ValueError, TypeError):
            continue
        if len(vector) == 3 and all(math.isfinite(component) for component in vector) and math.hypot(*vector) > 1.0e-12:
            return vector
    return None


@dataclass(frozen=True)
class Generatrice:
    """A section reference direction, and where it came from.

    Carrying the provenance with the vector is the point: a glyph placed with a
    fallback generatrice is still a measured value in a plausible place, and
    nothing in the picture would otherwise say the angle is unverified.
    """

    vector: tuple[float, float, float]
    source: str

    @property
    def solved(self) -> bool:
        return self.source == GENERATRICE_SOLVED

    def to_dict(self) -> dict[str, object]:
        return {"vector": list(self.vector), "source": self.source, "solved": self.solved}


def read_gene_tuyau_factors(comm_text: str) -> list[tuple[tuple[str, ...] | None, Generatrice]]:
    """Read every endpoint seed without discarding its ``GROUP_NO`` scope.

    A scoped seed must contain one endpoint node; Code_Aster propagates it to
    the connected TUYAU chain. Element groups cannot define ``GENE_TUYAU``.
    ``None`` denotes an unscoped legacy factor, whose global interpretation is
    retained by the solver reader only for old studies.
    """
    try:
        tree = ast.parse(dedent(comm_text))
    except SyntaxError as exc:
        raise ValueError("GENE_TUYAU command file is not valid Python.") from exc
    factors = []
    for call in ast.walk(tree):
        if not isinstance(call, ast.Call):
            continue
        keywords = {item.arg: item.value for item in call.keywords}
        try:
            cara = ast.literal_eval(keywords.get("CARA"))
        except (ValueError, TypeError):
            continue
        if cara != "GENE_TUYAU":
            continue
        try:
            vector = tuple(float(value) for value in ast.literal_eval(keywords.get("VALE")))
            if len(vector) != 3 or not all(math.isfinite(value) for value in vector) or math.hypot(*vector) <= 1e-12:
                raise ValueError("not a finite direction")
            if "GROUP_MA" in keywords:
                raise ValueError("requires GROUP_NO, not GROUP_MA")
            groups = ast.literal_eval(keywords["GROUP_NO"]) if "GROUP_NO" in keywords else None
            if isinstance(groups, str):
                groups = (groups,)
            if groups is not None:
                if not isinstance(groups, (tuple, list)) or len(groups) != 1 or not isinstance(groups[0], str) or not groups[0]:
                    raise ValueError("requires one GROUP_NO endpoint group")
                groups = tuple(groups)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Invalid GENE_TUYAU endpoint factor: {exc}.") from exc
        factors.append((groups, Generatrice(vector, GENERATRICE_SOLVED)))
    return factors


def solve_generatrice(comm_text: str | None) -> Generatrice:
    """The model\'s own generatrice, or the documented fallback."""
    if comm_text:
        vector = read_gene_tuyau(comm_text)
        if vector is not None:
            return Generatrice(vector, GENERATRICE_SOLVED)
    return Generatrice(DISPLAY_GENERATRICE, GENERATRICE_FALLBACK)


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
    if subpoint_index > stride * layers_through_wall(ncou):
        return None
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
    generatrice: Generatrice | None = None,
) -> dict[str, object]:
    """Scene-ready description of the sub-point grid on one element node.

    The generatrice is reported with its provenance. A panel that says "sector 0
    on (0, 0, 1)" when the solver was given something else is stating a display
    convention as a solved angle, which is the one thing a wall-stress claim
    must not do.
    """
    sectors = sectors_per_layer(nsec)
    layers = layers_through_wall(ncou)
    reference = generatrice or Generatrice(DISPLAY_GENERATRICE, GENERATRICE_FALLBACK)
    return {
        "nsec": int(nsec),
        "ncou": int(ncou),
        "sectors": sectors,
        "layers": layers,
        "subpoints_per_node": sectors * layers,
        "generatrice": reference.to_dict(),
    }
