"""Local HTTP/WebSocket preview server for trusted Tuba scripts."""

from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import socket
import struct
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from tuba.model import TubaModel
from tuba.patches import ModelPatch
from tuba.visualization.live_preview import preview_json_patch
from tuba.visualization.scene import SceneDiagnostic, VisualizationScene
from tuba.visualization.web_export import write_scene_bundle


@dataclass(frozen=True)
class PreviewRunResult:
    revision: int
    events: list[dict[str, Any]]
    ok: bool
    duration_ms: int


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


def execute_preview_script(
    script_path: str | Path,
    out_dir: str | Path,
    *,
    timeout_s: float = 5.0,
    cwd: str | Path | None = None,
) -> dict[str, Any]:
    script = Path(script_path).resolve()
    out = Path(out_dir).resolve()
    if not script.exists() or not script.is_file():
        diagnostic = _diagnostic("visualization.preview.missing_script", f"Preview script does not exist: {script}", str(script))
        return {"ok": False, "diagnostics": [diagnostic.to_dict()], "messages": [_diagnostic_event(diagnostic)]}

    cmd = [sys.executable, "-m", "tuba.visualization.preview._runner", str(script), "--out", str(out)]
    env = os.environ.copy()
    repo_root = Path(__file__).resolve().parents[3]
    env["PYTHONPATH"] = os.pathsep.join(part for part in [str(repo_root), env.get("PYTHONPATH", "")] if part)
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(cwd or script.parent),
            env=env,
            text=True,
            capture_output=True,
            timeout=_preview_subprocess_timeout(timeout_s),
            check=False,
        )
    except subprocess.TimeoutExpired:
        diagnostic = _diagnostic(
            "visualization.preview.timeout",
            f"Preview script timed out after {timeout_s:g}s.",
            str(script),
        )
        return {"ok": False, "diagnostics": [diagnostic.to_dict()], "messages": [_diagnostic_event(diagnostic)]}

    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        diagnostic = _diagnostic(
            "visualization.preview.invalid_runner_output",
            (completed.stderr or completed.stdout or "Preview runner produced no JSON output.").strip(),
            str(script),
        )
        return {"ok": False, "diagnostics": [diagnostic.to_dict()], "messages": [_diagnostic_event(diagnostic)]}

    if completed.returncode != 0:
        payload["ok"] = False
    return payload


def run_preview_once(
    script_path: str | Path,
    out_dir: str | Path,
    *,
    revision: int = 1,
    timeout_s: float = 5.0,
    bundle_url: str = ".",
    broker: PreviewEventBroker | None = None,
) -> PreviewRunResult:
    started = time.perf_counter()
    events: list[dict[str, Any]] = [{"type": "run_started", "revision": revision}]
    _broadcast_all(broker, events)

    payload = execute_preview_script(script_path, out_dir, timeout_s=timeout_s)
    for message in payload.get("messages", []):
        event = dict(message)
        event.setdefault("revision", revision)
        if event.get("type") == "scene_reloaded":
            event.setdefault("scene_uri", "scene.json")
            event.setdefault("bundle_url", bundle_url)
            event["bundle_revision"] = revision
        events.append(event)
        _broadcast_all(broker, [event])

    duration_ms = int((time.perf_counter() - started) * 1000)
    finished = {"type": "run_finished", "revision": revision, "duration_ms": duration_ms, "ok": bool(payload.get("ok"))}
    events.append(finished)
    _broadcast_all(broker, [finished])
    return PreviewRunResult(revision=revision, events=events, ok=bool(payload.get("ok")), duration_ms=duration_ms)


