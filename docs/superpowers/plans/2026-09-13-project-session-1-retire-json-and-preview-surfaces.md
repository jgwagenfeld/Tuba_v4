# Project and Authoring Session, Plan 1: Retire the JSON Editing and Script-Preview Surfaces

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Leave one studio (a project folder with `model.py`) and one kind of MCP session (a `model.py`), by deleting plain `StudioServer`, the JSON editing routes, the script-preview modes and MCP's viewer broadcast.

**Architecture:** Pure deletion plus one fold. `ProjectStudioServer` absorbs the four `StudioServer` methods it actually uses and inherits the transport (`PreviewServer`) directly. `python -m tuba.cli_studio` refuses anything but a project folder. The MCP server keeps a `model.py` only and sends no viewer events. No behaviour of the project studio changes; its existing tests are rewritten to pin that before the fold.

**Tech Stack:** Python 3.12, pytest/unittest, the repo's own HTTP/WebSocket transport.

**Spec:** `docs/superpowers/specs/2026-09-13-project-authoring-session-design.md` (decisions 25 and 26; roadmap step 1)

## Global Constraints

- **Worktree:** execute in `D:/tmp/tuba-session` on branch `project-session/1-retire-surfaces`, created with superpowers:using-git-worktrees from `main`. The short base path matters: this repo's fixture paths exceed Windows MAX_PATH under long bases. Never commit in `D:/Gitprojects/Tuba_v4`: another session commits on `main` there.
- **Python:** the worktree has no `.venv`. Run tests with the main repo's interpreter from the worktree root, as a module so the worktree's `tuba` is imported first: `D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest <args>` (written `PY -m pytest` below).
- **Known worktree failures:** two tests in `tests/test_package_release.py` fail in a fresh worktree with "'vite' is not recognized" (no `viewer/node_modules`). They are not caused by this plan; ignore them.
- **Line numbers** cite the files as of `main` @ `15b4116`. Earlier steps shift them; always locate code by the function, class or test name quoted beside the numbers.
- **No compatibility shims** (ADR 0001): removed names are not aliased or re-exported.
- **No new dependencies.**
- **Do not touch** `viewer/`, `examples/`, `docs/content/`, or `tuba/visualization/live_preview.py` (its fate is an open question in the spec).
- **Commit attribution:** every commit message ends with
  `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`
- **Merging:** the finished branch is reported to the user; `main` is fast-forwarded only with the user's approval.

---

### Task 1: The studio opens project folders only

Delete plain `StudioServer`, its JSON routes (`/api/model`, `/api/patch`) and the WebSocket mutation messages, and fold the four methods `ProjectStudioServer` uses into it. `cli_studio` refuses a file.

**Files:**
- Modify: `tuba/cli_studio.py` (whole file)
- Modify: `tuba/visualization/preview/server.py`: imports (1–30), `PreviewServer.start` (288–311), `_handler_factory` (386–711), delete `StudioServer` (853–1216), `ProjectStudioServer` (1219–1403), delete `export_model_to_python` (1424–1436)
- Create: `tests/test_cli_studio.py`
- Modify: `tests/test_visualization_patch_preview.py` (studio tests, 170–505)
- Modify: `tests/test_mcp_server.py` (import at 23, tests at 148–221)

**Interfaces:**
- Consumes: `tuba.project.load_project`, `tuba.project.run_model_script` (unchanged).
- Produces: `ProjectStudioServer(project, out_dir, *, host="127.0.0.1", port=8765, timeout_s=5.0, poll_interval_s=0.25, debounce_s=0.2)` subclassing `PreviewServer`, with `start() -> ProjectStudioServer`, `run_once() -> None`, `get_python_script() -> str`, `execute_python_code(code: str) -> dict[str, Any]`, plus its existing `project_info`, `start_solve`, `review_stale`. `_handler_factory(out_dir, broker, script_get_handler=None, script_post_handler=None, solve_handler=None, project_handler=None, bound_host="127.0.0.1")`. `tuba.cli_studio.main(argv)` exits with code 2 for anything but a folder holding `model.py`.

- [ ] **Step 1: Record the baseline in the worktree**

Run: `PY -m pytest -q -p no:cacheprovider`
Expected: note every failing test id. Only the two `test_package_release.py` vite failures are expected; any other failure is pre-existing and must be listed in the task report so later steps can tell it apart.

- [ ] **Step 2: Write the failing CLI test**

Create `tests/test_cli_studio.py`:

```python
"""The studio opens a project folder, never a bare model file."""

from pathlib import Path

import pytest

from tuba import cli_studio


def test_the_studio_refuses_anything_but_a_project_folder(tmp_path: Path, monkeypatch, capsys):
    class _Refuse:
        def __init__(self, *args, **kwargs):
            raise AssertionError("the studio started on a model file")

    # Until the file form is gone, this stops main() from starting a server that never returns.
    monkeypatch.setattr(cli_studio, "StudioServer", _Refuse, raising=False)
    model_json = tmp_path / "model.json"
    model_json.write_text("{}", encoding="utf-8")

    with pytest.raises(SystemExit) as exit_info:
        cli_studio.main([str(model_json), "--no-open"])

    assert exit_info.value.code == 2
    assert "project folder" in capsys.readouterr().err
```

