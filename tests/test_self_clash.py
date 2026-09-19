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
