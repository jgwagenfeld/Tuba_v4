import csv
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tuba.visualization import Overlay, SceneObject, VisualizationScene
from tuba.visualization.reports import (
    build_reports,
    line_list,
    load_case_summary,
    reaction_report,
    section_schedule,
    stress_report,
    write_report_csvs,
)


def _scene():
    return VisualizationScene(
        scene_id="scene:reports",
        model_id="model:reports",
        objects=[
            SceneObject(
                id="object:element:pipe_0",
                kind="pipe",
                name="pipe_0",
                metadata={"element_type": "pipe_straight", "nodes": ["N0", "N1"], "section": "PipeSec", "material": "Steel"},
                physical={"element_id": "pipe_0", "bare_od_m": 0.1, "metal_area_m2": 0.00283, "mass_kg_per_m": 22.2},
                quantities={"length_m": 1.0, "total_mass_kg": 22.2},
            ),
            SceneObject(id="object:support:anchor_0", kind="support", name="anchor_0", metadata={"node": "N0", "support_type": "anchor"}),
        ],
        overlays=[
            Overlay(
                id="overlay:stress",
                kind="solver_result",
                name="Stress Hot",
                data={
                    "result_type": "stress",
                    "load_case": "Hot",
                    "unit": "Pa",
                    "values": {"object:element:pipe_0": 118e6},
                    "utilization_values": {"object:element:pipe_0": 0.86},
                    "legend": {"thresholds": {"warning": 0.8, "critical": 1.0}},
                },
            ),
            Overlay(
                id="overlay:result_state",
                kind="result_state",
                name="Result state Hot",
                data={
                    "load_case": "Hot",
                    "node_reactions": {"N0": [900.0, 0.0, -300.0, 0.0, 0.0, 0.0]},
                    "node_displacements": {"N0": [0.0] * 6, "N1": [0.0, 0.012, 0.0, 0.0, 0.0, 0.0]},
                },
            ),
        ],
    )


class TestVisualizationReports(unittest.TestCase):
    def test_line_list_and_section_schedule(self):
        rows = line_list(_scene())
        self.assertEqual(rows[0]["from_node"], "N0")
        self.assertEqual(rows[0]["to_node"], "N1")
        self.assertEqual(rows[0]["section"], "PipeSec")
        schedule = section_schedule(_scene())
        self.assertEqual(schedule[0]["count"], 1)
        self.assertAlmostEqual(schedule[0]["total_mass_kg"], 22.2)

    def test_stress_status_from_utilization_thresholds(self):
        rows = stress_report(_scene())
        self.assertEqual(rows[0]["load_case"], "Hot")
        self.assertEqual(rows[0]["status"], "warning")  # 0.86 is between 0.8 and 1.0

    def test_reaction_magnitude_and_support_mapping(self):
        rows = reaction_report(_scene())
        self.assertEqual(rows[0]["support"], "anchor_0")
        self.assertAlmostEqual(rows[0]["magnitude_n"], (900.0**2 + 300.0**2) ** 0.5)

    def test_load_case_summary_aggregates_worst_values(self):
        rows = load_case_summary(_scene())
        summary = {row["load_case"]: row for row in rows}["Hot"]
        self.assertAlmostEqual(summary["max_von_mises_pa"], 118e6)
        self.assertAlmostEqual(summary["max_utilization"], 0.86)
        self.assertAlmostEqual(summary["max_displacement_m"], 0.012)

    def test_write_report_csvs_skips_empty_and_writes_headers(self):
        with TemporaryDirectory() as tmpdir:
            paths = write_report_csvs(_scene(), tmpdir)
            names = {path.stem for path in paths}
            self.assertIn("line_list", names)
            self.assertIn("reactions", names)
            line_csv = next(path for path in paths if path.stem == "line_list")
            rows = list(csv.DictReader(Path(line_csv).open(encoding="utf-8")))
            self.assertEqual(rows[0]["name"], "pipe_0")

    def test_empty_scene_reports_are_empty_not_error(self):
        empty = VisualizationScene(scene_id="s", model_id="m")
        self.assertEqual(build_reports(empty), {name: [] for name in build_reports(empty)})


if __name__ == "__main__":
    unittest.main()
