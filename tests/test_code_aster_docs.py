import json
import unittest
from pathlib import Path

import yaml


class TestCodeAsterDocs(unittest.TestCase):
    def test_shared_environment_selects_the_installed_python_bridge(self):
        recipe = yaml.safe_load(Path("environment.yml").read_text(encoding="utf-8"))
        text = Path("docs/content/setup.md").read_text(encoding="utf-8")
        dependencies = recipe["dependencies"]
        self.assertIn("code-aster=18.0.12=*nompi*", dependencies)
        self.assertIn("numpy=2.4.6", dependencies)
        self.assertEqual(recipe["variables"]["TUBA_CODE_ASTER_EXEC_METHOD"], "python_bridge")
        self.assertEqual(recipe["variables"]["TUBA_CODE_ASTER_PYTHON"], "python")
        self.assertIn("conda env create -f environment.yml", text)
        self.assertIn("conda activate tuba", text)
        self.assertIn("--output .build/first-review --force", text)
        self.assertIn("tuba-viewer .build/first-review/review_scene --open", text)

    def test_installation_walkthrough_documents_wsl_conda_runtime(self):
        text = Path("docs/content/setup.md").read_text(encoding="utf-8")

        self.assertIn("`uv sync` installs Tuba", text)
        self.assertIn("does not install Code_Aster", text)
        self.assertIn("uv sync --extra course --extra code-aster-rmed --locked", text)
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

        self.assertIn("uv installs Tuba, not Code_Aster", text)
        self.assertIn("Miniforge3-Linux-x86_64.sh", text)
        self.assertIn("conda create -y -n tuba-code-aster", text)
        self.assertIn("code-aster=18.0.12", text)
        self.assertIn("Native Linux", text)
        self.assertIn("sudo apt-get install -y libglu1-mesa", text)
        self.assertIn("uv sync --extra course --locked", text)
        self.assertIn("https://github.com/jgwagenfeld/Tuba_v4.git", text)
        self.assertIn("Tuba does not need conda", text)
        self.assertNotIn("/opt/aster/bin/run_aster", text)
        self.assertNotIn("simvia/code_aster:stable", text)
        self.assertNotIn("your-tuba-v4-repo-url", text)

    def test_readme_states_that_results_require_the_solver(self):
        """The README states the solver and result-import requirements."""
        text = Path("README.md").read_text(encoding="utf-8")

        self.assertIn("Code_Aster", text)
        self.assertIn("results require a completed Code_Aster run", text)
        self.assertIn("and imported result files", text)
        self.assertIn("does not run an analysis", text)
        self.assertIn("git clone --branch main", text)

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

    def test_public_installation_uses_the_development_checkout(self):
        paths = [
            Path("README.md"),
            Path("docs/content/setup.md"),
            Path("docs/content/tutorial.md"),
            Path("notebooks/04_visualization_gallery.ipynb"),
            Path("notebooks/07_bim_data_exchange.ipynb"),
        ]
        texts = {path: path.read_text(encoding="utf-8") for path in paths}

        self.assertIn(
            "git clone --branch main --depth 1 https://github.com/jgwagenfeld/Tuba_v4.git",
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
