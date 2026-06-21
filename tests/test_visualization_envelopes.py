import unittest

from tuba import Model
from tuba.visualization import SceneBuildOptions, build_visualization_scene


class TestVisualizationEnvelopes(unittest.TestCase):
    def _insulated_model(self):
        model = Model(project_name="EnvelopeReview")
        model.add_material("Steel", E=2.0e11, nu=0.3, rho=7850.0)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([2.0, 0.0, 0.0])
        elem = model.add_element(
            id="pipe_0",
            type="pipe_straight",
            n1=n0,
            n2=n1,
            section="PipeSec",
            material="Steel",
        )
        model.add_insulation_spec("mw_50", material="mineral_wool", thickness_m=0.05, density_kg_m3=100.0)
        model.assign_insulation(f"element:{elem.id}", "mw_50")
        return model

    def test_build_scene_adds_selectable_physical_envelope_objects(self):
        scene = build_visualization_scene(
            self._insulated_model(),
            options=SceneBuildOptions(include_physical_envelopes=True, clearance_m=0.05),
            scene_id="scene_envelopes",
        )
        scene.validate()

        envelope_objects = [obj for obj in scene.objects if obj.kind == "physical_envelope"]
        envelope_types = {obj.metadata["envelope_type"] for obj in envelope_objects}
        self.assertEqual(envelope_types, {"bare_pipe", "insulation", "clearance", "wind"})

        insulation = next(obj for obj in envelope_objects if obj.metadata["envelope_type"] == "insulation")
        self.assertEqual(insulation.metadata["source"]["insulation_id"], "mw_50")
        self.assertAlmostEqual(insulation.metadata["radius_m"], 0.10)

        clearance = next(obj for obj in envelope_objects if obj.metadata["envelope_type"] == "clearance")
        self.assertAlmostEqual(clearance.metadata["radius_m"], 0.15)
        self.assertEqual(clearance.metadata["source"]["clearance_m"], 0.05)

        asset = next(asset for asset in scene.geometry_assets if asset.id == insulation.geometry_asset_id)
        self.assertEqual(asset.format, "tube_envelope")
        self.assertEqual(asset.generation_config["points"], [[0.0, 0.0, 0.0], [2.0, 0.0, 0.0]])
        self.assertAlmostEqual(asset.generation_config["radius_m"], 0.10)

    def test_physical_envelope_overlays_are_independently_toggleable(self):
        scene = build_visualization_scene(
            self._insulated_model(),
            options=SceneBuildOptions(include_physical_envelopes=True, clearance_m=0.05),
            scene_id="scene_envelopes",
        )

        overlays = [overlay for overlay in scene.overlays if overlay.kind == "physical_envelope"]
        self.assertEqual({overlay.data["envelope_type"] for overlay in overlays}, {"bare_pipe", "insulation", "clearance", "wind"})
        self.assertEqual(len({tuple(overlay.object_ids) for overlay in overlays}), 4)


if __name__ == "__main__":
    unittest.main()
