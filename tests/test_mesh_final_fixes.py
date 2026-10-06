"""Focused integration regressions; controlled lifecycle cases are not solver evidence."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from tests.test_studio_mesh_jobs import studio, complete, convergence_settings, SCRIPT


@pytest.mark.parametrize("authored", [False, True])
@pytest.mark.parametrize("formulation", ["POU_D_T", "TUYAU_3M"])
def test_diagnostic_matches_effective_study_compiler(studio, authored, formulation):
    from tuba.solver.aster_mesh import generate_analysis_mesh
    from tuba.visualization.preview.mesh import read_native_line_mail
    server, process = studio
    if not authored:
        server.project.model_path.write_text(SCRIPT.replace("model.set_mesh_size(.025)\n", ""))
    (server.project.root / "study.py").write_text(
        f'SOLVER_OPTIONS={{"pipe_modelization":"{formulation}","line_segments":4}}\n')
    assert server._run_script()[0]["ok"]
    expected_path = server.out_dir / "expected.mail"
    expected = generate_analysis_mesh(server.model, pipe_modelization=formulation,
                                     line_segments=4, mail_path=expected_path)
    _, job = server.mesh_jobs.start()
    complete(server, process)
    actual = server.mesh_jobs.current_meshes()[0]
    assert actual.modelisations == expected.modelisations
    assert read_native_line_mail(Path(job["directory"]) / "mesh.mail") == read_native_line_mail(expected_path)


def test_native_bridge_controller_selected_and_unsupported_preflight(tmp_path, monkeypatch):
    from tuba.solver import code_aster_process as owned
    from tuba.solver.code_aster_runtime import CodeAsterRuntimeConfig
    monkeypatch.setattr(owned, "native_process_supported", lambda: True)
    config = CodeAsterRuntimeConfig(exec_method="auto", bridge_python="conda-python", env={})
    capability = owned.convergence_capability(config)
    assert capability["supported"] and capability["runtime"] == "python_bridge"
    assert owned.ExecutionController(tmp_path, config).capability == capability
    docker = CodeAsterRuntimeConfig(exec_method="docker", env={})
    assert not owned.convergence_capability(docker)["supported"]
    with pytest.raises(ValueError, match="Docker"):
        owned.ExecutionController(tmp_path, docker)


def test_dispatch_routes_configured_candidate_and_failed_aggregate_is_not_verified(tmp_path, monkeypatch):
    from tuba.solver import code_aster_process as owned
    from tuba.solver.code_aster_runtime import CodeAsterRuntimeCandidate, CodeAsterRuntimeConfig
    config = CodeAsterRuntimeConfig(exec_method="wsl", wsl_distro="Ubuntu", env={})
    controller = owned.ExecutionController(tmp_path, config)
    monkeypatch.setattr(owned, "native_process_supported", lambda: True)
    calls=[]
    monkeypatch.setattr(owned.NativeExecutionController, "execute", lambda self,*args: calls.append("native"))
    monkeypatch.setattr(owned.WslExecutionController, "execute", lambda self,*args: calls.append("wsl"))
    controller.execute(CodeAsterRuntimeCandidate("python_bridge",("python",)), [], tmp_path, 1, tmp_path)
    controller.execute(CodeAsterRuntimeCandidate("command",("run_aster",)), [], tmp_path, 1, tmp_path)
    controller.execute(CodeAsterRuntimeCandidate("wsl",("wsl","-d","Ubuntu","--")), [], None, 1, tmp_path)
    assert calls == ["native","native","wsl"]
    (tmp_path / "native-owned").mkdir()
    def refuse(self): raise RuntimeError("native scan unavailable")
    monkeypatch.setattr(owned.NativeExecutionController,"cleanup",refuse)
    with pytest.raises(RuntimeError,match="native scan unavailable"):
        controller.cancel()
    assert not json.loads((tmp_path / "cleanup.json").read_text())["verified"]


def test_cleanup_uses_durable_runtime_after_invalid_environment_change(tmp_path, monkeypatch):
    from tuba.solver import code_aster_process as owned
    monkeypatch.setenv("TUBA_CODE_ASTER_EXEC_METHOD", "invalid")
    assert not owned.convergence_capability()["supported"]
    assert owned.ExecutionController(tmp_path, cleanup_only=True).cancel() == []


def test_unsupported_runtime_rejected_before_launch(studio, monkeypatch):
    server, _ = studio
    convergence_settings(server)
    monkeypatch.setenv("TUBA_CODE_ASTER_EXEC_METHOD", "docker")
    code, result = server.mesh_jobs.start(mode="convergence")
    assert code == 422 and "Docker" in result["error"]
    assert not server.mesh_jobs.root.exists()
    assert not server.mesh_jobs.status()["convergence_capability"]["supported"]


def test_cleanup_failure_survives_exit_reopening_and_cross_process_claim(studio, monkeypatch):
    from tuba.solver import code_aster_process as owned
    from tuba.project.claim import claim_solve, solve_claimed, SolveBusy
    from tuba.visualization.preview.mesh import MeshJobManager
    server, process = studio
    convergence_settings(server)
    def refuse(self):
        raise RuntimeError("Ownership scan unavailable; descendants unverified")
    monkeypatch.setattr(owned.WslExecutionController, "cleanup", refuse)
    _, job = server.mesh_jobs.start(mode="convergence")
    server.mesh_jobs.cancel(job["id"])
    process.returncode = -1
    server.mesh_jobs._complete(job["id"], process)
    assert server.mesh_jobs.status()["cleanup_pending"]
    assert server.mesh_jobs.busy and solve_claimed(server.project.root, stale_after_s=-1)
    with pytest.raises(SolveBusy):
        with claim_solve(server.project.root, stale_after_s=-1):
            pass
    claimant = subprocess.run([sys.executable, "-c",
        'import sys; from tuba.project.claim import claim_solve, SolveBusy\n'
        'try:\n with claim_solve(sys.argv[1], stale_after_s=-1): pass\n'
        'except SolveBusy: sys.exit(3)', str(server.project.root)], capture_output=True, text=True)
    assert claimant.returncode == 3, claimant.stderr
    old_manager = server.mesh_jobs
    old_manager.close()  # stops heartbeat like owner death; durable obligation must remain
    server.mesh_jobs = MeshJobManager(server)
    assert server.mesh_jobs.status()["id"] == job["id"]
    assert server.mesh_jobs.start()[0] == 409
    assert server.mesh_jobs.cancel("different-job")[0] == 404
    assert server.mesh_jobs.cancel(job["id"])[1]["cleanup_pending"]
    monkeypatch.setattr(owned.WslExecutionController, "cleanup", lambda self: [])
    released = server.mesh_jobs.cancel(job["id"])[1]
    assert not released["cleanup_pending"] and not released["busy"]
    assert not solve_claimed(server.project.root)
    with claim_solve(server.project.root):
        pass


def test_owner_death_durable_claim_and_worker_exit_barrier(studio, monkeypatch):
    from tuba.visualization.preview.mesh import MeshJobManager, atomic_json
    from tuba.project.claim import solve_claimed
    from tuba.solver import code_aster_process as owned
    server, _ = studio
    job_id = "d" * 32
    directory = server.mesh_jobs.root / job_id
    obligation = {"job_id":job_id, "directory":str(directory.resolve())}
    command = 'import os,sys,json; from tuba.project.claim import claim_solve\n' \
        'claim=claim_solve(sys.argv[1],cleanup_obligation=json.loads(sys.argv[2])); claim.__enter__(); os._exit(0)'
    dead_owner = subprocess.run([sys.executable, "-c", command, str(server.project.root), json.dumps(obligation)],
                               capture_output=True, text=True)
    assert dead_owner.returncode == 0, dead_owner.stderr
    assert solve_claimed(server.project.root, stale_after_s=-1)
    identity = owned.worker_process_identity(os.getpid())
    atomic_json(directory / "worker.json", {"schema":"tuba.mesh-worker.v1", "job_id":job_id,
        "project_root":str(server.project.root.resolve()), **identity})
    server.mesh_jobs = MeshJobManager(server)
    monkeypatch.setattr(owned.WslExecutionController, "cleanup", lambda self: [])
    assert server.mesh_jobs.cancel(job_id)[1]["cleanup_pending"]  # actual live worker identity
    assert solve_claimed(server.project.root, stale_after_s=-1)
    monkeypatch.setattr(owned, "worker_process_identity", lambda pid: None)
    assert not server.mesh_jobs.cancel(job_id)[1]["cleanup_pending"]
    assert not solve_claimed(server.project.root)


def test_cleanup_claim_release_requires_nonce_and_exact_named_obligation(tmp_path):
    from tuba.project.claim import claim_solve, release_cleanup_claim, solve_claimed, SolveBusy
    obligation={"job_id":"a"*32,"directory":str(tmp_path / "job")}
    with claim_solve(tmp_path,cleanup_obligation=obligation) as token:
        pass  # portable verified-cleanup seam only, no solver processes
    for nonce, expected in (("wrong",obligation),(token,{**obligation,"job_id":"b"*32})):
        with pytest.raises(SolveBusy,match="identity changed"):
            release_cleanup_claim(tmp_path,token=nonce,obligation=expected)
        assert solve_claimed(tmp_path,stale_after_s=-1)
    release_cleanup_claim(tmp_path,token=token,obligation=obligation)
    assert not solve_claimed(tmp_path)


@pytest.mark.parametrize("volume", [False, True])
def test_comparison_only_scene_has_effective_sizing_preview(studio, monkeypatch, volume):
    from tuba.geometry.volume import build_volume_geometry
    from tuba.meshing.policy import resolve_mesh_policy
    server, _ = studio
    server.project.model_path.write_text(SCRIPT.replace("b.run(.2)","b.run(1.)").replace("model.set_mesh_size(.025)","model.set_mesh_size(.1)"))
    assert server._run_script()[0]["ok"]
    if volume:
        elements = [element.id for element in server.model.elements]
        (server.project.root / "study.py").write_text(
            f'VOLUME_EXPORT={{"element_ids":{elements!r},"max_element_size":.005}}\n')
        server.study = server.project.load_study()
    monkeypatch.setattr(server.mesh_jobs, "current_comparison", lambda: {"levels":[],"status":"completed"})
    server._publish_scene(advance_revision=False)
    scene = json.loads((server.out_dir / "build" / "scene.json").read_text())
    reviews = [layer["mesh_identity"]["mesh_review"] for layer in scene["layers"] if layer.get("mesh_identity")]
    comparison = next(review for review in reviews if review.get("comparison"))
    effective = resolve_mesh_policy(server.model, max_element_size=.005 if volume else None,
        volume_geometry=build_volume_geometry(server.model, elements) if volume else None)
    assert comparison["policy"] == effective.to_dict()
    assert comparison["size_preview"]["sample_count"] > 0
    assert comparison["size_preview"] == effective.preview()
