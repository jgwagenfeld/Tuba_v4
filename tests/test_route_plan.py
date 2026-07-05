import json
import unittest

from tuba import Model
from tuba.patches import ModelTransaction
from tuba.routing.plan import RoutePlan
from tuba.routing.postprocess import build_segments
from tuba.routing.types import PipeRouteCandidate, PipeRouteRequest, RouteEndpoint, RoutingConstraints


class TestRoutePlan(unittest.TestCase):
    def _request_and_candidate(self):
        request = PipeRouteRequest(
            id="P-100",
            start=RouteEndpoint(id="A", point=(0.0, 0.0, 0.0)),
            goal=RouteEndpoint(id="B", point=(2.0, 2.0, 0.0)),
            section="PipeSec",
            material="Steel",
            constraints=RoutingConstraints(min_bend_radius=0.5),
        )
        points = [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (2.0, 2.0, 0.0)]
        candidate = PipeRouteCandidate(
            request_id="P-100",
            points=points,
            segments=build_segments(points, request.constraints),
            cost=4.0,
            cost_breakdown={"length": 4.0, "bends": 1.0},
            metadata={"rank": 0},
        )
        return request, candidate

    def _model(self):
        model = Model(project_name="RoutePlan")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        return model

    def test_route_plan_roundtrips_without_mutating_model(self):
        request, candidate = self._request_and_candidate()
        model = self._model()
        before = model.to_dict()

        plan = RoutePlan.from_candidate(candidate, request)
        data = plan.to_dict()
        json.dumps(data)
        restored = RoutePlan.from_dict(data)
        patch = restored.to_patch(model)

        self.assertEqual(model.to_dict(), before)
        self.assertEqual(restored.request_id, "P-100")
        self.assertEqual(restored.section, "PipeSec")
        self.assertEqual(restored.cost_breakdown["bends"], 1.0)
        self.assertGreaterEqual(len(patch.operations), 5)

    def test_route_plan_patch_applies_same_route_geometry(self):
        request, candidate = self._request_and_candidate()
        model = self._model()

        plan = RoutePlan.from_candidate(candidate, request)
        result = ModelTransaction(model).apply(plan.to_patch(model))

        self.assertEqual(len(result.element_ids), 3)
        self.assertEqual([elem.type for elem in model.elements], ["pipe_straight", "pipe_bend", "pipe_straight"])
        self.assertEqual(model.elements[1].bend_radius, 0.5)
        self.assertEqual([elem.route_id for elem in model.elements], ["P-100", "P-100", "P-100"])
        self.assertAlmostEqual(model.elements[0].station_start, 0.0)
        self.assertIsNotNone(model.elements[2].station_end)

    def test_empty_route_plan_serializes_to_empty_patch(self):
        request = PipeRouteRequest(
            id="P-empty",
            start=RouteEndpoint(id="A", point=(0.0, 0.0, 0.0)),
            goal=RouteEndpoint(id="B", point=(0.0, 0.0, 0.0)),
            section="PipeSec",
            material="Steel",
        )
        candidate = PipeRouteCandidate(
            request_id="P-empty",
            points=[],
            segments=[],
            cost=0.0,
            cost_breakdown={},
        )
        model = self._model()

        plan = RoutePlan.from_candidate(candidate, request)
        patch = plan.to_patch(model)

        self.assertEqual(patch.operations, [])
        self.assertEqual(patch.provenance["request_id"], "P-empty")


if __name__ == "__main__":
    unittest.main()
