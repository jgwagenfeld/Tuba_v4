import unittest

from tuba import Model
from tuba.routing.grid import RoutingGrid
from tuba.routing.spaces import RoutingSpace, RoutingZone
from tuba.routing.types import PipeRouteRequest, RouteEndpoint, RoutingGridSpec


def _zone_model():
    model = Model("Zones")
    model.add_material("steel", E=210e9, nu=0.3, rho=7850.0)
    model.add_pipe_section("DN100", OD=0.1143, WT=0.00602)
    return model


class TestRoutingSpaces(unittest.TestCase):
    def test_point_classification_prefers_most_specific_zone(self):
        space = RoutingSpace(
            id="rack_A",
            zones=(
                RoutingZone(
                    id="rack_volume",
                    kind="allowed",
                    min_point=(0.0, 0.0, 0.0),
                    max_point=(10.0, 2.0, 2.0),
                ),
                RoutingZone(
                    id="maintenance_gap",
                    kind="forbidden",
                    min_point=(4.0, 0.0, 0.0),
                    max_point=(5.0, 2.0, 2.0),
                ),
            ),
            policy="require_allowed",
        )

        self.assertEqual(space.classify_point((1.0, 1.0, 1.0)).kind, "allowed")
        self.assertEqual(space.classify_point((4.5, 1.0, 1.0)).kind, "forbidden")
        self.assertIsNone(space.classify_point((12.0, 1.0, 1.0)))

    def test_invalid_zone_bounds_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "max_point must be greater"):
            RoutingZone(
                id="bad",
                kind="allowed",
                min_point=(1.0, 0.0, 0.0),
                max_point=(1.0, 2.0, 2.0),
            )


