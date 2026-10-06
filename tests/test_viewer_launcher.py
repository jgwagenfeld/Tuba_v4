import json
import threading
from pathlib import Path
from urllib.request import urlopen

import pytest


def _bundle(tmp_path: Path) -> Path:
    bundle = tmp_path / "review"
    bundle.mkdir()
    (bundle / "scene.json").write_text(
        json.dumps(
            {
                "schema_version": "visualization.scene.v1",
                "scene_id": "scene:test",
                "model_id": "model:test",
                "objects": [],
                "geometry_assets": [],
                "overlays": [],
            }
        ),
        encoding="utf-8",
    )
    return bundle


def test_viewer_server_serves_packaged_app_and_selected_bundle(tmp_path):
    from tuba.visualization.viewer import create_server

    server, url = create_server(_bundle(tmp_path), port=0)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        assert url == f"http://127.0.0.1:{server.server_port}/?bundle=/bundle"
        assert "Tuba Viewer" in urlopen(url, timeout=5).read().decode()
        payload = json.load(urlopen(f"http://127.0.0.1:{server.server_port}/bundle/scene.json", timeout=5))
        assert payload["scene_id"] == "scene:test"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    assert not thread.is_alive()


@pytest.mark.parametrize("contents", ["not json", "[]"])
def test_viewer_rejects_malformed_scene_bundle(tmp_path, contents):
    from tuba.visualization.viewer import create_server

    bundle = tmp_path / "bad"
    bundle.mkdir()
    (bundle / "scene.json").write_text(contents, encoding="utf-8")

    with pytest.raises(ValueError, match="scene.json"):
        create_server(bundle)


def test_viewer_rejects_missing_bundle_directory(tmp_path):
    from tuba.visualization.viewer import create_server

    with pytest.raises(ValueError, match="does not exist"):
        create_server(tmp_path / "missing")


def test_viewer_asset_directory_default_and_external_build(tmp_path, monkeypatch):
    from importlib.resources import files
    from tuba.visualization.viewer import viewer_assets_path

    monkeypatch.delenv("TUBA_VIEWER_ASSETS", raising=False)
    assert viewer_assets_path() == files("tuba.visualization").joinpath("_viewer")
    (tmp_path / "index.html").write_text("<!doctype html><title>External viewer</title>")
    monkeypatch.setenv("TUBA_VIEWER_ASSETS", str(tmp_path))
    assert viewer_assets_path() == tmp_path.resolve()
    from tuba.visualization.viewer import create_server
    server, _ = create_server(_bundle(tmp_path), port=0)
    server.server_close()


@pytest.mark.parametrize("path_kind", ["empty", "missing", "file", "incomplete"])
def test_viewer_asset_override_rejects_invalid_paths(tmp_path, monkeypatch, path_kind):
    from tuba.visualization.viewer import viewer_assets_path

    root = tmp_path / path_kind
    if path_kind == "file":
        root.write_text("not a directory")
    elif path_kind == "incomplete":
        root.mkdir()
    monkeypatch.setenv("TUBA_VIEWER_ASSETS", " " if path_kind == "empty" else str(root))
    with pytest.raises(ValueError, match="TUBA_VIEWER_ASSETS"):
        viewer_assets_path()
