"""Portable ownership/cancellation safety; no fixture qualifies native execution."""
import json
import subprocess
from types import SimpleNamespace

import pytest

from tuba.solver import code_aster_process as owned
from tuba.solver.code_aster_runtime import CodeAsterRuntimeCandidate


def identity():
    return {"schema": "tuba.wsl-owned-process.v1", "pid": 123, "pgid": 123, "sid": 123,
            "token": "token", "starttime": "10", "distro": "Ubuntu", "state": "S"}


@pytest.mark.parametrize("change", [{}, {"pid":124}, {"pgid":124}, {"sid":124}, {"token":"wrong"}, {"starttime":"11"}])
def test_identity_requires_token_starttime_and_dedicated_session(change):
    owner = identity()
    process = {**owner, **change}
    assert owned.validate_owner(owner, process, "token") == (not change)


def test_cancel_before_launch_and_repeated_cancel_are_barriers(tmp_path):
    control = owned.WslExecutionController(tmp_path)
    assert control.cancel() == []
    assert control.cancel() == []
    with pytest.raises(owned.SolverCancelled):
        control.execute(CodeAsterRuntimeCandidate("wsl", ("wsl", "-d", "Ubuntu", "--")), [], None, 1, tmp_path)


def test_corrupt_or_wrong_token_record_refuses_cleanup(tmp_path):
    directory = tmp_path / "runtime-owned"
    directory.mkdir()
    control = owned.WslExecutionController(tmp_path)
    for data in ("invalid json", json.dumps({**identity(), "token":"other"})):
        (directory / "ownership.json").write_text(data)
        with pytest.raises(RuntimeError, match="cleanup failed"):
            control.cancel()
        assert not json.loads((tmp_path / "cleanup.json").read_text())["verified"]


def test_linux_pid_reuse_and_unowned_descendants_never_signal(tmp_path, monkeypatch):
    import os
    path = tmp_path / "ownership.json"
    path.write_text(json.dumps(identity()))
    signals = []
    monkeypatch.setattr(os, "kill", lambda *args: signals.append(args))
    monkeypatch.setattr(owned, "_proc", lambda pid: {**identity(), "starttime":"reused"})
    with pytest.raises(RuntimeError, match="identity/token/starttime"):
        owned._linux_cleanup(path, "token")
    monkeypatch.setattr(owned, "_proc", lambda pid: None)
    monkeypatch.setattr(owned, "_session_members", lambda record: [{**identity(), "pid":124, "token":"other"}])
    with pytest.raises(RuntimeError, match="inherited ownership"):
        owned._linux_cleanup(path, "token")
    assert signals == []


def test_missing_receipt_after_launch_is_not_verified_cleanup(tmp_path, monkeypatch):
    directory = tmp_path / "runtime-owned"
    directory.mkdir()
    (directory / "intent.json").write_text(json.dumps({"token":"owned", "distro":"Ubuntu"}))
    control = owned.WslExecutionController(tmp_path)
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout='[{"pid":123}]', stderr=""))
    with pytest.raises(RuntimeError, match="ownership record is missing"):
        control.cancel()


def test_linux_cleanup_escalates_and_validates_descendants_without_leader(tmp_path, monkeypatch, capsys):
    import os
    import signal
    from enum import IntEnum
    class LinuxSignal(IntEnum):
        SIGKILL = 9
    monkeypatch.setattr(signal, "SIGKILL", LinuxSignal.SIGKILL, raising=False)
    path = tmp_path / "ownership.json"
    path.write_text(json.dumps(identity()))
    child = {**identity(), "pid":124, "starttime":"20"}
    alive = [child]
    signals = []
    monkeypatch.setattr(owned, "_proc", lambda pid: child if pid == 124 and alive else None)
    monkeypatch.setattr(owned, "_session_members", lambda record: list(alive))
    ticks = iter(range(100))
    monkeypatch.setattr(owned.time, "monotonic", lambda: float(next(ticks)))
    monkeypatch.setattr(owned.time, "sleep", lambda delay: None)
    def kill(pid, sig):
        signals.append((pid, sig))
        if sig == signal.SIGKILL:
            alive.clear()
    monkeypatch.setattr(os, "kill", kill)
    owned._linux_cleanup(path, "token")
    assert signals == [(124, signal.SIGTERM), (124, signal.SIGKILL)]
    assert json.loads(path.read_text())["cleanup"]["verified"]
