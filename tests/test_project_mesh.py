"""Headless jobs use native cells and retain failures without solved-result claims."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import tuba.mcp.server as server
from tuba.project import load_project
from tuba.project.claim import claim_solve, solve_claimed
from tuba.project.mesh import main, run_project_mesh
from tuba.project.package import export_project_package, unpack_project_package

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "mesh-refinement-review"
SCRIPT = '''from tuba import Model
model = Model("Headless")
model.add_material("Steel", E=2e11, nu=.3)
model.add_pipe_section("Pipe", OD=.1, WT=.01)
with model.pipe(section="Pipe", material="Steel") as pipe:
    pipe.start([0,0,0], support="anchor").run(.2)
model.define_load_case("Load", gravity=False)
model.set_mesh_size(.025)
model.add_mesh_refinement("detail", target="element:pipe_str_0", size_m=.0125)
'''


def project(tmp_path, *, convergence=False):
    root = tmp_path / "project"
    root.mkdir()
    (root / "model.py").write_text(SCRIPT, encoding="utf-8")
    if convergence:
        (root / "study.py").write_text('LOAD_CASES = ("Load",)\nMESH_CONVERGENCE = {"scales": [1., .5]}\n')
    return root


@pytest.mark.parametrize("suffix", [".tubaproject", ".tgz"])
def test_shipped_step_project_opens_after_archive_move(tmp_path, suffix):
    archive = tmp_path / ("example" + suffix)
    manifest = export_project_package(EXAMPLE, archive)
    assert "geometry/spool.step" in [item["path"] for item in manifest["files"]]
    opened = unpack_project_package(archive, tmp_path / "moved")
    model = load_project(opened).run_model()["model"]
    assert model.ports["spool_outlet"].position == pytest.approx([.2, 0, 0])
    if suffix == ".tgz":
        result = run_project_mesh(opened, tmp_path / "mesh")
        directory = Path(result["directory"])
        assert result["result_status"] == "mesh_only"
        assert (directory / "mesh.med").is_file()
        assert result["mesh_review"]["quality"]["invalid_count"] == 0
        assert not (opened / "evidence").exists()
        assert not solve_claimed(opened)


def test_documented_recipe_uses_normalized_mm_selectors(tmp_path):
    from tests.test_code_aster_step_component_reference import build_step_reference
    build_step_reference(tmp_path / "cad", mesh_size=.008, unit_scale_to_m=.001)
    root = tmp_path / "documented"
    (root / "geometry").mkdir(parents=True)
    (root / "geometry" / "spool.step").write_bytes((tmp_path / "cad" / "annulus.step").read_bytes())
    guide = (EXAMPLE.parents[1] / "docs" / "content" / "step-meshing.md").read_text(encoding="utf-8")
    (root / "model.py").write_text(guide.split("```python\n", 1)[1].split("```", 1)[0], encoding="utf-8")
    model = load_project(root).run_model()["model"]
    assert model.ports["spool_outlet"].position == pytest.approx([.2, 0, 0])
    assert model.nodes[model.elements[0].n2].coords == pytest.approx([1.2, 0, 0])
    assert model.verify().passed


def test_cli_and_mcp_use_the_same_native_job_and_inspection(tmp_path, capsys):
    root = project(tmp_path)
    original = (root / "model.py").read_bytes()
    assert main(["mesh", str(root), "--output", str(tmp_path / "cli")]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["result_status"] == "mesh_only"
    assert (Path(result["directory"]) / "mesh.mail").is_file()
    server.init_session(file_path=str(root / "model.py"), load_existing=True)
    inspection = server.inspect_model()
    assert inspection["mesh_settings"] == {"global_size_m": .025}
    assert inspection["mesh_refinements"]["detail"]["size_m"] == .0125
    assert "mesh_groups" in inspection
    result = server.generate_mesh(str(tmp_path / "mcp"))
    assert result["result_status"] == "mesh_only"
    assert (root / "model.py").read_bytes() == original
    assert not (root / "evidence").exists()


def test_package_inspection_neither_executes_source_nor_changes_session(tmp_path):
    root = tmp_path / "unbound"
    root.mkdir()
    (root / "model.py").write_text("raise RuntimeError('must not execute')\n")
    archive = tmp_path / "source.tgz"
    export_project_package(root, archive)
    active = server._ACTIVE_PATH
    assert server.inspect_project_package(str(archive))["include_results"] is False
    assert server._ACTIVE_PATH == active


def test_existing_outputs_and_project_claims_are_preserved(tmp_path):
    root = project(tmp_path)
    destination = tmp_path / "owned"
    destination.mkdir()
    marker = destination / "keep"
    marker.write_text("keep")
    with pytest.raises(FileExistsError):
        run_project_mesh(root, destination)
    assert marker.read_text() == "keep"
    with claim_solve(root):
        with pytest.raises(RuntimeError, match="already being solved"):
            run_project_mesh(root, tmp_path / "busy")
    assert not (tmp_path / "busy").exists()


@pytest.mark.parametrize("convergence", [False, True])
def test_convergence_config_and_runtime_block_before_output(tmp_path, monkeypatch, convergence):
    root = project(tmp_path, convergence=convergence)
    monkeypatch.setattr("tuba.solver.code_aster_process.convergence_capability",
                        lambda: {"supported": False, "reason": "test runtime unavailable"})
    with pytest.raises(ValueError, match="runtime unavailable" if convergence else "MESH_CONVERGENCE"):
        run_project_mesh(root, tmp_path / "blocked", mode="convergence")
    assert not (tmp_path / "blocked").exists()


def test_convergence_clash_gate_blocks_before_output(tmp_path):
    root = project(tmp_path, convergence=True)
    with (root / "model.py").open("a") as stream:
        stream.write('model.add_obstacle("blocked", "cuboid", min_point=[.05,-.1,-.1], max_point=[.15,.1,.1])\n')
    with pytest.raises(ValueError, match="verification failed"):
        run_project_mesh(root, tmp_path / "blocked", mode="convergence")
    assert not (tmp_path / "blocked").exists()


def test_source_change_during_worker_blocks_publication(tmp_path, monkeypatch):
    root = project(tmp_path)
    def launch(*args):
        def wait():
            with (root / "model.py").open("a") as stream:
                stream.write("\n# outside edit\n")
            return 0
        return SimpleNamespace(wait=wait, poll=lambda: 0)
    monkeypatch.setattr("tuba.project.mesh.launch_mesh_worker", launch)
    with pytest.raises(ValueError, match="source changed"):
        run_project_mesh(root, tmp_path / "stale")
    saved = json.loads(next((tmp_path / "stale").glob("*/job.json")).read_text())
    assert saved["state"] == "failed"
    assert not solve_claimed(root)


def test_worker_failure_retains_diagnostics_and_releases_the_slot(tmp_path, monkeypatch):
    root = project(tmp_path)
    def launch(project_root, directory):
        (directory / "status.json").write_text('{"error": "test mesher failure"}')
        return SimpleNamespace(wait=lambda: 1, poll=lambda: 1)
    monkeypatch.setattr("tuba.project.mesh.launch_mesh_worker", launch)
    with pytest.raises(RuntimeError, match="test mesher failure"):
        run_project_mesh(root, tmp_path / "failed")
    saved = json.loads(next((tmp_path / "failed").glob("*/job.json")).read_text())
    assert saved["state"] == "failed"
    assert not solve_claimed(root)


def test_unverified_cleanup_keeps_the_durable_claim(tmp_path, monkeypatch):
    from tuba.project.claim import cleanup_claim
    from tuba.solver.code_aster_process import ExecutionController
    root = project(tmp_path, convergence=True)
    monkeypatch.setattr("tuba.solver.code_aster_process.convergence_capability",
                        lambda *args: {"supported": True})
    monkeypatch.setattr("tuba.project.mesh.launch_mesh_worker",
                        lambda *args: SimpleNamespace(wait=lambda: 0, poll=lambda: 0))
    monkeypatch.setattr("tuba.analysis.mesh_convergence.reopen_mesh_convergence",
                        lambda *args: {"fixture": "portable lifecycle replay, no solver results"})
    def failed_cleanup(self):
        raise RuntimeError("test cleanup not verified")
    monkeypatch.setattr(ExecutionController, "cleanup", failed_cleanup)
    with pytest.raises(RuntimeError, match="cleanup not verified"):
        run_project_mesh(root, tmp_path / "cleanup", mode="convergence")
    saved = json.loads(next((tmp_path / "cleanup").glob("*/job.json")).read_text())
    assert saved["state"] == "failed" and saved["cleanup_pending"]
    assert solve_claimed(root)
    assert cleanup_claim(root)["cleanup_obligation"]["directory"] == saved["directory"]
