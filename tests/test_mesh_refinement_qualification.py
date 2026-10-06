"""Qualification reuse must follow the current study and executed source bytes."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace

import pytest

from tuba.project.study import study_settings

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("mesh_qualifier", ROOT / "scripts" / "qualify_mesh_refinement_review.py")
qualifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(qualifier)


class ReopenReached(RuntimeError):
    """Stop matching reuse at the public artifact verification boundary."""


@pytest.fixture
def authored_study():
    return SimpleNamespace(LOAD_CASES=("Bending",), SOLVER_OPTIONS={"pipe_modelization": "TUYAU_3M"},
                           MESH_CONVERGENCE={"scales": [1., .75], "relative_tolerance": .03})


def saved_inputs(study):
    settings = study_settings(study)
    return json.loads(json.dumps({"load_case": settings.operations[0], "solver_options": settings.solver_options,
                                 "volume_export": settings.volume_export, **settings.mesh_convergence}))


def prepare_reuse(tmp_path, monkeypatch, study, saved):
    comparison = tmp_path / "comparison"
    comparison.mkdir()
    (comparison / "comparison.json").write_text(json.dumps(saved), encoding="utf-8")
    monkeypatch.setattr(qualifier.runpy, "run_path", lambda path: {"model": object()})
    monkeypatch.setattr(qualifier, "load_project", lambda path: SimpleNamespace(load_study=lambda: study))

    def stop_before_artifacts(*args, **kwargs):
        raise ReopenReached("Public reopen reached")

    monkeypatch.setattr(qualifier, "reopen_mesh_convergence", stop_before_artifacts)
    monkeypatch.setattr(qualifier, "run_mesh_convergence", lambda *args, **kwargs: pytest.fail("Reuse started a solve"))
    return comparison


@pytest.mark.parametrize(("field", "attribute", "value"), [
    ("load_case", "LOAD_CASES", ("Other",)),
    ("solver_options", "SOLVER_OPTIONS", {"pipe_modelization": "POU_D_T"}),
    ("scales", "MESH_CONVERGENCE", {"scales": [1., .5], "relative_tolerance": .03}),
    ("relative_tolerance", "MESH_CONVERGENCE", {"scales": [1., .75], "relative_tolerance": .01}),
    ("volume_export", "VOLUME_EXPORT", {"element_ids": ("member",), "element_order": 2}),
])
def test_reuse_rejects_current_study_change_before_reopen(tmp_path, monkeypatch, authored_study, field, attribute, value):
    saved = saved_inputs(authored_study)
    setattr(authored_study, attribute, deepcopy(value))
    comparison = prepare_reuse(tmp_path, monkeypatch, authored_study, saved)
    with pytest.raises(ValueError, match=rf"Stale study.*{field}.*rerun"):
        qualifier.qualify(tmp_path / "output", comparison)


@pytest.mark.parametrize("mode", ["authored", "defaults", "volume"])
def test_matching_study_reuse_reaches_public_verification(tmp_path, monkeypatch, authored_study, mode):
    if mode == "defaults":
        authored_study = SimpleNamespace(LOAD_CASES=("Bending",), MESH_CONVERGENCE={"scales": (1, .75)})
    elif mode == "volume":
        authored_study.SOLVER_OPTIONS = {}
        authored_study.VOLUME_EXPORT = {"element_ids": ("member",), "element_order": 2}
    comparison = prepare_reuse(tmp_path, monkeypatch, authored_study, saved_inputs(authored_study))
    with pytest.raises(ReopenReached):
        qualifier.qualify(tmp_path / "output", comparison)


def test_reuse_rejects_removed_convergence_configuration(tmp_path, monkeypatch, authored_study):
    saved = saved_inputs(authored_study)
    del authored_study.MESH_CONVERGENCE
    comparison = prepare_reuse(tmp_path, monkeypatch, authored_study, saved)
    with pytest.raises(ValueError, match="MESH_CONVERGENCE"):
        qualifier.qualify(tmp_path / "output", comparison)


def test_new_comparison_uses_effective_volume_export(tmp_path, monkeypatch, authored_study):
    authored_study.SOLVER_OPTIONS = {}
    authored_study.VOLUME_EXPORT = {"element_ids": ("member",), "element_order": 2}
    expected = study_settings(authored_study).volume_export
    comparison = prepare_reuse(tmp_path, monkeypatch, authored_study, saved_inputs(authored_study))
    (comparison / "comparison.json").unlink()

    def capture_solve(model, load_case, **kwargs):
        assert kwargs["volume_export"] == expected
        assert kwargs["solver_options"] == {}
        assert load_case == "Bending"
        (comparison / "comparison.json").write_text(json.dumps(saved_inputs(authored_study)), encoding="utf-8")
        return {"status": "completed"}

    monkeypatch.setattr(qualifier, "run_mesh_convergence", capture_solve)
    with pytest.raises(ReopenReached):
        qualifier.qualify(tmp_path / "output", comparison)


def test_source_provenance_includes_staged_unstaged_and_untracked_bytes(tmp_path):
    # Gmsh finalization breaks bare executable lookup on Windows.
    with qualifier.gmsh_model(qualifier.gmsh, "provenance"):
        pass
    git_executable = shutil.which("git") or "git"
    # An isolated repository exercises the real index without touching shared Git.
    def git(*args):
        return subprocess.check_output([git_executable, *args], cwd=tmp_path, text=True).strip()

    git("init", "--quiet")
    git("config", "user.name", "Qualification test")
    git("config", "user.email", "qualification@example.invalid")
    git("config", "core.autocrlf", "false")
    staged = tmp_path / "staged source.py"
    unstaged = tmp_path / "unstaged.py"
    staged.write_bytes(b"before staged\n")
    unstaged.write_bytes(b"before unstaged\n")
    git("add", "--", staged.name, unstaged.name)
    git("-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "Fixture baseline")
    head = git("rev-parse", "HEAD")
    staged.write_bytes(b"staged edit\n")
    git("add", "--", staged.name)
    unstaged.write_bytes(b"unstaged edit\n")
    untracked = tmp_path / "untracked.py"
    untracked.write_bytes(b"untracked source\n")
    provenance = qualifier.source_provenance(tmp_path)
    assert provenance["source_head"] == head
    assert provenance["changed_source_sha256"] == {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (staged, unstaged, untracked)
    }
