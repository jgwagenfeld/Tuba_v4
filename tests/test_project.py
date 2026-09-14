import subprocess
import sys
from pathlib import Path

import pytest

from tuba.project import load_project, run_model_script

MODEL = """from tuba import Model

model = Model("ProjectDemo")
model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0, alpha=1.2e-5)
"""


def _project(tmp_path: Path, model: str, study: str | None = None) -> Path:
    (tmp_path / "model.py").write_text(model, encoding="utf-8")
    if study is not None:
        (tmp_path / "study.py").write_text(study, encoding="utf-8")
    return tmp_path


def test_a_project_runs_its_model_and_reads_its_study(tmp_path):
    study = 'LOAD_CASES = ("Operating",)\n\ndef build_review(namespace, output, *, artifact_dir=None, force=False):\n    return namespace["model"].project_name\n'
    project = load_project(_project(tmp_path, MODEL, study))

    namespace = project.run_model()
    loaded = project.load_study()

    assert namespace["model"].project_name == "ProjectDemo"
    assert loaded.LOAD_CASES == ("Operating",)
    # Study functions keep their own globals after loading.
    assert loaded.build_review(namespace, tmp_path) == "ProjectDemo"


def test_build_model_counts_as_the_model_and_a_missing_one_is_refused(tmp_path):
    wrapped = MODEL.replace('model = Model("ProjectDemo")', 'def build_model():\n    return Model("Wrapped")\n\nmodel = None')
    wrapped = wrapped.replace('model.add_material', '# model.add_material')
    assert run_model_script(_project(tmp_path, wrapped) / "model.py")["model"].project_name == "Wrapped"

    (tmp_path / "model.py").write_text("x = 1\n", encoding="utf-8")
    with pytest.raises(TypeError, match="must bind 'model'"):
        run_model_script(tmp_path / "model.py")


def test_a_folder_without_model_py_is_not_a_project(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_project(tmp_path)
    assert load_project(_project(tmp_path, MODEL)).load_study() is None


def test_the_project_command_runs_as_a_module():
    completed = subprocess.run(
        [sys.executable, "-m", "tuba.project", "--help"], capture_output=True, text=True, check=False
    )
    assert completed.returncode == 0, completed.stderr
    assert "--artifact-dir" in completed.stdout
