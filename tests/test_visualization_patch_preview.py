import json
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import urlopen

from tuba import Model
from tuba.patches import AddElement, AddNode, ModelPatch
from tuba.visualization.preview import PatchPreviewServer, execute_patch_preview, run_patch_preview_once


class TestVisualizationPatchPreview(unittest.TestCase):
    def _model(self):
        model = Model(project_name="PatchPreview")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        return model

    def _patch(self, *, length=1.0):
        return ModelPatch(
            operations=[
                AddNode(local_id="a", coords=(0.0, 0.0, 0.0)),
                AddNode(local_id="b", coords=(length, 0.0, 0.0)),
                AddElement(local_id="pipe", type="pipe_straight", n1="a", n2="b", section="PipeSec", material="Steel"),
            ],
            provenance={"source": "test"},
        )

    def _write_inputs(self, root: Path, patch: ModelPatch | dict):
        model_path = root / "model.json"
        patch_path = root / "patch.json"
        model_payload = self._model().to_dict()
        model_path.write_text(json.dumps(model_payload, indent=2, sort_keys=True), encoding="utf-8")
        patch_payload = patch.to_dict() if isinstance(patch, ModelPatch) else patch
        patch_path.write_text(json.dumps(patch_payload, indent=2, sort_keys=True), encoding="utf-8")
        return model_path, patch_path, model_payload

    def test_run_patch_preview_once_writes_scene_without_mutating_model_snapshot(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            model_path, patch_path, original_model = self._write_inputs(root, self._patch(length=2.0))
            out = root / "bundle"

            result = run_patch_preview_once(model_path, patch_path, out, revision=4, bundle_url="http://preview/")

            scene = json.loads((out / "scene.json").read_text(encoding="utf-8"))
            self.assertTrue(result.ok)
            self.assertEqual(json.loads(model_path.read_text(encoding="utf-8")), original_model)
            self.assertEqual([event["type"] for event in result.events], ["run_started", "scene_reloaded", "run_finished"])
            self.assertEqual(result.events[1]["bundle_revision"], 4)
            self.assertEqual(scene["agent_proposals"][0]["proposal_id"], "live_preview")
            self.assertEqual(scene["scene_diffs"][0]["added_geometry_assets"][0]["generation_config"]["points"], [[0.0, 0.0, 0.0], [2.0, 0.0, 0.0]])

    def test_invalid_patch_returns_diagnostic_without_mutating_model_snapshot(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            model_path, patch_path, original_model = self._write_inputs(
                root,
                {
                    "operations": [
                        {"op": "add_node", "local_id": "a", "coords": [0.0, 0.0, 0.0]},
                        {
                            "op": "add_element",
                            "local_id": "bad",
                            "type": "pipe_straight",
                            "n1": "a",
                            "n2": "missing",
                            "section": "PipeSec",
                            "material": "Steel",
                        },
                    ]
                },
            )

            payload = execute_patch_preview(model_path, patch_path, root / "bundle")

            self.assertFalse(payload["ok"])
            self.assertEqual(json.loads(model_path.read_text(encoding="utf-8")), original_model)
            self.assertEqual(payload["messages"][0]["type"], "diagnostic")
            self.assertEqual(payload["diagnostics"][0]["code"], "visualization.patch_preview.invalid_patch")

    def test_patch_preview_server_watches_patch_and_serves_updated_scene(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            model_path, patch_path, _original_model = self._write_inputs(root, self._patch(length=1.0))
            out = root / "bundle"
            server = PatchPreviewServer(model_path, patch_path, out, port=0, poll_interval_s=0.05, debounce_s=0.05).start()
            self.addCleanup(server.stop)

            initial = json.loads(urlopen(server.base_url + "scene.json", timeout=2).read().decode("utf-8"))
            self.assertEqual(initial["scene_diffs"][0]["added_geometry_assets"][0]["generation_config"]["points"][1], [1.0, 0.0, 0.0])

            patch_path.write_text(json.dumps(self._patch(length=3.0).to_dict(), indent=2, sort_keys=True), encoding="utf-8")
            deadline = time.time() + 5
            while time.time() < deadline:
                scene = json.loads((out / "scene.json").read_text(encoding="utf-8"))
                if scene["scene_diffs"][0]["added_geometry_assets"][0]["generation_config"]["points"][1] == [3.0, 0.0, 0.0]:
                    break
                time.sleep(0.05)
            else:
                self.fail("patch preview server did not refresh the scene bundle")

            event_types = [event["type"] for event in server.broker.events]
            self.assertIn("scene_reloaded", event_types)
            self.assertGreaterEqual(server.revision, 2)


if __name__ == "__main__":
    unittest.main()
