# Code Aster Runtime Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Code_Aster execution a first-class, tested Tuba runtime path: define a pipe model, solve it with Code_Aster, import solver artifacts, and display processed results without mock/proxy values.

**Architecture:** Keep Tuba pipe-native and keep `CodeAsterSolver` as the authoritative solver adapter. Add a focused runtime layer that discovers and executes Code_Aster through a configured Python/conda/WSL/Docker environment, then feeds existing CSV/RMED artifact import paths. Borrow ada-py's lifecycle shape, `write -> execute -> postprocess`, but do not copy or depend on ada-py implementation code.

**Tech Stack:** Python 3.10+, `unittest`, `subprocess`, existing `CodeAsterSolver`, existing `AnalysisStudy` and `ResultState`, optional Code_Aster `run_aster` Python package inside the solver environment, optional Docker fallback.

## Global Constraints

- Tuba v4 production workflow is `Tuba model -> Code_Aster solve -> processed result display`.
- Code_Aster execution is not optional for production stress, displacement, reaction, thermal expansion, operating-state clash, compliance, and result visualization workflows.
- Export-only paths are development, diagnostic, or batch-handoff tools, not completed engineering evaluation.
- Do not display, report, or score fabricated/mock/proxy solver values as Code_Aster results.
- Tuba remains pipe-native: do not replace `TubaModel`, routing, supports, `CodeAsterSolver`, result states, deformed envelopes, or clash checks with ada-py abstractions.
- `ada-py` is GPL-3.0-or-later. Do not vendor or copy ada-py source. Do not make ada-py a mandatory dependency.
- Tuba is LGPL. Keep GPL solver/runtime boundaries external-process/file based unless the project explicitly accepts stronger copyleft obligations.
- Windows is the primary developer workstation. The production Code_Aster runtime may run under WSL, conda/pixi Linux, or Docker.
- Prefer `run_aster` over legacy `as_run`. Keep `as_run` only as a compatibility fallback.

---

## Source Facts

- Official Code_Aster docs say `bin/run_aster path/to/file.export` executes a study from a `.export` file, and the Python package provides `run_aster.export.Export` plus `run_aster.run.RunAster` for execution.
- Official Code_Aster docs describe `code_aster.Commands` and `code_aster.CA` as direct Python APIs, but the existing Tuba `.comm/.mail/.export` workflow should first stabilize through `run_aster`.
- ada-py's main Code_Aster backend wires three stages: preprocessor `to_fem`, executor `run_code_aster`, postprocessor `read_rmed_file`; it maps Code_Aster to `run_aster`.
- The current Tuba checkout already exports `.mail`, `.comm`, `.export`, `study_manifest.json`, and `study_tuba_fem.json`; it already imports `study_depl.csv`, `study_effo.csv`, `study_reac.csv`, `study_sieq.csv`, and optional `study.rmed`.

Reference links:

- Official `run_aster` docs: https://codeaster.readthedocs.io/en/latest/devguide/run_aster/run_aster.html
- Official `code_aster` Python package docs: https://codeaster.readthedocs.io/en/latest/devguide/code_aster/code_aster.html

---

## Files To Create Or Modify

- Create `tuba/solver/code_aster_runtime.py`  
  Owns runtime configuration, discovery, command construction, execution, logs, and actionable diagnostics.

- Create `tuba/solver/code_aster_bridge.py`  
  Small module executed by a Code_Aster Python interpreter. It runs an exported study through the `run_aster` Python API when available, with a `run_aster` CLI fallback.

- Create `tuba/solver/code_aster_doctor.py`  
  Command-line diagnostics via `python -m tuba.solver.code_aster_doctor`.

- Modify `tuba/solver/aster.py`  
  Replace local WSL/Docker execution logic with `code_aster_runtime.run_code_aster_export(...)`, while preserving `CodeAsterSolver` public behavior.

- Modify `tuba/analysis/code_aster_notebook.py`  
  Default notebook execution to `exec_method="auto"` and pass runtime options through.

- Modify `README.md`, `AGENTS.md`, and `installation_and_interface_strategy.md`  
  Document the non-optional solver runtime, environment variables, doctor command, and real integration smoke test.

- Create `tests/test_code_aster_runtime.py`  
  Unit coverage for runtime discovery, priority, command building, log handling, and failure messages.

- Create `tests/test_code_aster_bridge.py`  
  Unit coverage for the bridge with fake `run_aster` modules and CLI fallback.

- Modify `tests/test_code_aster_study.py`  
  Update execution tests to target the new runtime module while keeping solver-level compatibility tests.

- Modify `tests/test_code_aster_notebook_loader.py`  
  Assert notebook helper defaults to auto runtime and still runs solver before artifact import.

- Create `tests/test_code_aster_doctor.py`  
  Unit coverage for CLI text/JSON diagnostics.

- Create `tests/integration/test_code_aster_real_smoke.py`  
  Gated real Code_Aster smoke test. Skips unless `TUBA_RUN_CODE_ASTER_INTEGRATION=1`.

