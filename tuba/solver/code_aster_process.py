"""Owned Linux native/WSL execution; ordinary solver execution is unchanged.

The Linux entry points intentionally use only the standard library. The parent
can run cleanup after worker death using durable records written inside setsid.
No process may be signalled using a PID/PGID alone.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4


class SolverCancelled(RuntimeError):
    pass


def _write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}-{uuid4().hex}.tmp")
    temporary.write_text(json.dumps(data), encoding="utf-8")
    temporary.replace(path)


def _proc(pid):
    try:
        raw = Path(f"/proc/{pid}/stat").read_text()
        fields = raw[raw.rfind(")")+2:].split()
        environ = Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
        tokens = [s.split(b"=", 1)[1].decode() for s in environ if s.startswith(b"TUBA_SOLVER_JOB_TOKEN=")]
        return {"pid": int(pid), "state": fields[0], "pgid": int(fields[2]), "sid": int(fields[3]),
                "starttime": fields[19], "token": tokens[0] if len(tokens) == 1 else None}
    except (OSError, ValueError, IndexError):
        return None


def validate_owner(record, process, token):
    """Portable ownership predicate, also reapplied immediately before signalling."""
    return bool(process and record.get("token") == token == process.get("token")
                and record.get("pid") == record.get("pgid") == record.get("sid")
                and process.get("pid") == record.get("pid")
                and process.get("pgid") == process.get("sid") == record.get("sid")
                and process.get("starttime") == record.get("starttime"))


def _session_members(record):
    members = []
    for path in Path("/proc").iterdir():
        if path.name.isdigit():
            process = _proc(path.name)
            if process and process["state"] != "Z" and process["sid"] == record["sid"]:
                members.append(process)
    return members


def _linux_cleanup(path, token, *, emit=True):
    import signal
    record = json.loads(Path(path).read_text(encoding="utf-8"))
    if (record.get("schema") not in {"tuba.wsl-owned-process.v1", "tuba.native-owned-process.v1"} or record.get("token") != token
            or not isinstance(record.get("pid"), int) or record["pid"] <= 1
            or record["pid"] != record.get("pgid") or record["pid"] != record.get("sid")
            or not isinstance(record.get("starttime"), str)):
        raise RuntimeError("Invalid WSL ownership record; cleanup refused.")
    leader = _proc(record["pid"])
    # A reused leader PID may now belong to an unrelated session. Never signal it.
    if leader and leader["state"] != "Z" and not validate_owner(record, leader, token):
        raise RuntimeError("WSL leader identity/token/starttime changed; cleanup refused.")
    observed = _session_members(record)
    if any(p["token"] != token or p["pgid"] != record["pgid"] for p in observed):
        raise RuntimeError("WSL session contains a process without matching inherited ownership; cleanup refused.")
    signalled = []
    for sig in (signal.SIGTERM, signal.SIGKILL):
        members = _session_members(record)
        for process in members:
            current = _proc(process["pid"])
            if not current or current["state"] == "Z":
                continue
            if (any(current[key] != process[key] for key in ("pid", "pgid", "sid", "starttime", "token"))
                    or current["token"] != token or current["pgid"] != record["pgid"]):
                raise RuntimeError("WSL descendant identity changed before signalling; cleanup refused.")
            # Each descendant is revalidated, including when the leader is gone.
            try:
                os.kill(process["pid"], sig)
            except ProcessLookupError:
                continue
            signalled.append({"pid": process["pid"], "starttime": process["starttime"], "signal": sig.name})
        deadline = time.monotonic()+2.
        while _session_members(record) and time.monotonic() < deadline:
            time.sleep(.05)
        if not _session_members(record):
            break
    remaining = _session_members(record)
    record.update(active=bool(remaining), cleanup={"verified": not remaining, "observed": observed,
                                               "signalled": signalled, "remaining": remaining})
    _write(path, record)
    if remaining:
        raise RuntimeError("Owned WSL descendants remain after TERM/KILL.")
    if emit:
        print(json.dumps(record["cleanup"]))
    return record["cleanup"]


def _linux_launch(path, token, distro, cancelled, workdir, command):
    pid = os.getpid()
    process = _proc(pid)
    if not process or pid != os.getpgid(pid) or pid != os.getsid(pid) or process["token"] != token:
        raise RuntimeError("WSL launcher requires a dedicated token-owned Linux session.")
    if Path(cancelled).exists():
        raise SolverCancelled("Job was cancelled before Linux launch.")
    record = {"schema": "tuba.native-owned-process.v1" if distro == "__native__" else "tuba.wsl-owned-process.v1", "token": token, "distro": distro, "pid": pid,
              "pgid": os.getpgid(pid), "sid": os.getsid(pid), "starttime": process["starttime"],
              "workdir": workdir, "active": True}
    _write(path, record)
    # Second barrier closes the launch/cancel race with a parent seeing no record.
    if Path(cancelled).exists():
        record.update(active=False, launch_cancelled=True)
        _write(path, record)
        raise SolverCancelled("Job was cancelled during Linux launch.")
    result = subprocess.run(command, cwd=workdir)
    record.update(active=False, returncode=result.returncode)
    _write(path, record)
    return result.returncode


def native_process_supported():
    """Native ownership requires Linux process/session identities, not only Popen."""
    return os.name == "posix" and Path("/proc/self/stat").is_file() and Path("/proc/self/environ").is_file()


def worker_process_identity(pid):
    """Query a worker's birth identity; permission failures are not proof of exit."""
    if os.name == "posix":
        process = _proc(pid)
        if process is None and Path(f"/proc/{pid}").exists():
            raise RuntimeError("Worker process identity could not be read.")
        return {"pid": pid, "starttime": process["starttime"]} if process and process["state"] != "Z" else None
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE, *([ctypes.POINTER(wintypes.FILETIME)] * 4)]
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        if ctypes.get_last_error() == 87:  # no such PID
            return None
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        exit_code = wintypes.DWORD()
        if not kernel.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            raise ctypes.WinError(ctypes.get_last_error())
        if exit_code.value != 259:
            return None
        times = [wintypes.FILETIME() for _ in range(4)]
        if not kernel.GetProcessTimes(handle, *(ctypes.byref(value) for value in times)):
            raise ctypes.WinError(ctypes.get_last_error())
        return {"pid": pid, "starttime": str((times[0].dwHighDateTime << 32) | times[0].dwLowDateTime)}
    finally:
        kernel.CloseHandle(handle)


