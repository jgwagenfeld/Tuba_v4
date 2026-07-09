import unittest
import numpy as np
import tempfile
from pathlib import Path

from tuba import Model, Material, PipeSection, PipingBuilder
from tuba.solver.base import FEAResults, NodeResult, ElementResult
from tuba.compliance.sif import compute_sifs, flexibility_characteristic, flexibility_factor, sif_inplane, sif_outplane
from tuba.compliance.asme_b313 import ASMEB313Evaluator
from tuba.optimization.optimizer import GeneticSupportPlacer, LLMSupportOptimizer, RuleBasedSupportPlacer
from tuba.plotting.pipeline import build_mesh_from_model, build_3d_mesh_from_model


class TestMaterial(unittest.TestCase):
    def test_material_properties(self):
        mat = Material(
            name="P265GH",
            E=2.1e11,
            nu=0.3,
            allowable_stress={20.0: 147e6, 100.0: 138e6, 200.0: 130e6}
        )
        # Check shear modulus
        self.assertAlmostEqual(mat.G, 2.1e11 / (2.0 * 1.3))

        # Check allowable stress interpolation
        self.assertEqual(mat.get_allowable(10.0), 147e6)  # clamping to min
        self.assertEqual(mat.get_allowable(20.0), 147e6)
        self.assertEqual(mat.get_allowable(100.0), 138e6)
        self.assertEqual(mat.get_allowable(250.0), 130e6)  # clamping to max
        
        # Test middle value
        self.assertAlmostEqual(mat.get_allowable(60.0), 142.5e6)  # half between 147 and 138


class TestPipeSection(unittest.TestCase):
    def test_section_properties(self):
        sec = PipeSection(name="4inch_sch40", OD=0.1143, WT=0.00602, corrosion_allowance=0.0015)
        
        # Inner diameter
        self.assertAlmostEqual(sec.ID, 0.1143 - 2 * 0.00602)
        
        # Corroded wall thickness
        self.assertAlmostEqual(sec.corroded_WT, 0.00602 - 0.0015)
        
        # Mean radius
        self.assertAlmostEqual(sec.mean_radius, (0.1143 - 0.00602) / 2.0)
        
        # Area, moment of inertia (uncorroded)
        r_o = 0.1143 / 2.0
        r_i = (0.1143 - 2 * 0.00602) / 2.0
        expected_area = np.pi * (r_o**2 - r_i**2)
        expected_I = (np.pi / 4.0) * (r_o**4 - r_i**4)
        
        self.assertAlmostEqual(sec.area, expected_area)
        self.assertAlmostEqual(sec.I, expected_I)
        self.assertAlmostEqual(sec.J, 2.0 * expected_I)
        self.assertAlmostEqual(sec.Z, expected_I / r_o)
        
        # Corroded modulus
        t_c = 0.00602 - 0.0015
        r_ic = (0.1143 - 2 * t_c) / 2.0
        expected_I_c = (np.pi / 4.0) * (r_o**4 - r_ic**4)
        expected_Z_c = expected_I_c / r_o
        self.assertAlmostEqual(sec.corroded_Z, expected_Z_c)

    def test_get_section_radius(self):
        from tuba.plotting.pipeline import get_section_radius
        from tuba.model import PipeSection, BarSection, CableSection, RectangularSection, IBeamSection
        
        pipe = PipeSection(name="pipe", OD=0.1, WT=0.01)
        self.assertAlmostEqual(get_section_radius(pipe), 0.05)
        
        bar = BarSection(name="bar", OD=0.08, WT=0.0)
        self.assertAlmostEqual(get_section_radius(bar), 0.04)
        
        cable = CableSection(name="cable", radius=0.03)
        self.assertAlmostEqual(get_section_radius(cable), 0.03)
        
        rect = RectangularSection(name="rect", height_y=0.1, height_z=0.2)
        self.assertAlmostEqual(get_section_radius(rect), 0.1)
        
        ibeam = IBeamSection(name="ibeam", profile_name="IPE100", properties={"EY": 0.05, "EZ": 0.04})
        self.assertAlmostEqual(get_section_radius(ibeam), 0.05)

        incomplete_ibeam = IBeamSection(name="bad_ibeam", profile_name="CUSTOM", properties={"EY": 0.05})
        with self.assertRaisesRegex(ValueError, "missing dimension"):
            get_section_radius(incomplete_ibeam)


