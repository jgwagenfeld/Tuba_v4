"""Serve the bundled Three.js review application with a selected scene bundle."""

from __future__ import annotations

import argparse
from importlib.resources import files
import json
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit
import webbrowser


def viewer_assets_path():
    """Return packaged assets, or an explicitly selected source-checkout build."""
    override = os.environ.get("TUBA_VIEWER_ASSETS")
    if override is not None:
        if not override.strip():
            raise ValueError("TUBA_VIEWER_ASSETS must name a built viewer directory.")
        root = Path(override).expanduser().resolve()
        if not root.is_dir():
            raise ValueError(f"TUBA_VIEWER_ASSETS directory does not exist: {root}")
        if not (root / "index.html").is_file():
            raise ValueError(f"TUBA_VIEWER_ASSETS is incomplete (missing index.html): {root}")
        return root
    return files("tuba.visualization").joinpath("_viewer")


class _ViewerRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, viewer_root: Path, bundle_root: Path, **kwargs):
        self.viewer_root = viewer_root
        self.bundle_root = bundle_root
        super().__init__(*args, directory=str(viewer_root), **kwargs)

    def translate_path(self, path: str) -> str:
        request_path = unquote(urlsplit(path).path)
        if request_path == "/":
            return str(self.viewer_root / "index.html")
        if request_path == "/bundle" or request_path.startswith("/bundle/"):
            root = self.bundle_root
            relative = request_path.removeprefix("/bundle").lstrip("/")
        else:
            root = self.viewer_root
            relative = request_path.lstrip("/")
        candidate = (root / relative).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            return str(root / "__not_found__")
        return str(candidate)


class LocalHTTPServer(ThreadingHTTPServer):
    """A local HTTP server that refuses a port another server is still using.

    ThreadingHTTPServer sets SO_REUSEADDR. On Windows that lets a second server
    bind a port an older one still serves, and the browser keeps reaching the old
    one; elsewhere it only allows a quick restart, so it stays on there.
    """

    allow_reuse_address = os.name != "nt"


def create_server(
    bundle_directory: str | Path,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
) -> tuple[ThreadingHTTPServer, str]:
    """Create a local viewer server and return it with its exact browser URL."""
    bundle_root = Path(bundle_directory).expanduser().resolve()
    if not bundle_root.is_dir():
        raise ValueError(f"Bundle directory does not exist: {bundle_root}")
    scene_path = bundle_root / "scene.json"
    try:
        scene = json.loads(scene_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Bundle is missing scene.json: {bundle_root}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Bundle scene.json is malformed: {exc}") from exc
    if not isinstance(scene, dict):
        raise ValueError(f"Bundle scene.json must contain a JSON object: {scene_path}")

    viewer_root = Path(viewer_assets_path()).resolve()
    if not (viewer_root / "index.html").is_file():
        raise ValueError(f"Packaged viewer is incomplete: {viewer_root}")
    handler = partial(
        _ViewerRequestHandler,
        viewer_root=viewer_root,
        bundle_root=bundle_root,
    )
    server = LocalHTTPServer((host, port), handler)
    url = f"http://{host}:{server.server_port}/?bundle=/bundle"
    return server, url


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Serve the packaged Tuba review viewer.",
        epilog=(
            "Extract a received review ZIP and keep the complete bundle: scene.json, "
            "geometry, reports, metadata and staged solver artifacts. Viewing existing "
            "results needs no new Code_Aster execution. To edit or solve a project, use "
            "python -m tuba.cli_studio <folder-containing-model.py>. "
            "Guide: docs/content/project-sharing.md (Share and open a project)."
        ),
    )
    parser.add_argument("bundle_directory", help="Complete extracted scene bundle directory containing scene.json")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--open", action="store_true", dest="open_browser")
    args = parser.parse_args(argv)
    try:
        server, url = create_server(args.bundle_directory, host=args.host, port=args.port)
    except ValueError as exc:
        parser.error(str(exc))
    print(url, flush=True)
    if args.open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