- [ ] **Step 3: Run it to verify it fails**

Run: `PY -m pytest tests/test_cli_studio.py -v`
Expected: FAIL with `AssertionError: the studio started on a model file`.

- [ ] **Step 4: Pin the project studio's behaviour before the fold**

In `tests/test_visualization_patch_preview.py`:

1. After `_BUILDER_SCRIPT` (line 25), add:

```python
_SMALL_SCRIPT = """from tuba import Model

model = Model("StudioStart")
model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0, alpha=1.2e-5)
model.add_pipe_section("DN100", OD=0.1143, WT=0.00602)
model.define_load_case("Operating", gravity=True, pressure=1.0e6)
with model.pipe(section="DN100", material="Steel") as builder:
    builder.start([0.0, 0.0, 0.0], support="anchor")
    builder.run(2.0)
    builder.end(support="anchor")
"""
```

2. Delete these tests, which only exercise plain `StudioServer`: `test_studio_server_get_and_post_model_json` (170–216), `test_studio_server_domain_action_extend_and_support` (218–268), `test_studio_server_ignores_cross_origin_websocket_mutations` (394–422) and `test_generated_script_rebuilds_the_model_exactly` (485–505; plan 2 replaces it with round-trip tests of the new generator).

3. Replace `test_studio_server_python_script_endpoints` (270–333) with:

```python
    def test_studio_server_serves_and_saves_model_py(self):
        with TemporaryDirectory() as tmpdir:
            server = self._start_studio(Path(tmpdir))

            with urlopen(server.base_url + "api/script", timeout=10) as response:
                self.assertEqual(json.loads(response.read().decode("utf-8")), {"ok": True, "code": _SMALL_SCRIPT})

            status, payload = self._post_script(server, _BUILDER_SCRIPT)
            self.assertEqual(status, 200, payload)
            self.assertEqual(payload["elements"], 3)
            self.assertEqual(server.script_path.read_text(encoding="utf-8"), _BUILDER_SCRIPT)
```

4. Replace the helper `_start_studio` (335–342) with:

```python
    def _start_studio(self, root: Path, script: str = _SMALL_SCRIPT, **kwargs):
        from tuba.visualization.preview.server import ProjectStudioServer

        project = root / "project"
        project.mkdir()
        (project / "model.py").write_text(script, encoding="utf-8")
        server = ProjectStudioServer(project, root / "out", port=0, **kwargs).start()
        self.addCleanup(server.stop)
        return server
```

5. Replace `_scene_objects` (360–362) with:

```python
    def _scene_objects(self, server) -> dict:
        scene = json.loads((server.out_dir / "build" / "scene.json").read_text(encoding="utf-8"))
        return {obj["name"]: obj for obj in scene["objects"]}
```

6. Replace `test_studio_server_refuses_cross_origin_posts` (375–392) with:

```python
    def test_studio_server_refuses_cross_origin_posts(self):
        # Without this, any web page could POST a script here and run Python on this machine.
        with TemporaryDirectory() as tmpdir:
            server = self._start_studio(Path(tmpdir))

            status, payload = self._post_script(server, _BUILDER_SCRIPT, Origin="http://evil.example")
            self.assertEqual((status, payload), (403, {"ok": False, "error": "cross-origin request refused"}))
            # DNS rebinding: the page is "same-origin", but on a foreign host name.
            rebound = f"evil.example:{server.port}"
            status, _payload = self._post_script(server, _BUILDER_SCRIPT, Host=rebound, Origin=f"http://{rebound}")
            self.assertEqual(status, 403)
            self.assertEqual(server.script_path.read_text(encoding="utf-8"), _SMALL_SCRIPT)

            status, payload = self._post_script(server, _BUILDER_SCRIPT, Origin=f"http://127.0.0.1:{server.port}")
            self.assertEqual(status, 200, payload)
            self.assertEqual(server.script_path.read_text(encoding="utf-8"), _BUILDER_SCRIPT)
```

7. In `test_studio_server_reruns_model_py_saved_by_another_editor` (459–483), replace its first five lines (from `with TemporaryDirectory() as tmpdir:` through the `self.assertIn("pipe_str_1", ...)` line) with:

```python
        with TemporaryDirectory() as tmpdir:
            server = self._start_studio(Path(tmpdir), _BUILDER_SCRIPT, poll_interval_s=0.05, debounce_s=0.05)
            script_path = server.script_path
            self.assertIn("pipe_str_1", self._scene_objects(server))  # the initial run executes model.py
```

