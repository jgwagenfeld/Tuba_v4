import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

_CLASH_SCRIPT = """from tuba import Model

model = Model("ClashDemo")
model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0)
model.add_rectangular_section("RS", height_y=0.1, height_z=0.1)
a0 = model.add_node([0.0, 0.0, 0.0])
a1 = model.add_node([2.0, 0.0, 0.0])
b0 = model.add_node([1.0, -1.0, 0.0])
b1 = model.add_node([1.0, 1.0, 0.0])
model.add_element(id="beam_a", type="beam", n1=a0, n2=a1, section="RS", material="Steel")
model.add_element(id="beam_b", type="beam", n1=b0, n2=b1, section="RS", material="Steel")
"""

_CLEAN_SCRIPT = """from tuba import Model

model = Model("CleanDemo")
model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0)
model.add_rectangular_section("RS", height_y=0.1, height_z=0.1)
a0 = model.add_node([0.0, 0.0, 0.0])
a1 = model.add_node([2.0, 0.0, 0.0])
b1 = model.add_node([2.0, 2.0, 0.0])
model.add_element(id="beam_a", type="beam", n1=a0, n2=a1, section="RS", material="Steel")
model.add_element(id="beam_b", type="beam", n1=a1, n2=b1, section="RS", material="Steel")
"""


class TestStudioClashIssues(unittest.TestCase):
    def _start_studio(self, root: Path, script: str):
        from tuba.visualization.preview.server import ProjectStudioServer

        project = root / "project"
        project.mkdir()
        (project / "model.py").write_text(script, encoding="utf-8")
        server = ProjectStudioServer(project, root / "out", port=0)
        server.start()
        self.addCleanup(server.stop)
        return server

    def _scene(self, server) -> dict:
        return json.loads((server.out_dir / "build" / "scene.json").read_text(encoding="utf-8"))

    def test_build_bundle_marks_self_clash(self):
        server = self._start_studio(Path(self.enterContext(TemporaryDirectory())), _CLASH_SCRIPT)
        scene = self._scene(server)

        issues = [issue for issue in scene["issues"] if issue["type"] == "clash"]
        self.assertEqual(len(issues), 1)
        refs = set(issues[0]["entity_refs"])
        self.assertEqual(refs, {"element:beam_a", "element:beam_b"})

        markers = [obj for obj in scene["objects"] if obj["kind"] == "clash_marker"]
        self.assertEqual(len(markers), 1)
        self.assertEqual(
            {markers[0]["metadata"]["left"], markers[0]["metadata"]["right"]},
            {"element:beam_a", "element:beam_b"},
        )
        self.assertTrue(any(view["issue_id"] == issues[0]["id"] for view in scene["views"]))

    def test_build_bundle_is_quiet_without_clash(self):
        server = self._start_studio(Path(self.enterContext(TemporaryDirectory())), _CLEAN_SCRIPT)
        scene = self._scene(server)

        self.assertEqual(scene["issues"], [])


if __name__ == "__main__":
    unittest.main()
