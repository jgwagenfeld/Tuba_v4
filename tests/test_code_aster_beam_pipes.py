"""Beam pipe export and real Code_Aster reference checks."""
import json
import math
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tuba import Model
from tuba.model import BendGeometry
from tuba.analysis.provenance import validate_solver_input_identity, CODE_ASTER_COMPILER_ID
from tuba.compliance.sif import compute_sif_set
from tuba.solver.aster import CodeAsterSolver
from tuba.solver.modelisation import PipeModelization


def beam_model(*, elbow=False):
    model = Model(project_name="Beam pipe qualification")
    model.add_material("Steel", E=200e9, nu=0.3, rho=7850, alpha=12e-6)
    model.add_pipe_section("Pipe", OD=0.1143, WT=0.006)
    start = model.add_node([0, 0, 0])
    end = model.add_node([4, 0, 0])
    model.add_element(id="straight", type="pipe_straight", n1=start, n2=end, section="Pipe", material="Steel")
    if elbow:
        bend_end = model.add_node([4.3, 0.3, 0])
        model.add_element(id="elbow", type="pipe_bend", n1=end, n2=bend_end,
                          section="Pipe", material="Steel", bend_radius=0.3, bend_angle=90,
                          bend_geometry=BendGeometry(center=[4, 0.3, 0], normal=[0, 0, 1], radius=0.3, angle=90,
                                                     start_tangent=[1, 0, 0], end_tangent=[0, 1, 0]))
        end = bend_end
    model.add_support(start, "anchor")
    model.define_load_case("Load", gravity=False)
    return model, end


class BeamPipeExportTests(unittest.TestCase):
    def test_formulation_mesh_loads_and_identity(self):
        model, end = beam_model(elbow=True)
        model.load_cases["Load"].gravity = True
        model.load_cases["Load"].temperature = 120
        model.load_cases["Load"].add_nodal_force(end, [1000, 0, 0])
        with TemporaryDirectory() as root:
            solver = CodeAsterSolver(pipe_modelization=PipeModelization.POU_D_T)
            study = solver.export_analysis_study(model, "Load", root)
            comm = (Path(root) / "study.comm").read_text()
            mail = (Path(root) / "study.mail").read_text()
            mesh = json.loads((Path(root) / "study_manifest.json").read_text())["analysis_mesh"]
            self.assertEqual(mesh["modelisations"]["AllPipes"], "POU_D_T")
            self.assertNotIn("SEG3", mail)
            self.assertNotIn("_mid", mail)
            self.assertIn("SEG2", mail)
            for forbidden in ("GENE_TUYAU", "WO=", "SIEQ_EL", "INDI_SIGM"):
                self.assertNotIn(forbidden, comm)
            for expected in ("PESANTEUR", "NOM_VARC='TEMP'", "FORCE_NODALE", "EFGE_ELNO", "ANGL_VRIL"):
                self.assertIn(expected, comm)
            k = compute_sif_set(model.get_element("elbow"), model).k_i
            self.assertIn(f"COEF_FLEX={k:.10E}", comm)
            self.assertFalse(study.metadata["pipe_stress_exported"])
            inputs = study.metadata["compiler_inputs"]
            validate_solver_input_identity(model, study.solver_input_identity, context="beam", expected_load_case="Load",
                                           expected_compiler_id=CODE_ASTER_COMPILER_ID, compiler_inputs=inputs)
            with self.assertRaisesRegex(ValueError, "fingerprint"):
                validate_solver_input_identity(model, study.solver_input_identity, context="beam", expected_load_case="Load",
                                               expected_compiler_id=CODE_ASTER_COMPILER_ID,
                                               compiler_inputs={**inputs, "pipe_modelization": "TUYAU_3M"})

    def test_default_and_public_forwarding(self):
        model, _ = beam_model()
        with TemporaryDirectory() as root:
            CodeAsterSolver().export_study(model, "Load", root)
            self.assertIn("SEG3", (Path(root) / "study.mail").read_text())
        with patch.object(CodeAsterSolver, "solve", autospec=True) as solve:
            model.solve(pipe_modelization="POU_D_T")
            self.assertIs(solve.call_args.args[0].pipe_modelization, PipeModelization.POU_D_T)

    def test_pressure_and_branch_fail(self):
        model, end = beam_model()
        solver = CodeAsterSolver(pipe_modelization="POU_D_T")
        with TemporaryDirectory() as root:
            model.load_cases["Load"].internal_pressure = 1e6
            with self.assertRaisesRegex(ValueError, "pressure end thrust"):
                solver.export_study(model, "Load", root)
            model.load_cases["Load"].internal_pressure = 0
            for i in (-1, 1):
                tip = model.add_node([4, i, 0])
                model.add_element(id=f"branch{i}", type="pipe_straight", n1=end, n2=tip, section="Pipe", material="Steel")
            with self.assertRaisesRegex(ValueError, "tee/branch"):
                solver.export_study(model, "Load", root)