`test_studio_server_script_errors_point_at_the_script_line`, `test_studio_server_links_scene_objects_to_script_lines` and `test_studio_server_websocket_survives_an_idle_viewer` stay as they are: they already go through `_start_studio`.

In `tests/test_mcp_server.py`, delete the import `from tuba.visualization.preview.server import StudioServer` (line 23) and the tests `test_studio_server_patch_handling` (148–169) and `test_studio_server_staleness` (172–221).

- [ ] **Step 5: Run the pinned tests against the current code**

Run: `PY -m pytest tests/test_visualization_patch_preview.py tests/test_studio_project.py tests/test_mcp_server.py -v`
Expected: PASS. `ProjectStudioServer` already behaves this way; these tests now guard the fold.

- [ ] **Step 6: Make `cli_studio` project-only**

Replace `tuba/cli_studio.py` with:

```python
"""CLI entrypoint for Tuba Studio: a project folder's model.py live in the 3D viewer."""

from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

from tuba.visualization.preview.server import ProjectStudioServer


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Launch Tuba Studio on a project folder.")
    parser.add_argument(
        "project",
        help="A project folder holding model.py (and optionally study.py), e.g. examples/code-aster-review",
    )
    parser.add_argument(
        "--out",
        dest="out_dir",
        default=None,
        help="Directory to write scene bundles to (default: .build/studio/<project>)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host address to bind HTTP and WebSocket server (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port number to bind (default: 8765, 0 for random)",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Do not open default web browser on launch",
    )
    args = parser.parse_args(argv)

    project = Path(args.project).resolve()
    if not (project / "model.py").is_file():
        parser.error(f"{project} is not a project folder: it needs a model.py.")
    out_dir = Path(args.out_dir or Path(".build") / "studio" / project.name).resolve()
    server = ProjectStudioServer(project, out_dir, host=args.host, port=args.port)
    server.start()

    # The viewer opens on the live model; Review switches to the review bundle.
    viewer_url = f"{server.base_url}?bundle=build&preview_ws={server.ws_url}"
    print("=" * 60)
    print("  TUBA PIPING STUDIO")
    print("=" * 60)
    print(f"  Project     : {project}")
    print(f"  3D Viewer   : {viewer_url}")
    print(f"  MCP Server  : python -m tuba.mcp.server")
    print("=" * 60)
    print("Studio running. Press Ctrl+C to stop.\n", flush=True)

    if not args.no_open:
        webbrowser.open(viewer_url)

    try:
        while not server._stop.wait(1.0):
            pass
    except KeyboardInterrupt:
        print("\nStopping Tuba Studio...")
    finally:
        server.stop()

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 7: Run the CLI test to verify it passes**

Run: `PY -m pytest tests/test_cli_studio.py -v`
Expected: PASS.

- [ ] **Step 8: Fold `StudioServer` into `ProjectStudioServer` and drop the JSON routes**

In `tuba/visualization/preview/server.py`:

1. Delete the line `import pprint` (line 10).

2. In `PreviewServer.start`, replace the `_handler_factory(...)` call (290–301) with:

```python
        handler = _handler_factory(
            self.out_dir,
            self.broker,
            script_get_handler=getattr(self, "get_python_script", None),
            script_post_handler=getattr(self, "execute_python_code", None),
            solve_handler=getattr(self, "start_solve", None),
            project_handler=getattr(self, "project_info", None),
            bound_host=self.host,
        )
```

3. Replace the signature of `_handler_factory` (386–397) with:

```python
def _handler_factory(
    out_dir: Path,
    broker: PreviewEventBroker,
    script_get_handler: Any = None,
    script_post_handler: Any = None,
    solve_handler: Any = None,
    project_handler: Any = None,
    bound_host: str = "127.0.0.1",
):
```

4. In `do_GET`, delete the whole `if parsed.path in ("/api/model", "/model.json"):` block (451–469).

5. In `do_POST`, delete the whole `if parsed.path in ("/api/patch", "/preview/patch"):` block (523–544) and the whole `if parsed.path in ("/api/model", "/model.json"):` block (545–566). The final `self.send_response(404)` stays.

6. In `_handle_websocket`, replace from `client = _WebSocketClient(self.connection)` (650) through the end of the frame loop (the `pass` at 690) with:

```python
            client = _WebSocketClient(self.connection)
            # Broadcasts reach every viewer (the Vite dev server subscribes cross-origin).
            # Viewers only listen: a text frame from a client changes nothing.
            broker.add(client)
            try:
                # Blocking reads. A timeout on the buffered rfile poisons it - every later
                # read raises "cannot read from timed out object" - which dropped each
                # viewer half a second after it connected. stop() wakes a blocked read by
                # shutting the socket down in _WebSocketClient.close().
                self.connection.settimeout(None)
                while not broker.closed:
                    try:
                        frame = self.rfile.read(2)
                    except OSError:
                        break
                    if not frame:
                        break
                    opcode = frame[0] & 0x0F
                    length = frame[1] & 0x7F
                    if length == 126:
                        length = struct.unpack("!H", self.rfile.read(2))[0]
                    elif length == 127:
                        length = struct.unpack("!Q", self.rfile.read(8))[0]
                    mask = self.rfile.read(4) if frame[1] & 0x80 else b""
                    payload = self.rfile.read(length) if length else b""
                    if mask and payload:
                        payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
                    if opcode == 0x8:
                        break
                    if opcode == 0x9:
                        client.send_pong(payload)
