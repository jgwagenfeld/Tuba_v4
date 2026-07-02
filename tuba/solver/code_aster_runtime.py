"""Runtime discovery and execution for Code_Aster studies."""

from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Mapping, Sequence


DEFAULT_DOCKER_IMAGE = "simvia/code_aster:stable"
DEFAULT_TIMEOUT_SECONDS = 7200


@dataclass(frozen=True)
class CodeAsterRuntimeConfig:
    exec_method: str = "auto"
    docker_image: str = DEFAULT_DOCKER_IMAGE
    wsl_distro: str | None = None
    runner_command: str | None = None
    bridge_python: str | None = None
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    preflight_timeout_seconds: int = 15
    env: Mapping[str, str] = field(default_factory=lambda: os.environ)


@dataclass(frozen=True)
class CodeAsterRuntimeCandidate:
    kind: str
    command: tuple[str, ...]
    available: bool = True
    reason: str | None = None

    @property
    def method(self) -> str:
        return self.kind


@dataclass(frozen=True)
class CodeAsterExecution:
    runtime: CodeAsterRuntimeCandidate
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class CodeAsterRuntimeCheck:
    runtime: CodeAsterRuntimeCandidate
    command: tuple[str, ...]
    returncode: int | None
    stdout: str
    stderr: str
    ok: bool
    reason: str | None = None


def discover_code_aster_runtimes(config: CodeAsterRuntimeConfig) -> list[CodeAsterRuntimeCandidate]:
    methods = _requested_methods(config.exec_method)
    candidates: list[CodeAsterRuntimeCandidate] = []
    bridge_python = config.bridge_python or config.env.get("TUBA_CODE_ASTER_PYTHON")
    runner_command = (
        config.runner_command
        or config.env.get("TUBA_CODE_ASTER_RUNNER_COMMAND")
        or config.env.get("TUBA_CODE_ASTER_RUNNER")
    )
    wsl_distro = config.wsl_distro or config.env.get("TUBA_CODE_ASTER_WSL_DISTRO")

    if "python_bridge" in methods and bridge_python:
        candidates.append(CodeAsterRuntimeCandidate("python_bridge", (bridge_python,)))
    if "command" in methods and (runner_command or config.exec_method == "command"):
        candidates.append(CodeAsterRuntimeCandidate("command", tuple(shlex.split(runner_command or "run_aster"))))
    if "wsl" in methods:
        command = ("wsl", "-d", wsl_distro, "--") if wsl_distro else ("wsl",)
        candidates.append(CodeAsterRuntimeCandidate("wsl", command))
    if "docker" in methods:
        candidates.append(CodeAsterRuntimeCandidate("docker", ("docker", "run", "--rm", config.docker_image)))

    if not candidates:
        candidates.append(
            CodeAsterRuntimeCandidate(
                config.exec_method,
                (),
                available=False,
                reason=(
                    "No Code_Aster runtime was configured. Set TUBA_CODE_ASTER_PYTHON, "
                    "TUBA_CODE_ASTER_RUNNER, exec_method='wsl', or exec_method='docker'."
                ),
            )
        )
    return candidates


def select_code_aster_runtime(config: CodeAsterRuntimeConfig) -> CodeAsterRuntimeCandidate:
    candidates = discover_code_aster_runtimes(config)
    for candidate in candidates:
        if candidate.available:
            return candidate
    first = candidates[0]
    raise RuntimeError(first.reason or "No Code_Aster runtime is available.")


def build_code_aster_command(
    export_file_or_candidate: Path | CodeAsterRuntimeCandidate,
    work_dir_or_export_file: Path,
    config_or_work_dir: CodeAsterRuntimeConfig | Path,
    *,
    docker_image: str = DEFAULT_DOCKER_IMAGE,
) -> tuple[list[str], Path | None] | list[str]:
    """Build the command used to execute a Code_Aster export.

    The public API accepts ``(export_file, work_dir, config)`` and returns
    ``(command, cwd)``.  The candidate-based form is kept for compatibility
    with older internal callers.
    """
    if isinstance(export_file_or_candidate, CodeAsterRuntimeCandidate):
        candidate = export_file_or_candidate
        export_file = work_dir_or_export_file
        work_dir = Path(config_or_work_dir)
        command, _cwd = _build_command_for_candidate(candidate, export_file, work_dir, docker_image=docker_image)
        return command

    export_file = export_file_or_candidate
    work_dir = work_dir_or_export_file
    config = config_or_work_dir
    if not isinstance(config, CodeAsterRuntimeConfig):
        raise TypeError("build_code_aster_command expected CodeAsterRuntimeConfig as the third argument.")
    candidate = select_code_aster_runtime(config)
    return _build_command_for_candidate(candidate, export_file, work_dir, docker_image=config.docker_image)


