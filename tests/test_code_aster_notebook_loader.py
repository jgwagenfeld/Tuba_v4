import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tuba import Model
from tuba.analysis.code_aster_notebook import load_or_run_code_aster_results
from tuba.solver.aster import CodeAsterSolver


class TestCodeAsterNotebookLoader(unittest.TestCase):
    def _model(self):
        model = Model(project_name="NotebookAsterLoader")
        model.add_material("Steel", E=2.0e11, nu=0.3, allowable_stress={20.0: 137e6})
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 0.0, 0.0])
        model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")
        model.add_support(node=n0, type="anchor", id="support_anchor_0")
        model.define_load_case("Hot", gravity=True, temperature=120.0, ref_temperature=20.0)
        return model, n0, n1

    def test_missing_tables_run_exported_code_aster_study_before_importing(self):
        model, n0, n1 = self._model()

        class SolverThatWritesTables:
            instances = []

            def __init__(self, work_dir=None, exec_method="wsl", docker_image=None):
                self.work_dir = Path(work_dir)
                self.exec_method = exec_method
                self.docker_image = docker_image
                self.ran_exported_study = False
                self.instances.append(self)

            def export_analysis_study(self, model, load_case_name, output_dir):
                return CodeAsterSolver(work_dir=output_dir).export_analysis_study(model, load_case_name, output_dir)

            def solve_exported_study(self, model, study):
                self.ran_exported_study = True
                _write_solver_tables(Path(study.work_dir), n0=n0, n1=n1)

        with TemporaryDirectory() as tmpdir:
            loaded = load_or_run_code_aster_results(
                model,
                "Hot",
                tmpdir,
                solver_factory=SolverThatWritesTables,
            )

        self.assertTrue(loaded.ran_solver)
        self.assertTrue(SolverThatWritesTables.instances[0].ran_exported_study)
        self.assertEqual(loaded.results.solver_name, "Code_Aster")
        self.assertEqual(loaded.artifact.result_state.node_displacements[n1][:3], (0.0, 0.015, 0.0))
        self.assertEqual(loaded.artifact.result_state.element_results["pipe_0"]["max_von_mises"], 120.0e6)

    def test_run_solver_false_keeps_export_only_mode_explicit(self):
        model, _n0, _n1 = self._model()

        with TemporaryDirectory() as tmpdir:
            with self.assertRaises(FileNotFoundError) as raised:
                load_or_run_code_aster_results(model, "Hot", tmpdir, run_solver=False)

        self.assertIn("RUN_CODE_ASTER", str(raised.exception))

    def test_notebook_loader_defaults_to_auto_runtime(self):
        model, _n0, _n1 = self._model()

        class CapturingSolver:
            instances = []

            def __init__(self, work_dir=None, exec_method="wsl", docker_image=None):
                self.work_dir = Path(work_dir)
                self.exec_method = exec_method
                self.docker_image = docker_image
                self.instances.append(self)

            def export_analysis_study(self, model, load_case_name, output_dir):
                return CodeAsterSolver(work_dir=output_dir).export_analysis_study(model, load_case_name, output_dir)

            def solve_exported_study(self, model, study):
                raise RuntimeError("test stops before solver execution")

        with TemporaryDirectory() as tmpdir:
            with self.assertRaises(RuntimeError):
                load_or_run_code_aster_results(model, "Hot", tmpdir, solver_factory=CapturingSolver)

        self.assertEqual(CapturingSolver.instances[0].exec_method, "auto")


def _write_solver_tables(work_dir: Path, *, n0: str, n1: str) -> None:
    (work_dir / "study_depl.csv").write_text(
        "\n".join(
            [
                "NOEUD,DX,DY,DZ,DRX,DRY,DRZ",
                f"{n0},0.0,0.0,0.0,0.0,0.0,0.0",
                f"{n1},0.0,0.015,0.0,0.0,0.0,0.0",
            ]
        ),
        encoding="utf-8",
    )
    (work_dir / "study_effo.csv").write_text(
        "\n".join(
            [
                "MAILLE,NOEUD,N,VY,VZ,MT,MFY,MFZ",
                f"pipe_0,{n0},10.0,20.0,30.0,1.0,2.0,3.0",
                f"pipe_0,{n1},11.0,21.0,31.0,4.0,5.0,6.0",
            ]
        ),
        encoding="utf-8",
    )
    (work_dir / "study_reac.csv").write_text(
        "\n".join(
            [
                "NOEUD,DX,DY,DZ,DRX,DRY,DRZ",
                f"{n0},1000.0,0.0,-250.0,0.0,0.0,0.0",
            ]
        ),
        encoding="utf-8",
    )
    (work_dir / "study_sieq.csv").write_text(
        "\n".join(
            [
                "MAILLE,NOEUD,VMIS",
                f"pipe_0,{n0},80000000.0",
                f"pipe_0,{n1},120000000.0",
            ]
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
