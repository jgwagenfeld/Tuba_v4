"""The solve claim: one solve per project folder, across processes (spec decision 20)."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tuba.project.claim import SolveBusy, claim_solve, solve_claimed

REPOSITORY = Path(__file__).resolve().parents[1]
CLAIMANT = """
import sys
from tuba.project.claim import SolveBusy, claim_solve
try:
    with claim_solve(sys.argv[1]):
        pass
except SolveBusy:
    sys.exit(3)
"""


def test_a_second_solve_of_a_project_is_busy_until_the_first_releases(tmp_path):
    with claim_solve(tmp_path):
        assert solve_claimed(tmp_path)
        with pytest.raises(SolveBusy, match="already being solved"):
            with claim_solve(tmp_path):
                pass
    assert not solve_claimed(tmp_path)
    assert not (tmp_path / ".tuba" / "solve.lock").exists()
    assert (tmp_path / ".tuba" / ".gitignore").read_text(encoding="utf-8") == "*\n"


def test_a_failing_solve_releases_its_claim(tmp_path):
    with pytest.raises(RuntimeError, match="solve failed"):
        with claim_solve(tmp_path):
            raise RuntimeError("solve failed")
    assert not solve_claimed(tmp_path)


def test_a_claim_untouched_for_a_minute_is_broken(tmp_path):
    lock = tmp_path / ".tuba" / "solve.lock"
    lock.parent.mkdir()
    lock.write_text('{"token": "crashed"}', encoding="utf-8")
    stalled = time.time() - 61
    os.utime(lock, (stalled, stalled))
    assert not solve_claimed(tmp_path)

    with claim_solve(tmp_path):
        assert solve_claimed(tmp_path)
        assert json.loads(lock.read_text(encoding="utf-8"))["token"] != "crashed"
    assert sorted(path.name for path in lock.parent.iterdir()) == [".gitignore"]


def test_the_heartbeat_keeps_a_long_solve_claimed(tmp_path):
    lock = tmp_path / ".tuba" / "solve.lock"
    with claim_solve(tmp_path, heartbeat_s=0.05, stale_after_s=1.0):
        stalled = time.time() - 30
        os.utime(lock, (stalled, stalled))
        deadline = time.time() + 5
        while lock.stat().st_mtime < stalled + 1 and time.time() < deadline:
            time.sleep(0.02)
        assert solve_claimed(tmp_path, stale_after_s=1.0)


def test_another_process_finds_a_claimed_project_busy(tmp_path):
    def claimant():
        return subprocess.run(
            [sys.executable, "-c", CLAIMANT, str(tmp_path)],
            cwd=REPOSITORY, capture_output=True, text=True, timeout=120,
        )

    with claim_solve(tmp_path):
        busy = claimant()
    free = claimant()

    assert busy.returncode == 3, busy.stderr
    assert free.returncode == 0, free.stderr
