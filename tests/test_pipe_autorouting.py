import unittest

from tuba import Model
from tuba.routing import GridRouter, PipeRouteRequest, RouteEndpoint, RoutingConstraints, RoutingGridSpec


class TestPipeAutorouting(unittest.TestCase):
    def test_grid_router_returns_direct_candidate_in_clear_space(self):
        model = Model(project_name="PipeAutorouting")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        request = PipeRouteRequest(
            id="P-100",
            start=RouteEndpoint(id="A", point=(0.0, 0.0, 0.0)),
            goal=RouteEndpoint(id="B", point=(3.0, 0.0, 0.0)),
            section="PipeSec",
            material="Steel",
            constraints=RoutingConstraints(),
        )

        result = GridRouter(RoutingGridSpec(cell_size=1.0, margin=1.0)).route(model, request)

        self.assertIsNotNone(result.selected)
        self.assertEqual(result.selected.points, [(0.0, 0.0, 0.0), (3.0, 0.0, 0.0)])


if __name__ == "__main__":
    unittest.main()
