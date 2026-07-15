import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tuba.visualization import GeometryAsset, Issue, SceneObject, VisualizationScene
from tuba.visualization.static_report import notebook_iframe_html, write_static_report


class TestVisualizationStaticReport(unittest.TestCase):
    def _scene(self):
        return VisualizationScene(
            scene_id="scene:static_report",
            model_id="model:static_report",
            objects=[
                SceneObject(
                    id="object:pipe",
                    kind="pipe",
                    name="Report pipe",
                    geometry_asset_id="asset:pipe",
                    layer_ids=["cold_geometry"],
                )
            ],
            geometry_assets=[
                GeometryAsset(
                    id="asset:pipe",
                    format="polyline",
                    bounds=[0, 0, 0, 1, 0, 0],
                    object_ids=["object:pipe"],
                    generation_config={"points": [[0, 0, 0], [1, 0, 0]]},
                )
            ],
            issues=[
                Issue(
                    id="issue:clearance",
                    type="clash",
                    title="Clearance review",
                    severity="warning",
                    status="open",
                    description="Review insulation clearance.",
                )
            ],
        )

    def test_write_static_report_creates_standalone_folder_and_issue_summary(self):
        with TemporaryDirectory() as tmpdir:
            report = write_static_report(self._scene(), tmpdir, title="Static Review")

            html = (Path(tmpdir) / "index.html").read_text(encoding="utf-8")
            scene = json.loads((Path(tmpdir) / "scene.json").read_text(encoding="utf-8"))
            issues = json.loads((Path(tmpdir) / "issue_summary.json").read_text(encoding="utf-8"))

        self.assertEqual(report.index_path.name, "index.html")
        self.assertEqual(scene["scene_id"], "scene:static_report")
        self.assertIn('id="tuba-scene"', html)
        self.assertIn("Static Review", html)
        self.assertEqual(issues["counts"]["warning"], 1)
        self.assertEqual(issues["issues"][0]["id"], "issue:clearance")

    def test_scene_only_static_report_labels_missing_authoritative_inputs(self):
        with TemporaryDirectory() as tmpdir:
            report = write_static_report(self._scene(), tmpdir)
            html = report.index_path.read_text(encoding="utf-8")

        self.assertIn("Legacy scene-derived report", html)
        self.assertIn("Code compliance unavailable", html)
        self.assertIn("FE Von Mises (not piping-code stress)", html)
        self.assertNotIn("ASME compliant", html)
        self.assertNotIn("Piping-code compliance: passed", html)

    def test_notebook_iframe_html_targets_report_index(self):
        html = notebook_iframe_html("reports/static_review", width="900", height=500)

        self.assertIn("<iframe", html)
        self.assertIn('src="reports/static_review/index.html"', html)
        self.assertIn('width="900"', html)
        self.assertIn('height="500"', html)

    def test_missing_screenshot_support_is_reported_as_diagnostic(self):
        with TemporaryDirectory() as tmpdir:
            report = write_static_report(self._scene(), tmpdir, include_screenshot=True, screenshot_backend="playwright")
            self.assertTrue(report.index_path.exists())

        if not report.screenshot_path:
            self.assertEqual(report.diagnostics[0]["code"], "visualization.static_report.screenshot_unavailable")


if __name__ == "__main__":
    unittest.main()
