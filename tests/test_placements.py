import unittest

import numpy as np

from tuba.coordinates import CoordinateSystem
from tuba import Model
from tuba.placements import PlacementAssignment
from tuba.placements import PlacementFrame, resolve_placement_frame
from tuba.validation import ModelValidationError


class TestPlacementFrame(unittest.TestCase):
    def test_axis_ref_direction_match_ifc_semantics(self):
        frame = PlacementFrame(
            id="rack_A",
            origin=(10.0, 20.0, 0.0),
            axis=(0.0, 0.0, 1.0),
            ref_direction=(0.0, 1.0, 0.0),
        )

        cs = frame.to_coordinate_system()

        self.assertTrue(np.allclose(cs.to_global_point((2.0, 0.0, 0.0)), (10.0, 22.0, 0.0)))
        self.assertTrue(np.allclose(cs.to_global_vector((0.0, 1.0, 0.0)), (-1.0, 0.0, 0.0)))

    def test_parent_child_frames_compose(self):
        parent = PlacementFrame(
            id="site",
            origin=(100.0, 0.0, 0.0),
            axis=(0.0, 0.0, 1.0),
            ref_direction=(0.0, 1.0, 0.0),
        )
        child = PlacementFrame(
            id="rack_A",
            origin=(2.0, 3.0, 0.0),
            axis=(0.0, 0.0, 1.0),
            ref_direction=(1.0, 0.0, 0.0),
            parent="placement_frame:site",
        )

        cs = resolve_placement_frame(
            "rack_A",
            {"site": parent, "rack_A": child},
        )

        self.assertTrue(np.allclose(cs.to_global_point((1.0, 0.0, 0.0)), (97.0, 3.0, 0.0)))

    def test_colinear_axis_and_ref_direction_are_rejected(self):
        with self.assertRaises(ValueError):
            PlacementFrame(
                id="bad",
                origin=(0.0, 0.0, 0.0),
                axis=(0.0, 0.0, 1.0),
                ref_direction=(0.0, 0.0, 2.0),
            ).to_coordinate_system()

    def test_coordinate_system_roundtrip(self):
        cs = CoordinateSystem(
            origin=(4.0, 5.0, 6.0),
            x_axis=(0.0, 1.0, 0.0),
            y_axis=(-1.0, 0.0, 0.0),
            z_axis=(0.0, 0.0, 1.0),
        )

        frame = PlacementFrame.from_coordinate_system("rack_A", cs)
        restored = frame.to_coordinate_system()

        self.assertEqual(frame.axis, (0.0, 0.0, 1.0))
        self.assertEqual(frame.ref_direction, (0.0, 1.0, 0.0))
        self.assertTrue(np.allclose(restored.to_global_point((1.0, 2.0, 3.0)), cs.to_global_point((1.0, 2.0, 3.0))))


class TestPlacementModelStorage(unittest.TestCase):
    def test_model_roundtrips_placement_frames_and_assignments(self):
        model = Model("PlacementTest")
        model.placement_frames["site"] = PlacementFrame(
            id="site",
            origin=(100.0, 0.0, 0.0),
            frame_type="site",
        )
        model.placement_frames["rack_A"] = PlacementFrame(
            id="rack_A",
            origin=(2.0, 0.0, 0.0),
            parent="placement_frame:site",
            frame_type="assembly",
        )
        model.placement_assignments.append(
            PlacementAssignment(
                target="group:rack_A",
                frame="placement_frame:rack_A",
                role="object_placement",
                source="native",
            )
        )

        loaded = Model.from_dict(model.to_dict())

        self.assertEqual(set(loaded.placement_frames), {"site", "rack_A"})
        self.assertEqual(loaded.placement_frames["rack_A"].parent, "placement_frame:site")
        self.assertEqual(len(loaded.placement_assignments), 1)
        self.assertEqual(loaded.placement_assignments[0].target, "group:rack_A")


class TestPlacementValidation(unittest.TestCase):
    def test_cycle_in_placement_frames_fails_model_validation(self):
        model = Model("BadFrames")
        model.placement_frames["a"] = PlacementFrame(id="a", origin=(0.0, 0.0, 0.0), parent="placement_frame:b")
        model.placement_frames["b"] = PlacementFrame(id="b", origin=(0.0, 0.0, 0.0), parent="placement_frame:a")

        with self.assertRaises(ModelValidationError) as ctx:
            model.validate()

        self.assertIn("Placement frame cycle", str(ctx.exception))

    def test_duplicate_object_placement_assignment_fails_validation(self):
        model = Model("DuplicateAssignments")
        model.groups["rack_A"] = {"name": "rack_A", "nodes": [], "elements": [], "supports": []}
        model.placement_frames["rack_A_frame"] = PlacementFrame(id="rack_A_frame", origin=(0.0, 0.0, 0.0))
        assignment = PlacementAssignment(
            target="group:rack_A",
            frame="placement_frame:rack_A_frame",
            role="object_placement",
            source="native",
        )
        model.placement_assignments.extend([assignment, assignment])

        with self.assertRaises(ModelValidationError) as ctx:
            model.validate()

        self.assertIn("duplicate object placement", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