class TestModelAndBuilder(unittest.TestCase):
    def test_builder_and_json(self):
        model = Model(project_name="TestProject", standard="ASME_B31.3")
        model.add_material("St37", E=2.1e11, nu=0.3, allowable_stress={20: 120e6})
        model.add_pipe_section("3inch", OD=0.0889, WT=0.00549)
        
        with model.pipe(section="3inch", material="St37") as b:
            b.start([0, 0, 0], support="anchor")
            b.run(4.0)
            b.bend(radius=0.1143, angle=90, plane="XY")
            b.run(3.0)
            b.end([4.1143, 3.1143, 0], support="anchor")
            
        # Inspect model structure
        self.assertEqual(len(model.nodes), 4) # start, bend-entry (advanced by tangent), bend-exit, end
        self.assertEqual(len(model.elements), 3) # 2 straight runs, 1 bend
        self.assertEqual(len(model.supports), 2)
        
        # Serialise to dictionary
        data = model.to_dict()
        self.assertEqual(data["meta"]["project_name"], "TestProject")
        self.assertIn("St37", data["materials"])
        self.assertIn("3inch", data["sections"])
        self.assertEqual(len(data["nodes"]), 4)
        self.assertEqual(len(data["elements"]), 3)
        self.assertEqual(len(data["supports"]), 2)
        
        # JSON Roundtrip
        with tempfile.TemporaryDirectory() as tmpdir:
            json_file = Path(tmpdir) / "model.json"
            model.to_json(str(json_file))
            
            loaded_model = Model.from_json(str(json_file))
            self.assertEqual(loaded_model.project_name, "TestProject")
            self.assertEqual(len(loaded_model.nodes), 4)
            self.assertEqual(len(loaded_model.elements), 3)
            self.assertEqual(len(loaded_model.supports), 2)
            self.assertIn("St37", loaded_model.materials)

    def test_element_ids_are_unique_across_builder_contexts(self):
        model = Model(project_name="BranchingIds")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)

        with model.pipe(section="PipeSec", material="Steel") as b:
            b.start([0, 0, 0]).run(2.0).run(2.0)

        with model.pipe(section="PipeSec", material="Steel") as b:
            b.start([2, 0, 0]).set_direction([0, 1, 0]).run(2.0)

        element_ids = [e.id for e in model.elements]
        self.assertEqual(len(element_ids), len(set(element_ids)))
        self.assertEqual(element_ids, ["pipe_str_0", "pipe_str_1", "pipe_str_2"])

        with tempfile.TemporaryDirectory() as tmpdir:
            json_file = Path(tmpdir) / "branching.json"
            model.to_json(str(json_file))
            loaded = Model.from_json(str(json_file))

            with loaded.pipe(section="PipeSec", material="Steel") as b:
                b.start([4, 0, 0]).run(1.0)

            loaded_ids = [e.id for e in loaded.elements]
            self.assertEqual(len(loaded_ids), len(set(loaded_ids)))
            self.assertIn("pipe_str_3", loaded_ids)

    def test_builder_v2_style_spring_uses_stiffness_matrix(self):
        model = Model(project_name="V2StyleSpring")
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)

        with model.pipe(section="PipeSec", material="Steel") as b:
            b.start([0, 0, 0])
            b.spring(y=1.5e6)

        self.assertEqual(len(model.supports), 1)
        self.assertEqual(model.supports[0].type, "spring")
        self.assertEqual(model.supports[0].stiffness_matrix, [0.0, 1.5e6, 0.0, 0.0, 0.0, 0.0])
        self.assertIsNone(model.supports[0].stiffness)

    def test_optimizer_llm_spring_suggestions_use_stiffness_matrix(self):
        model = Model(project_name="LLMSpring")
        model.add_node(np.array([0.0, 0.0, 0.0]))

        optimizer = LLMSupportOptimizer()
        logs = optimizer.apply_llm_suggestions(
            model,
            '[{"action": "ADD", "node": "N0", "type": "spring", "y": 150000.0}]',
        )

        self.assertEqual(logs, ["Added spring support at node N0"])
        self.assertEqual(model.supports[0].stiffness_matrix, [0.0, 150000.0, 0.0, 0.0, 0.0, 0.0])
        self.assertIsNone(model.supports[0].stiffness)

    def test_genetic_support_placer_spring_gene_uses_stiffness_matrix(self):
        model = Model(project_name="GeneticSpring")
        model.add_support(node="N0", type="anchor")

        placer = GeneticSupportPlacer(spring_stiffness_matrix=[0.0, 200000.0, 0.0, 0.0, 0.0, 0.0])
        placer._apply_chromosome(model, ["N1"], np.array([3]))

        spring = next(s for s in model.supports if s.type == "spring")
        self.assertEqual(spring.stiffness_matrix, [0.0, 200000.0, 0.0, 0.0, 0.0, 0.0])
        self.assertIsNone(spring.stiffness)

    def test_genetic_support_placer_rejects_implicit_spring_gene(self):
        model = Model(project_name="GeneticNoImplicitSpring")
        placer = GeneticSupportPlacer()

        with self.assertRaisesRegex(ValueError, "spring_stiffness_matrix"):
            placer._apply_chromosome(model, ["N1"], np.array([3]))

    def test_rule_based_support_placer_is_disabled(self):
        model = Model(project_name="NoHeuristicSupportPlacement")
        placer = RuleBasedSupportPlacer()

        with self.assertRaisesRegex(NotImplementedError, "heuristic support layouts"):
            placer.optimize(model, evaluator=None)

    def test_load_case_ref_temperature_roundtrip(self):
        model = Model(project_name="LoadCaseRoundtrip")
        model.define_load_case(
            "Hot",
            gravity=True,
            pressure=1.0e6,
            temperature=120.0,
            ref_temperature=45.0,
        )

        loaded = Model.from_dict(model.to_dict())

        self.assertEqual(loaded.load_cases["Hot"].ref_temperature, 45.0)

    def test_bend_visualization_polyline(self):
        model = Model()
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1143, WT=0.006)
        with model.pipe(section="PipeSec", material="Steel") as b:
            b.start([0, 0, 0])
            b.run(2.0)
            b.bend(radius=0.2, angle=90, plane="XY")
            b.run(2.0)
            b.end()

        mesh = build_mesh_from_model(model)
        # Expected points: 4 nodes + 15 intermediate bend points = 19 points
        self.assertEqual(mesh.n_points, 19)
        # Expected cells: 1 continuous polyline cell
        self.assertEqual(mesh.n_cells, 1)

        # Retrieve the cell array data
        # lines format: [n_pts, p0, p1, ...]
        cells = mesh.lines
        self.assertEqual(cells[0], 19)
        self.assertEqual(len(cells), 20)

    def test_bend_visualization_requires_explicit_geometry(self):
        model = Model()
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1143, WT=0.006)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 1.0, 0.0])
        model.add_element(
            id="pipe_bend_0",
            type="pipe_bend",
            n1=n0,
            n2=n1,
            section="PipeSec",
            material="Steel",
            bend_radius=0.5,
            bend_angle=90.0,
        )

        with self.assertRaisesRegex(ValueError, "explicit bend_geometry"):
            build_mesh_from_model(model)

    def test_element_local_frame(self):
        from tuba.plotting.plots import _get_element_local_frame
        
        # Test horizontal pipe
        model = Model()
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        with model.pipe(section="PipeSec", material="Steel") as b:
            b.start([0, 0, 0]).run(2.0).end()
            
        elem = model.elements[0]
        lx, ly, lz = _get_element_local_frame(model, elem)
        
        # lx points along +X
        np.testing.assert_array_almost_equal(lx, [1.0, 0.0, 0.0])
        # For pipe, default V = (0, 0, 1). ly = V x lx = (0, 0, 1) x (1, 0, 0) = (0, 1, 0)
        np.testing.assert_array_almost_equal(ly, [0.0, 1.0, 0.0])
        # lz = lx x ly = (1, 0, 0) x (0, 1, 0) = (0, 0, 1)
        np.testing.assert_array_almost_equal(lz, [0.0, 0.0, 1.0])

        # Test horizontal beam with 90 degree twist angle
        model2 = Model()
        model2.add_material("Steel", E=2.0e11, nu=0.3)
        model2.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        with model2.pipe(section="PipeSec", material="Steel") as b:
            b.start([0, 0, 0]).beam(2.0, twist_angle=90.0).end()
            
        elem2 = model2.elements[0]
        lx2, ly2, lz2 = _get_element_local_frame(model2, elem2)
        
        # lx2 points along +X
        np.testing.assert_array_almost_equal(lx2, [1.0, 0.0, 0.0])
        # Default beam frame: Z_global = (0,0,1). ly = Z x lx = (0,0,1) x (1,0,0) = (0,1,0), lz = lx x ly = (0,0,1)
        # Rotated by 90 degrees counter-clockwise around lx:
        # ly_new = ly * cos(90) + lz * sin(90) = lz = (0, 0, 1)
        # lz_new = lz * cos(90) - ly * sin(90) = -ly = (0, -1, 0)
        np.testing.assert_array_almost_equal(ly2, [0.0, 0.0, 1.0])
        np.testing.assert_array_almost_equal(lz2, [0.0, -1.0, 0.0])


