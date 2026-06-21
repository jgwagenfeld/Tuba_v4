import zipfile
import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from tuba import Model
from tests.operating_state_fixtures import straight_pipe_hot_clash_fixture
from tuba.analysis import AnalysisStudy
from tuba.analysis.results import result_state_from_fea_results
from tuba.analysis.states import create_cold_geometry_state, create_operating_geometry_state
from tuba.clash import TrimeshClashEngine
from tuba.visualization import build_visualization_scene
from tuba.visualization.bcf import export_bcf_topics, import_bcf_topics


class TestVisualizationBcf(unittest.TestCase):
    def _scene_with_issue(self):
        model = Model(project_name="BcfReview")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([2.0, 0.0, 0.0])
        model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")
        model.add_obstacle("box", "cuboid", min_point=[1.0, -0.1, -0.1], max_point=[2.0, 0.1, 0.1])
        clashes = TrimeshClashEngine().check_model(model)
        return build_visualization_scene(model, clash_results=clashes, scene_id="scene_bcf")

    def test_export_bcf_topics_writes_markup_and_viewpoint_payloads(self):
        scene = self._scene_with_issue()

        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "issues.bcfzip"
            export_bcf_topics(scene, path)

            with zipfile.ZipFile(path) as archive:
                names = set(archive.namelist())
                self.assertIn("bcf.version", names)
                topic_dir = next(name.split("/", 1)[0] for name in names if name.endswith("/markup.bcf"))
                self.assertIn(f"{topic_dir}/viewpoint.json", names)
                markup = archive.read(f"{topic_dir}/markup.bcf").decode("utf-8")
                self.assertIn("element:pipe_0", markup)
                self.assertIn("obstacle:box", markup)

    def test_import_bcf_topics_returns_scene_issues_with_external_refs(self):
        scene = self._scene_with_issue()

        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "issues.bcfzip"
            export_bcf_topics(scene, path)

            issues = import_bcf_topics(path)

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].type, "clash")
        self.assertEqual(issues[0].status, "open")
        self.assertEqual([str(ref) for ref in issues[0].entity_refs], ["element:pipe_0", "obstacle:box"])
        self.assertEqual(issues[0].external_refs["bcf"]["topic_status"], "Open")

    def test_operating_clash_bcf_exports_load_case_and_geometry_state_metadata(self):
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
        clashes = TrimeshClashEngine().check_operating_state(
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
            scene_id="scene_bcf_operating",
        )

        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "operating.bcfzip"
            export_bcf_topics(scene, path)
            with zipfile.ZipFile(path) as archive:
                topic_dir = next(name.split("/", 1)[0] for name in archive.namelist() if name.endswith("/markup.bcf"))
                markup = archive.read(f"{topic_dir}/markup.bcf").decode("utf-8")
                viewpoint = json.loads(archive.read(f"{topic_dir}/viewpoint.json").decode("utf-8"))

        self.assertIn("Hot", markup)
        self.assertIn(operating_state.id, markup)
        self.assertEqual(viewpoint["clash_metadata"]["load_case"], "Hot")
        self.assertEqual(viewpoint["clash_metadata"]["geometry_state"], operating_state.id)


if __name__ == "__main__":
    unittest.main()