```

The `finally: broker.remove(client)` that follows stays.

7. Delete the whole `class StudioServer(PreviewServer):` (853–1216).

8. Replace `class ProjectStudioServer(StudioServer):` from its `class` line through the end of its `start` method (1219–1286) with:

```python
class ProjectStudioServer(PreviewServer):
    """The studio for a project folder: ``model.py`` drives Build, ``study.py`` drives Review.

    The live model scene is the ``build/`` bundle and the solved or imported review is
    ``review/``. A Run never overwrites a review, and Review never shows results for a
    model that has changed since without saying so (``review_stale``).
    """

    def __init__(
        self,
        project: str | Path,
        out_dir: str | Path,
        *,
        host: str = "127.0.0.1",
        port: int = 8765,
        timeout_s: float = 5.0,
        poll_interval_s: float = 0.25,
        debounce_s: float = 0.2,
    ) -> None:
        from tuba.project import load_project

        self.project = load_project(project)
        super().__init__(
            self.project.model_path,
            out_dir,
            host=host,
            port=port,
            timeout_s=timeout_s,
            poll_interval_s=poll_interval_s,
            debounce_s=debounce_s,
        )
        self.model: TubaModel | None = None
        self.namespace: dict[str, Any] | None = None
        self.study = self.project.load_study()
        self.review_error: str | None = None
        self._review_model_hash: str | None = None
        self._solve_lock = threading.Lock()
        # Busy with a review (the startup import or a Solve); _preparing marks the import.
        self._solving = False
        self._preparing = False

    def start(self) -> "ProjectStudioServer":
        super().start(run_initial=False)
        result, event = self._run_script()
        if not result["ok"]:
            self.broker.broadcast(event)
            return self
        artifact_dir = getattr(self.study, "ARTIFACT_DIR", None)
        if self.study is not None and (artifact_dir is not None or not getattr(self.study, "LOAD_CASES", ())):
            # Attested evidence imports without a solver, and a study with no solver
            # has nothing to wait for; a study that must solve waits for Solve. It runs
            # in the background: the viewer is already up and hears review_ready.
            with self._solve_lock:
                self._solving = self._preparing = True
            threading.Thread(
                target=self._prepare_review,
                args=(self.namespace, artifact_dir),
                name="tuba-studio-review",
                daemon=True,
            ).start()
        return self

    def run_once(self) -> None:
        # model.py is the source of truth: a save from any editor reruns it.
        result, event = self._run_script()
        if not result["ok"]:
            # The last good scene stays; tell viewers why it did not change.
            self.broker.broadcast(event)

    def get_python_script(self) -> str:
        return self.script_path.read_text(encoding="utf-8")

    def execute_python_code(self, code: str) -> dict[str, Any]:
        """Save *code* as model.py, run it, and broadcast the live scene."""
        with self._fingerprint_lock:
            # newline="": write what the client sent. Text mode on Windows turns a CRLF body
            # into CR CR LF, and Python then counts every line twice in tracebacks.
            self.script_path.write_text(code, encoding="utf-8", newline="")
            # The watcher compares against this, so it does not run the same file again.
            self._last_fingerprint = _file_fingerprint(self.script_path)
        return self._run_script()[0]

    def _run_script(self) -> tuple[dict[str, Any], dict[str, Any]]:
        """Run model.py; on success validate it and publish its scene.

        Returns the /api/script response and the viewer event: ``scene_reloaded``, or
        ``script_error`` when the script fails (the previous scene is left as it was).
        """
        from tuba.project import run_model_script
        from tuba.validation import validate_model

        # ponytail: scripts run in-process, so an infinite loop still hangs the server;
        # upgrade path is a subprocess with a timeout.
        try:
            namespace = run_model_script(self.script_path)
            new_model = namespace["model"]
            validate_model(new_model)
            self.model = new_model
            # Kept for Solve: a study reviews the script's globals, not just the model.
            self.namespace = namespace
            event = self._publish_scene()
        except KeyboardInterrupt:
            raise
        except BaseException as exc:  # sys.exit() in a script fails the run, not the request
            error = f"{type(exc).__name__}: {exc}"
            line = _script_error_line(exc, self.script_path)
            return (
                {"ok": False, "error": error, "line": line, "traceback": traceback.format_exc()},
                {"type": "script_error", "error": error, "line": line},
            )
        return (
            {
                "ok": True,
                "revision": self.revision,
                "results_stale": event["results_stale"],
                "review_stale": event["review_stale"],
                "nodes": len(self.model.nodes),
                "elements": len(self.model.elements),
            },
            event,
        )
