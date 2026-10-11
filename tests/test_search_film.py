import json
from pathlib import Path
import subprocess
import threading

import pytest

from tuba.search.film import write_search_film, FilmCaptureError
from tuba.search.__main__ import main


def package(tmp_path):
    root = tmp_path / 'replay'; root.mkdir()
    (root / 'search_replay.json').write_text(json.dumps({'schema': 'tuba.search.viewer.v1', 'candidates': [], 'events': [{'sequence': 1}]}))
    return root


def test_existing_output_is_refused_before_runtime_resolution(tmp_path):
    output = tmp_path / 'kept'; output.mkdir(); (output / 'data').write_text('preserve')
    with pytest.raises(FileExistsError):
        write_search_film(package(tmp_path), output, ffmpeg='missing')
    assert (output / 'data').read_text() == 'preserve'


def test_missing_encoder_is_a_clear_requirement(tmp_path):
    with pytest.raises(FilmCaptureError, match='FFmpeg'):
        write_search_film(package(tmp_path), tmp_path / 'film', ffmpeg=tmp_path / 'missing.exe')
    assert not (tmp_path / 'film').exists()


def test_capture_cannot_write_into_replay_package(tmp_path):
    root = package(tmp_path)
    with pytest.raises(ValueError, match='outside'):
        write_search_film(root, root / 'film', ffmpeg='missing')


@pytest.mark.parametrize('options', [{'fps': 0}, {'width': 641}, {'height': 10}, {'hold_seconds': float('nan')}, {'start': 2, 'end': 1}, {'events': 'bad'}])
def test_invalid_options_fail_before_starting_capture(tmp_path, options):
    with pytest.raises(ValueError):
        write_search_film(package(tmp_path), tmp_path / 'film', **options)


@pytest.mark.parametrize('events', ['all', 'review', 'iterations'])
def test_cli_passes_film_options_without_a_solver(tmp_path, monkeypatch, capsys, events):
    calls = []
    def capture(replay, output, **options):
        calls.append((replay, output, options)); return output / 'film.json'
    monkeypatch.setattr('tuba.search.__main__.write_search_film', capture)
    assert main(['film', '--replay-dir', str(tmp_path / 'replay'), '--output', str(tmp_path / 'film'), '--ffmpeg', 'encoder', '--start', '2', '--end', '8', '--events', events, '--fps', '30', '--hold-seconds', '1.5']) == 0
    assert calls[0][2]['start'] == 2 and calls[0][2]['end'] == 8
    assert calls[0][2]['fps'] == 30 and calls[0][2]['hold_seconds'] == 1.5
    assert calls[0][2]['events'] == events


def test_default_film_follows_iterations_with_readable_holds(tmp_path, monkeypatch):
    calls = []
    def capture(replay, output, **options):
        calls.append(options)
        return output / 'film.json'
    monkeypatch.setattr('tuba.search.__main__.write_search_film', capture)
    assert main(['film', '--replay-dir', str(tmp_path / 'replay'), '--output', str(tmp_path / 'film')]) == 0
    assert calls[0]['events'] == 'iterations'
    assert calls[0]['hold_seconds'] == 8.0


def test_failed_capture_stops_server_and_reports_retained_failure(tmp_path, monkeypatch):
    from tuba.search import film
    root = package(tmp_path); output = tmp_path / 'film'
    class Server:
        done = threading.Event()
        def serve_forever(self): self.done.wait()
        def shutdown(self): self.stopped = True; self.done.set()
        def server_close(self): self.closed = True
    server = Server()
    monkeypatch.setattr(film, 'create_server', lambda p: (server, 'http://127.0.0.1:1/?search=/bundle/search_replay.json'))
    def fail(args, **kwargs):
        output.mkdir(); (output / 'film.json').write_text('{"status":"failed","error":"encoder failed"}')
        assert kwargs.get('shell', False) is False
        assert json.loads(args[-1])['fps'] == 25
        return subprocess.CompletedProcess(args, 1, '', 'encoder failed')
    monkeypatch.setattr(film.subprocess, 'run', fail)
    with pytest.raises(FilmCaptureError, match='encoder failed'):
        write_search_film(root, output, ffmpeg=Path(__file__), node=Path(__file__))
    assert server.stopped and server.closed
    assert json.loads((output / 'film.json').read_text())['status'] == 'failed'
