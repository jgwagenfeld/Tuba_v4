import unittest

from tests.operating_state_fixtures import straight_pipe_hot_clash_fixture
from tuba.analysis import AnalysisStudy
from tuba.analysis.results import result_state_from_fea_results
from tuba.analysis.states import (
    create_cold_geometry_state,
    create_operating_geometry_state,
    create_visual_deformed_geometry_state,
)
from tuba.clash import TrimeshClashEngine


class TestDeformedClash(unittest.TestCase):
    def _result_state_for_fixture(self):
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
        return fixture, result_state_from_fea_results(model=fixture.model, study=study, results=fixture.results)

    def test_thermal_expansion_fixture_is_cold_clear_and_hot_clashing(self):
        fixture, result_state = self._result_state_for_fixture()
        cold_state = create_cold_geometry_state(fixture.model)
        operating_state = create_operating_geometry_state(model=fixture.model, result_state=result_state)

        cold_clashes = TrimeshClashEngine().check_model(fixture.model)
        operating_clashes = TrimeshClashEngine().check_operating_state(
            fixture.model,
            cold_state=cold_state,
            operating_state=operating_state,
            result_state=result_state,
            envelope_type="bare",
        )

        self.assertEqual(cold_clashes, [])
        self.assertEqual(len(operating_clashes), 1)
        self.assertEqual(operating_clashes[0].severity, "operating_only_hard")
        self.assertTrue(operating_clashes[0].metadata["introduced_by_deformation"])

    def test_visual_deformation_state_cannot_drive_engineering_clash(self):
        fixture, result_state = self._result_state_for_fixture()
        cold_state = create_cold_geometry_state(fixture.model)
        visual_state = create_visual_deformed_geometry_state(
            model=fixture.model,
            result_state=result_state,
            visual_scale=50.0,
        )

        with self.assertRaises(ValueError):
            TrimeshClashEngine().check_operating_state(
                fixture.model,
                cold_state=cold_state,
                operating_state=visual_state,
                result_state=result_state,
                envelope_type="bare",
            )


if __name__ == "__main__":
    unittest.main()
