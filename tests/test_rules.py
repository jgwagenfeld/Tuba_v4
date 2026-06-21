import unittest

from tuba import Model
from tuba.rules import ClashFreeRule, RuleEngine, SupportSpacingRule, rule_report_to_markdown


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

    def test_clash_free_rule_reports_structured_clash(self):
        model = self._model()
        model.add_obstacle("box", "cuboid", min_point=[1.0, -0.1, -0.1], max_point=[2.0, 0.1, 0.1])

        report = RuleEngine([ClashFreeRule()]).evaluate(model)

        self.assertFalse(report.passed)
        self.assertEqual(report.results[0].rule_id, "clash_free")
        self.assertEqual(str(report.results[0].refs[0]), "element:pipe_0")
        self.assertEqual(str(report.results[0].refs[1]), "obstacle:box")

    def test_rule_report_serializes_to_dict_and_markdown(self):
        model = self._model()
        report = RuleEngine([SupportSpacingRule(max_span_m=2.5)]).evaluate(model)

        data = report.to_dict()
        markdown = rule_report_to_markdown(report)

        self.assertEqual(data["passed"], False)
        self.assertEqual(data["results"][0]["rule_id"], "support_spacing")
        self.assertIn("support_spacing", markdown)


if __name__ == "__main__":
    unittest.main()
