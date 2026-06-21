import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tuba import Model
from tuba.patches import AddElement, AddNode, ModelPatch
from tuba.visualization.live_preview import preview_json_patch, preview_python_script


class TestVisualizationLivePreview(unittest.TestCase):
    def _model(self):
        model = Model(project_name="LivePreview")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        return model

    def _patch(self):
        return ModelPatch(
            operations=[
                AddNode(local_id="a", coords=(0.0, 0.0, 0.0)),
                AddNode(local_id="b", coords=(1.0, 0.0, 0.0)),
                AddElement(local_id="pipe", type="pipe_straight", n1="a", n2="b", section="PipeSec", material="Steel"),
            ]
        )

    def test_preview_json_patch_dry_runs_and_returns_scene_diff(self):
        model = self._model()

        result = preview_json_patch(model, self._patch().to_dict())

        self.assertEqual(model.elements, [])
        self.assertEqual(result.scene_diff.added_objects[0].kind, "proposal_added")
        self.assertEqual(result.messages[0]["type"], "scene_diff")
        self.assertEqual(result.messages[0]["diff_id"], result.scene_diff.diff_id)
        self.assertEqual(result.diagnostics, [])

    def test_invalid_json_patch_returns_diagnostic_without_mutation(self):
        model = self._model()
        payload = {
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
        }

        result = preview_json_patch(model, payload)

        self.assertEqual(model.elements, [])
        self.assertIsNone(result.scene_diff)
        self.assertEqual(result.diagnostics[0].severity, "error")
        self.assertEqual(result.messages[0]["type"], "diagnostic")

    def test_preview_python_script_uses_trusted_build_patch_function(self):
        model = self._model()

        with TemporaryDirectory() as tmpdir:
            script = Path(tmpdir) / "proposal.py"
            script.write_text(
                "from tuba.patches import AddElement, AddNode, ModelPatch\n"
                "def build_patch(model):\n"
                "    return ModelPatch(operations=[\n"
                "        AddNode(local_id='a', coords=(0, 0, 0)),\n"
                "        AddNode(local_id='b', coords=(2, 0, 0)),\n"
                "        AddElement(local_id='pipe', type='pipe_straight', n1='a', n2='b', section='PipeSec', material='Steel'),\n"
                "    ])\n",
                encoding="utf-8",
            )

            result = preview_python_script(model, script)

        self.assertEqual(result.scene_diff.added_geometry_assets[0].generation_config["points"], [[0.0, 0.0, 0.0], [2.0, 0.0, 0.0]])


if __name__ == "__main__":
    unittest.main()
