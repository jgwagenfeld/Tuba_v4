import unittest

from tuba import Model
from tuba.rules import RuleResult, SupportSpacingRule
from tuba.verify import verify_model


class TestVerify(unittest.TestCase):
    def _model(self):
        model = Model(project_name="Verify")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([4.0, 0.0, 0.0])
        model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")
        return model

    def test_clean_model_passes_and_serializes(self):
        report = verify_model(self._model())

        self.assertTrue(report.passed)
        self.assertEqual(report.validation_errors, [])
        self.assertEqual(report.clashes, [])
        self.assertEqual(report.to_dict()["passed"], True)

    def test_validation_error_blocks_and_skips_geometry(self):
        model = self._model()
        model.add_element(id="bad", type="pipe_straight", n1="missing", n2="missing", section="PipeSec", material="Steel")

        report = verify_model(model)

        self.assertFalse(report.passed)
        self.assertTrue(any("missing" in error for error in report.validation_errors))
        self.assertEqual(report.clashes, [])  # geometry checks need valid topology, so they are skipped

    def test_hard_clash_blocks(self):
        model = self._model()
        model.add_obstacle("box", "cuboid", min_point=[1.0, -0.1, -0.1], max_point=[2.0, 0.1, 0.1])

        report = verify_model(model)

        self.assertFalse(report.passed)
        self.assertEqual(len(report.clashes), 1)
        self.assertEqual(report.clashes[0].severity, "hard")

    def test_error_severity_rule_blocks_and_warning_does_not(self):
        class BlockingRule:
            rule_id = "blocking"

            def evaluate(self, model):
                return [RuleResult(rule_id="blocking", passed=False, severity="error", message="nope")]

        blocking = verify_model(self._model(), rules=[BlockingRule()])
        warning = verify_model(self._model(), rules=[SupportSpacingRule(max_span_m=2.5)])

        self.assertFalse(blocking.passed)
        self.assertTrue(warning.passed)  # SupportSpacingRule reports a warning; it never blocks a solve
        self.assertTrue(any("4" in text for text in warning.warnings))

    def test_model_method_delegates(self):
        report = self._model().verify()

        self.assertTrue(report.passed)


if __name__ == "__main__":
    unittest.main()
