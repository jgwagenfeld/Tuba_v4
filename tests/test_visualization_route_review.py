import unittest

from tuba import Model
from tuba.routing.types import (
    PipeRouteCandidate,
    PipeRouteRequest,
    PipeRouteResult,
    RouteEndpoint,
    RouteSegment,
)
from tuba.visualization import SceneBuildOptions, build_visualization_scene


class TestVisualizationRouteReview(unittest.TestCase):
    def _model_and_result(self):
        model = Model(project_name="RouteReview")
        model.add_material("Steel", E=2.0e11, nu=0.3, rho=7850.0)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        request = PipeRouteRequest(
            id="P-100",
            start=RouteEndpoint("A", (0.0, 0.0, 0.0)),
            goal=RouteEndpoint("B", (4.0, 0.0, 0.0)),
            section="PipeSec",
            material="Steel",
        )
        selected = PipeRouteCandidate(
            request_id="P-100",
            points=[(0.0, 0.0, 0.0), (4.0, 0.0, 0.0)],
            segments=[RouteSegment((0.0, 0.0, 0.0), (4.0, 0.0, 0.0), "straight")],
            cost=4.0,
            cost_breakdown={"length": 4.0, "bends": 0.0},
        )
        invalid = PipeRouteCandidate(
            request_id="P-100",
            points=[(0.0, 0.0, 0.0), (2.0, 1.0, 0.0), (4.0, 0.0, 0.0)],
            segments=[
                RouteSegment((0.0, 0.0, 0.0), (2.0, 1.0, 0.0), "straight"),
                RouteSegment((2.0, 1.0, 0.0), (4.0, 0.0, 0.0), "straight"),
            ],
            cost=7.5,
            cost_breakdown={"length": 4.5, "bends": 2.0, "clearance": 1.0},
            diagnostics=["clearance violation"],
            is_valid=False,
        )
        return model, PipeRouteResult(request=request, candidates=[selected, invalid], selected_index=0, diagnostics=[])

    def test_build_scene_adds_route_candidate_objects_and_overlay(self):
        model, result = self._model_and_result()

        scene = build_visualization_scene(
            model,
            options=SceneBuildOptions(include_elements=False, include_supports=False, include_obstacles=False),
            route_results=[result],
            scene_id="scene_route_review",
        )
        scene.validate()

        route_objects = [obj for obj in scene.objects if obj.kind == "route_candidate"]
        self.assertEqual(len(route_objects), 2)
        self.assertEqual(route_objects[0].entity_ref.kind, "route")
        self.assertTrue(route_objects[0].metadata["selected"])
        self.assertFalse(route_objects[1].metadata["is_valid"])
        self.assertEqual(route_objects[1].metadata["diagnostics"], ["clearance violation"])

        overlay = next(overlay for overlay in scene.overlays if overlay.kind == "route_alternatives")
        self.assertEqual(overlay.data["selected_candidate_id"], "route:P-100:candidate:0")
        self.assertEqual(set(overlay.object_ids), {obj.id for obj in route_objects})

    def test_build_scene_adds_route_review_comparison_data(self):
        model, result = self._model_and_result()

        scene = build_visualization_scene(model, route_results=[result], scene_id="scene_route_review")
        review = scene.route_reviews[0]

        self.assertEqual(review.request_id, "P-100")
        self.assertEqual(review.selected_candidate_id, "route:P-100:candidate:0")
        self.assertEqual(review.candidates[0]["cost"], 4.0)
        self.assertEqual(review.candidates[1]["diagnostics"], ["clearance violation"])
        self.assertEqual(review.cost_terms[0]["name"], "length")
        self.assertEqual(review.cost_terms[0]["total"], 4.0)

    def test_route_candidate_geometry_assets_preserve_points_for_viewer(self):
        model, result = self._model_and_result()

        scene = build_visualization_scene(model, route_results=[result], scene_id="scene_route_review")
        route_asset = next(asset for asset in scene.geometry_assets if asset.id == "geometry:route:P-100:candidate:0")

        self.assertEqual(route_asset.format, "polyline")
        self.assertEqual(route_asset.object_ids, ["object:route:P-100:candidate:0"])
        self.assertEqual(route_asset.generation_config["points"], [[0.0, 0.0, 0.0], [4.0, 0.0, 0.0]])


if __name__ == "__main__":
    unittest.main()
