import unittest

from tuba import Model
from tuba.rules import ClashFreeRule, RuleEngine, SupportSpacingRule


class TestRules(unittest.TestCase):
    def _model(self):
        model = Model(project_name="Rules")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([4.0, 0.0, 0.0])
        model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")
        return model

    def test_support_spacing_rule_reports_long_span(self):
        model = self._model()

        report = RuleEngine([SupportSpacingRule(max_span_m=2.5)]).evaluate(model)

        self.assertFalse(report.passed)
        self.assertEqual(report.results[0].rule_id, "support_spacing")
        self.assertEqual(str(report.results[0].refs[0]), "element:pipe_0")
        self.assertIn("4", report.results[0].message)

    def test_support_spacing_does_not_count_an_unsupported_split_as_a_support(self):
        model = self._model()
        first = model.elements[0]
        end = first.n2
        middle = model.add_node([2.0, 0.0, 0.0])
        first.n2 = middle
        model.add_element(id="pipe_1", type="pipe_straight", n1=middle, n2=end,
                          section="PipeSec", material="Steel")
        model.add_support(first.n1, "rest")
        model.add_support(end, "rest")
        rule = SupportSpacingRule(max_span_m=3.5)

        result, = rule.evaluate(model)
        self.assertEqual(result.data, {"span_m": 4.0, "max_span_m": 3.5})
        self.assertEqual([str(ref) for ref in result.refs], ["element:pipe_0", "element:pipe_1"])
        model.add_support(middle, "rest")
        self.assertEqual(rule.evaluate(model), [])

    def test_support_spacing_stops_at_branches_and_terminates_closed_loops(self):
        model = self._model()
        first = model.elements[0]
        end = first.n2
        middle = model.add_node([2.0, 0.0, 0.0])
        first.n2 = middle
        model.add_element(id="pipe_1", type="pipe_straight", n1=middle, n2=end,
                          section="PipeSec", material="Steel")
        branch = model.add_node([2.0, 2.0, 0.0])
        model.add_element(id="pipe_2", type="pipe_straight", n1=middle, n2=branch,
                          section="PipeSec", material="Steel")
        rule = SupportSpacingRule(max_span_m=3.5)
        self.assertEqual(rule.evaluate(model), [])

        # Close a three-edge loop without supports; it must be checked once.
        model.elements[-1].n1 = end
        model.elements[-1].n2 = first.n1
        result, = rule.evaluate(model)
        self.assertEqual(result.data["span_m"], 8.0)
        self.assertEqual([ref.id for ref in result.refs], ["pipe_0", "pipe_1", "pipe_2"])

    def test_clash_free_rule_reports_structured_clash(self):
        model = self._model()
        model.add_obstacle("box", "cuboid", min_point=[1.0, -0.1, -0.1], max_point=[2.0, 0.1, 0.1])

        report = RuleEngine([ClashFreeRule()]).evaluate(model)

        self.assertFalse(report.passed)
        self.assertEqual(report.results[0].rule_id, "clash_free")
        self.assertEqual(str(report.results[0].refs[0]), "element:pipe_0")
        self.assertEqual(str(report.results[0].refs[1]), "obstacle:box")

    def test_rule_report_serializes_to_dict(self):
        model = self._model()
        report = RuleEngine([SupportSpacingRule(max_span_m=2.5)]).evaluate(model)

        data = report.to_dict()

        self.assertEqual(data["passed"], False)
        self.assertEqual(data["results"][0]["rule_id"], "support_spacing")


if __name__ == "__main__":
    unittest.main()
