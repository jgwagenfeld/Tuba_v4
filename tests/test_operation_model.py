import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np

from tuba import Model, Operation
from tuba.analysis import AnalysisRun, AnalysisStudy, ResultState
from tuba.compliance import ASMEB313Evaluator
from tuba.solver.aster import CodeAsterSolver
from tuba.solver.base import ElementResult, FEAResults


class TestOperationModel(unittest.TestCase):
    def test_code_aster_solve_returns_provenance_bearing_analysis_run(self):
        model = _base_model("SolveRun")
        model.define_operation("Operating")
        results = FEAResults(solver_name="Code_Aster", load_case="Operating")

        with TemporaryDirectory() as tmpdir:
            study = AnalysisStudy(
                id="analysis_study:Operating",
                model_revision=0,
                solver_name="Code_Aster",
                load_case="Operating",
                work_dir=tmpdir,
                input_files={},
                mesh_id="analysis_mesh:Operating",
            )
            state = ResultState(
                id="result_state:Operating",
                study_id=study.id,
                model_revision=0,
                solver_name="Code_Aster",
                load_case="Operating",
                mesh_id=study.mesh_id,
                node_displacements={},
                node_reactions={},
                element_results={},
            )
            expected = AnalysisRun(study=study, results=results, result_state=state)
            solver = CodeAsterSolver(work_dir=tmpdir)

            with (
                patch("tuba.solver.aster.load_and_validate_artifact_chain", return_value=(study, study, None, None)),
                patch.object(solver, "_execute", return_value=object()),
                patch("tuba.solver.aster.write_code_aster_execution_attestation"),
                patch.object(solver, "parse_result_artifacts", return_value=results),
                patch("tuba.analysis.code_aster_artifacts.import_code_aster_artifacts", return_value=expected) as importer,
            ):
                run = solver.solve_exported_study(model, study)

        self.assertIs(run, expected)
        importer.assert_called_once_with(model=model, work_dir=Path(tmpdir), study=study)

    def test_operation_roundtrips_without_requiring_load_case(self):
        model = Model(project_name="OperationRoundtrip")
        op = model.define_operation(
            "Operating",
            gravity=True,
            pressure=1.6e6,
            temperature=120.0,
            ref_temperature=20.0,
            metadata={"source": "test"},
        )

        self.assertIsInstance(op, Operation)
        data = model.to_dict()
        self.assertEqual(data["operations"]["Operating"]["internal_pressure"], 1.6e6)

        loaded = Model.from_dict(data)

        self.assertEqual(loaded.operations["Operating"].internal_pressure, 1.6e6)
        self.assertEqual(loaded.operations["Operating"].metadata, {"source": "test"})
        self.assertEqual(loaded.load_cases, {})

    def test_pre_operation_model_fixture_still_loads_validates_and_exports(self):
        fixture = Path(__file__).resolve().parent / "fixtures" / "pre_operation_model.json"
        model = Model.from_dict(json.loads(fixture.read_text(encoding="utf-8")))

        model.validate()
        self.assertEqual(model.operations, {})

        with TemporaryDirectory() as tmpdir:
            CodeAsterSolver(work_dir=tmpdir).export_study(model, "Hot", tmpdir)
            self.assertTrue((Path(tmpdir) / "study.comm").exists())

    def test_uniform_operation_exports_same_comm_as_equivalent_load_case(self):
        load_case_model = _base_model("LoadCaseModel")
        load_case_model.define_load_case("Hot", gravity=True, pressure=1.0e6, temperature=120.0, ref_temperature=20.0)
        operation_model = _base_model("OperationModel")
        operation_model.define_operation("Hot", gravity=True, pressure=1.0e6, temperature=120.0, ref_temperature=20.0)

        with TemporaryDirectory() as load_dir, TemporaryDirectory() as op_dir:
            CodeAsterSolver(work_dir=load_dir).export_study(load_case_model, "Hot", load_dir)
            CodeAsterSolver(work_dir=op_dir).export_study(operation_model, "Hot", op_dir)

            self.assertEqual(
                (Path(load_dir) / "study.comm").read_text(encoding="utf-8"),
                (Path(op_dir) / "study.comm").read_text(encoding="utf-8"),
            )

    def test_model_solve_accepts_operation_name(self):
        model = _base_model("SolveOperation")
        model.define_operation("Operating")

        with patch("tuba.solver.aster.CodeAsterSolver") as solver_class:
            solver = solver_class.return_value
            solver.solve.return_value = "solved"

            result = model.solve(operation="Operating", work_dir="ignored")

        self.assertEqual(result, "solved")
        solver_class.assert_called_once_with(work_dir="ignored")
        solver.solve.assert_called_once_with(model, "Operating")

    def test_compliance_lookup_accepts_operation_name(self):
        model = _base_model("ComplianceOperation")
        model.materials["Steel"].allowable_stress = {20.0: 120e6, 120.0: 110e6}
        model.define_operation("Operating", pressure=1.0e6, temperature=120.0, ref_temperature=20.0)
        results = FEAResults(solver_name="Code_Aster", load_case="Operating")
        moment = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 100.0])
        results.element_results["pipe_str_0"] = ElementResult("pipe_str_0", moment, moment)

        report = ASMEB313Evaluator().evaluate(model, results)

        self.assertEqual(report.load_case, "Operating")
        self.assertEqual(len(report.results), 2)


def _base_model(name: str) -> Model:
    model = Model(project_name=name)
    model.add_material("Steel", E=2.0e11, nu=0.3, alpha=1.2e-5)
    model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
    n0 = model.add_node((0.0, 0.0, 0.0))
    n1 = model.add_node((1.0, 0.0, 0.0))
    model.add_element(
        id="pipe_str_0",
        type="pipe_straight",
        n1=n0,
        n2=n1,
        section="PipeSec",
        material="Steel",
    )
    return model


if __name__ == "__main__":
    unittest.main()
