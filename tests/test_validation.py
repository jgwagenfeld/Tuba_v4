import unittest

from tuba import Model
from tuba.validation import ModelValidationError, validate_model


class TestModelValidation(unittest.TestCase):
    def test_valid_model_passes(self):
        model = Model(project_name="Valid")
        model.add_material("Steel", E=2.0e11, nu=0.3)
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

        validate_model(model)

    def test_missing_node_reference_fails(self):
        model = Model(project_name="Invalid")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node((0.0, 0.0, 0.0))
        model.add_element(
            id="pipe_str_0",
            type="pipe_straight",
            n1=n0,
            n2="N999",
            section="PipeSec",
            material="Steel",
        )

        with self.assertRaises(ModelValidationError) as ctx:
            validate_model(model)

        self.assertIn("references missing node", str(ctx.exception))

    def test_duplicate_element_id_fails(self):
        model = Model(project_name="Invalid")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node((0.0, 0.0, 0.0))
        n1 = model.add_node((1.0, 0.0, 0.0))
        kwargs = {
            "id": "pipe_str_0",
            "type": "pipe_straight",
            "n1": n0,
            "n2": n1,
            "section": "PipeSec",
            "material": "Steel",
        }
        model.add_element(**kwargs)
        model.add_element(**kwargs)

        with self.assertRaises(ModelValidationError) as ctx:
            validate_model(model)

        self.assertIn("Duplicate element id", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