def convergence_runtime_config():
    from tuba.solver.aster import CodeAsterSolver
    from tuba.solver.code_aster_runtime import CodeAsterRuntimeConfig
    solver = CodeAsterSolver()
    return CodeAsterRuntimeConfig(**{key: getattr(solver, key) for key in
        ("exec_method", "docker_image", "wsl_distro", "runner_command", "bridge_python", "timeout_seconds")})


def runtime_capability(candidate):
    if candidate.kind in {"python_bridge", "command"}:
        supported = native_process_supported()
        reason = None if supported else "Cancellable native execution requires Linux /proc ownership. Use a Linux Python bridge/runner or configure an explicit WSL distro on Windows."
    elif candidate.kind == "wsl":
        supported = len(candidate.command) >= 4 and candidate.command[1] == "-d" and candidate.command[3] == "--"
        reason = None if supported else "Configure TUBA_CODE_ASTER_WSL_DISTRO for cancellable WSL execution."
    else:
        supported = False
        reason = "Docker convergence has no verified container cancellation controller. Configure a Linux Python bridge/runner or an explicit WSL distro."
    return {"supported": supported and candidate.available, "runtime": candidate.kind,
            "reason": candidate.reason if not candidate.available else reason}


def convergence_capability(config=None):
    from tuba.solver.code_aster_runtime import discover_code_aster_runtimes
    try:
        candidates = discover_code_aster_runtimes(config or convergence_runtime_config())
    except (ValueError, RuntimeError) as exc:
        return {"supported": False, "runtime": None, "reason": f"Configured Code_Aster runtime is invalid: {exc}"}
    candidate = next((c for c in candidates if c.available), candidates[0])
    return runtime_capability(candidate)


