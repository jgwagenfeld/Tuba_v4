"""Local HTTP/WebSocket transport for the studio preview.

Owns bytes only: serving files, the preview event broker, and the request
routes. Project knowledge (models, bundles, solves) enters through injected
handler callables, so this module never imports the model, the solver, or the
review builders.
"""

from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import re
import shutil
import socket
import struct
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from tuba.local_auth import LocalAccess, new_access_token
from tuba.visualization.viewer import LocalHTTPServer, viewer_assets_path


class PreviewEventBroker:
    """Fan-out only: broadcasts reach connected clients, nothing is retained.

    A viewer recovers state from ``/api/project`` and the bundle on connect, so
    the broker keeps no event history and never replays.
    """

    def __init__(self) -> None:
        self._clients: set[_WebSocketClient] = set()
        self._lock = threading.RLock()
        self.closed = False

    def add(self, client: "_WebSocketClient") -> None:
        with self._lock:
            self._clients.add(client)

    def remove(self, client: "_WebSocketClient") -> None:
        with self._lock:
            self._clients.discard(client)

    def broadcast(self, event: dict[str, Any]) -> None:
        with self._lock:
            clients = list(self._clients)
        for client in clients:
            try:
                client.send_json(event)
            except OSError:
                self.remove(client)

    def close(self) -> None:
        self.closed = True
        with self._lock:
            clients = list(self._clients)
            self._clients.clear()
        for client in clients:
            client.close()


