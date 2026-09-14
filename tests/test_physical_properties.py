import math
import unittest

from tuba import Model
from tuba.refs import EntityRef
from tuba.physical import (
    element_length,
    element_quantities,
    physical_properties_for_element,
)


class TestPhysicalProperties(unittest.TestCase):
    def _model(self):
        model = Model(project_name="Physical")
        model.add_material("Steel", E=2.0e11, nu=0.3, rho=7850.0)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([2.0, 0.0, 0.0])
        elem = model.add_element(
            id="pipe_0",
            type="pipe_straight",
            n1=n0,
            n2=n1,
            section="PipeSec",
            material="Steel",
        )
        return model, elem

    def test_bare_pipe_properties_use_section_and_material(self):
        model, elem = self._model()

        props = physical_properties_for_element(model, elem)

        self.assertAlmostEqual(props.bare_od_m, 0.1)
        self.assertAlmostEqual(props.effective_od_m, 0.1)
        self.assertAlmostEqual(props.effective_radius_m, 0.05)
        self.assertAlmostEqual(props.wind_diameter_m, 0.1)
        self.assertAlmostEqual(props.insulation_mass_kg_per_m, 0.0)
        self.assertAlmostEqual(props.pipe_mass_kg_per_m, model.sections["PipeSec"].area * 7850.0)
        self.assertAlmostEqual(props.mass_kg_per_m, props.pipe_mass_kg_per_m)

    def test_insulation_spec_increases_envelope_weight_and_wind_diameter(self):
        model, elem = self._model()
        model.add_insulation_spec(
            id="mw_50",
            material="mineral_wool",
            thickness_m=0.05,
            density_kg_m3=100.0,
            cost_per_m=20.0,
        )
        model.assign_insulation(EntityRef("element", elem.id), "mw_50")

        props = physical_properties_for_element(model, "pipe_0")

        expected_insulation_volume = math.pi * (0.10**2 - 0.05**2)
        self.assertEqual(props.insulation_spec_id, "mw_50")
        self.assertAlmostEqual(props.effective_radius_m, 0.10)
        self.assertAlmostEqual(props.effective_od_m, 0.20)
        self.assertAlmostEqual(props.wind_diameter_m, 0.20)
        self.assertAlmostEqual(props.insulation_volume_m3_per_m, expected_insulation_volume)
        self.assertAlmostEqual(props.insulation_mass_kg_per_m, expected_insulation_volume * 100.0)
        self.assertAlmostEqual(props.insulation_cost_per_m, 20.0)

    def test_group_insulation_and_direct_override_are_resolved(self):
        model, elem = self._model()
        model.groups["line_A"] = {"name": "line_A", "elements": [elem.id]}
        model.add_insulation_spec("mw_30", material="mineral_wool", thickness_m=0.03, density_kg_m3=80.0)
        model.add_insulation_spec("aero_10", material="aerogel", thickness_m=0.01, density_kg_m3=150.0)
        model.assign_insulation("group:line_A", "mw_30")

        group_props = physical_properties_for_element(model, elem)
        self.assertEqual(group_props.insulation_spec_id, "mw_30")
        self.assertAlmostEqual(group_props.effective_od_m, 0.16)

        model.assign_insulation(f"element:{elem.id}", "aero_10")
        direct_props = physical_properties_for_element(model, elem)
        self.assertEqual(direct_props.insulation_spec_id, "aero_10")
        self.assertAlmostEqual(direct_props.effective_od_m, 0.12)

    def test_element_quantities_scale_by_length(self):
        model, elem = self._model()
        model.add_insulation_spec("mw_50", material="mineral_wool", thickness_m=0.05, density_kg_m3=100.0)
        model.assign_insulation(f"element:{elem.id}", "mw_50")

        quantities = element_quantities(model, elem)

        self.assertAlmostEqual(element_length(model, elem), 2.0)
        self.assertAlmostEqual(quantities.length_m, 2.0)
        self.assertAlmostEqual(quantities.total_mass_kg, quantities.mass_kg_per_m * 2.0)
        self.assertAlmostEqual(quantities.insulation_volume_m3, quantities.insulation_volume_m3_per_m * 2.0)


if __name__ == "__main__":
    unittest.main()
