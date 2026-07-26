"""Serve the bundled Three.js review application with a selected scene bundle."""

from __future__ import annotations

import argparse
from importlib.resources import files
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit
import webbrowser


def viewer_assets_path():
    """Return the installed viewer asset directory."""
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
    server = ThreadingHTTPServer((host, port), handler)
    url = f"http://{host}:{server.server_port}/?bundle=/bundle"
    return server, url


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve the packaged Tuba review viewer.")
    parser.add_argument("bundle_directory", help="Scene bundle directory containing scene.json")
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
