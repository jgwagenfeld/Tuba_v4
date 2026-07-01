import unittest

from tests.operating_state_fixtures import straight_pipe_hot_clash_fixture
from tuba.analysis import AnalysisStudy, ResultState
from tuba.analysis.results import result_state_from_fea_results
from tuba.analysis.states import create_cold_geometry_state, create_operating_geometry_state
from tuba.optimization.objectives import ClashObjective, ObjectiveEvaluator


class TestRoutingObjectives(unittest.TestCase):
    def _fixture_context(self):
        fixture = straight_pipe_hot_clash_fixture()
        study = AnalysisStudy(
            id="analysis_study:Hot",
            model_revision=0,
            solver_name=fixture.results.solver_name,
            load_case="Hot",
            work_dir=None,
            input_files={},
            mesh_id="analysis_mesh:Hot",
        )
        result_state = result_state_from_fea_results(model=fixture.model, study=study, results=fixture.results)
        cold_state = create_cold_geometry_state(fixture.model)
        operating_state = create_operating_geometry_state(model=fixture.model, result_state=result_state)
        return fixture, result_state, cold_state, operating_state

    def test_clash_objective_penalizes_operating_state_clashes_from_result_state(self):
        fixture, result_state, cold_state, operating_state = self._fixture_context()

        score = ClashObjective(weight=1.0).evaluate(
            fixture.model,
            result_state=result_state,
            cold_state=cold_state,
            geometry_state=operating_state,
            envelope_type="bare",
        )
        details = ClashObjective(weight=1.0).get_details(
            fixture.model,
            result_state=result_state,
            cold_state=cold_state,
            geometry_state=operating_state,
            envelope_type="bare",
        )

        self.assertEqual(score, 500.0)
        self.assertEqual(details["operating_clash_count"], 1)
        self.assertEqual(details["operating_clashes"][0]["severity"], "operating_only_hard")

    def test_operating_clash_score_is_worse_than_clear_operating_state(self):
        fixture, _result_state, cold_state, operating_state = self._fixture_context()
        clear_state = ResultState(
            id="result_clear",
            study_id="study_hot",
            model_revision=0,
            solver_name="Code_Aster",
            load_case="Hot",
            mesh_id=None,
            node_displacements={node_id: (0.0, 0.0, 0.0, 0.0, 0.0, 0.0) for node_id in fixture.model.nodes},
            node_reactions={},
            element_results={},
        )
        clear_geometry = create_operating_geometry_state(model=fixture.model, result_state=clear_state)

        clashing = ObjectiveEvaluator([ClashObjective(weight=1.0)]).evaluate_model(
            fixture.model,
            result_state=_result_state,
            cold_state=cold_state,
            geometry_state=operating_state,
            envelope_type="bare",
        )
        clear = ObjectiveEvaluator([ClashObjective(weight=1.0)]).evaluate_model(
            fixture.model,
            result_state=clear_state,
            cold_state=cold_state,
            geometry_state=clear_geometry,
            envelope_type="bare",
        )

        self.assertGreater(clashing, clear)


if __name__ == "__main__":
    unittest.main()
