"""The braced-rack thermal split: bracing, shoe layout, growth, line weight."""

import unittest
from pathlib import Path

from tuba import Model
from tuba.project import load_project

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
PROJECT = "braced-rack-thermal-split"


def _namespace() -> dict:
    return load_project(EXAMPLES / PROJECT).run_model()


def _shoe_supports(model):
    return [support for support in model.supports if support.type == "rest" and support.attached_to]


def _mid_nodes(model) -> dict:
    """Station number to the cross-beam midpoint node its shoes hang from."""
    mids = {}
    for group in model.groups.values():
        for name, ref in group.get("metadata", {}).get("attachment_points", {}).items():
            if name.startswith("mid_"):
                mids[int(name[4:])] = ref.split(":", 1)[1]
    return mids


class ThermalSplitLayout(unittest.TestCase):
    def test_row_is_four_bays_of_six_metres_with_a_shoe_level(self):
        ns = _namespace()
        model = ns["model"]

        self.assertEqual(model.project_name, "BracedRackThermalSplit")
        self.assertEqual(sorted(model.groups), ["rack0", "rack1", "rack2", "rack3"])
        self.assertEqual(ns["rack_run_length"], 24.0)
        self.assertEqual(len(_mid_nodes(model)), 5)

    def test_line_puts_a_node_at_every_station_mid_width(self):
        model = _namespace()["model"]
        stations = _mid_nodes(model)

        self.assertEqual(len(stations), 5)
        for station, node in stations.items():
            coords = model.nodes[node].coords
            self.assertAlmostEqual(coords[0], station * 6.0)
            self.assertAlmostEqual(coords[1], 1.2)  # half of the 2.4 m rack width
            self.assertAlmostEqual(coords[2], 5.5)  # the shoe level

    def test_every_sliding_shoe_hangs_from_its_own_station_midpoint(self):
        model = _namespace()["model"]
        mids = _mid_nodes(model)
        shoes = _shoe_supports(model)

        self.assertEqual(len(shoes), 4)
        self.assertEqual([support.friction_coefficient for support in shoes], [0.3] * 4)
        for support in shoes:
            pipe = model.nodes[support.node].coords
            beam = model.nodes[support.attached_to].coords
            self.assertEqual(support.attached_to, mids[round(pipe[0] / 6.0)])
            self.assertAlmostEqual(pipe[1], beam[1])
            # The pipe sits above the beam midpoint by the shoe offset, not on it.
            self.assertAlmostEqual(pipe[2] - beam[2], 0.33655, places=5)

    def test_the_fixed_point_is_at_mid_run_so_shoe_travel_stays_short(self):
        # The defect this arrangement exists to avoid: with the fixed point at an
        # end station the line slid 78 mm at the far shoe, well past what a guide
        # shoe allows. Mid-run halves it to about 40 mm and makes the thermal
        # response symmetric, because the line and the rack share a thermal centre.
        model = _namespace()["model"]
        attached = [
            support
            for support in model.supports
            if support.type == "anchor" and support.attached_to is not None
        ]

        self.assertEqual(len(attached), 1)
        self.assertEqual(attached[0].attached_to, _mid_nodes(model)[2])
        self.assertAlmostEqual(model.nodes[attached[0].node].coords[0], 12.0)
        feet = [s for s in model.supports if s.type == "anchor" and s.attached_to is None]
        self.assertEqual(len(feet), 10)

    def test_each_approach_guide_leaves_the_line_free_along_the_rack(self):
        model = _namespace()["model"]
        guides = [support for support in model.supports if support.type == "guide"]

        # One per approach. A guide shoe (a guide on a shoe node) is not
        # expressible, so the end stations are plain rests and these are the only
        # lateral restraints the line has.
        self.assertEqual(len(guides), 2)
        for guide in guides:
            self.assertIsNone(guide.attached_to)  # ground guides, not rack guides
            self.assertEqual(guide.direction, [0.0, 1.0, 0.0])
            self.assertEqual(
                guide.restraint().states, ("free", "fixed", "free", "free", "free", "free")
            )

    def test_no_shoe_shares_its_node_with_a_guide(self):
        # Tuba refuses this combination, so the example must not contain it. If
        # guide shoes ever become expressible this is the assertion to revisit.
        model = _namespace()["model"]
        shoe_nodes = {support.node for support in model.supports if support.type == "rest"}
        guide_nodes = {support.node for support in model.supports if support.type == "guide"}

        self.assertEqual(shoe_nodes & guide_nodes, set())


