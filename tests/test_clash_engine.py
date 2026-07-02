import unittest

from tuba import Model
from tuba.clash import ClashEngine, TrimeshClashEngine, clash_report_to_dict, clash_report_to_markdown


class TestClashEngineAlias(unittest.TestCase):
    def test_trimesh_name_is_a_backwards_compatible_alias(self):
        import tuba

        self.assertIs(TrimeshClashEngine, ClashEngine)
        self.assertIs(tuba.TrimeshClashEngine, tuba.ClashEngine)


class TestClashEngine(unittest.TestCase):
    def _model(self):
        model = Model(project_name="Clash")
        model.add_material("Steel", E=2.0e11, nu=0.3)
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
        model.add_obstacle(
            id="tray_0",
            type="cuboid",
            min_point=[0.5, 0.11, -0.10],
            max_point=[1.5, 0.20, 0.10],
        )
        return model, elem

    def test_structured_results_use_entity_refs(self):
        model, _ = self._model()
        model.add_obstacle(
            id="box_0",
            type="cuboid",
            min_point=[0.5, -0.02, -0.10],
            max_point=[1.5, 0.20, 0.10],
        )

        clashes = TrimeshClashEngine().check_model(model)

        self.assertEqual(len(clashes), 1)
        clash = clashes[0]
        self.assertEqual(str(clash.left), "element:pipe_0")
        self.assertEqual(str(clash.right), "obstacle:box_0")
        self.assertEqual(clash.severity, "hard")
        self.assertGreater(clash.penetration_m, 0.0)
        self.assertEqual(clash.to_dict()["left"], {"kind": "element", "id": "pipe_0"})

    def test_insulation_envelope_can_create_clash(self):
        model, elem = self._model()

        bare_clashes = TrimeshClashEngine().check_model(model)
        self.assertEqual(bare_clashes, [])

        model.add_insulation_spec("mw_80", material="mineral_wool", thickness_m=0.08)
        model.assign_insulation(f"element:{elem.id}", "mw_80")

        insulated_clashes = TrimeshClashEngine().check_model(model)
        self.assertEqual(len(insulated_clashes), 1)
        self.assertEqual(str(insulated_clashes[0].right), "obstacle:tray_0")
        self.assertGreater(insulated_clashes[0].penetration_m, 0.01)

    def test_report_serializers_are_json_and_markdown_friendly(self):
        model, elem = self._model()
        model.add_insulation_spec("mw_80", material="mineral_wool", thickness_m=0.08)
        model.assign_insulation(f"element:{elem.id}", "mw_80")
        clashes = TrimeshClashEngine().check_model(model)

        data = clash_report_to_dict(clashes)
        markdown = clash_report_to_markdown(clashes)

        self.assertEqual(data["clash_count"], 1)
        self.assertEqual(data["clashes"][0]["right"]["id"], "tray_0")
        self.assertIn("element:pipe_0", markdown)
        self.assertIn("obstacle:tray_0", markdown)


if __name__ == "__main__":
    unittest.main()
