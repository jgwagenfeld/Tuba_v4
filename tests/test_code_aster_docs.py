import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class TestCodeAsterDocs(unittest.TestCase):
    def test_readme_documents_required_runtime_and_doctor(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("Code_Aster execution is required", text)
        self.assertIn("python -m tuba.solver.code_aster_doctor", text)
        self.assertIn("docs/code_aster_installation.md", text)
        self.assertIn("TUBA_CODE_ASTER_PYTHON", text)
        self.assertIn("TUBA_CODE_ASTER_WSL_DISTRO", text)
        self.assertIn("TUBA_RUN_CODE_ASTER_INTEGRATION", text)

    def test_agents_keeps_ada_py_license_boundary(self):
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

        self.assertIn("Do not vendor or copy ada-py", text)
        self.assertIn("GPL-3.0-or-later", text)
        self.assertIn("Code_Aster execution is not optional", text)

    def test_installation_walkthrough_has_wsl_conda_and_validation_steps(self):
        text = (ROOT / "docs" / "code_aster_installation.md").read_text(encoding="utf-8")

        self.assertIn("conda create -n tuba-code-aster", text)
        self.assertIn("conda-forge", text)
        self.assertIn("run_aster --version", text)
        self.assertIn("TUBA_CODE_ASTER_EXEC_METHOD", text)
        self.assertIn("TUBA_CODE_ASTER_WSL_DISTRO", text)
        self.assertIn("TUBA_RUN_CODE_ASTER_INTEGRATION", text)
        self.assertIn("python -m tuba.solver.code_aster_doctor", text)


if __name__ == "__main__":
    unittest.main()
