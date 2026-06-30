"""Thermal requirements and solver acceptance criteria for route candidates."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


LoopFamily = Literal["u_loop", "z_loop", "offset_loop"]


@dataclass(frozen=True)
class ThermalRouteRequirement:
    design_temperature_c: float
    reference_temperature_c: float
    line_length_m: float
    thermal_expansion_coefficient: float
    requires_expansion_loop: bool = True
    preferred_loop_families: tuple[LoopFamily, ...] = ("u_loop", "z_loop")
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def delta_t_c(self) -> float:
        return float(self.design_temperature_c - self.reference_temperature_c)


@dataclass(frozen=True)
class ExpansionLoopSpec:
    family: LoopFamily
    width_m: float
    depth_m: float
    plane: Literal["xy", "xz", "yz"] = "xy"
    min_clearance_m: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.width_m <= 0.0 or self.depth_m <= 0.0:
            raise ValueError("Expansion loop width_m and depth_m must be positive.")


@dataclass(frozen=True)
class SolverAcceptanceCriteria:
    max_expansion_ratio: float = 1.0
    max_sustained_ratio: float = 1.0
    max_anchor_reaction_n: float = 50_000.0
    max_nozzle_reaction_n: float = 10_000.0
    max_operating_displacement_m: float = 0.25
    max_operating_clearance_violation_m: float = 0.0

    @classmethod
    def hot_line_defaults(cls) -> "SolverAcceptanceCriteria":
        return cls()


def estimate_free_expansion(requirement: ThermalRouteRequirement) -> float:
    return (
        float(requirement.thermal_expansion_coefficient)
        * float(requirement.delta_t_c)
        * float(requirement.line_length_m)
    )
