import unittest

from tuba import Model
from tuba.routing import GridRouter
from tuba.routing.planner import AStarPipePlanner, PipePlanner, SearchState
from tuba.routing.types import (
    PipeRouteRequest,
    RouteEndpoint,
    RoutingConstraints,
    RoutingGridSpec,
)


def _base_model():
    model = Model(project_name="AStarRouting")
    model.add_material("Steel", E=2.0e11, nu=0.3)
    model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
    return model


def _req(start=(0.0, 0.0, 0.0), goal=(4.0, 0.0, 0.0), **constraint_kwargs):
    clearance = constraint_kwargs.pop("clearance", 0.0)
    start_direction = constraint_kwargs.pop("start_direction", None)
    goal_direction = constraint_kwargs.pop("goal_direction", None)
    start_min_straight = constraint_kwargs.pop("start_min_straight", 0.0)
    goal_min_straight = constraint_kwargs.pop("goal_min_straight", 0.0)
    return PipeRouteRequest(
        id="P-100",
        start=RouteEndpoint(id="A", point=start, direction=start_direction, min_straight=start_min_straight),
        goal=RouteEndpoint(id="B", point=goal, direction=goal_direction, min_straight=goal_min_straight),
        section="PipeSec",
        material="Steel",
        constraints=RoutingConstraints(clearance=clearance, **constraint_kwargs),
    )


