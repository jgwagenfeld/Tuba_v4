"""Trusted local preview runner and websocket event server."""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import http.server
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tuba.model import TubaModel
from tuba.patches import ModelPatch
from tuba.visualization.builders import build_visualization_scene
from tuba.visualization.live_preview import preview_json_patch
from tuba.visualization.scene import SceneDiagnostic, VisualizationScene
from tuba.visualization.web_export import SceneBundle, write_scene_bundle

PREVIEW_SOURCE = "visualization.preview"

_CAPTURED_OUTPUTS: list[dict[str, Any]] = []


@dataclass
class PreviewRunResult:
    """Result of one trusted preview script run."""

    success: bool
    events: list[dict[str, Any]] = field(default_factory=list)
    diagnostics: list[SceneDiagnostic] = field(default_factory=list)
    scene: VisualizationScene | None = None
    bundle: SceneBundle | None = None
    elapsed_s: float = 0.0
    run_id: str = ""

    @property
    def ok(self) -> bool:
        return self.success


def show_model(model: TubaModel, **scene_kwargs: Any) -> None:
    """Capture a model from a trusted preview script."""

    _CAPTURED_OUTPUTS.append({"kind": "model", "value": model, "scene_kwargs": dict(scene_kwargs)})


def show_scene(scene: VisualizationScene | dict[str, Any]) -> None:
    """Capture a scene from a trusted preview script."""

    _CAPTURED_OUTPUTS.append({"kind": "scene", "value": scene, "scene_kwargs": {}})


def show_patch(patch: ModelPatch | dict[str, Any], *, model: TubaModel | None = None, **scene_kwargs: Any) -> None:
    """Capture a model patch from a trusted preview script."""

    _CAPTURED_OUTPUTS.append({"kind": "patch", "value": patch, "model": model, "scene_kwargs": dict(scene_kwargs)})


def _reset_output_capture() -> None:
    _CAPTURED_OUTPUTS.clear()


def _consume_output_capture() -> list[dict[str, Any]]:
    outputs = list(_CAPTURED_OUTPUTS)
    _CAPTURED_OUTPUTS.clear()
    return outputs


class PreviewRunner:
    """Run a trusted Python generation script in a subprocess and write a scene bundle."""

    def __init__(
        self,
        script_path: str | Path,
        *,
        out_dir: str | Path,
        timeout_s: float = 10.0,
        python_executable: str | Path | None = None,
        cwd: str | Path | None = None,
        bundle_url: str | None = None,
    ) -> None:
        self.script_path = Path(script_path)
        self.out_dir = Path(out_dir)
        self.timeout_s = float(timeout_s)
        self.python_executable = str(python_executable or sys.executable)
        self.cwd = Path(cwd) if cwd is not None else Path.cwd()
        self.bundle_url = bundle_url or self.out_dir.as_posix()

    def run_once(self) -> PreviewRunResult:
        run_id = f"preview:{uuid.uuid4().hex}"
        started = time.monotonic()
        events: list[dict[str, Any]] = [
            {
                "type": "run_started",
                "run_id": run_id,
                "script": str(self.script_path),
            }
        ]

        try:
            scene = self._run_worker()
            bundle = write_scene_bundle(scene, self.out_dir)
            elapsed_s = time.monotonic() - started
            events.append(
                {
                    "type": "scene_reloaded",
                    "run_id": run_id,
                    "bundle_url": self.bundle_url,
                    "scene_id": scene.scene_id,
                    "objects": len(scene.objects),
                    "issues": len(scene.issues),
                }
            )
            events.append({"type": "run_finished", "run_id": run_id, "status": "success", "elapsed_s": elapsed_s})
            return PreviewRunResult(
                success=True,
                events=events,
                scene=scene,
                bundle=bundle,
                elapsed_s=elapsed_s,
                run_id=run_id,
            )
        except subprocess.TimeoutExpired:
            diagnostic = _diagnostic(
                "visualization.preview.timeout",
                f"Preview script timed out after {self.timeout_s:g} seconds.",
                target=str(self.script_path),
            )
            return self._failed_result(run_id, started, events, diagnostic)
        except PreviewWorkerError as exc:
            diagnostic = _diagnostic(exc.code, exc.message, target=str(self.script_path))
            return self._failed_result(run_id, started, events, diagnostic)
        except Exception as exc:
            diagnostic = _diagnostic("visualization.preview.python_error", str(exc), target=str(self.script_path))
            return self._failed_result(run_id, started, events, diagnostic)

    def _run_worker(self) -> VisualizationScene:
        with tempfile.TemporaryDirectory(prefix="tuba-preview-") as tmpdir:
            result_path = Path(tmpdir) / "result.json"
            completed = subprocess.run(
                [
                    self.python_executable,
                    "-m",
                    "tuba.visualization.preview._worker",
                    str(self.script_path),
                    str(result_path),
                ],
                cwd=self.cwd,
                capture_output=True,
                text=True,
                timeout=_preview_subprocess_timeout(self.timeout_s),
                check=False,
            )
            if not result_path.exists():
                message = (completed.stderr or completed.stdout or f"Preview worker exited with {completed.returncode}").strip()
                raise PreviewWorkerError("visualization.preview.python_error", message)
            payload = json.loads(result_path.read_text(encoding="utf-8"))
            if not payload.get("ok"):
                diagnostic = (payload.get("diagnostics") or [{}])[0]
                raise PreviewWorkerError(
                    diagnostic.get("code") or "visualization.preview.python_error",
                    diagnostic.get("message") or "Preview worker failed.",
                )
            scene = VisualizationScene.from_dict(payload["scene"])
            scene.validate()
            return scene

    def _failed_result(
        self,
        run_id: str,
        started: float,
        events: list[dict[str, Any]],
        diagnostic: SceneDiagnostic,
    ) -> PreviewRunResult:
        scene = _diagnostic_scene(diagnostic)
        bundle = write_scene_bundle(scene, self.out_dir)
        elapsed_s = time.monotonic() - started
        events.append({"type": "diagnostic", "run_id": run_id, "diagnostic": diagnostic.to_dict()})
        events.append(
            {
                "type": "scene_reloaded",
                "run_id": run_id,
                "bundle_url": self.bundle_url,
                "scene_id": scene.scene_id,
                "objects": 0,
                "issues": 0,
            }
        )
        events.append({"type": "run_finished", "run_id": run_id, "status": "failed", "elapsed_s": elapsed_s})
        return PreviewRunResult(
            success=False,
            events=events,
            diagnostics=[diagnostic],
            scene=scene,
            bundle=bundle,
            elapsed_s=elapsed_s,
            run_id=run_id,
        )


