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

    def test_user_facing_examples_do_not_publish_synthetic_solver_results(self):
        examples_dir = Path(__file__).resolve().parents[1] / "examples"
        user_facing_examples = (
            "demo.py",
            "operating_state_clash.py",
            "realtime_visualization_review.py",
        )
        forbidden_snippets = (
            'FEAResults(solver_name="mock',
            "FEAResults(solver_name='mock",
            'ResultState(\n        id="result_state:Hot:mock"',
            'ResultState(\n        id="result_state:Hot:review_mock"',
            'metadata={"source": "mock_result_state_for_example"}',
            'metadata={"source": "realtime_visualization_review_mock_result_state"}',
        )
        offenders: list[str] = []

        for name in user_facing_examples:
            path = examples_dir / name
            text = path.read_text(encoding="utf-8")
            matches = [snippet for snippet in forbidden_snippets if snippet in text]
            if matches:
                offenders.append(f"{path.name}: {', '.join(matches)}")

        self.assertEqual([], offenders)


if __name__ == "__main__":
    unittest.main()