class TestGridRouter(unittest.TestCase):
    def test_astar_pipe_planner_uses_grid_router_interface(self):
        planner = AStarPipePlanner(RoutingGridSpec(cell_size=1.0, margin=1.0))

        self.assertIsInstance(planner, PipePlanner)
        result = planner.plan_pipe(_base_model(), _req(goal=(3.0, 0.0, 0.0)))

        self.assertIsNotNone(result.selected)
        self.assertEqual(result.selected.points, [(0.0, 0.0, 0.0), (3.0, 0.0, 0.0)])

    def test_search_state_tracks_direction_and_straight_run(self):
        state = SearchState(cell=(1, 0, 0), incoming=(1, 0, 0), straight_run_m=2.0)

        self.assertEqual(state.cell, (1, 0, 0))
        self.assertEqual(state.incoming, (1, 0, 0))
        self.assertEqual(state.straight_run_m, 2.0)
        self.assertEqual(len({state}), 1)

    def test_direct_route_empty_space(self):
        router = GridRouter(RoutingGridSpec(cell_size=1.0, margin=1.0))
        result = router.route(_base_model(), _req(goal=(3.0, 0.0, 0.0)))

        self.assertIsNotNone(result.selected)
        self.assertEqual(result.selected.points, [(0.0, 0.0, 0.0), (3.0, 0.0, 0.0)])
        self.assertEqual(result.selected.cost_breakdown["bends"], 0)

    def test_allow_diagonal_uses_diagonal_neighbors(self):
        model = _base_model()
        orthogonal = GridRouter(RoutingGridSpec(cell_size=1.0, margin=1.0, allow_diagonal=False)).route(
            model,
            _req(goal=(1.0, 1.0, 0.0)),
        )
        diagonal = GridRouter(RoutingGridSpec(cell_size=1.0, margin=1.0, allow_diagonal=True)).route(
            model,
            _req(goal=(1.0, 1.0, 0.0)),
        )

        self.assertGreater(len(orthogonal.selected.points), 2)
        self.assertEqual(diagonal.selected.points, [(0.0, 0.0, 0.0), (1.0, 1.0, 0.0)])

    def test_routes_around_cuboid(self):
        model = _base_model()
        model.add_obstacle(
            id="box",
            type="cuboid",
            min_point=[1.5, -0.5, -0.5],
            max_point=[2.5, 0.5, 0.5],
        )
        router = GridRouter(RoutingGridSpec(cell_size=1.0, margin=2.0))
        result = router.route(model, _req())

        self.assertIsNotNone(result.selected)
        self.assertNotEqual(result.selected.points, [(0.0, 0.0, 0.0), (4.0, 0.0, 0.0)])
        self.assertTrue(any(abs(y) >= 1.0 or abs(z) >= 1.0 for _x, y, z in result.selected.points))

    def test_no_route_when_blocked(self):
        model = _base_model()
        model.add_obstacle(
            id="wall",
            type="cuboid",
            min_point=[1.5, -2.0, -2.0],
            max_point=[2.5, 2.0, 2.0],
        )
        router = GridRouter(
            RoutingGridSpec(
                cell_size=1.0,
                bounds_min=(0.0, -1.0, -1.0),
                bounds_max=(4.0, 1.0, 1.0),
                margin=0.0,
            )
        )
        result = router.route(model, _req())

        self.assertIsNone(result.selected)
        self.assertIn("No route found", " ".join(result.diagnostics))

    def test_endpoint_outside_explicit_bounds_returns_diagnostic(self):
        router = GridRouter(
            RoutingGridSpec(
                cell_size=1.0,
                bounds_min=(0.0, -1.0, -1.0),
                bounds_max=(2.0, 1.0, 1.0),
                margin=0.0,
            )
        )
        result = router.route(_base_model(), _req(goal=(4.0, 0.0, 0.0)))

        self.assertIsNone(result.selected)
        self.assertIn("outside routing grid bounds", " ".join(result.diagnostics))

    def test_multiple_candidates(self):
        model = _base_model()
        model.add_obstacle(
            id="box",
            type="cuboid",
            min_point=[1.5, -0.5, -0.5],
            max_point=[2.5, 0.5, 0.5],
        )
        router = GridRouter(
            RoutingGridSpec(cell_size=1.0, margin=2.0),
            candidate_count=2,
        )
        result = router.route(model, _req())

        self.assertGreaterEqual(len(result.candidates), 2)
        self.assertNotEqual(result.candidates[0].points, result.candidates[1].points)

    def test_selects_lowest_cost_valid_candidate(self):
        model = _base_model()
        model.add_obstacle(
            id="equipment_box",
            type="cuboid",
            min_point=[1.5, -0.4, -0.4],
            max_point=[2.5, 0.4, 0.4],
        )
        router = GridRouter(
            RoutingGridSpec(cell_size=0.25, margin=1.0),
            candidate_count=3,
        )
        result = router.route(
            model,
            _req(clearance=0.10, min_bend_radius=0.20),
        )

        self.assertIsNotNone(result.selected)
        valid_costs = [candidate.cost for candidate in result.candidates if candidate.is_valid]
        self.assertEqual(result.selected.cost, min(valid_costs))

    def test_alternative_generation_failure_is_nonfatal_diagnostic(self):
        model = _base_model()
        model.add_obstacle(
            id="equipment_box",
            type="cuboid",
            min_point=[1.5, -0.4, -0.4],
            max_point=[2.5, 0.4, 0.4],
        )
        router = GridRouter(
            RoutingGridSpec(cell_size=0.25, margin=1.0),
            candidate_count=3,
        )
        result = router.route(
            model,
            _req(
                clearance=0.10,
                min_bend_radius=0.20,
                start_direction=(1.0, 0.0, 0.0),
                goal_direction=(0.0, -1.0, 0.0),
            ),
        )

        self.assertIsNotNone(result.selected)
        self.assertNotIn("No route found", " ".join(result.diagnostics))
        self.assertIn("No additional route", " ".join(result.diagnostics))

    def test_endpoint_direction_and_min_straight_are_respected(self):
        router = GridRouter(RoutingGridSpec(cell_size=1.0, margin=3.0))
        result = router.route(
            _base_model(),
            _req(
                goal=(4.0, 0.0, 0.0),
                start_direction=(0.0, 1.0, 0.0),
                goal_direction=(0.0, -1.0, 0.0),
                start_min_straight=2.0,
                goal_min_straight=2.0,
            ),
        )

        self.assertIsNotNone(result.selected)
        self.assertEqual(result.selected.points[0], (0.0, 0.0, 0.0))
        self.assertEqual(result.selected.points[-1], (4.0, 0.0, 0.0))
        first_leg = tuple(result.selected.points[1][i] - result.selected.points[0][i] for i in range(3))
        last_leg = tuple(result.selected.points[-1][i] - result.selected.points[-2][i] for i in range(3))
        self.assertEqual(first_leg, (0.0, 2.0, 0.0))
        self.assertEqual(last_leg, (0.0, -2.0, 0.0))


if __name__ == "__main__":
    unittest.main()
