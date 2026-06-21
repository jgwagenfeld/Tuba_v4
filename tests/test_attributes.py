import unittest

from tuba import EntityRef, Model
from tuba.attributes import InsulationSpec
from tuba.schema import validate_model_dict
from tuba.validation import ModelValidationError, validate_model


class TestAttributes(unittest.TestCase):
    def _model_with_two_elements(self):
        model = Model(project_name="Attributes")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 0.0, 0.0])
        n2 = model.add_node([2.0, 0.0, 0.0])
        e0 = model.add_element(
            id="pipe_0",
            type="pipe_straight",
            n1=n0,
            n2=n1,
            section="PipeSec",
            material="Steel",
        )
        e1 = model.add_element(
            id="pipe_1",
            type="pipe_straight",
            n1=n1,
            n2=n2,
            section="PipeSec",
            material="Steel",
        )
        return model, e0, e1

    def test_insulation_spec_assignment_roundtrips(self):
        model, element, _ = self._model_with_two_elements()
        spec = model.add_insulation_spec(
            id="mw_50",
            material="mineral_wool",
            thickness_m=0.05,
            density_kg_m3=120.0,
            cost_per_m=18.5,
        )

        assignment = model.assign_insulation(EntityRef("element", element.id), spec.id)

        self.assertEqual(assignment.key, "insulation")
        self.assertEqual(model.get_insulation(EntityRef("element", element.id)), spec)

        data = model.to_dict()
        self.assertEqual(data["specs"]["insulation"]["mw_50"]["thickness_m"], 0.05)
        self.assertEqual(
            data["attributes"][0],
            {
                "target": {"kind": "element", "id": "pipe_0"},
                "key": "insulation",
                "value": "mw_50",
            },
        )
        validate_model_dict(data)

        loaded = Model.from_dict(data)
        self.assertEqual(loaded.get_insulation("element:pipe_0").thickness_m, 0.05)
        self.assertEqual(loaded.get_insulation("element:pipe_0").cost_per_m, 18.5)

    def test_group_attribute_applies_to_members_and_direct_attribute_overrides(self):
        model, e0, e1 = self._model_with_two_elements()
        model.groups["rack_A"] = {"name": "rack_A", "elements": [e0.id, e1.id]}
        model.add_insulation_spec("mw_30", material="mineral_wool", thickness_m=0.03)
        model.add_insulation_spec("aero_10", material="aerogel", thickness_m=0.01)

        model.assign_insulation("group:rack_A", "mw_30")
        model.assign_insulation(EntityRef("element", e1.id), "aero_10")

        self.assertEqual(model.get_insulation(EntityRef("element", e0.id)).id, "mw_30")
        self.assertEqual(model.get_insulation(EntityRef("element", e1.id)).id, "aero_10")
        self.assertEqual(model.get_attributes(EntityRef("element", e0.id))["insulation"], "mw_30")

    def test_generic_attributes_are_preserved_without_geometry_effect(self):
        model, element, _ = self._model_with_two_elements()

        model.assign_attribute(
            EntityRef("element", element.id),
            "maintenance.priority",
            {"value": "high", "source": "operator"},
        )

        loaded = Model.from_dict(model.to_dict())
        self.assertEqual(
            loaded.get_attributes("element:pipe_0")["maintenance.priority"],
            {"value": "high", "source": "operator"},
        )

    def test_invalid_specs_and_unresolved_attribute_targets_fail_clearly(self):
        with self.assertRaises(ValueError):
            InsulationSpec(id="bad", material="mineral_wool", thickness_m=-0.01)

        model, _, _ = self._model_with_two_elements()
        with self.assertRaises(ValueError):
            model.assign_insulation("element:pipe_0", "missing_spec")

        model.assign_attribute("element:missing", "maintenance.priority", "high")
        with self.assertRaises(ModelValidationError):
            validate_model(model)


if __name__ == "__main__":
    unittest.main()