class PreviewServer:
    def __init__(
        self,
        script_path: str | Path,
        out_dir: str | Path,
        *,
        host: str = "127.0.0.1",
        port: int = 8765,
        poll_interval_s: float = 0.25,
        debounce_s: float = 0.2,
        allowed_dev_origin: str | None = None,
    ) -> None:
        self.script_path = Path(script_path).resolve()
        self.out_dir = Path(out_dir).resolve()
        self.host = host
        self.port = port
        self.poll_interval_s = poll_interval_s
        self.debounce_s = debounce_s
        self.access_token = new_access_token()
        self.access = LocalAccess(self.access_token, allowed_dev_origin=allowed_dev_origin)
        self.broker = PreviewEventBroker()
        self.revision = 0
        self._stop = threading.Event()
        self._httpd: ThreadingHTTPServer | None = None
        self._server_thread: threading.Thread | None = None
        self._watch_thread: threading.Thread | None = None
        self._last_fingerprint: bytes | None = None
        # Held while the watcher fingerprints the file, and by a writer of that file
        # until its new fingerprint is recorded: the server's own write is not an edit.
        self._fingerprint_lock = threading.Lock()

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}/"

    @property
    def ws_url(self) -> str:
        return f"ws://{self.host}:{self.port}/preview/ws"

    def start(self) -> "PreviewServer":
        self.out_dir.mkdir(parents=True, exist_ok=True)
        handler = _handler_factory(
            self.out_dir,
            self.broker,
            script_get_handler=getattr(self, "get_python_script", None),
            script_post_handler=getattr(self, "execute_python_code", None),
            solve_handler=getattr(self, "start_solve", None),
            mesh_handler=getattr(self, "mesh_jobs", None),
            project_handler=getattr(self, "project_info", None),
            profiles_handler=getattr(self, "profile_library", None),
            ifc_handler=getattr(self, "ifc_request", None),
            geometry_handler=getattr(self, "geometry_request", None),
            package_preview_handler=getattr(self, "package_preview", None),
            package_export_handler=getattr(self, "package_export", None),
            project_name=getattr(getattr(self, "project", None), "name", None),
            comm_handler=getattr(self, "code_aster_commands", None),
            bound_host=self.host,
            access=self.access,
        )
        self._httpd = LocalHTTPServer((self.host, self.port), handler)
        self.port = int(self._httpd.server_address[1])
        self._server_thread = threading.Thread(target=self._httpd.serve_forever, name="tuba-preview-http", daemon=True)
        self._server_thread.start()
        self._last_fingerprint = self.watch_fingerprint()
        # ponytail: ProjectStudioServer is the only server; its run_once is what the watcher
        # calls. Plan 7 splits this transport from the authoring session.
        self._watch_thread = threading.Thread(target=self._watch_loop, name="tuba-preview-watch", daemon=True)
        self._watch_thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        self.broker.close()
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
        if self._watch_thread is not None:
            self._watch_thread.join(timeout=2)
        if self._server_thread is not None:
            self._server_thread.join(timeout=2)

    def _watch_loop(self) -> None:
        # Compare against the attribute, not a copy: a server that writes the watched
        # file itself (ProjectStudioServer's POST /api/script) updates it, so the watcher
        # does not run the same content a second time.
        while not self._stop.wait(self.poll_interval_s):
            self.poll_review()
            if not self._source_changed():
                continue
            time.sleep(self.debounce_s)
            if not self._stop.is_set():
                self.run_once()

    def _source_changed(self) -> bool:
        # A run in flight records the bytes it consumed when it finishes. Comparing
        # against the fingerprint it has not written yet queued a second full run at
        # every studio start, which then held the script lock behind the review import.
        lock = getattr(self, "_script_lock", None)
        if lock is not None and not lock.acquire(blocking=False):
            return False
        try:
            with self._fingerprint_lock:
                current = self.watch_fingerprint()
                if current is None or current == self._last_fingerprint:
                    return False
                self._last_fingerprint = current
                return True
        finally:
            if lock is not None:
                lock.release()

    def poll_review(self) -> None:
        """Observe completed external project solves, when the host supports them."""

    def mark_saved(self, code: str, expected_revision: str | None = None) -> str:
        """Persist *code* as the watched script under the fingerprint lock, so the
        server's own write is not seen as an external edit."""
        with self._fingerprint_lock:
            from tuba.project.source import save_source, source_revision

            if expected_revision is None:
                expected_revision = source_revision(self.script_path)
            revision = save_source(self.script_path, code, expected_revision)
            # The watcher compares against this, so it does not run the same file again.
            self._last_fingerprint = self.watch_fingerprint()
            return revision

    def watch_fingerprint(self) -> bytes | None:
        """The dependency snapshot monitored by this preview surface."""
        return file_fingerprint(self.script_path)

    # --- Handler interface -------------------------------------------------
    # ProjectStudioServer overrides each of these. Declared here so the transport
    # routes against a stated contract rather than getattr-discovered names, and so
    # a bare PreviewServer fails loudly instead of 404-ing or AttributeError-ing.

    def run_once(self) -> None:
        """Re-run the watched script after it changes on disk."""
        raise NotImplementedError("PreviewServer.run_once")

    def get_python_script(self) -> dict[str, str]:
        raise NotImplementedError("PreviewServer.get_python_script")

    def execute_python_code(self, code: str, *, expected_revision: str | None = None) -> dict[str, Any]:
        raise NotImplementedError("PreviewServer.execute_python_code")

    def start_solve(self, force: bool = False) -> tuple[int, dict[str, Any]]:
        raise NotImplementedError("PreviewServer.start_solve")

    def project_info(self) -> dict[str, Any]:
        raise NotImplementedError("PreviewServer.project_info")

    def code_aster_commands(self, case: str) -> tuple[int, dict[str, Any]]:
        raise NotImplementedError("PreviewServer.code_aster_commands")


