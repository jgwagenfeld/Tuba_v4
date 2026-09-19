import unittest

from tuba import Model
from tuba.assemblies import RackBay, RackRow
from tuba.load_path import analyze_load_paths
from tuba.patches import ModelTransaction
from tuba.visualization import SceneRequest, build_visualization_scene


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
            rack_node = model.groups["rack_A"]["metadata"]["attachment_points"]["level_1_left"].split(":", 1)[1]
            x, y, z = model.nodes[rack_node].coords
            pipe_node = model.add_node([x, y, z + 0.25])
            support = model.add_support(node=pipe_node, type="rest", attached_to=rack_node)
        else:
            node = model.add_node([20.0, 0.0, 0.0])
            support = model.add_support(node=node, type="rest")
        return model, support

    def test_build_scene_adds_rack_assembly_and_load_path_overlays(self):
        model, support = self._rack_model()
        report = analyze_load_paths(model, node_reactions={support.attached_to: (100.0, 0.0, -1000.0)})

        scene = build_visualization_scene(SceneRequest(model, load_path_report=report, scene_id="scene_rack_review"))
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
        self.assertEqual(load_overlay.data["grounded_loads"], [])

    def test_grounded_support_loads_draw_vectors_to_ground(self):
        model, support = self._rack_model(attach_support=False)
        report = analyze_load_paths(model, node_reactions={support.node: (0.0, 0.0, -500.0)})

        scene = build_visualization_scene(SceneRequest(model, load_path_report=report, scene_id="scene_grounded"))
        scene.validate()

        vector = next(obj for obj in scene.objects if obj.kind == "load_path_vector")
        self.assertEqual(vector.metadata["support_id"], support.id)
        self.assertEqual(vector.metadata["target"], "ground")
        self.assertEqual(vector.metadata["reaction_n"], [0.0, 0.0, -500.0])
        load_overlay = next(overlay for overlay in scene.overlays if overlay.kind == "load_path")
        self.assertIn(vector.id, load_overlay.object_ids)
        self.assertEqual(load_overlay.data["rack_loads"], {})
        self.assertEqual(len(load_overlay.data["grounded_loads"]), 1)
        self.assertEqual(load_overlay.data["grounded_loads"][0]["force_n"], [0.0, 0.0, -500.0])
        # Grounded is by design: no load-path issue.
        self.assertEqual([issue for issue in scene.issues if issue.type == "load_path"], [])

    def test_grounded_support_without_reactions_draws_no_vector(self):
        model, support = self._rack_model(attach_support=False)
        report = analyze_load_paths(model)

        scene = build_visualization_scene(SceneRequest(model, load_path_report=report, scene_id="scene_grounded_unsolved"))
        scene.validate()

        self.assertEqual([obj for obj in scene.objects if obj.kind == "load_path_vector"], [])
        load_overlay = next(overlay for overlay in scene.overlays if overlay.kind == "load_path")
        self.assertEqual(len(load_overlay.data["grounded_loads"]), 1)
        self.assertIsNone(load_overlay.data["grounded_loads"][0]["force_n"])

    def test_row_bays_emit_a_rack_assembly_overlay_each(self):
        model = Model(project_name="RowRackReview")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_rectangular_section("RackSec", height_y=0.1, height_z=0.1, thickness_y=0.01, thickness_z=0.01)
        pipe = [model.add_node([x, 1.0, 0.0]) for x in (0.0, 2.0, 4.0)]
        row = RackRow(
            name_prefix="rack_A",
            origin=(0.0, 0.0, -3.0),
            material="Steel",
            section="RackSec",
            bays=2,
            bay_length=2.0,
            width=2.0,
            height=3.0,
            levels=(2.75,),
            shoe_level=2.75,
            shoes=tuple((node, station) for station, node in enumerate(pipe)),
            anchor_feet=False,
            zone="yard",
        )
        ModelTransaction(model).apply(row.to_patch())
        report = analyze_load_paths(model)

        scene = build_visualization_scene(SceneRequest(model, load_path_report=report, scene_id="scene_row_rack"))
        scene.validate()

        overlays = sorted(
            (overlay for overlay in scene.overlays if overlay.kind == "rack_assembly"),
            key=lambda overlay: overlay.data["rack_id"],
        )
        self.assertEqual([overlay.data["rack_id"] for overlay in overlays], ["rack_A0", "rack_A1"])
        for overlay in overlays:
            self.assertEqual(overlay.data["assembly_type"], "rack_row_bay")
            self.assertEqual(overlay.data["zone"], "yard")
            self.assertEqual(overlay.data["levels"], [2.75])
            self.assertTrue(all(ref.startswith("node:") for ref in overlay.data["attachment_points"].values()))
            self.assertGreaterEqual(len(overlay.object_ids), 1)
        self.assertEqual(set(overlays[0].data["attachment_points"]), {"mid_0", "mid_1"})
        self.assertEqual(set(overlays[1].data["attachment_points"]), {"mid_1", "mid_2"})

    def test_misattached_support_becomes_review_issue(self):
        model, _grounded = self._rack_model(attach_support=False)
        stray = model.add_node([25.0, 0.0, 0.0])
        pipe_node = model.add_node([25.0, 0.0, 0.25])
        support = model.add_support(node=pipe_node, type="rest", attached_to=stray)
        report = analyze_load_paths(model)

        scene = build_visualization_scene(SceneRequest(model, load_path_report=report, scene_id="scene_rack_review"))
        issues = [issue for issue in scene.issues if issue.type == "load_path"]

        # The misattached support is the one problem; the grounded one is by design.
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, "warning")
        self.assertEqual(issues[0].status, "open")
        self.assertIn(support.id, issues[0].description)
        self.assertIn("belongs to no rack", issues[0].description)

    def test_attached_support_emits_a_link_to_its_structure_node(self):
        model, support = self._rack_model()

        scene = build_visualization_scene(SceneRequest(model, scene_id="scene_rack_review"))
        scene.validate()

        link = next(obj for obj in scene.objects if obj.kind == "support_link")
        self.assertEqual(link.metadata["support_id"], support.id)
        self.assertEqual(link.metadata["attached_to"], support.attached_to)
        self.assertIn("rack_A", link.metadata["attached_to_groups"])
        asset = next(item for item in scene.geometry_assets if item.id == link.geometry_asset_id)
        self.assertEqual(asset.format, "polyline")
        self.assertEqual(
            asset.generation_config["points"],
            [
                [float(value) for value in model.nodes[support.node].coords.tolist()],
                [float(value) for value in model.nodes[support.attached_to].coords.tolist()],
            ],
        )
        self.assertIn("support_link", {layer.id for layer in scene.layers})

        support_object = next(
            obj for obj in scene.objects if obj.kind == "support" and obj.name == support.id
        )
        self.assertEqual(support_object.metadata["attached_to"], support.attached_to)
        self.assertIn("rack_A", support_object.metadata["attached_to_groups"])

    def test_ground_support_emits_no_link(self):
        model, _support = self._rack_model(attach_support=False)

        scene = build_visualization_scene(SceneRequest(model, scene_id="scene_rack_review"))
        scene.validate()

        self.assertEqual([obj for obj in scene.objects if obj.kind == "support_link"], [])
        self.assertNotIn("support_link", {layer.id for layer in scene.layers})


if __name__ == "__main__":
    unittest.main()
