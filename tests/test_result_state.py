import unittest

import numpy as np

from tuba import Model
from tuba.analysis import AnalysisStudy
from tuba.analysis.results import fea_results_from_result_state, result_state_from_fea_results
from tuba.solver.base import ElementResult, FEAResults, NodeResult


class TestResultStateConversion(unittest.TestCase):
    def _model_study_and_results(self):
        model = Model(project_name="ResultState")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 0.0, 0.0])
        elem = model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")
        study = AnalysisStudy(
            id="analysis_study:Hot",
            model_revision=0,
            solver_name="Code_Aster",
            load_case="Hot",
            work_dir=None,
            input_files={"mail": "study.mail"},
            mesh_id="analysis_mesh:Hot",
        )
        results = FEAResults(solver_name="Code_Aster", load_case="Hot")
        results.node_results[n0] = NodeResult(
            node_id=n0,
            displacement=np.array([0.001, 0.0, 0.0, 0.0, 0.0, 0.0]),
            reaction_force=np.array([100.0, 0.0, -500.0, 0.0, 0.0, 0.0]),
        )
        results.node_results[n1] = NodeResult(
            node_id=n1,
            displacement=np.array([0.002, 0.0, 0.0, 0.0, 0.0, 0.0]),
        )
        results.analysis_node_results["pipe_bend_0_n1"] = NodeResult(
            node_id="pipe_bend_0_n1",
            displacement=np.array([0.010, 0.020, 0.030, 0.001, 0.002, 0.003]),
        )
        results.element_results[elem.id] = ElementResult(
            element_id=elem.id,
            forces_n1=np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0]),
            forces_n2=np.array([6.0, 5.0, 4.0, 3.0, 2.0, 1.0]),
            von_mises_n1=80.0e6,
            von_mises_n2=120.0e6,
            max_von_mises=120.0e6,
        )
        results.parser_diagnostics.append("diagnostic")
        results.tuyau_subpoints.append(
            {
                "field": "SIEQ_ELNO",
                "component": "VMIS",
                "unit": "Pa",
                "value": 42.0,
                "element_id": elem.id,
                "analysis_element_id": elem.id,
                "solver_element_label": "M1",
                "node_id": n0,
                "solver_node_label": "N1",
                "subpoint_index": 7,
                "centerline_position": [0.0, 0.0, 0.0],
                "display_position": [0.0, 0.0, 0.04],
                "position_source": "code_aster_tuyau_subpoint_formula",
            }
        )
        return model, study, results

    def test_result_state_from_fea_results_preserves_native_and_generated_displacements(self):
        model, study, results = self._model_study_and_results()

        state = result_state_from_fea_results(model=model, study=study, results=results)
        loaded = state.from_dict(state.to_dict())

        self.assertEqual(loaded, state)
        self.assertEqual(state.mesh_id, "analysis_mesh:Hot")
        self.assertEqual(state.node_displacements["N0"], (0.001, 0.0, 0.0, 0.0, 0.0, 0.0))
        self.assertEqual(state.node_displacements["pipe_bend_0_n1"], (0.010, 0.020, 0.030, 0.001, 0.002, 0.003))
        self.assertEqual(state.node_reactions["N0"], (100.0, 0.0, -500.0, 0.0, 0.0, 0.0))
        self.assertEqual(state.element_results["pipe_0"]["max_von_mises"], 120.0e6)
        self.assertEqual(state.metadata["analysis_node_ids"], ["pipe_bend_0_n1"])
        self.assertEqual(state.metadata["parser_diagnostics"], ["diagnostic"])
        self.assertEqual(state.metadata["tuyau_subpoints"][0]["subpoint_index"], 7)

    def test_fea_results_from_result_state_reconstructs_native_and_analysis_nodes(self):
        model, study, results = self._model_study_and_results()
        state = result_state_from_fea_results(model=model, study=study, results=results)

        reconstructed = fea_results_from_result_state(model=model, result_state=state)

        self.assertTrue(np.allclose(reconstructed.get_displacement("N0")[:3], [0.001, 0.0, 0.0]))
        self.assertTrue(
            np.allclose(reconstructed.get_analysis_displacement("pipe_bend_0_n1")[:3], [0.010, 0.020, 0.030])
        )
        self.assertEqual(reconstructed.get_max_von_mises("pipe_0"), 120.0e6)
        self.assertEqual(reconstructed.tuyau_subpoints[0]["value"], 42.0)

    def test_result_state_conversion_rejects_wrong_model_revision(self):
        model, study, results = self._model_study_and_results()
        model.revision = 1

        with self.assertRaises(ValueError):
            result_state_from_fea_results(model=model, study=study, results=results)


if __name__ == "__main__":
    unittest.main()
