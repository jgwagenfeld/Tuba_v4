import unittest

from tuba import Model
from tuba.routing.types import (
    PipeRouteCandidate,
    PipeRouteRequest,
    PipeRouteResult,
    RouteEndpoint,
    RouteSegment,
)
from tuba.routing.visualization import build_route_plotter


class TestRoutingVisualization(unittest.TestCase):
    def test_build_route_plotter_adds_scene_actors(self):
        model = Model(project_name="RoutingVisualization")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        model.add_obstacle(
            id="box",
            type="cuboid",
            min_point=[1.0, -0.5, -0.5],
            max_point=[2.0, 0.5, 0.5],
        )
        request = PipeRouteRequest(
            id="P-100",
            start=RouteEndpoint("A", (0.0, 0.0, 0.0)),
            goal=RouteEndpoint("B", (3.0, 0.0, 0.0)),
            section="PipeSec",
            material="Steel",
        )
        candidate = PipeRouteCandidate(
            request_id="P-100",
            points=[(0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (3.0, 1.0, 0.0), (3.0, 0.0, 0.0)],
            segments=[
                RouteSegment((0.0, 0.0, 0.0), (0.0, 1.0, 0.0), "straight"),
                RouteSegment((0.0, 1.0, 0.0), (0.0, 1.0, 0.0), "bend"),
                RouteSegment((0.0, 1.0, 0.0), (3.0, 1.0, 0.0), "straight"),
                RouteSegment((3.0, 1.0, 0.0), (3.0, 1.0, 0.0), "bend"),
                RouteSegment((3.0, 1.0, 0.0), (3.0, 0.0, 0.0), "straight"),
            ],
            cost=10.0,
            cost_breakdown={"length": 5.0, "bends": 2.0},
        )
        result = PipeRouteResult(request=request, candidates=[candidate], selected_index=0, diagnostics=[])

        plotter = build_route_plotter(model, request=request, result=result, off_screen=True)
        try:
            self.assertGreaterEqual(len(plotter.actors), 4)
        finally:
            plotter.close()


if __name__ == "__main__":
    unittest.main()
