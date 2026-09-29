"""Reference solve: a buckling factor checked against a closed form.

Gated behind ``TUBA_RUN_CODE_ASTER_INTEGRATION=1`` like every other reference in
this repository. A buckling feature that merely runs proves nothing, so this pins
the number to the fixed-free Euler load; the un-gated tests cover emission,
parsing and the refusals.
"""

import math
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tuba.model import BucklingOptions
from tuba.solver.aster import CodeAsterSolver

LENGTH = 6.0
SIDE = 0.1
WALL = 0.025
MODULUS = 2.0e11
REFERENCE_LOAD = 100_000.0


def _euler_fixed_free():
    """pi^2 E I / (4 L^2) for the hollow box this fixture builds."""
    inertia = (SIDE**4 - (SIDE - 2 * WALL) ** 4) / 12.0
    return math.pi**2 * MODULUS * inertia / (4 * LENGTH**2)


@unittest.skipUnless(
    os.environ.get("TUBA_RUN_CODE_ASTER_INTEGRATION") == "1",
    "set TUBA_RUN_CODE_ASTER_INTEGRATION=1 to run the real Code_Aster buckling reference",
)
class TestCodeAsterBucklingReference(unittest.TestCase):
    def test_critical_factor_matches_the_euler_load(self):
        from tuba import Model

        model = Model("Column")
        model.add_material(
            "S355", E=MODULUS, nu=0.3, rho=7850.0, alpha=1.2e-5
        )
        model.add_rectangular_section(
            "SQUARE", height_y=SIDE, height_z=SIDE,
            thickness_y=WALL, thickness_z=WALL,
        )
        with model.pipe(section="SQUARE", material="S355") as b:
            b.start([0.0, 0.0, 0.0], support="anchor")
            b.set_direction([0.0, 0.0, 1.0])
            b.beam(LENGTH)
            tip = b.last_node_id
        operation = model.define_operation("Ref", gravity=False)
        operation.add_nodal_force(node=tip, force=[0.0, 0.0, -REFERENCE_LOAD])
        operation.buckling = BucklingOptions(n_modes=2, modal_subspace=8)
        model.validate()

        expected = _euler_fixed_free() / REFERENCE_LOAD
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            solver = CodeAsterSolver(work_dir=root, line_segments=1)
            study = solver.export_analysis_study(model, "Ref", root)
            run = solver.solve_exported_study(model, study)

            buckling = run.result_state.buckling
            self.assertIsNotNone(buckling, "a buckling study must produce a buckling result")
            self.assertTrue(buckling.critical_factors)
            governing = buckling.governing_factor
            # One element with a Timoshenko section is not the textbook continuum
            # problem, so allow a small discretisation difference; 5% is generous
            # for this case and still far tighter than any wiring error could be.
            self.assertAlmostEqual(
                governing, expected, delta=abs(expected) * 0.05,
                msg=f"critical factor {governing} does not match the closed form {expected}",
            )

            # The static result must survive alongside the eigenproblem: the
            # buckling factors are built from this same solve's prestress.
            self.assertEqual(len(run.result_state.node_displacements), 2)
            self.assertIn("beam_0", run.result_state.element_results)
            self.assertGreater(governing, 0.0)

    def test_a_plain_study_reports_no_buckling_at_all(self):
        from tuba import Model

        model = Model("Column")
        model.add_material("S355", E=MODULUS, nu=0.3, rho=7850.0, alpha=1.2e-5)
        model.add_rectangular_section(
            "SQUARE", height_y=SIDE, height_z=SIDE,
            thickness_y=WALL, thickness_z=WALL,
        )
        with model.pipe(section="SQUARE", material="S355") as b:
            b.start([0.0, 0.0, 0.0], support="anchor")
            b.set_direction([0.0, 0.0, 1.0])
            b.beam(LENGTH)
        model.define_operation("Plain", gravity=True)
        model.validate()

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            solver = CodeAsterSolver(work_dir=root, line_segments=1)
            study = solver.export_analysis_study(model, "Plain", root)
            run = solver.solve_exported_study(model, study)
            # Absent, not an empty result: "did not ask" is not "did not buckle".
            self.assertIsNone(run.result_state.buckling)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
