import json
import unittest
from pathlib import Path


NOTEBOOK_DIR = Path(__file__).resolve().parents[1] / "notebooks"


def _notebook_text(name: str) -> str:
    notebook = json.loads((NOTEBOOK_DIR / name).read_text(encoding="utf-8"))
    return "\n".join("".join(cell.get("source", [])) for cell in notebook.get("cells", []))


class TestNotebookCourseDidactics(unittest.TestCase):
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
