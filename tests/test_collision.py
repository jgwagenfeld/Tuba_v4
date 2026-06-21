# tests/test_collision.py
import unittest
import os
import tempfile
import numpy as np

from tuba import Model
from tuba.geometry.importer import StepGeometryImporter
from tuba.geometry.collision import PipingCollisionChecker


class TestPipingCollision(unittest.TestCase):
    def setUp(self):
        # Create a temp directory for STEP files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.step_path = os.path.join(self.temp_dir.name, "test_box.step")
        
        # Write a simple STEP file containing a box using Gmsh OCC
        import gmsh
        if not gmsh.isInitialized():
            gmsh.initialize()
            gmsh.option.setNumber("General.Terminal", 0)
        
        gmsh.model.add("temp_step_gen")
        # Add box from [1.0, -1.0, -1.0] to [3.0, 1.0, 1.0] (extents dx=2, dy=2, dz=2)
        gmsh.model.occ.addBox(1.0, -1.0, -1.0, 2.0, 2.0, 2.0)
        gmsh.model.occ.synchronize()
        gmsh.write(self.step_path)
        gmsh.model.remove()
        
        self.model = Model(project_name="TestCollision")
        self.model.add_material("Steel", E=2.0e11, nu=0.3)
        self.model.add_pipe_section("PipeSec", OD=0.2, WT=0.01) # Radius = 0.1m

    def tearDown(self):
        # Clean up temp files
        self.temp_dir.cleanup()
        import gmsh
        if gmsh.isInitialized():
            gmsh.finalize()

    def test_primitive_cuboid_collision(self):
        # Build pipe centerline run directly crossing the box [1, -1, -1] -> [3, 1, 1]
        # Pipe starts at [0, 0, 0] and runs in +X direction for 4 meters
        with self.model.pipe(section="PipeSec", material="Steel") as b:
            b.start([0.0, 0.0, 0.0]).run(4.0).end()

        # Add colliding cuboid obstacle
        self.model.add_obstacle(
            id="box_obs",
            type="cuboid",
            min_point=[1.5, -0.5, -0.5],
            max_point=[2.5, 0.5, 0.5]
        )

        checker = PipingCollisionChecker(self.model)
        collisions = checker.check_collisions()
        self.assertIn("pipe_str_0", collisions)

    def test_no_collision(self):
        # Build pipe centerline that doesn't cross the obstacle
        with self.model.pipe(section="PipeSec", material="Steel") as b:
            b.start([0.0, 5.0, 0.0]).run(4.0).end() # offset in Y direction

        # Add cuboid obstacle at [1.5, -0.5, -0.5] -> [2.5, 0.5, 0.5]
        self.model.add_obstacle(
            id="box_obs",
            type="cuboid",
            min_point=[1.5, -0.5, -0.5],
            max_point=[2.5, 0.5, 0.5]
        )

        checker = PipingCollisionChecker(self.model)
        collisions = checker.check_collisions()
        self.assertEqual(len(collisions), 0)

    def test_mesh_step_collision(self):
        # Build pipe centerline directly crossing the STEP box
        with self.model.pipe(section="PipeSec", material="Steel") as b:
            b.start([0.0, 0.0, 0.0]).run(4.0).end()

        # Add STEP mesh obstacle
        self.model.add_obstacle(
            id="mesh_obs",
            type="mesh",
            file_path=self.step_path,
            position=[0.0, 0.0, 0.0]
        )

        checker = PipingCollisionChecker(self.model)
        collisions = checker.check_collisions()
        self.assertIn("pipe_str_0", collisions)


if __name__ == "__main__":
    unittest.main()
