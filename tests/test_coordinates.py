import unittest

import numpy as np

from tuba.coordinates import CoordinateSystem


class TestCoordinateSystem(unittest.TestCase):
    def test_identity_transform_keeps_point(self):
        cs = CoordinateSystem.identity()
        self.assertTrue(np.allclose(cs.to_global_point((1.0, 2.0, 3.0)), (1.0, 2.0, 3.0)))

    def test_translation_and_rotation_transform_point(self):
        cs = CoordinateSystem(
            origin=(10.0, 20.0, 30.0),
            x_axis=(0.0, 1.0, 0.0),
            y_axis=(-1.0, 0.0, 0.0),
            z_axis=(0.0, 0.0, 1.0),
        )

        point = cs.to_global_point((2.0, 3.0, 4.0))

        self.assertTrue(np.allclose(point, (7.0, 22.0, 34.0)))

    def test_inverse_roundtrip(self):
        cs = CoordinateSystem(
            origin=(4.0, -2.0, 1.0),
            x_axis=(0.0, 1.0, 0.0),
            y_axis=(0.0, 0.0, 1.0),
            z_axis=(1.0, 0.0, 0.0),
        )

        local = np.array((1.5, 2.5, -3.0))
        global_point = cs.to_global_point(local)
        roundtrip = cs.to_local_point(global_point)

        self.assertTrue(np.allclose(roundtrip, local))

    def test_non_orthogonal_axes_are_rejected(self):
        with self.assertRaises(ValueError):
            CoordinateSystem(
                origin=(0.0, 0.0, 0.0),
                x_axis=(1.0, 0.0, 0.0),
                y_axis=(1.0, 0.0, 0.0),
                z_axis=(0.0, 0.0, 1.0),
            )


if __name__ == "__main__":
    unittest.main()
