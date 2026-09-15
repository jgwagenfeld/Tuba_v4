import math
import unittest

import numpy as np

from tuba import Model
from tuba.model import BendGeometry
from tuba.sampling import field_from_cloud, field_from_function, field_from_route_table


def _model(name: str = "Sampling") -> Model:
    model = Model(project_name=name)
    model.add_material("Steel", E=2.0e11, nu=0.3, alpha=1.2e-5)
    model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
    return model


def _two_element_route() -> Model:
    """pipe_str_0 runs N0 (0, 0, 0) to N1 (1, 0, 0), pipe_str_1 runs N1 to N2 (2, 0, 0); stations 0 to 2 on P-100."""
    model = _model()
    with model.pipe("PipeSec", "Steel", route="P-100") as pipe:
        pipe.start([0.0, 0.0, 0.0], support="anchor")
        pipe.run(1.0)
        pipe.run(1.0)
        pipe.end(support="anchor")
    return model


def _elbow_model(*, stored_geometry: bool = True) -> Model:
    """run: N0 (0, 0, 0) to N1 (4, 0, 0); elbow: 90 degrees, R 0.5, N1 to N2 (4.5, 0.5, 0); anchored at N0 and N2."""
    model = _model("SamplingElbow")
    start = model.add_node([0.0, 0.0, 0.0])
    corner = model.add_node([4.0, 0.0, 0.0])
    end = model.add_node([4.5, 0.5, 0.0])
    model.add_element(id="run", type="pipe_straight", n1=start, n2=corner, section="PipeSec", material="Steel")
    geometry = BendGeometry(
        center=[4.0, 0.5, 0.0], normal=[0.0, 0.0, 1.0], radius=0.5, angle=90,
        start_tangent=[1.0, 0.0, 0.0], end_tangent=[0.0, 1.0, 0.0],
    )
    model.add_element(
        id="elbow", type="pipe_bend", n1=corner, n2=end, section="PipeSec", material="Steel",
        bend_radius=0.5, bend_angle=90, bend_geometry=geometry if stored_geometry else None,
    )
    model.add_support(start, "anchor")
    model.add_support(end, "anchor")
    return model


class TestFieldFromCloud(unittest.TestCase):
    def test_a_ring_of_wall_points_gives_the_node_its_circumferential_mean(self):
        model = _two_element_route()
        operation = model.define_operation("CFD", gravity=False)
        # Eight wall points on the 0.05 m pipe radius around N1, plus one point on each end node.
        ring = [[1.0, 0.05 * math.cos(angle), 0.05 * math.sin(angle)] for angle in np.linspace(0.0, 2.0 * math.pi, 8, endpoint=False)]
        points = ring + [[0.0, 0.0, 0.0], [2.0, 0.0, 0.0]]
        values = [100.0 + 10.0 * k for k in range(8)] + [50.0, 70.0]

        fields = field_from_cloud(model, operation, "temperature", points, values)

        self.assertEqual([(f.node_ids, f.value) for f in fields], [(["N0"], 50.0), (["N1"], 135.0), (["N2"], 70.0)])
        model.validate()

    def test_targets_without_a_point_are_refused_and_nothing_is_written(self):
        model = _two_element_route()
        operation = model.define_operation("CFD", gravity=False)
        # The default radius is 1.25 x the 0.05 m bare radius; only N0 has a point that close.
        with self.assertRaisesRegex(
            ValueError,
            r"2 target\(s\) have no cloud point within the capture radius: 'N1' nearest point 1 m, radius 0\.0625 m; "
            r"'N2' nearest point 2 m.*units \(mm vs m\)",
        ):
            field_from_cloud(model, operation, "temperature", [[0.0, 0.0, 0.0]], [80.0])
        self.assertEqual(operation.fields, [])

        fields = field_from_cloud(model, operation, "temperature", [[0.0, 0.0, 0.0]], [80.0], capture_radius=2.5)
        self.assertEqual([f.value for f in fields], [80.0, 80.0, 80.0])

        with self.assertRaisesRegex(ValueError, r"points must have shape \(N, 3\)"):
            field_from_cloud(model, operation, "temperature", [[0.0, 0.0]], [80.0])


