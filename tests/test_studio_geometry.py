"""Actual reference upload, Python preservation and project dependency reload."""

import ast
import hashlib
import json
import struct
import threading
import time
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

import pytest

from tuba.visualization.preview.server import ProjectStudioServer


MODEL = "from tuba import Model\nmodel=Model('Geometry project')\n"


def binary_triangle(x=1):
    # A binary STL whose header begins with solid must still use its binary count.
    return b"solid actual binary".ljust(80, b" ") + struct.pack("<I", 1) + struct.pack(
        "<12fH", 0, 0, 1, 0, 0, 0, x, 0, 0, 0, 1, 0, 0,
    )


@pytest.fixture
def server(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "model.py").write_text(MODEL)
    instance = ProjectStudioServer(project, tmp_path / "out", port=0, poll_interval_s=.03, debounce_s=.02)
    instance.start()
    try:
        yield instance
    finally:
        instance.stop()


def upload(server, route="preview", body=None, name="A triangle's.stl", options=None, headers=None):
    headers = {"Authorization": "Bearer " + server.access_token, "Content-Type": "application/octet-stream", "X-Geometry-Name": quote(name, safe=""),
               "X-Geometry-Options": json.dumps(options if options is not None else {
                   "id": "reference", "unit_scale_to_m": .001,
                   "placement": {"origin": [2,3,4], "rotation": [1,0,0,0]},
               }), **(headers or {})}
    request = Request(server.base_url + "api/geometry/" + route, data=binary_triangle() if body is None else body, headers=headers)
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read())
    except HTTPError as error:
        return error.code, json.loads(error.read())


def test_preview_and_immutable_store_return_actual_geometry_and_quoted_python_without_authoring(server):
    before = server.script_path.read_bytes()
    status, preview = upload(server)
    assert status == 200 and preview["role"] == "reference"
    assert preview["metadata"]["inspection"]["triangle_count"] == 1
    assert preview["bounds_m"] == pytest.approx([2,3,4,2.001,3.001,4])
    assert preview["ports"] == [] and preview["diagnostics"]
    assert "path" not in preview and not (server.project.root / "geometry").exists()
    status, stored = upload(server, "store")
    assert status == 200
    assert stored["path"] == f"geometry/{hashlib.sha256(binary_triangle()).hexdigest()}.stl"
    assert (server.project.root / stored["path"]).read_bytes() == binary_triangle()
    ast.parse(stored["python"])
    assert "from pathlib import Path" in stored["python"]
    assert upload(server, "store")[1]["path"] == stored["path"]
    assert server.script_path.read_bytes() == before
    assert not server.model.imported_components and not server.model.analysis_regions
    with urlopen(Request(server.base_url + "api/project", headers={"Authorization": "Bearer " + server.access_token})) as response:
        assert json.loads(response.read())["geometry"]["max_upload_bytes"] == 16 * 1024 * 1024


@pytest.mark.parametrize("options", [{"id":"safe"}, {"id":"safe","unit_scale_to_m":True},
                                      {"id":"safe","unit_scale_to_m":0}, {"id":"x'); evil()","unit_scale_to_m":1},
                                      {"id":"safe","unit_scale_to_m":1,"placement":{"origin":[0,0,float('inf')]}}])
def test_upload_rejects_invalid_explicit_options(server, options):
    status, result = upload(server, options=options)
    assert status == 400 and not result["ok"]
    assert not (server.project.root / "geometry").exists()


@pytest.mark.parametrize("name", ["../bad.stl", r"C:\bad.stl", "bad.py", "folder/bad.step"])
def test_upload_rejects_paths_and_non_geometry_names(server, name):
    assert upload(server, name=name)[0] == 400


def test_upload_origin_limits_and_malformed_geometry_fail_before_store(server):
    assert upload(server, "store", headers={"Origin":"http://evil.example"})[0] == 403
    assert upload(server, headers={"Content-Length":str(16*1024*1024+1)})[0] == 413
    assert upload(server, headers={"Content-Type":"text/plain"})[0] == 400
    assert upload(server, "store", body=b"invalid STL")[0] == 422
    assert not (server.project.root / "geometry").exists()


def test_preview_store_reuses_inspection_and_storage_quota_precedes_parsing(server, monkeypatch):
    assert upload(server)[0] == 200
    monkeypatch.setattr("tuba.geometry.stl_reference.inspect_stl_reference", lambda _: pytest.fail("preview must not be reparsed"))
    assert upload(server, "store")[0] == 200
    monkeypatch.setattr("tuba.visualization.preview.geometry.MAX_STORED_GEOMETRIES", 1)
    status, result = upload(server, "store", body=binary_triangle(2))
    assert status == 422 and "stored geometry exceeds" in result["error"]


