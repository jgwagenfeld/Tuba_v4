import unittest

from tuba import Model
from tuba.analysis import ResultState
from tuba.analysis.states import create_cold_geometry_state, create_operating_geometry_state
from tuba.clash import TrimeshClashEngine


class TestOperatingClash(unittest.TestCase):
    def test_operating_state_reports_deformation_introduced_clash(self):
        model = Model(project_name="OperatingClash")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([2.0, 0.0, 0.0])
        model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")
        model.add_obstacle(
            id="tray_0",
            type="cuboid",
            min_point=[0.5, 0.08, -0.10],
            max_point=[1.5, 0.18, 0.10],
        )
        result_state = ResultState(
            id="result_hot",
            study_id="study_hot",
            model_revision=0,
            solver_name="Code_Aster",
            load_case="Hot",
            mesh_id=None,
            node_displacements={
                n0: (0.0, 0.06, 0.0, 0.0, 0.0, 0.0),
                n1: (0.0, 0.06, 0.0, 0.0, 0.0, 0.0),
            },
            node_reactions={},
            element_results={},
        )
        cold_state = create_cold_geometry_state(model)
        operating_state = create_operating_geometry_state(model=model, result_state=result_state)

        cold_clashes = TrimeshClashEngine().check_model(model)
        operating_clashes = TrimeshClashEngine().check_operating_state(
            model,
            cold_state=cold_state,
            operating_state=operating_state,
            result_state=result_state,
            envelope_type="bare",
        )

        self.assertEqual(cold_clashes, [])
        self.assertEqual(len(operating_clashes), 1)
        clash = operating_clashes[0]
        self.assertEqual(clash.severity, "operating_only_hard")
        self.assertEqual(str(clash.left), "element:pipe_0")
        self.assertEqual(str(clash.right), "obstacle:tray_0")
        self.assertTrue(clash.metadata["introduced_by_deformation"])
        self.assertEqual(clash.metadata["load_case"], "Hot")
        self.assertEqual(clash.metadata["geometry_state"], operating_state.id)
        self.assertGreater(clash.metadata["cold_distance_m"], clash.metadata["operating_distance_m"])


if __name__ == "__main__":
    unittest.main()
