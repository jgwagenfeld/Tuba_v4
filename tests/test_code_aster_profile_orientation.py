"""The committed artifacts were solved by Code_Aster; fixtures are never solver evidence."""
from pathlib import Path
import math

import numpy as np
import pytest

from tuba.project import load_project

_PROJECT = load_project(Path(__file__).resolve().parents[1] / "examples" / "profile-orientation-review")
_STUDY = _PROJECT.load_study()
_NAMESPACE = _PROJECT.run_model()
CASES, ROLLS = _STUDY.LOAD_CASES, _NAMESPACE["ROLLS"]


def build_model():
    return _PROJECT.run_model()["model"]


def check_solved_response(model, runs):
    return _STUDY.check_solved_response(model, runs, rolls=ROLLS, length=_NAMESPACE["LENGTH"])
from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts, stage_code_aster_artifact_evidence
from tuba.geometry.section_mesh import beam_local_frame
from tuba.analysis.provenance import build_solver_input_identity


def test_local_force_identity_ignores_libm_last_bit(monkeypatch):
    identity = build_solver_input_identity(build_model(), "local")
    sine = math.sin
    monkeypatch.setattr(math, "sin", lambda angle: math.nextafter(sine(angle), 0.0))
    assert build_solver_input_identity(build_model(), "local") == identity


def test_disconnected_cantilevers_and_solved_orientation():
    model = build_model()
    roots = Path(__file__).resolve().parents[1] / "examples/profile-orientation-review/evidence"
    assert len(model.elements) == 36
    node_sets = [{n for e in model.elements if e.id.startswith(f"roll{roll}_") for n in (e.n1,e.n2)} for roll in ROLLS]
    assert all(len(nodes) == 13 for nodes in node_sets)
    assert len(set.union(*node_sets)) == 39
    for force, roll in zip(model.load_cases["local"].nodal_forces, ROLLS):
        basis = np.asarray(beam_local_frame([0,0,0],[1,0,0],twist_angle_deg=roll))
        np.testing.assert_allclose(basis @ force.components[:3], [0,0,-500], atol=1e-9)
    runs = [import_code_aster_artifacts(model=model,work_dir=roots/case) for case in CASES]
    assert len({run.study.id for run in runs}) == 2
    assert len({run.analysis_mesh.id for run in runs}) == 2
    assert len(check_solved_response(model,runs)) == 6


def test_artifact_subdirectory_cannot_escape_bundle(tmp_path):
    for unsafe in ("", ".", "../outside", str(tmp_path.parent)):
        with pytest.raises(ValueError, match="within the review bundle"):
            stage_code_aster_artifact_evidence(None,tmp_path,artifact_subdir=unsafe)
