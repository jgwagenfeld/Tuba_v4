import unittest

from tuba import Model
from tuba.routing.cost import score_candidate
from tuba.routing.cost_model import RouteCostModel
from tuba.routing.types import (
    PipeRouteCandidate,
    PipeRouteRequest,
    RouteEndpoint,
    RouteSegment,
    RoutingCostWeights,
)


class TestRouteCostModel(unittest.TestCase):
    def _model(self):
        model = Model(project_name="RouteCost")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        return model

    def _request(self, **kwargs):
        return PipeRouteRequest(
            id="P-100",
            start=RouteEndpoint(id="A", point=(0.0, 0.0, 0.0)),
            goal=RouteEndpoint(id="B", point=(4.0, 0.0, 0.0)),
            section="PipeSec",
            material="Steel",
            **kwargs,
        )

    def test_route_cost_model_matches_legacy_weight_terms(self):
        model = self._model()
        request = self._request(costs=RoutingCostWeights(length=2.0, bend=5.0, vertical=3.0, support_span=0.5))
        candidate = PipeRouteCandidate(
            request_id="P-100",
            points=[(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (2.0, 0.0, 1.0)],
            segments=[
                RouteSegment((0.0, 0.0, 0.0), (2.0, 0.0, 0.0), "straight"),
                RouteSegment((2.0, 0.0, 0.0), (2.0, 0.0, 1.0), "bend"),
            ],
            cost=0.0,
            cost_breakdown={},
        )

        breakdown = RouteCostModel.from_routing_weights(request.costs).evaluate_candidate(model, request, candidate)
        score_candidate(candidate, model, request)

        self.assertAlmostEqual(breakdown.total, candidate.cost)
        self.assertEqual(breakdown.terms["length"].quantity, 3.0)
        self.assertEqual(breakdown.terms["bends"].quantity, 1.0)
        self.assertEqual(candidate.cost_breakdown["support_span_max"], 2.0)

    def test_insulation_spec_contributes_cost_and_weight_penalty(self):
        model = self._model()
        model.add_insulation_spec(
            id="mw_50",
            material="mineral_wool",
            thickness_m=0.05,
            density_kg_m3=100.0,
            cost_per_m=20.0,
        )
        model.assign_insulation("route:P-100", "mw_50")
        request = self._request(costs=RoutingCostWeights(length=1.0, bend=0.0, support_span=0.0))
        candidate = PipeRouteCandidate(
            request_id="P-100",
            points=[(0.0, 0.0, 0.0), (4.0, 0.0, 0.0)],
            segments=[RouteSegment((0.0, 0.0, 0.0), (4.0, 0.0, 0.0), "straight")],
            cost=0.0,
            cost_breakdown={},
        )

        breakdown = RouteCostModel.from_routing_weights(
            request.costs,
            insulation_mass_weight=2.0,
        ).evaluate_candidate(model, request, candidate)

        self.assertAlmostEqual(breakdown.terms["insulation"].quantity, 4.0)
        self.assertAlmostEqual(breakdown.terms["insulation"].total, 80.0)
        self.assertGreater(breakdown.terms["insulation_weight"].quantity, 0.0)
        self.assertGreater(breakdown.total, 84.0)

    def test_support_count_tradeoff_can_be_costed_before_model_mutation(self):
        model = self._model()
        request = self._request(costs=RoutingCostWeights(length=1.0, bend=0.0, support_span=0.0))
        candidate = PipeRouteCandidate(
            request_id="P-100",
            points=[(0.0, 0.0, 0.0), (4.0, 0.0, 0.0)],
            segments=[RouteSegment((0.0, 0.0, 0.0), (4.0, 0.0, 0.0), "straight")],
            cost=0.0,
            cost_breakdown={},
            metadata={"support_count": 2},
        )

        breakdown = RouteCostModel.from_routing_weights(
            request.costs,
            support_unit_cost=25.0,
        ).evaluate_candidate(model, request, candidate)

        self.assertEqual(breakdown.terms["supports"].quantity, 2.0)
        self.assertEqual(breakdown.terms["supports"].total, 50.0)
        self.assertAlmostEqual(breakdown.total, 54.0)


if __name__ == "__main__":
    unittest.main()
