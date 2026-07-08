"""Normalized section profile adapter for geometry, collision, IFC, and quantities."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tuba.model import BarSection, CableSection, IBeamSection, PipeSection, RectangularSection


@dataclass(frozen=True)
class SectionProfile:
    kind: str
    collision_radius_m: float
    area_m2: float
    dimensions: dict[str, float] = field(default_factory=dict)
    source: Any = None


def profile_for_section(section) -> SectionProfile:
    if isinstance(section, PipeSection):
        return SectionProfile(
            kind="pipe",
            collision_radius_m=section.OD / 2.0,
            area_m2=section.area,
            dimensions={
                "OD": section.OD,
                "WT": section.WT,
                "ID": section.ID,
            },
            source=section,
        )
    if isinstance(section, BarSection):
        return SectionProfile(
            kind="bar",
            collision_radius_m=section.OD / 2.0,
            area_m2=section.area,
            dimensions={"OD": section.OD, "WT": section.WT},
            source=section,
        )
    if isinstance(section, CableSection):
        return SectionProfile(
            kind="cable",
            collision_radius_m=section.radius,
            area_m2=section.area,
            dimensions={"radius": section.radius, "pretension": section.pretension},
            source=section,
        )
    if isinstance(section, RectangularSection):
        return SectionProfile(
            kind="rectangular",
            collision_radius_m=max(section.height_y, section.height_z) / 2.0,
            area_m2=section.area,
            dimensions={
                "height_y": section.height_y,
                "height_z": section.height_z,
                "thickness_y": section.thickness_y,
                "thickness_z": section.thickness_z,
            },
            source=section,
        )
    if isinstance(section, IBeamSection):
        h = _dimension(section, "H", "EY")
        b = _dimension(section, "B", "EZ")
        area = float(section.properties.get("A", section.properties.get("area", 0.0)))
        return SectionProfile(
            kind="ibeam",
            collision_radius_m=max(h, b) / 2.0,
            area_m2=area,
            dimensions={
                "H": h,
                "B": b,
                "Tw": float(section.properties.get("Tw", 0.0)),
                "Tf": float(section.properties.get("Tf", 0.0)),
            },
            source=section,
        )
    raise ValueError(f"Unsupported section profile type {type(section).__name__}.")


def collision_radius_for_section(section) -> float:
    return profile_for_section(section).collision_radius_m


def area_for_section(section) -> float:
    return profile_for_section(section).area_m2


def _dimension(section: IBeamSection, primary: str, fallback: str) -> float:
    if primary in section.properties:
        return float(section.properties[primary])
    if fallback in section.properties:
        return float(section.properties[fallback]) * 2.0
    raise ValueError(
        f"I-beam section {section.name!r} is missing dimension {primary!r}. "
        f"Load it from the section catalog or provide {primary!r}/{fallback!r} explicitly."
    )
