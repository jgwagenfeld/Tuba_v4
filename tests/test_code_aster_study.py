import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tuba import Model
from tuba.analysis import AnalysisMesh, AnalysisStudy
from tuba.routing.adapter import apply_candidate_to_model
from tuba.routing.postprocess import build_segments
from tuba.routing.types import PipeRouteCandidate, PipeRouteRequest, RouteEndpoint, RoutingConstraints
from tuba.solver.aster import CodeAsterSolver


class TestCodeAsterStudyManifest(unittest.TestCase):
    def _model_with_bend_and_structure(self):
        model = Model(project_name="AsterStudy")
        model.add_material("Steel", E=2.0e11, nu=0.3, alpha=1.2e-5)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        model.add_rectangular_section("RackSec", height_y=0.1, height_z=0.1, thickness_y=0.01, thickness_z=0.01)
        request = PipeRouteRequest(
            id="P-100",
            start=RouteEndpoint(id="A", point=(0.0, 0.0, 0.0)),
            goal=RouteEndpoint(id="B", point=(2.0, 2.0, 0.0)),
            section="PipeSec",
            material="Steel",
            constraints=RoutingConstraints(min_bend_radius=0.5),
        )
        points = [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (2.0, 2.0, 0.0)]
        apply_candidate_to_model(
            model,
            PipeRouteCandidate(
                request_id="P-100",
                points=points,
                segments=build_segments(points, request.constraints),
                cost=4.0,
                cost_breakdown={"length": 4.0, "bends": 1},
            ),
            request,
        )
        beam_n0 = model.add_node([0.0, 0.5, -0.5])
        beam_n1 = model.add_node([2.0, 0.5, -0.5])
        model.add_element(id="rack_beam_0", type="beam", n1=beam_n0, n2=beam_n1, section="RackSec", material="Steel")
        model.define_load_case("Hot", gravity=True, pressure=1.0e6, temperature=120.0, ref_temperature=20.0)
        return model

    def test_export_analysis_study_writes_manifest_with_mesh_provenance(self):
        model = self._model_with_bend_and_structure()
        bend = next(element for element in model.elements if element.type == "pipe_bend")

        with TemporaryDirectory() as tmpdir:
            study = CodeAsterSolver(work_dir=tmpdir).export_analysis_study(model, "Hot", tmpdir)
            manifest = json.loads((Path(study.work_dir) / "study_manifest.json").read_text(encoding="utf-8"))

        loaded_study = AnalysisStudy.from_dict(manifest["study"])
        mesh = AnalysisMesh.from_dict(manifest["analysis_mesh"])

        self.assertEqual(loaded_study.id, study.id)
        self.assertEqual(loaded_study.mesh_id, mesh.id)
        self.assertIn("study.mail", loaded_study.input_files["mail"])
        self.assertIn("sidecar", loaded_study.input_files)
        sidecar_path = Path(loaded_study.input_files["sidecar"])
        self.assertTrue(sidecar_path.name.endswith("study_tuba_fem.json"))
        self.assertIn(f"{bend.id}_n1", mesh.nodes)
        self.assertEqual(mesh.node_sources[f"{bend.id}_n1"].role, "generated_bend_node")
        self.assertEqual(str(mesh.node_sources[f"{bend.id}_n1"].source_ref), f"element:{bend.id}")
        self.assertEqual(mesh.element_sources[f"{bend.id}_s0"].role, "bend_segment")
        self.assertEqual(str(mesh.element_sources["rack_beam_0"].source_ref), "element:rack_beam_0")
        self.assertIn("PipeElbows", mesh.groups)

    def test_export_study_keeps_returning_output_directory(self):
        model = self._model_with_bend_and_structure()

        with TemporaryDirectory() as tmpdir:
            out_dir = CodeAsterSolver(work_dir=tmpdir).export_study(model, "Hot", tmpdir)

        self.assertEqual(str(out_dir), tmpdir)


if __name__ == "__main__":
    unittest.main()
