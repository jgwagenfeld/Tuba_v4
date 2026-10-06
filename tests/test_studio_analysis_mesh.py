"""Build publishes only explicit, verified native diagnostic mesh jobs."""
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from tuba.visualization.preview.server import ProjectStudioServer


SCRIPT = '''from tuba import Model
model = Model("Native shell review")
model.add_material("Steel", E=2e11, nu=.3)
model.add_shell_panel("panel", polygon=[[0,0,0],[.1,0,0],[.1,.1,0],[0,.1,0]],
    thickness=.005, material="Steel", mesh_size=.05)
model.set_mesh_size(.025)
model.add_mesh_refinement("corner", target={"kind":"sphere","center_m":[.1,0,0],"radius_m":.015},
    size_m=.015, transition_distance_m=.025)
'''


def wait_job(server):
    deadline = time.monotonic() + 30
    while server.mesh_jobs.busy and time.monotonic() < deadline:
        time.sleep(.05)
    assert not server.mesh_jobs.busy, server.mesh_jobs.status()
    return server.mesh_jobs.status()


def request(server, path="/api/mesh", method="GET", payload=None):
    request = Request(server.base_url.rstrip("/") + path, method=method,
                      data=json.dumps(payload).encode() if payload is not None else None,
                      headers={"Content-Type":"application/json", "Origin":server.base_url.rstrip("/")})
    try:
        response = urlopen(request)
    except HTTPError as failure:
        response = failure
    with response:
        assert response.headers["Content-Type"] == "application/json"
        return response.status, json.load(response)


def test_native_job_http_generation_reuse_force_stale_and_med_validation(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "model.py").write_text(SCRIPT)
    out = tmp_path / "out"
    server = ProjectStudioServer(project, out, port=0, poll_interval_s=60).start()
    try:
        assert server.namespace is not None, server._run_script()[0]
        assert request(server)[1]["state"] == "idle"
        assert not server._current_build_meshes(server.model)
        assert request(server, method="POST", payload={"force": "yes"})[0] == 400
        assert request(server, method="POST", payload={"expected_source_revision": -1})[0] == 409
        _, job = request(server, method="POST", payload={"expected_source_revision": server.revision})
        assert job["state"] == "running"
        assert wait_job(server)["current"], server.mesh_jobs.status()
        assert request(server, method="POST", payload={})[0] == 200
        data = json.loads((out / "build" / "scene.json").read_text())
        assert not data["result_fields"] and not data.get("result_states")
        assert any(obj["kind"] == "shell_panel" or obj["kind"] == "analysis_mesh_surface" for obj in data["objects"])
        identity = next(layer["mesh_identity"] for layer in data["layers"] if layer.get("mesh_identity", {}).get("mesh_review", {}).get("statistics"))
        assert identity["mesh_review"]["statistics"]["by_family"]["TRI3"] > 0
        assert identity["mesh_review"]["quality"]["invalid_count"] == 0
        assert all(not layer["default_visible"] for layer in data["layers"] if layer["category"] == "analysis_mesh")
        directory = Path(job["directory"])
    finally:
        server.stop()

    server = ProjectStudioServer(project, out, port=0, poll_interval_s=60).start()
    try:
        assert server.mesh_jobs.status()["current"]
        # Hashes alone do not prove MED validity: matching corrupt receipts fail readback.
        from tuba.visualization.preview.mesh import digest
        (directory / "mesh.med").write_bytes(b"corrupt MED bytes")
        manifest = json.loads((directory / "manifest.json").read_text())
        manifest["sha256"]["mesh.med"] = digest(directory / "mesh.med")
        (directory / "manifest.json").write_text(json.dumps(manifest))
        assert not request(server)[1]["current"]
        assert not server._current_build_meshes(server.model)
        assert request(server, method="POST", payload={"force":True})[0] == 202
        assert wait_job(server)["current"]
        assert server.execute_python_code(SCRIPT.replace(".025", ".02"))["ok"]
        assert request(server)[1]["state"] == "stale"
        assert not server._current_build_meshes(server.model)
        assert request(server, "/api/mesh/unknown", method="DELETE")[0] == 404
    finally:
        server.stop()


def test_policy_free_step_preview_matches_solver_mesh(tmp_path):
    import hashlib
    import meshio
    from tuba.project import run_model_script
    from tuba.meshing.policy import resolve_mesh_policy
    from tuba.solver.aster import CodeAsterSolver
    from tuba.visualization.preview.mesh import mesh_inputs
    from tuba.visualization.preview.mesh_worker import run

    project = tmp_path / "project"
    project.mkdir()
    (project / "model.py").write_text(
        'from examples.code_aster_step_component_review import build_model\n'
        'model = build_model(mesh_size=.015)\n'
    )
    model = run_model_script(project / "model.py")["model"]
    assert not model.mesh_settings
    old_inputs = {"model": model.to_dict(), "volume_export": None,
                  "policy": resolve_mesh_policy(model).to_dict()}
    old_identity = hashlib.sha256(json.dumps(old_inputs, sort_keys=True, allow_nan=False).encode()).hexdigest()
    assert mesh_inputs(model) != old_identity  # Eight-segment caches must be retired.
    directory = tmp_path / "preview"
    directory.mkdir()
    (directory / "request.json").write_text(json.dumps({
        "inputs": mesh_inputs(model), "identity": "preview", "source_fingerprints": [],
    }))
    run(project, directory)
    study = CodeAsterSolver().export_mixed_analysis_study(model, "Bending", tmp_path / "solve")
    preview = meshio.read(directory / "mesh.med")
    solver = meshio.read(study.input_files["med"])
    assert len(preview.points) == len(solver.points)
    assert {c.type: len(c.data) for c in preview.cells} == {c.type: len(c.data) for c in solver.cells}
    assert sum(len(c.data) for c in preview.cells if c.type == "line3") == 8
