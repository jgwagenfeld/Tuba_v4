"""Runtime discovery and execution for Code_Aster studies."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Mapping, Sequence

from tuba.analysis.provenance import SolverInputIdentity, require_matching_solver_input_identities


DEFAULT_DOCKER_IMAGE = "simvia/code_aster:stable"
DEFAULT_TIMEOUT_SECONDS = 7200
DEFAULT_WSL_DISTRO = "Ubuntu"
ATTESTED_CODE_ASTER_FILES = (
    "study.comm", "study.mail", "study.export", "study_manifest.json",
    "study_tuba_fem.json", "study.mess", "study.rmed", "study_depl.csv",
    "study_effo.csv", "study_reac.csv", "study_sieq.csv",
)
VOLUME_ATTESTED_CODE_ASTER_FILES = (
    "study.comm", "study.med", "study.export", "study_manifest.json",
    "study_tuba_fem.json", "study.mess", "study.rmed", "study_depl.csv",
    "study_reac.csv", "study_sieq.csv",
)
_EXECUTION_ATTESTATION_SCHEMA = "tuba.code_aster_execution.v1"
_SOLVER_VERSION_PATTERN = re.compile(r"\bVersion\s+(\d+(?:\.\d+)+)\b")
_EXECUTION_ATTESTATION_FIELDS = frozenset(
    {
        "schema_version", "solver_name", "solver_version", "execution_method",
        "solved_at", "solver_input_identity", "artifacts",
    }
)
_SOLVER_INPUT_IDENTITY_FIELDS = frozenset({"fingerprint", "load_case", "schema_id", "compiler_id"})
_ARTIFACT_INTEGRITY_FIELDS = frozenset({"size_bytes", "sha256"})


@dataclass(frozen=True)
class CodeAsterRuntimeConfig:
    exec_method: str = "auto"
    docker_image: str = DEFAULT_DOCKER_IMAGE
    wsl_distro: str | None = None
    runner_command: str | None = None
    bridge_python: str | None = None
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    preflight_timeout_seconds: int = 45
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
        if wsl_distro:
            candidates.append(CodeAsterRuntimeCandidate("wsl", ("wsl", "-d", wsl_distro, "--")))
        else:
            candidates.append(CodeAsterRuntimeCandidate("wsl", ("wsl", "-d", DEFAULT_WSL_DISTRO, "--")))
            candidates.append(CodeAsterRuntimeCandidate("wsl", ("wsl",)))
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
    export_file: Path,
    work_dir: Path,
    config: CodeAsterRuntimeConfig,
) -> tuple[list[str], Path | None]:
    """Build the command used to execute a Code_Aster export.

    Accepts ``(export_file, work_dir, config)`` and returns ``(command, cwd)``.
    """
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


def write_code_aster_execution_attestation(
    work_dir: str | Path,
    execution: CodeAsterExecution,
    solver_input_identity: SolverInputIdentity | None,
) -> dict[str, Any]:
    """Record observed, portable facts from a successful Code_Aster execution."""
    root = Path(work_dir)
    if execution.returncode != 0:
        raise ValueError("Cannot attest an unsuccessful Code_Aster execution.")
    if solver_input_identity is None:
        raise ValueError("Cannot attest a Code_Aster solve without a solver input identity.")
    mess_path = root / "study.mess"
    if not mess_path.is_file():
        raise ValueError(f"Cannot attest Code_Aster execution: missing required artifact {mess_path.name}.")
    version_match = _SOLVER_VERSION_PATTERN.search(mess_path.read_text(encoding="utf-8", errors="replace"))
    if version_match is None:
        raise ValueError("Cannot attest Code_Aster execution: study.mess does not report a solver Version X.Y.Z.")
    artifact_names = attested_code_aster_files(root)
    artifacts = {
        filename: _file_integrity(root / filename)
        for filename in artifact_names
    }
    payload = {
        "schema_version": _EXECUTION_ATTESTATION_SCHEMA,
        "solver_name": "Code_Aster",
        "solver_version": version_match.group(1),
        "execution_method": execution.runtime.kind,
        "solved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "solver_input_identity": solver_input_identity.to_dict(),
        "artifacts": artifacts,
    }
    (root / "study_execution.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def load_code_aster_execution_attestation(work_dir: str | Path) -> dict[str, Any] | None:
    """Load and integrity-check a solve attestation, if this artifact directory has one."""
    root = Path(work_dir)
    path = root / "study_execution.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid Code_Aster execution attestation {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid Code_Aster execution attestation {path}: expected an object.")
    _require_exact_fields(payload, _EXECUTION_ATTESTATION_FIELDS, "attestation", path)
    if payload.get("schema_version") != _EXECUTION_ATTESTATION_SCHEMA:
        raise ValueError(f"Invalid Code_Aster execution attestation {path}: unsupported schema_version.")
    if payload.get("solver_name") != "Code_Aster":
        raise ValueError(f"Invalid Code_Aster execution attestation {path}: solver_name must be Code_Aster.")
    if not isinstance(payload.get("solver_version"), str) or not _SOLVER_VERSION_PATTERN.fullmatch(
        f"Version {payload.get('solver_version', '')}"
    ):
        raise ValueError(f"Invalid Code_Aster execution attestation {path}: solver_version is required.")
    if not isinstance(payload.get("execution_method"), str) or not payload["execution_method"]:
        raise ValueError(f"Invalid Code_Aster execution attestation {path}: execution_method is required.")
    _validate_solved_at(payload.get("solved_at"), path)
    _attestation_identity(payload.get("solver_input_identity"), path)
    artifact_names = attested_code_aster_files(root)
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != set(artifact_names):
        raise ValueError(f"Invalid Code_Aster execution attestation {path}: required artifact inventory does not match.")
    for filename in artifact_names:
        expected = artifacts[filename]
        if not isinstance(expected, dict):
            raise ValueError(f"Invalid Code_Aster execution attestation {path}: {filename} integrity record is invalid.")
        _require_exact_fields(expected, _ARTIFACT_INTEGRITY_FIELDS, f"{filename} integrity record", path)
        if not isinstance(expected["size_bytes"], int) or expected["size_bytes"] < 0:
            raise ValueError(f"Invalid Code_Aster execution attestation {path}: {filename} size_bytes is invalid.")
        if not isinstance(expected["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", expected["sha256"]):
            raise ValueError(f"Invalid Code_Aster execution attestation {path}: {filename} sha256 is invalid.")
        actual = _file_integrity(root / filename)
        if expected.get("size_bytes") != actual["size_bytes"]:
            raise ValueError(f"Code_Aster execution attestation {path}: {filename} size does not match.")
        if expected.get("sha256") != actual["sha256"]:
            raise ValueError(f"Code_Aster execution attestation {path}: {filename} hash does not match.")
    return payload


def attested_code_aster_files(work_dir: str | Path) -> tuple[str, ...]:
    """Return the artifact inventory for the study compiler recorded in its manifest."""
    manifest_path = Path(work_dir) / "study_manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ATTESTED_CODE_ASTER_FILES
    metadata = manifest.get("study", {}).get("metadata", {})
    if not metadata.get("volume_analysis"):
        if metadata.get("pipe_stress_exported") is False:
            return tuple(name for name in ATTESTED_CODE_ASTER_FILES if name != "study_sieq.csv")
        return ATTESTED_CODE_ASTER_FILES
    return VOLUME_ATTESTED_CODE_ASTER_FILES + (
        ("study_sigm.csv",) if metadata.get("tensor_stress_exported", True) else ()
    )


def validate_code_aster_execution_attestation(
    work_dir: str | Path,
    *,
    study_identity: SolverInputIdentity | None,
    mesh_identity: SolverInputIdentity | None,
    sidecar_identity: SolverInputIdentity | None,
) -> dict[str, Any] | None:
    """Require an attested solve, when present, to bind to every artifact identity."""
    payload = load_code_aster_execution_attestation(work_dir)
    if payload is None:
        return None
    attestation_identity = _attestation_identity(payload["solver_input_identity"], Path(work_dir) / "study_execution.json")
    for context, identity in (
        ("Code_Aster study", study_identity),
        ("Code_Aster analysis mesh", mesh_identity),
        ("Code_Aster sidecar", sidecar_identity),
    ):
        if identity is None:
            raise ValueError(f"Attested Code_Aster execution requires a non-null solver input identity on the {context}.")
        require_matching_solver_input_identities(
            attestation_identity,
            identity,
            context=f"Code_Aster execution attestation and {context}",
        )
    return payload


def _file_integrity(path: Path) -> dict[str, int | str]:
    if not path.is_file():
        raise ValueError(f"Cannot attest Code_Aster execution: missing required artifact {path.name}.")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"size_bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def _attestation_identity(value: Any, path: Path) -> SolverInputIdentity:
    if not isinstance(value, dict):
        raise ValueError(f"Invalid Code_Aster execution attestation {path}: solver_input_identity is required.")
    _require_exact_fields(value, _SOLVER_INPUT_IDENTITY_FIELDS, "solver_input_identity", path)
    if any(not isinstance(value[key], str) or not value[key] for key in _SOLVER_INPUT_IDENTITY_FIELDS):
        raise ValueError(f"Invalid Code_Aster execution attestation {path}: solver_input_identity is required.")
    return SolverInputIdentity.from_dict(value)


def _validate_solved_at(value: Any, path: Path) -> None:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"Invalid Code_Aster execution attestation {path}: solved_at must be a UTC timestamp.")
    try:
        datetime.fromisoformat(f"{value[:-1]}+00:00")
    except ValueError as exc:
        raise ValueError(f"Invalid Code_Aster execution attestation {path}: solved_at is invalid.") from exc


def _require_exact_fields(value: Mapping[str, Any], fields: frozenset[str], label: str, path: Path) -> None:
    unknown = sorted(set(value) - fields)
    missing = sorted(fields - set(value))
    if unknown or missing:
        details = []
        if unknown:
            details.append(f"unknown fields: {', '.join(unknown)}")
        if missing:
            details.append(f"missing fields: {', '.join(missing)}")
        raise ValueError(f"Invalid Code_Aster execution attestation {path}: {label} has {'; '.join(details)}.")


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
    mess_file = work_dir / "study.mess"
    mess_tail = _file_tail(mess_file) if mess_file.exists() else "study.mess was not written."
    attempts = "\n".join(
        (
            f"{item.runtime.kind}: command={shlex.join(item.command)}; "
            f"return code {item.returncode}; "
            f"stdout log={work_dir / f'stdout.{item.runtime.kind}.log'}; "
            f"stderr log={work_dir / f'stderr.{item.runtime.kind}.log'}; "
            f"stdout tail: {_text_tail(item.stdout, 300)}; "
            f"stderr tail: {_text_tail(item.stderr, 300)}"
        )
        for item in attempted
    )
    return (
        f"Code_Aster failed through {failed.runtime.kind} with return code {failed.returncode}.\n"
        f"command: {shlex.join(failed.command)}\n"
        f"stdout log: {work_dir / f'stdout.{failed.runtime.kind}.log'}\n"
        f"stderr log: {work_dir / f'stderr.{failed.runtime.kind}.log'}\n"
        f"stdout tail: {_text_tail(failed.stdout)}\n"
        f"stderr tail: {_text_tail(failed.stderr)}\n"
        f"--- Last lines of {mess_file} ---\n{mess_tail}\n"
        f"--- Runtime attempts ---\n{attempts}"
    )


def _file_tail(path: Path, *, lines: int = 40) -> str:
    return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])


def _text_tail(text: str, chars: int = 500) -> str:
    return text[-chars:] if text else ""
