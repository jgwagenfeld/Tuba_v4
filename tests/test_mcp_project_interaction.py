"""MCP uses the same fresh, folder-bound project study as CLI and Studio."""

import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess

import pytest

from tests.project_replay import ReplaySolver
from tuba.mcp import server
from tuba.project.claim import claim_solve
from tuba.solver.aster import CodeAsterSolver


EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
RACK = EXAMPLES / "support-rack-review"


@pytest.mark.parametrize("tool", [server.inspect_model, server.verify_model, server.check_clashes])
def test_reads_rebuild_external_python_and_helpers_without_acknowledging_writes(tmp_path, tool):
    helper = tmp_path / "helper.py"
    helper.write_text("NAME = 'First'\n", encoding="utf-8")
    script = tmp_path / "model.py"
    script.write_text("from tuba import Model\nfrom helper import NAME\nmodel = Model(NAME)\n", encoding="utf-8")
    server.init_session(file_path=str(script))
    original_guard = server._SCRIPT_TEXT
    helper.write_text("NAME = 'Second'\n", encoding="utf-8")
    tool()
    assert server.get_active_model().project_name == "Second"
    assert server._SCRIPT_TEXT == original_guard
    with pytest.raises(RuntimeError, match="helper.py changed elsewhere"):
        server.add_material("Steel", E=2.1e11, nu=.3)
    script.write_text(script.read_text(encoding="utf-8") + "\nmodel.project_name = 'Third'\n", encoding="utf-8")
    tool()
    assert server.get_active_model().project_name == "Third"
    assert server._SCRIPT_TEXT == original_guard


def test_imported_reference_is_reloaded_after_external_asset_edit(tmp_path):
    asset = tmp_path / "reference.stl"
    shutil.copyfile(EXAMPLES / "imported-geometry-studio" / "geometry" / "reference.stl", asset)
    script = tmp_path / "model.py"
    script.write_text(
        "from pathlib import Path\nfrom tuba import Model\nmodel = Model('Reference')\n"
        "model.import_stl(Path(__file__).parent / 'reference.stl', id='reference', unit_scale_to_m=.001)\n",
        encoding="utf-8",
    )
    server.init_session(file_path=str(script))
    before = server.inspect_model()["cad_assets"]["reference_asset"]["content_digest"]
    asset.write_bytes(asset.read_bytes() + b"\n")
    after = server.inspect_model()["cad_assets"]["reference_asset"]["content_digest"]
    assert before != after
    assert after.removeprefix("sha256:") == hashlib.sha256(asset.read_bytes()).hexdigest()
    with pytest.raises(RuntimeError, match="reference.stl changed elsewhere"):
        server.add_material("Steel", E=2.1e11, nu=.3)


def test_invalid_external_source_refuses_stale_solve(tmp_path, monkeypatch):
    script = tmp_path / "model.py"
    script.write_text("from tuba import Model\nmodel = Model('Previous')\n", encoding="utf-8")
    server.init_session(file_path=str(script))
    previous = server.get_active_model()
    script.write_text("raise RuntimeError('changed source is invalid')\n", encoding="utf-8")
    monkeypatch.setattr(CodeAsterSolver, "solve_exported_study", lambda *_: pytest.fail("must not solve the old model"))
    response = server.solve_model(force=True)
    assert response["status"] == "error"
    assert response["message"] == "changed source is invalid"
    assert server.get_active_model() is previous


def test_failed_unit_rebuild_never_rolls_back_over_an_outside_edit(tmp_path, monkeypatch):
    script = tmp_path / "model.py"
    server.init_session(file_path=str(script), load_existing=False)
    edited = []

    def failed_rebuild(path):
        edited.append(path.read_text(encoding="utf-8") + "\n# outside edit during the rebuild\n")
        path.write_text(edited[-1], encoding="utf-8")
        raise RuntimeError("rebuild failed")

    monkeypatch.setattr(server, "run_model_script", failed_rebuild)
    with pytest.raises(RuntimeError, match="not rolled back over the outside edit"):
        server.save_unit("posts", 'def posts(model):\n    """Build an empty unit."""\n', func="posts", where="model")
    assert script.read_text(encoding="utf-8") == edited[-1]


@pytest.mark.parametrize('where', ['units', 'model'])
def test_units_and_snippets_use_current_project_helpers(tmp_path, where):
    code = ('from dimensions import HEIGHT\n'
            'def build(model, x):\n'
            '    """Build a post at x using the project height."""\n'
            '    model.add_node([x, 0, HEIGHT])\n')
    for height in (1, 2):
        root = tmp_path / str(height)
        root.mkdir()
        (root / "dimensions.py").write_text(f"HEIGHT = {height}\n")
        script = root / "model.py"
        server.init_session(file_path=str(script), load_existing=False)
        saved = server.save_unit('posts', code, params={'x': 0}, where=where)
        assert saved['status'] == 'saved'
        assert server.apply_unit(saved['ref'], {'x': 0})['status'] == 'success'
        assert server.run_model_code("from dimensions import HEIGHT\nmodel.add_node([1, 0, HEIGHT])")['status'] == 'success'
        model = server.get_active_model()
        assert [node.coords[2] for node in model.nodes.values()] == [height, height]
        assert f"assemble(model, {saved['ref']!r}, x=0)" in script.read_text()