class ThermalSplitBracing(unittest.TestCase):
    def test_end_bays_are_x_braced_panel_by_panel_with_a_shared_gusset_node(self):
        ns = _namespace()
        model = ns["model"]
        braces = [e for e in model.elements if e.section == "RackBraceIPE"]

        # Two end bays, two frame lines, two panels each, four legs per panel:
        # the X is split at its crossing so the two diagonals share a node
        # instead of passing through each other.
        self.assertEqual(len(braces), 32)
        for brace in braces:
            self.assertEqual(brace.type, "beam")

        for bay, across, panel in ((0, 0.0, 0), (3, 2.4, 1)):
            legs = [
                e
                for e in braces
                if e.id.startswith(f"brace_{bay}_{int(across)}_{panel}_")
            ]
            self.assertEqual(len(legs), 4)
            # All four frame into one shared node, which is the gusseted crossing,
            # and each starts at a different corner of the panel.
            shared = {leg.n2 for leg in legs}
            self.assertEqual(len(shared), 1)
            crossing = shared.pop()
            corners = {leg.n1 for leg in legs}
            self.assertEqual(len(corners), 4)
            self.assertNotIn(crossing, corners)
            centre = model.nodes[crossing].coords
            self.assertAlmostEqual(centre[1], across)
            for corner in corners:
                self.assertNotEqual(corner, shared)

    def test_braces_frame_into_existing_nodes_and_clear_everything(self):
        from tuba.clash import ClashEngine

        model = _namespace()["model"]
        engine = ClashEngine()

        # Braces resolved their endpoints against the row's nodes, so they frame
        # into the columns and beams instead of duplicating them.
        self.assertEqual(engine.check_duplicate_nodes(model), [])
        self.assertEqual(engine.check_self(model), [])

    def test_bracing_reports_a_missing_corner_by_coordinate(self):
        ns = _namespace()
        model = _bare()
        model.add_node([0.0, 0.0, 0.0])

        with self.assertRaisesRegex(ValueError, "No rack frame node at"):
            ns["braced_end_bays"](
                model, bays=1, bay_length=6.0, rack_width=2.4,
                levels=(0.0, 3.0, 5.5), braced_bays=(0,),
            )


