import importlib.util
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


class TestOperatingStateExample(unittest.TestCase):
    def test_example_workflow_reports_operating_only_clash(self):
        module_path = Path(__file__).resolve().parents[1] / "examples" / "operating_state_clash.py"
        spec = importlib.util.spec_from_file_location("operating_state_clash_example", module_path)
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        with TemporaryDirectory() as tmpdir:
            summary = module.run_example(output_dir=tmpdir)

        self.assertEqual(summary["envelopes"], 1)
        self.assertEqual(len(summary["clashes"]), 1)
        self.assertEqual(summary["clashes"][0]["severity"], "operating_only_hard")
        self.assertTrue(summary["manifest"].endswith("study_manifest.json"))
        self.assertTrue(summary["scene"].endswith("operating_state_scene.json"))
        self.assertTrue(summary["bcf"].endswith("operating_state_clash.bcfzip"))


if __name__ == "__main__":
    unittest.main()
