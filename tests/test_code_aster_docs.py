import json
import unittest
from pathlib import Path


class TestCodeAsterDocs(unittest.TestCase):
    def test_installation_walkthrough_documents_wsl_conda_runtime(self):
        text = Path("docs/code_aster_installation.md").read_text(encoding="utf-8")

        self.assertIn("`pip install tuba` installs Tuba only", text)
        self.assertIn("does not install Code_Aster", text)
        self.assertIn('pip install "tuba[code-aster-rmed]"', text)
        self.assertIn("conda create -y -n tuba-code-aster", text)
        self.assertIn("code-aster=18.0.12", text)
        self.assertIn("run_aster --version", text)
        self.assertIn("TUBA_CODE_ASTER_EXEC_METHOD", text)
        self.assertIn("TUBA_CODE_ASTER_WSL_DISTRO", text)
        self.assertIn("TUBA_RUN_CODE_ASTER_INTEGRATION", text)
        self.assertIn("python -m tuba.solver.code_aster_doctor", text)
        self.assertIn("tuba.solver.code_aster_doctor --check", text)
        self.assertIn("If the check reports `blocked`, do not set `RUN_CODE_ASTER = True`", text)
        self.assertNotIn("As of the last local check", text)

    def test_public_setup_includes_the_tested_solver_install_path(self):
        text = Path("docs/site/setup.html").read_text(encoding="utf-8")

        self.assertIn("pip installs Tuba, not Code_Aster", text)
        self.assertIn("Miniforge3-Linux-x86_64.sh", text)
        self.assertIn("conda create -y -n tuba-code-aster", text)
        self.assertIn("code-aster=18.0.12", text)
        self.assertIn("Native Linux", text)
        self.assertIn("python3 -m venv .venv", text)
        self.assertNotIn("/opt/aster/bin/run_aster", text)
        self.assertNotIn("simvia/code_aster:stable", text)

    def test_welcome_notebook_points_to_solver_setup_before_execution(self):
        notebook = json.loads(Path("notebooks/00_welcome_and_setup.ipynb").read_text(encoding="utf-8"))
        source = "\n".join("".join(cell.get("source", [])) for cell in notebook.get("cells", []))

        self.assertIn("pip installs Tuba, not Code_Aster", source)
        self.assertIn("python -m tuba.solver.code_aster_doctor --check", source)

    def test_readme_documents_required_runtime_and_doctor(self):
        text = Path("README.md").read_text(encoding="utf-8")

        self.assertIn("Code_Aster is required for the full Tuba workflow", text)
        self.assertIn("docs/code_aster_installation.md", text)
        self.assertIn("TUBA_CODE_ASTER_EXEC_METHOD", text)
        self.assertIn("python -m tuba.solver.code_aster_doctor --check", text)
        self.assertIn("VS Code notebooks default to loading committed Code_Aster artifacts", text)
        self.assertIn("pip installs Tuba; it does not install Code_Aster", text)

    def test_agent_instructions_state_code_aster_is_not_optional(self):
        text = Path("AGENTS.md").read_text(encoding="utf-8")

        self.assertIn("Code_Aster is not optional", text)
        self.assertIn("define piping structure", text)
        self.assertIn("evaluate it with Code_Aster", text)
        self.assertIn("display processed results", text)


if __name__ == "__main__":
    unittest.main()
