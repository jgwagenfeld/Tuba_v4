import unittest

from tuba import Model
from tuba.analysis import GeometryState
from tuba.analysis.states import (
    create_cold_geometry_state,
    create_operating_geometry_state,
    create_visual_deformed_geometry_state,
)


class TestGeometryState(unittest.TestCase):
    def test_engineering_geometry_state_defaults_to_physical_scale(self):
        state = GeometryState(
            id="geometry_state:hot:physical",
            model_revision=7,
            state_type="operating",
            load_case="Hot",
            result_state_id="result_hot",
        )

        loaded = GeometryState.from_dict(state.to_dict())

        self.assertEqual(loaded, state)
        self.assertEqual(loaded.displacement_scale, 1.0)
        self.assertEqual(loaded.purpose, "engineering")

    def test_visual_geometry_state_can_use_exaggerated_scale(self):
        state = GeometryState(
            id="geometry_state:hot:visual_x50",
            model_revision=7,
            state_type="deformed",
            load_case="Hot",
            result_state_id="result_hot",
            displacement_scale=50.0,
            purpose="visualization",
        )

        self.assertEqual(GeometryState.from_dict(state.to_dict()), state)

    def test_engineering_geometry_state_rejects_visual_deformation_scale(self):
        with self.assertRaises(ValueError):
            GeometryState(
                id="geometry_state:hot:bad",
                model_revision=7,
                state_type="operating",
                load_case="Hot",
                result_state_id="result_hot",
                displacement_scale=50.0,
                purpose="engineering",
            )

    def test_geometry_state_helpers_create_cold_operating_and_visual_states(self):
        model = Model(project_name="GeometryStateHelpers")
        model.revision = 3

        cold = create_cold_geometry_state(model)
        operating = create_operating_geometry_state(model=model, result_state_id="result_hot", load_case="Hot", safety_factor=1.25)
        visual = create_visual_deformed_geometry_state(
            model=model,
            result_state_id="result_hot",
            load_case="Hot",
            visual_scale=50.0,
        )

        self.assertEqual(cold.state_type, "cold")
        self.assertIsNone(cold.result_state_id)
        self.assertEqual(operating.state_type, "operating")
        self.assertEqual(operating.displacement_scale, 1.0)
        self.assertEqual(operating.safety_factor, 1.25)
        self.assertEqual(visual.purpose, "visualization")
        self.assertEqual(visual.displacement_scale, 50.0)

    def test_operating_helper_requires_positive_safety_factor(self):
        with self.assertRaises(ValueError):
            create_operating_geometry_state(
                model=Model(project_name="GeometryStateHelpers"),
                result_state_id="result_hot",
                load_case="Hot",
                safety_factor=0.0,
            )


if __name__ == "__main__":
    unittest.main()
