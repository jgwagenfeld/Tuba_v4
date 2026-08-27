import json
import unittest
from pathlib import Path

import pytest

nbformat = pytest.importorskip("nbformat")


NOTEBOOK_DIR = Path(__file__).resolve().parents[1] / "notebooks"


def _notebook_text(name: str) -> str:
    notebook = json.loads((NOTEBOOK_DIR / name).read_text(encoding="utf-8"))
    return "\n".join("".join(cell.get("source", [])) for cell in notebook.get("cells", []))


class TestNotebookCourseDidactics(unittest.TestCase):
    def test_notebooks_are_current_clean_and_portable(self):
        for path in sorted(NOTEBOOK_DIR.glob("*.ipynb")):
            with self.subTest(path=path.name):
                notebook = nbformat.read(path, as_version=nbformat.NO_CONVERT)
                nbformat.validate(notebook)
                self.assertEqual(nbformat.current_nbformat, notebook.nbformat)
                self.assertEqual(nbformat.current_nbformat_minor, notebook.nbformat_minor)
                self.assertEqual("python3", notebook.metadata.kernelspec.name)
                self.assertEqual("Python 3", notebook.metadata.kernelspec.display_name)
                self.assertNotIn("widgets", notebook.metadata)
                self.assertFalse(
                    [output for cell in notebook.cells for output in cell.get("outputs", [])]
                )

    def test_notebook_course_uses_installed_viewer_launcher(self):
        text = "\n".join(_notebook_text(path.name) for path in NOTEBOOK_DIR.glob("*.ipynb"))
        self.assertIn("tuba-viewer", text)
        self.assertNotIn("npm.cmd run dev", text)
        self.assertNotIn("viewer/public", text)
        self.assertNotIn("publish_viewer_bundle", text)

    def test_visualization_review_uses_its_analysis_mesh(self):
        text = _notebook_text("04_visualization_gallery.ipynb")
        review_call = text[text.index("review = build_engineering_review(") :]
        self.assertIn("analysis_meshes=analysis_meshes", review_call.split(")", 1)[0])

    def test_support_lesson_updates_existing_supports_instead_of_duplicating_them(self):
        text = _notebook_text("02_supports_and_loading.ipynb")
        self.assertIn("Adding another support would append", text)
        self.assertNotIn('model.add_support(\n    node="N2"', text)
        self.assertNotIn('model.add_support(\n    node="N3"', text)

    def test_design_evaluation_lesson_does_not_claim_to_run_optimization(self):
        text = _notebook_text("06_structural_frames_and_optimization.ipynb")
        self.assertIn("No optimization is run in this lesson", text)
        self.assertNotIn("Solver-Scored Support Optimization", text)

    def test_notebooks_use_plain_coordinates_for_add_node_examples(self):
        offenders: list[str] = []
        for path in sorted(NOTEBOOK_DIR.glob("*.ipynb")):
            text = path.read_text(encoding="utf-8")
            if "add_node(np.array" in text:
                offenders.append(path.name)

        self.assertEqual([], offenders)

    def test_course_map_covers_all_numbered_notebooks(self):
        welcome = _notebook_text("00_welcome_and_setup.ipynb")
        readme = (NOTEBOOK_DIR.parent / "README.md").read_text(encoding="utf-8")

        for label in [f"{index:02d}" for index in range(11)]:
            with self.subTest(label=label):
                self.assertIn(f"**{label}**", welcome)
                self.assertIn(f"{label}_", readme)

    def test_notebooks_that_print_n1_n2_also_show_endpoint_vectors(self):
        expected_phrases = {
            "01_building_piping_systems.ipynb": "element vector",
            "06_structural_frames_and_optimization.ipynb": "Frame element endpoint vectors",
            "07_bim_data_exchange.ipynb": "First pipe endpoints",
            "advanced_piping_design_and_bim.ipynb": "Frame element endpoint vectors",
        }

        missing = [
            f"{name}: {phrase}"
            for name, phrase in expected_phrases.items()
            if phrase not in _notebook_text(name)
        ]

        self.assertEqual([], missing)


if __name__ == "__main__":
    unittest.main()
