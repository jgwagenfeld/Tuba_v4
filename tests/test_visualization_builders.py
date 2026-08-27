import unittest
from unittest.mock import patch

from tuba import Model
from tuba.refs import EntityRef
from tuba.model import sample_bend_geometry
from tuba.visualization import SceneBuildOptions, build_visualization_scene
from tuba.visualization.builders import _find_element


class TestVisualizationBuilders(unittest.TestCase):
    def _model(self):
        model = Model(project_name="VisualizationBuilder")
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
        support = model.add_support(n0, "anchor")
        obstacle = model.add_obstacle(
            id="equipment_box",
            type="cuboid",
            min_point=[3.0, -0.5, -0.5],
            max_point=[4.0, 0.5, 0.5],
        )
        model.groups["line_A"] = {"name": "line_A", "elements": [elem.id]}
        model.add_insulation_spec("mw_50", material="mineral_wool", thickness_m=0.05, density_kg_m3=100.0, cost_per_m=20.0)
        model.assign_insulation("group:line_A", "mw_50")
        return model, elem, support, obstacle

    def test_build_visualization_scene_projects_model_objects_and_physical_metadata(self):
        model, elem, support, _obstacle = self._model()

        scene = build_visualization_scene(
            model,
            options=SceneBuildOptions(include_physical=True, include_quantities=True),
            scene_id="scene_builder",
        )
        scene.validate()
        objects_by_ref = {str(obj.entity_ref): obj for obj in scene.objects if obj.entity_ref is not None}

        pipe = objects_by_ref[f"element:{elem.id}"]
        self.assertEqual(pipe.kind, "pipe")
        self.assertEqual(pipe.metadata["section"], "PipeSec")
        self.assertEqual(pipe.metadata["material"], "Steel")
        self.assertEqual(pipe.metadata["profile"]["kind"], "pipe")
        self.assertAlmostEqual(pipe.metadata["profile"]["outer_diameter_m"], 0.1)
        self.assertAlmostEqual(pipe.metadata["profile"]["wall_thickness_m"], 0.01)
        self.assertAlmostEqual(pipe.metadata["profile"]["inner_diameter_m"], 0.08)
        self.assertEqual(pipe.metadata["attributes"]["insulation"], "mw_50")
        self.assertEqual(pipe.metadata["insulation"]["material"], "mineral_wool")
        self.assertAlmostEqual(pipe.physical["effective_od_m"], 0.2)
        self.assertAlmostEqual(pipe.quantities["length_m"], 2.0)
        self.assertIsNotNone(pipe.geometry_asset_id)

        self.assertIn(f"support:{support.id}", objects_by_ref)
        self.assertIn("obstacle:equipment_box", objects_by_ref)
        self.assertTrue(any(asset.id == pipe.geometry_asset_id for asset in scene.geometry_assets))

    def test_build_visualization_scene_honors_object_inclusion_options(self):
        model, elem, _support, _obstacle = self._model()

        scene = build_visualization_scene(
            model,
            options=SceneBuildOptions(include_supports=False, include_obstacles=False),
            scene_id="scene_filtered",
        )
        entity_refs = {obj.entity_ref for obj in scene.objects}

        self.assertIn(EntityRef("element", elem.id), entity_refs)
        self.assertNotIn(EntityRef("support", "support_0"), entity_refs)
        self.assertNotIn(EntityRef("obstacle", "equipment_box"), entity_refs)

    def test_pipe_geometry_carries_inner_radius_for_hollow_rendering(self):
        model, elem, _support, _obstacle = self._model()

        scene = build_visualization_scene(model)
        asset = next(item for item in scene.geometry_assets if item.id == f"geometry:element:{elem.id}")

        self.assertAlmostEqual(asset.generation_config["radius_m"], 0.05)
        self.assertAlmostEqual(asset.generation_config["inner_radius_m"], 0.04)

    def test_scene_builder_does_not_require_pyvista(self):
        model, _elem, _support, _obstacle = self._model()
        original_import = __import__

        def guarded_import(name, *args, **kwargs):
            if name.startswith("pyvista"):
                raise AssertionError("build_visualization_scene must not import pyvista")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=guarded_import):
            scene = build_visualization_scene(model)

        self.assertTrue(scene.objects)

    def test_structural_sections_emit_true_mesh_assets(self):
        model = Model(project_name="StructuralProfiles")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_ibeam_section("ColumnIPE", "IPE100")
        model.add_rectangular_section(
            "BeamRHS",
            height_y=0.12,
            height_z=0.08,
            thickness_y=0.01,
            thickness_z=0.01,
        )
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([0.0, 0.0, 2.0])
        n2 = model.add_node([2.0, 0.0, 2.0])
        model.add_element(
            id="column",
            type="beam",
            n1=n0,
            n2=n1,
            section="ColumnIPE",
            material="Steel",
        )
        model.add_element(
            id="crossbeam",
            type="beam",
            n1=n1,
            n2=n2,
            section="BeamRHS",
            material="Steel",
        )

        scene = build_visualization_scene(model)
        assets = {asset.id: asset for asset in scene.geometry_assets}
        column = assets["geometry:element:column"]
        crossbeam = assets["geometry:element:crossbeam"]

        self.assertEqual(column.format, "mesh")
        self.assertEqual(crossbeam.format, "mesh")
        self.assertEqual(len(column.generation_config["vertices"]), 24)
        self.assertEqual(len(column.generation_config["faces"]), 44)
        self.assertEqual(len(crossbeam.generation_config["vertices"]), 16)
        self.assertEqual(len(crossbeam.generation_config["faces"]), 32)
        self.assertNotEqual(
            column.generation_config["vertices"],
            crossbeam.generation_config["vertices"],
        )

    def test_scene_element_lookup_uses_model_index_when_available(self):
        model, elem, _support, _obstacle = self._model()

        class ScanBlockedElements(list):
            def __iter__(self):
                raise AssertionError("scene helper should use the element index")

        model.elements = ScanBlockedElements(model.elements)

        self.assertEqual(_find_element(model, elem.id), elem)

    def test_scene_pipe_bend_uses_sampled_bend_geometry(self):
        model = Model(project_name="VisualizationBend")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        with model.pipe("PipeSec", "Steel") as pipe:
            pipe.start([0.0, 0.0, 0.0])
            pipe.bend(radius=1.0, angle=90.0, plane="XY")

        bend = model.elements[0]
        scene = build_visualization_scene(model)
        asset = next(item for item in scene.geometry_assets if item.id == f"geometry:element:{bend.id}")
        expected = sample_bend_geometry(model.nodes[bend.n1].coords, bend.bend_geometry, n_segments=16)

        self.assertEqual(asset.generation_config["points"], expected.tolist())
        self.assertGreater(len(asset.generation_config["points"]), 2)


if __name__ == "__main__":
    unittest.main()