class TestFieldFromFunction(unittest.TestCase):
    def test_values_land_on_nodes_and_on_the_bend_arc_midpoint(self):
        model = _elbow_model()
        operation = model.define_operation("Formula", gravity=False)

        temperatures = field_from_function(model, operation, "temperature", lambda x, y, z: 20.0 + 10.0 * x + 100.0 * y)
        self.assertEqual([(f.node_ids, f.value) for f in temperatures], [(["N0"], 20.0), (["N1"], 60.0), (["N2"], 115.0)])

        winds = field_from_function(model, operation, "wind", lambda x, y, z: 1000.0 * y, direction=[0.0, 1.0, 0.0])
        # The run's midpoint is (2, 0, 0); the elbow's arc midpoint is the centre (4, 0.5) plus R (sin 45, -cos 45).
        self.assertEqual([f.element_ids for f in winds], [["run"], ["elbow"]])
        self.assertAlmostEqual(winds[0].value, 0.0)
        self.assertAlmostEqual(winds[1].value, 1000.0 * (0.5 - 0.5 * math.cos(math.pi / 4.0)))
        self.assertEqual(winds[1].direction, [0.0, 1.0, 0.0])
        model.validate()

    def test_helpers_follow_the_field_rules(self):
        model = _two_element_route()
        operation = model.define_operation("Rules", gravity=False)
        for quantity in ("wind", "line_load"):
            with self.subTest(quantity=quantity), self.assertRaisesRegex(ValueError, f"{quantity} needs a direction"):
                field_from_function(model, operation, quantity, lambda x, y, z: 1000.0)
        with self.assertRaisesRegex(ValueError, "temperature takes no direction"):
            field_from_function(model, operation, "temperature", lambda x, y, z: 80.0, direction=[1.0, 0.0, 0.0])
        with self.assertRaisesRegex(TypeError, "formula strings are not evaluated"):
            field_from_function(model, operation, "temperature", "20 + 10 * x")
        with self.assertRaisesRegex(ValueError, "function returned nan at 'N0'"):
            field_from_function(model, operation, "temperature", lambda x, y, z: float("nan"))
        with self.assertRaisesRegex(ValueError, r"line_load station range 0 to 0\.5 only partly covers 'pipe_str_0'"):
            field_from_function(
                model, operation, "line_load", lambda x, y, z: 100.0, direction=[0.0, 0.0, -1.0],
                route_id="P-100", station_start=0.0, station_end=0.5,
            )
        self.assertEqual(operation.fields, [])

        for kind in ("bar", "cable"):
            rack = _model("Rack")
            with rack.pipe("PipeSec", "Steel", route="RACK") as pipe:
                pipe.start([0.0, 0.0, 0.0], support="anchor")
                pipe.run(2.0)
                getattr(pipe, kind)(2.0)
                pipe.end(support="anchor")
            with self.subTest(element=kind), self.assertRaisesRegex(ValueError, rf"cannot carry 'wind': \['{kind}_0'\]"):
                field_from_function(
                    rack, rack.define_operation("Wind", gravity=False), "wind", lambda x, y, z: 1000.0,
                    direction=[0.0, 1.0, 0.0], route_id="RACK",
                )

    def test_bends_without_stored_geometry_have_no_known_midpoint(self):
        model = _elbow_model(stored_geometry=False)
        operation = model.define_operation("Formula", gravity=False)
        with self.assertRaisesRegex(ValueError, "Bend 'elbow' has no stored bend_geometry"):
            field_from_function(model, operation, "pressure", lambda x, y, z: 1.0e6)
        self.assertEqual(operation.fields, [])


class TestFieldFromRouteTable(unittest.TestCase):
    def test_tables_interpolate_by_station_and_refuse_stations_outside_them(self):
        model = _two_element_route()
        operation = model.define_operation("Table", gravity=False)

        pressures = field_from_route_table(model, operation, "pressure", "P-100", [(0.0, 1.0e6), (2.0, 3.0e6)])
        # Element stations are their midpoints, 0.5 and 1.5.
        self.assertEqual(
            [(f.element_ids, f.value) for f in pressures], [(["pipe_str_0"], 1.5e6), (["pipe_str_1"], 2.5e6)]
        )

        with self.assertRaisesRegex(
            ValueError, r"'N2' sits at station 2, outside the table's stations 0 to 1; narrow the selection"
        ):
            field_from_route_table(model, operation, "temperature", "P-100", [(0.0, 100.0), (1.0, 200.0)])
        self.assertEqual(len(operation.fields), 2)

        temperatures = field_from_route_table(
            model, operation, "temperature", "P-100", [(0.0, 100.0), (1.0, 200.0)], station_start=0.0, station_end=1.0
        )
        self.assertEqual([(f.node_ids, f.value) for f in temperatures], [(["N0"], 100.0), (["N1"], 200.0)])

        with self.assertRaisesRegex(ValueError, "strictly increasing stations"):
            field_from_route_table(model, operation, "temperature", "P-100", [(1.0, 100.0), (0.0, 200.0)])

    def test_a_table_without_a_route_id_is_refused_and_nothing_is_written(self):
        # Without a route_id the selection would span every run in the model, not the one the table follows.
        model = _model()
        with model.pipe("PipeSec", "Steel") as pipe:
            pipe.start([0.0, 0.0, 0.0], support="anchor")
            pipe.run(1.0)
            pipe.run(1.0)
            pipe.end(support="anchor")
        operation = model.define_operation("Table", gravity=False)

        with self.assertRaisesRegex(
            ValueError,
            r"field_from_route_table needs the route_id of the route the table follows; "
            r"name unnamed runs with model\.pipe\(\.\.\., route=\.\.\.\)\.",
        ):
            field_from_route_table(model, operation, "temperature", None, [(0.0, 100.0), (2.0, 300.0)])
        self.assertEqual(operation.fields, [])