```

Keep the rest of `ProjectStudioServer` exactly as it is: `_prepare_review`, `review_stale`, `_publish_scene`, `_swap_bundle`, `_produce_review`, `project_info`, `start_solve`, `_solve`. The two class attributes `handle_patch = None` / `handle_model_json = None` and the `self.model_path = self.out_dir / "model.json"` line are gone with the replaced block: nothing reads that file.

9. Delete `export_model_to_python` (1424–1436).

- [ ] **Step 9: Run the studio, MCP and project tests**

Run: `PY -m pytest tests/test_visualization_patch_preview.py tests/test_studio_project.py tests/test_mcp_server.py tests/test_cli_studio.py -v`
Expected: PASS.

- [ ] **Step 10: Drop the CLI test's stub**

The file form is gone, so the stub has nothing left to stop. In `tests/test_cli_studio.py`, delete the `_Refuse` class, its comment and the `monkeypatch.setattr(...)` line, and remove `monkeypatch` from the test's parameters:

```python
def test_the_studio_refuses_anything_but_a_project_folder(tmp_path: Path, capsys):
    model_json = tmp_path / "model.json"
    model_json.write_text("{}", encoding="utf-8")

    with pytest.raises(SystemExit) as exit_info:
        cli_studio.main([str(model_json), "--no-open"])

    assert exit_info.value.code == 2
    assert "project folder" in capsys.readouterr().err
```

Run: `PY -m pytest tests/test_cli_studio.py -v`
Expected: PASS.

- [ ] **Step 11: Check that nothing still names the removed surface**

Run: `git grep -n -w -e StudioServer -e handle_patch -e handle_model_json -e get_model_json -e client_patch -e client_model_update -e export_model_to_python -- tuba tests scripts`
Expected: no output. (`ProjectStudioServer` does not match `-w StudioServer`.)

Run: `git grep -n -e "api/model" -e "api/patch" -e "preview/patch" -- tuba tests scripts viewer/src`
Expected: no output.

- [ ] **Step 12: Run the full suite**

Run: `PY -m pytest -q -p no:cacheprovider`
Expected: the same failures as the Step 1 baseline, and no others.

- [ ] **Step 13: Commit**

```bash
git add tuba/cli_studio.py tuba/visualization/preview/server.py tests/test_cli_studio.py tests/test_visualization_patch_preview.py tests/test_mcp_server.py
git commit -m "refactor(studio): open project folders only and drop the JSON editing routes

Plain StudioServer, /api/model, /api/patch and the WebSocket model mutations
had no caller in the viewer. ProjectStudioServer takes over the four methods
it used, and cli_studio refuses anything but a folder holding model.py.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Retire the script-preview modes

Delete `python -m tuba.visualization.preview watch|watch-patch`, `PatchPreviewServer`, the subprocess runner and the `show_*` capture helpers. `PreviewServer` stays as the studio's transport. The surviving studio tests move to a file named for what they test.

**Files:**
- Delete: `tuba/visualization/preview/__main__.py`
- Delete: `tuba/visualization/preview/_runner.py`
- Modify: `tuba/visualization/preview/__init__.py` (whole file)
- Modify: `tuba/visualization/preview/server.py`: imports, delete `PreviewRunResult`, `execute_preview_script`, `run_preview_once`, `execute_patch_preview`, `run_patch_preview_once`, `PreviewServer.run_once`, `PatchPreviewServer`, `_broadcast_all`, `_diagnostic`, `_preview_subprocess_timeout`, `_diagnostic_event`, `_PARTIAL_WRITE_ATTEMPTS`, `_PARTIAL_WRITE_BACKOFF_S`, `_read_json_file`, `_patch_preview_failure`, `_diagnostic_scene`, `_PatchPreviewError`; `PreviewServer.start`; `ProjectStudioServer.start`
- Rename: `tests/test_visualization_patch_preview.py` → `tests/test_studio_server.py`
- Delete: `tests/test_visualization_preview_server.py` (its port-refusal test moves)

**Interfaces:**
- Consumes: `ProjectStudioServer` and `_handler_factory` as produced by Task 1.
- Produces: `PreviewServer(script_path, out_dir, *, host, port, timeout_s, poll_interval_s, debounce_s)` with `start() -> PreviewServer` (no `run_initial` parameter; subclasses provide `run_once()`), `stop()`, `base_url`, `ws_url`. `tuba.visualization.preview` exports nothing; import from `tuba.visualization.preview.server`.

- [ ] **Step 1: Move the surviving tests and delete the ones for retired modes**

Run: `git mv tests/test_visualization_patch_preview.py tests/test_studio_server.py`

In `tests/test_studio_server.py`:

