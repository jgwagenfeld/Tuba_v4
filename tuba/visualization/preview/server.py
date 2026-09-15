"""The studio's local HTTP/WebSocket transport and ``ProjectStudioServer``, which serves
a project folder's Build and Review bundles."""

from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import re
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


class PreviewEventBroker:
    def __init__(self) -> None:
        self._clients: set[_WebSocketClient] = set()
        self._events: list[dict[str, Any]] = []
        self._lock = threading.RLock()
        self.closed = False

    @property
    def events(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._events)

    def add(self, client: "_WebSocketClient") -> None:
        with self._lock:
            self._clients.add(client)
            events = list(self._events)
        for event in events:
            client.send_json(event)

    def remove(self, client: "_WebSocketClient") -> None:
        with self._lock:
            self._clients.discard(client)

    def broadcast(self, event: dict[str, Any]) -> None:
        with self._lock:
            self._events.append(event)
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
        timeout_s: float = 5.0,
        poll_interval_s: float = 0.25,
        debounce_s: float = 0.2,
    ) -> None:
        self.script_path = Path(script_path).resolve()
        self.out_dir = Path(out_dir).resolve()
        self.host = host
        self.port = port
        self.timeout_s = timeout_s
        self.poll_interval_s = poll_interval_s
        self.debounce_s = debounce_s
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
            with self._fingerprint_lock:
                current = _file_fingerprint(self.script_path)
                if current is None or current == self._last_fingerprint:
                    continue
                self._last_fingerprint = current
            time.sleep(self.debounce_s)
            if not self._stop.is_set():
                self.run_once()


def _handler_factory(
    out_dir: Path,
    broker: PreviewEventBroker,
    script_get_handler: Any = None,
    script_post_handler: Any = None,
    solve_handler: Any = None,
    project_handler: Any = None,
    bound_host: str = "127.0.0.1",
):
    # Host names a request may address; the Host check stops DNS rebinding.
    local_hosts = {"127.0.0.1", "localhost", "::1", bound_host.lower()}
    try:
        viewer_root = Path(viewer_assets_path()).resolve()
    except Exception:
        viewer_root = None

    class PreviewRequestHandler(BaseHTTPRequestHandler):
        server_version = "TubaPreview/0.1"

        def log_message(self, _format: str, *_args: Any) -> None:
            return

        def do_OPTIONS(self) -> None:
            if not self._may_serve():
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
            if parsed.path == "/preview/ws":
                self._handle_websocket()
                return
            if parsed.path == "/api/project" and project_handler is not None:
                data = json.dumps(project_handler()).encode("utf-8")
                self.send_response(200)
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
                        code = script_get_handler()
                        data = json.dumps({"ok": True, "code": code}).encode("utf-8")
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
                if length > 0:
                    self.rfile.read(length)
                status, result = solve_handler()
                data = json.dumps(result).encode("utf-8")
                self.send_response(status)
                self._response_headers()
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            if parsed.path in ("/api/script", "/model.py"):
                body = self.rfile.read(length) if length > 0 else b"{}"
                try:
                    payload = json.loads(body.decode("utf-8"))
                    code = payload.get("code") if isinstance(payload, dict) else None
                    if not isinstance(code, str):
                        # A missing "code" (an empty body too) saved an empty model.py; an explicit "" still does.
                        raise ValueError('a script save needs a string "code"')
                    if script_post_handler is not None:
                        result = script_post_handler(code)
                        self.send_response(200 if result.get("ok") else 400)
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

        def _serve_file(self, raw_path: str) -> None:
            relative = unquote(raw_path.lstrip("/"))
            if not relative:
                relative = "index.html"

            # Direct report routes
            if relative in ("report", "report.html"):
                for cand in (out_dir / "report.html", out_dir / "index.html"):
                    if cand.is_file():
                        target = cand
                        break
                else:
                    self.send_response(404)
                    self._response_headers()
                    self.end_headers()
                    return
            # Bundle prefix routes
            elif relative.startswith("bundle/"):
                bundle_rel = relative.removeprefix("bundle/").lstrip("/")
                target = (out_dir / (bundle_rel or "index.html")).resolve()
                if not (os.path.commonpath([str(out_dir), str(target)]) == str(out_dir) and target.is_file()):
                    if bundle_rel == "index.html" and (out_dir / "report.html").is_file():
                        target = (out_dir / "report.html").resolve()
                    else:
                        self.send_response(404)
                        self._response_headers()
                        self.end_headers()
                        return
            # Root index.html: ALWAYS serve the packaged 3D Web Studio viewer if available
            elif relative == "index.html" and viewer_root is not None and (viewer_root / "index.html").is_file():
                target = (viewer_root / "index.html").resolve()
            # Standard file resolution: out_dir first, then viewer_root
            else:
                target = (out_dir / relative).resolve()
                if not (os.path.commonpath([str(out_dir), str(target)]) == str(out_dir) and target.is_file()):
                    # Prefix fallback: e.g. /code-aster-review/scene.json -> scene.json
                    if "/" in relative:
                        stripped = relative.split("/", 1)[1]
                        cand = (out_dir / stripped).resolve()
                        if os.path.commonpath([str(out_dir), str(cand)]) == str(out_dir) and cand.is_file():
                            target = cand
                    if not target.is_file():
                        if viewer_root is not None:
                            candidate = (viewer_root / relative).resolve()
                            if os.path.commonpath([str(viewer_root), str(candidate)]) == str(viewer_root) and candidate.is_file():
                                target = candidate
                            else:
                                self.send_response(404)
                                self._response_headers()
                                self.end_headers()
                                return
                        else:
                            self.send_response(404)
                            self._response_headers()
                            self.end_headers()
                            return

            data = target.read_bytes()
            self.send_response(200)
            self._response_headers()
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
            return host if hostname in local_hosts else None

        def _same_origin(self) -> bool:
            """Whether this request may mutate: it addresses a local host name and comes
            from this server's own page or from a non-browser client (no Origin)."""
            host = self._local_host()
            origin = self.headers.get("Origin")
            return host is not None and (origin is None or origin == f"http://{host}")

        def _may_serve(self) -> bool:
            """Whether this request may read: as for a mutation, or from a loopback page
            (the Vite dev server subscribes and fetches bundles cross-origin)."""
            return self._same_origin() or (self._local_host() is not None and self._loopback_origin())

        def _loopback_origin(self) -> bool:
            """Whether Origin is a loopback page, such as the Vite dev server on localhost:5173."""
            origin = self.headers.get("Origin", "")
            return re.fullmatch(r"http://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?", origin) is not None

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
            if length > 0:
                # Drain the body: closing with unread input resets the connection
                # before the client reads the 403.
                self.rfile.read(length)
            self.send_response(403)
            self._response_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": False, "error": "cross-origin request refused"}).encode("utf-8"))

        def _response_headers(self) -> None:
            # Sent with every response this handler writes, except the WebSocket route's own (its 400 and
            # the 101 upgrade) and stdlib send_error pages, for three purposes:
            # - CORS only for loopback pages (the Vite dev server fetches bundles cross-origin), never
            #   "*", which let any web page read model.py. Vary on every response, so a cached answer
            #   without the header is not reused for a loopback page.
            # - No cross-site embedding: another site cannot load a response through <img>, <script> or
            #   <link>. CORP binds only no-cors loads, so a loopback page's CORS fetches still work.
            # - No framing by another site, which could trick a click on Solve or a save. Allowed framers:
            #   the studio itself, localhost and 127.0.0.1 pages on any port, and the VS Code desktop app,
            #   so the studio can sit in an IDE preview pane such as Simple Browser. [::1] pages may read
            #   through CORS but cannot frame: CSP host sources cannot name IPv6 literals. frame-ancestors
            #   must match every ancestor, not only the parent: Simple Browser frames the studio from a
            #   vscode-webview: page, which sits inside the window's vscode-file: page, so both schemes
            #   are listed. Neither admits a website. X-Frame-Options is for legacy browsers only: where
            #   CSP is supported, a frame-ancestors directive overrides it.
            self.send_header("Vary", "Origin")
            if self._loopback_origin():
                self.send_header("Access-Control-Allow-Origin", self.headers["Origin"])
                self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Cross-Origin-Resource-Policy", "same-site")
            self.send_header("X-Frame-Options", "SAMEORIGIN")
            self.send_header("Content-Security-Policy", "frame-ancestors 'self' http://localhost:* http://127.0.0.1:* vscode-webview: vscode-file:")

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


