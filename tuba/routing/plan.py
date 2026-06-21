"""Serializable route plans that can be evaluated before model mutation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from tuba.model import TubaModel
from tuba.patches import ModelPatch
from tuba.routing.adapter import build_candidate_patch
from tuba.routing.types import (
    PipeRouteCandidate,
    PipeRouteRequest,
    Point3D,
    RouteEndpoint,
    RouteSegment,
    RoutingConstraints,
)


@dataclass
class RoutePlan:
    request_id: str
    start: Point3D
    goal: Point3D
    section: str
    material: str
    points: list[Point3D]
    segments: list[RouteSegment]
    cost: float = 0.0
    cost_breakdown: dict[str, float] = field(default_factory=dict)
    constraints: RoutingConstraints = field(default_factory=RoutingConstraints)
    metadata: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_candidate(cls, candidate: PipeRouteCandidate, request: PipeRouteRequest) -> "RoutePlan":
        return cls(
            request_id=request.id,
            start=request.start.point,
            goal=request.goal.point,
            section=request.section,
            material=request.material,
            points=list(candidate.points),
            segments=list(candidate.segments),
            cost=candidate.cost,
            cost_breakdown=dict(candidate.cost_breakdown),
            constraints=request.constraints,
            metadata=dict(candidate.metadata),
            provenance={"source": "PipeRouteCandidate", "candidate_request_id": candidate.request_id},
        )

    def to_patch(
        self,
        model: TubaModel,
        *,
        add_supports: bool = False,
        support_spacing: float | None = None,
    ) -> ModelPatch:
        request = PipeRouteRequest(
            id=self.request_id,
            start=RouteEndpoint(id="start", point=self.start),
            goal=RouteEndpoint(id="goal", point=self.goal),
            section=self.section,
            material=self.material,
            constraints=self.constraints,
            metadata={"route_plan": self.request_id},
        )
        candidate = PipeRouteCandidate(
            request_id=self.request_id,
            points=list(self.points),
            segments=list(self.segments),
            cost=self.cost,
            cost_breakdown=dict(self.cost_breakdown),
            metadata=dict(self.metadata),
        )
        patch = build_candidate_patch(
            model,
            candidate,
            request,
            add_supports=add_supports,
            support_spacing=support_spacing,
        )
        patch.provenance.update({"route_plan": self.request_id, **self.provenance})
        return patch

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "start": list(self.start),
            "goal": list(self.goal),
            "section": self.section,
            "material": self.material,
            "points": [list(point) for point in self.points],
            "segments": [_segment_to_dict(segment) for segment in self.segments],
            "cost": self.cost,
            "cost_breakdown": dict(self.cost_breakdown),
            "constraints": asdict(self.constraints),
            "metadata": dict(self.metadata),
            "provenance": dict(self.provenance),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RoutePlan":
        return cls(
            request_id=data["request_id"],
            start=_point(data["start"]),
            goal=_point(data["goal"]),
            section=data["section"],
            material=data["material"],
            points=[_point(point) for point in data.get("points", [])],
            segments=[_segment_from_dict(segment) for segment in data.get("segments", [])],
            cost=data.get("cost", 0.0),
            cost_breakdown=dict(data.get("cost_breakdown", {})),
            constraints=RoutingConstraints(**data.get("constraints", {})),
            metadata=dict(data.get("metadata", {})),
            provenance=dict(data.get("provenance", {})),
        )


def _segment_to_dict(segment: RouteSegment) -> dict[str, Any]:
    data: dict[str, Any] = {
        "start": list(segment.start),
        "end": list(segment.end),
        "kind": segment.kind,
    }
    if segment.bend_radius is not None:
        data["bend_radius"] = segment.bend_radius
    if segment.bend_angle is not None:
        data["bend_angle"] = segment.bend_angle
    return data


def _segment_from_dict(data: dict[str, Any]) -> RouteSegment:
    return RouteSegment(
        start=_point(data["start"]),
        end=_point(data["end"]),
        kind=data["kind"],
        bend_radius=data.get("bend_radius"),
        bend_angle=data.get("bend_angle"),
    )


def _point(value) -> Point3D:
    return (float(value[0]), float(value[1]), float(value[2]))
