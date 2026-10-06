"""Actual-byte revisions and cooperating local writers must not lose source edits."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import threading

import pytest

from tuba.project.source import SourceConflict, read_source, save_source


def test_revision_preserves_unicode_and_crlf_and_rejects_stale_source(tmp_path):
    source = tmp_path / "model.py"
    content = '# Grüße\r\nname = "管"\r\n'
    source.write_bytes(content.encode("utf-8"))
    snapshot = read_source(source)
    assert snapshot == {"code": content, "source_revision": hashlib.sha256(content.encode()).hexdigest()}
    assert save_source(source, content, snapshot["source_revision"]) == snapshot["source_revision"]
    agent = '# newer agent edit\n'
    newer = save_source(source, agent, snapshot["source_revision"])
    with pytest.raises(SourceConflict) as conflict:
        save_source(source, '# unsaved browser edit\n', snapshot["source_revision"])
    assert conflict.value.source_revision == newer
    assert source.read_bytes() == agent.encode()


def test_concurrent_source_saves_exactly_one_wins(tmp_path):
    source = tmp_path / "model.py"
    source.write_bytes(b"old\n")
    revision = read_source(source)["source_revision"]
    gate = threading.Barrier(2)

    def save(code):
        gate.wait(timeout=5)
        try:
            return save_source(source, code, revision)
        except SourceConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(save, ["first\n", "second\n"]))
    assert results.count("conflict") == 1
    assert source.read_text() in {"first\n", "second\n"}
    assert not list(tmp_path.glob(".model.py.*.tmp"))


def test_atomic_write_retries_windows_sharing_errors(tmp_path, monkeypatch):
    import tuba.project.source as module

    source = tmp_path / "model.py"
    source.write_bytes(b"old\n")
    revision = read_source(source)["source_revision"]
    real_replace = module.os.replace
    calls = []

    def replace(temporary: Path, target: Path):
        calls.append(temporary)
        if len(calls) < 3:
            assert target.read_bytes() == b"old\n"
            raise PermissionError("sharing violation")
        real_replace(temporary, target)

    monkeypatch.setattr(module.os, "replace", replace)
    save_source(source, "new\n", revision)
    assert source.read_bytes() == b"new\n"
    assert len(calls) == 3
    assert not list(tmp_path.glob(".model.py.*.tmp"))


def test_failed_atomic_write_keeps_existing_source_and_removes_temporary(tmp_path, monkeypatch):
    import tuba.project.source as module

    source = tmp_path / "model.py"
    source.write_bytes(b"old\n")
    monkeypatch.setattr(module.os, "replace", lambda *_: (_ for _ in ()).throw(PermissionError("sharing")))
    with pytest.raises(PermissionError):
        save_source(source, "new\n", read_source(source)["source_revision"])
    assert source.read_bytes() == b"old\n"
    assert not list(tmp_path.glob(".model.py.*.tmp"))


def test_external_edit_during_windows_sharing_retry_is_preserved(tmp_path, monkeypatch):
    import tuba.project.source as module

    source = tmp_path / "model.py"
    source.write_bytes(b"old\n")
    revision = read_source(source)["source_revision"]

    def replace(*_):
        source.write_bytes(b"external editor\n")
        raise PermissionError("sharing violation")

    monkeypatch.setattr(module.os, "replace", replace)
    with pytest.raises(SourceConflict):
        save_source(source, "browser\n", revision)
    assert source.read_bytes() == b"external editor\n"
    assert not list(tmp_path.glob(".model.py.*.tmp"))


def test_separate_processes_share_the_revision_lock(tmp_path):
    source = tmp_path / "model.py"
    source.write_bytes(b"old\n")
    revision = read_source(source)["source_revision"]
    child = """import json, sys
from tuba.project.source import SourceConflict, save_source
path, revision, code = json.loads(sys.stdin.readline())
try:
    print(save_source(path, code, revision))
except SourceConflict:
    print('conflict')
"""
    processes = [subprocess.Popen([sys.executable, "-c", child], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(2)]
    try:
        for number, process in enumerate(processes):
            process.stdin.write(json.dumps([str(source), revision, f"child {number}\n"]) + "\n")
            process.stdin.flush()
        results = []
        for process in processes:
            output, error = process.communicate(timeout=15)
            assert process.returncode == 0, error
            results.append(output.strip())
        assert results.count("conflict") == 1
        assert source.read_text() in {"child 0\n", "child 1\n"}
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