def _file_fingerprint(path: Path) -> bytes | None:
    try:
        return hashlib.sha256(path.read_bytes()).digest()
    except FileNotFoundError:
        return None


_WEBSOCKET_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
# Studio request bodies are small model scripts.
_MAX_BODY_BYTES = 16 * 1024 * 1024


class ProjectStudioServer(PreviewServer):
    """The studio for a project folder: ``model.py`` drives Build, ``study.py`` drives Review.

    The live model scene is the ``build/`` bundle and the solved or imported review is
    ``review/``. A Run never overwrites a review, and Review never shows results for a
    model that has changed since without saying so (``review_stale``): a review is stale
    when an operation it was solved for would now attest a different identity.
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
        from tuba.project.freshness import attested_identities

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
        # review_stale runs on every save, and a review scene can be tens of MB: read its identities
        # once per bundle, here for a bundle left on disk and in _produce_review for each new one.
        self._review_identities = attested_identities(self.out_dir / "review")
        self._solve_lock = threading.Lock()
        # Busy with a review (the startup import or a Solve); _preparing marks the import.
        self._solving = False
        self._preparing = False

    def start(self) -> "ProjectStudioServer":
        super().start()
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

    def _prepare_review(self, namespace: dict[str, Any], artifact_dir: Path | None) -> None:
        try:
            self._produce_review(namespace, artifact_dir=artifact_dir)
        except Exception as exc:
            self.review_error = f"{type(exc).__name__}: {exc}"
            self.broker.broadcast({"type": "review_failed", "error": self.review_error})
        else:
            self.broker.broadcast({
                "type": "review_ready",
                "bundle": "review",
                "bundle_url": f"{self.base_url}review/",
                "review_stale": self.review_stale,
            })
        finally:
            with self._solve_lock:
                self._solving = self._preparing = False

    @property
    def review_stale(self) -> bool:
        """Spec decision 15: an operation the review was solved for would now attest a different identity."""
        from tuba.project.freshness import stale_operations

        if self.model is None or self.study is None:
            return False
        attested = self._review_identities
        if not attested:
            return False
        try:
            stale = stale_operations(
                self.model,
                attested,
                solver_options=getattr(self.study, "SOLVER_OPTIONS", None),
                volume_export=getattr(self.study, "VOLUME_EXPORT", None),
            )
        except (TypeError, ValueError):
            # study.py's own solver options are invalid: staleness cannot be judged, and a Solve reports why.
            return False
        return bool(stale)

    def _publish_scene(self) -> dict[str, Any]:
        from tuba.visualization.builders import build_visualization_scene

        self.revision += 1
        scene = build_visualization_scene(self.model)
        staging = self.out_dir / ".build-staging"
        shutil.rmtree(staging, ignore_errors=True)
        write_scene_bundle(scene, staging)
        self._swap_bundle("build", staging)
        stale = self.review_stale
        event = {
            "type": "scene_reloaded",
            "revision": self.revision,
            "bundle_revision": self.revision,
            "scene_id": scene.scene_id,
            "scene_uri": "scene.json",
            "bundle": "build",
            "bundle_url": f"{self.base_url}build/",
            "review_stale": stale,
            "results_stale": stale,
            "objects": len(scene.objects),
            "issues": len(scene.issues),
        }
        self.broker.broadcast(event)
        return event

    def _swap_bundle(self, name: str, source: Path) -> None:
        """Move a finished bundle into place, so a half-written one is never served."""
        target = self.out_dir / name
        retired = self.out_dir / f".{name}-retired"
        shutil.rmtree(retired, ignore_errors=True)
        if target.exists():
            target.rename(retired)
        Path(source).rename(target)
        shutil.rmtree(retired, ignore_errors=True)

    def _produce_review(self, namespace: dict[str, Any], *, artifact_dir: Path | None, force: bool = False) -> None:
        from tuba.project.freshness import attested_identities

        work = self.out_dir / ".review-work"
        shutil.rmtree(work, ignore_errors=True)
        root = self.study.build_review(namespace, work, artifact_dir=artifact_dir, force=force)
        identities = attested_identities(Path(root))
        self._swap_bundle("review", Path(root))
        self._review_identities = identities
        self.review_error = None
        shutil.rmtree(work, ignore_errors=True)

    def project_info(self) -> dict[str, Any]:
        return {
            "ok": True,
            "name": self.project.name,
            "has_study": self.study is not None,
            "can_solve": self.study is not None and self.namespace is not None,
            "solves": bool(getattr(self.study, "LOAD_CASES", ())),
            "has_review": (self.out_dir / "review" / "scene.json").is_file(),
            "review_stale": self.review_stale,
            "review_error": self.review_error,
            "solving": self._solving and not self._preparing,
            "preparing_review": self._preparing,
        }

    def start_solve(self) -> tuple[int, dict[str, Any]]:
        if self.study is None:
            return 400, {"ok": False, "error": f"{self.project.name} has no study.py to solve."}
        if self.namespace is None:
            return 400, {"ok": False, "error": "model.py has not run successfully yet."}
        with self._solve_lock:
            if self._solving:
                busy = "The review is still being imported." if self._preparing else "A solve is already running."
                return 409, {"ok": False, "error": busy}
            self._solving = True
        threading.Thread(target=self._solve, args=(self.namespace,), name="tuba-studio-solve", daemon=True).start()
        return 202, {"ok": True}

    def _solve(self, namespace: dict[str, Any]) -> None:
        self.broker.broadcast({"type": "solve_started"})
        try:
            self._produce_review(namespace, artifact_dir=None, force=True)
        except KeyboardInterrupt:
            raise
        except BaseException as exc:  # a study calling sys.exit() fails the solve, not the server
            self.review_error = f"{type(exc).__name__}: {exc}"
            self.broker.broadcast({"type": "solve_failed", "error": self.review_error})
        else:
            self.broker.broadcast({
                "type": "solve_finished",
                "bundle": "review",
                "bundle_url": f"{self.base_url}review/",
                "review_stale": self.review_stale,
            })
        finally:
            with self._solve_lock:
                self._solving = False


def _script_error_line(exc: BaseException, script_path: Path) -> int | None:
    """The model.py line to blame for *exc*: a syntax error's own line, else the
    innermost traceback frame in the script; None when the script is not on the stack."""
    script = script_path.resolve()
    if isinstance(exc, SyntaxError) and exc.filename and Path(exc.filename).resolve() == script:
        return exc.lineno
    lines = [
        lineno
        for frame, lineno in traceback.walk_tb(exc.__traceback__)
        if Path(frame.f_code.co_filename).resolve() == script
    ]
    return lines[-1] if lines else None


