import unittest

import numpy as np

from tuba import Model
from tuba.routing.types import (
    PipeRouteCandidate,
    PipeRouteRequest,
    PipeRouteResult,
    RouteEndpoint,
    RouteSegment,
    RoutingConstraints,
)
from tuba.routing.postprocess import build_segments
from tuba.routing.adapter import apply_candidate_to_model, candidate_render_points
from tuba.routing.visualization import _candidate_render_points, _element_render_points, build_route_plotter


class TestRoutingVisualization(unittest.TestCase):
    def test_visualization_uses_adapter_owned_candidate_render_geometry(self):
        self.assertIs(_candidate_render_points, candidate_render_points)

        model = Model(project_name="RoutingVisualizationAdapterGeometry")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        request = PipeRouteRequest(
            id="P-100",
            start=RouteEndpoint("A", (0.0, 0.0, 0.0)),
            goal=RouteEndpoint("B", (2.0, 2.0, 0.0)),
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
        )

        render_points = _candidate_render_points(model, request, candidate)

        self.assertNotIn((2.0, 0.0, 0.0), render_points)
        self.assertTrue(any(np.allclose(point, (1.5, 0.0, 0.0)) for point in render_points))

    def test_candidate_render_points_replace_corner_with_bend_arc(self):
        model = Model(project_name="RoutingVisualizationBends")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        request = PipeRouteRequest(
            id="P-100",
            start=RouteEndpoint("A", (0.0, 0.0, 0.0)),
            goal=RouteEndpoint("B", (2.0, 2.0, 0.0)),
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
        )

        render_points = _candidate_render_points(model, request, candidate)

        self.assertNotIn((2.0, 0.0, 0.0), render_points)
        self.assertTrue(any(np.allclose(point, (1.5, 0.0, 0.0)) for point in render_points))
        self.assertTrue(any(np.allclose(point, (2.0, 0.5, 0.0)) for point in render_points))
        self.assertGreater(len(render_points), len(points))

    def test_candidate_render_points_reject_missing_bend_radius(self):
        model = Model(project_name="RoutingVisualizationRequiresRadius")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        request = PipeRouteRequest(
            id="P-100",
            start=RouteEndpoint("A", (0.0, 0.0, 0.0)),
            goal=RouteEndpoint("B", (2.0, 2.0, 0.0)),
            section="PipeSec",
            material="Steel",
        )
        points = [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (2.0, 2.0, 0.0)]
        candidate = PipeRouteCandidate(
            request_id="P-100",
            points=points,
            segments=build_segments(points, request.constraints),
            cost=4.0,
            cost_breakdown={"length": 4.0, "bends": 1.0},
        )

        with self.assertRaisesRegex(ValueError, "explicit bend radius"):
            _candidate_render_points(model, request, candidate)

    def test_model_pipe_bend_render_points_use_bend_geometry(self):
        model = Model(project_name="RoutingVisualizationAppliedBends")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        request = PipeRouteRequest(
            id="P-100",
            start=RouteEndpoint("A", (0.0, 0.0, 0.0)),
            goal=RouteEndpoint("B", (2.0, 2.0, 0.0)),
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
        )
        apply_candidate_to_model(model, candidate, request)
        bend = next(element for element in model.elements if element.type == "pipe_bend")

        render_points = _element_render_points(model, bend)

        self.assertGreater(len(render_points), 2)
        self.assertFalse(np.allclose(render_points[1], model.nodes[bend.n2].coords))

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
            constraints=RoutingConstraints(min_bend_radius=0.2),
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
            constraints=RoutingConstraints(min_bend_radius=0.2),
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

    def test_build_route_plotter_rejects_candidate_without_request_section(self):
        model = Model(project_name="RoutingVisualizationNoRequest")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        candidate = PipeRouteCandidate(
            request_id="P-100",
            points=[(0.0, 0.0, 0.0), (2.0, 0.0, 0.0)],
            segments=[RouteSegment((0.0, 0.0, 0.0), (2.0, 0.0, 0.0), "straight")],
            cost=2.0,
            cost_breakdown={"length": 2.0},
        )

        with self.assertRaisesRegex(ValueError, "without a PipeRouteRequest section"):
            build_route_plotter(model, candidates=[candidate], off_screen=True)


if __name__ == "__main__":
    unittest.main()
