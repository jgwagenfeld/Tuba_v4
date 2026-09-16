import unittest

from tuba import Model
from tuba.assemblies import RackBay
from tuba.analysis import ResultState
from tuba.load_path import analyze_load_paths
from tuba.patches import ModelTransaction


class TestLoadPath(unittest.TestCase):
    def _rack_model(self):
        model = Model(project_name="LoadPath")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_rectangular_section("RackSec", height_y=0.1, height_z=0.1, thickness_y=0.01, thickness_z=0.01)
        rack = RackBay(
            name="rack_A",
            origin=(0.0, 0.0, 0.0),
            length=4.0,
            width=1.0,
            height=3.0,
            levels=(1.5, 3.0),
            section="RackSec",
            material="Steel",
        )
        ModelTransaction(model).apply(rack.to_patch())
        return model

    def _attached_support(self, model, kind="rest"):
        rack_node = model.groups["rack_A"]["metadata"]["attachment_points"]["level_1_left"].split(":", 1)[1]
        x, y, z = model.nodes[rack_node].coords
        pipe_node = model.add_node([x, y + 0.1 * len(model.supports), z + 0.25])
        return model.add_support(node=pipe_node, type=kind, attached_to=rack_node), rack_node

    def test_attached_support_associates_to_its_rack(self):
        model = self._rack_model()
        support, rack_node = self._attached_support(model)
        report = analyze_load_paths(model)
        self.assertEqual(len(report.associations), 1)
        association = report.associations[0]
        self.assertEqual(str(association.support), f"support:{support.id}")
        self.assertEqual(str(association.rack), "group:rack_A")
        self.assertEqual(str(association.node), f"node:{rack_node}")
        self.assertEqual(association.attachment_point, "level_1_left")

    def test_rack_load_is_the_reaction_at_the_attached_node(self):
        model = self._rack_model()
        _support, rack_node = self._attached_support(model)
        report = analyze_load_paths(model, node_reactions={rack_node: (100.0, 0.0, -1000.0)})
        self.assertEqual(report.rack_loads["rack_A"]["support_count"], 1)
        self.assertEqual(report.rack_loads["rack_A"]["force_x_n"], 100.0)
        self.assertEqual(report.rack_loads["rack_A"]["force_z_n"], -1000.0)

    def test_two_supports_on_one_attached_node_count_its_reaction_once(self):
        model = self._rack_model()
        _first, rack_node = self._attached_support(model)
        self._attached_support(model, kind="guide")
        report = analyze_load_paths(model, node_reactions={rack_node: (0.0, 0.0, -1000.0)})
        self.assertEqual(report.rack_loads["rack_A"]["support_count"], 2)
        self.assertEqual(report.rack_loads["rack_A"]["force_z_n"], -1000.0)

    def test_result_state_reactions_roll_up_to_rack_loads(self):
        model = self._rack_model()
        _support, rack_node = self._attached_support(model)
        result_state = ResultState(
            id="result_hot",
            study_id="study_hot",
            model_revision=0,
            solver_name="Code_Aster",
            load_case="Hot",
            mesh_id=None,
            node_displacements={},
            node_reactions={rack_node: (100.0, 0.0, -1000.0, 0.0, 0.0, 0.0)},
            element_results={},
        )
        report = analyze_load_paths(model, result_state=result_state)
        self.assertEqual(report.rack_loads["rack_A"]["force_x_n"], 100.0)
        self.assertEqual(report.rack_loads["rack_A"]["force_z_n"], -1000.0)

    def test_grounded_support_on_a_rack_node_is_not_a_rack_load(self):
        model = self._rack_model()
        rack_node = model.groups["rack_A"]["metadata"]["attachment_points"]["level_1_left"].split(":", 1)[1]
        support = model.add_support(node=rack_node, type="rest")
        report = analyze_load_paths(model)
        self.assertEqual(report.associations, [])
        self.assertIn(f"Support {support.id!r} is not associated", " ".join(report.diagnostics))


if __name__ == "__main__":
    unittest.main()
