import unittest

from tuba import Model
from tuba.rules import RuleEngine, SupportSpacingRule
from tuba.visualization import build_visualization_scene


class TestVisualizationRules(unittest.TestCase):
    def _model_and_rule_result(self):
        model = Model(project_name="RuleReview")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([4.0, 0.0, 0.0])
        model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")
        report = RuleEngine([SupportSpacingRule(max_span_m=2.5)]).evaluate(model)
        return model, report.results[0]

    def test_build_scene_adds_rule_issue_marker_overlay_and_view(self):
        model, result = self._model_and_rule_result()

        scene = build_visualization_scene(model, rule_results=[result], scene_id="scene_rule_review")
        scene.validate()

        issue = next(issue for issue in scene.issues if issue.type == "rule")
        self.assertEqual(issue.id, "issue:rule:support_spacing:element:pipe_0")
        self.assertEqual(issue.severity, "warning")
        self.assertEqual(issue.status, "open")
        self.assertEqual([str(ref) for ref in issue.entity_refs], ["element:pipe_0"])

        marker = next(obj for obj in scene.objects if obj.kind == "rule_marker")
        self.assertEqual(marker.id, "object:issue:rule:support_spacing:element:pipe_0")
        self.assertEqual(marker.metadata["rule_id"], "support_spacing")
        self.assertEqual(marker.metadata["rule_data"]["max_span_m"], 2.5)

        overlay = next(overlay for overlay in scene.overlays if overlay.kind == "rule_violation")
        self.assertEqual(overlay.data["issue_ids"], [issue.id])
        self.assertIn(marker.id, overlay.object_ids)

        view = next(view for view in scene.views if view.issue_id == issue.id)
        self.assertEqual(
            set(view.selected_object_ids),
            {"object:element:pipe_0", marker.id},
        )
        self.assertEqual(view.active_overlay_ids, [overlay.id])

    def test_rule_issue_carries_rule_report_payload_for_details_panel(self):
        model, result = self._model_and_rule_result()

        scene = build_visualization_scene(model, rule_results=[result], scene_id="scene_rule_review")
        issue = next(issue for issue in scene.issues if issue.type == "rule")

        self.assertEqual(issue.external_refs["rule"]["rule_id"], "support_spacing")
        self.assertFalse(issue.external_refs["rule"]["passed"])
        self.assertEqual(issue.external_refs["rule"]["refs"], [{"kind": "element", "id": "pipe_0"}])
        self.assertEqual(issue.external_refs["rule"]["data"]["span_m"], 4.0)


if __name__ == "__main__":
    unittest.main()
