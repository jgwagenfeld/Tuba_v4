import unittest
from tempfile import TemporaryDirectory

import numpy as np

from tuba import Model
from tuba.routing.adapter import apply_candidate_to_model
from tuba.routing.postprocess import build_segments, simplify_grid_path, validate_bend_geometry
from tuba.routing.types import (
    PipeRouteCandidate,
    PipeRouteRequest,
    RouteEndpoint,
    RoutingConstraints,
)
from tuba.solver.aster import CodeAsterSolver


class TestRoutePostprocess(unittest.TestCase):
    def test_simplify_grid_path_removes_collinear_points(self):
        points = [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
            (2.0, 1.0, 0.0),
        ]
        self.assertEqual(
            simplify_grid_path(points),
            [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (2.0, 1.0, 0.0)],
        )

    def test_build_segments_marks_direction_changes_as_bends(self):
        segments = build_segments(
            [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (2.0, 2.0, 0.0)],
            RoutingConstraints(min_bend_radius=0.5),
        )
        self.assertEqual([s.kind for s in segments], ["straight", "bend", "straight"])
        self.assertEqual(segments[1].bend_angle, 90.0)

    def test_bend_validation_rejects_insufficient_tangent_length(self):
        diagnostics = validate_bend_geometry(
            [(0.0, 0.0, 0.0), (0.2, 0.0, 0.0), (0.2, 0.2, 0.0)],
            RoutingConstraints(min_bend_radius=0.5),
        )

        self.assertIn("Insufficient straight length", " ".join(diagnostics))


class TestRouteAdapter(unittest.TestCase):
    def test_apply_candidate_to_model(self):
        model = Model(project_name="Adapter")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        model.define_load_case("operating", gravity=True)
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
            cost_breakdown={"length": 4.0, "bends": 1},
        )

        created = apply_candidate_to_model(model, candidate, request)

        self.assertEqual(len(created), 3)
        self.assertEqual([e.type for e in model.elements], ["pipe_straight", "pipe_bend", "pipe_straight"])
        self.assertEqual(len({e.id for e in model.elements}), 3)
        self.assertEqual(model.elements[0].section, "PipeSec")
        self.assertEqual(model.elements[1].bend_radius, 0.5)
        self.assertNotEqual(model.elements[1].n1, model.elements[1].n2)
        self.assertTrue(np.allclose(model.nodes[model.elements[1].n1].coords, (1.5, 0.0, 0.0)))
        self.assertTrue(np.allclose(model.nodes[model.elements[1].n2].coords, (2.0, 0.5, 0.0)))

        with TemporaryDirectory() as tmp:
            CodeAsterSolver(work_dir=tmp).export_study(model, None, tmp)

    def test_build_candidate_patch_does_not_mutate_model(self):
        model = Model(project_name="PatchRoute")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        request = PipeRouteRequest(
            id="P-100",
            start=RouteEndpoint(id="A", point=(0.0, 0.0, 0.0)),
            goal=RouteEndpoint(id="B", point=(2.0, 0.0, 0.0)),
            section="PipeSec",
            material="Steel",
        )
        candidate = PipeRouteCandidate(
            request_id="P-100",
            points=[(0.0, 0.0, 0.0), (2.0, 0.0, 0.0)],
            segments=build_segments([(0.0, 0.0, 0.0), (2.0, 0.0, 0.0)], request.constraints),
            cost=2.0,
            cost_breakdown={"length": 2.0},
        )

        from tuba.routing.adapter import build_candidate_patch

        patch = build_candidate_patch(model, candidate, request)

        self.assertEqual(len(model.nodes), 0)
        self.assertEqual(len(model.elements), 0)
        self.assertGreaterEqual(len(patch.operations), 3)

    def test_apply_candidate_adds_spaced_supports_on_long_straight_route(self):
        model = Model(project_name="SupportedRoute")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        request = PipeRouteRequest(
            id="P-200",
            start=RouteEndpoint(id="A", point=(0.0, 0.0, 0.0)),
            goal=RouteEndpoint(id="B", point=(10.0, 0.0, 0.0)),
            section="PipeSec",
            material="Steel",
        )
        points = [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0)]
        candidate = PipeRouteCandidate(
            request_id="P-200",
            points=points,
            segments=build_segments(points, request.constraints),
            cost=10.0,
            cost_breakdown={"length": 10.0},
        )

        apply_candidate_to_model(model, candidate, request, add_supports=True, support_spacing=2.5)

        support_coords = [model.nodes[support.node].coords for support in model.supports]
        self.assertEqual(len(model.supports), 3)
        self.assertEqual(len(model.elements), 4)
        self.assertTrue(any(np.allclose(coord, (2.5, 0.0, 0.0)) for coord in support_coords))
        self.assertTrue(any(np.allclose(coord, (5.0, 0.0, 0.0)) for coord in support_coords))
        self.assertTrue(any(np.allclose(coord, (7.5, 0.0, 0.0)) for coord in support_coords))

    def test_apply_candidate_rolls_back_on_invalid_bend(self):
        model = Model(project_name="RollbackRoute")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        request = PipeRouteRequest(
            id="P-100",
            start=RouteEndpoint(id="A", point=(0.0, 0.0, 0.0)),
            goal=RouteEndpoint(id="B", point=(0.2, 0.2, 0.0)),
            section="PipeSec",
            material="Steel",
            constraints=RoutingConstraints(min_bend_radius=1.0),
        )
        points = [(0.0, 0.0, 0.0), (0.2, 0.0, 0.0), (0.2, 0.2, 0.0)]
        candidate = PipeRouteCandidate(
            request_id="P-100",
            points=points,
            segments=build_segments(points, request.constraints),
            cost=0.4,
            cost_breakdown={"length": 0.4, "bends": 1},
        )

        with self.assertRaises(ValueError):
            apply_candidate_to_model(model, candidate, request)

        self.assertEqual(len(model.nodes), 0)
        self.assertEqual(len(model.elements), 0)


if __name__ == "__main__":
    unittest.main()