def execute_patch_preview(
    base_model_path: str | Path,
    patch_path: str | Path,
    out_dir: str | Path,
) -> dict[str, Any]:
    """Dry-run a JSON ModelPatch file against a committed model snapshot."""
    model_file = Path(base_model_path).resolve()
    patch_file = Path(patch_path).resolve()
    out = Path(out_dir).resolve()

    try:
        model_payload = _read_json_file(model_file, "visualization.patch_preview.invalid_model")
        patch_payload = _read_json_file(patch_file, "visualization.patch_preview.invalid_patch")
        model = TubaModel.from_dict(model_payload)
        patch = ModelPatch.from_dict(patch_payload)
        preview = preview_json_patch(model, patch)
        if preview.diagnostics:
            first = preview.diagnostics[0]
            raise _PatchPreviewError(
                _diagnostic(
                    "visualization.patch_preview.invalid_patch",
                    first.message,
                    str(patch_file),
                )
            )
        if preview.scene is None:
            raise _PatchPreviewError(
                _diagnostic(
                    "visualization.patch_preview.invalid_patch",
                    "Patch preview did not produce a scene.",
                    str(patch_file),
                )
            )
        write_scene_bundle(preview.scene, out)
        return {
            "ok": True,
            "diagnostics": [],
            "messages": [
                {
                    "type": "scene_reloaded",
                    "scene_uri": "scene.json",
                    "scene_id": preview.scene.scene_id,
                    "objects": len(preview.scene.objects),
                    "issues": len(preview.scene.issues),
                }
            ],
            "scene": preview.scene.to_dict(),
        }
    except _PatchPreviewError as exc:
        return _patch_preview_failure(out, exc.diagnostic)
    except Exception as exc:
        diagnostic = _diagnostic("visualization.patch_preview.invalid_patch", str(exc), str(patch_file))
        return _patch_preview_failure(out, diagnostic)


def run_patch_preview_once(
    base_model_path: str | Path,
    patch_path: str | Path,
    out_dir: str | Path,
    *,
    revision: int = 1,
    bundle_url: str = ".",
    broker: PreviewEventBroker | None = None,
) -> PreviewRunResult:
    started = time.perf_counter()
    events: list[dict[str, Any]] = [{"type": "run_started", "revision": revision, "mode": "json_patch"}]
    _broadcast_all(broker, events)

    payload = execute_patch_preview(base_model_path, patch_path, out_dir)
    for message in payload.get("messages", []):
        event = dict(message)
        event.setdefault("revision", revision)
        if event.get("type") == "scene_reloaded":
            event.setdefault("scene_uri", "scene.json")
            event.setdefault("bundle_url", bundle_url)
            event["bundle_revision"] = revision
        events.append(event)
        _broadcast_all(broker, [event])

    duration_ms = int((time.perf_counter() - started) * 1000)
    finished = {"type": "run_finished", "revision": revision, "duration_ms": duration_ms, "ok": bool(payload.get("ok"))}
    events.append(finished)
    _broadcast_all(broker, [finished])
    return PreviewRunResult(revision=revision, events=events, ok=bool(payload.get("ok")), duration_ms=duration_ms)


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

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}/"

    @property
    def ws_url(self) -> str:
        return f"ws://{self.host}:{self.port}/preview/ws"

    def start(self, *, run_initial: bool = True) -> "PreviewServer":
        self.out_dir.mkdir(parents=True, exist_ok=True)
        handler = _handler_factory(self.out_dir, self.broker)
        self._httpd = ThreadingHTTPServer((self.host, self.port), handler)
        self.port = int(self._httpd.server_address[1])
        self._server_thread = threading.Thread(target=self._httpd.serve_forever, name="tuba-preview-http", daemon=True)
        self._server_thread.start()
        self._last_fingerprint = _file_fingerprint(self.script_path)
        if run_initial:
            self.run_once()
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

    def run_once(self) -> PreviewRunResult:
        self.revision += 1
        return run_preview_once(
            self.script_path,
            self.out_dir,
            revision=self.revision,
            timeout_s=self.timeout_s,
            bundle_url=self.base_url,
            broker=self.broker,
        )

    def _watch_loop(self) -> None:
        last_fingerprint = self._last_fingerprint
        while not self._stop.wait(self.poll_interval_s):
            current = _file_fingerprint(self.script_path)
            if current is None or current == last_fingerprint:
                continue
            last_fingerprint = current
            time.sleep(self.debounce_s)
            if not self._stop.is_set():
                self.run_once()