def _build_command_for_candidate(
    candidate: CodeAsterRuntimeCandidate,
    export_file: Path,
    work_dir: Path,
    *,
    docker_image: str = DEFAULT_DOCKER_IMAGE,
) -> tuple[list[str], Path | None]:
    export_name = export_file.name
    if candidate.kind == "python_bridge":
        bridge_script = Path(__file__).with_name("code_aster_bridge.py").resolve()
        return [*candidate.command, str(bridge_script), export_name], work_dir
    if candidate.kind == "command":
        return [*candidate.command, export_name], work_dir
    if candidate.kind == "wsl":
        wsl_dir = _win_to_wsl(work_dir)
        return [*candidate.command, "bash", "-lc", f"cd {shlex.quote(wsl_dir)} && {_runner_detection_script(export_name)}"], None
    if candidate.kind == "docker":
        image = candidate.command[-1] if candidate.command else docker_image
        return [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{work_dir.resolve()}:/work",
            "-w",
            "/work",
            image,
            "sh",
            "-lc",
            _runner_detection_script(export_name),
        ], None
    raise ValueError(f"Unsupported Code_Aster runtime kind: {candidate.kind}")


def run_code_aster_export(export_file: Path, work_dir: Path, config: CodeAsterRuntimeConfig) -> CodeAsterExecution:
    if not export_file.exists():
        raise FileNotFoundError(f"Export file not found: {export_file}")

    attempted: list[CodeAsterExecution] = []
    for candidate in discover_code_aster_runtimes(config):
        if not candidate.available:
            continue
        command, cwd = _build_command_for_candidate(candidate, export_file, work_dir, docker_image=config.docker_image)
        try:
            result = subprocess.run(
                command,
                cwd=str(cwd) if cwd is not None else None,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=config.timeout_seconds,
            )
            execution = CodeAsterExecution(
                candidate,
                tuple(command),
                result.returncode,
                result.stdout or "",
                result.stderr or "",
            )
        except FileNotFoundError as exc:
            execution = CodeAsterExecution(candidate, tuple(command), 127, "", str(exc))
        attempted.append(execution)
        _write_runtime_logs(work_dir, execution)
        if execution.returncode == 0:
            _write_compat_logs(work_dir, execution)
            return execution
        if not _should_try_next(config.exec_method, execution):
            break

    if not attempted:
        raise RuntimeError("No executable Code_Aster runtime candidate was available.")
    failed = attempted[-1]
    _write_compat_logs(work_dir, failed)
    raise RuntimeError(_failure_message(failed, attempted, work_dir))


def _requested_methods(exec_method: str) -> list[str]:
    if exec_method == "auto":
        return ["python_bridge", "command", "wsl", "docker"]
    if exec_method in {"python_bridge", "command", "wsl", "docker"}:
        return [exec_method]
    raise ValueError(
        "Unsupported Code_Aster exec_method. "
        "Supported values: 'auto', 'python_bridge', 'command', 'wsl', 'docker'."
    )


def _win_to_wsl(path: Path) -> str:
    posix = path.as_posix()
    if len(posix) >= 2 and posix[1] == ":":
        return f"/mnt/{posix[0].lower()}{posix[2:]}"
    return posix


def _runner_detection_script(export_name: str) -> str:
    export_arg = shlex.quote(export_name)
    return (
        f"if command -v run_aster >/dev/null 2>&1; then run_aster {export_arg}; "
        f"elif command -v as_run >/dev/null 2>&1; then as_run {export_arg}; "
        f"elif command -v aster >/dev/null 2>&1; then aster {export_arg}; "
        'else echo "Code_Aster runner not found" >&2; exit 127; fi'
    )


def _runner_probe_script(probe_file: str | None = None) -> str:
    parts: list[str] = ["set -e"]
    if probe_file:
        probe_arg = shlex.quote(probe_file)
        parts.extend(
            [
                f"rm -f {probe_arg}",
                f": > {probe_arg}",
                f"test -f {probe_arg}",
                f"rm -f {probe_arg}",
            ]
        )
    parts.append(
        "if command -v run_aster >/dev/null 2>&1; then run_aster --help >/dev/null 2>&1; echo run_aster; "
        "elif command -v as_run >/dev/null 2>&1; then as_run --help >/dev/null 2>&1; echo as_run; "
        "elif command -v aster >/dev/null 2>&1; then aster --help >/dev/null 2>&1; echo aster; "
        'else echo "Code_Aster runner not found" >&2; exit 127; fi'
    )
    return "; ".join(parts)


