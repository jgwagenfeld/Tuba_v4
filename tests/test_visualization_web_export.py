import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tuba import Model
from tuba.visualization import SceneBuildOptions, VisualizationScene, build_visualization_scene, write_scene_bundle


class TestVisualizationWebExport(unittest.TestCase):
    def _scene(self) -> VisualizationScene:
        model = Model(project_name="BundleExport")
        model.add_material("Steel", E=2.0e11, nu=0.3, rho=7850.0)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 0.0, 0.0])
        model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")
        return build_visualization_scene(
            model,
            options=SceneBuildOptions(include_supports=False, include_obstacles=False),
            scene_id="scene_bundle",
            created_at="2026-06-20T12:00:00Z",
        )

    def test_write_scene_bundle_creates_browser_loadable_layout(self):
        scene = self._scene()

        with TemporaryDirectory() as tmpdir:
            bundle = write_scene_bundle(scene, Path(tmpdir) / "review_scene")

            self.assertTrue(bundle.scene_path.exists())
            self.assertTrue((bundle.root / "metadata" / "objects.json").exists())
            self.assertTrue((bundle.root / "metadata" / "object_map.json").exists())
            self.assertTrue((bundle.root / "metadata" / "overlays.json").exists())
            self.assertTrue((bundle.root / "geometry" / "geometry_assets.json").exists())

            scene_payload = json.loads(bundle.scene_path.read_text(encoding="utf-8"))
            restored = VisualizationScene.from_dict(scene_payload)
            restored.validate()
            self.assertEqual(restored.scene_id, "scene_bundle")

    def test_write_scene_bundle_exports_relative_geometry_payloads_with_object_ids(self):
        scene = self._scene()

        with TemporaryDirectory() as tmpdir:
            bundle = write_scene_bundle(scene, Path(tmpdir) / "review_scene")
            scene_payload = json.loads(bundle.scene_path.read_text(encoding="utf-8"))
            asset = scene_payload["geometry_assets"][0]

            self.assertFalse(Path(asset["uri"]).is_absolute())
            geometry_payload_path = bundle.root / asset["uri"]
            self.assertTrue(geometry_payload_path.exists())

            geometry_payload = json.loads(geometry_payload_path.read_text(encoding="utf-8"))
            self.assertEqual(geometry_payload["asset_id"], asset["id"])
            self.assertEqual(geometry_payload["object_ids"], asset["object_ids"])
            self.assertEqual(geometry_payload["generation_config"]["entity_ref"], "element:pipe_0")

    def test_write_scene_bundle_exports_object_identity_map(self):
        scene = self._scene()

        with TemporaryDirectory() as tmpdir:
            bundle = write_scene_bundle(scene, Path(tmpdir) / "review_scene")
            object_map = json.loads((bundle.root / "metadata" / "object_map.json").read_text(encoding="utf-8"))

            pipe_entry = object_map["object:element:pipe_0"]
            self.assertEqual(pipe_entry["entity_ref"], "element:pipe_0")
            self.assertEqual(pipe_entry["kind"], "pipe")
            self.assertEqual(pipe_entry["geometry_asset_id"], "geometry:element:pipe_0")


if __name__ == "__main__":
    unittest.main()
