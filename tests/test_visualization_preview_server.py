import json
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import urlopen

from tuba.visualization.preview import PreviewServer, execute_preview_script, run_preview_once


SCENE_SCRIPT = """
from tuba.visualization import GeometryAsset, SceneObject, VisualizationScene
from tuba.visualization.preview import show_scene

scene = VisualizationScene(
    scene_id="{scene_id}",
    model_id="model:preview",
    objects=[
        SceneObject(
            id="object:pipe",
            kind="pipe",
            name="{name}",
            geometry_asset_id="asset:pipe",
            layer_ids=["cold:pipe_body"],
        )
    ],
    geometry_assets=[
        GeometryAsset(
            id="asset:pipe",
            format="polyline",
            bounds=[0, 0, 0, 1, 0, 0],
            object_ids=["object:pipe"],
            generation_config={{"points": [[0, 0, 0], [1, 0, 0]], "source": "preview.test"}},
        )
    ],
)
show_scene(scene)
"""


class TestVisualizationPreviewServer(unittest.TestCase):
    def test_run_preview_once_writes_bundle_and_events(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            script = root / "preview_scene.py"
            out = root / "bundle"
            script.write_text(SCENE_SCRIPT.format(scene_id="scene:preview:1", name="Pipe 1"), encoding="utf-8")

            result = run_preview_once(script, out, revision=7, timeout_s=10.0, bundle_url="http://preview/")

            scene = json.loads((out / "scene.json").read_text(encoding="utf-8"))
            self.assertTrue(result.ok)
            self.assertEqual(scene["scene_id"], "scene:preview:1")
            self.assertEqual([event["type"] for event in result.events], ["run_started", "scene_reloaded", "run_finished"])
            self.assertEqual(result.events[1]["bundle_url"], "http://preview/")
            self.assertEqual(result.events[1]["bundle_revision"], 7)

    def test_invalid_script_returns_diagnostic_event(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            script = root / "bad.py"
            out = root / "bundle"
            script.write_text("raise RuntimeError('broken preview')\n", encoding="utf-8")

            payload = execute_preview_script(script, out, timeout_s=10.0)

            self.assertFalse(payload["ok"])
            self.assertEqual(payload["messages"][0]["type"], "diagnostic")
            self.assertEqual(payload["diagnostics"][0]["code"], "visualization.preview.python_error")
            self.assertIn("broken preview", payload["diagnostics"][0]["message"])

    def test_preview_subprocess_timeout_is_enforced(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            script = root / "slow.py"
            out = root / "bundle"
            script.write_text("import time\ntime.sleep(5)\n", encoding="utf-8")
            started = time.perf_counter()

            payload = execute_preview_script(script, out, timeout_s=0.2)

            self.assertLess(time.perf_counter() - started, 2.0)
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["diagnostics"][0]["code"], "visualization.preview.timeout")

    def test_preview_server_watches_script_and_serves_updated_scene(self):
        # ignore_cleanup_errors: the watch loop spawns subprocesses that write
        # into tmpdir; on Windows the OS can briefly hold a handle after
        # server.stop(), racing rmtree. The assertions below verify behavior.
        with TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            root = Path(tmpdir)
            script = root / "preview_scene.py"
            out = root / "bundle"
            script.write_text(SCENE_SCRIPT.format(scene_id="scene:preview:1", name="Pipe 1"), encoding="utf-8")
            server = PreviewServer(script, out, port=0, poll_interval_s=0.05, debounce_s=0.05, timeout_s=10.0).start()
            try:
                initial = json.loads(urlopen(server.base_url + "scene.json", timeout=2).read().decode("utf-8"))
                self.assertEqual(initial["scene_id"], "scene:preview:1")

                script.write_text(SCENE_SCRIPT.format(scene_id="scene:preview:2", name="Pipe 2"), encoding="utf-8")
                deadline = time.time() + 15
                while time.time() < deadline:
                    scene = json.loads((out / "scene.json").read_text(encoding="utf-8"))
                    if scene["scene_id"] == "scene:preview:2":
                        break
                    time.sleep(0.05)
                else:
                    self.fail("preview server did not refresh the scene bundle")

                event_types = [event["type"] for event in server.broker.events]
                self.assertIn("scene_reloaded", event_types)
                self.assertGreaterEqual(server.revision, 2)
            finally:
                # Stop the server (joins watch thread + HTTP) before the
                # TemporaryDirectory is removed; the subprocess-backed server
                # otherwise still holds the dir on Windows during rmtree.
                server.stop()


if __name__ == "__main__":
    unittest.main()
