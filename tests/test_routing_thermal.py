import unittest

from tuba.routing.thermal import SolverAcceptanceCriteria


class TestRoutingThermal(unittest.TestCase):
    def test_solver_acceptance_has_strict_hot_line_defaults(self):
        criteria = SolverAcceptanceCriteria.hot_line_defaults()

        self.assertEqual(criteria.max_expansion_ratio, 1.0)
        self.assertGreater(criteria.max_anchor_reaction_n, 0.0)
        self.assertGreater(criteria.max_operating_clearance_violation_m, -1e-12)


if __name__ == "__main__":
    unittest.main()
