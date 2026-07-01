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

    def test_code_aster_notebooks_use_explicit_wsl_runtime(self):
        notebooks_dir = Path(__file__).resolve().parents[1] / "notebooks"
        offenders: list[str] = []

        for notebook_path in sorted(notebooks_dir.glob("*.ipynb")):
            notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
            code_sources = [
                "".join(cell.get("source", []))
                for cell in notebook.get("cells", [])
                if cell.get("cell_type") == "code"
            ]
            full_code = "\n".join(code_sources)
            if "load_or_run_code_aster_results(" in full_code:
                if "configure_code_aster_notebook_runtime" not in full_code:
                    offenders.append(f"{notebook_path.name}: missing configure_code_aster_notebook_runtime")
                if "wsl_distro=CODE_ASTER_RUNTIME.wsl_distro" not in full_code:
                    offenders.append(f"{notebook_path.name}: loader missing CODE_ASTER_RUNTIME.wsl_distro")
            if "SolverLoopConfig(" in full_code and "run_solver=RUN_CODE_ASTER" in full_code:
                if "exec_method=CODE_ASTER_RUNTIME.exec_method" not in full_code:
                    offenders.append(f"{notebook_path.name}: solver loop missing runtime exec_method")
                if "wsl_distro=CODE_ASTER_RUNTIME.wsl_distro" not in full_code:
                    offenders.append(f"{notebook_path.name}: solver loop missing runtime wsl_distro")
            if "CodeAsterSolver(" in full_code and "export_study(" in full_code:
                if "exec_method=CODE_ASTER_RUNTIME.exec_method" not in full_code:
                    offenders.append(f"{notebook_path.name}: CodeAsterSolver missing runtime exec_method")
                if "wsl_distro=CODE_ASTER_RUNTIME.wsl_distro" not in full_code:
                    offenders.append(f"{notebook_path.name}: CodeAsterSolver missing runtime wsl_distro")

        self.assertEqual([], offenders)

    def test_notebooks_do_not_refer_to_legacy_as_run_setup(self):
        notebooks_dir = Path(__file__).resolve().parents[1] / "notebooks"
        offenders: list[str] = []

        for notebook_path in sorted(notebooks_dir.glob("*.ipynb")):
            text = notebook_path.read_text(encoding="utf-8")
            if "Code_Aster/as_run" in text:
                offenders.append(notebook_path.name)

        self.assertEqual([], offenders)


if __name__ == "__main__":
    unittest.main()
