import unittest

from tuba import Model
from tuba.assemblies import RackBay
from tuba.load_path import analyze_load_paths
from tuba.patches import ModelTransaction
from tuba.visualization import build_visualization_scene


class TestVisualizationRacks(unittest.TestCase):
    def _rack_model(self, *, attach_support=True):
        model = Model(project_name="RackReview")
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
            zone="north",
        )
        ModelTransaction(model).apply(rack.to_patch())
        if attach_support:
            node_ref = model.groups["rack_A"]["metadata"]["attachment_points"]["level_1_left"]
            support = model.add_support(node=node_ref.split(":", 1)[1], type="rest")
        else:
            node = model.add_node([20.0, 0.0, 0.0])
            support = model.add_support(node=node, type="rest")
        return model, support

    def test_build_scene_adds_rack_assembly_and_load_path_overlays(self):
        model, support = self._rack_model()
        report = analyze_load_paths(model, support_reactions={support.id: (100.0, 0.0, -1000.0)})

        scene = build_visualization_scene(model, load_path_report=report, scene_id="scene_rack_review")
        scene.validate()

        rack_overlay = next(overlay for overlay in scene.overlays if overlay.kind == "rack_assembly")
        self.assertEqual(rack_overlay.data["rack_id"], "rack_A")
        self.assertEqual(rack_overlay.data["assembly_type"], "rack_bay")
        self.assertEqual(rack_overlay.data["zone"], "north")
        self.assertGreaterEqual(len(rack_overlay.object_ids), 12)

        vector = next(obj for obj in scene.objects if obj.kind == "load_path_vector")
        self.assertEqual(vector.metadata["support_id"], support.id)
        self.assertEqual(vector.metadata["rack_id"], "rack_A")
        self.assertEqual(vector.metadata["attachment_point"], "level_1_left")
        self.assertEqual(vector.metadata["reaction_n"], [100.0, 0.0, -1000.0])

        load_overlay = next(overlay for overlay in scene.overlays if overlay.kind == "load_path")
        self.assertIn(vector.id, load_overlay.object_ids)
        self.assertEqual(load_overlay.data["rack_loads"]["rack_A"]["force_z_n"], -1000.0)

    def test_unassociated_support_becomes_review_issue(self):
        model, _support = self._rack_model(attach_support=False)
        report = analyze_load_paths(model)

        scene = build_visualization_scene(model, load_path_report=report, scene_id="scene_rack_review")
        issue = next(issue for issue in scene.issues if issue.type == "load_path")

        self.assertEqual(issue.severity, "warning")
        self.assertEqual(issue.status, "open")
        self.assertIn("not associated", issue.description)


if __name__ == "__main__":
    unittest.main()
