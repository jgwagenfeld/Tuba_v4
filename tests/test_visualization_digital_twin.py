import unittest

from tuba import Model
from tuba.visualization import build_visualization_scene


class TestVisualizationDigitalTwin(unittest.TestCase):
    def _model(self):
        model = Model(project_name="TwinReview")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 0.0, 0.0])
        model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")
        return model

    def test_runtime_state_overlay_contains_timestamped_object_states(self):
        scene = build_visualization_scene(
            self._model(),
            runtime_states=[
                {
                    "timestamp": "2026-06-20T10:00:00Z",
                    "states": {"element:pipe_0": {"status": "active", "temperature_c": 80.0}},
                },
                {
                    "timestamp": "2026-06-20T11:00:00Z",
                    "states": {"element:pipe_0": {"status": "alarm", "temperature_c": 120.0}},
                },
            ],
            scene_id="scene_twin",
        )
        scene.validate()

        overlay = next(overlay for overlay in scene.overlays if overlay.kind == "runtime_state")
        self.assertEqual(overlay.object_ids, ["object:element:pipe_0"])
        self.assertEqual(overlay.data["timestamps"], ["2026-06-20T10:00:00Z", "2026-06-20T11:00:00Z"])
        self.assertEqual(overlay.data["states"]["2026-06-20T11:00:00Z"]["object:element:pipe_0"]["status"], "alarm")


if __name__ == "__main__":
    unittest.main()
