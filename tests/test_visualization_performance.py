import json
import os
import unittest
from inspect import signature
from pathlib import Path
from tempfile import TemporaryDirectory

from tuba import Model
from tuba.visualization.benchmarks import main as benchmarks_main
from tuba.visualization.performance import benchmark_scene_build, benchmark_viewer_smoke


class TestVisualizationPerformance(unittest.TestCase):
    def _model(self, count=25):
        model = Model(project_name="Performance")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        previous = model.add_node([0.0, 0.0, 0.0])
        for index in range(count):
            node = model.add_node([float(index + 1), 0.0, 0.0])
            model.add_element(
                id=f"pipe_{index}",
                type="pipe_straight",
                n1=previous,
                n2=node,
                section="PipeSec",
                material="Steel",
            )
            previous = node
        return model

    def test_benchmark_scene_build_writes_report(self):
        with TemporaryDirectory() as tmpdir:
            report = benchmark_scene_build(self._model(), output_dir=tmpdir)

            path = Path(report["report_path"])
            self.assertTrue(path.exists())
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["object_count"], 25)
            self.assertEqual(data["geometry_asset_count"], 25)
            self.assertGreaterEqual(data["build_seconds"], 0.0)
            self.assertGreater(data["bundle_size_bytes"], 0)
            self.assertEqual(len(data["asset_hashes"]), 25)
            self.assertTrue(all(value.startswith("sha256:") for value in data["asset_hashes"].values()))

    def test_benchmark_adds_diagnostics_when_limits_are_exceeded(self):
        report = benchmark_scene_build(self._model(), limits={"max_objects": 10})

        self.assertEqual(report["diagnostics"][0]["code"], "visualization.performance.object_limit")
        self.assertIn("object count", report["diagnostics"][0]["message"])

    def test_geometry_asset_hashes_are_stable_across_repeated_bundles(self):
        with TemporaryDirectory() as tmpdir:
            first = benchmark_scene_build(self._model(4), output_dir=Path(tmpdir) / "first")
            second = benchmark_scene_build(self._model(4), output_dir=Path(tmpdir) / "second")

            self.assertEqual(first["asset_hashes"], second["asset_hashes"])

    def test_viewer_smoke_benchmark_writes_load_selection_and_overlay_metrics(self):
        with TemporaryDirectory() as tmpdir:
            report = benchmark_viewer_smoke(output_dir=tmpdir, model=self._model(6))

            path = Path(report["report_path"])
            self.assertTrue(path.exists())
            self.assertEqual(report["scenario"], "viewer-smoke")
            self.assertGreater(report["bundle_size_bytes"], 0)
            self.assertGreaterEqual(report["viewer_load_ms"], 0.0)
            self.assertGreaterEqual(report["selection_latency_ms"], 0.0)
            self.assertGreaterEqual(report["overlay_toggle_latency_ms"], 0.0)

    def test_benchmarks_cli_runs_viewer_smoke(self):
        with TemporaryDirectory() as tmpdir:
            exit_code = benchmarks_main(["viewer-smoke", "--output-dir", tmpdir])

            self.assertEqual(exit_code, 0)
            self.assertTrue((Path(tmpdir) / "viewer_smoke_latest.json").exists())

    def test_visualization_benchmark_defaults_use_build_root(self):
        self.assertEqual(
            signature(benchmark_viewer_smoke).parameters["output_dir"].default,
            ".build/benchmarks",
        )
        with TemporaryDirectory() as tmpdir:
            original_directory = Path.cwd()
            os.chdir(tmpdir)
            try:
                self.assertEqual(benchmarks_main(["viewer-smoke"]), 0)
                self.assertTrue(Path(".build/benchmarks/viewer_smoke_latest.json").is_file())
            finally:
                os.chdir(original_directory)


if __name__ == "__main__":
    unittest.main()
