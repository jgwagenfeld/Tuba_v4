import unittest

from tuba import Model
from tuba.clash import ClashEngine
from tuba.visualization import build_visualization_scene


class TestVisualizationIssues(unittest.TestCase):
    def _model_and_clash(self):
        model = Model(project_name="ClashReview")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([2.0, 0.0, 0.0])
        elem = model.add_element(
            id="pipe_0",
            type="pipe_straight",
            n1=n0,
            n2=n1,
            section="PipeSec",
            material="Steel",
        )
        model.add_obstacle(
            id="tray_0",
            type="cuboid",
            min_point=[0.5, 0.11, -0.10],
            max_point=[1.5, 0.20, 0.10],
        )
        model.add_insulation_spec("mw_80", material="mineral_wool", thickness_m=0.08)
        model.assign_insulation(f"element:{elem.id}", "mw_80")
        clash = ClashEngine().check_model(model)[0]
        return model, clash

    def test_build_scene_adds_clash_issue_marker_overlay_and_view(self):
        model, clash = self._model_and_clash()

        scene = build_visualization_scene(model, clash_results=[clash], scene_id="scene_clash_review")
        scene.validate()

        self.assertEqual(len(scene.issues), 1)
        issue = scene.issues[0]
        self.assertEqual(issue.id, "issue:clash:element:pipe_0:obstacle:tray_0")
        self.assertEqual(issue.type, "clash")
        self.assertEqual(issue.severity, "error")
        self.assertEqual(issue.status, "open")
        self.assertEqual([str(ref) for ref in issue.entity_refs], ["element:pipe_0", "obstacle:tray_0"])

        marker = next(obj for obj in scene.objects if obj.kind == "clash_marker")
        self.assertEqual(marker.id, "object:issue:clash:element:pipe_0:obstacle:tray_0")
        self.assertEqual(marker.metadata["issue_id"], issue.id)
        self.assertEqual(marker.metadata["envelope_source"]["type"], "insulation")
        self.assertEqual(marker.metadata["envelope_source"]["insulation_id"], "mw_80")

        overlay = next(overlay for overlay in scene.overlays if overlay.kind == "clash")
        self.assertEqual(overlay.data["issue_ids"], [issue.id])
        self.assertIn(marker.id, overlay.object_ids)

        view = scene.views[0]
        self.assertEqual(view.issue_id, issue.id)
        self.assertEqual(
            set(view.selected_object_ids),
            {"object:element:pipe_0", "object:obstacle:tray_0", marker.id},
        )
        self.assertEqual(view.active_overlay_ids, [overlay.id])

    def test_clash_issue_carries_bcf_compatible_fields_and_raw_payload(self):
        model, clash = self._model_and_clash()

        scene = build_visualization_scene(model, clash_results=[clash], scene_id="scene_clash_review")
        issue = scene.issues[0]

        self.assertEqual(issue.external_refs["bcf"]["topic_type"], "Clash")
        self.assertEqual(issue.external_refs["bcf"]["topic_status"], "Open")
        self.assertEqual(issue.external_refs["bcf"]["related_entity_refs"], ["element:pipe_0", "obstacle:tray_0"])
        self.assertEqual(issue.external_refs["clash"]["left"], {"kind": "element", "id": "pipe_0"})
        self.assertGreater(issue.external_refs["clash"]["penetration_m"], 0.0)


if __name__ == "__main__":
    unittest.main()
