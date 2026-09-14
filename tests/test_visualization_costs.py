import unittest

from tuba import Model
from tuba.quantities import quantity_takeoff
from tuba.visualization import SceneBuildOptions, build_visualization_scene


class TestVisualizationCosts(unittest.TestCase):
    def _model(self):
        model = Model(project_name="CostReview")
        model.add_material("Steel", E=2.0e11, nu=0.3, rho=7850.0)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([2.0, 0.0, 0.0])
        n2 = model.add_node([5.0, 0.0, 0.0])
        e0 = model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")
        e1 = model.add_element(id="pipe_1", type="pipe_straight", n1=n1, n2=n2, section="PipeSec", material="Steel")
        model.groups["line_A"] = {"name": "line_A", "elements": [e0.id, e1.id]}
        model.add_insulation_spec("mw_50", material="mineral_wool", thickness_m=0.05, density_kg_m3=100.0, cost_per_m=20.0)
        model.assign_insulation("group:line_A", "mw_50")
        return model

    def test_cost_heatmap_overlay_matches_quantity_takeoff_records(self):
        model = self._model()

        scene = build_visualization_scene(
            model,
            options=SceneBuildOptions(include_cost_overlays=True, cost_metric="insulation_cost"),
            scene_id="scene_cost_review",
        )
        scene.validate()

        heatmap = next(overlay for overlay in scene.overlays if overlay.kind == "cost_heatmap")
        self.assertEqual(heatmap.data["metric"], "insulation_cost")
        self.assertEqual(heatmap.object_ids, ["object:element:pipe_0", "object:element:pipe_1"])
        self.assertEqual(
            heatmap.data["values"],
            {"object:element:pipe_0": 40.0, "object:element:pipe_1": 60.0},
        )
        self.assertEqual(heatmap.data["range"], {"min": 40.0, "max": 60.0})

    def test_quantity_summary_overlay_matches_takeoff_totals_and_groups(self):
        model = self._model()
        takeoff = quantity_takeoff(model)

        scene = build_visualization_scene(
            model,
            options=SceneBuildOptions(include_cost_overlays=True, cost_metric="insulation_cost"),
            scene_id="scene_cost_review",
        )
        summary = next(overlay for overlay in scene.overlays if overlay.kind == "quantity_summary")

        self.assertEqual(summary.data["totals"], takeoff.totals)
        self.assertEqual(summary.data["groups"], takeoff.groups)
        self.assertEqual(summary.data["record_count"], 2)


if __name__ == "__main__":
    unittest.main()