def execute_preview_script(script_path: str | Path, out_dir: str | Path, *, timeout_s: float = 10.0) -> dict[str, Any]:
    """Execute a trusted preview script once and return a JSON-friendly payload."""

    result = PreviewRunner(script_path, out_dir=out_dir, timeout_s=timeout_s).run_once()
    messages = [event for event in result.events if event["type"] in {"scene_reloaded", "diagnostic"}]
    return {
        "ok": result.success,
        "events": result.events,
        "messages": messages,
        "diagnostics": [diagnostic.to_dict() for diagnostic in result.diagnostics],
        "scene": result.scene.to_dict() if result.scene else None,
    }


def run_preview_once(
    script_path: str | Path,
    out_dir: str | Path,
    *,
    revision: int = 1,
    timeout_s: float = 10.0,
    bundle_url: str | None = None,
) -> PreviewRunResult:
    """Execute a trusted preview script once and annotate reload events with a bundle revision."""

    result = PreviewRunner(script_path, out_dir=out_dir, timeout_s=timeout_s, bundle_url=bundle_url).run_once()
    for event in result.events:
        if event["type"] == "scene_reloaded":
            event["bundle_revision"] = revision
    return result


class PreviewBroker:
    """In-memory event broker used by the synchronous preview server."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def publish_all(self, events: list[dict[str, Any]]) -> None:
        self.events.extend(dict(event) for event in events)


class PreviewServer:
    """Synchronous local preview server for tests and simple desktop workflows."""

    def __init__(
        self,
        script_path: str | Path,
        out_dir: str | Path,
        *,
        host: str = "127.0.0.1",
        port: int = 8765,
        poll_interval_s: float = 0.25,
        debounce_s: float = 0.25,
        timeout_s: float = 10.0,
    ) -> None:
        self.script_path = Path(script_path)
        self.out_dir = Path(out_dir)
        self.host = host
        self.port = port
        self.poll_interval_s = poll_interval_s
        self.debounce_s = debounce_s
        self.timeout_s = timeout_s
        self.base_url = ""
        self.revision = 0
        self.broker = PreviewBroker()
        self._httpd: http.server.ThreadingHTTPServer | None = None
        self._http_thread: threading.Thread | None = None
        self._watch_thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._last_signature: tuple[int, int, str] | None = None

    def start(self) -> "PreviewServer":
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._run_preview()
        self._last_signature = self._file_signature()
        handler = self._handler()
        self._httpd = http.server.ThreadingHTTPServer((self.host, self.port), handler)
        self._httpd.daemon_threads = True
        self.port = int(self._httpd.server_address[1])
        self.base_url = f"http://{self.host}:{self.port}/"
        self._http_thread = threading.Thread(target=self._httpd.serve_forever, name="tuba-preview-http", daemon=True)
        self._http_thread.start()
        self._watch_thread = threading.Thread(target=self._watch_loop, name="tuba-preview-watch", daemon=True)
        self._watch_thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
        if self._watch_thread is not None:
            self._watch_thread.join(timeout=1.0)
        if self._http_thread is not None:
            self._http_thread.join(timeout=1.0)

    def _handler(self):
        root = self.out_dir

        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                super().__init__(*args, directory=str(root), **kwargs)

            def log_message(self, _format: str, *args: Any) -> None:
                return

        return Handler

    def _watch_loop(self) -> None:
        while not self._stop.wait(self.poll_interval_s):
            current_signature = self._file_signature()
            if current_signature == self._last_signature:
                continue
            self._last_signature = current_signature
            if self._stop.wait(self.debounce_s):
                return
            try:
                self._run_preview()
            except Exception as exc:
                diagnostic = _diagnostic("visualization.preview.watch_error", str(exc), target=str(self.script_path))
                self.broker.publish_all([{"type": "diagnostic", "diagnostic": diagnostic.to_dict()}])

    def _run_preview(self) -> PreviewRunResult:
        self.revision += 1
        result = run_preview_once(
            self.script_path,
            self.out_dir,
            revision=self.revision,
            timeout_s=self.timeout_s,
            bundle_url=self.base_url or None,
        )
        self.broker.publish_all(result.events)
        return result

    def _mtime_ns(self) -> int:
        try:
            return self.script_path.stat().st_mtime_ns
        except FileNotFoundError:
            return -1

    def _file_signature(self) -> tuple[int, int, str] | None:
        try:
            stat = self.script_path.stat()
            content = self.script_path.read_bytes()
            return (stat.st_mtime_ns, stat.st_size, hashlib.sha1(content).hexdigest())
        except FileNotFoundError:
            return None


class PreviewWorkerError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class PreviewEventHub:
    """Fan out JSON preview events to websocket clients."""

    def __init__(self) -> None:
        self._clients: set[asyncio.Queue[dict[str, Any]]] = set()
        self.history: list[dict[str, Any]] = []

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._clients.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._clients.discard(queue)

    async def broadcast(self, event: dict[str, Any]) -> None:
        payload = dict(event)
        self.history.append(payload)
        for queue in list(self._clients):
            await queue.put(payload)


class PreviewWebSocketServer:
    """Small server-to-client websocket broadcaster using only stdlib asyncio."""

    def __init__(self, hub: PreviewEventHub, *, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.hub = hub
        self.host = host
        self.requested_port = port
        self.port = port
        self._server: asyncio.AbstractServer | None = None

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._handle_client, self.host, self.requested_port)
        sockets = self._server.sockets or []
        if sockets:
            self.port = int(sockets[0].getsockname()[1])

    async def stop(self) -> None:
        if self._server is None:
            return
        self._server.close()
        await self._server.wait_closed()
        self._server = None

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        queue = self.hub.subscribe()
        try:
            await _accept_websocket(reader, writer)
            while True:
                event = await queue.get()
                writer.write(_text_frame(json.dumps(event)))
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError, OSError):
            return
        finally:
            self.hub.unsubscribe(queue)
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass


class PreviewWatcher:
    """Polling watcher for trusted local script preview."""

    def __init__(
        self,
        runner: PreviewRunner,
        hub: PreviewEventHub,
        *,
        poll_interval_s: float = 0.25,
        debounce_s: float = 0.25,
    ) -> None:
        self.runner = runner
        self.hub = hub
        self.poll_interval_s = poll_interval_s
        self.debounce_s = debounce_s

    async def run_forever(self) -> None:
        await self.run_once()
        last_mtime = self._mtime_ns()
        while True:
            await asyncio.sleep(self.poll_interval_s)
            current_mtime = self._mtime_ns()
            if current_mtime == last_mtime:
                continue
            last_mtime = current_mtime
            await asyncio.sleep(self.debounce_s)
            await self.run_once()

    async def run_once(self) -> PreviewRunResult:
        result = await asyncio.to_thread(self.runner.run_once)
        for event in result.events:
            await self.hub.broadcast(event)
        return result

    def _mtime_ns(self) -> int:
        try:
            return self.runner.script_path.stat().st_mtime_ns
        except FileNotFoundError:
            return -1


async def watch_script(
    script_path: str | Path,
    *,
    out_dir: str | Path,
    port: int = 8765,
    timeout_s: float = 10.0,
    host: str = "127.0.0.1",
    bundle_url: str | None = None,
) -> None:
    """Run the websocket preview server and trusted script watcher forever."""

    hub = PreviewEventHub()
    runner = PreviewRunner(script_path, out_dir=out_dir, timeout_s=timeout_s, bundle_url=bundle_url)
    server = PreviewWebSocketServer(hub, host=host, port=port)
    watcher = PreviewWatcher(runner, hub)
    await server.start()
    try:
        await watcher.run_forever()
    finally:
        await server.stop()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tuba.visualization.preview")
    subparsers = parser.add_subparsers(dest="command", required=True)
    watch_parser = subparsers.add_parser("watch", help="Watch a trusted Python script and emit preview websocket events.")
    watch_parser.add_argument("script", type=Path)
    watch_parser.add_argument("--out", type=Path, required=True)
    watch_parser.add_argument("--port", type=int, default=8765)
    watch_parser.add_argument("--host", default="127.0.0.1")
    watch_parser.add_argument("--timeout", type=float, default=10.0)
    watch_parser.add_argument("--bundle-url", default=None)

    args = parser.parse_args(argv)
    if args.command == "watch":
        asyncio.run(
            watch_script(
                args.script,
                out_dir=args.out,
                port=args.port,
                host=args.host,
                timeout_s=args.timeout,
                bundle_url=args.bundle_url,
            )
        )
        return 0
    return 2


def _diagnostic(code: str, message: str, *, target: str | None = None) -> SceneDiagnostic:
    return SceneDiagnostic(severity="error", code=code, message=message, target=target, source=PREVIEW_SOURCE)


def _preview_subprocess_timeout(timeout_s: float) -> float:
    """Allow normal preview runs enough interpreter startup time on Windows."""

    timeout = float(timeout_s)
    if timeout < 1.0:
        return timeout
    return timeout + 15.0


def _diagnostic_scene(diagnostic: SceneDiagnostic) -> VisualizationScene:
    return VisualizationScene(
        scene_id="scene:preview_diagnostics",
        model_id="model:preview_diagnostics",
        diagnostics=[diagnostic],
    )


async def _accept_websocket(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    headers = await reader.readuntil(b"\r\n\r\n")
    key = None
    for line in headers.decode("ascii", errors="ignore").split("\r\n"):
        if line.lower().startswith("sec-websocket-key:"):
            key = line.split(":", 1)[1].strip()
            break
    if not key:
        raise ConnectionError("Missing Sec-WebSocket-Key")
    accept = base64.b64encode(hashlib.sha1(f"{key}258EAFA5-E914-47DA-95CA-C5AB0DC85B11".encode("ascii")).digest()).decode(
        "ascii"
    )
    writer.write(
        (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept}\r\n"
            "\r\n"
        ).encode("ascii")
    )
    await writer.drain()


def _text_frame(text: str) -> bytes:
    payload = text.encode("utf-8")
    if len(payload) < 126:
        return bytes([0x81, len(payload)]) + payload
    if len(payload) < 65536:
        return bytes([0x81, 126]) + len(payload).to_bytes(2, "big") + payload
    return bytes([0x81, 127]) + len(payload).to_bytes(8, "big") + payload


def _scene_from_output(output: dict[str, Any], namespace: dict[str, Any]) -> VisualizationScene:
    kind = output["kind"]
    value = output["value"]
    scene_kwargs = dict(output.get("scene_kwargs") or {})
    if kind == "scene":
        scene = value if isinstance(value, VisualizationScene) else VisualizationScene.from_dict(value)
    elif kind == "model":
        scene = build_visualization_scene(value, **scene_kwargs)
    elif kind == "patch":
        model = output.get("model") or namespace.get("model")
        if model is None:
            raise ValueError("Patch preview output requires a model variable or show_patch(..., model=model).")
        preview = preview_json_patch(model, value)
        if preview.diagnostics:
            first = preview.diagnostics[0]
            raise ValueError(first.message)
        if preview.scene is None:
            raise ValueError("Patch preview did not produce a scene.")
        scene = preview.scene
    else:
        raise ValueError(f"Unsupported preview output kind: {kind}")
    scene.validate()
    return scene


def _output_from_namespace(namespace: dict[str, Any]) -> dict[str, Any]:
    if "scene" in namespace:
        return {"kind": "scene", "value": namespace["scene"], "scene_kwargs": {}}
    if "model" in namespace:
        return {"kind": "model", "value": namespace["model"], "scene_kwargs": {}}
    if "patch" in namespace:
        return {"kind": "patch", "value": namespace["patch"], "model": namespace.get("model"), "scene_kwargs": {}}
    raise ValueError("Trusted preview script must define model, scene, patch, or call show_model/show_scene/show_patch.")


__all__ = [
    "PreviewBroker",
    "PreviewEventHub",
    "PreviewRunResult",
    "PreviewRunner",
    "PreviewServer",
    "PreviewWatcher",
    "PreviewWebSocketServer",
    "execute_preview_script",
    "run_preview_once",
    "show_model",
    "show_patch",
    "show_scene",
    "watch_script",
]

from tuba.visualization.preview.server import PatchPreviewServer, execute_patch_preview, run_patch_preview_once

__all__.extend(
    [
        "PatchPreviewServer",
        "execute_patch_preview",
        "run_patch_preview_once",
    ]
)
