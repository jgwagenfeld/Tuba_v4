import json
import unittest
from pathlib import Path


class TestCodeAsterDocs(unittest.TestCase):
    def test_installation_walkthrough_documents_wsl_conda_runtime(self):
        text = Path("docs/content/setup.md").read_text(encoding="utf-8")

        self.assertIn("`python -m pip install .` installs Tuba", text)
        self.assertIn("does not install Code_Aster", text)
        self.assertIn('.\\.venv\\Scripts\\python.exe -m pip install ".[code-aster-rmed]"', text)
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
        text = Path("docs/content/setup.md").read_text(encoding="utf-8")

        self.assertIn("pip installs Tuba, not Code_Aster", text)
        self.assertIn("Miniforge3-Linux-x86_64.sh", text)
        self.assertIn("conda create -y -n tuba-code-aster", text)
        self.assertIn("code-aster=18.0.12", text)
        self.assertIn("Native Linux", text)
        self.assertIn("sudo apt-get install -y libglu1-mesa", text)
        self.assertIn("python3 -m venv .venv", text)
        self.assertIn("https://github.com/jgwagenfeld/Tuba_v4.git", text)
        self.assertIn("python -m pip install .", text)
        self.assertNotIn("/opt/aster/bin/run_aster", text)
        self.assertNotIn("simvia/code_aster:stable", text)
        self.assertNotIn("your-tuba-v4-repo-url", text)

    def test_welcome_notebook_points_to_solver_setup_before_execution(self):
        notebook = json.loads(Path("notebooks/00_welcome_and_setup.ipynb").read_text(encoding="utf-8"))
        source = "\n".join("".join(cell.get("source", [])) for cell in notebook.get("cells", []))

        self.assertIn("pip installs Tuba, not Code_Aster", source)
        self.assertIn("python -m tuba.solver.code_aster_doctor --check", source)

    def test_readme_states_that_results_require_the_solver(self):
        """The README no longer teaches runtime setup, but it must still be
        honest that results are computed, never assumed."""
        text = Path("README.md").read_text(encoding="utf-8")

        self.assertIn("Code_Aster", text)
        self.assertIn("Tuba will not show you a number it did not compute", text)
        self.assertIn("a study has no results", text)
        self.assertIn("git clone --branch v4.0.1", text)

    def test_setup_documents_required_runtime_and_doctor(self):
        """Runtime setup lives on the Setup page; it owns every detail of it."""
        text = Path("docs/content/setup.md").read_text(encoding="utf-8")

        self.assertIn("TUBA_CODE_ASTER_EXEC_METHOD", text)
        self.assertIn("python -m tuba.solver.code_aster_doctor --check", text)
        self.assertIn("VS Code notebooks default to loading committed Code_Aster artifacts", text)
        self.assertIn("This installs Tuba from the checkout; it does not install Code_Aster", text)
        self.assertIn("sudo apt-get install -y libglu1-mesa", text)
        self.assertIn(".\\.venv\\Scripts\\jupyter.exe lab", text)
        self.assertIn(". .venv/bin/activate", text)

    def test_public_installation_uses_a_tagged_github_checkout(self):
        paths = [
            Path("README.md"),
            Path("docs/content/setup.md"),
            Path("docs/content/tutorial.md"),
            Path("notebooks/00_welcome_and_setup.ipynb"),
            Path("notebooks/autorouting_quick_iteration.ipynb"),
        ]
        texts = {path: path.read_text(encoding="utf-8") for path in paths}

        self.assertIn(
            "git clone --branch v4.0.1 --depth 1 https://github.com/jgwagenfeld/Tuba_v4.git",
            texts[Path("README.md")],
        )
        for path, text in texts.items():
            self.assertNotIn("pip install tuba", text, path)
            self.assertNotIn("pip install -e", text, path)

    def test_agent_instructions_state_code_aster_is_not_optional(self):
        text = Path("AGENTS.md").read_text(encoding="utf-8")

        self.assertIn("Code_Aster is not optional", text)
        self.assertIn("define piping structure", text)
        self.assertIn("evaluate it with Code_Aster", text)
        self.assertIn("display processed results", text)


if __name__ == "__main__":
    unittest.main()
