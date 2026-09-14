"""How faithfully the analysis mesh represents the geometry it was built from.

One check today: **bend discretisation**. A circular bend reaches the solver as
a chain of segments whose nodes sit on the arc, so the mesh cuts the corner. The
reviewer's question - "is this bend meshed finely enough?" - is two numbers: how
many elements span the arc, and how far the chord falls inside it.

Everything here reads the :class:`~tuba.analysis.mesh.AnalysisMesh` alone. A
bend's true arc travels with the mesh in
``MeshElementSource.metadata["bend_geometry"]``, so the check needs no
``TubaModel`` and stays usable wherever a mesh record is.

The verdict this module reports is **geometric, not a code check**. It states
whether the chord falls inside the arc by more than a declared fraction of the
bend radius, and it carries that fraction along so the reader sees the criterion
rather than a bare pass mark. Nothing here speaks to ASME acceptability.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from tuba.analysis.mesh import AnalysisMesh

#: Default geometric tolerance for the bend chord: the mid-chord may fall no
#: more than this fraction of the bend radius inside the true arc. This is a
#: meshing-fidelity tolerance chosen for display, not a code acceptance
#: criterion - callers that have a project rule should pass their own.
DEFAULT_CHORD_TOLERANCE_RATIO = 0.01

#: ``MeshElementSource.role`` values that mean "this element is one span of a
#: larger curved source element".
BEND_SEGMENT_ROLES = frozenset({"bend_segment"})


@dataclass(frozen=True)
class BendDiscretisation:
    """How one source bend was cut into mesh elements."""

    source_element_id: str
    element_count: int
    radius: float  # [m]
    angle: float  # [deg]
    chord_deviation: float  # [m], mid-chord sagitta of a single segment
    tolerance: float  # [m], radius * tolerance_ratio
    tolerance_ratio: float

    @property
    def within_tolerance(self) -> bool:
        return self.chord_deviation <= self.tolerance

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_element_id": self.source_element_id,
            "element_count": self.element_count,
            "radius": self.radius,
            "angle": self.angle,
            "chord_deviation": self.chord_deviation,
            "tolerance": self.tolerance,
            "tolerance_ratio": self.tolerance_ratio,
            "within_tolerance": self.within_tolerance,
        }


def chord_deviation(radius: float, angle_deg: float, element_count: int) -> float:
    """Sagitta of one chord when ``angle_deg`` of arc is cut into equal spans.

    Each span subtends ``angle / n``; the chord's deepest excursion inside the
    arc is ``R (1 - cos(half-span))``. Returns ``0.0`` for a degenerate input
    rather than raising - a mesh that cannot be measured must not take the
    scene build down with it.
    """
    if radius <= 0.0 or element_count < 1 or not math.isfinite(radius) or not math.isfinite(angle_deg):
        return 0.0
    half_span = math.radians(abs(angle_deg)) / (2.0 * element_count)
    return float(radius * (1.0 - math.cos(half_span)))


def bend_discretisation(
    analysis_mesh: AnalysisMesh,
    *,
    tolerance_ratio: float = DEFAULT_CHORD_TOLERANCE_RATIO,
) -> list[BendDiscretisation]:
    """One record per source bend the mesh was built from, worst chord first."""
    spans: dict[str, list[dict[str, Any]]] = {}
    for source in analysis_mesh.element_sources.values():
        if source.role not in BEND_SEGMENT_ROLES:
            continue
        geometry = source.metadata.get("bend_geometry")
        if not isinstance(geometry, dict):
            continue
        spans.setdefault(str(source.source_ref), []).append(geometry)

    records: list[BendDiscretisation] = []
    for source_ref, geometries in spans.items():
        geometry = geometries[0]
        radius = _as_float(geometry.get("radius"))
        angle = _as_float(geometry.get("angle"))
        if radius is None or angle is None:
            continue
        count = len(geometries)
        deviation = chord_deviation(radius, angle, count)
        records.append(
            BendDiscretisation(
                source_element_id=source_ref.split(":", 1)[-1],
                element_count=count,
                radius=radius,
                angle=angle,
                chord_deviation=deviation,
                tolerance=radius * tolerance_ratio,
                tolerance_ratio=tolerance_ratio,
            )
        )
    records.sort(key=lambda record: (-record.chord_deviation, record.source_element_id))
    return records


def discretisation_summary(
    analysis_mesh: AnalysisMesh,
    *,
    tolerance_ratio: float = DEFAULT_CHORD_TOLERANCE_RATIO,
) -> dict[str, Any] | None:
    """Scene-ready summary of the bend check, or ``None`` when the mesh has no bends.

    Returning ``None`` rather than an empty shell matters: a straight-run mesh
    has nothing to say here, and the viewer must omit the panel instead of
    showing a check that passed vacuously.
    """
    records = bend_discretisation(analysis_mesh, tolerance_ratio=tolerance_ratio)
    if not records:
        return None
    worst = records[0]
    return {
        "check": "bend_chord_deviation",
        "unit": "m",
        "bend_count": len(records),
        "min_elements_per_bend": min(record.element_count for record in records),
        "max_elements_per_bend": max(record.element_count for record in records),
        "max_chord_deviation": worst.chord_deviation,
        "worst_bend": worst.to_dict(),
        "tolerance_ratio": tolerance_ratio,
        "within_tolerance": all(record.within_tolerance for record in records),
        "bends": [record.to_dict() for record in records],
    }


def _as_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None
