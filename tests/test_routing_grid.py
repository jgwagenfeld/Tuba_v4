import unittest

from tuba import Model
from tuba.routing.grid import RoutingGrid
from tuba.routing.types import (
    PipeRouteRequest,
    RouteEndpoint,
    RoutingConstraints,
    RoutingGridSpec,
)


def _model():
    model = Model(project_name="RoutingGrid")
    model.add_material("Steel", E=2.0e11, nu=0.3)
    model.add_pipe_section("PipeSec", OD=0.2, WT=0.01)
    return model


def _request(**kwargs):
    return PipeRouteRequest(
        id="P-100",
        start=RouteEndpoint(id="A", point=(0.0, 0.0, 0.0)),
        goal=RouteEndpoint(id="B", point=(4.0, 0.0, 0.0)),
        section="PipeSec",
        material="Steel",
        constraints=RoutingConstraints(clearance=0.0, **kwargs),
    )


class TestRoutingGrid(unittest.TestCase):
    def test_coordinate_index_roundtrip(self):
        grid = RoutingGrid.from_model(
            _model(),
            _request(),
            RoutingGridSpec(cell_size=1.0, margin=1.0),
        )
        idx = grid.world_to_index((2.0, 0.0, 0.0))
        point = grid.index_to_world(idx)
        self.assertEqual(point, (2.0, 0.0, 0.0))

    def test_cuboid_obstacle_inflation(self):
        model = _model()
        model.add_obstacle(
            id="box",
            type="cuboid",
            min_point=[1.5, -0.5, -0.5],
            max_point=[2.5, 0.5, 0.5],
        )
        grid = RoutingGrid.from_model(
            model,
            _request(),
            RoutingGridSpec(cell_size=1.0, margin=1.0),
        )
        self.assertTrue(grid.is_blocked(grid.world_to_index((2.0, 0.0, 0.0))))
        self.assertFalse(grid.is_blocked(grid.world_to_index((2.0, 2.0, 0.0))))

    def test_existing_pipe_blocks_cells(self):
        model = _model()
        with model.pipe(section="PipeSec", material="Steel") as b:
            b.start([1.0, 0.0, 0.0]).run(2.0)

        grid = RoutingGrid.from_model(
            model,
            _request(),
            RoutingGridSpec(cell_size=1.0, margin=1.0),
        )
        self.assertTrue(grid.is_blocked(grid.world_to_index((2.0, 0.0, 0.0))))

    def test_grid_size_guardrail(self):
        with self.assertRaises(ValueError):
            RoutingGrid.from_model(
                _model(),
                _request(),
                RoutingGridSpec(
                    cell_size=0.01,
                    bounds_min=(0.0, 0.0, 0.0),
                    bounds_max=(10.0, 10.0, 10.0),
                    margin=0.0,
                    max_cells=1000,
                ),
            )

    def test_validate_polyline_detects_blocked_simplified_segment(self):
        model = _model()
        model.add_obstacle(
            id="box",
            type="cuboid",
            min_point=[1.5, -0.5, -0.5],
            max_point=[2.5, 0.5, 0.5],
        )
        grid = RoutingGrid.from_model(
            model,
            _request(),
            RoutingGridSpec(cell_size=0.5, margin=1.0),
        )

        direct = grid.validate_polyline([(0.0, 0.0, 0.0), (4.0, 0.0, 0.0)], "P-100")
        detour = grid.validate_polyline(
            [(0.0, 0.0, 0.0), (0.0, 1.5, 0.0), (4.0, 1.5, 0.0), (4.0, 0.0, 0.0)],
            "P-100",
        )

        self.assertIn("blocked cell", " ".join(direct))
        self.assertEqual(detour, [])


if __name__ == "__main__":
    unittest.main()
