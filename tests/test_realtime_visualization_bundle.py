import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tuba.visualization import VisualizationScene
from tests.realtime_visualization_fixtures import operating_state_review_fixture


class TestRealtimeVisualizationBundle(unittest.TestCase):
    def test_example_writes_complete_review_scene_bundle(self):
        with TemporaryDirectory() as tmpdir:
            fixture = operating_state_review_fixture(Path(tmpdir))
            scene_payload = json.loads(fixture.bundle.scene_path.read_text(encoding="utf-8"))
            self.assertTrue(fixture.bundle.root.exists())
            self.assertTrue((fixture.bundle.metadata_dir / "object_map.json").exists())
            self.assertTrue((fixture.bundle.geometry_dir / "geometry_assets.json").exists())

        scene = VisualizationScene.from_dict(scene_payload)
        scene.validate()
        kinds = {obj.kind for obj in scene.objects}
        overlay_types = {overlay.data.get("result_type") for overlay in scene.overlays if overlay.kind == "solver_result"}

        self.assertEqual(fixture.expected_counts["operating_clashes"], 1)
        self.assertGreater(fixture.expected_counts["analysis_mesh_elements"], 0)
        self.assertGreater(fixture.expected_counts["scene_geometry_assets"], 0)
        self.assertIn("analysis_mesh_element", kinds)
        self.assertIn("deformed_centerline", kinds)
        self.assertIn("deformed_envelope", kinds)
        self.assertIn("deformed_analysis_mesh_element", kinds)
        self.assertIn("clash_marker", kinds)
        self.assertIn("stress", overlay_types)
        self.assertEqual(scene.issues[0].external_refs["clash_review"]["grouping"]["load_case"], "Hot")


if __name__ == "__main__":
    unittest.main()
