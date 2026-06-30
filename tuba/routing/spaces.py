"""Structured routing-space definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from tuba.routing.types import Point3D


ZoneKind = Literal["allowed", "preferred", "forbidden", "reserved"]
RoutingSpacePolicy = Literal["unrestricted", "prefer_allowed", "require_allowed"]

_POINT_TOLERANCE = 1e-9
_ZONE_PRIORITY: dict[ZoneKind, int] = {
    "forbidden": 0,
    "reserved": 1,
    "preferred": 2,
    "allowed": 3,
}


def _validate_point3d(name: str, point: Point3D) -> None:
    if len(point) != 3:
        raise ValueError(f"{name} must be a 3D point")


@dataclass(frozen=True)
class RoutingZone:
    id: str
    kind: ZoneKind
    min_point: Point3D
    max_point: Point3D
    penalty: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_point3d("min_point", self.min_point)
        _validate_point3d("max_point", self.max_point)
        if any(max_coord <= min_coord for min_coord, max_coord in zip(self.min_point, self.max_point)):
            raise ValueError("max_point must be greater than min_point in every coordinate")

    def contains_point(self, point: Point3D) -> bool:
        _validate_point3d("point", point)
        return all(
            min_coord - _POINT_TOLERANCE <= coord <= max_coord + _POINT_TOLERANCE
            for coord, min_coord, max_coord in zip(point, self.min_point, self.max_point)
        )

    @property
    def volume(self) -> float:
        return (
            (self.max_point[0] - self.min_point[0])
            * (self.max_point[1] - self.min_point[1])
            * (self.max_point[2] - self.min_point[2])
        )


@dataclass(frozen=True)
class RoutingSpace:
    id: str
    zones: tuple[RoutingZone, ...] = ()
    policy: RoutingSpacePolicy = "unrestricted"
    metadata: dict[str, Any] = field(default_factory=dict)

    def classify_point(self, point: Point3D) -> RoutingZone | None:
        matching_zones = [zone for zone in self.zones if zone.contains_point(point)]
        if not matching_zones:
            return None
        return min(matching_zones, key=lambda zone: (_ZONE_PRIORITY[zone.kind], zone.volume))

    def point_allowed(self, point: Point3D) -> bool:
        zone = self.classify_point(point)
        if zone is not None and zone.kind in {"forbidden", "reserved"}:
            return False
        if self.policy == "require_allowed":
            return zone is not None and zone.kind in {"allowed", "preferred"}
        return True
