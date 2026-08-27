import unittest

from tests.operating_state_fixtures import (
    bend_near_obstacle_fixture,
    insulated_pipe_near_rack_fixture,
    pipe_supported_by_rack_fixture,
    straight_pipe_hot_clash_fixture,
)
from tuba.clash import ClashEngine


class TestOperatingStateFixtures(unittest.TestCase):
    def test_straight_fixture_is_cold_clear_and_hot_clashing(self):
        fixture = straight_pipe_hot_clash_fixture()

        cold_clashes = ClashEngine().check_model(fixture.model)
        self.assertEqual(cold_clashes, [])
        self.assertEqual(fixture.results.solver_name, "mock")
        self.assertEqual(fixture.results.load_case, "Hot")

    def test_fixture_suite_covers_bend_rack_support_and_reactions_without_code_aster(self):
        bend = bend_near_obstacle_fixture()
        insulated = insulated_pipe_near_rack_fixture()
        supported = pipe_supported_by_rack_fixture()

        self.assertEqual(ClashEngine().check_model(bend.model), [])
        self.assertTrue(insulated.rack_group_id)
        self.assertTrue(supported.support_id)
        self.assertIn(supported.support_node_id, supported.results.node_results)
        self.assertIsNotNone(supported.results.get_reaction(supported.support_node_id))


if __name__ == "__main__":
    unittest.main()
