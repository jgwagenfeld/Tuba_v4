"""Friction must not be silently discarded on the way to Code_Aster.

``friction_coefficient`` reaches the solver in exactly one place today: it
flips the analysis to ``STAT_NON_LINE``. No friction law is ever emitted, so a
model that asks for Coulomb friction is solved frictionless, more slowly, and
the result is presented as a friction analysis.

Until the native law is qualified, asking for friction must fail loudly.
"""

from __future__ import annotations

import unittest
from tempfile import TemporaryDirectory

from tuba import Model
from tuba.solver.aster import CodeAsterSolver


def _model_with_rest(friction_coefficient: float = 0.0) -> Model:
    model = Model(project_name="FrictionGuard", standard="ASME_B31.3")
    model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0, alpha=1.2e-5)
    model.add_pipe_section("DN100", OD=0.1143, WT=0.00602)
    model.define_load_case("Operating", gravity=True, pressure=1.0e6, temperature=120.0)
    with model.pipe(section="DN100", material="Steel") as builder:
        builder.start([0.0, 0.0, 0.0], support="anchor")
        builder.run(2.0)
        builder.add_support(type="rest", friction_coefficient=friction_coefficient)
        builder.run(2.0)
        builder.end(support="anchor")
    model.validate()
    return model


class TestFrictionIsNotSilentlyDropped(unittest.TestCase):
    def test_export_analysis_study_rejects_positive_friction(self):
        model = _model_with_rest(0.3)

        with TemporaryDirectory() as tmpdir:
            with self.assertRaises(NotImplementedError) as caught:
                CodeAsterSolver(work_dir=tmpdir).export_analysis_study(model, "Operating", tmpdir)

        message = str(caught.exception)
        self.assertIn("friction", message.lower())
        # Actionable: it must name what to do, not just refuse.
        self.assertIn("friction_coefficient", message)

    def test_export_study_rejects_positive_friction(self):
        model = _model_with_rest(0.3)

        with TemporaryDirectory() as tmpdir:
            with self.assertRaises(NotImplementedError):
                CodeAsterSolver(work_dir=tmpdir).export_study(model, "Operating", tmpdir)

    def test_zero_friction_still_exports(self):
        """The guard must reject the unsupported request, not rest supports."""
        model = _model_with_rest(0.0)

        with TemporaryDirectory() as tmpdir:
            study = CodeAsterSolver(work_dir=tmpdir).export_analysis_study(
                model, "Operating", tmpdir
            )

        self.assertIsNotNone(study.solver_input_identity)


class TestFrictionCoefficientBoundary(unittest.TestCase):
    """A coefficient that is negative or nonfinite is wrong at the boundary."""

    def test_negative_friction_is_rejected(self):
        with self.assertRaises(ValueError):
            _model_with_rest(-0.1)

    def test_nonfinite_friction_is_rejected(self):
        for value in (float("nan"), float("inf")):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    _model_with_rest(value)


if __name__ == "__main__":
    unittest.main()
