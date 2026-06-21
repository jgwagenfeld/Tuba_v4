"""Structured clash result types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from tuba.refs import EntityRef


ClashSeverity = Literal[
    "hard",
    "clearance",
    "cold_hard",
    "cold_clearance",
    "operating_hard",
    "operating_clearance",
    "operating_only_hard",
    "operating_only_clearance",
    "resolved_in_operating",
]


@dataclass(frozen=True)
class ClashResult:
    left: EntityRef
    right: EntityRef
    severity: ClashSeverity
    distance_m: float
    penetration_m: float
    location: tuple[float, float, float] | None = None
    diagnostics: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "left": self.left.to_dict(),
            "right": self.right.to_dict(),
            "severity": self.severity,
            "distance_m": self.distance_m,
            "penetration_m": self.penetration_m,
            "diagnostics": list(self.diagnostics),
        }
        if self.location is not None:
            data["location"] = list(self.location)
        if self.metadata:
            data["metadata"] = dict(self.metadata)
        return data