def _handler_factory(
    out_dir: Path,
    broker: PreviewEventBroker,
    script_get_handler: Any = None,
    script_post_handler: Any = None,
    solve_handler: Any = None,
    project_handler: Any = None,
    ifc_handler: Any = None,
    project_name: str | None = None,
    comm_handler: Any = None,
    bound_host: str = "127.0.0.1",
    profiles_handler: Any = None,
    geometry_handler: Any = None,
    mesh_handler: Any = None,
    package_preview_handler: Any = None,
    package_export_handler: Any = None,
    access: LocalAccess | None = None,
):
    # Host names a request may address; the Host check stops DNS rebinding.
    local_hosts = {"127.0.0.1", "localhost", "::1", bound_host.lower()}
    try:
        viewer_root = Path(viewer_assets_path()).resolve()
    except Exception:
        viewer_root = None
    access = access or LocalAccess(new_access_token())
    package_lock = threading.Lock()
    package_nonce = None

    class PreviewRequestHandler(BaseHTTPRequestHandler):
        server_version = "TubaPreview/0.1"

        def setup(self) -> None:
            super().setup()
            self.connection.settimeout(10)

        def log_message(self, _format: str, *_args: Any) -> None:
            return

        def do_OPTIONS(self) -> None:
            # Browser preflights carry header names, not their credential values.
            dev_preflight = (access.allowed_dev_origin is not None and
                             self.headers.get("Origin") == access.allowed_dev_origin and
                             access.browser_request(self.headers, self._local_host()))
            if not dev_preflight and not self._may_serve():
                self._refuse()
                return
            self.send_response(204)
            self._response_headers()
            self.end_headers()

        def do_GET(self) -> None:
            if not self._may_serve():
                # Also before the WebSocket upgrade: a foreign page must not subscribe to events.
                self._refuse()
                return
            parsed = urlparse(self.path)
            if parsed.path in {"/api/package/preview", "/api/package/export"} and package_export_handler is not None:
                if parsed.path.endswith("/export"):
                    self._json_response(405, {"ok": False, "error": "Package creation requires authenticated POST."})
                else:
                    self._package_request(parsed, export=False)
                return
            if parsed.path in {"/api/mesh", "/api/mesh/convergence"} and mesh_handler is not None:
                self._json_response(200, mesh_handler.status())
                return
            if parsed.path == "/api/ifc/export" and ifc_handler is not None:
                if not self._same_origin():
                    self._refuse()
                    return
                self._ifc_response("export", ifc_handler("export"))
                return
            if parsed.path == "/preview/ws":
                self._handle_websocket()
                return
            if ((parsed.path == "/api/project" and project_handler is not None) or
                    (parsed.path == "/api/profiles" and profiles_handler is not None)):
                handler = profiles_handler if parsed.path == "/api/profiles" else project_handler
                try:
                    data = json.dumps(handler()).encode("utf-8")
                    status = 200
                except Exception as exc:
                    data = json.dumps({"ok": False, "error": str(exc)}).encode("utf-8")
                    status = 500
                self.send_response(status)
                self._response_headers()
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            if parsed.path == "/api/comm" and comm_handler is not None:
                status, result = comm_handler(parse_qs(parsed.query).get("case", [""])[0])
                data = json.dumps(result).encode("utf-8")
                self.send_response(status)
                self._response_headers()
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            if parsed.path in ("/api/script", "/model.py"):
                if script_get_handler is not None:
                    try:
                        snapshot = script_get_handler()
                        data = json.dumps({"ok": True, **snapshot}).encode("utf-8")
                        self.send_response(200)
                        self._response_headers()
                        self.send_header("Content-Type", "application/json")
                        self.send_header("Cache-Control", "no-store")
                        self.send_header("Content-Length", str(len(data)))
                        self.end_headers()
                        self.wfile.write(data)
                        return
                    except Exception as exc:
                        self.send_response(500)
                        self._response_headers()
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(json.dumps({"ok": False, "error": str(exc)}).encode("utf-8"))
                        return
            self._serve_file(parsed.path)

        def do_POST(self) -> None:
            if not self._same_origin():
                # Every POST route mutates the model or runs Python on this machine.
                self._refuse()
                return
            parsed = urlparse(self.path)
            if parsed.path == "/api/package/export" and package_export_handler is not None:
                self._package_request(parsed, export=True)
                return
            if parsed.path in ("/api/geometry/preview", "/api/geometry/store") and geometry_handler is not None:
                try:
                    size = int(self.headers.get("Content-Length", ""))
                except ValueError:
                    size = 0
                if size > _MAX_BODY_BYTES:
                    self.close_connection = True
                    self._json_response(413, {"ok": False, "error": "Geometry upload exceeds 16 MiB"})
                    return
                if (size < 1 or self.headers.get("Transfer-Encoding")
                        or self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/octet-stream"):
                    self.close_connection = True
                    self._json_response(400, {"ok": False, "error": "Expected bounded nonempty application/octet-stream body"})
                    return
                body = self.rfile.read(size)
                if len(body) != size:
                    self.close_connection = True
                    self._json_response(400, {"ok": False, "error": "Geometry upload body is truncated"})
                    return
                status, result = geometry_handler(
                    parsed.path.rsplit("/", 1)[1], body,
                    self.headers.get("X-Geometry-Name", ""), self.headers.get("X-Geometry-Options", ""),
                )
                self._json_response(status, result)
                return
            if parsed.path in ("/api/ifc/preview", "/api/ifc/attach", "/api/ifc/remove", "/api/ifc/convert") and ifc_handler is not None:
                raw = self.headers.get("Content-Length")
                try:
                    size = int(raw) if raw is not None else 0
                except ValueError:
                    size = 0
                if size > _MAX_BODY_BYTES:
                    self.close_connection = True
                    self._ifc_response("error", (413, {"ok": False, "error": "IFC request exceeds 16 MiB"}))
                    return
                route = parsed.path.rsplit("/", 1)[1]
                media_type = "application/octet-stream" if route in ("preview", "attach") else "application/json"
                if size < 1 or (route in ("remove", "convert") and size > 65536) or self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != media_type:
                    self._ifc_response("error", (400, {"ok": False, "error": f"Expected nonempty {media_type} body"}))
                    return
                name = self.headers.get("X-IFC-Name", "reference.ifc")
                self._ifc_response(route, ifc_handler(route, self.rfile.read(size), name))
                return
            length = self._content_length()
            if length is None:
                # Answered before any body is read or handler runs: a value that would not parse, or was
                # too large to read, used to drop the connection.
                self.send_response(400)
                self._response_headers()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": "invalid Content-Length"}).encode("utf-8"))
                return
            parsed = urlparse(self.path)
            if parsed.path == "/api/solve" and solve_handler is not None:
                body = self.rfile.read(length) if length > 0 else b"{}"
                try:
                    payload = json.loads(body.decode("utf-8"))
                    force = payload.get("force", False) if isinstance(payload, dict) else None
                    if not isinstance(force, bool):
                        raise ValueError('a solve takes an optional boolean "force"')
                except ValueError as exc:
                    status, result = 400, {"ok": False, "error": str(exc)}
                else:
                    status, result = solve_handler(force=force)
                data = json.dumps(result).encode("utf-8")
                self.send_response(status)
                self._response_headers()
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            if parsed.path in {"/api/mesh", "/api/mesh/convergence"} and mesh_handler is not None:
                try:
                    payload = json.loads(self.rfile.read(length) if length else b"{}")
                    if not isinstance(payload, dict) or set(payload) - {"force", "expected_source_revision"}:
                        raise ValueError("A mesh request takes force and expected_source_revision.")
                    force = payload.get("force", False)
                    revision = payload.get("expected_source_revision")
                    if not isinstance(force, bool) or (revision is not None and (isinstance(revision, bool) or not isinstance(revision, int))):
                        raise ValueError("force must be boolean and expected_source_revision an integer.")
                    status, result = mesh_handler.start(force=force, expected_source_revision=revision,
                        mode="convergence" if parsed.path.endswith("/convergence") else "mesh")
                except (ValueError, TypeError) as exc:
                    status, result = 400, {"ok": False, "error": str(exc)}
                self._json_response(status, result)
                return
            if parsed.path in ("/api/script", "/model.py"):
                body = self.rfile.read(length) if length > 0 else b"{}"
                try:
                    payload = json.loads(body.decode("utf-8"))
                    code = payload.get("code") if isinstance(payload, dict) else None
                    if not isinstance(code, str):
                        # A missing "code" (an empty body too) saved an empty model.py; an explicit "" still does.
                        raise ValueError('a script save needs a string "code"')
                    expected_revision = payload.get("expected_revision")
                    if not isinstance(expected_revision, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_revision):
                        raise ValueError('a script save needs the "expected_revision" returned by GET /api/script')
                    if script_post_handler is not None:
                        result = script_post_handler(code, expected_revision=expected_revision)
                        self.send_response(409 if result.get("conflict") else (200 if result.get("ok") else 400))
                        self._response_headers()
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(json.dumps(result).encode("utf-8"))
                        return
                    else:
                        raise ValueError("No script handler configured on server.")
                except Exception as exc:
                    self.send_response(400)
                    self._response_headers()
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": False, "error": str(exc)}).encode("utf-8"))
                    return
            self.send_response(404)
            self._response_headers()
            self.end_headers()

        def do_DELETE(self) -> None:
            if not self._same_origin():
                self._refuse()
                return
            path = urlparse(self.path).path
            if path.startswith("/api/mesh/") and mesh_handler is not None:
                self._json_response(*mesh_handler.cancel(path.removeprefix("/api/mesh/")))
            else:
                self._json_response(404, {"ok": False, "error": "No such route."})

        def _json_response(self, status: int, result: dict) -> None:
            data = json.dumps(result, allow_nan=False).encode("utf-8")
            self.send_response(status)
            self._response_headers()
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _package_request(self, parsed, *, export: bool) -> None:
            nonlocal package_nonce
            if not package_lock.acquire(blocking=False):
                self._json_response(409, {"ok": False, "error": "Another package operation is running."})
                return
            streaming = False
            try:
                if export:
                    length = self._content_length()
                    if (length is None or not 0 < length <= 4096 or parsed.query
                            or self.headers.get("Transfer-Encoding")
                            or self.headers.get_content_type() != "application/json"):
                        self.close_connection = True
                        raise ValueError("Package export takes a JSON preview nonce, results and format.")
                    payload = json.loads(self.rfile.read(length))
                    if (not isinstance(payload, dict) or set(payload) != {"operation_nonce", "results", "format"}
                            or not isinstance(payload["results"], bool) or payload["format"] not in {"zip", "tgz"}):
                        raise ValueError("Package export takes a JSON preview nonce, results and format.")
                    if (package_nonce is None or payload["operation_nonce"] != package_nonce[0]
                            or payload["results"] != package_nonce[1] or time.monotonic() > package_nonce[2]):
                        self._json_response(409, {"ok": False, "error": "Preview the project again before exporting."})
                        return
                    package_nonce = None
                    archive_format = payload["format"]
                    with package_export_handler(payload["results"], archive_format) as path, path.open("rb") as source:
                        streaming = True
                        self.send_response(200)
                        self._response_headers()
                        self.send_header("Content-Type", "application/gzip" if archive_format == "tgz" else "application/zip")
                        self.send_header("Content-Disposition", f'attachment; filename="{path.name}"')
                        self.send_header("Content-Length", str(path.stat().st_size))
                        self.send_header("Cache-Control", "no-store")
                        self.end_headers()
                        shutil.copyfileobj(source, self.wfile)
                else:
                    options = parse_qs(parsed.query, keep_blank_values=True)
                    if set(options) - {"results"} or options.get("results", ["0"]) not in (["0"], ["1"]):
                        raise ValueError("Package preview takes results=0|1.")
                    include_results = options.get("results") == ["1"]
                    result = package_preview_handler(include_results)
                    nonce = new_access_token()
                    package_nonce = (nonce, include_results, time.monotonic() + 60)
                    self._json_response(200, {**result, "operation_nonce": nonce})
            except Exception as exc:
                if streaming:
                    self.close_connection = True
                else:
                    self._json_response(400, {"ok": False, "error": str(exc)})
            finally:
                package_lock.release()

        def _ifc_response(self, route: str, response: tuple[int, Any]) -> None:
            status, result = response
            if isinstance(result, bytes):
                data = result
                media_type = "application/x-step" if route == "export" else "application/zip"
                base = re.sub(r"[^A-Za-z0-9_-]", "_", project_name or out_dir.name)[:64] or "project"
                filename = f"{base}.ifc" if route == "export" else f"{base}-ifc-pipes.zip"
            else:
                data = json.dumps(result).encode("utf-8")
                media_type, filename = "application/json", None
            self.send_response(status)
            self._response_headers()
            self.send_header("Content-Type", media_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            if filename:
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(data)

        def _public_asset(self, raw_path: str) -> Path | None:
            relative = unquote(raw_path).lstrip("/") or "index.html"
            if viewer_root is None or (relative != "index.html" and not relative.startswith("assets/")):
                return None
            candidate = (viewer_root / relative).resolve()
            return candidate if candidate.is_relative_to(viewer_root) and candidate.is_file() else None

        def _serve_file(self, raw_path: str) -> None:
            relative = unquote(raw_path).lstrip("/") or "index.html"
            public = self._public_asset(raw_path)
            # Anonymous bootstrap can only read packaged code, never an out_dir shadow.
            if public is not None and (relative == "index.html" or not access.authenticated(self.headers)):
                target = public
            else:
                candidates = [out_dir / relative]
                if "/" in relative:
                    candidates.append(out_dir / relative.split("/", 1)[1])
                candidates.extend(out_dir / sub / relative for sub in ("build", "review"))
                target = next((candidate.resolve() for candidate in candidates
                               if candidate.resolve().is_relative_to(out_dir) and candidate.is_file()), None)
                if target is None and viewer_root is not None:
                    candidate = (viewer_root / relative).resolve()
                    if candidate.is_relative_to(viewer_root) and candidate.is_file():
                        target = candidate
            if target is None:
                self.send_response(404)
                self._response_headers()
                self.end_headers()
                return
            data = target.read_bytes()
            self.send_response(200)
            self._response_headers(bundle=target.is_relative_to(out_dir))
            self.send_header("Content-Type", mimetypes.guess_type(str(target))[0] or "application/octet-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _handle_websocket(self) -> None:
            key = self.headers.get("Sec-WebSocket-Key")
            if not key:
                self.send_response(400)
                self.end_headers()
                return
            accept = base64.b64encode(hashlib.sha1((key + _WEBSOCKET_GUID).encode("ascii")).digest()).decode("ascii")
            self.send_response(101, "Switching Protocols")
            self.send_header("Upgrade", "websocket")
            self.send_header("Connection", "Upgrade")
            self.send_header("Sec-WebSocket-Accept", accept)
            if "tuba-preview" in [value.strip() for value in self.headers.get("Sec-WebSocket-Protocol", "").split(",")]:
                self.send_header("Sec-WebSocket-Protocol", "tuba-preview")
            self.end_headers()

            client = _WebSocketClient(self.connection)
            # Broadcasts reach every viewer do_GET let in (the Vite dev server subscribes cross-origin).
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
            finally:
                broker.remove(client)

        def _local_host(self) -> str | None:
            """The Host header when it names a local host name, else None."""
            host = self.headers.get("Host", "")
            try:
                hostname = urlparse(f"//{host}").hostname
            except ValueError:
                return None
            return host if hostname in local_hosts and host == f"{hostname}:{self.server.server_port}" else None

        def _same_origin(self) -> bool:
            return (access.browser_request(self.headers, self._local_host(), mutate=True)
                    and access.authenticated(self.headers))

        def _may_serve(self) -> bool:
            path = urlparse(self.path).path
            return (access.browser_request(self.headers, self._local_host(), bootstrap=path in {"/", "/index.html"}) and
                    (access.authenticated(self.headers, websocket=path == "/preview/ws")
                     or self._public_asset(path) is not None))

        def _content_length(self) -> int | None:
            """The request's Content-Length, 0 when absent; None when it will not parse, is negative, or
            is above _MAX_BODY_BYTES."""
            try:
                length = int(self.headers.get("Content-Length", 0))
            except ValueError:
                return None
            return length if 0 <= length <= _MAX_BODY_BYTES else None

        def _refuse(self) -> None:
            # A header that will not parse, or a body too large to drain, still gets its 403.
            length = self._content_length() or 0
            if 0 < length <= 8192:
                # Drain the body: closing with unread input resets the connection
                # before the client reads the 403.
                self.rfile.read(length)
            self.close_connection = True
            self.send_response(403)
            self._response_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": False, "error": "cross-origin request refused"}).encode("utf-8"))

        def _response_headers(self, *, bundle: bool = False) -> None:
            self.send_header("Vary", "Origin, Sec-Fetch-Site")
            if access.allowed_dev_origin is not None and self.headers.get("Origin") == access.allowed_dev_origin:
                self.send_header("Access-Control-Allow-Origin", access.allowed_dev_origin)
                self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-IFC-Name, X-Geometry-Name, X-Geometry-Options")
                self.send_header("Access-Control-Expose-Headers", "Content-Disposition")
            self.send_header("Cross-Origin-Resource-Policy", "same-origin")
            self.send_header("X-Frame-Options", "SAMEORIGIN")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            if bundle:
                from tuba.visualization.viewer import BUNDLE_CONTENT_SECURITY_POLICY
                policy = BUNDLE_CONTENT_SECURITY_POLICY
            else:
                policy = "frame-ancestors 'self' vscode-webview: vscode-file:"
            self.send_header("Content-Security-Policy", policy)

    return PreviewRequestHandler


class _WebSocketClient:
    def __init__(self, connection: socket.socket) -> None:
        self.connection = connection
        self._lock = threading.Lock()

    def send_json(self, event: dict[str, Any]) -> None:
        self.send_text(json.dumps(event, sort_keys=True))

    def send_text(self, text: str) -> None:
        self._send_frame(0x1, text.encode("utf-8"))

    def send_pong(self, payload: bytes) -> None:
        self._send_frame(0xA, payload)

    def close(self) -> None:
        try:
            self._send_frame(0x8, b"")
            # shutdown before close: the handler's rfile still references the socket, so
            # close() alone would leave its blocking read waiting forever.
            self.connection.shutdown(socket.SHUT_RDWR)
            self.connection.close()
        except OSError:
            return

    def _send_frame(self, opcode: int, payload: bytes) -> None:
        length = len(payload)
        if length < 126:
            header = bytes([0x80 | opcode, length])
        elif length < 65536:
            header = bytes([0x80 | opcode, 126]) + struct.pack("!H", length)
        else:
            header = bytes([0x80 | opcode, 127]) + struct.pack("!Q", length)
        with self._lock:
            self.connection.sendall(header + payload)


def file_fingerprint(path: Path) -> bytes | None:
    try:
        return hashlib.sha256(path.read_bytes()).digest()
    except (FileNotFoundError, PermissionError):
        # Missing file: nothing to run. Unreadable file: a writer holds it mid-save;
        # report nothing so the watcher retries on the next poll instead of dying and
        # freezing the viewer on a stale model.
        return None


_WEBSOCKET_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
# Studio request bodies are small model scripts.
_MAX_BODY_BYTES = 16 * 1024 * 1024


