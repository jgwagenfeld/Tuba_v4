import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from examples.autoroute_expansion_loop import run_example as run_expansion_loop_example
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

    def test_autoroute_expansion_loop_writes_review_metadata(self):
        with TemporaryDirectory() as tmpdir:
            run = run_expansion_loop_example(tmpdir)
            report_path = Path(run.report_path)

            self.assertTrue(report_path.exists())
            self.assertIsNotNone(run.result.selected)
            self.assertIsNone(run.result.request.constraints.allowed_directions)
            self.assertIn("grid", {candidate.metadata.get("route_family") for candidate in run.result.candidates})
            self.assertEqual(run.result.selected.metadata.get("route_family"), "u_loop")
            report = report_path.read_text(encoding="utf-8")
            self.assertIn("Expansion loop", report)
            self.assertIn("Route family", report)


if __name__ == "__main__":
    unittest.main()
