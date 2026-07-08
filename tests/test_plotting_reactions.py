import unittest

import numpy as np

from tuba import Model
from tuba.plotting.plots import _reaction_glyph_factor, _reaction_vector_points
from tuba.solver.base import FEAResults, NodeResult


class TestPlottingReactions(unittest.TestCase):
    def test_reaction_vectors_use_native_nodes_not_surface_points(self):
        model = Model(project_name="ReactionPlot")
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 0.0, 0.0])
        results = FEAResults(solver_name="mock", load_case="Hot")
        results.node_results[n0] = NodeResult(
            node_id=n0,
            displacement=np.zeros(6),
            reaction_force=np.array([100.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
        )
        results.node_results[n1] = NodeResult(
            node_id=n1,
            displacement=np.zeros(6),
            reaction_force=np.zeros(6),
        )

        points, vectors, magnitudes = _reaction_vector_points(results, model)

        self.assertEqual(points.shape, (1, 3))
        self.assertTrue(np.allclose(vectors, [[100.0, 0.0, 0.0]]))
        self.assertTrue(np.allclose(magnitudes, [100.0]))

    def test_auto_reaction_scale_is_bounded_by_model_size(self):
        factor = _reaction_glyph_factor("auto", [0.0, 0.0, 0.0, 10.0, 0.0, 0.0], np.array([1000.0]))

        self.assertAlmostEqual(factor, 0.0012)


if __name__ == "__main__":
    unittest.main()
