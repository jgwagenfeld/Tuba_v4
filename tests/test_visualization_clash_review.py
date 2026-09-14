import unittest

from tests.operating_state_fixtures import straight_pipe_hot_clash_fixture
from tuba.analysis import AnalysisStudy
from tuba.analysis.results import result_state_from_fea_results
from tuba.analysis.states import create_cold_geometry_state, create_operating_geometry_state
from tuba.clash import ClashEngine
from tuba.visualization import build_visualization_scene


class TestVisualizationClashReview(unittest.TestCase):
    def test_operating_clash_issue_overlay_exposes_review_fields(self):
        fixture = straight_pipe_hot_clash_fixture()
        study = AnalysisStudy(
            id="analysis_study:Hot",
            model_revision=0,
            solver_name=fixture.results.solver_name,
            load_case="Hot",
            work_dir=None,
            input_files={},
            mesh_id="analysis_mesh:Hot",
        )
        result_state = result_state_from_fea_results(model=fixture.model, study=study, results=fixture.results)
        operating_state = create_operating_geometry_state(model=fixture.model, result_state=result_state)
        clashes = ClashEngine().check_operating_state(
            fixture.model,
            cold_state=create_cold_geometry_state(fixture.model),
            operating_state=operating_state,
            result_state=result_state,
            envelope_type="bare",
        )

        scene = build_visualization_scene(
            fixture.model,
            result_states=[result_state],
            geometry_states=[operating_state],
            operating_clash_results=clashes,
            scene_id="scene:operating_clash_review",
        )
        scene.validate()

        clash = clashes[0]
        issue = scene.issues[0]
        overlay = next(overlay for overlay in scene.overlays if overlay.kind == "clash")
        marker = next(obj for obj in scene.objects if obj.kind == "clash_marker")
        view = scene.views[0]

        self.assertEqual(issue.id, "issue:clash:element:pipe_0:obstacle:hot_clash_box")
        self.assertEqual(marker.metadata["review"]["load_case"], "Hot")
        self.assertEqual(marker.metadata["review"]["geometry_state"], operating_state.id)
        self.assertEqual(marker.metadata["review"]["result_state_id"], result_state.id)
        self.assertTrue(marker.metadata["review"]["introduced_by_deformation"])
        self.assertEqual(overlay.data["cold_distance_m"], clash.metadata["cold_distance_m"])
        self.assertEqual(overlay.data["operating_distance_m"], clash.metadata["operating_distance_m"])
        self.assertEqual(overlay.data["load_case"], "Hot")
        self.assertEqual(overlay.data["geometry_state"], operating_state.id)
        self.assertEqual(overlay.data["result_state_id"], result_state.id)
        self.assertEqual(overlay.data["envelope_type"], "bare")
        self.assertTrue(overlay.data["introduced_by_deformation"])
        self.assertEqual(overlay.data["object_pair"], ["element:pipe_0", "obstacle:hot_clash_box"])
        self.assertEqual(overlay.data["grouping"]["severity"], "operating_only_hard")
        self.assertEqual(overlay.data["grouping"]["load_case"], "Hot")
        self.assertEqual(issue.external_refs["clash_review"]["focus_object_ids"], view.selected_object_ids)
        self.assertEqual(issue.external_refs["clash_review"]["grouping"], overlay.data["grouping"])


if __name__ == "__main__":
    unittest.main()
