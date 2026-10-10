"""Serve the bundled Three.js review application with a selected scene bundle."""

from __future__ import annotations

import argparse
from importlib.resources import files
import json
import os
import socket
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit
import webbrowser

BUNDLE_CONTENT_SECURITY_POLICY = (
    "sandbox allow-downloads; default-src 'none'; style-src 'unsafe-inline'; "
    "img-src 'self' data:; font-src data:; base-uri 'none'; form-action 'none'; frame-ancestors 'self'"
)
MAX_SCENE_BYTES = 64 * 1024**2


def _relative_replay_path(value):
    if not isinstance(value, str) or not value:
        raise ValueError('Unsafe relative replay path')
    for _ in range(5):
        decoded = unquote(value)
        if decoded == value:
            break
        value = decoded
    if any(c in value for c in '\\%:?#') or any(c.isspace() or ord(c) < 32 for c in value) or any(p in ('', '.', '..') for p in value.split('/')):
        raise ValueError('Unsafe relative replay path')
    return value


def _read_bundle_json(path):
    try:
        if path.stat().st_size > MAX_SCENE_BYTES:
            raise ValueError(f'Bundle {path.name} exceeds the 64 MiB limit.')
        value = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError as exc:
        raise ValueError(f'Bundle is missing {path.name}: {path.parent}') from exc
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ValueError(f'Bundle {path.name} is malformed: {exc}') from exc
    if not isinstance(value, dict):
        raise ValueError(f'Bundle {path.name} must contain a JSON object: {path}')
    return value


def _replay_default(manifest, root):
    if manifest.get('schema') != 'tuba.search.viewer.v1' or not isinstance(manifest.get('candidates'), list) or not isinstance(manifest.get('events'), list):
        raise ValueError('Malformed search_replay.json')
    for row in manifest['candidates']:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not isinstance(row.get('attempt_reviews', []), list):
            raise ValueError('Malformed search_replay.json candidate')
        entries = [*row.get('attempt_reviews', []), row.get('preview')]
        if any(entry is not None and not isinstance(entry, dict) for entry in entries):
            raise ValueError('Malformed search_replay.json view')
    views = []
    rows = sorted(manifest['candidates'], key=lambda c: c.get('outcome') != 'selected')
    for row in rows:
        entries = [*reversed(row.get('attempt_reviews', [])), row.get('preview')]
        for entry in entries:
            if entry and entry.get('bundle'):
                relative = _relative_replay_path(entry['bundle'])
                if not (root / relative).resolve().is_relative_to(root):
                    raise ValueError('Unsafe relative replay path')
                if entry.get('availability') == 'available':
                    views.append(relative)
    if views:
        _read_bundle_json(root / views[0] / 'scene.json')
    return views[0] if views else None


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

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        path = unquote(urlsplit(self.path).path)
        if path == "/bundle" or path.startswith("/bundle/"):
            self.send_header("Content-Security-Policy", BUNDLE_CONTENT_SECURITY_POLICY)
        super().end_headers()

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
    # socketserver's default listen backlog is 5. A viewer page opens more parallel
    # connections than that (fonts, chunks, bundles.json), and two tabs opening at
    # once overflow it; Windows then refuses the excess outright, and a refused
    # viewer chunk leaves the page dead until reload.
    request_queue_size = 128

    def server_bind(self) -> None:
        if os.name == "nt":
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


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
    replay_path = bundle_root / 'search_replay.json'
    is_replay = replay_path.is_file()
    default_view = _replay_default(_read_bundle_json(replay_path), bundle_root) if is_replay else None
    if not is_replay:
        _read_bundle_json(bundle_root / 'scene.json')

    viewer_root = Path(viewer_assets_path()).resolve()
    if not (viewer_root / "index.html").is_file():
        raise ValueError(f"Packaged viewer is incomplete: {viewer_root}")
    if is_replay and 'data-search-replay' not in (viewer_root / 'index.html').read_text(encoding='utf-8'):
        raise ValueError('Replay requires current viewer assets. Build viewer/ and set TUBA_VIEWER_ASSETS to that output.')
    handler = partial(
        _ViewerRequestHandler,
        viewer_root=viewer_root,
        bundle_root=bundle_root,
    )
    server = LocalHTTPServer((host, port), handler)
    url = f"http://{host}:{server.server_port}/?bundle=/bundle"
    if is_replay:
        if default_view:
            url += '/' + default_view
        url += '&search=/bundle/search_replay.json'
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
    parser.add_argument("bundle_directory", help="Scene bundle or search replay directory")
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
