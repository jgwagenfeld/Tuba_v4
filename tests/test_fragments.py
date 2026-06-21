import unittest

import numpy as np

from tuba import CoordinateSystem, Model
from tuba.fragments import ModelFragment, place_fragment


class TestModelFragment(unittest.TestCase):
    def test_fragment_places_local_geometry_into_parent_coordinate_system(self):
        fragment = ModelFragment("rack_template")
        fragment.model.add_material("Steel", E=2.0e11, nu=0.3)
        fragment.model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        with fragment.pipe(section="PipeSec", material="Steel") as b:
            b.start([0.0, 0.0, 0.0], support="anchor")
            b.run(2.0)

        parent = Model(project_name="Parent")
        parent.add_material("Steel", E=2.0e11, nu=0.3)
        parent.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        placement = CoordinateSystem(
            origin=(10.0, 20.0, 0.0),
            x_axis=(0.0, 1.0, 0.0),
            y_axis=(-1.0, 0.0, 0.0),
            z_axis=(0.0, 0.0, 1.0),
        )

        result = place_fragment(parent, fragment, placement, name="rack_A")

        coords = [node.coords for node in parent.nodes.values()]
        self.assertTrue(any(np.allclose(coord, (10.0, 20.0, 0.0)) for coord in coords))
        self.assertTrue(any(np.allclose(coord, (10.0, 22.0, 0.0)) for coord in coords))
        self.assertEqual(len(parent.elements), 1)
        self.assertIn("rack_A", parent.groups)
        self.assertEqual(result.group_name, "rack_A")

    def test_same_fragment_can_be_placed_twice(self):
        fragment = ModelFragment("pipe_module")
        fragment.model.add_material("Steel", E=2.0e11, nu=0.3)
        fragment.model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        with fragment.pipe(section="PipeSec", material="Steel") as b:
            b.start([0.0, 0.0, 0.0]).run(1.0)

        parent = Model(project_name="Parent")
        parent.add_material("Steel", E=2.0e11, nu=0.3)
        parent.add_pipe_section("PipeSec", OD=0.1, WT=0.01)

        place_fragment(parent, fragment, CoordinateSystem(origin=(0.0, 0.0, 0.0)), name="pipe_A")
        place_fragment(parent, fragment, CoordinateSystem(origin=(0.0, 5.0, 0.0)), name="pipe_B")

        self.assertEqual(len(parent.elements), 2)
        self.assertIn("pipe_A", parent.groups)
        self.assertIn("pipe_B", parent.groups)

    def test_placed_group_metadata_roundtrips_through_model_dict(self):
        fragment = ModelFragment("rack_template", metadata={"revision": "A"})
        fragment.model.add_material("Steel", E=2.0e11, nu=0.3)
        fragment.model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        with fragment.pipe(section="PipeSec", material="Steel") as b:
            b.start([0.0, 0.0, 0.0], support="anchor").run(1.0)

        parent = Model(project_name="Parent")
        placement = CoordinateSystem(
            origin=(10.0, 20.0, 0.0),
            x_axis=(0.0, 1.0, 0.0),
            y_axis=(-1.0, 0.0, 0.0),
            z_axis=(0.0, 0.0, 1.0),
        )

        result = parent.place_fragment(fragment, placement, name="rack_A")
        loaded = Model.from_dict(parent.to_dict())

        self.assertIn("rack_A", loaded.groups)
        group = loaded.groups["rack_A"]
        self.assertEqual(group["fragment"], "rack_template")
        self.assertEqual(group["coordinate_system"]["origin"], [10.0, 20.0, 0.0])
        self.assertEqual(set(group["nodes"]), set(result.node_ids.values()))
        self.assertEqual(set(group["elements"]), set(result.element_ids.values()))
        self.assertEqual(len(loaded.supports), 1)
        self.assertEqual(group["supports"], [0])
        self.assertEqual(group["metadata"], {"revision": "A"})

    def test_duplicate_placement_name_is_rejected_without_mutation(self):
        fragment = ModelFragment("pipe_module")
        fragment.model.add_material("Steel", E=2.0e11, nu=0.3)
        fragment.model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        with fragment.pipe(section="PipeSec", material="Steel") as b:
            b.start([0.0, 0.0, 0.0]).run(1.0)

        parent = Model(project_name="Parent")
        parent.place_fragment(fragment, CoordinateSystem.identity(), name="pipe_A")
        before = parent.to_dict()

        with self.assertRaises(ValueError) as ctx:
            parent.place_fragment(fragment, CoordinateSystem(origin=(0.0, 5.0, 0.0)), name="pipe_A")

        self.assertIn("already exists", str(ctx.exception))
        self.assertEqual(parent.to_dict(), before)

    def test_catalog_name_conflict_is_rejected_without_mutation(self):
        fragment = ModelFragment("pipe_module")
        fragment.model.add_material("Steel", E=2.0e11, nu=0.3)
        fragment.model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        with fragment.pipe(section="PipeSec", material="Steel") as b:
            b.start([0.0, 0.0, 0.0]).run(1.0)

        parent = Model(project_name="Parent")
        parent.add_material("Steel", E=1.0e11, nu=0.3)
        parent.add_pipe_section("PipeSec", OD=0.1, WT=0.02)
        before = parent.to_dict()

        with self.assertRaises(ValueError) as ctx:
            parent.place_fragment(fragment, CoordinateSystem.identity(), name="pipe_A")

        self.assertIn("conflicts", str(ctx.exception))
        self.assertEqual(parent.to_dict(), before)


if __name__ == "__main__":
    unittest.main()
