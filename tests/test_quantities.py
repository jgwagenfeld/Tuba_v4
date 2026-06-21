import unittest

from tuba import Model
from tuba.external.bom import bom_to_csv, bom_to_dict
from tuba.quantities import quantity_takeoff, wind_loads


class TestQuantities(unittest.TestCase):
    def _model(self):
        model = Model(project_name="Quantities")
        model.add_material("Steel", E=2.0e11, nu=0.3, rho=7850.0)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([2.0, 0.0, 0.0])
        n2 = model.add_node([5.0, 0.0, 0.0])
        e0 = model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")
        e1 = model.add_element(id="pipe_1", type="pipe_straight", n1=n1, n2=n2, section="PipeSec", material="Steel")
        model.groups["line_A"] = {"name": "line_A", "elements": [e0.id, e1.id]}
        model.add_insulation_spec("mw_50", material="mineral_wool", thickness_m=0.05, density_kg_m3=100.0, cost_per_m=20.0)
        model.assign_insulation("group:line_A", "mw_50")
        return model

    def test_quantity_takeoff_totals_and_group_totals(self):
        model = self._model()

        takeoff = quantity_takeoff(model)
        data = takeoff.to_dict()

        self.assertAlmostEqual(takeoff.totals["length_m"], 5.0)
        self.assertAlmostEqual(takeoff.totals["insulation_cost"], 100.0)
        self.assertGreater(takeoff.totals["total_mass_kg"], 0.0)
        self.assertAlmostEqual(takeoff.groups["line_A"]["length_m"], 5.0)
        self.assertEqual(data["records"][0]["element"]["id"], "pipe_0")
        self.assertEqual(data["groups"]["line_A"]["element_count"], 2)

    def test_wind_loads_use_effective_insulated_diameter(self):
        model = self._model()

        loads = wind_loads(model, pressure_pa=1000.0)

        self.assertAlmostEqual(loads["pipe_0"]["projected_area_m2"], 0.4)
        self.assertAlmostEqual(loads["pipe_0"]["force_n"], 400.0)
        self.assertAlmostEqual(loads["pipe_1"]["projected_area_m2"], 0.6)
        self.assertAlmostEqual(loads["pipe_1"]["force_n"], 600.0)

    def test_bom_export_includes_groups_and_insulation_metadata(self):
        model = self._model()

        bom = bom_to_dict(model)
        csv_text = bom_to_csv(model)

        self.assertEqual(bom["rows"][0]["element_id"], "pipe_0")
        self.assertEqual(bom["rows"][0]["insulation_spec"], "mw_50")
        self.assertEqual(bom["rows"][0]["insulation_material"], "mineral_wool")
        self.assertAlmostEqual(bom["groups"]["line_A"]["length_m"], 5.0)
        self.assertIn("element_id,section,material,length_m", csv_text.splitlines()[0])
        self.assertIn("pipe_1", csv_text)


if __name__ == "__main__":
    unittest.main()