class WslExecutionController:
    """Durable per-job cancellation barrier and separately callable Linux cleanup."""
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.cancel_path = self.directory / "cancelled.json"

    @property
    def cancelled(self):
        return self.cancel_path.exists()

    def check_cancelled(self):
        if self.cancelled:
            raise SolverCancelled("Code_Aster job cancelled; no result publication is permitted.")

    def cancel(self):
        _write(self.cancel_path, {"cancelled": True})
        return self.cleanup()

    def cleanup(self):
        from tuba.solver.code_aster_runtime import _win_to_wsl
        outcomes = []
        helper = _win_to_wsl(Path(__file__).resolve())
        for directory in sorted(self.directory.glob("runtime-*")):
            path = directory / "ownership.json"
            try:
                if not path.is_file():
                    intent = json.loads((directory / "intent.json").read_text(encoding="utf-8"))
                    if intent.get("token") != directory.name.removeprefix("runtime-") or not intent.get("distro"):
                        raise ValueError("Invalid WSL launch intent; cleanup refused.")
                    # If cancellation wins before the receipt, a launch barrier
                    # forbids child spawn. Verify no token-owned process exists;
                    # an active process without its receipt is an explicit error.
                    result = subprocess.run(["wsl", "-d", intent["distro"], "--", "python3", helper,
                        "scan", intent["token"]], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15)
                    if result.returncode or not self.cancelled or json.loads(result.stdout):
                        raise RuntimeError("WSL ownership record is missing after launch; cleanup cannot be verified.")
                    outcomes.append({"verified": True, "launch_prevented": True, "token": intent["token"]})
                    continue
                record = json.loads(path.read_text(encoding="utf-8"))
                if (record.get("schema") != "tuba.wsl-owned-process.v1" or not record.get("distro")
                        or record.get("token") != path.parent.name.removeprefix("runtime-")):
                    raise ValueError("Invalid durable WSL ownership record; cleanup refused.")
                if record.get("cleanup", {}).get("verified") and not record.get("active"):
                    outcomes.append(record["cleanup"])
                    continue
                # Even completed launchers can leave children; Linux revalidates all.
                command = ["wsl", "-d", record["distro"], "--", "python3", helper, "cleanup",
                           _win_to_wsl(path), record["token"]]
                result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15)
                if result.returncode:
                    raise RuntimeError(result.stderr or result.stdout)
                outcomes.append(json.loads(result.stdout.strip().splitlines()[-1]))
            except Exception as exc:
                _write(self.directory / "cleanup.json", {"verified": False, "error": str(exc), "outcomes": outcomes})
                raise RuntimeError(f"Owned WSL cleanup failed: {exc}") from exc
        _write(self.directory / "cleanup.json", {"verified": True, "outcomes": outcomes,
                                                "launch_barrier": self.cancelled})
        return outcomes

    def execute(self, candidate, command, cwd, timeout_seconds, work_dir):
        from tuba.solver.code_aster_runtime import _win_to_wsl
        self.check_cancelled()
        if candidate.kind != "wsl" or len(candidate.command) < 4 or candidate.command[1] != "-d":
            raise RuntimeError("Cancellable convergence requires an explicit WSL distro runtime; configure Ubuntu.")
        distro = candidate.command[2]
        token = uuid4().hex
        receipt = self.directory / f"runtime-{token}" / "ownership.json"
        receipt.parent.mkdir()
        _write(receipt.parent / "intent.json", {"token": token, "distro": distro, "workdir": str(work_dir)})
        helper = _win_to_wsl(Path(__file__).resolve())
        owned = [*candidate.command, "setsid", "--wait", "env", f"TUBA_SOLVER_JOB_TOKEN={token}",
                 "python3", helper, "launch", _win_to_wsl(receipt), token, distro,
                 _win_to_wsl(self.cancel_path), _win_to_wsl(Path(work_dir)), *command[len(candidate.command):]]
        self.check_cancelled()
        process = subprocess.Popen(owned, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, encoding="utf-8", errors="replace",
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        deadline = time.monotonic()+timeout_seconds
        try:
            while True:
                self.check_cancelled()
                if time.monotonic() > deadline:
                    raise subprocess.TimeoutExpired(owned, timeout_seconds)
                try:
                    stdout, stderr = process.communicate(timeout=.2)
                    break
                except subprocess.TimeoutExpired:
                    continue
            self.check_cancelled()
            self.cleanup()
            return subprocess.CompletedProcess(owned, process.returncode, stdout, stderr)
        except BaseException:
            try:
                self.cancel()
            finally:
                if process.poll() is None:
                    process.terminate()
                process.communicate(timeout=10)
            raise


class NativeExecutionController(WslExecutionController):
    """Linux native bridge/runner in a durable, dedicated token-owned session."""
    def cleanup(self):
        outcomes = []
        try:
            for directory in sorted(self.directory.glob("native-*")):
                token = directory.name.removeprefix("native-")
                intent = json.loads((directory / "intent.json").read_text(encoding="utf-8"))
                if intent.get("token") != token or intent.get("distro") != "__native__":
                    raise ValueError("Invalid native launch intent; cleanup refused.")
                path = directory / "ownership.json"
                if not path.is_file():
                    observed = [p for entry in Path("/proc").iterdir() if entry.name.isdigit()
                                and (p := _proc(entry.name)) and p["state"] != "Z" and p["token"] == token]
                    if not self.cancelled or observed:
                        raise RuntimeError("Native ownership record is missing; cleanup cannot be verified.")
                    outcomes.append({"verified": True, "launch_prevented": True, "token": token})
                    continue
                record = json.loads(path.read_text(encoding="utf-8"))
                if (record.get("schema") != "tuba.native-owned-process.v1" or record.get("token") != token
                        or record.get("distro") != "__native__" or record.get("workdir") != intent.get("workdir")):
                    raise ValueError("Invalid native ownership identity/workdir; cleanup refused.")
                outcomes.append(_linux_cleanup(path, token, emit=False))
        except Exception as exc:
            _write(self.directory / "native-cleanup.json", {"verified": False, "error": str(exc), "outcomes": outcomes})
            raise RuntimeError(f"Owned native cleanup failed: {exc}") from exc
        _write(self.directory / "native-cleanup.json", {"verified": True, "outcomes": outcomes})
        return outcomes

    def execute(self, candidate, command, cwd, timeout_seconds, work_dir):
        self.check_cancelled()
        capability = runtime_capability(candidate)
        if not capability["supported"] or candidate.kind not in {"python_bridge", "command"}:
            raise ValueError(capability["reason"] or "Unsupported native runtime.")
        token = uuid4().hex
        receipt = self.directory / f"native-{token}" / "ownership.json"
        receipt.parent.mkdir()
        workdir = str(Path(work_dir).resolve())
        _write(receipt.parent / "intent.json", {"token": token, "distro": "__native__", "workdir": workdir})
        environment = os.environ.copy()
        environment["TUBA_SOLVER_JOB_TOKEN"] = token
        owned = [sys.executable, str(Path(__file__).resolve()), "launch", str(receipt), token,
                 "__native__", str(self.cancel_path), workdir, *command]
        self.check_cancelled()
        process = subprocess.Popen(owned, cwd=cwd, env=environment, start_new_session=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
        deadline = time.monotonic() + timeout_seconds
        try:
            while True:
                self.check_cancelled()
                if time.monotonic() > deadline:
                    raise subprocess.TimeoutExpired(owned, timeout_seconds)
                try:
                    stdout, stderr = process.communicate(timeout=.2)
                    break
                except subprocess.TimeoutExpired:
                    continue
            self.check_cancelled()
            self.cleanup()
            return subprocess.CompletedProcess(owned, process.returncode, stdout, stderr)
        except BaseException:
            try:
                self.cancel()
            finally:
                process.communicate(timeout=10)
            raise


class ExecutionController(WslExecutionController):
    """Runtime dispatch plus one publication barrier; cleanup is usable after reopening."""
    def __init__(self, directory, config=None, *, cleanup_only=False):
        self.capability = None if cleanup_only else convergence_capability(config)
        if not cleanup_only and not self.capability["supported"]:
            raise ValueError(self.capability["reason"])
        super().__init__(directory)

    def cleanup(self):
        outcomes = []
        try:
            outcomes += WslExecutionController(self.directory).cleanup()
            if any(self.directory.glob("native-*")):
                if not native_process_supported():
                    raise RuntimeError("Native ownership cleanup must be retried on its Linux host.")
                outcomes += NativeExecutionController(self.directory).cleanup()
        except Exception as exc:
            _write(self.directory / "cleanup.json", {"verified": False, "error": str(exc), "outcomes": outcomes})
            raise
        _write(self.directory / "cleanup.json", {"verified": True, "outcomes": outcomes, "launch_barrier": self.cancelled})
        return outcomes

    def execute(self, candidate, command, cwd, timeout_seconds, work_dir):
        capability = runtime_capability(candidate)
        if not capability["supported"]:
            raise ValueError(capability["reason"])
        controller = WslExecutionController if candidate.kind == "wsl" else NativeExecutionController
        return controller(self.directory).execute(candidate, command, cwd, timeout_seconds, work_dir)


if __name__ == "__main__":
    if sys.argv[1] == "launch":
        sys.exit(_linux_launch(*sys.argv[2:7], sys.argv[7:]))
    elif sys.argv[1] == "cleanup":
        _linux_cleanup(*sys.argv[2:])
    elif sys.argv[1] == "scan":
        print(json.dumps([p for path in Path("/proc").iterdir() if path.name.isdigit()
                          and (p := _proc(path.name)) and p["state"] != "Z" and p["token"] == sys.argv[2]]))
    else:
        raise ValueError("Unknown ownership helper operation.")
