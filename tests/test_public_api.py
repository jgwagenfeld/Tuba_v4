import subprocess
import sys
import inspect
import unittest


class TestPublicApi(unittest.TestCase):
    def test_code_aster_is_the_model_solver_contract(self):
        from tuba import Model
        import tuba.solver.base as result_types

        self.assertNotIn("solver", inspect.signature(Model.solve).parameters)
        self.assertFalse(hasattr(result_types, "BaseSolver"))

    def test_import_does_not_load_optional_geometry_stack(self):
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys, tuba; "
                "assert 'scipy' not in sys.modules; "
                "assert 'trimesh' not in sys.modules; "
                "assert 'meshio' not in sys.modules",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual("", completed.stderr)
        self.assertEqual(0, completed.returncode)

    def test_step_analysis_importer_does_not_require_scipy(self):
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; import tuba.builder, tuba.geometry.step_analysis_importer; "
                "assert 'scipy' not in sys.modules",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual("", completed.stderr)
        self.assertEqual(0, completed.returncode)

    def test_public_facade_contains_only_the_stable_engineering_entry_points(self):
        import tuba
        from tuba import AnalysisRun, Model, Operation

        self.assertEqual(tuba.__all__, ["AnalysisRun", "Model", "Operation"])
        self.assertIsNotNone(AnalysisRun)
        self.assertIsNotNone(Model)
        self.assertIsNotNone(Operation)


if __name__ == "__main__":
    unittest.main()
