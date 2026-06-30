import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

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

    def test_export_analysis_study_shortens_long_solver_group_names(self):
        model = Model(project_name="LongNames")
        model.add_material("Steel", E=2.0e11, nu=0.3, alpha=1.2e-5)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 0.0, 0.0])
        long_id = "pipe_segment_with_a_name_that_exceeds_code_aster_limit"
        model.add_element(id=long_id, type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")
        model.define_load_case("Hot", gravity=True)

        with TemporaryDirectory() as tmpdir:
            study = CodeAsterSolver(work_dir=tmpdir).export_analysis_study(model, "Hot", tmpdir)
            root = Path(study.work_dir)
            mail = (root / "study.mail").read_text(encoding="utf-8")
            comm = (root / "study.comm").read_text(encoding="utf-8")
            sidecar = json.loads((root / "study_tuba_fem.json").read_text(encoding="utf-8"))

        short_name = sidecar["name_map"][long_id]
        self.assertLessEqual(len(short_name), 24)
        self.assertIn(short_name, mail)
        self.assertNotIn(long_id, mail)
        self.assertNotIn(long_id, comm)

    def test_solver_execute_delegates_to_code_aster_runtime(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "study.export").write_text("", encoding="utf-8")
            captured = {}

            def fake_run_code_aster_export(export_file, work_dir, config):
                captured["export_file"] = export_file
                captured["work_dir"] = work_dir
                captured["config"] = config
                return object()

            with patch("tuba.solver.aster.run_code_aster_export", fake_run_code_aster_export):
                CodeAsterSolver(
                    work_dir=tmpdir,
                    exec_method="python_bridge",
                    bridge_python="/opt/aster/bin/python",
                )._execute(root)

        self.assertEqual(captured["export_file"], root / "study.export")
        self.assertEqual(captured["work_dir"], root)
        self.assertEqual(captured["config"].exec_method, "python_bridge")
        self.assertEqual(captured["config"].bridge_python, "/opt/aster/bin/python")

    def test_solver_preserves_runner_command_compatibility(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "study.export").write_text("", encoding="utf-8")
            captured = {}

            def fake_run_code_aster_export(export_file, work_dir, config):
                captured["config"] = config
                return object()

            with patch("tuba.solver.aster.run_code_aster_export", fake_run_code_aster_export):
                CodeAsterSolver(
                    work_dir=tmpdir,
                    exec_method="command",
                    runner_command="conda run -n aster run_aster",
                )._execute(root)

        self.assertEqual(captured["config"].exec_method, "command")
        self.assertEqual(captured["config"].runner_command, "conda run -n aster run_aster")

    def test_solver_reads_code_aster_environment_defaults(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "study.export").write_text("", encoding="utf-8")
            captured = {}

            def fake_run_code_aster_export(export_file, work_dir, config):
                captured["config"] = config
                return object()

            env = {
                "TUBA_CODE_ASTER_EXEC_METHOD": "wsl",
                "TUBA_CODE_ASTER_WSL_DISTRO": "Ubuntu",
            }
            with patch.dict(os.environ, env, clear=False):
                with patch("tuba.solver.aster.run_code_aster_export", fake_run_code_aster_export):
                    CodeAsterSolver(work_dir=tmpdir)._execute(root)

        self.assertEqual(captured["config"].exec_method, "wsl")
        self.assertEqual(captured["config"].wsl_distro, "Ubuntu")


if __name__ == "__main__":
    unittest.main()
