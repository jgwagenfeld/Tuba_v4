import json
import tempfile
import unittest
from pathlib import Path

from tuba.solver.aster_sidecar import build_solver_name_map, dump_solver_sidecar


class TestCodeAsterSidecar(unittest.TestCase):
    def test_long_names_are_mapped_to_short_deterministic_names(self):
        mapping = build_solver_name_map(["PipeStraights", "element_with_a_name_that_is_longer_than_24_chars"])

        self.assertEqual(mapping["PipeStraights"], "PipeStraights")
        self.assertLessEqual(len(mapping["element_with_a_name_that_is_longer_than_24_chars"]), 24)
        self.assertEqual(
            mapping["element_with_a_name_that_is_longer_than_24_chars"],
            build_solver_name_map(["element_with_a_name_that_is_longer_than_24_chars"])[
                "element_with_a_name_that_is_longer_than_24_chars"
            ],
        )

    def test_sidecar_contains_name_map_and_analysis_mesh_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "study_tuba_fem.json"
            dump_solver_sidecar(
                path,
                solver_name="Code_Aster",
                load_case="Hot",
                analysis_mesh_id="analysis_mesh:Hot",
                name_map={"long": "G000001"},
                lineage={"G000001": "element:long"},
            )
            data = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(data["solver_name"], "Code_Aster")
        self.assertEqual(data["analysis_mesh_id"], "analysis_mesh:Hot")
        self.assertEqual(data["name_map"]["long"], "G000001")
        self.assertEqual(data["lineage"]["G000001"], "element:long")