class TestComplianceAndSif(unittest.TestCase):
    def test_sif_formulas(self):
        # Straight pipe
        from tuba.model import Element
        straight = Element(id="E0", type="pipe_straight", n1="N0", n2="N1", section="3inch", material="St37")
        model = Model()
        model.add_pipe_section("3inch", OD=0.0889, WT=0.00549)
        model.add_material("St37", E=2.1e11, nu=0.3)
        
        i_i, i_o, k, h = compute_sifs(straight, model)
        self.assertEqual(i_i, 1.0)
        self.assertEqual(i_o, 1.0)
        self.assertEqual(k, 1.0)
        self.assertEqual(h, 0.0)
        
        # Elbow
        elbow = Element(
            id="E1",
            type="pipe_bend",
            n1="N1",
            n2="N2",
            section="3inch",
            material="St37",
            bend_radius=0.1143,
            bend_angle=90.0
        )
        # Calculate manually
        # h = t * R / r_m^2
        t = 0.00549
        R = 0.1143
        r_m = (0.0889 - 0.00549) / 2.0
        expected_h = t * R / (r_m ** 2)
        expected_ii = max(0.9 / (expected_h ** (2.0 / 3.0)), 1.0)
        expected_io = max(0.75 / (expected_h ** (2.0 / 3.0)), 1.0)
        expected_k = 1.65 / expected_h
        
        i_i, i_o, k, h = compute_sifs(elbow, model)
        self.assertAlmostEqual(h, expected_h)
        self.assertAlmostEqual(i_i, expected_ii)
        self.assertAlmostEqual(i_o, expected_io)
        self.assertAlmostEqual(k, expected_k)

    def test_compliance_evaluation(self):
        model = Model(project_name="TestCompliance")
        model.add_material("Steel", E=2.0e11, nu=0.3, allowable_stress={20.0: 137.0e6, 200.0: 120.0e6})
        model.add_pipe_section("PipeSec", OD=0.1143, WT=0.00602, corrosion_allowance=0.001)
        
        with model.pipe(section="PipeSec", material="Steel") as b:
            b.start([0, 0, 0], support="anchor")
            b.run(5.0)
            b.end([5, 0, 0], support="anchor")
            
        model.define_load_case("HotCase", gravity=True, pressure=1.5e6, temperature=200.0)
        
        # Build mock results
        results = FEAResults(solver_name="mock_solver", load_case="HotCase")
        
        # 1 element: E0, connecting N0 and N1
        eid = model.elements[0].id
        results.node_results["N0"] = NodeResult(node_id="N0", displacement=np.zeros(6), reaction_force=np.zeros(6))
        results.node_results["N1"] = NodeResult(node_id="N1", displacement=np.zeros(6), reaction_force=np.zeros(6))
        
        # Set some internal forces (N, Vy, Vz, Mx, My, Mz)
        # Apply pure bending moment at both ends: Mz = 1000 N*m, Mx (torsion) = 500 N*m
        forces_n1 = np.array([0.0, 0.0, 0.0, 500.0, 0.0, 1000.0])
        forces_n2 = np.array([0.0, 0.0, 0.0, -500.0, 0.0, -1000.0])
        results.element_results[eid] = ElementResult(
            element_id=eid,
            forces_n1=forces_n1,
            forces_n2=forces_n2,
            von_mises_n1=50e6,
            von_mises_n2=50e6,
            max_von_mises=50e6
        )
        
        evaluator = ASMEB313Evaluator()
        report = evaluator.evaluate(model, results)
        
        self.assertEqual(len(report.results), 2) # two nodes (n1 and n2)
        res_n1 = report.results[0]
        
        # Verify manual sustained stress: S_L = P*Do/(4*t) + M_resultant / Z_c
        # P = 1.5e6, Do = 0.1143, t_c = 0.00502
        pressure_term = 1.5e6 * 0.1143 / (4 * 0.00502)
        # M_resultant = 1000, Z_c
        OD = 0.1143
        t_c = 0.00502
        ID_c = OD - 2 * t_c
        I_c = (np.pi / 64) * (OD**4 - ID_c**4)
        Z_c = I_c / (OD / 2.0)
        bending_term = 1000.0 / Z_c
        expected_SL = pressure_term + bending_term
        
        self.assertAlmostEqual(res_n1.sustained_stress, expected_SL, delta=1.0)
        
        # Allowable sustained stress S_h at 200C is 120 MPa
        self.assertEqual(res_n1.sustained_allowable, 120.0e6)
        
        # Verify detailed calculation string
        detail = report.get_detailed_calculation(eid)
        self.assertIn("ASME B31.3 Detailed Calculation — Element `pipe_str_0`", detail)
        self.assertIn("Node `N0`", detail)
        self.assertIn("Sustained Stress", detail)