def wait_for(predicate):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.03)
    raise AssertionError("Studio did not reload the changed project dependency")


def test_watcher_reloads_local_helpers_and_keeps_last_good_model_after_error(server):
    helper = server.project.root / "dimensions.py"
    helper.write_text("NAME='First'\n")
    server.execute_python_code("from tuba import Model\nfrom dimensions import NAME\nmodel=Model(NAME)\n")
    helper.write_text("NAME='Second'\n")
    wait_for(lambda: server.model.project_name == "Second")
    wait_for(lambda: json.loads((server.out_dir / "build" / "scene.json").read_text())["scene_id"] == "scene:Second")
    old_scene = (server.out_dir / "build" / "scene.json").read_bytes()
    helper.write_text("raise ValueError('broken dependency')\n")
    wait_for(lambda: server._source_error)
    assert server.model.project_name == "Second"
    assert (server.out_dir / "build" / "scene.json").read_bytes() == old_scene
    assert not server.project_info()["can_solve"]
    assert server.start_solve()[0] == 400
    assert server.code_aster_commands("Operating")[0] == 422
    helper.write_text("NAME='Fixed'\n")
    wait_for(lambda: server.model.project_name == "Fixed" and not server._source_error)


def test_watcher_reimports_changed_reference_and_marks_review_stale(server):
    source = server.project.root / "part.stl"
    source.write_bytes(binary_triangle())
    code = ("from pathlib import Path\nfrom tuba import Model\nmodel=Model('Asset')\n"
            "model.import_stl(Path(__file__).resolve().parent/'part.stl', id='part', unit_scale_to_m=1)\n")
    assert server.execute_python_code(code)["ok"]
    first = server.model.cad_assets["part_asset"].content_digest
    review = server.out_dir / "review"
    review.mkdir()
    (review / "scene.json").write_text("{}")
    source.write_bytes(binary_triangle(2))
    wait_for(lambda: server.model.cad_assets["part_asset"].content_digest != first)
    assert server.model.cad_assets["part_asset"].metadata["local_bounds"][3] == 2
    source.write_bytes(b"corrupt geometry")
    wait_for(lambda: server._source_error)
    assert server.project_info()["review_stale"]
    assert server.script_path.read_text() == code


def test_asset_edit_during_scene_publication_is_not_acknowledged_as_loaded(server, monkeypatch):
    source = server.project.root / "part.stl"
    source.write_bytes(binary_triangle())
    original = server._publish_scene
    edited = False

    def publish():
        nonlocal edited
        if not edited:
            edited = True
            source.write_bytes(binary_triangle(2))
        return original()

    monkeypatch.setattr(server, "_publish_scene", publish)
    code = ("from pathlib import Path\nfrom tuba import Model\nmodel=Model('Asset')\n"
            "model.import_stl(Path(__file__).resolve().parent/'part.stl', id='part', unit_scale_to_m=1)\n")
    assert server.execute_python_code(code)["ok"]
    wait_for(lambda: server.model.cad_assets["part_asset"].metadata["local_bounds"][3] == 2)
    assert server.model.cad_assets["part_asset"].content_digest == hashlib.sha256(source.read_bytes()).hexdigest()


@pytest.mark.parametrize("options", [
    {"id":"part", "unit_scale_to_m":1e308},
    {"id":"part", "unit_scale_to_m":1, "placement":{"origin":[1e308,1e308,1e308]}},
])
def test_preview_refuses_overflow_or_collapsed_placed_geometry(server, options):
    assert upload(server, "store", body=binary_triangle(2), options=options)[0] == 422
    assert not (server.project.root / "geometry").exists()


def test_concurrent_older_failed_run_cannot_rollback_newer_valid_save(tmp_path, monkeypatch):
    import tuba.project as project_module

    project = tmp_path / "project"
    project.mkdir()
    (project / "model.py").write_text(MODEL)
    server = ProjectStudioServer(project, tmp_path / "out", port=0)
    assert server._run_script()[0]["ok"]
    entered, release, saved = threading.Event(), threading.Event(), threading.Event()
    actual = project_module.run_model_script
    calls = []

    def run(path):
        calls.append(path.read_text())
        if len(calls) == 1:
            entered.set()
            assert release.wait(5)
            raise ValueError("Older execution failed")
        return actual(path)

    monkeypatch.setattr(project_module, "run_model_script", run)
    older = threading.Thread(target=server._run_script)
    newer = threading.Thread(target=lambda: (server.execute_python_code(MODEL.replace('Geometry project', 'Latest')), saved.set()))
    older.start()
    assert entered.wait(5)
    newer.start()
    assert not saved.wait(.1)
    assert server.script_path.read_text() == MODEL
    release.set()
    older.join(5)
    newer.join(5)
    assert not older.is_alive() and not newer.is_alive()
    assert saved.is_set() and server.model.project_name == "Latest"
    assert not server._source_error
    assert server._last_fingerprint == server.watch_fingerprint()