def build_code_aster_preflight_command(
    candidate: CodeAsterRuntimeCandidate,
    config: CodeAsterRuntimeConfig,
    work_dir: Path | None = None,
) -> tuple[list[str], Path | None]:
    if candidate.kind == "python_bridge":
        return [*candidate.command, "-c", "import run_aster.export, run_aster.run; print('run_aster python bridge ok')"], None
    if candidate.kind == "command":
        return [*candidate.command, "--help"], None
    if candidate.kind == "wsl":
        if work_dir is None:
            raise ValueError("build_code_aster_preflight_command requires work_dir for WSL preflight.")
        wsl_dir = _win_to_wsl(work_dir)
        return [*candidate.command, "bash", "-lc", f"cd {shlex.quote(wsl_dir)} && {_runner_probe_script('.tuba-preflight-probe')}"], None
    if candidate.kind == "docker":
        if work_dir is None:
            raise ValueError("build_code_aster_preflight_command requires work_dir for Docker preflight.")
        image = candidate.command[-1] if candidate.command else config.docker_image
        return [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{work_dir.resolve()}:/work",
            "-w",
            "/work",
            image,
            "sh",
            "-lc",
            _runner_probe_script(".tuba-preflight-probe"),
        ], None
    return [], None


def preflight_code_aster_runtimes(config: CodeAsterRuntimeConfig) -> list[CodeAsterRuntimeCheck]:
    checks: list[CodeAsterRuntimeCheck] = []
    with TemporaryDirectory(prefix="tuba-code-aster-preflight-") as tmpdir:
        work_dir = Path(tmpdir)
        for candidate in discover_code_aster_runtimes(config):
            if not candidate.available:
                checks.append(
                    CodeAsterRuntimeCheck(
                        runtime=candidate,
                        command=tuple(candidate.command),
                        returncode=None,
                        stdout="",
                        stderr="",
                        ok=False,
                        reason=candidate.reason or "Runtime candidate is not available.",
                    )
                )
                continue
            candidate_work_dir = work_dir if candidate.kind in {"wsl", "docker"} else None
            command, cwd = build_code_aster_preflight_command(candidate, config, candidate_work_dir)
            try:
                result = subprocess.run(
                    command,
                    cwd=str(cwd) if cwd is not None else None,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=config.preflight_timeout_seconds,
                )
                stdout = result.stdout or ""
                stderr = result.stderr or ""
                ok = result.returncode == 0
                reason = None if ok else (stderr or stdout or f"return code {result.returncode}")
                checks.append(
                    CodeAsterRuntimeCheck(
                        runtime=candidate,
                        command=tuple(command),
                        returncode=result.returncode,
                        stdout=stdout,
                        stderr=stderr,
                        ok=ok,
                        reason=reason,
                    )
                )
            except subprocess.TimeoutExpired as exc:
                checks.append(
                    CodeAsterRuntimeCheck(
                        runtime=candidate,
                        command=tuple(command),
                        returncode=None,
                        stdout=str(exc.output or ""),
                        stderr=str(exc.stderr or ""),
                        ok=False,
                        reason=f"{candidate.kind} preflight timed out after {config.preflight_timeout_seconds} seconds.",
                    )
                )
            except FileNotFoundError as exc:
                checks.append(
                    CodeAsterRuntimeCheck(
                        runtime=candidate,
                        command=tuple(command),
                        returncode=127,
                        stdout="",
                        stderr=str(exc),
                        ok=False,
                        reason=str(exc),
                    )
                )
    return checks


def _write_runtime_logs(work_dir: Path, execution: CodeAsterExecution) -> None:
    (work_dir / f"stdout.{execution.runtime.kind}.log").write_text(execution.stdout, encoding="utf-8")
    (work_dir / f"stderr.{execution.runtime.kind}.log").write_text(execution.stderr, encoding="utf-8")


def _write_compat_logs(work_dir: Path, execution: CodeAsterExecution) -> None:
    (work_dir / "stdout.log").write_text(execution.stdout, encoding="utf-8")
    (work_dir / "stderr.log").write_text(execution.stderr, encoding="utf-8")


def _should_try_next(exec_method: str, execution: CodeAsterExecution) -> bool:
    if exec_method != "auto":
        return False
    return execution.returncode == 127 or "Code_Aster runner not found" in execution.stderr


def _failure_message(failed: CodeAsterExecution, attempted: Sequence[CodeAsterExecution], work_dir: Path) -> str:
    mess_tail = ""
    mess_file = work_dir / "study.mess"
    if mess_file.exists():
        mess_tail = "\n".join(mess_file.read_text(encoding="utf-8", errors="replace").splitlines()[-40:])
    attempts = "\n".join(
        f"{item.runtime.kind}: return code {item.returncode}; stderr tail: {item.stderr[-300:]}"
        for item in attempted
    )
    return (
        f"Code_Aster failed through {failed.runtime.kind} with return code {failed.returncode}.\n"
        f"stderr: {failed.stderr[-500:]}\n"
        f"--- Last lines of study.mess ---\n{mess_tail}\n"
        f"--- Runtime attempts ---\n{attempts}"
    )