class ThermalSplitGrowth(unittest.TestCase):
    def test_rack_steel_is_the_case_temperature_and_the_line_overrides_it(self):
        ns = _namespace()
        model = ns["model"]
        operation = model.operations["Operating"]

        self.assertEqual(operation.temperature, 120.0)
        self.assertEqual(operation.ref_temperature, 20.0)
        hot = [f for f in operation.fields if f.quantity == "temperature"]
        self.assertEqual(len(hot), 1)
        self.assertEqual(hot[0].value, 400.0)
        self.assertEqual(hot[0].route_id, "P-100")
        covered = {element.id for element in model.resolve_operation_field_elements(hot[0])}
        route = {e.id for e in model.elements if e.route_id == "P-100"}
        self.assertEqual(covered, route)

    def test_tributary_lengths_partition_the_whole_route(self):
        ns = _namespace()
        model = ns["model"]
        tributary = ns["route_tributary_lengths"](model, "P-100")
        stations = ns["station_nodes"]
        route = [e for e in model.elements if e.route_id == "P-100"]

        # 30 m in spans of 1, 2, 6, 6, 6, 6, 1, 2 between two approach ends, two
        # approach guides and the five stations.
        self.assertEqual(len(tributary), 9)
        self.assertAlmostEqual(sum(tributary.values()), 30.0, places=9)
        self.assertAlmostEqual(tributary[route[0].n1], 0.5, places=9)
        self.assertAlmostEqual(tributary[route[-1].n2], 1.0, places=9)
        # Station 0 sits between a 2 m approach and a 6 m bay; the anchor station
        # and station 1 sit between two 6 m bays.
        self.assertAlmostEqual(tributary[stations[0]], 4.0, places=9)
        for node in stations[1:4]:
            self.assertAlmostEqual(tributary[node], 6.0, places=9)
        # Station 4 sits between a 6 m bay and a 1 m approach.
        self.assertAlmostEqual(tributary[stations[4]], 3.5, places=9)

    def test_line_weight_is_point_loads_and_never_a_distributed_line_load(self):
        # Code_Aster refuses CALC_CHAMP/FORCE='REAC_NODA' for a beam modelisation
        # carrying more than one distributed load, so the insulation weight must
        # stay as nodal forces alongside gravity. A FORCE_POUTRE or wind field
        # here is a regression, not a simplification: wind compiles to
        # FORCE_POUTRE/TYPE_CHARGE='VENT' and fails the same way.
        ns = _namespace()
        operation = ns["model"].operations["Operating"]

        self.assertEqual({field.quantity for field in operation.fields}, {"temperature"})
        self.assertTrue(operation.nodal_forces)
        total = sum(force.components[2] for force in operation.nodal_forces)
        self.assertAlmostEqual(total, -450.0 * 30.0, places=6)

    def test_line_weight_rejects_a_zero_direction(self):
        ns = _namespace()
        operation = ns["model"].define_operation("Cold", temperature=20.0, ref_temperature=20.0)

        with self.assertRaisesRegex(ValueError, "non-zero direction"):
            ns["add_uniform_line_weight"](ns["model"], operation, "P-100", 450.0, direction=[0.0, 0.0, 0.0])

    def test_tributary_lengths_refuse_a_route_with_a_bend(self):
        ns = _namespace()
        model = _bare()
        model.add_node([0.0, 0.0, 0.0])
        bend = model.add_node([1.0, 0.0, 0.0])
        model.add_element(
            id="p1", type="pipe_straight", n1="N0", n2=bend, section="DN250", material="Steel",
            route_id="P-100",
        )
        model.add_element(
            id="p2", type="pipe_bend", n1=bend, n2="N0", section="DN250", material="Steel",
            route_id="P-100",
        )

        with self.assertRaisesRegex(ValueError, "straight route"):
            ns["route_tributary_lengths"](model, "P-100")

    def test_tributary_lengths_refuse_an_empty_route(self):
        ns = _namespace()

        with self.assertRaisesRegex(ValueError, "no elements"):
            ns["route_tributary_lengths"](_bare(), "P-100")


class ThermalSplitGuards(unittest.TestCase):
    def test_unit_rejects_impossible_arguments(self):
        build = _namespace()["shoed_line_on_rack"]

        with self.assertRaisesRegex(ValueError, "at least one bay"):
            build(_bare(), bays=0)
        with self.assertRaisesRegex(ValueError, "anchor_station"):
            build(_bare(), anchor_station=9)
        with self.assertRaisesRegex(ValueError, "direction"):
            build(_bare(), direction="Z")

    def test_bracing_rejects_a_bay_outside_the_row(self):
        ns = _namespace()
        model = _bare()
        model.add_node([0.0, 0.0, 0.0])

        with self.assertRaisesRegex(ValueError, "outside 0..3"):
            ns["braced_end_bays"](model, bays=4, braced_bays=(7,))


def _bare() -> Model:
    model = Model("Bare", standard="ASME B31.3")
    model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0, alpha=1.2e-5)
    model.add_ibeam_section("RackColumnIPE", "IPE400")
    model.add_ibeam_section("RackLongIPE", "IPE300")
    model.add_ibeam_section("RackCrossIPE", "IPE200")
    model.add_ibeam_section("RackBraceIPE", "IPE160")
    model.add_pipe_section("DN250", OD=0.2731, WT=0.0071)
    return model


if __name__ == "__main__":
    unittest.main()