@unittest.skipUnless(os.getenv("TUBA_RUN_CODE_ASTER_INTEGRATION") == "1", "Real Code_Aster opt-in")
class BeamPipeReferenceTests(unittest.TestCase):
    def test_axial_bending_and_temperature(self):
        model, end = beam_model()
        model.load_cases["Load"].add_nodal_force(end, [1000, 1000, 0])
        model.load_cases["Load"].temperature = 120
        root = Path(".build/beam-qualification/straight").resolve()
        run = model.solve("Load", pipe_modelization="POU_D_T", work_dir=str(root), exec_method="wsl", wsl_distro="Ubuntu", force=True)
        u = run.results.node_results[end].displacement
        section = model.sections["Pipe"]
        area = math.pi / 4 * (section.OD**2 - (section.OD - 2*section.WT)**2)
        inertia = math.pi / 64 * (section.OD**4 - (section.OD - 2*section.WT)**4)
        expected_axial = 1000 * 4 / (200e9 * area) + 12e-6 * 100 * 4
        # Slender beam: transverse shear is below the declared 1% tolerance.
        expected_bending = 1000 * 4**3 / (3 * 200e9 * inertia)
        self.assertAlmostEqual(u[0] / expected_axial, 1, delta=0.01)
        self.assertAlmostEqual(u[1] / expected_bending, 1, delta=0.01)
        self.assertFalse(run.result_state.metadata.get("pipe_stress_exported", False))
        print("Beam straight measured/reference:", float(u[0]), expected_axial, float(u[1]), expected_bending)

    def test_elbow_flexibility_and_refinement(self):
        model, end = beam_model(elbow=True)
        model.load_cases["Load"].add_nodal_force(end, [0, 0, 0], moment=[0, 0, 100])
        sec = model.sections["Pipe"]
        inertia = math.pi / 64 * (sec.OD**4 - (sec.OD - 2*sec.WT)**4)
        k = compute_sif_set(model.get_element("elbow"), model).k_i
        scale = 100 / (200e9 * inertia)
        # Independent unit-moment integration on straight + circular arc,
        # using EI/k on the elbow; no transverse force/shear deformation.
        expected = [-(4*0.3 + k*0.3**2)*scale,
                    (4**2/2 + 4*0.3 + k*0.3**2*(math.pi/2 - 1))*scale,
                    (4 + k*0.3*math.pi/2)*scale]
        observed = []
        for segments in (32, 64):
            root = Path(f".build/beam-qualification/elbow-{segments}").resolve()
            solver = CodeAsterSolver(pipe_modelization="POU_D_T", work_dir=str(root), exec_method="wsl", wsl_distro="Ubuntu")
            solver._BEND_SEGMENTS = segments
            run = solver.solve(model, "Load", force=True)
            u = run.results.node_results[end].displacement
            values = [float(u[i]) for i in (0, 1, 5)]
            observed.append(values)
            for actual, reference in zip(values, expected):
                self.assertAlmostEqual(actual/reference, 1, delta=0.01)
            self.assertAlmostEqual(float(run.results.node_results[next(iter(model.nodes))].reaction_force[5]), -100, delta=0.1)
        for coarse, fine in zip(*observed):
            self.assertAlmostEqual(coarse/fine, 1, delta=0.01)
        print("Beam elbow measured 32/64/reference:", observed, expected)


if __name__ == "__main__":
    unittest.main()