def test_solve_and_command_snapshots_wait_for_inflight_failed_reload(tmp_path, monkeypatch):
    import tuba.project as project_module

    project = tmp_path / "project"
    project.mkdir()
    (project / "model.py").write_text(MODEL)
    (project / "study.py").write_text("LOAD_CASES=('Operating',)\n")
    server = ProjectStudioServer(project, tmp_path / "out", port=0)
    assert server._run_script()[0]["ok"]
    entered, release = threading.Event(), threading.Event()
    solve_done, comm_done = threading.Event(), threading.Event()
    solve_results, comm_results, solve_calls = [], [], []

    def run(_path):
        entered.set()
        assert release.wait(5)
        raise ValueError("Reload failed")

    monkeypatch.setattr(project_module, "run_model_script", run)
    monkeypatch.setattr(server, "_solve", lambda *args: solve_calls.append(args))
    reload = threading.Thread(target=server._run_script)
    solve = threading.Thread(target=lambda: (solve_results.append(server.start_solve()), solve_done.set()))
    comm = threading.Thread(target=lambda: (comm_results.append(server.code_aster_commands('Operating')), comm_done.set()))
    reload.start()
    assert entered.wait(5)
    solve.start()
    comm.start()
    assert not solve_done.wait(.1) and not comm_done.wait(.1)
    release.set()
    for thread in (reload, solve, comm):
        thread.join(5)
        assert not thread.is_alive()
    assert solve_results[0][0] == 400 and comm_results[0][0] == 422
    assert not solve_calls and server._source_error


def test_solve_and_commands_refresh_disk_edits_before_the_watcher(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    source = project / "model.py"
    source.write_text(MODEL)
    (project / "study.py").write_text("LOAD_CASES=('Operating',)\n")
    server = ProjectStudioServer(project, tmp_path / "out", port=0)
    assert server._run_script()[0]["ok"]
    solved = []
    done = threading.Event()

    def solve(namespace, force):
        solved.append(namespace["model"].project_name)
        done.set()

    monkeypatch.setattr(server, "_solve", solve)
    source.write_text(MODEL.replace("Geometry project", "Fresh disk source"))
    assert server.start_solve()[0] == 202
    assert done.wait(5)
    assert solved == ["Fresh disk source"]
    source.write_text("raise ValueError('Unsaved source is invalid')\n")
    assert server.code_aster_commands("Operating")[0] == 422
    assert server._source_error


def test_evidence_poll_waits_for_script_snapshot(tmp_path, monkeypatch):
    from types import SimpleNamespace

    project = tmp_path / "project"
    project.mkdir()
    (project / "model.py").write_text(MODEL)
    server = ProjectStudioServer(project, tmp_path / "out", port=0)
    assert server._run_script()[0]["ok"]
    server.study = SimpleNamespace(LOAD_CASES=("Operating",))
    monkeypatch.setattr(server, "_external_evidence_signature", lambda: (("receipt", b"completed"),))
    entered, release, importing = threading.Event(), threading.Event(), threading.Event()
    monkeypatch.setattr(server, "_prepare_review", lambda *_: importing.set())

    def save_snapshot():
        with server._script_lock:
            entered.set()
            assert release.wait(5)

    save = threading.Thread(target=save_snapshot)
    save.start()
    assert entered.wait(5)
    try:
        server.poll_review()
        assert not importing.wait(.1)
    finally:
        release.set()
        save.join(5)
    assert not save.is_alive()
    server.poll_review()
    assert importing.wait(5)


def test_start_runs_model_once_even_when_the_watcher_polls_mid_run(tmp_path):
    # The watcher used to compare against the pre-run fingerprint while start()'s
    # run was still going, and queued a second full run of model.py.
    project = tmp_path / "project"
    project.mkdir()
    runs = tmp_path / "runs.txt"
    # A project module the run discovers: the watched set grows mid-run.
    (project / "helper.py").write_text("SIZE = 1\n")
    (project / "model.py").write_text(f"import helper\nopen({str(runs)!r}, 'a').write('run ')\n" + MODEL)
    instance = ProjectStudioServer(project, tmp_path / "out", port=0, poll_interval_s=.03, debounce_s=.02)
    publish = instance._publish_scene
    # The window opens once model.py has returned: a slow scene publication.
    instance._publish_scene = lambda **kwargs: (time.sleep(0.4), publish(**kwargs))[1]
    instance.start()
    try:
        time.sleep(1.0)
        assert runs.read_text().count("run") == 1
    finally:
        instance.stop()