Use this unit baseline after each task:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_code_aster_runtime tests.test_code_aster_bridge tests.test_code_aster_study tests.test_code_aster_notebook_loader tests.test_code_aster_doctor -v
```

Expected:

```text
OK
```

Use this real-solver baseline only when Code_Aster is configured:

```powershell
$env:TUBA_RUN_CODE_ASTER_INTEGRATION = "1"
.\.venv\Scripts\python.exe -m unittest tests.integration.test_code_aster_real_smoke -v
```

Expected:

```text
OK
```

---

### Task 1: Runtime Contract And Discovery

**Files:**
- Create: `tuba/solver/code_aster_runtime.py`
- Create: `tests/test_code_aster_runtime.py`

**Interfaces:**
- Produces: `CodeAsterRuntimeConfig`, `CodeAsterRuntimeCandidate`, `CodeAsterExecution`, `discover_code_aster_runtimes(config)`, `select_code_aster_runtime(config)`, `build_code_aster_command(candidate, export_file, work_dir)`, `run_code_aster_export(export_file, work_dir, config)`.
- Consumes: standard library only.

- [ ] **Step 1: Write failing discovery tests**

Create `tests/test_code_aster_runtime.py`:

```python
import os
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from tuba.solver.code_aster_runtime import (
    CodeAsterRuntimeConfig,
    build_code_aster_command,
    discover_code_aster_runtimes,
    run_code_aster_export,
    select_code_aster_runtime,
)


