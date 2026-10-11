"""Capture retained replay evidence through the existing review viewer."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import threading

from tuba.visualization.viewer import create_server, _read_bundle_json


class FilmCaptureError(RuntimeError):
    """A missing capture runtime or failed browser/encoder export."""


def _runtime(value, name):
    resolved = shutil.which(str(value)) if value else None
    if not resolved and value and Path(value).is_file():
        resolved = str(Path(value).resolve())
    if not resolved:
        raise FilmCaptureError(f'{name} is unavailable: {value!s}. Install/select an existing runtime; film capture does not download one.')
    return resolved


def write_search_film(replay_directory, output_directory, *, ffmpeg=None, node=None,
                      start=1, end=None, events='iterations', fps=25,
                      hold_seconds=8.0, width=1600, height=900):
    """Export held recorded frames; no agent or fresh Code_Aster run is involved.

    Requires the source checkout's viewer capture script, Node/Playwright,
    a current viewer build and an FFmpeg executable with VP8 encoding.
    Native replay files are served read-only and never copied into the film.
    """
    root, output = Path(replay_directory).resolve(), Path(output_directory).resolve()
    if output.exists():
        raise FileExistsError(f'Film output already exists: {output}')
    if output.is_relative_to(root):
        raise ValueError('Film output must be outside the retained replay package')
    data = _read_bundle_json(root / 'search_replay.json')
    if data.get('schema') != 'tuba.search.viewer.v1' or not isinstance(data.get('events'), list):
        raise ValueError('Film requires an existing tuba.search.viewer.v1 replay package')
    final = data['events'][-1]['sequence'] if data['events'] else 0
    end = final if end is None else end
    if (type(start) is not int or type(end) is not int or not 1 <= start <= end <= final or
        type(fps) is not int or not 1 <= fps <= 60 or
        not isinstance(hold_seconds, (int, float)) or not math.isfinite(hold_seconds) or
        not 0 < hold_seconds <= 30 or int(fps * hold_seconds + .5) < 1 or
        type(width) is not int or not 640 <= width <= 3840 or width % 2 or
        type(height) is not int or not 360 <= height <= 2160 or height % 2 or
        events not in ('all', 'milestones', 'review', 'iterations')):
        raise ValueError('Invalid film range, fps, hold, size or events policy')
    encoder = _runtime(ffmpeg or os.environ.get('TUBA_FFMPEG') or 'ffmpeg', 'FFmpeg VP8 encoder')
    node_path = _runtime(node or os.environ.get('TUBA_NODE') or 'node', 'Node/Playwright capture runtime')
    script = Path(__file__).resolve().parents[2] / 'viewer/scripts/search-film.mjs'
    if not script.is_file():
        raise FilmCaptureError('Film capture currently requires a Tuba source checkout with viewer/scripts/search-film.mjs and its existing npm dependencies.')
    options = dict(start=start, end=end, events=events, fps=fps,
                   holdSeconds=hold_seconds, width=width, height=height)
    server, url = create_server(root)
    thread = threading.Thread(target=server.serve_forever, name='tuba-film-review', daemon=True)
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        thread.start()
        result = subprocess.run([node_path, str(script), url, str(output), encoder,
                                 json.dumps(options, allow_nan=False)],
                                capture_output=True, text=True, encoding='utf-8', errors='replace')
        if result.returncode:
            raise FilmCaptureError(f'Film capture failed; retained diagnostics: {output / "film.json"}\n{result.stderr[-2500:]}')
        manifest = _read_bundle_json(output / 'film.json')
        if (manifest.get('schema') != 'tuba.search.film.v1' or manifest.get('status') != 'complete' or
            not (output / 'film.webm').is_file() or not (output / 'captions.vtt').is_file()):
            raise FilmCaptureError(f'Capture did not produce a complete film: {output}')
        return output / 'film.json'
    finally:
        if thread.is_alive():
            server.shutdown()
            thread.join(timeout=10)
        server.server_close()
