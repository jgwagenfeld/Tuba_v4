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

    def test_build_route_plotter_adds_reserved_envelope_actor(self):
        model = Model(project_name="RoutingVisualizationEnvelope")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        request = PipeRouteRequest(
            id="HOT-100",
            start=RouteEndpoint("A", (0.0, 0.0, 0.0)),
            goal=RouteEndpoint("B", (3.0, 0.0, 0.0)),
            section="PipeSec",
            material="Steel",
        )
        candidate = PipeRouteCandidate(
            request_id="HOT-100",
            points=[(0.0, 0.0, 0.0), (1.5, 1.0, 0.0), (3.0, 0.0, 0.0)],
            segments=[
                RouteSegment((0.0, 0.0, 0.0), (1.5, 1.0, 0.0), "straight"),
                RouteSegment((1.5, 1.0, 0.0), (3.0, 0.0, 0.0), "straight"),
            ],
            cost=5.0,
            cost_breakdown={"length": 4.0, "bends": 2.0},
            metadata={
                "route_family": "u_loop",
                "reserved_envelope": {
                    "min_point": (1.0, -0.2, -0.2),
                    "max_point": (2.0, 1.2, 0.2),
                },
            },
        )
        result = PipeRouteResult(request=request, candidates=[candidate], selected_index=0, diagnostics=[])

        without_envelope = build_route_plotter(
            model,
            request=request,
            result=result,
            show_reserved_envelopes=False,
            off_screen=True,
        )
        with_envelope = build_route_plotter(model, request=request, result=result, off_screen=True)
        try:
            self.assertGreater(len(with_envelope.actors), len(without_envelope.actors))
        finally:
            without_envelope.close()
            with_envelope.close()


if __name__ == "__main__":
    unittest.main()
