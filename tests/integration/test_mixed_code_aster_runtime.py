import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from tests.test_mixed_code_aster_export import build_mixed_fixture
from tuba.solver.aster import CodeAsterSolver


class TestMixedCodeAsterRuntime(unittest.TestCase):
    def test_mixed_export_runtime_gate_is_explicit(self):
        model = build_mixed_fixture()
        with TemporaryDirectory() as tmpdir:
            study = CodeAsterSolver(work_dir=tmpdir).export_mixed_analysis_study(model, "Hot", tmpdir)
            self.assertTrue(Path(study.input_files["comm"]).exists())
            self.assertTrue(Path(study.input_files["med"]).exists())
            self.assertEqual(study.metadata["result_status"], "export_only")
            self.assertEqual(study.metadata["code_aster_solve_ready"], False)
            self.assertIn("diagnostic handoff", study.metadata["runtime_blocker"])

    def test_mixed_export_only_stops_before_code_aster_execution(self):
        model = build_mixed_fixture()
        with TemporaryDirectory() as tmpdir:
            solver = CodeAsterSolver(work_dir=tmpdir)
            study = solver.export_mixed_analysis_study(model, "Hot", tmpdir)
            with patch.object(solver, "_execute") as execute:
                with self.assertRaisesRegex(RuntimeError, "export-only"):
                    solver.solve_exported_study(model, study)
            execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
