import json
import unittest
from pathlib import Path


class TestNotebookResultProvenance(unittest.TestCase):
    def test_notebooks_do_not_display_hand_built_or_mock_solver_results(self):
        notebooks_dir = Path(__file__).resolve().parents[1] / "notebooks"
        forbidden_snippets = (
            "FEAResults(",
            "NodeResult(",
            "ElementResult(",
            'solver_name="mock',
            "solver_name='mock",
            "model.solve =",
            "def dynamic_solve",
            "mock FEA",
            "mock solver",
            "mock results",
        )
        offenders: list[str] = []

        for notebook_path in sorted(notebooks_dir.glob("*.ipynb")):
            notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
            for cell_index, cell in enumerate(notebook.get("cells", [])):
                source = "".join(cell.get("source", []))
                matches = [snippet for snippet in forbidden_snippets if snippet.lower() in source.lower()]
                if matches:
                    offenders.append(f"{notebook_path.name}:cell {cell_index}:{', '.join(matches)}")

        self.assertEqual([], offenders)


if __name__ == "__main__":
    unittest.main()
