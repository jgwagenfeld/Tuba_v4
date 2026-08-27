import hashlib
import json
import unittest
from pathlib import Path


class TestNotebookResultProvenance(unittest.TestCase):
    def test_advanced_notebook_uses_current_model_and_results(self):
        notebook_path = Path(__file__).resolve().parents[1] / "notebooks" / "advanced_piping_design_and_bim.ipynb"
        notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
        code = "\n".join(
            "".join(cell.get("source", []))
            for cell in notebook.get("cells", [])
            if cell.get("cell_type") == "code"
        )

        self.assertNotIn("opt_model", code)
        self.assertNotIn("opt_results", code)
        self.assertIn("export_html(init_results, html_file, model=model)", code)
        self.assertIn("exporter.export_model(model, ifc_path, results=init_results)", code)
        self.assertNotIn("Visualization export warning", code)

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

    def test_autorouting_notebooks_fail_loudly_for_solver_runs(self):
        notebooks_dir = Path(__file__).resolve().parents[1] / "notebooks"
        autorouting_notebooks = (
            "05_autorouting.ipynb",
            "08_expansion_aware_autorouting.ipynb",
            "autorouting_quick_iteration.ipynb",
        )
        offenders: list[str] = []

        for notebook_name in autorouting_notebooks:
            notebook = json.loads((notebooks_dir / notebook_name).read_text(encoding="utf-8"))
            full_code = "\n".join(
                "".join(cell.get("source", []))
                for cell in notebook.get("cells", [])
                if cell.get("cell_type") == "code"
            )
            if "SolverLoopConfig(" not in full_code or "run_solver=RUN_CODE_ASTER" not in full_code:
                continue
            if "strict=RUN_CODE_ASTER" not in full_code:
                offenders.append(f"{notebook_name}: solver loop is not strict when RUN_CODE_ASTER is enabled")
            if "route_pipe(" in full_code and "add_supports=True" not in full_code:
                offenders.append(f"{notebook_name}: solver-backed route_pipe call does not add supports")

        self.assertEqual([], offenders)

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

    def test_building_notebook_shows_profile_twist_with_local_axes(self):
        notebook_path = Path(__file__).resolve().parents[1] / "notebooks" / "01_building_piping_systems.ipynb"
        text = notebook_path.read_text(encoding="utf-8")

        self.assertIn("twist_angle=45.0", text)
        self.assertIn("twist_angle=90.0", text)
        self.assertIn("add_local_axes_to_plotter", text)
        self.assertIn("PROFILE_FORCE_SEGMENTS = 12", text)
        self.assertIn("for _ in range(PROFILE_FORCE_SEGMENTS):", text)
        self.assertIn("PROFILE_FORCE_DEFORM_SCALE = 8.0", text)
        self.assertIn("show_edges=True", text)

    def test_artifact_backed_notebooks_default_to_load_existing_results(self):
        notebooks_dir = Path(__file__).resolve().parents[1] / "notebooks"
        artifact_backed = {
            "00_welcome_and_setup.ipynb": "stress_analysis_operating",
            "01_building_piping_systems.ipynb": "building_profile_end_force",
            "03_stress_analysis_and_compliance.ipynb": "stress_analysis_operating",
            "04_visualization_gallery.ipynb": "viz_gallery_operating",
            "06_structural_frames_and_optimization.ipynb": "structural_operating_hot",
            "07_bim_data_exchange.ipynb": "bim_operating",
            "advanced_piping_design_and_bim.ipynb": "advanced_operating_hot",
            "visualize_elements_and_supports.ipynb": "elements_supports_loadcase1",
        }
        offenders: list[str] = []

        for notebook_name, artifact_dir in artifact_backed.items():
            artifact_root = notebooks_dir / "code_aster_results" / artifact_dir
            self.assertTrue((artifact_root / "study_depl.csv").exists(), artifact_root)
            attestation = json.loads((artifact_root / "study_execution.json").read_text(encoding="utf-8"))
            for artifact_name, expected in attestation["artifacts"].items():
                content = (artifact_root / artifact_name).read_bytes()
                self.assertEqual(expected["size_bytes"], len(content), artifact_name)
                self.assertEqual(expected["sha256"], hashlib.sha256(content).hexdigest(), artifact_name)
            text = (notebooks_dir / notebook_name).read_text(encoding="utf-8")
            if (
                "RUN_CODE_ASTER = False" not in text
                and "TUBA_NOTEBOOK_RUN_CODE_ASTER" not in text
            ):
                offenders.append(notebook_name)

        self.assertEqual([], offenders)


if __name__ == "__main__":
    unittest.main()
