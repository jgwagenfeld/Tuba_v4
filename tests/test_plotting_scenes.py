import unittest

from tuba import Model
from tuba.geometry.profiles import profile_for_section
from tuba.model import RectangularSection
from tuba.visualizer.scenes import build_model_scene


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


if __name__ == "__main__":
    unittest.main()
