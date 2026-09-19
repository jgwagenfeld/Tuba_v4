import hashlib
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

    # The three autorouting notebooks this file used to guard (05, 08 and
    # autorouting_quick_iteration) are gone: autorouting.md holds their code
    # verbatim and the autorouted-expansion-loop gallery publishes the solved
    # outcome, so the lesson survives where a reader can actually find it.

    def test_notebooks_do_not_refer_to_legacy_as_run_setup(self):
        notebooks_dir = Path(__file__).resolve().parents[1] / "notebooks"
        offenders: list[str] = []

        for notebook_path in sorted(notebooks_dir.glob("*.ipynb")):
            text = notebook_path.read_text(encoding="utf-8")
            if "Code_Aster/as_run" in text:
                offenders.append(notebook_path.name)

        self.assertEqual([], offenders)

    def test_notebooks_keep_visualization_contract(self):
        notebooks_dir = Path(__file__).resolve().parents[1] / "notebooks"
        forbidden_snippets = ("Plotly", "K3D", "Matplotlib", "._model =")
        offenders: list[str] = []

        for notebook_path in sorted(notebooks_dir.glob("*.ipynb")):
            notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
            text = "\n".join("".join(cell.get("source", [])) for cell in notebook.get("cells", []))
            matches = [snippet for snippet in forbidden_snippets if snippet in text]
            if matches:
                offenders.append(f"{notebook_path.name}: {', '.join(matches)}")
            for cell_index, cell in enumerate(notebook.get("cells", [])):
                if cell.get("cell_type") != "code":
                    continue
                for line in "".join(cell.get("source", [])).splitlines():
                    if ".show(" in line and "jupyter_backend=" not in line:
                        offenders.append(f"{notebook_path.name}:cell {cell_index}: {line.strip()}")

        self.assertEqual([], offenders)

    def test_artifact_backed_notebooks_default_to_load_existing_results(self):
        repo_root = Path(__file__).resolve().parents[1]
        # Seven more notebooks were listed here, five of them pointing at
        # private runs under notebooks/code_aster_results/. Those runs went
        # with their readers; only bim_operating is still needed, because
        # nothing but 07 round-trips IFC. 04 reads the gallery's own evidence.
        artifact_backed = {
            "04_visualization_gallery.ipynb": "examples/code-aster-review/evidence/Operating",
            "07_bim_data_exchange.ipynb": "notebooks/code_aster_results/bim_operating",
        }
        offenders: list[str] = []

        for notebook_name, artifact_dir in artifact_backed.items():
            artifact_root = repo_root / artifact_dir
            self.assertTrue((artifact_root / "study_depl.csv").exists(), artifact_root)
            attestation = json.loads((artifact_root / "study_execution.json").read_text(encoding="utf-8"))
            for artifact_name, expected in attestation["artifacts"].items():
                content = (artifact_root / artifact_name).read_bytes()
                self.assertEqual(expected["size_bytes"], len(content), artifact_name)
                self.assertEqual(expected["sha256"], hashlib.sha256(content).hexdigest(), artifact_name)
            text = (repo_root / "notebooks" / notebook_name).read_text(encoding="utf-8")
            code = "".join(
                "".join(cell.get("source", []))
                for cell in json.loads(text).get("cells", [])
                if cell.get("cell_type") == "code"
            )
            # The notebook must import this very folder, not merely one that happens to exist.
            folder = "REPO_ROOT / " + " / ".join(f'"{part}"' for part in artifact_dir.split("/"))
            self.assertIn(folder, code, notebook_name)
            if (
                "RUN_CODE_ASTER = False" not in text
                and "TUBA_NOTEBOOK_RUN_CODE_ASTER" not in text
            ):
                offenders.append(notebook_name)

        self.assertEqual([], offenders)


if __name__ == "__main__":
    unittest.main()
