"""Project identity and disposable Studio endpoint discovery."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
from urllib.parse import urlencode

import pytest

from tuba.project.session import project_bundle_dir, project_id, register_studio, studio_session, unregister_studio


def test_sessions_use_full_paths_and_validate_live_project_nonce(tmp_path):
    first = tmp_path / "first space" / "Anlage"
    second = tmp_path / "second" / "Anlage"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    assert project_id(first) != project_id(second)
    assert project_bundle_dir(tmp_path / "bundles", first) != project_bundle_dir(tmp_path / "bundles", second)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if getattr(self.server, "redirect", False):
                self.send_response(302)
                self.send_header("Location", "http://example.com/api/project")
                self.end_headers()
                return
            assert self.headers.get("Authorization") == "Bearer " + self.server.session["access_token"]
            payload = json.dumps(self.server.session).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/"
        old = register_studio(first, url)
        server.session = old
        assert studio_session(first) == old
        pointer = first / ".tuba" / "studio.json"
        original = pointer.read_text(encoding="utf-8")
        assert old["access_token"] not in original and "tuba_token" not in original
        forged_base = f"http://127.0.0.1:{server.server_port + 1}/"
        public = json.loads(original)
        public.update(base_url=forged_base, viewer_url=forged_base + "?" + urlencode({
            "bundle": "build", "preview_ws": "ws" + forged_base[4:] + "preview/ws"}))
        pointer.write_text(json.dumps(public), encoding="utf-8")
        with patch("urllib.request.OpenerDirector.open", side_effect=AssertionError("Must not send credentials to a changed endpoint")):
            assert studio_session(first) is None
        pointer.write_text(original, encoding="utf-8")
        server.redirect = True
        assert studio_session(first) is None
        server.redirect = False
        assert studio_session(second) is None
        current = register_studio(first, url, old["access_token"])
        assert studio_session(first) is None  # the live server still has the previous nonce
        server.session = current
        unregister_studio(first, old["session_id"])
        assert studio_session(first) == current
        path = first / ".tuba" / "studio.json"
        path.write_text(json.dumps({**current, "viewer_url": "https://example.com/"}), encoding="utf-8")
        assert studio_session(first) is None
        path.write_text(json.dumps({key: value.split("#", 1)[0] if key == "viewer_url" else value for key, value in current.items() if key != "access_token"}), encoding="utf-8")
        server.session = {**current, "project_id": project_id(second)}
        assert studio_session(first) is None
        unregister_studio(first, current["session_id"])
        assert studio_session(first) is None
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.mark.parametrize("url", ["https://example.com/", "http://127.0.0.1:80@evil.example/", "http://127.0.0.1:0/", "file:///model.py", "http://127.0.0.1:80/\n"])
def test_registration_refuses_nonlocal_or_invalid_endpoints(tmp_path, url):
    with pytest.raises(ValueError):
        register_studio(tmp_path, url)
    assert not (tmp_path / ".tuba" / "studio.json").exists()