1. Delete the imports `from tuba import Model`, `from tuba.patches import AddElement, AddNode, ModelPatch` and `from tuba.visualization.preview import PatchPreviewServer, execute_patch_preview, run_patch_preview_once`.

2. Rename `class TestVisualizationPatchPreview(unittest.TestCase):` to `class TestStudioServer(unittest.TestCase):`.

3. Delete the helpers `_model`, `_patch` and `_write_inputs`, and the tests `test_run_patch_preview_once_writes_scene_without_mutating_model_snapshot`, `test_invalid_patch_returns_diagnostic_without_mutating_model_snapshot`, `test_patch_preview_server_watches_patch_and_serves_updated_scene` and `test_half_written_patch_does_not_clobber_the_served_bundle`.

4. Add this test to the class (moved from `tests/test_visualization_preview_server.py`; Step 3 drops `run_initial` once the parameter is gone):

```python
    def test_studio_transport_refuses_a_port_another_server_is_serving(self):
        # Windows let a second server share a port an older studio still served
        # (SO_REUSEADDR), and the browser kept talking to the old one.
        from tuba.visualization.preview.server import PreviewServer

        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            script = root / "model.py"
            script.write_text("", encoding="utf-8")
            first = PreviewServer(script, root / "first", port=0).start(run_initial=False)
            try:
                with self.assertRaises(OSError):
                    PreviewServer(script, root / "second", port=first.port).start(run_initial=False)
            finally:
                first.stop()
```

Run: `git rm tests/test_visualization_preview_server.py`

- [ ] **Step 2: Run the moved tests before touching the code**

Run: `PY -m pytest tests/test_studio_server.py -v`
Expected: PASS. Nothing in this file depends on the retired modes any more, so these tests guard the deletion in Step 3.

- [ ] **Step 3: Delete the retired modes from the code**

1. Run: `git rm tuba/visualization/preview/__main__.py tuba/visualization/preview/_runner.py`

2. Replace `tuba/visualization/preview/__init__.py` with:

```python
"""The studio's local HTTP/WebSocket transport.

:mod:`tuba.visualization.preview.server` holds ``ProjectStudioServer``, which serves a
project folder's Build and Review bundles, and the transport it runs on.
"""
```

3. In `tuba/visualization/preview/server.py`, replace the import block (the lines from `from __future__ import annotations` through `from tuba.visualization.web_export import write_scene_bundle`) with:

```python
from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import socket
import struct
import shutil
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from tuba.model import TubaModel
from tuba.visualization.viewer import LocalHTTPServer, viewer_assets_path
from tuba.visualization.web_export import write_scene_bundle
```

4. Delete these definitions entirely: `PreviewRunResult`, `execute_preview_script`, `run_preview_once`, `execute_patch_preview`, `run_patch_preview_once`, `PatchPreviewServer`, `_broadcast_all`, `_diagnostic`, `_preview_subprocess_timeout`, `_diagnostic_event`, the `_PARTIAL_WRITE_ATTEMPTS` comment block and constants, `_PARTIAL_WRITE_BACKOFF_S`, `_read_json_file`, `_patch_preview_failure`, `_diagnostic_scene` and `_PatchPreviewError`. Keep `PreviewEventBroker`, `PreviewServer`, `_handler_factory`, `_WebSocketClient`, `_file_fingerprint`, `_WEBSOCKET_GUID`, `ProjectStudioServer`, `_model_hash` and `_script_error_line`.

5. In `PreviewServer`, delete the method `run_once`, and replace the `start` method with:

```python
    def start(self) -> "PreviewServer":
        self.out_dir.mkdir(parents=True, exist_ok=True)
        handler = _handler_factory(
            self.out_dir,
            self.broker,
            script_get_handler=getattr(self, "get_python_script", None),
            script_post_handler=getattr(self, "execute_python_code", None),
            solve_handler=getattr(self, "start_solve", None),
            project_handler=getattr(self, "project_info", None),
            bound_host=self.host,
        )
        self._httpd = LocalHTTPServer((self.host, self.port), handler)
        self.port = int(self._httpd.server_address[1])
        self._server_thread = threading.Thread(target=self._httpd.serve_forever, name="tuba-preview-http", daemon=True)
        self._server_thread.start()
        self._last_fingerprint = _file_fingerprint(self.script_path)
        # ponytail: ProjectStudioServer is the only server; its run_once is what the watcher
        # calls. Plan 7 splits this transport from the authoring session.
        self._watch_thread = threading.Thread(target=self._watch_loop, name="tuba-preview-watch", daemon=True)
        self._watch_thread.start()
        return self
```

6. In `ProjectStudioServer.start`, replace `super().start(run_initial=False)` with `super().start()`.

7. In `tests/test_studio_server.py`, in `test_studio_transport_refuses_a_port_another_server_is_serving`, change both `.start(run_initial=False)` calls to `.start()`.

- [ ] **Step 4: Run the studio tests**

Run: `PY -m pytest tests/test_studio_server.py tests/test_studio_project.py tests/test_mcp_server.py tests/test_cli_studio.py -v`
Expected: PASS.

