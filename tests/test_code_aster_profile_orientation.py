"""The committed artifacts were solved by Code_Aster; fixtures are never solver evidence."""
from pathlib import Path

import numpy as np
import pytest

from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts
from tuba.project import load_project

_PROJECT = load_project(Path(__file__).resolve().parents[1] / "examples" / "profile-orientation-review")
_STUDY = _PROJECT.load_study()
_NAMESPACE = _PROJECT.run_model()
CASES, ROLLS = _STUDY.LOAD_CASES, _NAMESPACE["ROLLS"]


def build_model():
    return _PROJECT.run_model()["model"]


def check_solved_response(model, runs):
    return _STUDY.check_solved_response(model, runs, rolls=ROLLS, length=_NAMESPACE["LENGTH"])
from tuba.analysis.staged_run import stage_runs


def test_every_tip_carries_the_same_force_in_global_axes():
    forces = [force.components[:3] for force in build_model().load_cases["global"].nodal_forces]
    np.testing.assert_allclose(forces, np.tile([0, 0, -500], (len(ROLLS), 1)), atol=1e-9)


def test_disconnected_cantilevers_and_solved_orientation():
    model = build_model()
    roots = Path(__file__).resolve().parents[1] / "examples/profile-orientation-review/evidence"
    assert len(model.elements) == 36
    node_sets = [{n for e in model.elements if e.id.startswith(f"roll{roll}_") for n in (e.n1,e.n2)} for roll in ROLLS]
    assert all(len(nodes) == 13 for nodes in node_sets)
    assert len(set.union(*node_sets)) == 39
    runs = [import_code_aster_artifacts(model=model,work_dir=roots/case) for case in CASES]
    assert len({run.study.id for run in runs}) == 1
    assert len({run.analysis_mesh.id for run in runs}) == 1
    assert len(check_solved_response(model,runs)) == 3


def test_an_operation_name_cannot_escape_the_bundle(tmp_path):
    for unsafe in ("", ".", "../outside", str(tmp_path.parent)):
        with pytest.raises(ValueError, match="cannot name"):
            stage_runs({unsafe: None}, tmp_path)