class TestVisualizer(unittest.TestCase):
    def test_pyvista_mesh_pipeline(self):
        model = Model()
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1143, WT=0.006)
        with model.pipe(section="PipeSec", material="Steel") as b:
            b.start([0,0,0]).run(2.0).end()
            
        mesh = build_mesh_from_model(model)
        self.assertEqual(mesh.n_points, 2)
        self.assertEqual(mesh.n_cells, 1)
        
        # The true 3D geometry is extruded straight from the section — no
        # inflation radius to hand-tune — and must carry real surface faces.
        solid = build_3d_mesh_from_model(model)
        self.assertGreater(solid.n_points, mesh.n_points)
        self.assertGreater(solid.n_cells, mesh.n_cells)

    def test_3d_cross_sectional_mesh(self):
        from tuba.plotting.pipeline import build_3d_mesh_from_model
        
        # 1. Circular section
        model = Model()
        model.add_material("Steel", E=2.0e11, nu=0.3)
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.005)
        with model.pipe(section="PipeSec", material="Steel") as b:
            b.start([0,0,0]).run(2.0).end()
            
        mesh = build_3d_mesh_from_model(model)
        # N=2 layers, M=16 outer + 16 inner vertices. Total points = 64.
        self.assertEqual(mesh.n_points, 64)
        # Outer wall + inner wall + annular profile faces at both ends.
        self.assertEqual(mesh.n_cells, 64)
        
        # 2. Rectangular Section
        model2 = Model()
        model2.add_material("Steel", E=2.0e11, nu=0.3)
        model2.add_rectangular_section("RectSec", height_y=0.1, height_z=0.2)
        with model2.pipe(section="RectSec", material="Steel") as b:
            b.start([0,0,0]).beam(2.0).end()
            
        mesh2 = build_3d_mesh_from_model(model2)
        # N=2 layers, M=4 vertices. Total points = 8
        self.assertEqual(mesh2.n_points, 8)
        # 4 quads + 2 end caps = 6 cells
        self.assertEqual(mesh2.n_cells, 6)

        # 3. Hollow Rectangular Section
        model4 = Model()
        model4.add_material("Steel", E=2.0e11, nu=0.3)
        model4.add_rectangular_section("BoxSec", height_y=0.1, height_z=0.2, thickness_y=0.01, thickness_z=0.02)
        with model4.pipe(section="BoxSec", material="Steel") as b:
            b.start([0,0,0]).beam(2.0).end()

        mesh4 = build_3d_mesh_from_model(model4)
        self.assertEqual(mesh4.n_points, 16)
        self.assertEqual(mesh4.n_cells, 16)
        
        # 4. I-Beam Section
        model3 = Model()
        model3.add_material("Steel", E=2.0e11, nu=0.3)
        model3.add_ibeam_section("IBeamSec", "IPE80")
        with model3.pipe(section="IBeamSec", material="Steel") as b:
            b.start([0,0,0]).beam(2.0).end()
            
        mesh3 = build_3d_mesh_from_model(model3)
        # N=2 layers, M=12 vertices. Total points = 24
        self.assertEqual(mesh3.n_points, 24)
        # 12 side quads + triangulated concave I-beam end caps.
        self.assertEqual(mesh3.n_cells, 32)
        cell_sizes = []
        idx = 0
        while idx < len(mesh3.faces):
            n = mesh3.faces[idx]
            cell_sizes.append(n)
            idx += n + 1
        self.assertEqual(cell_sizes.count(4), 12)
        self.assertEqual(cell_sizes.count(3), 20)
        self.assertNotIn(12, cell_sizes)


