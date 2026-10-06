"""Explicit diagnostic workers must never promote stale or corrupt meshes."""
import json
from pathlib import Path

import pytest

from tuba.visualization.preview.server import ProjectStudioServer


SCRIPT = '''from tuba import Model
model = Model("Mesh job")
model.add_material("Steel", E=2e11, nu=.3)
model.add_pipe_section("Pipe", OD=.1, WT=.01)
with model.pipe(section="Pipe", material="Steel") as b:
    b.start([0, 0, 0])
    b.run(.2)
model.set_mesh_size(.025)
'''


class Process:
    returncode = None
    terminated = False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True


@pytest.fixture
def studio(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    (root / "model.py").write_text(SCRIPT)
    server = ProjectStudioServer(root, tmp_path / "out", port=0)
    result, _ = server._run_script()
    assert result["ok"], result
    process = Process()
    monkeypatch.setattr(server.mesh_jobs, "_launch", lambda *args: process)
    monkeypatch.setattr(server.mesh_jobs, "_monitor", lambda *args: None)
    yield server, process
    if server.mesh_jobs.busy:
        server.mesh_jobs.close()
        process.returncode = -1
        server.mesh_jobs._complete(server.mesh_jobs._job["id"], process)


def complete(server, process):
    from tuba.visualization.preview.mesh_worker import run

    job = server.mesh_jobs._job
    run(server.project.root, Path(job["directory"]))
    process.returncode = 0
    server.mesh_jobs._complete(job["id"], process)


@pytest.mark.parametrize("shell", [False, True])
@pytest.mark.parametrize("corrupt", [False, True])
def test_worker_receipt_has_one_independent_host_import(studio, monkeypatch, shell, corrupt):
    from tuba.analysis.mesh import AnalysisMesh
    from tuba.visualization.preview.mesh_worker import run

    server, process = studio
    if shell:
        server.project.model_path.write_text(SCRIPT + '''model.add_shell_panel("panel",
    polygon=[[0,0,0],[.2,0,0],[.2,.2,0],[0,.2,0]], thickness=.005, material="Steel", mesh_size=.05)
''')
        assert server._run_script()[0]["ok"]
    imports = []
    original = AnalysisMesh.from_dict
    def hydrate(cls, data):
        imports.append(data)
        return original(data)
    monkeypatch.setattr(AnalysisMesh, "from_dict", classmethod(hydrate))
    _, job = server.mesh_jobs.start()
    directory = Path(job["directory"])
    run(server.project.root, directory)
    assert not imports  # generation does not rehydrate the just-written mesh
    assert not (directory / "mesh.mesh.json").exists()
    if corrupt:
        with (directory / "analysis_mesh.json").open("a") as stream:
            stream.write(" ")  # still valid JSON, but different receipt bytes
    process.returncode = 0
    server.mesh_jobs._complete(job["id"], process)
    status = server.mesh_jobs.status()
    assert status["current"] is (not corrupt)
    assert status["state"] == ("failed" if corrupt else "succeeded")
    assert len(imports) == (0 if corrupt else 1)
    if not corrupt:
        assert "mesh_manifest" not in server.mesh_jobs.current_meshes()[0].files


@pytest.mark.parametrize("publication_fails", [False, True])
def test_completion_time_includes_verified_import_and_scene_publication(studio, monkeypatch, publication_fails):
    import tuba.visualization.preview.mesh as mesh
    from tuba.project.claim import solve_claimed

    server, process = studio
    clock = [1000.]
    monkeypatch.setattr(mesh.time, "monotonic", lambda: clock[0])
    _, job = server.mesh_jobs.start()
    validate = server.mesh_jobs._validate_current
    publish = server._publish_scene
    imported = []
    def verified_import(*args):
        if not imported:
            clock[0] += 3.
            imported.append(True)
        return validate(*args)
    def publication(**kwargs):
        clock[0] += 7.
        if publication_fails:
            raise OSError("Scene output unavailable")
        return publish(**kwargs)
    monkeypatch.setattr(server.mesh_jobs, "_validate_current", verified_import)
    monkeypatch.setattr(server, "_publish_scene", publication)
    clock[0] += 20.
    complete(server, process)
    status = server.mesh_jobs.status()
    receipt = json.loads((Path(job["directory"]) / "job.json").read_text())
    assert status["elapsed_seconds"] == receipt["elapsed_seconds"] == 30.
    assert status["state"] == ("failed" if publication_fails else "succeeded")
    assert status["current"] is (not publication_fails)
    assert not solve_claimed(server.project.root)
    if publication_fails:
        assert "Mesh scene publication failed" in status["error"]
    clock[0] += 1000.
    server.mesh_jobs._retain_report()
    assert json.loads((Path(job["directory"]) / "job.json").read_text())["elapsed_seconds"] == 30.


def test_source_change_rejects_completed_mesh_publication(studio):
    server, process = studio
    assert server.mesh_jobs.start(expected_source_revision=server.revision)[0] == 202
    from tuba.visualization.preview.mesh_worker import run
    run(server.project.root, Path(server.mesh_jobs._job["directory"]))
    complete_source = server.revision
    (server.project.model_path).write_text(SCRIPT.replace(".025", ".02"))
    assert server._run_script()[0]["ok"]
    assert server.revision > complete_source
    process.returncode = 0
    server.mesh_jobs._complete(server.mesh_jobs._job["id"], process)
    status = server.mesh_jobs.status()
    assert status["state"] == "stale"
    assert not status["current"]
    assert not server._current_build_meshes(server.model)


def test_named_cancel_blocks_late_completion_and_busy_slot(studio):
    server, process = studio
    _, job = server.mesh_jobs.start(expected_source_revision=server.revision)
    assert server.mesh_jobs.start()[0] == 409
    assert server.mesh_jobs.cancel("another-job")[0] == 404
    assert not process.terminated
    assert server.mesh_jobs.cancel(job["id"])[0] == 200
    assert process.terminated
    report = Path(job["directory"]) / "job.json"
    assert json.loads(report.read_text())["state"] == "cancelled"
    assert server.mesh_jobs.start()[0] == 409  # until the child actually exits
    complete(server, process)
    assert server.mesh_jobs.status()["state"] == "cancelled"
    assert json.loads(report.read_text())["state"] == "cancelled"
    assert not server.mesh_jobs.status()["current"]


def test_reuse_force_and_failed_remesh(studio):
    server, process = studio
    _, job = server.mesh_jobs.start()
    complete(server, process)
    assert server.mesh_jobs.status()["current"]
    assert server.mesh_jobs.start()[0] == 200
    assert server.mesh_jobs.start(force=True)[0] == 202
    assert not server.mesh_jobs.status()["current"]
    process.returncode = 1
    server.mesh_jobs._complete(server.mesh_jobs._job["id"], process)
    assert server.mesh_jobs.status()["state"] == "failed"
    assert not server._current_build_meshes(server.model)


def test_policy_change_without_reload_and_source_error_fail_closed(studio):
    server, process = studio
    assert server.mesh_jobs.start(expected_source_revision=server.revision - 1)[0] == 409
    server.mesh_jobs.start()
    complete(server, process)
    server.model.set_mesh_size(.01)
    assert server.mesh_jobs.status()["state"] == "stale"
    assert not server.mesh_jobs.status()["current"]
    (server.project.model_path).write_text("invalid Python !")
    assert not server._run_script()[0]["ok"]
    assert server.mesh_jobs.start()[0] == 422
    assert not server.mesh_jobs.status()["current"]


def test_solve_flags_and_external_claim_protect_mesh_slot(studio, monkeypatch):
    server, _ = studio
    server._solving = True
    assert server.mesh_jobs.start()[0] == 409
    server._solving = False
    monkeypatch.setattr("tuba.project.claim.solve_claimed", lambda root: True)
    assert server.mesh_jobs.start()[0] == 409


def test_mesh_holds_cross_process_claim_until_cancelled_child_exits(studio):
    from tuba.project.claim import claim_solve, solve_claimed, SolveBusy
    server, process = studio
    _, job = server.mesh_jobs.start()
    assert solve_claimed(server.project.root)
    assert not server.project_info()["solving"]  # mesh-only ownership is not a Code_Aster solve
    with pytest.raises(SolveBusy):
        with claim_solve(server.project.root):
            pytest.fail("external solve entered a meshing project")
    server.mesh_jobs.cancel(job["id"])
    assert solve_claimed(server.project.root)
    process.returncode = -1
    server.mesh_jobs._complete(job["id"], process)
    assert not solve_claimed(server.project.root)


def test_cache_manifest_is_checked(studio):
    server, process = studio
    server.mesh_jobs.start()
    complete(server, process)
    manifest = Path(server.mesh_jobs._job["directory"]) / "manifest.json"
    manifest.write_text(json.dumps({"schema": "unexpected"}))
    assert not server.mesh_jobs.status()["current"]
    assert server.mesh_jobs.status()["state"] == "failed"
    scene = json.loads((server.out_dir / "build" / "scene.json").read_text())
    assert not any(obj["kind"].startswith("analysis_mesh_") for obj in scene["objects"])


@pytest.mark.parametrize("filename", ["mesh.mail", "analysis_mesh.json"])
def test_verified_mesh_cache_skips_hydration_but_rechecks_bytes(studio, monkeypatch, filename):
    import os
    from tuba.analysis.mesh import AnalysisMesh

    server, process = studio
    server.mesh_jobs.start()
    complete(server, process)
    current = server.mesh_jobs.current_meshes()[0]
    hydrated = []
    original = AnalysisMesh.from_dict

    def hydrate(cls, data):
        hydrated.append(data)
        return original(data)

    monkeypatch.setattr(AnalysisMesh, "from_dict", classmethod(hydrate))
    for _ in range(3):
        assert server.mesh_jobs.status()["mesh_current"]
        assert server.mesh_jobs.current_meshes()[0] is current
    assert not hydrated

    path = Path(server.mesh_jobs._job["directory"]) / filename
    before = path.stat()
    data = path.read_bytes()
    path.write_bytes(data[:-1] + (b" " if data[-1:] != b" " else b"\n"))
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert path.stat().st_size == before.st_size
    assert not server.mesh_jobs.status()["current"]
    assert server.mesh_jobs.status()["state"] == "failed"
    assert not server.mesh_jobs.current_meshes()


def convergence_settings(server):
    (server.project.root / "study.py").write_text('LOAD_CASES=("load",)\nMESH_CONVERGENCE={"scales":[1.,.5]}\n')
    server.project.model_path.write_text(SCRIPT+'model.define_load_case("load",gravity=False)\n')
    assert server._run_script()[0]["ok"]


def test_convergence_uses_single_slot_and_survives_worker_death_and_shutdown(studio, monkeypatch):
    from tuba.solver.code_aster_process import WslExecutionController
    from tuba.project.claim import solve_claimed
    server, process = studio
    assert server.mesh_jobs.start(mode="convergence")[0] == 422
    convergence_settings(server)
    cleaned=[]
    monkeypatch.setattr(WslExecutionController,"cleanup",lambda self:cleaned.append(str(self.directory)) or [])
    _,job=server.mesh_jobs.start(mode="convergence")
    assert job["mode"] == "convergence"
    assert server.mesh_jobs.start()[0] == 409
    process.returncode=1
    server.mesh_jobs._complete(job["id"],process)
    assert cleaned and not solve_claimed(server.project.root)
    assert server.mesh_jobs.status()["state"] == "failed"
    process.returncode=None
    _,job=server.mesh_jobs.start(mode="convergence")
    server.mesh_jobs.close()
    assert process.terminated
    assert (Path(job["directory"])/"cancelled.json").is_file()
    assert solve_claimed(server.project.root)
    assert server.mesh_jobs.cancel(job["id"])[0] == 200
    process.returncode=0
    server.mesh_jobs._complete(job["id"],process)
    assert server.mesh_jobs.status()["state"] == "cancelled"
    assert not server.mesh_jobs.status()["current"]
    assert not solve_claimed(server.project.root)


def test_mesh_and_convergence_receipts_survive_switching_modes_and_reopen(studio,monkeypatch):
    from tuba.visualization.preview.mesh import MeshJobManager,atomic_json
    server, process=studio
    convergence_settings(server)
    server.mesh_jobs.start()
    complete(server,process)
    mesh_directory=server.mesh_jobs._job["directory"]
    assert server.mesh_jobs.current_meshes()
    comparison={"schema":"tuba.mesh-convergence.v1","status":"completed","levels":[],
                "distinct_successful_meshes":2,"all_available_changes_within_tolerance":False}
    native_validate=MeshJobManager._validate_current
    def validate(self,job,identity):
        if job.get("mode")=="convergence":
            return comparison # Explicit portable comparison replay only.
        return native_validate(self,job,identity)
    monkeypatch.setattr(MeshJobManager,"_validate_current",validate)
    process.returncode=None
    _,job=server.mesh_jobs.start(mode="convergence")
    assert server.mesh_jobs.current_meshes() # independent mesh, same physics/source
    atomic_json(Path(job["directory"])/"status.json",{"stage":"complete"})
    process.returncode=0
    server.mesh_jobs._complete(job["id"],process)
    assert server.mesh_jobs.current_comparison()==comparison
    assert server.mesh_jobs.current_meshes()[0].files==server.mesh_jobs._artifact_for_mode("mesh").files
    process.returncode=None
    server.mesh_jobs.start(force=True)
    assert server.mesh_jobs.current_comparison()==comparison
    complete(server,process)
    assert server.mesh_jobs.status()["comparison_current"]
    assert server.mesh_jobs.current_meshes()
    server.mesh_jobs=MeshJobManager(server)
    assert server.mesh_jobs.current_meshes()
    assert server.mesh_jobs.current_comparison()==comparison
    server.project.model_path.write_text(SCRIPT+'model.define_load_case("load",gravity=False)\nmodel.set_mesh_size(.01)\n')
    assert server._run_script()[0]["ok"]
    assert not server.mesh_jobs.current_meshes()
    assert server.mesh_jobs.current_comparison() is None


@pytest.mark.parametrize("secondary_mode",["convergence","mesh"])
def test_secondary_artifact_corruption_republishes_scene_once(studio,monkeypatch,secondary_mode):
    from tests.test_mesh_convergence import portable_execution_fixture
    server,process=studio
    convergence_settings(server)
    portable_execution_fixture(monkeypatch)
    latest_mode="mesh" if secondary_mode=="convergence" else "convergence"
    for mode in (secondary_mode,latest_mode):
        process.returncode=None
        assert server.mesh_jobs.start(mode=mode)[0]==202
        complete(server,process)
    scene_path=server.out_dir / "build" / "scene.json"
    def has_comparison():
        return any(layer.get("mesh_identity",{}).get("mesh_review",{}).get("comparison") for layer in json.loads(scene_path.read_text())["layers"])
    def has_mesh():
        return any(obj["kind"].startswith("analysis_mesh_") for obj in json.loads(scene_path.read_text())["objects"])
    assert has_comparison() and has_mesh()
    artifact=server.mesh_jobs._artifacts[secondary_mode]
    filename="level-00/study.mail" if secondary_mode=="convergence" else "mesh.mail"
    corrupted=Path(artifact["directory"]) / filename
    corrupted.write_bytes(corrupted.read_bytes()+b"corrupt retained secondary artifact")
    calls=[]
    publish=server._publish_scene
    def republish(**kwargs):
        calls.append(kwargs)
        return publish(**kwargs)
    monkeypatch.setattr(server,"_publish_scene",republish)
    status=server.mesh_jobs.status()
    assert status["current"] and status["state"]=="succeeded"
    assert status[f"{secondary_mode if secondary_mode=='mesh' else 'comparison'}_current"] is False
    assert status[f"{latest_mode if latest_mode=='mesh' else 'comparison'}_current"] is True
    assert len(calls)==1
    assert has_comparison()==(latest_mode=="convergence")
    assert has_mesh()==(latest_mode=="mesh")
    server.mesh_jobs.status()
    assert len(calls)==1 # subsequent polls do not republish the same retirement


def test_cad_bytes_change_without_python_edit_blocks_reuse_and_late_publication(studio):
    server, process = studio
    cad = server.project.root / "reference.step"
    cad.write_bytes(b"authored CAD reference bytes")
    code = SCRIPT + '\nmodel.add_cad_asset(id="reference", source_path="reference.step")\n'
    server.project.model_path.write_text(code)
    assert server._run_script()[0]["ok"]
    server.mesh_jobs.start()
    from tuba.visualization.preview.mesh_worker import run
    run(server.project.root, Path(server.mesh_jobs._job["directory"]))
    revision = server.revision
    cad.write_bytes(b"changed CAD reference bytes")
    assert server.project.model_path.read_text() == code
    assert server.mesh_jobs.start()[0] == 409  # active slot still owns the project
    process.returncode = 0
    server.mesh_jobs._complete(server.mesh_jobs._job["id"], process)
    assert server.revision == revision  # no Python/watcher reload is needed to reject it
    assert server.mesh_jobs.status()["state"] == "stale"
    assert not server.mesh_jobs.status()["current"]
    assert server.mesh_jobs.start()[0] == 422
    assert server._run_script()[0]["ok"]
    server.mesh_jobs.start()
    complete(server, process)
    assert server.mesh_jobs.status()["current"]
    cad.write_bytes(b"changed again after mesh publication")
    assert not server.mesh_jobs.status()["current"]


def test_mail_readback_rejects_matching_hash_with_missing_connectivity(studio):
    from tuba.visualization.preview.mesh import digest
    server, process = studio
    server.mesh_jobs.start()
    complete(server, process)
    directory = Path(server.mesh_jobs._job["directory"])
    path = directory / "mesh.mail"
    text = path.read_text()
    start = text.index("SEG3\n") + len("SEG3\n")
    end = text.index("\n", start)
    parts = text[start:end].split()
    parts[1] = "missing_node"
    path.write_text(text[:start] + "  ".join(parts) + text[end:])
    manifest = json.loads((directory / "manifest.json").read_text())
    manifest["sha256"]["mesh.mail"] = digest(path)
    (directory / "manifest.json").write_text(json.dumps(manifest))
    restarted = ProjectStudioServer(server.project.root, server.out_dir, port=0)
    assert restarted._run_script()[0]["ok"]
    assert restarted.mesh_jobs.status()["state"] == "failed"
    assert not restarted.mesh_jobs.status()["current"]
    assert server.mesh_jobs.status()["state"] == "failed"
    assert not server.mesh_jobs.status()["current"]


def test_setup_failure_releases_project_claim(studio, monkeypatch):
    from tuba.project.claim import solve_claimed
    server, _ = studio
    def unavailable(*args):
        raise OSError("Diagnostic output directory is unavailable")
    monkeypatch.setattr("tuba.visualization.preview.mesh.atomic_json", unavailable)
    status, response = server.mesh_jobs.start()
    assert status == 500
    assert not response["current"]
    assert not solve_claimed(server.project.root)


def test_ifc_request_takes_script_lock_before_publication_lock(studio, monkeypatch):
    server, _ = studio
    class PublicationLock:
        def __enter__(self):
            assert server._script_lock._is_owned(), "IFC publication must not invert script -> IFC lock order"
        def __exit__(self, *args):
            pass
    monkeypatch.setattr(server, "_ifc_lock", PublicationLock())
    monkeypatch.setattr(server, "_ifc_request_locked", lambda *args: (200, {"ok":True}))
    assert server.ifc_request("preview")[0] == 200


def test_cancel_terminates_and_rejects_late_completion_when_cleanup_io_fails(studio, monkeypatch):
    from tuba.project.claim import solve_claimed
    from tuba.visualization.preview.mesh import atomic_json
    server, process = studio
    _, job = server.mesh_jobs.start()
    def unavailable(path, record):
        if Path(path).name in {"current.json", "job.json"}:
            raise OSError(f"Cannot write {Path(path).name}")
        return atomic_json(path, record)
    with monkeypatch.context() as patcher:
        patcher.setattr("tuba.visualization.preview.mesh.atomic_json", unavailable)
        code, cancelled = server.mesh_jobs.cancel(job["id"])
        assert code == 200
        assert process.terminated
        assert cancelled["state"] == "cancelled" and not cancelled["current"]
        assert "current.json" in cancelled["pointer_error"]
        assert "job.json" in cancelled["report_error"]
        assert cancelled["busy"] and solve_claimed(server.project.root)
        assert server.mesh_jobs.start()[0] == 409
        complete(server, process)  # a successful child completion cannot revive it
        assert server.mesh_jobs.status()["state"] == "cancelled"
        assert not server.mesh_jobs.status()["current"]
        assert not server.mesh_jobs.busy and not solve_claimed(server.project.root)
        assert not server._current_build_meshes(server.model)


@pytest.mark.parametrize("mixed_linear_beam", [False, True])
def test_policy_free_review_matches_actual_mail_topology_without_changing_legacy_records(studio, mixed_linear_beam):
    from collections import Counter
    from tuba.analysis.mesh import AnalysisMesh
    from tuba.solver.aster_mesh import generate_analysis_mesh
    server, process = studio
    code = SCRIPT.replace("model.set_mesh_size(.025)\n", "")
    if mixed_linear_beam:
        code += '''model.add_rectangular_section("Frame", height_y=.1, height_z=.1)
a, b = model.add_node([0,.2,0]), model.add_node([.2,.2,0])
model.add_element(id="frame", type="beam", n1=a, n2=b, section="Frame", material="Steel")
'''
    server.project.model_path.write_text(code)
    assert server._run_script()[0]["ok"]
    legacy = generate_analysis_mesh(server.model)
    assert all(len(cell) == 2 for cell in legacy.elements.values())
    _, job = server.mesh_jobs.start()
    complete(server, process)
    directory = Path(job["directory"])
    published = AnalysisMesh.from_dict(json.loads((directory / "analysis_mesh.json").read_text()))
    before, after = legacy.to_dict(), published.to_dict()
    after.pop("mesh_review")
    before.pop("files", None)
    after.pop("files", None)
    assert after == before  # historical records/identity remain authoritative and unchanged
    counts, node_count, block = Counter(), 0, None
    for raw in (directory / "mesh.mail").read_text().splitlines():
        line = raw.strip()
        if line in {"COOR_3D", "SEG2", "SEG3"}:
            block = line
        elif line == "FINSF":
            block = None
        elif line and block == "COOR_3D":
            node_count += 1
        elif line and block in {"SEG2", "SEG3"}:
            counts[block] += 1
    review = published.mesh_review
    assert counts["SEG3"] > 0
    assert bool(counts["SEG2"]) == mixed_linear_beam
    assert review["statistics"]["by_family"] == counts
    assert review["statistics"]["node_count"] == node_count
    assert review["statistics"]["cell_count"] == sum(counts.values())
    assert {metric["applicable_family"] for metric in review["quality"]["metrics"]} == set(counts)


def test_worker_runs_where_the_host_ran_model_py(tmp_path, monkeypatch):
    # A cwd-relative CAD path resolved by the host must resolve the same way in the worker.
    import tuba.visualization.preview.mesh as mesh

    monkeypatch.chdir(tmp_path)
    root = tmp_path / "project"
    root.mkdir()
    (root / "model.py").write_text(SCRIPT)
    server = ProjectStudioServer(root, tmp_path / "out", port=0)
    seen = {}
    monkeypatch.setattr(mesh.subprocess, "Popen", lambda *args, **kwargs: seen.update(kwargs))
    (tmp_path / "job").mkdir()
    server.mesh_jobs._launch(tmp_path / "job")
    assert Path(seen["cwd"]) == tmp_path
