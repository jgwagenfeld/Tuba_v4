import unittest

from tuba.geometry.spatial import SpatialIndex, bounds_overlap


class TestSpatialIndex(unittest.TestCase):
    def test_query_returns_only_overlapping_bounds(self):
        index = SpatialIndex.from_bounds(
            [
                ("near", (0.0, 0.0, 0.0, 1.0, 1.0, 1.0)),
                ("far", (5.0, 5.0, 5.0, 6.0, 6.0, 6.0)),
                ("touching", (1.0, 0.2, 0.2, 2.0, 0.8, 0.8)),
            ]
        )

        candidates = index.query((0.25, 0.25, 0.25, 1.25, 0.75, 0.75))

        self.assertEqual(set(candidates), {"near", "touching"})

    def test_candidate_pairs_reduce_sparse_all_pairs(self):
        right_index = SpatialIndex.from_bounds(
            (f"right_{idx}", (idx * 10.0, -0.25, -0.25, idx * 10.0 + 1.0, 0.25, 0.25))
            for idx in range(20)
        )
        left_bounds = [
            (f"left_{idx}", (idx * 10.0 + 0.25, -0.1, -0.1, idx * 10.0 + 0.75, 0.1, 0.1))
            for idx in range(20)
        ]

        pairs = right_index.candidate_pairs(left_bounds)

        self.assertEqual(len(pairs), 20)
        self.assertLess(len(pairs), len(left_bounds) * len(right_index))
        self.assertTrue(bounds_overlap((0, 0, 0, 1, 1, 1), (1, 1, 1, 2, 2, 2)))
        self.assertFalse(bounds_overlap((0, 0, 0, 1, 1, 1), (1.01, 0, 0, 2, 1, 1)))


if __name__ == "__main__":
    unittest.main()