class TestRoutingGridZones(unittest.TestCase):
    def test_forbidden_zone_blocks_grid_cells(self):
        model = _zone_model()
        space = RoutingSpace(
            id="rack_A",
            zones=(
                RoutingZone(
                    "forbidden_gap",
                    "forbidden",
                    (1.0, -1.0, -1.0),
                    (2.0, 1.0, 1.0),
                ),
            ),
        )
        request = PipeRouteRequest(
            id="P-100",
            start=RouteEndpoint("A", (0.0, 0.0, 0.0)),
            goal=RouteEndpoint("B", (3.0, 0.0, 0.0)),
            section="DN100",
            material="steel",
            routing_space=space,
        )

        grid = RoutingGrid.from_model(model, request, RoutingGridSpec(cell_size=0.5, margin=1.0))

        self.assertTrue(grid.is_blocked(grid.world_to_index((1.5, 0.0, 0.0))))

    def test_reserved_zone_blocks_grid_cells(self):
        model = _zone_model()
        space = RoutingSpace(
            id="rack_A",
            zones=(
                RoutingZone(
                    "future_loop",
                    "reserved",
                    (1.0, -1.0, -1.0),
                    (2.0, 1.0, 1.0),
                ),
            ),
        )
        request = PipeRouteRequest(
            id="P-100",
            start=RouteEndpoint("A", (0.0, 0.0, 0.0)),
            goal=RouteEndpoint("B", (3.0, 0.0, 0.0)),
            section="DN100",
            material="steel",
            routing_space=space,
        )

        grid = RoutingGrid.from_model(model, request, RoutingGridSpec(cell_size=0.5, margin=1.0))

        self.assertTrue(grid.is_blocked(grid.world_to_index((1.5, 0.0, 0.0))))

    def test_preferred_zone_reduces_grid_penalty(self):
        model = _zone_model()
        space = RoutingSpace(
            id="rack_A",
            zones=(
                RoutingZone(
                    "rack_lane",
                    "preferred",
                    (0.0, -0.5, -0.5),
                    (3.0, 0.5, 0.5),
                    penalty=-2.0,
                ),
            ),
        )
        request = PipeRouteRequest(
            id="P-100",
            start=RouteEndpoint("A", (0.0, 0.0, 0.0)),
            goal=RouteEndpoint("B", (3.0, 0.0, 0.0)),
            section="DN100",
            material="steel",
            routing_space=space,
        )

        grid = RoutingGrid.from_model(model, request, RoutingGridSpec(cell_size=0.5, margin=1.0))

        corridor_penalty = grid.penalty(grid.world_to_index((1.0, 0.0, 0.0)))
        outside_penalty = grid.penalty(grid.world_to_index((1.0, 1.0, 0.0)))
        self.assertGreaterEqual(corridor_penalty, 0.0)
        self.assertLess(corridor_penalty, outside_penalty)

    def test_negative_preferred_zone_penalty_is_normalized_non_negative(self):
        model = _zone_model()
        space = RoutingSpace(
            id="rack_A",
            zones=(
                RoutingZone(
                    "rack_lane",
                    "preferred",
                    (0.0, -0.5, -0.5),
                    (3.0, 0.5, 0.5),
                    penalty=-2.0,
                ),
            ),
        )
        request = PipeRouteRequest(
            id="P-100",
            start=RouteEndpoint("A", (0.0, 0.0, 0.0)),
            goal=RouteEndpoint("B", (3.0, 0.0, 0.0)),
            section="DN100",
            material="steel",
            routing_space=space,
        )

        grid = RoutingGrid.from_model(model, request, RoutingGridSpec(cell_size=0.5, margin=1.0))

        self.assertGreaterEqual(float(grid.penalties.min()), 0.0)

    def test_prefer_allowed_policy_adds_allowed_zone_penalty(self):
        model = _zone_model()
        space = RoutingSpace(
            id="rack_A",
            zones=(
                RoutingZone(
                    "rack_lane",
                    "allowed",
                    (0.0, -0.5, -0.5),
                    (3.0, 0.5, 0.5),
                    penalty=-1.5,
                ),
            ),
            policy="prefer_allowed",
        )
        request = PipeRouteRequest(
            id="P-100",
            start=RouteEndpoint("A", (0.0, 0.0, 0.0)),
            goal=RouteEndpoint("B", (3.0, 0.0, 0.0)),
            section="DN100",
            material="steel",
            routing_space=space,
        )

        grid = RoutingGrid.from_model(model, request, RoutingGridSpec(cell_size=0.5, margin=1.0))

        corridor_penalty = grid.penalty(grid.world_to_index((1.0, 0.0, 0.0)))
        outside_penalty = grid.penalty(grid.world_to_index((1.0, 1.0, 0.0)))
        self.assertGreaterEqual(corridor_penalty, 0.0)
        self.assertLess(corridor_penalty, outside_penalty)

    def test_unrestricted_allowed_zone_ignores_allowed_zone_penalty(self):
        model = _zone_model()
        space = RoutingSpace(
            id="rack_A",
            zones=(
                RoutingZone(
                    "rack_lane",
                    "allowed",
                    (0.0, -0.5, -0.5),
                    (3.0, 0.5, 0.5),
                    penalty=-1.5,
                ),
            ),
        )
        request = PipeRouteRequest(
            id="P-100",
            start=RouteEndpoint("A", (0.0, 0.0, 0.0)),
            goal=RouteEndpoint("B", (3.0, 0.0, 0.0)),
            section="DN100",
            material="steel",
            routing_space=space,
        )

        grid = RoutingGrid.from_model(model, request, RoutingGridSpec(cell_size=0.5, margin=1.0))

        corridor_penalty = grid.penalty(grid.world_to_index((1.0, 0.0, 0.0)))
        outside_penalty = grid.penalty(grid.world_to_index((1.0, 1.0, 0.0)))
        self.assertGreaterEqual(corridor_penalty, 0.0)
        self.assertEqual(corridor_penalty, outside_penalty)
        self.assertEqual(corridor_penalty, 0.0)

    def test_require_allowed_blocks_outside_zones_but_keeps_endpoints_open(self):
        model = _zone_model()
        space = RoutingSpace(
            id="rack_A",
            zones=(
                RoutingZone(
                    "rack_lane",
                    "allowed",
                    (0.5, -0.5, -0.5),
                    (2.5, 0.5, 0.5),
                ),
            ),
            policy="require_allowed",
        )
        request = PipeRouteRequest(
            id="P-100",
            start=RouteEndpoint("A", (0.0, 0.0, 0.0)),
            goal=RouteEndpoint("B", (3.0, 0.0, 0.0)),
            section="DN100",
            material="steel",
            routing_space=space,
        )

        grid = RoutingGrid.from_model(model, request, RoutingGridSpec(cell_size=0.5, margin=1.0))

        self.assertTrue(grid.is_blocked(grid.world_to_index((0.0, 1.0, 0.0))))
        self.assertFalse(grid.is_blocked(grid.world_to_index(request.start.point)))
        self.assertFalse(grid.is_blocked(grid.world_to_index(request.goal.point)))

    def test_no_routing_space_keeps_zero_grid_penalties(self):
        model = _zone_model()
        request = PipeRouteRequest(
            id="P-100",
            start=RouteEndpoint("A", (0.0, 0.0, 0.0)),
            goal=RouteEndpoint("B", (3.0, 0.0, 0.0)),
            section="DN100",
            material="steel",
        )

        grid = RoutingGrid.from_model(model, request, RoutingGridSpec(cell_size=0.5, margin=1.0))

        self.assertEqual(float(grid.penalties.min()), 0.0)
        self.assertEqual(float(grid.penalties.max()), 0.0)


if __name__ == "__main__":
    unittest.main()
