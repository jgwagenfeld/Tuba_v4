import unittest

import numpy as np

from tuba import Model
from tuba.geometry.profiles import profile_for_section
from tuba.model import RectangularSection
from tuba.plotting.pipeline import build_3d_mesh_from_model
from tuba.plotting.scenes import build_model_scene
from tuba.solver.base import ElementResult, FEAResults, NodeResult


class TestVisualizerScenes(unittest.TestCase):
    def test_section_profile_adapter_normalizes_common_shapes(self):
        model = Model(project_name="Profiles")
        pipe = model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        rect = RectangularSection(name="Rect", height_y=0.2, height_z=0.1, thickness_y=0.01, thickness_z=0.01)

        pipe_profile = profile_for_section(pipe)
        rect_profile = profile_for_section(rect)

        self.assertEqual(pipe_profile.kind, "pipe")
        self.assertAlmostEqual(pipe_profile.collision_radius_m, 0.05)
        self.assertAlmostEqual(pipe_profile.area_m2, pipe.area)
        self.assertEqual(rect_profile.kind, "rectangular")
        self.assertAlmostEqual(rect_profile.collision_radius_m, 0.1)
        self.assertEqual(rect_profile.dimensions["height_y"], 0.2)

    def test_build_model_scene_returns_plotter(self):
        model = Model(project_name="Scene")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        with model.pipe(section="PipeSec", material="Steel") as b:
            b.start([0.0, 0.0, 0.0]).run(1.0)

        plotter = build_model_scene(model, off_screen=True)
        try:
            self.assertTrue(hasattr(plotter, "add_mesh"))
        finally:
            plotter.close()

    def test_geometry_mesh_has_no_solver_fields_without_results(self):
        model = Model(project_name="GeometryOnly")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        with model.pipe(section="PipeSec", material="Steel") as b:
            b.start([0.0, 0.0, 0.0]).run(1.0)

        mesh = build_3d_mesh_from_model(model)

        self.assertNotIn("DEPL", mesh.point_data)
        self.assertNotIn("DEPL_magnitude", mesh.point_data)
        self.assertNotIn("VMIS", mesh.point_data)
        self.assertNotIn("FORC_NODA", mesh.point_data)
        self.assertNotIn("FORC_magnitude", mesh.point_data)

    def test_build_model_scene_adds_undeformed_reference_when_warped(self):
        model = Model(project_name="Scene")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        model.define_load_case("Hot")
        with model.pipe(section="PipeSec", material="Steel") as b:
            b.start([0.0, 0.0, 0.0]).run(1.0)

        n0, n1 = [node.id for node in model.nodes.values()]
        results = FEAResults(solver_name="Code_Aster", load_case="Hot")
        results.node_results[n0] = NodeResult(n0, np.zeros(6))
        results.node_results[n1] = NodeResult(n1, np.array([0.01, 0.0, 0.0, 0.0, 0.0, 0.0]))
        results.element_results[model.elements[0].id] = ElementResult(
            model.elements[0].id,
            np.zeros(6),
            np.zeros(6),
            von_mises_n1=1.0,
            von_mises_n2=2.0,
            max_von_mises=2.0,
        )

        plotter = build_model_scene(model, results, off_screen=True, deform_scale=10.0)
        try:
            opacities = [actor.GetProperty().GetOpacity() for actor in plotter.actors.values() if hasattr(actor, "GetProperty")]
            edge_visibilities = [
                prop.GetEdgeVisibility()
                for actor in plotter.actors.values()
                if hasattr(actor, "GetProperty")
                for prop in [actor.GetProperty()]
                if hasattr(prop, "GetEdgeVisibility")
            ]
            self.assertIn(0.25, opacities)
            self.assertIn(1, edge_visibilities)
        finally:
            plotter.close()


if __name__ == "__main__":
    unittest.main()
