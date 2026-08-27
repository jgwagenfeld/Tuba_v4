import unittest
from dataclasses import replace

from tuba.analysis import AnalysisRun, AnalysisStudy, ResultState
from tuba.solver.base import FEAResults


class TestAnalysisStudy(unittest.TestCase):
    def test_analysis_run_links_transient_results_to_persistent_state(self):
        study = AnalysisStudy(
            id="study_hot",
            model_revision=7,
            solver_name="Code_Aster",
            load_case="Hot",
            work_dir="solver/hot",
            input_files={},
            mesh_id="mesh_hot",
        )
        state = ResultState(
            id="result_hot",
            study_id=study.id,
            model_revision=study.model_revision,
            solver_name=study.solver_name,
            load_case=study.load_case,
            mesh_id=study.mesh_id,
            node_displacements={},
            node_reactions={},
            element_results={},
        )
        results = FEAResults(solver_name=study.solver_name, load_case=study.load_case)

        run = AnalysisRun(study=study, results=results, result_state=state)

        self.assertIs(run.results, results)
        self.assertIs(run.result_state, state)
        with self.assertRaisesRegex(ValueError, "does not belong"):
            AnalysisRun(study=study, results=results, result_state=replace(state, study_id="other"))

    def test_analysis_study_roundtrips_with_metadata_and_files(self):
        study = AnalysisStudy(
            id="study_hot",
            model_revision=7,
            solver_name="code_aster",
            load_case="Hot",
            work_dir="solver/hot",
            input_files={"mail": "solver/hot/study.mail", "comm": "solver/hot/study.comm"},
            mesh_id="mesh_hot",
            metadata={"temperature_c": 120.0},
        )

        loaded = AnalysisStudy.from_dict(study.to_dict())

        self.assertEqual(loaded, study)
        self.assertEqual(loaded.metadata["temperature_c"], 120.0)

    def test_result_state_roundtrips_solver_vectors(self):
        state = ResultState(
            id="result_hot",
            study_id="study_hot",
            model_revision=7,
            solver_name="code_aster",
            load_case="Hot",
            mesh_id="mesh_hot",
            node_displacements={"N0": (0.0, 0.01, 0.0, 0.0, 0.0, 0.0)},
            node_reactions={"N0": (100.0, 0.0, -500.0, 0.0, 0.0, 0.0)},
            element_results={"pipe_0": {"max_von_mises": 120.0e6}},
            files={"rmed": "solver/hot/result.rmed"},
            metadata={"diagnostics": []},
        )

        loaded = ResultState.from_dict(state.to_dict())

        self.assertEqual(loaded, state)
        self.assertEqual(loaded.node_displacements["N0"], (0.0, 0.01, 0.0, 0.0, 0.0, 0.0))

    def test_analysis_study_requires_stable_identity(self):
        with self.assertRaises(ValueError):
            AnalysisStudy(
                id="",
                model_revision=1,
                solver_name="code_aster",
                load_case="Hot",
                work_dir=None,
                input_files={},
                mesh_id="mesh_hot",
            )


if __name__ == "__main__":
    unittest.main()
