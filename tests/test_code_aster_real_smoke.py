import math
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from tuba import Model
from tuba.compliance.asme_b313 import ASMEB313Evaluator


@unittest.skipUnless(
    os.environ.get("TUBA_RUN_CODE_ASTER_INTEGRATION") == "1",
    "set TUBA_RUN_CODE_ASTER_INTEGRATION=1 to run real Code_Aster smoke test",
)
class TestCodeAsterRealSmoke(unittest.TestCase):
    def test_minimal_pipe_model_solves_with_real_code_aster(self):
        model = Model(project_name="CodeAsterRealSmoke")
        model.add_material(
            "Steel",
            E=2.0e11,
            nu=0.3,
            rho=7850.0,
            alpha=1.2e-5,
            allowable_stress={20.0: 137e6},
        )
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 0.0, 0.0])
        model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")
        model.add_support(node=n0, type="anchor", id="support_anchor_0")
        model.define_load_case("Operating", gravity=True, pressure=1.0e6, temperature=120.0, ref_temperature=20.0)

        with TemporaryDirectory() as tmpdir:
            run = model.solve(
                load_case="Operating",
                work_dir=tmpdir,
                exec_method=os.environ.get("TUBA_CODE_ASTER_EXEC_METHOD", "auto"),
            )
            results = run.results
            root = Path(tmpdir)

            self.assertTrue((root / "study.export").exists())
            self.assertTrue((root / "study_depl.csv").exists())
            self.assertTrue((root / "study_effo.csv").exists())
            self.assertTrue((root / "study_reac.csv").exists())
            self.assertTrue((root / "study_sieq.csv").exists())

        self.assertEqual(results.solver_name, "Code_Aster")
        self.assertEqual(results.load_case, "Operating")
        self.assertGreater(np.linalg.norm(results.node_results[n1].displacement[:3]), 0.0)
        self.assertIsNotNone(results.node_results[n0].reaction_force)
        self.assertGreater(np.linalg.norm(results.node_results[n0].reaction_force[:3]), 0.0)
        self.assertGreater(results.element_results["pipe_0"].max_von_mises, 0.0)

    def test_cantilever_matches_independent_beam_reference(self):
        """Validate solve/import/compliance against a closed-form cantilever."""
        length = 2.0
        force = 1_000.0
        youngs_modulus = 2.0e11
        outer_diameter = 0.1
        wall_thickness = 0.01

        model = Model(project_name="CodeAsterCantileverReference")
        model.add_material(
            "Steel",
            E=youngs_modulus,
            nu=0.3,
            rho=7850.0,
            allowable_stress={20.0: 120.0e6},
        )
        model.add_pipe_section("PipeSec", OD=outer_diameter, WT=wall_thickness)
        fixed_node = model.add_node([0.0, 0.0, 0.0])
        loaded_node = model.add_node([length, 0.0, 0.0])
        model.add_element(
            id="pipe_0",
            type="pipe_straight",
            n1=fixed_node,
            n2=loaded_node,
            section="PipeSec",
            material="Steel",
        )
        model.add_support(node=fixed_node, type="anchor", id="support_anchor_0")
        load_case = model.define_load_case(
            "PointLoad",
            gravity=False,
            pressure=0.0,
            temperature=20.0,
            ref_temperature=20.0,
        )
        load_case.add_nodal_force(loaded_node, force=[0.0, 0.0, -force])

        with TemporaryDirectory() as tmpdir:
            run = model.solve(
                load_case="PointLoad",
                work_dir=tmpdir,
                exec_method=os.environ.get("TUBA_CODE_ASTER_EXEC_METHOD", "auto"),
            )

        inner_diameter = outer_diameter - 2.0 * wall_thickness
        second_moment = math.pi * (outer_diameter**4 - inner_diameter**4) / 64.0
        section_modulus = second_moment / (outer_diameter / 2.0)
        expected_tip_displacement = force * length**3 / (3.0 * youngs_modulus * second_moment)
        expected_fixed_moment = force * length
        expected_code_stress = expected_fixed_moment / section_modulus

        self.assertEqual(run.results.solver_name, "Code_Aster")
        displacement = run.results.node_results[loaded_node].displacement
        reaction = run.results.node_results[fixed_node].reaction_force
        # TUYAU_3M includes shear deformation; allow 3% against Euler-Bernoulli.
        self.assertAlmostEqual(
            abs(displacement[2]),
            expected_tip_displacement,
            delta=0.03 * expected_tip_displacement,
        )
        self.assertAlmostEqual(abs(reaction[2]), force, delta=1.0e-3 * force)
        self.assertAlmostEqual(
            abs(reaction[4]),
            expected_fixed_moment,
            delta=1.0e-3 * expected_fixed_moment,
        )

        report = ASMEB313Evaluator(edition="2022").evaluate(model, run.results)
        fixed_end = next(item for item in report.results if item.node_id == fixed_node)
        self.assertAlmostEqual(
            fixed_end.sustained_stress,
            expected_code_stress,
            delta=0.01 * expected_code_stress,
        )
        self.assertAlmostEqual(
            fixed_end.sustained_ratio,
            expected_code_stress / 120.0e6,
            delta=0.01 * expected_code_stress / 120.0e6,
        )


if __name__ == "__main__":
    unittest.main()
