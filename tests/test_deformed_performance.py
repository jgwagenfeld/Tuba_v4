import unittest

from tuba import Model
from tuba.analysis import GeometryState, ResultState
from tuba.clash.engine import ClashEngine
from tuba.clash.operating import candidate_obstacle_pairs_for_envelopes
from tuba.geometry.deformed import build_deformed_envelope_index, build_deformed_envelopes


class TestDeformedPerformance(unittest.TestCase):
    def _sparse_model_state_and_geometry(self, count=16):
        model = Model(project_name="DeformedPerformance")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        model.add_insulation_spec("thin", material="mineral_wool", thickness_m=0.02)
        node_displacements = {}
        for idx in range(count):
            y = float(idx * 4)
            n0 = model.add_node([0.0, y, 0.0])
            n1 = model.add_node([2.0, y, 0.0])
            element_id = f"pipe_{idx}"
            model.add_element(id=element_id, type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")
            model.assign_insulation(f"element:{element_id}", "thin")
            model.add_obstacle(
                id=f"rack_{idx}",
                type="cuboid",
                min_point=[0.9, y + 0.04, -0.15],
                max_point=[1.1, y + 0.14, 0.15],
            )
            node_displacements[n0] = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
            node_displacements[n1] = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        result_state = ResultState(
            id="result_hot_sparse",
            study_id="study_hot_sparse",
            model_revision=0,
            solver_name="Code_Aster",
            load_case="Hot",
            mesh_id=None,
            node_displacements=node_displacements,
            node_reactions={},
            element_results={},
        )
        geometry_state = GeometryState(
            id="geometry_state:hot:physical:sparse",
            model_revision=0,
            state_type="operating",
            load_case="Hot",
            result_state_id=result_state.id,
        )
        cold_state = GeometryState(id="geometry_state:cold:sparse", model_revision=0, state_type="cold")
        return model, result_state, geometry_state, cold_state

    def test_deformed_envelope_index_prunes_obstacle_candidates(self):
        model, result_state, geometry_state, _cold_state = self._sparse_model_state_and_geometry()
        envelopes = build_deformed_envelopes(model=model, result_state=result_state, geometry_state=geometry_state)

        index = build_deformed_envelope_index(envelopes)
        pairs = candidate_obstacle_pairs_for_envelopes(model=model, envelopes=envelopes)

        self.assertEqual(len(index), len(envelopes))
        self.assertEqual(len(pairs), len(envelopes))
        self.assertLess(len(pairs), len(envelopes) * len(model.obstacles))

    def test_operating_clash_reuses_cached_deformed_envelopes(self):
        model, result_state, geometry_state, cold_state = self._sparse_model_state_and_geometry(count=4)
        first = build_deformed_envelopes(model=model, result_state=result_state, geometry_state=geometry_state)

        ClashEngine().check_operating_state(
            model,
            cold_state=cold_state,
            operating_state=geometry_state,
            result_state=result_state,
        )
        second = build_deformed_envelopes(model=model, result_state=result_state, geometry_state=geometry_state)

        self.assertIs(first, second)


if __name__ == "__main__":
    unittest.main()
