import unittest
from pathlib import Path


class TestCodeAsterDocs(unittest.TestCase):
    def test_installation_walkthrough_documents_wsl_conda_runtime(self):
        text = Path("docs/code_aster_installation.md").read_text(encoding="utf-8")

        self.assertIn("conda create -n tuba-code-aster", text)
        self.assertIn("code-aster", text)
        self.assertIn("run_aster --version", text)
        self.assertIn("TUBA_CODE_ASTER_EXEC_METHOD", text)
        self.assertIn("TUBA_CODE_ASTER_WSL_DISTRO", text)
        self.assertIn("TUBA_RUN_CODE_ASTER_INTEGRATION", text)
        self.assertIn("python -m tuba.solver.code_aster_doctor", text)

    def test_readme_states_code_aster_is_core_workflow(self):
        text = Path("README.md").read_text(encoding="utf-8")

        self.assertIn("Code_Aster is required for the full Tuba workflow", text)
        self.assertIn("docs/code_aster_installation.md", text)
        self.assertIn("TUBA_CODE_ASTER_EXEC_METHOD", text)

    def test_agent_instructions_state_code_aster_is_not_optional(self):
        text = Path("AGENTS.md").read_text(encoding="utf-8")

        self.assertIn("Code_Aster is not optional", text)
        self.assertIn("define piping structure", text)
        self.assertIn("evaluate it with Code_Aster", text)
        self.assertIn("display processed results", text)


if __name__ == "__main__":
    unittest.main()