def _rack_project(tmp_path):
    for filename in ("model.py", "study.py"):
        shutil.copyfile(RACK / filename, tmp_path / filename)
    study = tmp_path / "study.py"
    study.write_text(
        study.read_text(encoding="utf-8")
        + "\ndef check(solved):\n"
        "    assert solved.runs['Operating'].result_state.metadata['result_trust'] == 'verified'\n"
        "    assert solved.namespace['model'] is solved.model\n"
        "    (Path(solved.namespace['__file__']).parent / 'check.json').write_text('true')\n",
        encoding="utf-8",
    )
    server.init_session(file_path=str(tmp_path / "model.py"))


def test_project_solve_promotes_real_evidence_runs_study_hook_and_reuses_it(tmp_path, monkeypatch):
    _rack_project(tmp_path)
    replay = ReplaySolver(RACK / "evidence")
    monkeypatch.setattr(CodeAsterSolver, "solve_exported_study", lambda _self, model, study: replay.solve_exported_study(model, study))
    solved = server.solve_model(load_case="Operating")
    assert solved["status"] == "success", solved
    assert (solved["solved"], solved["reused"], solved["unverified"]) == (["Operating"], [], [])
    assert solved["results_available"] is True
    assert json.loads((tmp_path / "check.json").read_text()) is True
    artifacts = solved["artifacts"]["Operating"]
    assert artifacts["work_dir"] == str((tmp_path / "evidence" / "Operating").resolve())
    assert artifacts["result_trust"] == "verified"
    assert all(Path(path).is_file() for path in artifacts["files"].values())
    assert Path(artifacts["execution_attestation"]).is_file()
    assert artifacts["solver_input_identity"]["fingerprint"]
    reused = server.solve_model()
    assert (reused["solved"], reused["reused"], replay.solved) == ([], ["Operating"], ["Operating"])
    forced = server.solve_model(force=True)
    assert (forced["solved"], forced["reused"], replay.solved) == (["Operating"], [], ["Operating", "Operating"])


def test_changed_study_options_invalidate_evidence_and_failed_solve_preserves_it(tmp_path, monkeypatch):
    _rack_project(tmp_path)
    replay = ReplaySolver(RACK / "evidence")
    monkeypatch.setattr(CodeAsterSolver, "solve_exported_study", lambda _self, model, study: replay.solve_exported_study(model, study))
    assert server.solve_model()["status"] == "success"
    evidence = tmp_path / "evidence" / "Operating"
    before = {path.name: path.read_bytes() for path in evidence.iterdir() if path.is_file()}
    study = tmp_path / "study.py"
    study.write_text(study.read_text(encoding="utf-8").replace("SOLVER_OPTIONS: dict = {}", "SOLVER_OPTIONS = {'line_segments': 4}"), encoding="utf-8")
    response = server.solve_model()
    assert response["status"] == "error"
    assert "No committed evidence" in response["message"]
    assert {path.name: path.read_bytes() for path in evidence.iterdir() if path.is_file()} == before


def test_shared_project_solve_claim_blocks_overlapping_agent_solve(tmp_path):
    _rack_project(tmp_path)
    with claim_solve(tmp_path):
        response = server.solve_model()
    assert response["status"] == "error"
    assert response["error_type"] == "SolveBusy"
    assert not (tmp_path / "evidence").exists()


def test_unverified_real_artifacts_are_returned_without_claiming_engineering_results(tmp_path, monkeypatch):
    _rack_project(tmp_path)
    study = tmp_path / "study.py"
    study.write_text(study.read_text(encoding="utf-8").replace("== 'verified'", "in ('verified', 'unverified')"), encoding="utf-8")
    replay = ReplaySolver(RACK / "evidence", execution_method="docker")
    monkeypatch.setattr(CodeAsterSolver, "solve_exported_study", lambda _self, model, exported: replay.solve_exported_study(model, exported))
    response = server.solve_model()
    assert response["status"] == "success", response
    assert response["unverified"] == ["Operating"]
    assert response["results_available"] is False
    assert Path(response["artifacts"]["Operating"]["execution_attestation"]).is_file()


def test_studio_endpoint_matches_explicit_project_binding_and_quotes_spaces(tmp_path, monkeypatch):
    from tuba.project import session

    folder = tmp_path / "Project with spaces"
    folder.mkdir()
    running = folder / "different-project"
    seen = []

    def active(root):
        seen.append(root)
        if root == running:
            return {"base_url": "http://127.0.0.1:9876/", "viewer_url": "http://127.0.0.1:9876/?bundle=build"}
        return None

    monkeypatch.setattr(session, "studio_session", active)
    response = server.init_session(file_path=str(folder / "model.py"), load_existing=False)
    hint = response["studio"]
    assert hint["running"] is False and hint["viewer_url"] is None
    command = ["python", "-m", "tuba.cli_studio", str(folder)]
    assert hint["cmd"] == (subprocess.list2cmdline(command) if os.name == "nt" else shlex.join(command))
    assert server.inspect_model()["project_root"] == str(folder)
    assert seen == [folder, folder]
    monkeypatch.setattr(session, "studio_session", lambda root: {
        "base_url": "http://127.0.0.1:9877/", "viewer_url": "http://127.0.0.1:9877/?bundle=build",
    } if root == folder else None)
    assert server.inspect_model()["studio"]["viewer_url"] == "http://127.0.0.1:9877/?bundle=build"
