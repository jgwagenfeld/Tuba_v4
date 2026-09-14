import json
import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from tuba.visualization.scene import VisualizationScene
from tests.realtime_visualization_fixtures import operating_state_review_fixture


class TestRealtimeVisualizationFixture(unittest.TestCase):
    def test_fixture_contains_model_mesh_results_states_and_operating_clash(self):
        with TemporaryDirectory() as tmpdir:
            fixture = operating_state_review_fixture(Path(tmpdir))

        self.assertEqual(fixture.model.project_name, "RealtimeVisualizationFixture")
        self.assertEqual(fixture.analysis_mesh.solver_name, "Code_Aster")
        self.assertGreaterEqual(fixture.expected_counts["analysis_mesh_nodes"], 2)
        self.assertGreaterEqual(fixture.expected_counts["analysis_mesh_elements"], 1)
        self.assertEqual(fixture.cold_state.state_type, "cold")
        self.assertEqual(fixture.operating_state.state_type, "operating")
        self.assertEqual(fixture.visual_state.purpose, "visualization")
        self.assertEqual(len(fixture.operating_clashes), 1)
        self.assertEqual(fixture.operating_clashes[0].severity, "operating_only_hard")
        self.assertEqual(fixture.expected_counts["operating_clashes"], 1)

    def test_fixture_writes_browser_loadable_scene_bundle_with_expected_counts(self):
        with TemporaryDirectory() as tmpdir:
            fixture = operating_state_review_fixture(Path(tmpdir))
            scene_payload = json.loads(fixture.bundle.scene_path.read_text(encoding="utf-8"))

            scene = VisualizationScene.from_dict(scene_payload)
            scene.validate()

            self.assertEqual(scene.scene_id, "scene:realtime_visualization_fixture")
            self.assertEqual(len(scene.objects), fixture.expected_counts["scene_objects"])
            self.assertEqual(len(scene.geometry_assets), fixture.expected_counts["scene_geometry_assets"])
            self.assertEqual(len(scene.overlays), fixture.expected_counts["scene_overlays"])
            self.assertEqual(len(scene.issues), fixture.expected_counts["scene_issues"])
            self.assertTrue((fixture.bundle.metadata_dir / "object_map.json").exists())
            self.assertTrue((fixture.bundle.geometry_dir / "geometry_assets.json").exists())


if __name__ == "__main__":
    unittest.main()