class PatchPreviewServer(PreviewServer):
    def __init__(
        self,
        base_model_path: str | Path,
        patch_path: str | Path,
        out_dir: str | Path,
        *,
        host: str = "127.0.0.1",
        port: int = 8765,
        timeout_s: float = 5.0,
        poll_interval_s: float = 0.25,
        debounce_s: float = 0.2,
    ) -> None:
        self.base_model_path = Path(base_model_path).resolve()
        super().__init__(
            patch_path,
            out_dir,
            host=host,
            port=port,
            timeout_s=timeout_s,
            poll_interval_s=poll_interval_s,
            debounce_s=debounce_s,
        )

    def run_once(self) -> PreviewRunResult:
        self.revision += 1
        return run_patch_preview_once(
            self.base_model_path,
            self.script_path,
            self.out_dir,
            revision=self.revision,
            bundle_url=self.base_url,
            broker=self.broker,
        )


def _handler_factory(out_dir: Path, broker: PreviewEventBroker):
    class PreviewRequestHandler(BaseHTTPRequestHandler):
        server_version = "TubaPreview/0.1"

        def log_message(self, _format: str, *_args: Any) -> None:
            return

        def do_OPTIONS(self) -> None:
            self.send_response(204)
            self._cors_headers()
            self.end_headers()

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/preview/ws":
                self._handle_websocket()
                return
            self._serve_file(parsed.path)

        def _serve_file(self, raw_path: str) -> None:
            relative = unquote(raw_path.lstrip("/")) or "scene.json"
            target = (out_dir / relative).resolve()
            if os.path.commonpath([str(out_dir), str(target)]) != str(out_dir) or not target.is_file():
                self.send_response(404)
                self._cors_headers()
                self.end_headers()
                return
            data = target.read_bytes()
            self.send_response(200)
            self._cors_headers()
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
            broker.add(client)
            try:
                self.connection.settimeout(0.5)
                while not broker.closed:
                    try:
                        frame = self.rfile.read(2)
                    except socket.timeout:
                        continue
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

        def _cors_headers(self) -> None:
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

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


def _broadcast_all(broker: PreviewEventBroker | None, events: list[dict[str, Any]]) -> None:
    if broker is None:
        return
    for event in events:
        broker.broadcast(event)


def _file_fingerprint(path: Path) -> bytes | None:
    try:
        return hashlib.sha256(path.read_bytes()).digest()
    except FileNotFoundError:
        return None


def _diagnostic(code: str, message: str, source: str) -> SceneDiagnostic:
    return SceneDiagnostic(severity="error", code=code, message=message, source=source)


def _preview_subprocess_timeout(timeout_s: float) -> float:
    timeout = float(timeout_s)
    if timeout < 1.0:
        return timeout
    return timeout + 15.0


def _diagnostic_event(diagnostic: SceneDiagnostic) -> dict[str, Any]:
    return {"type": "diagnostic", "severity": diagnostic.severity, "message": diagnostic.message, "payload": diagnostic.to_dict()}


def _read_json_file(path: Path, code: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise _PatchPreviewError(_diagnostic(code, f"JSON file does not exist: {path}", str(path))) from exc
    except json.JSONDecodeError as exc:
        raise _PatchPreviewError(_diagnostic(code, f"Invalid JSON in {path}: {exc}", str(path))) from exc
    if not isinstance(payload, dict):
        raise _PatchPreviewError(_diagnostic(code, f"Expected a JSON object in {path}.", str(path)))
    return payload


def _patch_preview_failure(out_dir: Path, diagnostic: SceneDiagnostic) -> dict[str, Any]:
    scene = _diagnostic_scene(diagnostic)
    write_scene_bundle(scene, out_dir)
    return {
        "ok": False,
        "diagnostics": [diagnostic.to_dict()],
        "messages": [
            _diagnostic_event(diagnostic),
            {
                "type": "scene_reloaded",
                "scene_uri": "scene.json",
                "scene_id": scene.scene_id,
                "objects": 0,
                "issues": 0,
            },
        ],
        "scene": scene.to_dict(),
    }


def _diagnostic_scene(diagnostic: SceneDiagnostic) -> VisualizationScene:
    return VisualizationScene(
        scene_id="scene:patch_preview_diagnostics",
        model_id="model:patch_preview_diagnostics",
        diagnostics=[diagnostic],
    )


class _PatchPreviewError(RuntimeError):
    def __init__(self, diagnostic: SceneDiagnostic) -> None:
        super().__init__(diagnostic.message)
        self.diagnostic = diagnostic


_WEBSOCKET_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