- [ ] **Step 5: Check that the retired modes are gone**

Run: `git grep -n -e PatchPreviewServer -e execute_preview_script -e run_preview_once -e execute_patch_preview -e run_patch_preview_once -e PreviewRunResult -e show_scene -e show_model -e show_patch -e "preview._runner" -e "visualization.preview import" -- tuba tests scripts`
Expected: no output.

Run: `PY -m tuba.visualization.preview`
Expected: exit code 1 with "No module named tuba.visualization.preview.__main__; 'tuba.visualization.preview' is a package and cannot be directly executed".

- [ ] **Step 6: Run the full suite**

Run: `PY -m pytest -q -p no:cacheprovider`
Expected: the Task 1 baseline failures only.

- [ ] **Step 7: Commit**

```bash
git add -A tuba/visualization/preview tests/test_studio_server.py tests/test_visualization_patch_preview.py tests/test_visualization_preview_server.py
git commit -m "refactor(preview): retire the watch and watch-patch preview modes

python -m tuba.visualization.preview, PatchPreviewServer, the subprocess
runner and the show_* capture helpers had no caller outside their tests; the
project studio covers them. PreviewServer stays as the studio's transport,
and the surviving studio tests move to test_studio_server.py.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: MCP sessions keep a model.py and send no viewer events

An MCP session saves to a `model.py` only; a JSON path is refused, and a tool called before `init_session` says so instead of creating a model that saves to `model.json` in the working directory. The broadcast to an in-process broker goes: ADR 0003 has viewers learn of MCP changes through the studio watching the folder.

**Files:**
- Modify: `tuba/mcp/server.py`: imports and globals (11–57), `get_active_model`, `set_active_model`, `set_preview_broker` (60–80), `_save_and_broadcast` (100–127), `init_session` (142–197), callers of `_save_and_broadcast` (221, 242, 288, 334, 364)
- Modify: `tests/test_mcp_server.py`

**Interfaces:**
- Consumes: nothing from Tasks 1–2 beyond `ProjectStudioServer` (used by the existing live-studio test).
- Produces: `init_session(project_name="Generative Piping", standard="ASME B31.3", file_path="model.py", load_existing=True)` raising `ValueError` for a path whose suffix is not `.py`; `get_active_model() -> TubaModel` raising `RuntimeError` when no session exists; `_save(model: TubaModel) -> None`. `set_active_model` and `set_preview_broker` no longer exist.

- [ ] **Step 1: Write the failing tests**

In `tests/test_mcp_server.py`, add `import tuba.mcp.server as mcp_server` below the existing imports, and add:

```python
def test_a_session_saves_to_a_model_py_only(tmp_path: Path):
    model_json = tmp_path / "model.json"

    with pytest.raises(ValueError, match="model.py"):
        init_session(file_path=str(model_json), load_existing=False)
    assert not model_json.exists()


def test_tools_need_a_session(monkeypatch):
    monkeypatch.setattr(mcp_server, "_ACTIVE_MODEL", None)
    monkeypatch.setattr(mcp_server, "_ACTIVE_PATH", None)

    with pytest.raises(RuntimeError, match="init_session"):
        inspect_model()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `PY -m pytest tests/test_mcp_server.py::test_a_session_saves_to_a_model_py_only tests/test_mcp_server.py::test_tools_need_a_session -v`
Expected: both FAIL: the JSON session is created (`DID NOT RAISE <class 'ValueError'>`), and `inspect_model()` returns a default model (`DID NOT RAISE <class 'RuntimeError'>`).

- [ ] **Step 3: Move the existing MCP tests off JSON sessions**

In `tests/test_mcp_server.py`, change each session path to a `model.py` in its own folder:

- `test_init_and_inspect`: `model_file = tmp_path / "rig" / "model.py"`
- `test_build_pipe_run_procedural`: `model_file = tmp_path / "pipe" / "model.py"`
- `test_configure_load_case_and_forces`: `model_file = tmp_path / "lc" / "model.py"`
- `test_apply_model_patch_transaction`: `model_file = tmp_path / "patch" / "model.py"`
- `test_export_python_script`: `model_file = tmp_path / "session" / "model.py"` (the export target `tmp_path / "line" / "model.py"` stays)

- [ ] **Step 4: Implement**

In `tuba/mcp/server.py`:

1. Delete `import logging` and `logger = logging.getLogger(__name__)`.

2. Delete the imports `from tuba.visualization.live_preview import preview_json_patch` and `from tuba.visualization.preview.server import PreviewEventBroker`.

3. Replace the globals block (the `# Global session state` comment through `_SCRIPT_TEXT: Optional[str] = None`) with:

