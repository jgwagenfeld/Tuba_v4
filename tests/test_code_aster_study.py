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
from tuba.solver.base import FEAResults
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

    def test_bend_gmsh_meshing_is_memoized_within_an_export(self):
        model = self._model_with_bend_and_structure()
        bends = [e for e in model.elements if e.type == "pipe_bend"]
        self.assertTrue(bends)
        solver = CodeAsterSolver()

        first = solver._compute_bend_nodes_gmsh(model, bends, 16)
        second = solver._compute_bend_nodes_gmsh(model, bends, 16)
        self.assertIs(first, second)  # memoized: the OCC bend mesher runs once

        # A fresh export clears the memo (so it never spans models), then the
        # two .mail writes share a single Gmsh run -> exactly one cached entry.
        with TemporaryDirectory() as tmpdir:
            solver.export_analysis_study(model, "Hot", tmpdir)
        self.assertEqual(len(solver._bend_gmsh_cache), 1)

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

    def test_export_analysis_study_uses_code_aster_safe_mesh_labels(self):
        model = self._model_with_bend_and_structure()
        bend = next(element for element in model.elements if element.type == "pipe_bend")

        with TemporaryDirectory() as tmpdir:
            study = CodeAsterSolver(work_dir=tmpdir).export_analysis_study(model, "Hot", tmpdir)
            root = Path(study.work_dir)
            mail = (root / "study.mail").read_text(encoding="utf-8")
            sidecar = json.loads((root / "study_tuba_fem.json").read_text(encoding="utf-8"))
            node_label_map, element_label_map = CodeAsterSolver._read_solver_label_maps(root)

        coor_labels: list[str] = []
        element_labels: list[str] = []
        block: str | None = None
        for raw_line in mail.splitlines():
            line = raw_line.strip()
            if line == "COOR_3D":
                block = "nodes"
                continue
            if line in {"SEG2", "SEG3"}:
                block = "elements"
                continue
            if line == "FINSF":
                block = None
                continue
            if line == "FIN" or line.startswith("GROUP_") or not line:
                block = None if line.startswith("GROUP_") else block
                continue
            if block == "nodes":
                coor_labels.append(line.split()[0])
            elif block == "elements":
                element_labels.append(line.split()[0])

        self.assertEqual(len(coor_labels), len({label[:8] for label in coor_labels}))
        self.assertEqual(len(element_labels), len({label[:8] for label in element_labels}))

        original_bend_node = f"{bend.id}_n1"
        solver_bend_node = sidecar["name_map"][original_bend_node]
        self.assertLessEqual(len(solver_bend_node), 8)
        self.assertIn(solver_bend_node, mail)
        self.assertNotIn(original_bend_node, mail)
        self.assertEqual(node_label_map[solver_bend_node], original_bend_node)

        original_bend_segment = f"{bend.id}_s0"
        solver_bend_segment = sidecar["name_map"][original_bend_segment]
        self.assertLessEqual(len(solver_bend_segment), 8)
        self.assertEqual(element_label_map[solver_bend_segment], original_bend_segment)

    def test_export_analysis_study_writes_supported_bend_cara_syntax(self):
        model = self._model_with_bend_and_structure()

        with TemporaryDirectory() as tmpdir:
            study = CodeAsterSolver(work_dir=tmpdir).export_analysis_study(model, "Hot", tmpdir)
            comm = (Path(study.work_dir) / "study.comm").read_text(encoding="utf-8")

        self.assertIn("SECTION='COUDE'", comm)
        self.assertNotIn("    COUDE=(", comm)
        self.assertNotIn("COUDE=_F", comm)

    def test_export_analysis_study_uses_group_material_assignment_syntax(self):
        model = self._model_with_bend_and_structure()

        with TemporaryDirectory() as tmpdir:
            study = CodeAsterSolver(work_dir=tmpdir).export_analysis_study(model, "Hot", tmpdir)
            comm = (Path(study.work_dir) / "study.comm").read_text(encoding="utf-8")

        self.assertIn("TOUT='OUI',", comm)
        self.assertNotIn("MAILLE=", comm)

    def test_export_analysis_study_writes_individual_groups_for_straight_elements(self):
        model = self._model_with_bend_and_structure()

        with TemporaryDirectory() as tmpdir:
            study = CodeAsterSolver(work_dir=tmpdir).export_analysis_study(model, "Hot", tmpdir)
            root = Path(study.work_dir)
            mail = (root / "study.mail").read_text(encoding="utf-8")
            sidecar = json.loads((root / "study_tuba_fem.json").read_text(encoding="utf-8"))

        solver_beam_name = sidecar["name_map"]["rack_beam_0"]
        self.assertIn(f"GROUP_MA NOM={solver_beam_name}", mail)

    def test_export_analysis_study_uses_single_pipe_orientation_node(self):
        model = self._model_with_bend_and_structure()

        with TemporaryDirectory() as tmpdir:
            study = CodeAsterSolver(work_dir=tmpdir).export_analysis_study(model, "Hot", tmpdir)
            root = Path(study.work_dir)
            mail = (root / "study.mail").read_text(encoding="utf-8")
            sidecar = json.loads((root / "study_tuba_fem.json").read_text(encoding="utf-8"))

        solver_group_name = sidecar["name_map"]["PipeOrientationNodes"]
        group_lines: list[str] = []
        in_group = False
        for raw_line in mail.splitlines():
            line = raw_line.strip()
            if line == f"GROUP_NO NOM={solver_group_name}":
                in_group = True
                continue
            if in_group and line == "FINSF":
                break
            if in_group and line:
                group_lines.append(line)

        self.assertEqual(len(group_lines), 1)

    def test_export_analysis_study_writes_required_unilateral_contact_coefficients(self):
        model = self._model_with_bend_and_structure()
        model.add_support("N1", type="rest")

        with TemporaryDirectory() as tmpdir:
            study = CodeAsterSolver(work_dir=tmpdir).export_analysis_study(model, "Hot", tmpdir)
            comm = (Path(study.work_dir) / "study.comm").read_text(encoding="utf-8")

        self.assertIn("UNIL_ZERO = DEFI_CONSTANTE(VALE=0.0);", comm)
        self.assertIn("UNIL_ONE = DEFI_CONSTANTE(VALE=1.0);", comm)
        self.assertIn("COEF_IMPO=UNIL_ZERO", comm)
        self.assertIn("COEF_MULT=UNIL_ONE", comm)

    def test_uniform_load_writer_preserves_legacy_pressure_and_temperature_syntax(self):
        model = Model(project_name="UniformLoadSyntax")
        model.add_material("Steel", E=2.0e11, nu=0.3, alpha=1.2e-5)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 0.0, 0.0])
        model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")
        model.add_support(n0, type="anchor")
        model.define_load_case("Hot", gravity=True, pressure=1.0e6, temperature=120.0, ref_temperature=20.0)

        with TemporaryDirectory() as tmpdir:
            study = CodeAsterSolver(work_dir=tmpdir).export_analysis_study(model, "Hot", tmpdir)
            comm = (Path(study.work_dir) / "study.comm").read_text(encoding="utf-8")

        self.assertIn("FORCE_TUYAU=_F(", comm)
        self.assertNotIn("FORCE_TUYAU=(", comm)
        self.assertIn("TEMP_FIELD = CREA_CHAMP(", comm)
        self.assertIn("    MAILLAGE=MAIL,\n    AFFE=_F(", comm)
        self.assertIn("CRITERES=('SIEQ_ELGA', 'SIEQ_ELNO'),", comm)
        self.assertIn("NOM_CHAM=('DEPL', 'SIEQ_ELGA', 'SIEQ_ELNO', 'EFGE_ELNO', 'FORC_NODA'),", comm)

    def test_beam_only_study_does_not_emit_pipe_stress_fields(self):
        model = Model(project_name="BeamOnly")
        model.add_material("Steel", E=2.0e11, nu=0.3, alpha=1.2e-5)
        model.add_rectangular_section("RackSec", height_y=0.1, height_z=0.1, thickness_y=0.01, thickness_z=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 0.0, 0.0])
        model.add_element(id="beam_0", type="beam", n1=n0, n2=n1, section="RackSec", material="Steel")
        model.add_support(n0, type="anchor")
        model.define_load_case("Hot", gravity=True)

        with TemporaryDirectory() as tmpdir:
            study = CodeAsterSolver(work_dir=tmpdir).export_analysis_study(model, "Hot", tmpdir)
            comm = (Path(study.work_dir) / "study.comm").read_text(encoding="utf-8")

        self.assertNotIn("SIEQ_ELGA", comm)
        self.assertNotIn("SIEQ_ELNO", comm)
        self.assertNotIn("TAB_SIEQ", comm)

    def test_write_comm_keeps_solver_command_blocks_in_execution_order(self):
        model = Model(project_name="CommOrder")
        model.add_material("Steel", E=2.0e11, nu=0.3, alpha=1.2e-5)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 0.0, 0.0])
        model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")
        model.add_support(n0, type="anchor")
        model.define_load_case("Hot", gravity=True, pressure=1.0e6, temperature=120.0, ref_temperature=20.0)

        with TemporaryDirectory() as tmpdir:
            study = CodeAsterSolver(work_dir=tmpdir).export_analysis_study(model, "Hot", tmpdir)
            comm = (Path(study.work_dir) / "study.comm").read_text(encoding="utf-8")

        tokens = [
            "DEBUT(PAR_LOT='NON');",
            "MAIL0 = LIRE_MAILLAGE",
            "MODELE = AFFE_MODELE",
            "MAT_STEEL = DEFI_MATERIAU",
            "CHMAT = AFFE_MATERIAU",
            "CARA = AFFE_CARA_ELEM",
            "BC_0 = AFFE_CHAR_MECA",
            "GRAVITY = AFFE_CHAR_MECA",
            "PRESSURE = AFFE_CHAR_MECA",
            "TEMP_FIELD = CREA_CHAMP",
            "RESU = MECA_STATIQUE",
            "RESU = CALC_CHAMP",
            "IMPR_RESU(",
            "TAB_EFFO = CREA_TABLE",
            "TAB_DEPL = CREA_TABLE",
            "TAB_REAC = CREA_TABLE",
            "TAB_SIEQ = CREA_TABLE",
            "FIN();",
        ]
        positions = [comm.index(token) for token in tokens]

        self.assertEqual(positions, sorted(positions))

    def test_export_analysis_study_restrains_pipe_warping_at_nonlinear_rest(self):
        model = Model(project_name="WarpingRest")
        model.add_material("Steel", E=2.0e11, nu=0.3, alpha=1.2e-5)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 0.0, 0.0])
        model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")
        model.add_support(n0, type="anchor")
        model.add_support(n1, type="rest")
        model.define_load_case("Hot", gravity=True, temperature=120.0, ref_temperature=20.0)

        with TemporaryDirectory() as tmpdir:
            study = CodeAsterSolver(work_dir=tmpdir).export_analysis_study(model, "Hot", tmpdir)
            comm = (Path(study.work_dir) / "study.comm").read_text(encoding="utf-8")

        self.assertIn("WO=0.0", comm)
        self.assertIn("CONTACT=contact", comm)

    def test_export_analysis_study_creates_poi1_with_code_aster_node_selector(self):
        model = Model(project_name="SpringPoi1")
        model.add_material("Steel", E=2.0e11, nu=0.3, alpha=1.2e-5)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 0.0, 0.0])
        n2 = model.add_node([2.0, 0.0, 0.0])
        model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")
        model.add_element(id="pipe_1", type="pipe_straight", n1=n1, n2=n2, section="PipeSec", material="Steel")
        model.add_support(n0, type="anchor")
        model.add_support(n1, type="spring", stiffness_matrix=[1.0e5, 1.0e5, 1.0e5, 1.0e3, 1.0e3, 1.0e3])
        model.add_support(n2, type="rest", mass=50.0)
        model.define_load_case("Hot", gravity=True, temperature=120.0, ref_temperature=20.0)

        with TemporaryDirectory() as tmpdir:
            study = CodeAsterSolver(work_dir=tmpdir).export_analysis_study(model, "Hot", tmpdir)
            comm = (Path(study.work_dir) / "study.comm").read_text(encoding="utf-8")

        self.assertIn(f"_F(NOM_GROUP_MA='DIS_{n1}', NOEUD='{n1}'),", comm)
        self.assertIn("CARA='K_TR_D_N'", comm)
        self.assertIn("CARA='M_TR_D_N'", comm)
        self.assertNotIn("NOM_NOEUD", comm)
        self.assertNotIn("CARA='K_TR_D_L'", comm)
        self.assertNotIn("CARA='M_T_D_N'", comm)

    def test_export_analysis_study_ramps_temperature_for_nonlinear_thermal_case(self):
        model = Model(project_name="ThermalRamp")
        model.add_material("Steel", E=2.0e11, nu=0.3, alpha=1.2e-5)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 0.0, 0.0])
        model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")
        model.add_support(n0, type="anchor")
        model.add_support(n1, type="rest")
        model.define_load_case("Hot", gravity=True, temperature=150.0, ref_temperature=20.0)

        with TemporaryDirectory() as tmpdir:
            study = CodeAsterSolver(work_dir=tmpdir).export_analysis_study(model, "Hot", tmpdir)
            comm = (Path(study.work_dir) / "study.comm").read_text(encoding="utf-8")

        self.assertIn("TEMP_REF_FIELD = CREA_CHAMP(", comm)
        self.assertIn("TEMP_HOT_FIELD = CREA_CHAMP(", comm)
        self.assertIn("TEMP_EVOL = CREA_RESU(", comm)
        self.assertIn("TYPE_RESU='EVOL_THER'", comm)
        self.assertIn("EVOL=TEMP_EVOL,", comm)
        self.assertNotIn("CHAM_GD=TEMP_FIELD", comm)

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

    def test_rmed_loader_reads_rmed_with_med_format(self):
        calls = []

        class FakeMesh:
            points = [(0.0, 0.0, 0.0)]

        class FakeMeshio:
            @staticmethod
            def read(path, *, file_format=None):
                calls.append((Path(path).name, file_format))
                return FakeMesh()

        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "study.rmed").write_bytes(b"fake-med-content")
            results = FEAResults(solver_name="Code_Aster")

            with patch.dict("sys.modules", {"meshio": FakeMeshio}):
                CodeAsterSolver._try_load_rmed(root, results)

        self.assertEqual(calls, [("study.rmed", "med")])
        self.assertIsInstance(results.raw_mesh, FakeMesh)


if __name__ == "__main__":
    unittest.main()
