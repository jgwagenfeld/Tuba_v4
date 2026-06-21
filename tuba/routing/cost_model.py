"""Structured route cost model for pre-mutation route evaluation."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from tuba.model import TubaModel
from tuba.routing.types import PipeRouteCandidate, PipeRouteRequest, RoutingCostWeights


@dataclass(frozen=True)
class CostTerm:
    name: str
    quantity: float
    unit: str
    unit_cost: float
    total: float
    source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "name": self.name,
            "quantity": self.quantity,
            "unit": self.unit,
            "unit_cost": self.unit_cost,
            "total": self.total,
        }
        if self.source is not None:
            data["source"] = self.source
        return data


@dataclass(frozen=True)
class RouteCostBreakdown:
    terms: dict[str, CostTerm] = field(default_factory=dict)

    @property
    def total(self) -> float:
        return sum(term.total for term in self.terms.values())

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "terms": {name: term.to_dict() for name, term in self.terms.items()},
        }

    def to_legacy_dict(self) -> dict[str, float]:
        support_span = self.terms.get("support_span")
        supports = self.terms.get("supports")
        insulation = self.terms.get("insulation")
        insulation_weight = self.terms.get("insulation_weight")
        data = {
            "length": self.terms.get("length", _zero("length")).quantity,
            "bends": self.terms.get("bends", _zero("bends")).quantity,
            "vertical": self.terms.get("vertical", _zero("vertical")).quantity,
            "support_span_max": support_span.quantity if support_span else 0.0,
            "support_span_penalty": support_span.total if support_span else 0.0,
            "support_count": supports.quantity if supports else 0.0,
            "support_cost": supports.total if supports else 0.0,
            "insulation_cost": insulation.total if insulation else 0.0,
            "insulation_weight_penalty": insulation_weight.total if insulation_weight else 0.0,
            "total": self.total,
        }
        return data


@dataclass(frozen=True)
class RouteCostModel:
    weights: RoutingCostWeights = RoutingCostWeights()
    support_unit_cost: float = 0.0
    insulation_mass_weight: float = 0.0

    @classmethod
    def from_routing_weights(
        cls,
        weights: RoutingCostWeights,
        *,
        support_unit_cost: float = 0.0,
        insulation_mass_weight: float = 0.0,
    ) -> "RouteCostModel":
        return cls(
            weights=weights,
            support_unit_cost=support_unit_cost,
            insulation_mass_weight=insulation_mass_weight,
        )

    def evaluate_candidate(
        self,
        model: TubaModel,
        request: PipeRouteRequest,
        candidate: PipeRouteCandidate,
    ) -> RouteCostBreakdown:
        length, spans, vertical = _path_metrics(candidate)
        bends = float(sum(1 for segment in candidate.segments if segment.kind == "bend"))
        support_span_max = max(spans) if spans else 0.0
        support_count = float(candidate.metadata.get("support_count", 0.0))

        terms: dict[str, CostTerm] = {
            "length": CostTerm("length", length, "m", self.weights.length, length * self.weights.length),
            "bends": CostTerm("bends", bends, "count", self.weights.bend, bends * self.weights.bend),
            "vertical": CostTerm("vertical", vertical, "m", self.weights.vertical, vertical * self.weights.vertical),
            "support_span": CostTerm(
                "support_span",
                support_span_max,
                "m",
                self.weights.support_span,
                support_span_max * self.weights.support_span,
            ),
        }

        if support_count:
            terms["supports"] = CostTerm(
                "supports",
                support_count,
                "count",
                self.support_unit_cost,
                support_count * self.support_unit_cost,
            )

        insulation = _route_insulation(model, request)
        if insulation is not None and length > 0.0:
            terms["insulation"] = CostTerm(
                "insulation",
                length,
                "m",
                insulation.cost_per_m,
                length * insulation.cost_per_m,
                source=f"insulation:{insulation.id}",
            )
            insulation_mass = _insulation_mass_per_m(model, request, insulation.thickness_m, insulation.density_kg_m3) * length
            if insulation_mass > 0.0 or self.insulation_mass_weight:
                terms["insulation_weight"] = CostTerm(
                    "insulation_weight",
                    insulation_mass,
                    "kg",
                    self.insulation_mass_weight,
                    insulation_mass * self.insulation_mass_weight,
                    source=f"insulation:{insulation.id}",
                )

        return RouteCostBreakdown(terms=terms)


def _path_metrics(candidate: PipeRouteCandidate) -> tuple[float, list[float], float]:
    length = 0.0
    spans: list[float] = []
    vertical = 0.0
    for a, b in zip(candidate.points, candidate.points[1:]):
        pa = np.asarray(a, dtype=float)
        pb = np.asarray(b, dtype=float)
        span = float(np.linalg.norm(pb - pa))
        length += span
        vertical += abs(float(pb[2] - pa[2]))
        if span > 1e-12:
            spans.append(span)
    return length, spans, vertical


def _route_insulation(model: TubaModel, request: PipeRouteRequest):
    spec_id = request.metadata.get("insulation_spec_id")
    if spec_id is not None:
        return model.specs.get("insulation", {}).get(spec_id)
    return model.get_insulation(f"route:{request.id}")


def _insulation_mass_per_m(model: TubaModel, request: PipeRouteRequest, thickness_m: float, density_kg_m3: float) -> float:
    if thickness_m <= 0.0 or density_kg_m3 <= 0.0:
        return 0.0
    section = model.sections[request.section]
    bare_radius = float(section.OD) / 2.0
    effective_radius = bare_radius + thickness_m
    return math.pi * (effective_radius**2 - bare_radius**2) * density_kg_m3


def _zero(name: str) -> CostTerm:
    return CostTerm(name=name, quantity=0.0, unit="", unit_cost=0.0, total=0.0)