class TestCodeAsterRuntime(unittest.TestCase):
    def test_env_python_bridge_has_first_priority_in_auto_mode(self):
        env = {"TUBA_CODE_ASTER_PYTHON": "/opt/aster/bin/python"}
        config = CodeAsterRuntimeConfig(exec_method="auto", env=env)

        candidates = discover_code_aster_runtimes(config)

        self.assertEqual(candidates[0].kind, "python_bridge")
        self.assertEqual(candidates[0].command, ("/opt/aster/bin/python",))
        self.assertTrue(candidates[0].available)

    def test_explicit_runner_command_builds_shell_runner(self):
        config = CodeAsterRuntimeConfig(exec_method="command", runner_command="run_aster")
        candidate = select_code_aster_runtime(config)

        with TemporaryDirectory() as tmpdir:
            cmd = build_code_aster_command(candidate, Path(tmpdir) / "study.export", Path(tmpdir))

        self.assertEqual(cmd[:2], ["run_aster", "study.export"])

    def test_wsl_command_uses_posix_workdir_and_runner_detection(self):
        config = CodeAsterRuntimeConfig(exec_method="wsl")
        candidate = select_code_aster_runtime(config)

        cmd = build_code_aster_command(candidate, Path("D:/Gitprojects/Tuba_v4/code_aster_study/study.export"), Path("D:/Gitprojects/Tuba_v4/code_aster_study"))

        self.assertEqual(cmd[:3], ["wsl", "bash", "-lc"])
        self.assertIn("/mnt/d/Gitprojects/Tuba_v4/code_aster_study", cmd[3])
        self.assertIn("run_aster study.export", cmd[3])
        self.assertIn("as_run study.export", cmd[3])

    def test_docker_command_mounts_workdir(self):
        config = CodeAsterRuntimeConfig(exec_method="docker", docker_image="local/code-aster:dev")
        candidate = select_code_aster_runtime(config)

        with TemporaryDirectory() as tmpdir:
            cmd = build_code_aster_command(candidate, Path(tmpdir) / "study.export", Path(tmpdir))

        self.assertEqual(cmd[:3], ["docker", "run", "--rm"])
        self.assertIn("local/code-aster:dev", cmd)
        self.assertIn("study.export", cmd[-1])

    def test_run_code_aster_export_writes_per_runtime_logs(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            export_file = root / "study.export"
            export_file.write_text("", encoding="utf-8")
            config = CodeAsterRuntimeConfig(exec_method="command", runner_command="run_aster")

            def fake_run(cmd, **kwargs):
                return subprocess.CompletedProcess(cmd, 0, stdout="solver stdout", stderr="solver stderr")

            with patch("tuba.solver.code_aster_runtime.subprocess.run", fake_run):
                execution = run_code_aster_export(export_file, root, config)

        self.assertEqual(execution.returncode, 0)
        self.assertEqual(execution.runtime.kind, "command")
        self.assertEqual((Path(tmpdir) / "stdout.command.log").read_text(encoding="utf-8"), "solver stdout")
        self.assertEqual((Path(tmpdir) / "stderr.command.log").read_text(encoding="utf-8"), "solver stderr")

    def test_auto_mode_falls_back_from_missing_wsl_runner_to_docker(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            export_file = root / "study.export"
            export_file.write_text("", encoding="utf-8")
            config = CodeAsterRuntimeConfig(exec_method="auto", docker_image="local/code-aster:dev", env={})
            calls = []

            def fake_run(cmd, **kwargs):
                calls.append(cmd)
                if cmd[0] == "wsl":
                    return subprocess.CompletedProcess(cmd, 127, stdout="", stderr="Code_Aster runner not found")
                return subprocess.CompletedProcess(cmd, 0, stdout="docker ok", stderr="")

            with patch("tuba.solver.code_aster_runtime.subprocess.run", fake_run):
                execution = run_code_aster_export(export_file, root, config)

        self.assertEqual(execution.runtime.kind, "docker")
        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_code_aster_runtime -v
```

Expected:

```text
ModuleNotFoundError: No module named 'tuba.solver.code_aster_runtime'
```

- [ ] **Step 3: Add the runtime module**

Create `tuba/solver/code_aster_runtime.py`:

```python
"""Runtime discovery and execution for Code_Aster studies."""

from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence


DEFAULT_DOCKER_IMAGE = "simvia/code_aster:stable"
DEFAULT_TIMEOUT_SECONDS = 7200


@dataclass(frozen=True)
class CodeAsterRuntimeConfig:
    exec_method: str = "auto"
    docker_image: str = DEFAULT_DOCKER_IMAGE
    runner_command: str | None = None
    bridge_python: str | None = None
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    env: Mapping[str, str] = field(default_factory=lambda: os.environ)


@dataclass(frozen=True)
class CodeAsterRuntimeCandidate:
    kind: str
    command: tuple[str, ...]
    available: bool = True
    reason: str | None = None


@dataclass(frozen=True)
class CodeAsterExecution:
    runtime: CodeAsterRuntimeCandidate
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


def discover_code_aster_runtimes(config: CodeAsterRuntimeConfig) -> list[CodeAsterRuntimeCandidate]:
    methods = _requested_methods(config.exec_method)
    candidates: list[CodeAsterRuntimeCandidate] = []
    bridge_python = config.bridge_python or config.env.get("TUBA_CODE_ASTER_PYTHON")
    runner_command = config.runner_command or config.env.get("TUBA_CODE_ASTER_RUNNER")

    if "python_bridge" in methods and bridge_python:
        candidates.append(CodeAsterRuntimeCandidate("python_bridge", (bridge_python,)))
    if "command" in methods and runner_command:
        candidates.append(CodeAsterRuntimeCandidate("command", tuple(shlex.split(runner_command))))
    if "wsl" in methods:
        candidates.append(CodeAsterRuntimeCandidate("wsl", ("wsl",)))
    if "docker" in methods:
        candidates.append(CodeAsterRuntimeCandidate("docker", ("docker", "run", "--rm", config.docker_image)))

    if not candidates:
        candidates.append(
            CodeAsterRuntimeCandidate(
                config.exec_method,
                (),
                available=False,
                reason="No Code_Aster runtime was configured. Set TUBA_CODE_ASTER_PYTHON, TUBA_CODE_ASTER_RUNNER, exec_method='wsl', or exec_method='docker'.",
            )
        )
    return candidates


def select_code_aster_runtime(config: CodeAsterRuntimeConfig) -> CodeAsterRuntimeCandidate:
    for candidate in discover_code_aster_runtimes(config):
        if candidate.available:
            return candidate
    first = discover_code_aster_runtimes(config)[0]
    raise RuntimeError(first.reason or "No Code_Aster runtime is available.")


def build_code_aster_command(candidate: CodeAsterRuntimeCandidate, export_file: Path, work_dir: Path, *, docker_image: str = DEFAULT_DOCKER_IMAGE) -> list[str]:
    export_name = export_file.name
    if candidate.kind == "python_bridge":
        return [*candidate.command, "-m", "tuba.solver.code_aster_bridge", "--export", export_name, "--workdir", str(work_dir)]
    if candidate.kind == "command":
        return [*candidate.command, export_name]
    if candidate.kind == "wsl":
        wsl_dir = _win_to_wsl(work_dir)
        return ["wsl", "bash", "-lc", f"cd {shlex.quote(wsl_dir)} && {_runner_detection_script(export_name)}"]
    if candidate.kind == "docker":
        image = candidate.command[-1] if candidate.command else docker_image
        return ["docker", "run", "--rm", "-v", f"{work_dir.resolve()}:/work", "-w", "/work", image, "sh", "-lc", _runner_detection_script(export_name)]
    raise ValueError(f"Unsupported Code_Aster runtime kind: {candidate.kind}")


def run_code_aster_export(export_file: Path, work_dir: Path, config: CodeAsterRuntimeConfig) -> CodeAsterExecution:
    if not export_file.exists():
        raise FileNotFoundError(f"Export file not found: {export_file}")

    attempted: list[CodeAsterExecution] = []
    for candidate in discover_code_aster_runtimes(config):
        if not candidate.available:
            continue
        command = build_code_aster_command(candidate, export_file, work_dir, docker_image=config.docker_image)
        result = subprocess.run(command, cwd=str(work_dir) if candidate.kind in {"command", "python_bridge"} else None, capture_output=True, text=True, timeout=config.timeout_seconds)
        execution = CodeAsterExecution(candidate, tuple(command), result.returncode, result.stdout, result.stderr)
        attempted.append(execution)
        _write_runtime_logs(work_dir, execution)
        if result.returncode == 0:
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
    raise ValueError("Unsupported Code_Aster exec_method. Supported values: 'auto', 'python_bridge', 'command', 'wsl', 'docker'.")


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
        "else echo \"Code_Aster runner not found\" >&2; exit 127; fi"
    )


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
    attempts = "\n".join(f"{item.runtime.kind}: return code {item.returncode}; stderr tail: {item.stderr[-300:]}" for item in attempted)
    return (
        f"Code_Aster failed through {failed.runtime.kind} with return code {failed.returncode}.\n"
        f"stderr: {failed.stderr[-500:]}\n"
        f"--- Last lines of study.mess ---\n{mess_tail}\n"
        f"--- Runtime attempts ---\n{attempts}"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_code_aster_runtime -v
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit**

```powershell
git add tuba/solver/code_aster_runtime.py tests/test_code_aster_runtime.py
git commit -m "feat: add Code_Aster runtime discovery"
```

---

### Task 2: Code Aster Python Bridge

**Files:**
- Create: `tuba/solver/code_aster_bridge.py`
- Create: `tests/test_code_aster_bridge.py`

**Interfaces:**
- Consumes: `run_aster.export.Export`, `run_aster.run.RunAster` when executed inside a Code_Aster Python environment.
- Produces: `run_export(export_path: Path, workdir: Path | None = None) -> int` and CLI `python -m tuba.solver.code_aster_bridge --export study.export --workdir .`.

- [ ] **Step 1: Write failing bridge tests**

Create `tests/test_code_aster_bridge.py`:

```python
import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from tuba.solver import code_aster_bridge


class TestCodeAsterBridge(unittest.TestCase):
    def test_run_export_uses_run_aster_python_api_when_available(self):
        calls = {}

        class FakeExport:
            def __init__(self, filename=None, check=True):
                calls["export_filename"] = filename
                calls["export_check"] = check

        class FakeRunner:
            @classmethod
            def factory(cls, export, tee=False, output=None):
                calls["factory_tee"] = tee
                calls["factory_output"] = output
                return cls()

            def execute(self, workdir):
                calls["workdir"] = workdir
                return types.SimpleNamespace(exitcode=0)

        fake_export_mod = types.ModuleType("run_aster.export")
        fake_export_mod.Export = FakeExport
        fake_run_mod = types.ModuleType("run_aster.run")
        fake_run_mod.RunAster = FakeRunner

        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            export_file = root / "study.export"
            export_file.write_text("", encoding="utf-8")
            with patch.dict(sys.modules, {"run_aster.export": fake_export_mod, "run_aster.run": fake_run_mod}):
                exitcode = code_aster_bridge.run_export(export_file, root)

        self.assertEqual(exitcode, 0)
        self.assertEqual(calls["export_filename"], str(export_file))
        self.assertTrue(calls["export_check"])
        self.assertTrue(calls["factory_tee"])
        self.assertEqual(calls["workdir"], str(root))

    def test_run_export_falls_back_to_run_aster_cli(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            export_file = root / "study.export"
            export_file.write_text("", encoding="utf-8")

            def fake_run(cmd, **kwargs):
                self.assertEqual(cmd, ["run_aster", str(export_file)])
                self.assertEqual(kwargs["cwd"], str(root))
                return types.SimpleNamespace(returncode=0)

            with patch("tuba.solver.code_aster_bridge._run_export_with_python_api", side_effect=ImportError("missing")):
                with patch("tuba.solver.code_aster_bridge.subprocess.run", fake_run):
                    exitcode = code_aster_bridge.run_export(export_file, root)

        self.assertEqual(exitcode, 0)

    def test_main_returns_nonzero_when_export_is_missing(self):
        exitcode = code_aster_bridge.main(["--export", "missing.export"])

        self.assertEqual(exitcode, 2)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_code_aster_bridge -v
```

Expected:

```text
ImportError: cannot import name 'code_aster_bridge'
```

- [ ] **Step 3: Add the bridge module**

Create `tuba/solver/code_aster_bridge.py`:

```python
"""Bridge executed by a Code_Aster Python interpreter."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run_export(export_path: Path, workdir: Path | None = None) -> int:
    export_path = export_path.resolve()
    root = workdir.resolve() if workdir is not None else export_path.parent
    if not export_path.exists():
        print(f"Code_Aster export file not found: {export_path}", file=sys.stderr)
        return 2
    try:
        return _run_export_with_python_api(export_path, root)
    except ImportError:
        return _run_export_with_cli(export_path, root)


def _run_export_with_python_api(export_path: Path, workdir: Path) -> int:
    from run_aster.export import Export
    from run_aster.run import RunAster

    export = Export(filename=str(export_path), check=True)
    runner = RunAster.factory(export, tee=True, output=str(workdir / "stdout.run_aster_api.log"))
    status = runner.execute(str(workdir))
    return int(getattr(status, "exitcode", 0))


def _run_export_with_cli(export_path: Path, workdir: Path) -> int:
    result = subprocess.run(["run_aster", str(export_path)], cwd=str(workdir))
    return int(result.returncode)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tuba.solver.code_aster_bridge")
    parser.add_argument("--export", required=True, help="Path to study.export")
    parser.add_argument("--workdir", default=None, help="Directory containing Code_Aster study files")
    args = parser.parse_args(argv)
    export_path = Path(args.export)
    workdir = Path(args.workdir) if args.workdir else export_path.parent
    return run_export(export_path, workdir)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_code_aster_bridge -v
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit**

```powershell
git add tuba/solver/code_aster_bridge.py tests/test_code_aster_bridge.py
git commit -m "feat: add Code_Aster Python bridge"
```

---

### Task 3: Wire Runtime Into CodeAsterSolver

**Files:**
- Modify: `tuba/solver/aster.py`
- Modify: `tests/test_code_aster_study.py`

**Interfaces:**
- Consumes: `CodeAsterRuntimeConfig` and `run_code_aster_export(...)` from Task 1.
- Produces: `CodeAsterSolver(..., exec_method="auto" | "python_bridge" | "command" | "wsl" | "docker", bridge_python=None, runner_command=None, docker_image=None)` behavior.

- [ ] **Step 1: Update solver-level failing tests**

In `tests/test_code_aster_study.py`, replace the runner-specific tests at the bottom with runtime-level solver tests:

```python
    def test_solver_execute_delegates_to_code_aster_runtime(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "study.export").write_text("", encoding="utf-8")
            captured = {}

            def fake_run_code_aster_export(export_file, work_dir, config):
                captured["export_file"] = export_file
                captured["work_dir"] = work_dir
                captured["config"] = config
                return object()

            with patch("tuba.solver.aster.run_code_aster_export", fake_run_code_aster_export):
                CodeAsterSolver(work_dir=tmpdir, exec_method="python_bridge", bridge_python="/opt/aster/bin/python")._execute(root)

        self.assertEqual(captured["export_file"], root / "study.export")
        self.assertEqual(captured["work_dir"], root)
        self.assertEqual(captured["config"].exec_method, "python_bridge")
        self.assertEqual(captured["config"].bridge_python, "/opt/aster/bin/python")

    def test_solver_preserves_runner_command_compatibility(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "study.export").write_text("", encoding="utf-8")
            captured = {}

            def fake_run_code_aster_export(export_file, work_dir, config):
                captured["config"] = config
                return object()

            with patch("tuba.solver.aster.run_code_aster_export", fake_run_code_aster_export):
                CodeAsterSolver(work_dir=tmpdir, exec_method="command", runner_command="conda run -n aster run_aster")._execute(root)

        self.assertEqual(captured["config"].exec_method, "command")
        self.assertEqual(captured["config"].runner_command, "conda run -n aster run_aster")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_code_aster_study -v
```

Expected:

```text
TypeError: CodeAsterSolver.__init__() got an unexpected keyword argument 'bridge_python'
```

- [ ] **Step 3: Modify `CodeAsterSolver` constructor and execution**

In `tuba/solver/aster.py`, add imports:

```python
from tuba.solver.code_aster_runtime import CodeAsterRuntimeConfig, run_code_aster_export
```

Change `CodeAsterSolver.__init__` to:

```python
    def __init__(
        self,
        work_dir: Optional[str] = None,
        exec_method: str = "auto",
        docker_image: Optional[str] = None,
        runner_command: Optional[str] = None,
        bridge_python: Optional[str] = None,
        timeout_seconds: int = 7200,
    ) -> None:
        self.work_dir = Path(work_dir) if work_dir else None
        self.exec_method = exec_method
        self.docker_image = docker_image or os.environ.get("TUBA_CODE_ASTER_DOCKER_IMAGE") or "simvia/code_aster:stable"
        self.runner_command = runner_command or os.environ.get("TUBA_CODE_ASTER_RUNNER")
        self.bridge_python = bridge_python or os.environ.get("TUBA_CODE_ASTER_PYTHON")
        self.timeout_seconds = timeout_seconds
```

Replace `_execute(...)` with:

```python
    def _execute(self, work_dir: Path) -> None:
        """Invoke Code_Aster on the generated study files."""
        export_file = work_dir / "study.export"
        config = CodeAsterRuntimeConfig(
            exec_method=self.exec_method,
            docker_image=self.docker_image,
            runner_command=self.runner_command,
            bridge_python=self.bridge_python,
            timeout_seconds=self.timeout_seconds,
        )
        run_code_aster_export(export_file, work_dir, config)
```

Remove `_execute_command(...)` and `_code_aster_runner_script(...)` only after all tests pass. Keep `_win_to_wsl(...)` only if another function still imports it; otherwise remove it in the same commit.

- [ ] **Step 4: Run solver tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_code_aster_study tests.test_code_aster_runtime -v
```

Expected:

```text
OK
```

- [ ] **Step 5: Run artifact/notebook regression tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_code_aster_results tests.test_code_aster_artifact_import tests.test_code_aster_notebook_loader tests.test_notebook_code_aster_results -v
```

Expected:

```text
OK
```

- [ ] **Step 6: Commit**

```powershell
git add tuba/solver/aster.py tests/test_code_aster_study.py
git commit -m "feat: execute Code_Aster through runtime layer"
```

---

### Task 4: Doctor Command For Runtime Diagnostics

**Files:**
- Create: `tuba/solver/code_aster_doctor.py`
- Create: `tests/test_code_aster_doctor.py`

**Interfaces:**
- Consumes: `discover_code_aster_runtimes(...)`.
- Produces: `python -m tuba.solver.code_aster_doctor --json` and human-readable `python -m tuba.solver.code_aster_doctor`.

- [ ] **Step 1: Write failing doctor tests**

Create `tests/test_code_aster_doctor.py`:

```python
import json
import unittest
from unittest.mock import patch

from tuba.solver.code_aster_doctor import main
from tuba.solver.code_aster_runtime import CodeAsterRuntimeCandidate


class TestCodeAsterDoctor(unittest.TestCase):
    def test_json_output_lists_candidates(self):
        candidates = [CodeAsterRuntimeCandidate("python_bridge", ("/opt/aster/bin/python",), True)]

        with patch("tuba.solver.code_aster_doctor.discover_code_aster_runtimes", return_value=candidates):
            payload = main(["--json"], return_output=True)

        data = json.loads(payload)
        self.assertEqual(data["candidates"][0]["kind"], "python_bridge")
        self.assertEqual(data["candidates"][0]["command"], ["/opt/aster/bin/python"])
        self.assertTrue(data["candidates"][0]["available"])

    def test_text_output_includes_setup_guidance_when_empty(self):
        candidates = [CodeAsterRuntimeCandidate("auto", (), False, "No runtime")]

        with patch("tuba.solver.code_aster_doctor.discover_code_aster_runtimes", return_value=candidates):
            output = main([], return_output=True)

        self.assertIn("No runtime", output)
        self.assertIn("TUBA_CODE_ASTER_PYTHON", output)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_code_aster_doctor -v
```

Expected:

```text
ModuleNotFoundError: No module named 'tuba.solver.code_aster_doctor'
```

- [ ] **Step 3: Add doctor module**

Create `tuba/solver/code_aster_doctor.py`:

```python
"""Diagnose Code_Aster runtime configuration."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from tuba.solver.code_aster_runtime import CodeAsterRuntimeConfig, discover_code_aster_runtimes


def main(argv: list[str] | None = None, *, return_output: bool = False) -> str | int:
    parser = argparse.ArgumentParser(prog="python -m tuba.solver.code_aster_doctor")
    parser.add_argument("--exec-method", default="auto", choices=["auto", "python_bridge", "command", "wsl", "docker"])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    candidates = discover_code_aster_runtimes(CodeAsterRuntimeConfig(exec_method=args.exec_method))
    if args.json:
        output = json.dumps({"candidates": [_candidate_payload(item) for item in candidates]}, indent=2, sort_keys=True)
    else:
        lines = ["Code_Aster runtime candidates:"]
        for item in candidates:
            status = "available" if item.available else "unavailable"
            command = " ".join(item.command) if item.command else "<not configured>"
            lines.append(f"- {item.kind}: {status}; command={command}")
            if item.reason:
                lines.append(f"  reason: {item.reason}")
        lines.append("")
        lines.append("Primary setup path: set TUBA_CODE_ASTER_PYTHON to the Python executable inside a Code_Aster environment that can import run_aster.")
        lines.append("Fallback setup path: set TUBA_CODE_ASTER_RUNNER to a command such as 'run_aster' or 'conda run -n aster run_aster'.")
        output = "\n".join(lines)

    if return_output:
        return output
    print(output)
    return 0


def _candidate_payload(candidate):
    payload = asdict(candidate)
    payload["command"] = list(candidate.command)
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run doctor tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_code_aster_doctor -v
```

Expected:

```text
OK
```

- [ ] **Step 5: Run the doctor manually**

Run:

```powershell
.\.venv\Scripts\python.exe -m tuba.solver.code_aster_doctor
```

Expected on a machine without configured Code_Aster:

```text
Code_Aster runtime candidates:
...
Primary setup path: set TUBA_CODE_ASTER_PYTHON ...
```

- [ ] **Step 6: Commit**

```powershell
git add tuba/solver/code_aster_doctor.py tests/test_code_aster_doctor.py
git commit -m "feat: add Code_Aster runtime doctor"
```

---

### Task 5: Notebook Runtime Defaults

**Files:**
- Modify: `tuba/analysis/code_aster_notebook.py`
- Modify: `tests/test_code_aster_notebook_loader.py`

**Interfaces:**
- Consumes: `CodeAsterSolver(..., exec_method="auto")`.
- Produces: notebook helper default that discovers the configured runtime before result display.

- [ ] **Step 1: Add a failing default-runtime assertion**

In `tests/test_code_aster_notebook_loader.py`, add:

```python
    def test_notebook_loader_defaults_to_auto_runtime(self):
        model, _n0, _n1 = self._model()

        class CapturingSolver:
            instances = []

            def __init__(self, work_dir=None, exec_method="wsl", docker_image=None):
                self.work_dir = Path(work_dir)
                self.exec_method = exec_method
                self.docker_image = docker_image
                self.instances.append(self)

            def export_analysis_study(self, model, load_case_name, output_dir):
                return CodeAsterSolver(work_dir=output_dir).export_analysis_study(model, load_case_name, output_dir)

            def solve_exported_study(self, model, study):
                raise RuntimeError("test stops before solver execution")

        with TemporaryDirectory() as tmpdir:
            with self.assertRaises(RuntimeError):
                load_or_run_code_aster_results(model, "Hot", tmpdir, solver_factory=CapturingSolver)

        self.assertEqual(CapturingSolver.instances[0].exec_method, "auto")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_code_aster_notebook_loader.TestCodeAsterNotebookLoader.test_notebook_loader_defaults_to_auto_runtime -v
```

Expected:

```text
AssertionError: 'wsl' != 'auto'
```

- [ ] **Step 3: Change the notebook helper default**

In `tuba/analysis/code_aster_notebook.py`, change:

```python
    exec_method: str = "wsl",
```

to:

```python
    exec_method: str = "auto",
```

- [ ] **Step 4: Run notebook loader tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_code_aster_notebook_loader tests.test_notebook_code_aster_results -v
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit**

```powershell
git add tuba/analysis/code_aster_notebook.py tests/test_code_aster_notebook_loader.py
git commit -m "feat: default notebooks to auto Code_Aster runtime"
```

---

### Task 6: Real Code Aster Smoke Test

**Files:**
- Create: `tests/integration/__init__.py`
- Create: `tests/integration/test_code_aster_real_smoke.py`

**Interfaces:**
- Consumes: `CodeAsterSolver.solve(...)`.
- Produces: gated real runtime proof that Code_Aster can solve a minimal Tuba pipe model and produce parsed results.

- [ ] **Step 1: Add gated integration test**

Create `tests/integration/__init__.py`:

```python
"""Integration tests that may require external solver runtimes."""
```

Create `tests/integration/test_code_aster_real_smoke.py`:

```python
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tuba import Model


@unittest.skipUnless(os.environ.get("TUBA_RUN_CODE_ASTER_INTEGRATION") == "1", "set TUBA_RUN_CODE_ASTER_INTEGRATION=1 to run real Code_Aster smoke test")
class TestCodeAsterRealSmoke(unittest.TestCase):
    def test_minimal_pipe_model_solves_with_real_code_aster(self):
        model = Model(project_name="CodeAsterRealSmoke")
        model.add_material("Steel", E=2.0e11, nu=0.3, rho=7850.0, alpha=1.2e-5, allowable_stress={20.0: 137e6})
        model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
        n0 = model.add_node([0.0, 0.0, 0.0])
        n1 = model.add_node([1.0, 0.0, 0.0])
        model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")
        model.add_support(node=n0, type="anchor", id="support_anchor_0")
        model.define_load_case("Operating", gravity=True, pressure=1.0e6, temperature=120.0, ref_temperature=20.0)

        with TemporaryDirectory() as tmpdir:
            results = model.solve("code_aster", load_case="Operating", work_dir=tmpdir, exec_method=os.environ.get("TUBA_CODE_ASTER_EXEC_METHOD", "auto"))
            root = Path(tmpdir)

            self.assertTrue((root / "study.export").exists())
            self.assertTrue((root / "study_depl.csv").exists())
            self.assertTrue((root / "study_effo.csv").exists())
            self.assertTrue((root / "study_reac.csv").exists())
            self.assertTrue((root / "study_sieq.csv").exists())

        self.assertEqual(results.solver_name, "Code_Aster")
        self.assertEqual(results.load_case, "Operating")
        self.assertGreaterEqual(len(results.node_results), 2)
        self.assertGreaterEqual(len(results.element_results), 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Verify skip behavior without real Code_Aster**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.integration.test_code_aster_real_smoke -v
```

Expected:

```text
skipped 'set TUBA_RUN_CODE_ASTER_INTEGRATION=1 to run real Code_Aster smoke test'
```

- [ ] **Step 3: Run against real Code_Aster**

Configure one runtime:

```powershell
$env:TUBA_CODE_ASTER_PYTHON = "\\wsl.localhost\\Ubuntu\\home\\jan\\miniforge3\\envs\\aster\\bin\\python"
```

or:

```powershell
$env:TUBA_CODE_ASTER_RUNNER = "wsl conda run -n aster run_aster"
```

Then run:

```powershell
$env:TUBA_RUN_CODE_ASTER_INTEGRATION = "1"
.\.venv\Scripts\python.exe -m unittest tests.integration.test_code_aster_real_smoke -v
```

Expected:

```text
OK
```

- [ ] **Step 4: Commit**

```powershell
git add tests/integration/__init__.py tests/integration/test_code_aster_real_smoke.py
git commit -m "test: add real Code_Aster smoke gate"
```

---

### Task 7: Documentation And Setup Contract

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `installation_and_interface_strategy.md`
- Create: `tests/test_code_aster_docs.py`

**Interfaces:**
- Consumes: runtime names from Tasks 1-6.
- Produces: clear setup instructions and repo rules that prevent future mock/export-only regressions.

- [ ] **Step 1: Write docs regression test**

Create `tests/test_code_aster_docs.py`:

```python
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class TestCodeAsterDocs(unittest.TestCase):
    def test_readme_documents_required_runtime_and_doctor(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("Code_Aster execution is required", text)
        self.assertIn("python -m tuba.solver.code_aster_doctor", text)
        self.assertIn("TUBA_CODE_ASTER_PYTHON", text)
        self.assertIn("TUBA_RUN_CODE_ASTER_INTEGRATION", text)

    def test_agents_keeps_ada_py_license_boundary(self):
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

        self.assertIn("Do not vendor or copy ada-py", text)
        self.assertIn("GPL-3.0-or-later", text)
        self.assertIn("Code_Aster execution is not optional", text)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_code_aster_docs -v
```

Expected:

```text
FAIL
```

- [ ] **Step 3: Update `README.md`**

Add this section near the existing core workflow section:

```markdown
## Code_Aster Runtime

Code_Aster execution is required for production stress, displacement, reaction, compliance, operating-state clash, and result visualization workflows. Exporting `.comm`, `.mail`, and `.export` files is only the solver handoff; the engineering evaluation is incomplete until Code_Aster has executed and Tuba has imported the generated artifacts.

Run the runtime doctor:

```powershell
.\.venv\Scripts\python.exe -m tuba.solver.code_aster_doctor
```

Preferred setup:

```powershell
$env:TUBA_CODE_ASTER_PYTHON = "<python executable inside a Code_Aster environment that can import run_aster>"
```

Fallback setup:

```powershell
$env:TUBA_CODE_ASTER_RUNNER = "run_aster"
```

Real solver smoke:

```powershell
$env:TUBA_RUN_CODE_ASTER_INTEGRATION = "1"
.\.venv\Scripts\python.exe -m unittest tests.integration.test_code_aster_real_smoke -v
```
```

- [ ] **Step 4: Update `AGENTS.md`**

Add this bullet under the Code_Aster rules:

```markdown
- Do not vendor or copy ada-py code. ada-py is GPL-3.0-or-later, while Tuba core remains LGPL. Tuba may independently implement the same write/execute/postprocess architecture, but the solver integration must remain native Tuba code with external-process Code_Aster execution.
```

- [ ] **Step 5: Update `installation_and_interface_strategy.md`**

Replace any text that implies Code_Aster is optional for the core product with:

```markdown
For Tuba v4 production workflows, Code_Aster is a required external solver runtime. The recommended developer setup is a Code_Aster-capable Python environment that can import `run_aster`, exposed to Tuba through `TUBA_CODE_ASTER_PYTHON`. WSL/conda, a direct `run_aster` command, and Docker are supported fallback execution methods.
```

- [ ] **Step 6: Run docs test**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_code_aster_docs -v
```

Expected:

```text
OK
```

- [ ] **Step 7: Commit**

```powershell
git add README.md AGENTS.md installation_and_interface_strategy.md tests/test_code_aster_docs.py
git commit -m "docs: document required Code_Aster runtime"
```

---

### Task 8: Final Verification Gate

**Files:**
- Verify only. No source edits unless a previous task failed.

**Interfaces:**
- Consumes: all tasks.
- Produces: a working unit gate, a documented real-solver gate, and clear failure diagnostics when Code_Aster is unavailable.

- [ ] **Step 1: Run targeted Code_Aster unit suite**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_code_aster_runtime tests.test_code_aster_bridge tests.test_code_aster_study tests.test_code_aster_sidecar tests.test_code_aster_results tests.test_code_aster_artifact_import tests.test_code_aster_notebook_loader tests.test_notebook_code_aster_results tests.test_code_aster_doctor tests.test_code_aster_docs -v
```

Expected:

```text
OK
```

- [ ] **Step 2: Run real-solver smoke when runtime is configured**

Run:

```powershell
$env:TUBA_RUN_CODE_ASTER_INTEGRATION = "1"
.\.venv\Scripts\python.exe -m unittest tests.integration.test_code_aster_real_smoke -v
```

Expected:

```text
OK
```

If this fails because the runtime is missing, stop and fix setup. Do not mark Code_Aster integration complete from unit tests alone.

- [ ] **Step 3: Run notebook loader smoke**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_code_aster_notebook_loader -v
```

Expected:

```text
OK
```

- [ ] **Step 4: Run broad test discovery**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit verification-only changes if any were needed**

```powershell
git status --short
```

If no files changed, do not create a commit. If a verification fix was necessary:

```powershell
git add <changed-files>
git commit -m "fix: stabilize Code_Aster runtime integration"
```

---

## Self-Review

Spec coverage:

- Runtime discovery is covered by Task 1.
- Python-managed Code_Aster execution is covered by Task 2.
- Existing `CodeAsterSolver` integration is covered by Task 3.
- Notebook result provenance is covered by Task 5.
- Real Code_Aster verification is covered by Task 6 and Task 8.
- Documentation and agent rules are covered by Task 7.
- ada-py GPL/LGPL boundary is covered in Global Constraints and Task 7.

Placeholder scan:

- The plan uses concrete file paths, explicit interfaces, exact commands, and expected test outcomes throughout.

Type consistency:

- `CodeAsterRuntimeConfig`, `CodeAsterRuntimeCandidate`, and `CodeAsterExecution` are introduced in Task 1 and consumed by Tasks 3 and 4 with the same names.
- `run_export(...)` is introduced in Task 2 and used only by the bridge CLI.
- `exec_method` values are consistently `auto`, `python_bridge`, `command`, `wsl`, and `docker`.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-30-code-aster-runtime-integration.md`. Two execution options:

1. **Subagent-Driven (recommended)** - Dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints.
