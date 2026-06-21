import importlib.util
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tuba.visualization import VisualizationScene


class TestRealtimeVisualizationBundle(unittest.TestCase):
    def test_example_writes_complete_review_scene_bundle(self):
        module_path = Path(__file__).resolve().parents[1] / "examples" / "realtime_visualization_review.py"
        spec = importlib.util.spec_from_file_location("realtime_visualization_review", module_path)
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        with TemporaryDirectory() as tmpdir:
            summary = module.run_example(output_dir=tmpdir)
            scene_payload = json.loads(Path(summary["scene"]).read_text(encoding="utf-8"))
            self.assertTrue(Path(summary["bundle_root"]).exists())
            self.assertTrue(Path(summary["object_map"]).exists())
            self.assertTrue(Path(summary["geometry_assets"]).exists())

        scene = VisualizationScene.from_dict(scene_payload)
        scene.validate()
        kinds = {obj.kind for obj in scene.objects}
        overlay_types = {overlay.data.get("result_type") for overlay in scene.overlays if overlay.kind == "solver_result"}

        self.assertEqual(summary["operating_clashes"], 1)
        self.assertGreater(summary["counts"]["analysis_mesh_elements"], 0)
        self.assertGreater(summary["counts"]["scene_geometry_assets"], 0)
        self.assertIn("analysis_mesh_element", kinds)
        self.assertIn("deformed_centerline", kinds)
        self.assertIn("deformed_envelope", kinds)
        self.assertIn("deformed_analysis_mesh_element", kinds)
        self.assertIn("clash_marker", kinds)
        self.assertIn("stress", overlay_types)
        self.assertEqual(scene.issues[0].external_refs["clash_review"]["grouping"]["load_case"], "Hot")


if __name__ == "__main__":
    unittest.main()
