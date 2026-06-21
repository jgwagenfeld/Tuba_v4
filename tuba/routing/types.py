"""Public dataclasses for pipe autorouting."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Optional


Point3D = tuple[float, float, float]
GridIndex = tuple[int, int, int]


@dataclass(frozen=True)
class RouteEndpoint:
    id: str
    point: Point3D
    direction: Optional[Point3D] = None
    min_straight: float = 0.0


@dataclass(frozen=True)
class RoutingGridSpec:
    cell_size: float = 0.25
    bounds_min: Optional[Point3D] = None
    bounds_max: Optional[Point3D] = None
    margin: float = 1.0
    allow_diagonal: bool = False
    max_cells: int = 2_000_000


@dataclass(frozen=True)
class RoutingConstraints:
    clearance: float = 0.05
    insulation_thickness: float = 0.0
    min_bend_radius: Optional[float] = None
    min_straight_between_bends: float = 0.0
    max_bends: Optional[int] = None
    max_length: Optional[float] = None
    slope: Optional[float] = None
    slope_axis: Optional[str] = None
    avoid_existing_pipes: bool = True
    avoid_obstacles: bool = True
    allowed_directions: Optional[tuple[tuple[int, int, int], ...]] = None


@dataclass(frozen=True)
class RoutingCostWeights:
    length: float = 1.0
    bend: float = 5.0
    vertical: float = 1.0
    clearance: float = 2.0
    support_span: float = 0.5
    rack_preference: float = 0.0
    direction_change: float = 0.0


@dataclass(frozen=True)
class PipeRouteRequest:
    id: str
    start: RouteEndpoint
    goal: RouteEndpoint
    section: str
    material: str
    constraints: RoutingConstraints = RoutingConstraints()
    costs: RoutingCostWeights = RoutingCostWeights()
    preferred_waypoints: tuple[Point3D, ...] = ()
    forbidden_zones: tuple[str, ...] = ()
    preferred_zones: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RouteSegment:
    start: Point3D
    end: Point3D
    kind: Literal["straight", "bend"]
    bend_radius: Optional[float] = None
    bend_angle: Optional[float] = None


@dataclass
class PipeRouteCandidate:
    request_id: str
    points: list[Point3D]
    segments: list[RouteSegment]
    cost: float
    cost_breakdown: dict[str, float]
    diagnostics: list[str] = field(default_factory=list)
    is_valid: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipeRouteResult:
    request: PipeRouteRequest
    candidates: list[PipeRouteCandidate]
    selected_index: Optional[int]
    diagnostics: list[str]

    @property
    def selected(self) -> Optional[PipeRouteCandidate]:
        if self.selected_index is None:
            return None
        if self.selected_index < 0 or self.selected_index >= len(self.candidates):
            return None
        return self.candidates[self.selected_index]


@dataclass
class NetworkRouteRequest:
    id: str
    pipe_requests: list[PipeRouteRequest]
    order_strategy: Literal[
        "given",
        "large_bore_first",
        "critical_first",
        "least_flexible_first",
    ] = "given"
    max_reroute_attempts: int = 20


@dataclass
class NetworkRouteResult:
    request: NetworkRouteRequest
    pipe_results: dict[str, PipeRouteResult]
    accepted_candidates: dict[str, PipeRouteCandidate]
    unresolved_conflicts: list[dict[str, Any]]
    diagnostics: list[str]


def route_result_to_dict(result: PipeRouteResult | NetworkRouteResult) -> dict[str, Any]:
    """Convert route results to JSON-serializable primitive containers."""
    return asdict(result)
