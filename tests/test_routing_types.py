import json
import unittest

from tuba.routing.types import (
    PipeRouteCandidate,
    PipeRouteRequest,
    RouteEndpoint,
    RouteSegment,
    RoutingConstraints,
    route_result_to_dict,
    PipeRouteResult,
)


class TestRoutingTypes(unittest.TestCase):
    def test_route_result_serializes_to_plain_json(self):
        request = PipeRouteRequest(
            id="P-100",
            start=RouteEndpoint(id="A", point=(0.0, 0.0, 0.0)),
            goal=RouteEndpoint(id="B", point=(2.0, 0.0, 0.0)),
            section="PipeSec",
            material="Steel",
            constraints=RoutingConstraints(clearance=0.1),
        )
        candidate = PipeRouteCandidate(
            request_id="P-100",
            points=[(0.0, 0.0, 0.0), (2.0, 0.0, 0.0)],
            segments=[
                RouteSegment(
                    start=(0.0, 0.0, 0.0),
                    end=(2.0, 0.0, 0.0),
                    kind="straight",
                )
            ],
            cost=2.0,
            cost_breakdown={"length": 2.0},
        )
        result = PipeRouteResult(
            request=request,
            candidates=[candidate],
            selected_index=0,
            diagnostics=[],
        )

        data = route_result_to_dict(result)
        json.dumps(data)
        self.assertEqual(data["request"]["id"], "P-100")
        self.assertEqual(data["selected_index"], 0)
        self.assertEqual(data["candidates"][0]["points"][1], (2.0, 0.0, 0.0))
        self.assertIs(result.selected, candidate)


if __name__ == "__main__":
    unittest.main()
