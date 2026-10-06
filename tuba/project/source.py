"""Byte revisions and atomic saves shared by Studio and generated-script writers."""

from __future__ import annotations

from contextlib import contextmanager
import errno
import hashlib
import os
from pathlib import Path
import tempfile
import time


class SourceConflict(RuntimeError):
    """A save was based on different source bytes from those currently on disk."""

    def __init__(self, source_revision: str | None):
        super().__init__("model.py changed on disk. Reload the latest source before saving your edits.")
        self.source_revision = source_revision


def read_source(path: str | Path) -> dict[str, str]:
    """Read code and its revision together, preserving Unicode and line endings."""
    data = Path(path).read_bytes()
    return {"code": data.decode("utf-8"), "source_revision": hashlib.sha256(data).hexdigest()}


def source_revision(path: str | Path) -> str | None:
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except FileNotFoundError:
        return None


@contextmanager
def source_lock(path: str | Path):
    """Serialize cooperating writers in this project; OS locks release after a crash."""
    state = Path(path).resolve().parent / ".tuba"
    state.mkdir(parents=True, exist_ok=True)
    try:
        with (state / ".gitignore").open("x", encoding="utf-8") as stream:
            stream.write("*\n")
    except FileExistsError:
        pass
    with (state / "source.lock").open("a+b") as stream:
        if not stream.seek(0, os.SEEK_END):
            stream.write(b"\0")
            stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt

            def lock(acquiring):
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK if acquiring else msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            def lock(acquiring):
                fcntl.flock(stream.fileno(), (fcntl.LOCK_EX | fcntl.LOCK_NB) if acquiring else fcntl.LOCK_UN)
        deadline = time.monotonic() + 5
        while True:
            try:
                lock(True)
                break
            except OSError as exc:
                if exc.errno not in {errno.EACCES, errno.EAGAIN, errno.EDEADLK} or time.monotonic() >= deadline:
                    raise
                time.sleep(0.025)
        try:
            yield
        finally:
            lock(False)


def replace_source(path: str | Path, code: str, expected_revision: str | None) -> str:
    """Replace complete source bytes under source_lock, with brief sharing retries."""
    target = Path(path)
    data = code.encode("utf-8")
    descriptor, name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        for attempt in range(6):
            current = source_revision(target)
            if current != expected_revision:
                raise SourceConflict(current)
            try:
                os.replace(temporary, target)
                break
            except PermissionError:
                if attempt == 5:
                    raise
                time.sleep(0.025 * (attempt + 1))
    finally:
        temporary.unlink(missing_ok=True)
    return hashlib.sha256(data).hexdigest()


def save_source(path: str | Path, code: str, expected_revision: str | None) -> str:
    """Compare actual source bytes under the project lock, then atomically replace."""
    with source_lock(path):
        current = source_revision(path)
        if current != expected_revision:
            raise SourceConflict(current)
        return replace_source(path, code, expected_revision)
