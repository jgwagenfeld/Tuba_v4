import unittest

from tuba import Model, RackBay
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

    def test_support_at_attachment_point_associates_to_rack(self):
        model = self._rack_model()
        node_ref = model.groups["rack_A"]["metadata"]["attachment_points"]["level_1_left"]
        support = model.add_support(node=node_ref.split(":", 1)[1], type="rest")

        report = analyze_load_paths(model)

        self.assertEqual(len(report.associations), 1)
        self.assertEqual(str(report.associations[0].support), f"support:{support.id}")
        self.assertEqual(str(report.associations[0].rack), "group:rack_A")
        self.assertEqual(report.associations[0].attachment_point, "level_1_left")

    def test_support_reaction_rolls_up_to_rack_loads(self):
        model = self._rack_model()
        node_ref = model.groups["rack_A"]["metadata"]["attachment_points"]["level_1_left"]
        support = model.add_support(node=node_ref.split(":", 1)[1], type="rest")

        report = analyze_load_paths(model, support_reactions={support.id: (100.0, 0.0, -1000.0)})

        self.assertEqual(report.rack_loads["rack_A"]["support_count"], 1)
        self.assertEqual(report.rack_loads["rack_A"]["force_x_n"], 100.0)
        self.assertEqual(report.rack_loads["rack_A"]["force_z_n"], -1000.0)

    def test_result_state_reactions_roll_up_to_rack_loads(self):
        model = self._rack_model()
        node_ref = model.groups["rack_A"]["metadata"]["attachment_points"]["level_1_left"]
        support = model.add_support(node=node_ref.split(":", 1)[1], type="rest")
        result_state = ResultState(
            id="result_hot",
            study_id="study_hot",
            model_revision=0,
            solver_name="Code_Aster",
            load_case="Hot",
            mesh_id=None,
            node_displacements={},
            node_reactions={support.node: (100.0, 0.0, -1000.0, 0.0, 0.0, 0.0)},
            element_results={},
        )

        report = analyze_load_paths(model, result_state=result_state)

        self.assertEqual(report.rack_loads["rack_A"]["support_count"], 1)
        self.assertEqual(report.rack_loads["rack_A"]["force_x_n"], 100.0)
        self.assertEqual(report.rack_loads["rack_A"]["force_z_n"], -1000.0)

    def test_unassociated_support_is_reported_as_diagnostic(self):
        model = self._rack_model()
        extra_node = model.add_node([20.0, 0.0, 0.0])
        support = model.add_support(node=extra_node, type="rest")

        report = analyze_load_paths(model)

        self.assertEqual(report.associations, [])
        self.assertIn(f"Support {support.id!r} is not associated", " ".join(report.diagnostics))


if __name__ == "__main__":
    unittest.main()
