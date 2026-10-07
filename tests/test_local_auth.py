"""Launch capabilities are required even for native clients and other loopback ports."""
import json
import socket
import threading
from contextlib import contextmanager
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from tuba.local_auth import LocalAccess, new_access_token
from tuba.studio_launcher import StudioLauncher
from tuba.visualization.preview.transport import PreviewEventBroker, _handler_factory
from tuba.visualization.viewer import LocalHTTPServer


def request(server, path, *, token=None, body=None, **headers):
    if token is not None:
        headers["Authorization"] = "Bearer " + token
    data = json.dumps(body).encode() if body is not None else None
    if data is not None:
        headers["Content-Type"] = "application/json"
    try:
        response = urlopen(Request(f"http://127.0.0.1:{server.server_port}" + path, data=data, headers=headers), timeout=5)
    except HTTPError as exc:
        response = exc
    with response:
        return response.status, response.headers, response.read()


@pytest.mark.parametrize("dev_origin", [None, "http://localhost:5173"])
def test_transport_requires_capability_before_handlers_files_and_websocket(tmp_path, monkeypatch, dev_origin):
    assets = tmp_path / "viewer"
    (assets / "assets").mkdir(parents=True)
    (assets / "index.html").write_text("<html>Viewer bootstrap</html>")
    (assets / "assets" / "main.js").write_text("export {}")
    monkeypatch.setenv("TUBA_VIEWER_ASSETS", str(assets))
    out = tmp_path / "bundle"
    (out / "assets").mkdir(parents=True)
    (out / "assets" / "main.js").write_text("private shadow file")
    (out / "scene.json").write_text('{"private":true}')
    calls = []
    token = new_access_token()
    access = LocalAccess(token, allowed_dev_origin=dev_origin)
    broker = PreviewEventBroker()

    def script():
        calls.append("script")
        return {"code": "private Python", "source_revision": "a" * 64}

    def preview(results):
        calls.append("preview")
        return {"ok": True, "file_count": 1}

    @contextmanager
    def package(results, archive_format):
        calls.append("export")
        path = out / "project.zip"
        path.write_bytes(b"package")
        yield path

    handler = _handler_factory(out, broker, script_get_handler=script,
        script_post_handler=lambda *args, **kw: calls.append("save"),
        solve_handler=lambda **kw: calls.append("solve"),
        package_preview_handler=preview, package_export_handler=package, access=access)
    server = LocalHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        for path in ("/api/script", "/model.py", "/scene.json", "/preview/ws", "/api/comm",
                     "/api/project", "/api/package/preview", "/api/package/export"):
            assert request(server, path)[0] == 403
            assert request(server, path, token="wrong")[0] == 403
            assert request(server, path, token=token, **{"Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "no-cors"})[0] == 403
        for path in ("/api/script", "/api/solve", "/api/package/export", "/api/geometry/store", "/api/ifc/attach"):
            assert request(server, path, body={})[0] == 403
        assert calls == []
        assert request(server, "/")[2] == b"<html>Viewer bootstrap</html>"
        navigation = {"Sec-Fetch-Site": "same-site", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Dest": "document"}
        assert request(server, "/", **navigation)[0] == 200
        assert request(server, "/api/package/preview", token=token, **navigation)[0] == 403
        assert request(server, "/assets/main.js")[2] == b"export {}"
        assert token.encode() not in request(server, "/")[2]
        assert request(server, "/api/script", token=token)[0] == 200
        for origin in ("http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174"):
            status, headers, _ = request(server, "/api/script", token=token, Origin=origin)
            assert status == (200 if origin == dev_origin else 403)
            assert headers.get("Access-Control-Allow-Origin") == (origin if origin == dev_origin else None)
        origin = f"http://127.0.0.1:{server.server_port}"
        assert request(server, "/api/script", token=token, Origin=origin, **{"Sec-Fetch-Site": "same-site"})[0] == 403
        assert request(server, "/api/script", token=token, Host="127.0.0.1:1")[0] == 403
        assert request(server, "/api/package/export", token=token)[0] == 405
        status, _, raw = request(server, "/api/package/preview?results=0", token=token)
        assert status == 200
        payload = {"operation_nonce": json.loads(raw)["operation_nonce"], "results": False, "format": "zip"}
        assert request(server, "/api/package/export", token=token, body=payload)[2] == b"package"
        assert request(server, "/api/package/export", token=token, body=payload)[0] == 409
        assert calls.count("export") == 1
        for capability, expected in ((None, 403), ("wrong", 403), (token, 101)):
            with socket.create_connection(("127.0.0.1", server.server_port), timeout=5) as sock:
                protocol = f"Sec-WebSocket-Protocol: tuba-preview, tuba-auth.{capability}\r\n" if capability else ""
                sock.sendall((f"GET /preview/ws HTTP/1.1\r\nHost: 127.0.0.1:{server.server_port}\r\n"
                    f"Origin: {origin}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                    f"Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n{protocol}\r\n").encode())
                response = sock.recv(4096)
                assert f" {expected} ".encode() in response.split(b"\r\n", 1)[0]
                assert token.encode() not in response
                if expected == 101:
                    assert b"Sec-WebSocket-Protocol: tuba-preview" in response
    finally:
        broker.close()
        server.shutdown()
        server.server_close()
        thread.join()


def test_launcher_anonymous_client_cannot_read_folders_or_execute_project(tmp_path):
    launcher = StudioLauncher(tmp_path / "state").start()
    try:
        for path in ("/api/projects", "/api/folders"):
            assert request(launcher._httpd, path)[0] == 403
        destination = tmp_path / "must-not-exist"
        assert request(launcher._httpd, "/api/projects/new", body={"path": str(destination)})[0] == 403
        assert not destination.exists()
        assert launcher.access_token.encode() not in request(launcher._httpd, "/")[2]
        assert request(launcher._httpd, "/", **{"Sec-Fetch-Site": "same-site", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Dest": "document"})[0] == 200
        assert request(launcher._httpd, "/api/projects", token=launcher.access_token)[0] == 200
        assert launcher.launch_url.endswith("#tuba_token=" + launcher.access_token)
    finally:
        launcher.stop()
