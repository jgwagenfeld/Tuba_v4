import unittest

from tuba.routing.thermal import SolverAcceptanceCriteria, ThermalRouteRequirement, estimate_free_expansion


class TestRoutingThermal(unittest.TestCase):
    def test_free_expansion_uses_alpha_delta_t_and_length(self):
        requirement = ThermalRouteRequirement(
            design_temperature_c=180.0,
            reference_temperature_c=20.0,
            line_length_m=25.0,
            thermal_expansion_coefficient=12e-6,
        )

        self.assertAlmostEqual(estimate_free_expansion(requirement), 0.048)

    def test_solver_acceptance_has_strict_hot_line_defaults(self):
        criteria = SolverAcceptanceCriteria.hot_line_defaults()

        self.assertEqual(criteria.max_expansion_ratio, 1.0)
        self.assertGreater(criteria.max_anchor_reaction_n, 0.0)
        self.assertGreater(criteria.max_operating_clearance_violation_m, -1e-12)


if __name__ == "__main__":
    unittest.main()