class TestCodeAsterSolver(unittest.TestCase):
    def test_export_study(self):
        model = Model(project_name="TestExport")
        model.add_material("Steel", E=2.0e11, nu=0.3, alpha=1.2e-5)
        model.add_pipe_section("PipeSec", OD=0.1143, WT=0.006)
        with model.pipe(section="PipeSec", material="Steel") as b:
            b.start([0, 0, 0], support="anchor").run(3.0).end(support="anchor")

        model.define_load_case("HotCase", gravity=True, pressure=1.5e6, temperature=150.0)

        from tuba.solver.aster import CodeAsterSolver
        solver = CodeAsterSolver()
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            solver.export_study(model, "HotCase", out_dir)

            # Check file existence
            self.assertTrue((out_dir / "study.mail").exists())
            self.assertTrue((out_dir / "study.comm").exists())
            self.assertTrue((out_dir / "study.export").exists())

            # Read content to ensure f-strings worked
            mail_content = (out_dir / "study.mail").read_text(encoding="utf-8")
            comm_content = (out_dir / "study.comm").read_text(encoding="utf-8")
            self.assertIn("SEG3", mail_content)
            self.assertIn("pipe_str_0_mid", mail_content)
            self.assertIn("GROUP_NO NOM=PipeOrientationNodes", mail_content)
            self.assertIn("GROUP_MA NOM=SEC_PipeSec", mail_content)
            self.assertIn("GROUP_NO='PipeOrientationNodes'", comm_content)
            self.assertIn("GROUP_MA='SEC_PipeSec'", comm_content)
            self.assertIn("VALE=1.500000E+02", comm_content)
            self.assertIn("PRES=1.500000E+06", comm_content)

            export_content = (out_dir / "study.export").read_text(encoding="utf-8")
            self.assertIn("F comm study.comm D 1", export_content)
            self.assertIn("F mail study.mail D 20", export_content)
            self.assertIn("F rmed study.rmed R 80", export_content)

    def test_export_study_with_all_elements_and_supports(self):
        model = Model(project_name="AllElementsExport")
        model.add_material("Steel", E=2.0e11, nu=0.3, alpha=1.2e-5)
        
        # Add various sections
        model.add_pipe_section("PipeSec", OD=0.1143, WT=0.006)
        model.add_bar_section("BarSec", OD=0.05, WT=0.0)
        model.add_cable_section("CableSec", radius=0.01, pretension=500.0)
        model.add_rectangular_section("RectSec", height_y=0.08, height_z=0.04, thickness_y=0.005, thickness_z=0.005)
        
        # Load I-Beam from DB
        try:
            model.add_ibeam_section("IBeamSec", "IPE100")
        except Exception:
            # Fallback if DB file is missing or in incorrect path in test env
            from tuba.model import IBeamSection
            model.sections["IBeamSec"] = IBeamSection(name="IBeamSec", profile_name="IPE100", properties={
                "A": 1.03e-3, "IY": 1.71e-6, "IZ": 1.59e-7, "JX": 1.2e-8, "RY": 4.07e-2, "RZ": 1.24e-2
            })
            
        with model.pipe(section="PipeSec", material="Steel") as b:
            b.start([0, 0, 0], support="anchor")
            b.run(2.0)
            
        # Add beam, bar, and cable elements
        with model.pipe(section="IBeamSec", material="Steel") as b:
            b.start([2, 0, 0]).beam(1.5)
            
        with model.pipe(section="BarSec", material="Steel") as b:
            b.start([3.5, 0, 0]).bar(1.0)
            
        with model.pipe(section="CableSec", material="Steel") as b:
            b.start([4.5, 0, 0]).cable(2.0)
            
        with model.pipe(section="RectSec", material="Steel") as b:
            b.start([6.5, 0, 0]).beam(1.0)
            
        # Add supports with stiffness, blocked DOFs, and masses
        model.add_support(node="N1", type="spring", stiffness_matrix=[0.0, 1.5e6, 0.0, 0.0, 0.0, 0.0])
        model.add_support(node="N2", type="custom", blocked_dof=[1, 1, 0, 0, 0, 1])
        model.add_support(node="N3", type="spring", stiffness_matrix=[1e5, 2e5, 3e5, 0.0, 0.0, 0.0])
        model.add_support(node="N4", type="rest", mass=50.0)

        model.define_load_case("LoadCase1", gravity=True, pressure=1.0e6, temperature=120.0)

        from tuba.solver.aster import CodeAsterSolver
        solver = CodeAsterSolver()
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            solver.export_study(model, "LoadCase1", out_dir)

            self.assertTrue((out_dir / "study.mail").exists())
            self.assertTrue((out_dir / "study.comm").exists())

            comm = (out_dir / "study.comm").read_text(encoding="utf-8")
            mail = (out_dir / "study.mail").read_text(encoding="utf-8")

            # Check modelisations are mapped
            self.assertIn("MODELISATION='POU_D_T'", comm)
            self.assertIn("MODELISATION='BARRE'", comm)
            self.assertIn("MODELISATION='CABLE'", comm)
            self.assertIn("MODELISATION='DIS_TR'", comm)
            self.assertIn("RELATION='CABLE'", comm)
            self.assertIn("DEFORMATION='GROT_GDEP'", comm)
            self.assertIn("GROUP_MA='G_CABLE'", comm)
            self.assertIn("SEG3", mail)
            self.assertIn("SEG2", mail)

            # Check section definitions
            self.assertIn("SECTION='CERCLE'", comm)
            self.assertIn("SECTION='RECTANGLE'", comm)
            self.assertIn("SECTION='GENERALE'", comm) # I-Beam
            self.assertIn("SECTION=3.14159265E-04", comm) # Cable area

            # Check boundary conditions and stiffnesses
            self.assertIn("CARA='K_TR_D_N'", comm)
            self.assertIn("CARA='M_TR_D_N'", comm)
            self.assertIn("DX=0.0", comm)
            self.assertIn("DY=0.0", comm)
            self.assertIn("DRZ=0.0", comm)


if __name__ == "__main__":
    unittest.main()
