import unittest

from tuba import Model
from tuba.clash import ClashEngine
from tuba.rules import ClashFreeRule, RuleEngine


def _base():
    model = Model(project_name="SelfClash")
    model.add_material("Steel", E=2.0e11, nu=0.3)
    model.add_rectangular_section("RS", height_y=0.1, height_z=0.1)
    return model


class TestSelfClash(unittest.TestCase):
    def test_crossing_without_connection_is_clash(self):
        model = _base()
        a0 = model.add_node([0.0, 0.0, 0.0])
        a1 = model.add_node([2.0, 0.0, 0.0])
        b0 = model.add_node([1.0, -1.0, 0.0])
        b1 = model.add_node([1.0, 1.0, 0.0])
        model.add_element(id="a", type="beam", n1=a0, n2=a1, section="RS", material="Steel")
        model.add_element(id="b", type="beam", n1=b0, n2=b1, section="RS", material="Steel")

        clashes = ClashEngine().check_self(model)

        self.assertEqual(len(clashes), 1)
        clash = clashes[0]
        self.assertEqual(str(clash.left), "element:a")
        self.assertEqual(str(clash.right), "element:b")
        self.assertEqual(clash.severity, "hard")
        self.assertEqual(clash.metadata["overlap_type"], "crossing")
        self.assertEqual(clash.metadata["reason"], "no_topological_connection")
        self.assertIsNotNone(clash.location)

    def _short_tee(self):
        """60 mm tee arms on a 100 mm pipe with 1D runs welded to their ends."""
        model = Model(project_name="ShortTee")
        model.add_material("Steel", E=2.1e11, nu=0.3)
        model.add_pipe_section("P", OD=0.1, WT=0.01)
        hub = model.add_node([0.0, 0.0, 0.0])
        for name, (x, y) in (("left", (-1.0, 0.0)), ("right", (1.0, 0.0)), ("branch", (0.0, 1.0))):
            stub = model.add_node([0.06 * x, 0.06 * y, 0.0])
            end = model.add_node([0.2 * x, 0.2 * y, 0.0])
            model.add_element(id=f"arm_{name}", type="pipe_straight", n1=hub, n2=stub, section="P", material="Steel")
            model.add_element(id=f"line_{name}", type="pipe_straight", n1=stub, n2=end, section="P", material="Steel")
        return model

    def test_short_tee_arms_do_not_clash_through_rounded_ends(self):
        # The runs welded to one arm sit within one diameter of the other arms,
        # so capsule end caps overlap although the flat-ended pipes are apart
        # (pipe-tee-volume-review).
        self.assertEqual(ClashEngine().check_self(self._short_tee()), [])

    def test_tee_runs_inside_clearance_report_the_flat_end_gap(self):
        model = self._short_tee()

        clashes = {(c.left.id, c.right.id): c for c in ClashEngine().check_self(model, clearance_m=0.05)}

        clash = clashes[("arm_left", "line_branch")]
        self.assertEqual(clash.severity, "clearance")
        self.assertAlmostEqual(clash.metadata["surface_gap_m"], 0.01)
        self.assertAlmostEqual(clash.penetration_m, 0.04)

    def test_square_beam_corners_are_not_excused_by_flat_ends(self):
        # The section's collision radius is half its side, not half its diagonal,
        # so a 45-degree twisted corner reaches past that cylinder.
        model = _base()
        a0, a1 = model.add_node([-1.0, 0.0, 0.0]), model.add_node([0.0, 0.0, 0.0])
        b0, b1 = model.add_node([0.06, -0.5, 0.0]), model.add_node([0.06, 0.5, 0.0])
        model.add_element(id="a", type="beam", n1=a0, n2=a1, section="RS", material="Steel")
        model.add_element(id="b", type="beam", n1=b0, n2=b1, section="RS", material="Steel", twist_angle=45)

        self.assertEqual([c.severity for c in ClashEngine().check_self(model)], ["hard"])

    def test_flat_ended_pipes_that_really_overlap_still_clash(self):
        model = Model(project_name="FlatEnds")
        model.add_material("Steel", E=2.1e11, nu=0.3)
        model.add_pipe_section("P", OD=0.1, WT=0.01)
        a0, a1 = model.add_node([-0.2, 0.0, 0.0]), model.add_node([-0.03, 0.0, 0.0])
        b0, b1 = model.add_node([0.0, 0.03, 0.0]), model.add_node([0.0, 0.2, 0.0])
        model.add_element(id="a", type="pipe_straight", n1=a0, n2=a1, section="P", material="Steel")
        model.add_element(id="b", type="pipe_straight", n1=b0, n2=b1, section="P", material="Steel")

        clashes = ClashEngine().check_self(model)

        self.assertEqual([(str(c.left), str(c.right), c.severity) for c in clashes],
                         [("element:a", "element:b", "hard")])

    def test_shared_node_is_intended_join(self):
        model = _base()
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([2.0, 0.0, 0.0])
        n2 = model.add_node([2.0, 2.0, 0.0])
        model.add_element(id="a", type="beam", n1=n0, n2=n1, section="RS", material="Steel")
        model.add_element(id="b", type="beam", n1=n1, n2=n2, section="RS", material="Steel")

        self.assertEqual(ClashEngine().check_self(model), [])

    def test_duplicate_element_is_reported(self):
        model = _base()
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([2.0, 0.0, 0.0])
        model.add_element(id="a", type="beam", n1=n0, n2=n1, section="RS", material="Steel")
        model.add_element(id="b", type="beam", n1=n0, n2=n1, section="RS", material="Steel")

        clashes = ClashEngine().check_self(model)

        self.assertEqual(len(clashes), 1)
        self.assertEqual(clashes[0].metadata["overlap_type"], "duplicate_element")

    def test_colinear_overlap_needs_corner_detail(self):
        model = _base()
        a0 = model.add_node([0.0, 0.0, 0.0])
        a1 = model.add_node([2.0, 0.0, 0.0])
        b0 = model.add_node([1.0, 0.02, 0.0])
        b1 = model.add_node([3.0, 0.02, 0.0])
        model.add_element(id="a", type="beam", n1=a0, n2=a1, section="RS", material="Steel")
        model.add_element(id="b", type="beam", n1=b0, n2=b1, section="RS", material="Steel")

        clashes = ClashEngine().check_self(model)

        self.assertEqual(len(clashes), 1)
        self.assertEqual(clashes[0].metadata["overlap_type"], "colinear_overlap")
        self.assertIn("corner", clashes[0].diagnostics[0])

    def test_support_link_excuses_shoe_contact(self):
        model = _base()
        p0 = model.add_node([0.0, 0.0, 0.0])
        p1 = model.add_node([2.0, 0.0, 0.0])
        s0 = model.add_node([0.0, 0.02, 0.0])
        s1 = model.add_node([2.0, 0.02, 0.0])
        model.add_element(id="pipe", type="beam", n1=p0, n2=p1, section="RS", material="Steel")
        model.add_element(id="steel", type="beam", n1=s0, n2=s1, section="RS", material="Steel")

        self.assertEqual(len(ClashEngine().check_self(model)), 1)

        model.add_support(node=p0, type="rest", attached_to=s0)
        model.add_support(node=p1, type="rest", attached_to=s1)

        self.assertEqual(ClashEngine().check_self(model), [])

    def test_duplicate_nodes_flag_merge_not_clash(self):
        model = _base()
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([0.0005, 0.0, 0.0])

        duplicates = ClashEngine().check_duplicate_nodes(model)

        self.assertEqual(len(duplicates), 1)
        pair = {duplicates[0].left.id, duplicates[0].right.id}
        self.assertEqual(pair, {n0, n1})
        self.assertIn("merge", duplicates[0].diagnostics[0])

    def test_coincident_reference_is_not_a_duplicate_physical_joint(self):
        model = _base()
        first = model.add_node([0, 0, 0])
        model.add_reference_point("attachment", position=[0, 0, 0])
        self.assertEqual(ClashEngine().check_duplicate_nodes(model), [])
        second = model.add_node([0, 0, 0])
        duplicates = ClashEngine().check_duplicate_nodes(model)
        self.assertEqual(len(duplicates), 1)
        self.assertEqual({duplicates[0].left.id, duplicates[0].right.id}, {first, second})

    def test_endpoint_nearmiss_defers_to_duplicate_check(self):
        model = _base()
        a0 = model.add_node([0.0, 0.0, 0.0])
        a1 = model.add_node([2.0, 0.0, 0.0])
        b0 = model.add_node([2.0005, 0.0, 0.0])
        b1 = model.add_node([4.0, 0.0, 0.0])
        model.add_element(id="a", type="beam", n1=a0, n2=a1, section="RS", material="Steel")
        model.add_element(id="b", type="beam", n1=b0, n2=b1, section="RS", material="Steel")

        self.assertEqual(ClashEngine().check_self(model), [])
        self.assertEqual(len(ClashEngine().check_duplicate_nodes(model)), 1)

    def test_clash_free_rule_covers_self(self):
        model = _base()
        a0 = model.add_node([0.0, 0.0, 0.0])
        a1 = model.add_node([2.0, 0.0, 0.0])
        b0 = model.add_node([1.0, -1.0, 0.0])
        b1 = model.add_node([1.0, 1.0, 0.0])
        model.add_element(id="a", type="beam", n1=a0, n2=a1, section="RS", material="Steel")
        model.add_element(id="b", type="beam", n1=b0, n2=b1, section="RS", material="Steel")

        report = RuleEngine([ClashFreeRule()]).evaluate(model)

        self.assertFalse(report.passed)
        self.assertTrue(any("no shared node" in result.message for result in report.results))


if __name__ == "__main__":
    unittest.main()
