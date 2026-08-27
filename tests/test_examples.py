import ast
import os
import unittest
from inspect import signature
from pathlib import Path
from tempfile import TemporaryDirectory

from examples.autoroute_expansion_loop import run_example as run_expansion_loop_example
from examples.autorouting_basic import main as run_autorouting_basic
from examples.code_aster_artifact_review import run_example as run_artifact_review
from examples.code_aster_tee_volume_review import run_example as run_tee_volume_review
from examples.demo import main as run_demo_example
from examples.future_ready_semantic_workflow import run_demo
from examples.operating_state_clash import run_example as run_operating_clash
from examples.realtime_visualization_review import run_example as run_realtime_review
from tuba.routing.agent import AutoroutingAgent


class TestExamples(unittest.TestCase):
    def test_generated_example_defaults_use_build_root(self):
        expected = {
            run_expansion_loop_example: ("output_root", ".build/routing_reports"),
            run_artifact_review: ("output_dir", ".build/benchmarks/code_aster_artifact_review"),
            run_tee_volume_review: ("output_dir", ".build/benchmarks/code_aster_tee_volume_review"),
            run_operating_clash: ("output_dir", ".build/benchmarks/operating_state_clash_example"),
            run_realtime_review: ("output_dir", ".build/benchmarks/realtime_visualization_review"),
            run_demo: ("output_dir", ".build/generated/future_ready_semantic_workflow"),
        }

        for runner, (parameter, output_dir) in expected.items():
            with self.subTest(runner=runner.__module__):
                self.assertEqual(
                    signature(runner).parameters[parameter].default,
                    output_dir,
                )

        self.assertEqual(
            signature(AutoroutingAgent).parameters["output_root"].default,
            ".build/routing_reports",
        )

    def test_generated_script_outputs_stay_under_build_root(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            previous = Path.cwd()
            try:
                os.chdir(root)
                run_autorouting_basic()
                run_demo_example()
            finally:
                os.chdir(previous)

            self.assertTrue((root / ".build/generated/autorouting_basic/route_report.md").is_file())
            self.assertTrue((root / ".build/piping_model.json").is_file())
            self.assertTrue((root / ".build/code_aster_study/study.comm").is_file())

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
        forbidden_solver_result_names = {"FEAResults", "NodeResult", "ElementResult", "ResultState"}
        offenders: list[str] = []

        for path in sorted(examples_dir.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            matches: list[str] = []
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    imported = {alias.asname or alias.name for alias in node.names}
                    matches.extend(sorted(imported & forbidden_solver_result_names))
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id in forbidden_solver_result_names:
                        matches.append(node.func.id)
                    elif isinstance(node.func, ast.Attribute) and node.func.attr in forbidden_solver_result_names:
                        matches.append(node.func.attr)
            if matches:
                offenders.append(f"{path.name}: {', '.join(sorted(set(matches)))}")

        self.assertEqual([], offenders)


if __name__ == "__main__":
    unittest.main()
