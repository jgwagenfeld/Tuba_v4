"""The solve claim: one solve per project folder at a time, across processes (spec decision 20).

A solve holds ``<project>/.tuba/solve.lock``, created atomically, and touches it every few seconds. A
claim nobody has touched for a minute belonged to a solve that crashed, and the next solve breaks it.
"""

from __future__ import annotations

import json
import os
import socket
import threading
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

CLAIM = Path(".tuba") / "solve.lock"
HEARTBEAT_S = 15.0
STALE_AFTER_S = 60.0


class SolveBusy(RuntimeError):
    """Another solve holds this project's claim."""


def solve_claimed(project_root: str | Path, *, stale_after_s: float = STALE_AFTER_S) -> bool:
    """Whether a live solve holds the project's claim: the claim exists and was touched recently."""
    try:
        touched = (Path(project_root) / CLAIM).stat().st_mtime
    except FileNotFoundError:
        return False
    return time.time() - touched < stale_after_s


@contextmanager
def claim_solve(
    project_root: str | Path,
    *,
    heartbeat_s: float = HEARTBEAT_S,
    stale_after_s: float = STALE_AFTER_S,
) -> Iterator[None]:
    """Hold the project's solve claim for the block, or raise :class:`SolveBusy` while a live solve holds it."""
    root = Path(project_root)
    path = root / CLAIM
    path.parent.mkdir(exist_ok=True)
    ignore = path.parent / ".gitignore"
    if not ignore.exists():
        ignore.write_text("*\n", encoding="utf-8")  # .tuba/ is tool state, never committed
    token = uuid.uuid4().hex
    if not _create(path, token):
        if solve_claimed(root, stale_after_s=stale_after_s):
            raise SolveBusy(f"{root.name} is already being solved.")
        _break(path, token)
        if not _create(path, token):
            raise SolveBusy(f"{root.name} is already being solved.")
    stop = threading.Event()
    heartbeat = threading.Thread(
        target=_heartbeat, args=(path, stop, heartbeat_s), name="tuba-solve-claim", daemon=True
    )
    heartbeat.start()
    try:
        yield
    finally:
        stop.set()
        heartbeat.join()
        _release(path, token)


def _create(path: Path, token: str) -> bool:
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump({"token": token, "pid": os.getpid(), "host": socket.gethostname(), "started_at": time.time()}, stream)
    return True


def _heartbeat(path: Path, stop: threading.Event, interval: float) -> None:
    while not stop.wait(interval):
        try:
            os.utime(path)
        except FileNotFoundError:
            return  # broken by another solve after a stall; the release finds it gone
        except OSError:
            continue  # a reader held the file for a moment (Windows); the next beat retries


def _break(path: Path, token: str) -> None:
    aside = path.with_name(f"{path.name}.{token}.broken")
    try:
        os.replace(path, aside)
    except FileNotFoundError:
        return  # another solve broke or released it first
    # ponytail: two solves breaking the same stale claim in one instant can both take it;
    # a generation number in the claim closes that if it ever matters.
    try:
        aside.unlink()
    except OSError:
        pass


def _release(path: Path, token: str) -> None:
    try:
        if json.loads(path.read_text(encoding="utf-8")).get("token") == token:
            path.unlink()
    except (OSError, ValueError):
        pass  # already broken by another solve, or held open by a reader: it goes stale in a minute
