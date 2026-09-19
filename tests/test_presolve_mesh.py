import unittest
from tuba.model import TubaModel, Element, Support
from tuba.solver.aster_mesh import generate_analysis_mesh
from tuba.visualization import SceneRequest, build_visualization_scene, SceneBuildOptions
from tuba.visualization.builders._layers import mesh_identity


class TestPresolveMesh(unittest.TestCase):
    def _create_test_model(self) -> TubaModel:
        model = TubaModel()
        model.add_material("Steel", E=210e9, nu=0.3, rho=7850.0, alpha=1.2e-5)
        model.add_pipe_section("Pipe40", OD=0.1143, WT=0.00602)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([2.0, 0.0, 0.0])
        n2 = model.add_node([2.0, 2.0, 0.0])
        model.add_element(id="p1", type="pipe_straight", n1=n0, n2=n1, section="Pipe40", material="Steel")
        model.add_element(id="p2", type="pipe_straight", n1=n1, n2=n2, section="Pipe40", material="Steel")
        model.add_support(node=n0, type="anchor")
        model.add_support(node=n2, type="guide")
        return model

    def test_generate_analysis_mesh_presolve(self):
        model = self._create_test_model()
        mesh = generate_analysis_mesh(model)
        self.assertIsNotNone(mesh)
        self.assertTrue(mesh.id.startswith("analysis_mesh:"))
        self.assertIn("AllPipes", mesh.groups)
        self.assertIn("PipeStraights", mesh.groups)
        self.assertIn("TUYAU_3M", mesh.modelisations.values())
        self.assertGreater(len(mesh.nodes), 3)  # Midpoint nodes generated
        self.assertGreater(len(mesh.elements), 0)

    def test_build_visualization_scene_with_presolve_mesh(self):
        model = self._create_test_model()
        scene = build_visualization_scene(SceneRequest(model, include_analysis_mesh=True))
        scene.validate()

        mesh_elements = [obj for obj in scene.objects if obj.kind == "analysis_mesh_element"]
        mesh_nodes = [obj for obj in scene.objects if obj.kind == "analysis_mesh_node"]
        self.assertGreater(len(mesh_elements), 0)
        self.assertGreater(len(mesh_nodes), 0)

        mesh_layers = [layer for layer in scene.layers if layer.category == "analysis_mesh"]
        self.assertGreater(len(mesh_layers), 0)
        identity_layer = next((l for l in mesh_layers if "mesh_identity" in l.extra), None)
        self.assertIsNotNone(identity_layer)
        self.assertEqual(identity_layer.extra["mesh_identity"]["solver"], "Code_Aster")

        # Mesh layers should default to hidden so model opens with solid geometry
        for layer in mesh_layers:
            self.assertFalse(layer.default_visible)

    def test_contact_helpers_routing(self):
        model = self._create_test_model()
        mid_node = list(model.nodes.keys())[1]
        model.add_support(node=mid_node, type="rest", friction_coefficient=0.3)
        scene = build_visualization_scene(SceneRequest(model, include_analysis_mesh=True))
        scene.validate()

        # Contact helpers should be routed to analysis_mesh:helpers, not physical analysis_mesh:elements
        helper_objects = [obj for obj in scene.objects if "analysis_mesh:helpers" in obj.layer_ids]
        self.assertGreater(len(helper_objects), 0)
        for obj in helper_objects:
            self.assertNotIn("analysis_mesh:elements", obj.layer_ids)
            self.assertNotIn("analysis_mesh:nodes", obj.layer_ids)


if __name__ == "__main__":
    unittest.main()