```python
# Global session state
_ACTIVE_MODEL: Optional[TubaModel] = None
_ACTIVE_PATH: Optional[Path] = None
_SCRIPT_HEADER = '"""Tuba v4 procedural pipeline script generated by Tuba MCP."""'
#: The text a model.py session last wrote to, or read from, its script. A save refuses
#: to overwrite anything else: that is an edit made in the studio or an editor.
_SCRIPT_TEXT: Optional[str] = None
```

4. Replace `get_active_model`, `set_active_model` and `set_preview_broker` with:

```python
def get_active_model() -> TubaModel:
    """Return the session's model."""
    if _ACTIVE_MODEL is None:
        raise RuntimeError("No model session: call init_session with the path of a model.py first.")
    return _ACTIVE_MODEL
```

5. Replace `_save_and_broadcast` with:

```python
def _save(model: TubaModel) -> None:
    """Rewrite the session's model.py; a studio watching its folder shows the change."""
    _ACTIVE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _write_script(model)
```

6. Replace `init_session` with:

```python
@mcp.tool()
def init_session(
    project_name: str = "Generative Piping",
    standard: str = "ASME B31.3",
    file_path: str = "model.py",
    load_existing: bool = True,
) -> Dict[str, Any]:
    """Initialize or load a piping analysis model session.

    Parameters:
    - project_name: Human-readable name for the engineering project.
    - standard: Piping code standard (e.g. 'ASME B31.3', 'EN 13480').
    - file_path: The model.py the model is saved to after every change. A model.py in its
      own folder is a project the studio opens (python -m tuba.cli_studio <folder>) to show
      each change as it happens. An existing model.py is only taken over if this server
      generated it.
    - load_existing: If True and the file exists, loads the existing model.
    """
    global _ACTIVE_MODEL, _ACTIVE_PATH, _SCRIPT_TEXT
    target = Path(file_path).resolve()
    if target.suffix != ".py":
        raise ValueError(
            f"{target} is not a model.py: a session saves its model to a Python model script "
            "that the studio can open."
        )
    existing = target.read_text(encoding="utf-8") if target.exists() else None
    if existing is not None and not existing.startswith(_SCRIPT_HEADER):
        raise ValueError(
            f"{target} was not generated by this server and may hold hand-written code. "
            "Edit it directly, or pass the path of a new model.py."
        )
    _SCRIPT_TEXT = existing
    _ACTIVE_PATH = target

    if load_existing and existing is not None:
        with contextlib.redirect_stdout(sys.stderr):  # stdout carries the MCP protocol
            _ACTIVE_MODEL = run_model_script(target)["model"]
        return {
            "status": "loaded",
            "project_name": _ACTIVE_MODEL.project_name,
            "standard": _ACTIVE_MODEL.standard,
            "nodes_count": len(_ACTIVE_MODEL.nodes),
            "elements_count": len(_ACTIVE_MODEL.elements),
            "file_path": str(target),
        }

    _ACTIVE_MODEL = TubaModel(project_name=project_name, standard=standard)
    _ensure_default_specs(_ACTIVE_MODEL)
    _save(_ACTIVE_MODEL)
    return {
        "status": "initialized",
        "project_name": project_name,
        "standard": standard,
        "file_path": str(target),
    }
```

7. In `add_material`, `add_pipe_section`, `build_pipe_run` and `configure_load_case`, replace `_save_and_broadcast(model)` with `_save(model)`. In `apply_model_patch`, replace `_save_and_broadcast(model, patch=patch)` with `_save(model)`.

- [ ] **Step 5: Run the MCP tests**

Run: `PY -m pytest tests/test_mcp_server.py -v`
Expected: PASS, including `test_a_model_py_session_keeps_a_running_studio_live`, which proves the studio still sees MCP changes through `model.py`.

- [ ] **Step 6: Check that MCP no longer reaches the viewer directly**

Run: `git grep -n -e set_preview_broker -e set_active_model -e _save_and_broadcast -e _PREVIEW_BROKER -e _PREVIEW_REVISION -e PreviewEventBroker -e preview_json_patch -- tuba/mcp tests/test_mcp_server.py`
Expected: no output.

- [ ] **Step 7: Run the full suite**

Run: `PY -m pytest -q -p no:cacheprovider`
Expected: the Task 1 baseline failures only.

- [ ] **Step 8: Commit**

```bash
git add tuba/mcp/server.py tests/test_mcp_server.py
git commit -m "refactor(mcp): keep sessions in model.py and stop broadcasting to viewers

A session saves to a model.py only, and a tool called before init_session
says so instead of writing model.json into the working directory. Viewers see
MCP changes through the studio watching the project folder (ADR 0003).

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Finish

- [ ] Run `PY -m pytest -q -p no:cacheprovider` once more on the branch tip and compare with the Task 1 baseline.
- [ ] Run `git log --oneline main..HEAD` and confirm exactly the three commits above.
- [ ] Report to the user: the three commits, the test result against the baseline, and that `main` has not been touched. Fast-forward `main` only after the user approves. Plan 2 (one generated-model-script module) is written after this branch lands.
