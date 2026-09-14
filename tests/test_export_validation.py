import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tuba import Model
from tuba.solver.aster import CodeAsterSolver
from tuba.validation import ModelValidationError


class TestCodeAsterExportValidation(unittest.TestCase):
    def test_export_study_validates_before_writing_files(self):
        model = _model_with_missing_section()

        with TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            with self.assertRaisesRegex(ModelValidationError, "missing section"):
                CodeAsterSolver(work_dir=out_dir).export_study(model, "Hot", out_dir)

            self.assertFalse((out_dir / "study.mail").exists())
            self.assertFalse((out_dir / "study.comm").exists())
            self.assertFalse((out_dir / "study.export").exists())

    def test_export_analysis_study_validates_before_writing_files(self):
        model = _model_with_missing_material()

        with TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            with self.assertRaisesRegex(ModelValidationError, "missing material"):
                CodeAsterSolver(work_dir=out_dir).export_analysis_study(model, "Hot", out_dir)

            self.assertFalse((out_dir / "study.mail").exists())
            self.assertFalse((out_dir / "study.comm").exists())
            self.assertFalse((out_dir / "study.export").exists())
            self.assertFalse((out_dir / "study_manifest.json").exists())


def _model_with_missing_section() -> Model:
    model = Model(project_name="MissingSection")
    model.add_material("Steel", E=2.0e11, nu=0.3)
    n0 = model.add_node((0.0, 0.0, 0.0))
    n1 = model.add_node((1.0, 0.0, 0.0))
    model.add_element(
        id="pipe_str_0",
        type="pipe_straight",
        n1=n0,
        n2=n1,
        section="MissingSection",
        material="Steel",
    )
    model.define_load_case("Hot")
    return model


def _model_with_missing_material() -> Model:
    model = Model(project_name="MissingMaterial")
    model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
    n0 = model.add_node((0.0, 0.0, 0.0))
    n1 = model.add_node((1.0, 0.0, 0.0))
    model.add_element(
        id="pipe_str_0",
        type="pipe_straight",
        n1=n0,
        n2=n1,
        section="PipeSec",
        material="MissingMaterial",
    )
    model.define_load_case("Hot")
    return model


if __name__ == "__main__":
    unittest.main()
