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
import os
import re
import socket
import struct
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

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
    ) -> None:
        self.script_path = Path(script_path).resolve()
        self.out_dir = Path(out_dir).resolve()
        self.host = host
        self.port = port
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
            comm_handler=getattr(self, "code_aster_commands", None),
            bound_host=self.host,
        )
        self._httpd = LocalHTTPServer((self.host, self.port), handler)
        self.port = int(self._httpd.server_address[1])
        self._server_thread = threading.Thread(target=self._httpd.serve_forever, name="tuba-preview-http", daemon=True)
        self._server_thread.start()
        self._last_fingerprint = file_fingerprint(self.script_path)
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
                current = file_fingerprint(self.script_path)
                if current is None or current == self._last_fingerprint:
                    continue
                self._last_fingerprint = current
            time.sleep(self.debounce_s)
            if not self._stop.is_set():
                self.run_once()

    def mark_saved(self, code: str) -> None:
        """Persist *code* as the watched script under the fingerprint lock, so the
        server's own write is not seen as an external edit."""
        with self._fingerprint_lock:
            # newline="": write what the client sent. Text mode on Windows turns a CRLF
            # body into CR CR LF, and Python then counts every line twice in tracebacks.
            self.script_path.write_text(code, encoding="utf-8", newline="")
            # The watcher compares against this, so it does not run the same file again.
            self._last_fingerprint = file_fingerprint(self.script_path)

    # --- Handler interface -------------------------------------------------
    # ProjectStudioServer overrides each of these. Declared here so the transport
    # routes against a stated contract rather than getattr-discovered names, and so
    # a bare PreviewServer fails loudly instead of 404-ing or AttributeError-ing.

    def run_once(self) -> None:
        """Re-run the watched script after it changes on disk."""
        raise NotImplementedError("PreviewServer.run_once")

    def get_python_script(self) -> str:
        raise NotImplementedError("PreviewServer.get_python_script")

    def execute_python_code(self, code: str) -> dict[str, Any]:
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
    comm_handler: Any = None,
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

            # Root index.html always serves the packaged 3D Web Studio viewer when
            # available; every other path resolves as bytes from out_dir, then viewer_root.
            if relative == "index.html" and viewer_root is not None and (viewer_root / "index.html").is_file():
                target = (viewer_root / "index.html").resolve()
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
                        # Sub-bundle fallback: e.g. /scene.json -> out_dir/build/scene.json
                        for sub in ("build", "review"):
                            cand_sub = (out_dir / sub / relative).resolve()
                            if os.path.commonpath([str(out_dir), str(cand_sub)]) == str(out_dir) and cand_sub.is_file():
                                target = cand_sub
                                break
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


