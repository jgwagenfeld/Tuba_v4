import unittest

from tuba import Model
from tuba.analysis import GeometryState, ResultState
from tuba.geometry.deformed import build_deformed_envelopes


class TestDeformedEnvelopes(unittest.TestCase):
    def _model_state_and_geometry(self):
        model = Model(project_name="DeformedEnvelopes")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([2.0, 0.0, 0.0])
        model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")
        model.add_insulation_spec("mw_50", material="mineral_wool", thickness_m=0.05)
        model.assign_insulation("element:pipe_0", "mw_50")
        result_state = ResultState(
            id="result_hot",
            study_id="study_hot",
            model_revision=0,
            solver_name="Code_Aster",
            load_case="Hot",
            mesh_id=None,
            node_displacements={
                n0: (0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
                n1: (0.0, 0.2, 0.0, 0.0, 0.0, 0.0),
            },
            node_reactions={},
            element_results={},
        )
        geometry_state = GeometryState(
            id="geometry_state:hot:physical",
            model_revision=0,
            state_type="operating",
            load_case="Hot",
            result_state_id=result_state.id,
        )
        return model, result_state, geometry_state

    def test_deformed_envelope_uses_insulation_radius_and_bounds(self):
        model, result_state, geometry_state = self._model_state_and_geometry()

        envelopes = build_deformed_envelopes(
            model=model,
            result_state=result_state,
            geometry_state=geometry_state,
            envelope_type="insulation",
        )

        self.assertEqual(len(envelopes), 1)
        envelope = envelopes[0]
        self.assertEqual(str(envelope.entity), "element:pipe_0")
        self.assertEqual(envelope.envelope_type, "insulation")
        self.assertAlmostEqual(envelope.radius_m, 0.10)
        self.assertEqual(envelope.polyline, ((0.0, 0.0, 0.0), (2.0, 0.2, 0.0)))
        self.assertEqual(envelope.bounds, (-0.1, -0.1, -0.1, 2.1, 0.30000000000000004, 0.1))

    def test_clearance_envelope_adds_clearance_to_effective_radius(self):
        model, result_state, geometry_state = self._model_state_and_geometry()

        envelopes = build_deformed_envelopes(
            model=model,
            result_state=result_state,
            geometry_state=geometry_state,
            envelope_type="clearance",
            clearance_m=0.05,
        )

        self.assertAlmostEqual(envelopes[0].radius_m, 0.15)

    def test_deformed_envelope_cache_reuses_same_state_and_invalidates_new_state(self):
        model, result_state, geometry_state = self._model_state_and_geometry()

        first = build_deformed_envelopes(model=model, result_state=result_state, geometry_state=geometry_state)
        second = build_deformed_envelopes(model=model, result_state=result_state, geometry_state=geometry_state)
        visual_state = GeometryState(
            id="geometry_state:hot:visual",
            model_revision=0,
            state_type="deformed",
            load_case="Hot",
            result_state_id=result_state.id,
            displacement_scale=10.0,
            purpose="visualization",
        )
        visual = build_deformed_envelopes(model=model, result_state=result_state, geometry_state=visual_state)

        self.assertIs(first, second)
        self.assertIsNot(first, visual)


if __name__ == "__main__":
    unittest.main()
