import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from examples.future_ready_semantic_workflow import run_demo


class TestExamples(unittest.TestCase):
    def test_future_ready_semantic_workflow_runs(self):
        with TemporaryDirectory() as tmpdir:
            summary = run_demo(tmpdir)

            self.assertEqual(summary["line_length_m"], 4.0)
            self.assertGreater(summary["route_cost_total"], 0.0)
            self.assertEqual(summary["rack_force_z_n"], -500.0)
            self.assertTrue(summary["rules_passed"])
            self.assertTrue(Path(summary["bom_csv_path"]).exists())
            self.assertTrue(Path(summary["benchmark_path"]).exists())


if __name__ == "__main__":
    unittest.main()
