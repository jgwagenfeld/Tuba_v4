# Code_Aster Notebook Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Tuba's notebook and example workflows reliably show real Code_Aster-backed results in VS Code/Jupyter, while failing fast when the solver runtime is not actually usable.

**Architecture:** Deepen the existing runtime module instead of adding a new solver path. `tuba.solver.code_aster_runtime` remains the single runtime readiness seam; notebooks and doctor diagnostics consume that interface. Keep the two visualization surfaces distinct: PyVista quick-look under `tuba/visualizer/` and reviewable Three.js scene bundles under `tuba/visualization/` plus `viewer/`.

**Tech Stack:** Python 3.10+, `unittest`/`pytest`, `subprocess`, `nbclient` when available, existing PyVista notebook backend, existing Code_Aster artifact importer, Node's built-in `node --test` for the viewer.

## Global Constraints

- Production stress, displacement, reaction, compliance, operating-state clash, and result visualization workflows must use real Code_Aster artifacts.
- Do not present fabricated, hand-built, mock, or proxy values as solver results.
- Export-only paths are development and diagnostic surfaces only.
- If Code_Aster is unavailable, fail loudly before displaying or reporting solver results.
- Unit tests may use deterministic fixtures; user-facing notebooks and examples must not label fixture values as Code_Aster results.
- Do not add a third visualization path.
- Windows plus VS Code is a primary user environment; notebook plots must emit visible static MIME output there.
- Do not vendor or copy ada-py code.
- Do not expand B31J tee/branch or sustained-stress formulas in this plan.

---

## File Structure

- Modify `tuba/solver/code_aster_runtime.py`
  - Add bounded runtime preflight checks.
  - Keep execution command construction unchanged except for sharing the same candidate model.

- Modify `tuba/solver/code_aster_doctor.py`
  - Add `--check` to report actual runtime readiness, not just discovered candidates.

- Modify `tuba/analysis/code_aster_notebook.py`
  - Check runtime readiness before deleting existing result artifacts when `run_solver=True`.

- Modify `tests/test_code_aster_runtime.py`
  - Unit-test preflight success, failure, and timeout behavior.

- Modify `tests/test_code_aster_doctor.py`
  - Unit-test text and JSON readiness output.

- Modify `tests/test_code_aster_notebook_loader.py`
  - Unit-test that failed preflight preserves existing result artifacts.

- Create `tests/test_notebook_vscode_render.py`
  - Execute a tiny plotting notebook under simulated VS Code environment and assert `image/png` output exists.

- Modify `tests/test_notebook_code_aster_results.py`
  - Assert artifact-backed notebooks default to loading committed artifacts instead of re-running Code_Aster.

- Modify selected notebooks:
  - `notebooks/00_welcome_and_setup.ipynb`
  - `notebooks/03_stress_analysis_and_compliance.ipynb`
  - `notebooks/04_visualization_gallery.ipynb`
  - `notebooks/06_structural_frames_and_optimization.ipynb`
  - `notebooks/07_bim_data_exchange.ipynb`
  - `notebooks/advanced_piping_design_and_bim.ipynb`

- Modify user-facing examples:
  - `examples/demo.py`
  - `examples/operating_state_clash.py`
  - `examples/realtime_visualization_review.py`

- Modify example tests:
  - `tests/test_examples.py`
  - `tests/test_operating_state_example.py`
  - `tests/test_realtime_visualization_bundle.py`

---

### Task 1: Runtime Readiness Preflight

**Files:**
- Modify: `tuba/solver/code_aster_runtime.py`
- Modify: `tests/test_code_aster_runtime.py`

**Interfaces:**
- Produces: `CodeAsterRuntimeCheck`, `build_code_aster_preflight_command(candidate, config)`, `preflight_code_aster_runtimes(config)`.
- Consumes: `CodeAsterRuntimeConfig`, `CodeAsterRuntimeCandidate`, `discover_code_aster_runtimes(config)`.

- [ ] **Step 1: Add failing runtime preflight tests**

Append these tests to `tests/test_code_aster_runtime.py`:

```python
    def test_preflight_reports_ok_runtime(self):
        from tuba.solver.code_aster_runtime import preflight_code_aster_runtimes

        calls = []

        def fake_run(cmd, **kwargs):
            calls.append((cmd, kwargs))
            return subprocess.CompletedProcess(cmd, 0, stdout="run_aster ok", stderr="")

        with patch("tuba.solver.code_aster_runtime.subprocess.run", fake_run):
            checks = preflight_code_aster_runtimes(
                CodeAsterRuntimeConfig(
                    exec_method="command",
                    runner_command="run_aster",
                    env={},
                    preflight_timeout_seconds=3,
                )
            )

        self.assertEqual(len(checks), 1)
        self.assertTrue(checks[0].ok)
        self.assertEqual(checks[0].runtime.kind, "command")
        self.assertEqual(checks[0].stdout, "run_aster ok")
        self.assertEqual(calls[0][1]["timeout"], 3)

    def test_preflight_reports_missing_wsl_runner(self):
        from tuba.solver.code_aster_runtime import preflight_code_aster_runtimes

        def fake_run(cmd, **_kwargs):
            return subprocess.CompletedProcess(cmd, 127, stdout="", stderr="Code_Aster runner not found")

        with patch("tuba.solver.code_aster_runtime.subprocess.run", fake_run):
            checks = preflight_code_aster_runtimes(
                CodeAsterRuntimeConfig(exec_method="wsl", wsl_distro="Ubuntu", env={})
            )

        self.assertEqual(len(checks), 1)
        self.assertFalse(checks[0].ok)
        self.assertEqual(checks[0].returncode, 127)
        self.assertIn("Code_Aster runner not found", checks[0].reason)

    def test_preflight_timeout_is_reported_without_hanging(self):
        from tuba.solver.code_aster_runtime import preflight_code_aster_runtimes

        def fake_run(cmd, **kwargs):
            raise subprocess.TimeoutExpired(cmd, kwargs["timeout"], output="pulling", stderr="still pulling")

        with patch("tuba.solver.code_aster_runtime.subprocess.run", fake_run):
            checks = preflight_code_aster_runtimes(
                CodeAsterRuntimeConfig(
                    exec_method="docker",
                    docker_image="simvia/code_aster:stable",
                    env={},
                    preflight_timeout_seconds=1,
                )
            )

        self.assertEqual(len(checks), 1)
        self.assertFalse(checks[0].ok)
        self.assertIsNone(checks[0].returncode)
        self.assertIn("timed out after 1 seconds", checks[0].reason)
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_code_aster_runtime.py -q
```

Expected: failure because `preflight_timeout_seconds` and `preflight_code_aster_runtimes` do not exist.

- [ ] **Step 3: Add the preflight interface**

In `tuba/solver/code_aster_runtime.py`, update `CodeAsterRuntimeConfig`:

```python
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
```

Add this dataclass below `CodeAsterExecution`:

```python
@dataclass(frozen=True)
class CodeAsterRuntimeCheck:
    runtime: CodeAsterRuntimeCandidate
    command: tuple[str, ...]
    returncode: int | None
    stdout: str
    stderr: str
    ok: bool
    reason: str | None = None
```

Add these functions before `run_code_aster_export(...)`:

```python
def build_code_aster_preflight_command(
    candidate: CodeAsterRuntimeCandidate,
    config: CodeAsterRuntimeConfig,
) -> tuple[list[str], Path | None]:
    if candidate.kind == "python_bridge":
        return [
            *candidate.command,
            "-c",
            "import run_aster.export, run_aster.run; print('run_aster python bridge ok')",
        ], None
    if candidate.kind == "command":
        return [*candidate.command, "--help"], None
    if candidate.kind == "wsl":
        return [*candidate.command, "bash", "-lc", _runner_probe_script()], None
    if candidate.kind == "docker":
        image = candidate.command[-1] if candidate.command else config.docker_image
        return ["docker", "run", "--rm", image, "sh", "-lc", _runner_probe_script()], None
    return [], None


def preflight_code_aster_runtimes(config: CodeAsterRuntimeConfig) -> list[CodeAsterRuntimeCheck]:
    checks: list[CodeAsterRuntimeCheck] = []
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
        command, cwd = build_code_aster_preflight_command(candidate, config)
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
```

Add this helper near `_runner_detection_script(...)`:

```python
def _runner_probe_script() -> str:
    return (
        "if command -v run_aster >/dev/null 2>&1; then run_aster --help >/dev/null 2>&1 || true; echo run_aster; "
        "elif command -v as_run >/dev/null 2>&1; then as_run --help >/dev/null 2>&1 || true; echo as_run; "
        "elif command -v aster >/dev/null 2>&1; then aster --help >/dev/null 2>&1 || true; echo aster; "
        'else echo "Code_Aster runner not found" >&2; exit 127; fi'
    )
```

- [ ] **Step 4: Run runtime tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_code_aster_runtime.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add tuba/solver/code_aster_runtime.py tests/test_code_aster_runtime.py
git commit -m "feat: add Code_Aster runtime preflight"
```

---

### Task 2: Doctor And Notebook Runtime Guard

**Files:**
- Modify: `tuba/solver/code_aster_doctor.py`
- Modify: `tuba/analysis/code_aster_notebook.py`
- Modify: `tests/test_code_aster_doctor.py`
- Modify: `tests/test_code_aster_notebook_loader.py`

**Interfaces:**
- Consumes: `preflight_code_aster_runtimes(config) -> list[CodeAsterRuntimeCheck]`.
- Produces: doctor `--check`; notebook guard `require_code_aster_runtime(...) -> CodeAsterRuntimeCheck`.

- [ ] **Step 1: Add failing doctor checks**

Append this test to `tests/test_code_aster_doctor.py`:

```python
    def test_check_json_output_lists_runtime_readiness(self):
        from tuba.solver.code_aster_runtime import CodeAsterRuntimeCheck

        checks = [
            CodeAsterRuntimeCheck(
                runtime=CodeAsterRuntimeCandidate("wsl", ("wsl", "-d", "Ubuntu", "--"), True),
                command=("wsl", "-d", "Ubuntu", "--", "bash", "-lc", "probe"),
                returncode=127,
                stdout="",
                stderr="Code_Aster runner not found",
                ok=False,
                reason="Code_Aster runner not found",
            )
        ]

        with patch("tuba.solver.code_aster_doctor.preflight_code_aster_runtimes", return_value=checks):
            payload = main(["--json", "--check"], return_output=True)

        data = json.loads(payload)
        self.assertFalse(data["checks"][0]["ok"])
        self.assertEqual(data["checks"][0]["kind"], "wsl")
        self.assertIn("Code_Aster runner not found", data["checks"][0]["reason"])
```

- [ ] **Step 2: Add failing notebook artifact-preservation check**

Append this test to `tests/test_code_aster_notebook_loader.py`:

```python
    def test_run_solver_true_preflight_failure_preserves_existing_tables(self):
        from tuba.solver.code_aster_runtime import CodeAsterRuntimeCandidate, CodeAsterRuntimeCheck

        model, n0, n1 = self._model()

        class SolverThatMustNotRun:
            def __init__(self, work_dir=None, exec_method="auto", docker_image=None, wsl_distro=None):
                self.work_dir = Path(work_dir)
                self.exec_method = exec_method
                self.docker_image = docker_image
                self.wsl_distro = wsl_distro

            def export_analysis_study(self, model, load_case_name, output_dir):
                return CodeAsterSolver(work_dir=output_dir).export_analysis_study(model, load_case_name, output_dir)

            def solve_exported_study(self, model, study):
                raise AssertionError("solver must not run when preflight fails")

        blocked = [
            CodeAsterRuntimeCheck(
                runtime=CodeAsterRuntimeCandidate("wsl", ("wsl",), True),
                command=("wsl", "bash", "-lc", "probe"),
                returncode=127,
                stdout="",
                stderr="Code_Aster runner not found",
                ok=False,
                reason="Code_Aster runner not found",
            )
        ]

        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_solver_tables(root, n0=n0, n1=n1, n1_dy=0.005)
            with patch("tuba.analysis.code_aster_notebook.preflight_code_aster_runtimes", return_value=blocked):
                with self.assertRaisesRegex(RuntimeError, "Code_Aster runtime is not ready"):
                    load_or_run_code_aster_results(
                        model,
                        "Hot",
                        root,
                        run_solver=True,
                        solver_factory=SolverThatMustNotRun,
                    )

            self.assertIn(",0.005,", (root / "study_depl.csv").read_text(encoding="utf-8"))
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_code_aster_doctor.py tests/test_code_aster_notebook_loader.py -q
```

Expected: failures because `--check` and `preflight_code_aster_runtimes` notebook wiring are not present.

- [ ] **Step 4: Wire doctor `--check`**

In `tuba/solver/code_aster_doctor.py`, import the preflight function:

```python
from tuba.solver.code_aster_runtime import (
    CodeAsterRuntimeConfig,
    discover_code_aster_runtimes,
    preflight_code_aster_runtimes,
)
```

Add the argument in `main(...)`:

```python
parser.add_argument("--check", action="store_true", help="Run bounded readiness probes for discovered runtimes.")
```

After building `candidates`, add:

```python
checks = preflight_code_aster_runtimes(config) if args.check else []
```

Use a local `config` variable:

```python
config = CodeAsterRuntimeConfig(exec_method=args.exec_method)
candidates = discover_code_aster_runtimes(config)
```

For JSON output, replace the payload with:

```python
output = json.dumps(
    {
        "candidates": [_candidate_payload(item) for item in candidates],
        "checks": [_check_payload(item) for item in checks],
    },
    indent=2,
    sort_keys=True,
)
```

For text output, append after the candidate loop:

```python
if args.check:
    lines.append("")
    lines.append("Code_Aster runtime readiness:")
    for item in checks:
        status = "ready" if item.ok else "blocked"
        command = " ".join(item.command) if item.command else "<not configured>"
        lines.append(f"- {item.runtime.kind}: {status}; command={command}")
        if item.reason:
            lines.append(f"  reason: {item.reason}")
```

Add this helper near `_candidate_payload(...)`:

```python
def _check_payload(check):
    return {
        "kind": check.runtime.kind,
        "command": list(check.command),
        "returncode": check.returncode,
        "stdout": check.stdout,
        "stderr": check.stderr,
        "ok": check.ok,
        "reason": check.reason,
    }
```

- [ ] **Step 5: Wire notebook runtime guard**

In `tuba/analysis/code_aster_notebook.py`, import:

```python
from tuba.solver.code_aster_runtime import CodeAsterRuntimeCheck, CodeAsterRuntimeConfig, preflight_code_aster_runtimes
```

Add this function before `_make_solver(...)`:

```python
def require_code_aster_runtime(
    *,
    exec_method: str,
    wsl_distro: str | None,
    docker_image: str | None,
) -> CodeAsterRuntimeCheck:
    config = CodeAsterRuntimeConfig(
        exec_method=exec_method,
        wsl_distro=wsl_distro,
        docker_image=docker_image or CodeAsterRuntimeConfig().docker_image,
    )
    checks = preflight_code_aster_runtimes(config)
    for check in checks:
        if check.ok:
            return check
    details = "; ".join(
        f"{check.runtime.kind}: {check.reason or check.stderr or check.stdout or 'not ready'}"
        for check in checks
    )
    raise RuntimeError(
        "Code_Aster runtime is not ready. Existing result tables were left in place. "
        "Set RUN_CODE_ASTER = False to load existing artifacts, or configure Code_Aster and rerun. "
        f"Checks: {details}"
    )
```

In `load_or_run_code_aster_results(...)`, change this block:

```python
if run_solver:
    _remove_result_artifacts(root)
    solver.solve_exported_study(model, study)
    ran_solver = True
```

to:

```python
if run_solver:
    require_code_aster_runtime(
        exec_method=exec_method,
        wsl_distro=wsl_distro,
        docker_image=docker_image,
    )
    _remove_result_artifacts(root)
    solver.solve_exported_study(model, study)
    ran_solver = True
```

- [ ] **Step 6: Run doctor and notebook tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_code_aster_doctor.py tests/test_code_aster_notebook_loader.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```powershell
git add tuba/solver/code_aster_doctor.py tuba/analysis/code_aster_notebook.py tests/test_code_aster_doctor.py tests/test_code_aster_notebook_loader.py
git commit -m "feat: guard notebook solves with Code_Aster preflight"
```

---

### Task 3: VS Code Notebook Render Regression

**Files:**
- Create: `tests/test_notebook_vscode_render.py`

**Interfaces:**
- Consumes: `configure_notebook_backend()`, `plots.plot_deformed_stress(...)`.
- Produces: a regression test proving VS Code emits static image MIME output.

- [ ] **Step 1: Add the render regression test**

Create `tests/test_notebook_vscode_render.py`:

```python
import importlib.util
import json
import os
import unittest
from unittest.mock import patch


@unittest.skipUnless(importlib.util.find_spec("nbclient"), "nbclient is required for notebook render checks")
@unittest.skipUnless(importlib.util.find_spec("nbformat"), "nbformat is required for notebook render checks")
@unittest.skipUnless(importlib.util.find_spec("pyvista"), "pyvista is required for notebook render checks")
class TestVSCodeNotebookRender(unittest.TestCase):
    def test_vscode_static_backend_emits_image_mime_for_result_plot(self):
        import nbformat
        from nbclient import NotebookClient

        code = r'''
import numpy as np
from tuba import Model
from tuba.solver.base import ElementResult, FEAResults, NodeResult
from tuba.visualizer.notebook import configure_notebook_backend
from tuba.visualizer import plots

JUPYTER_BACKEND = configure_notebook_backend()
model = Model(project_name="VSCodeRenderSmoke")
model.add_material("Steel", E=2.0e11, nu=0.3)
model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
n0 = model.add_node([0.0, 0.0, 0.0])
n1 = model.add_node([1.0, 0.0, 0.0])
model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")
model.add_support(node=n0, type="anchor", id="support_anchor_0")

results = FEAResults(solver_name="fixture", load_case="Hot")
results._model = model
results.node_results[n0] = NodeResult(node_id=n0, displacement=np.zeros(6), reaction_force=np.zeros(6))
results.node_results[n1] = NodeResult(node_id=n1, displacement=np.array([0.0, 0.01, 0.0, 0.0, 0.0, 0.0]))
results.element_results["pipe_0"] = ElementResult(
    element_id="pipe_0",
    forces_n1=np.zeros(6),
    forces_n2=np.zeros(6),
    von_mises_n1=1.0,
    von_mises_n2=2.0,
    max_von_mises=2.0,
)

plots.plot_deformed_stress(results, deform_scale=20.0, model=model)
'''
        nb = nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell(code)])

        env = {"TERM_PROGRAM": "vscode", "VSCODE_PID": "12345"}
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("TUBA_NOTEBOOK_BACKEND", None)
            client = NotebookClient(nb, timeout=120, kernel_name="python3", allow_errors=False)
            client.execute()

        mime_types = set()
        for output in nb.cells[0].get("outputs", []):
            mime_types.update((output.get("data") or {}).keys())

        self.assertIn("image/png", mime_types)
        self.assertIn("image/jpeg", mime_types)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the render regression**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_notebook_vscode_render.py -q
```

Expected: pass or skip only when notebook/PyVista packages are not installed.

- [ ] **Step 3: Commit**

```powershell
git add tests/test_notebook_vscode_render.py
git commit -m "test: verify VS Code notebook plot output"
```

---

### Task 4: Notebook Default Mode Cleanup

**Files:**
- Modify: `tests/test_notebook_code_aster_results.py`
- Modify: `notebooks/00_welcome_and_setup.ipynb`
- Modify: `notebooks/03_stress_analysis_and_compliance.ipynb`
- Modify: `notebooks/04_visualization_gallery.ipynb`
- Modify: `notebooks/06_structural_frames_and_optimization.ipynb`
- Modify: `notebooks/07_bim_data_exchange.ipynb`
- Modify: `notebooks/advanced_piping_design_and_bim.ipynb`

**Interfaces:**
- Consumes: committed result artifacts under `notebooks/code_aster_results/<case>/`.
- Produces: notebooks that default to displaying committed real artifacts in VS Code, while still allowing explicit real solver execution.

- [ ] **Step 1: Add failing notebook default test**

Append this test to `tests/test_notebook_code_aster_results.py`:

```python
    def test_artifact_backed_notebooks_default_to_load_existing_results(self):
        notebooks_dir = Path(__file__).resolve().parents[1] / "notebooks"
        artifact_backed = {
            "00_welcome_and_setup.ipynb": "stress_analysis_operating",
            "03_stress_analysis_and_compliance.ipynb": "stress_analysis_operating",
            "04_visualization_gallery.ipynb": "viz_gallery_operating",
            "06_structural_frames_and_optimization.ipynb": "structural_operating_hot",
            "07_bim_data_exchange.ipynb": "bim_operating",
            "advanced_piping_design_and_bim.ipynb": "advanced_operating_hot",
        }
        offenders: list[str] = []

        for notebook_name, artifact_dir in artifact_backed.items():
            artifact_root = notebooks_dir / "code_aster_results" / artifact_dir
            self.assertTrue((artifact_root / "study_depl.csv").exists(), artifact_root)
            text = (notebooks_dir / notebook_name).read_text(encoding="utf-8")
            if "RUN_CODE_ASTER = False" not in text:
                offenders.append(notebook_name)

        self.assertEqual([], offenders)
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_notebook_code_aster_results.py::TestNotebookResultProvenance::test_artifact_backed_notebooks_default_to_load_existing_results -q
```

Expected: failure listing notebooks that still default to `RUN_CODE_ASTER = True`.

- [ ] **Step 3: Update the artifact-backed notebooks**

In each listed notebook, change the code cell line:

```python
RUN_CODE_ASTER = True
```

to:

```python
RUN_CODE_ASTER = False
```

Immediately above it, add this comment line in the same code cell:

```python
# VS Code/Jupyter review defaults to committed real Code_Aster artifacts; set True only after the runtime doctor passes.
```

Do not change `notebooks/visualize_elements_and_supports.ipynb` in this task because it does not have a committed `elements_supports_loadcase1` artifact directory.

- [ ] **Step 4: Run notebook provenance tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_notebook_code_aster_results.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Execute two representative notebooks**

Run:

```powershell
$env:TUBA_NOTEBOOK_BACKEND = "static"
$script = @'
import pathlib
import nbformat
from nbclient import NotebookClient

for name in ["03_stress_analysis_and_compliance.ipynb", "04_visualization_gallery.ipynb"]:
    path = pathlib.Path("notebooks") / name
    nb = nbformat.read(path, as_version=4)
    NotebookClient(nb, timeout=240, kernel_name="python3", allow_errors=False).execute()
    print(f"executed {name}")
'@
$script | .\.venv\Scripts\python.exe -
```

Expected:

```text
executed 03_stress_analysis_and_compliance.ipynb
executed 04_visualization_gallery.ipynb
```

- [ ] **Step 6: Remove generated notebook outputs**

Run:

```powershell
$root = (Resolve-Path .).Path
$targets = @(
  "notebooks\viz_gallery_bundle",
  "notebooks\viz_gallery_report",
  "notebooks\viz_gallery_deformed.html",
  "notebooks\viz_gallery_stress.ply",
  "notebooks\viz_gallery_model.gltf",
  "notebooks\viz_gallery_blender.py"
)
foreach ($target in $targets) {
  if (Test-Path -LiteralPath $target) {
    $resolved = (Resolve-Path -LiteralPath $target).Path
    if (-not $resolved.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
      throw "Refusing to remove outside workspace: $resolved"
    }
    Remove-Item -LiteralPath $target -Recurse -Force
  }
}
```

- [ ] **Step 7: Commit**

```powershell
git add tests/test_notebook_code_aster_results.py notebooks/00_welcome_and_setup.ipynb notebooks/03_stress_analysis_and_compliance.ipynb notebooks/04_visualization_gallery.ipynb notebooks/06_structural_frames_and_optimization.ipynb notebooks/07_bim_data_exchange.ipynb notebooks/advanced_piping_design_and_bim.ipynb
git commit -m "docs: default notebooks to committed Code_Aster artifacts"
```

---

### Task 5: User-Facing Example Provenance Cleanup

**Files:**
- Modify: `examples/demo.py`
- Modify: `examples/operating_state_clash.py`
- Modify: `examples/realtime_visualization_review.py`
- Modify: `tests/test_examples.py`
- Modify: `tests/test_operating_state_example.py`
- Modify: `tests/test_realtime_visualization_bundle.py`
- Modify: `tests/realtime_visualization_fixtures.py` if the example tests need a shared fixture.

**Interfaces:**
- Consumes: deterministic fixture result states only from tests.
- Produces: user-facing examples that either import real Code_Aster artifacts or stop before displaying solver-derived values.

- [ ] **Step 1: Add a failing guardrail test for examples**

Append this test to `tests/test_examples.py`:

```python
    def test_user_facing_examples_do_not_publish_synthetic_solver_results(self):
        examples_dir = Path(__file__).resolve().parents[1] / "examples"
        forbidden_snippets = (
            'FEAResults(solver_name="mock',
            "FEAResults(solver_name='mock",
            'ResultState(\n        id="result_state:Hot:mock"',
            'ResultState(\n        id="result_state:Hot:review_mock"',
            'metadata={"source": "mock_result_state_for_example"}',
            'metadata={"source": "realtime_visualization_review_mock_result_state"}',
        )
        offenders: list[str] = []

        for path in sorted(examples_dir.glob("*.py")):
            text = path.read_text(encoding="utf-8")
            matches = [snippet for snippet in forbidden_snippets if snippet in text]
            if matches:
                offenders.append(f"{path.name}: {', '.join(matches)}")

        self.assertEqual([], offenders)
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_examples.py::TestExamples::test_user_facing_examples_do_not_publish_synthetic_solver_results -q
```

Expected: failure listing `demo.py`, `operating_state_clash.py`, and `realtime_visualization_review.py`.

- [ ] **Step 3: Change `examples/demo.py` to stop at export-only**

In `examples/demo.py`, remove imports of `FEAResults`, `NodeResult`, `ElementResult`, `numpy`, and `ASMEB313Evaluator`.

Replace the entire section beginning with:

```python
# 5. Perform ASME B31.3 Compliance check using mock results
```

through the final interactive plot block with:

```python
    # 5. Stop before compliance and result visualization.
    print("\n[5/6] Code_Aster execution required before compliance or result visualization.")
    print("  -> This demo generated solver handoff files only.")
    print("  -> Run Code_Aster, then import study_depl.csv, study_effo.csv, study_reac.csv, and study_sieq.csv.")

    print("\n[6/6] Next command for a configured runtime:")
    print("     python -m tuba.solver.code_aster_doctor --check")
    print("     $env:TUBA_RUN_CODE_ASTER_INTEGRATION = \"1\"")
    print("     .\\.venv\\Scripts\\python.exe -m pytest tests/integration/test_code_aster_real_smoke.py -q")

    print("\nNo compliance report or stress plot was produced from synthetic values.")
```

- [ ] **Step 4: Change operating-state example to fail loud without real artifacts**

In `examples/operating_state_clash.py`, replace `run_example(...)` with:

```python
def run_example(output_dir: str | Path = ".benchmarks/operating_state_clash_example") -> dict[str, Any]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    model, _n0, _n1 = build_model()

    study = CodeAsterSolver(work_dir=str(output_path / "code_aster")).export_analysis_study(
        model,
        "Hot",
        output_dir=output_path / "code_aster",
    )
    raise RuntimeError(
        "Operating-state clash review requires real Code_Aster result artifacts. "
        f"Exported the study to {study.work_dir}. Execute study.export with Code_Aster, "
        "then import the generated result tables before building operating geometry states."
    )
```

Remove unused imports from that file: `json`, `TrimeshClashEngine`, `ResultState`, `create_cold_geometry_state`, `create_operating_geometry_state`, `build_deformed_envelopes`, `export_bcf_topics`, and `build_visualization_scene`.

- [ ] **Step 5: Change realtime visualization example to fail loud without real artifacts**

In `examples/realtime_visualization_review.py`, replace `run_example(...)` with:

```python
def run_example(output_dir: str | Path = ".benchmarks/realtime_visualization_review") -> dict[str, Any]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    model, _n0, _n1 = build_model()

    study_dir = output_path / "code_aster"
    study = CodeAsterSolver(work_dir=str(study_dir)).export_analysis_study(
        model,
        "Hot",
        output_dir=study_dir,
    )
    raise RuntimeError(
        "Realtime result review requires real Code_Aster result artifacts. "
        f"Exported the study to {study.work_dir}. Execute study.export with Code_Aster, "
        "then use tuba.analysis.code_aster_artifacts.import_code_aster_artifacts before writing a review scene."
    )
```

Remove unused imports from that file: `json`, `TrimeshClashEngine`, `AnalysisMesh`, `ResultState`, `create_cold_geometry_state`, `create_operating_geometry_state`, `create_visual_deformed_geometry_state`, `build_visualization_scene`, and `write_scene_bundle`.

- [ ] **Step 6: Update example tests**

In `tests/test_operating_state_example.py`, replace the assertions after `with TemporaryDirectory() as tmpdir:` with:

```python
        with TemporaryDirectory() as tmpdir:
            with self.assertRaisesRegex(RuntimeError, "requires real Code_Aster result artifacts"):
                module.run_example(output_dir=tmpdir)
            self.assertTrue((Path(tmpdir) / "code_aster" / "study_manifest.json").exists())
```

In `tests/test_realtime_visualization_bundle.py`, replace the call to the example with the existing fixture:

```python
from tests.realtime_visualization_fixtures import operating_state_review_fixture
```

Then replace the body of `test_example_writes_complete_review_scene_bundle` with:

```python
        with TemporaryDirectory() as tmpdir:
            fixture = operating_state_review_fixture(Path(tmpdir))
            scene_payload = json.loads(fixture.bundle.scene_path.read_text(encoding="utf-8"))
            self.assertTrue(fixture.bundle.root.exists())
            self.assertTrue((fixture.bundle.metadata_dir / "object_map.json").exists())
            self.assertTrue((fixture.bundle.geometry_dir / "geometry_assets.json").exists())

        scene = VisualizationScene.from_dict(scene_payload)
        scene.validate()
        kinds = {obj.kind for obj in scene.objects}
        overlay_types = {overlay.data.get("result_type") for overlay in scene.overlays if overlay.kind == "solver_result"}

        self.assertEqual(fixture.expected_counts["operating_clashes"], 1)
        self.assertGreater(fixture.expected_counts["analysis_mesh_elements"], 0)
        self.assertGreater(fixture.expected_counts["scene_geometry_assets"], 0)
        self.assertIn("analysis_mesh_element", kinds)
        self.assertIn("deformed_centerline", kinds)
        self.assertIn("deformed_envelope", kinds)
        self.assertIn("deformed_analysis_mesh_element", kinds)
        self.assertIn("clash_marker", kinds)
        self.assertIn("stress", overlay_types)
        self.assertEqual(scene.issues[0].external_refs["clash_review"]["grouping"]["load_case"], "Hot")
```

- [ ] **Step 7: Run example tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_examples.py tests/test_operating_state_example.py tests/test_realtime_visualization_bundle.py -q
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```powershell
git add examples/demo.py examples/operating_state_clash.py examples/realtime_visualization_review.py tests/test_examples.py tests/test_operating_state_example.py tests/test_realtime_visualization_bundle.py
git commit -m "fix: remove synthetic solver results from user examples"
```

---

### Task 6: Documentation And Final Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/code_aster_installation.md`
- Modify: `tests/test_code_aster_docs.py`

**Interfaces:**
- Consumes: doctor `--check`, notebook defaults, user-facing example behavior.
- Produces: documentation that matches the new workflow.

- [ ] **Step 1: Add failing docs assertions**

In `tests/test_code_aster_docs.py`, add to `test_readme_documents_required_runtime_and_doctor`:

```python
        self.assertIn("python -m tuba.solver.code_aster_doctor --check", text)
        self.assertIn("VS Code notebooks default to loading committed Code_Aster artifacts", text)
```

- [ ] **Step 2: Run docs test to verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_code_aster_docs.py -q
```

Expected: failure because README does not yet document `--check` and VS Code artifact defaults.

- [ ] **Step 3: Update README**

In `README.md`, update the Code_Aster runtime section to include:

```markdown
Run the bounded runtime readiness check before enabling solver execution from notebooks:

```powershell
.\.venv\Scripts\python.exe -m tuba.solver.code_aster_doctor --check
```

VS Code notebooks default to loading committed Code_Aster artifacts when those
artifacts are present. Set `RUN_CODE_ASTER = True` only after the doctor check
reports a ready runtime; the notebook loader preserves existing result tables
when runtime preflight fails.
```

- [ ] **Step 4: Update Code_Aster installation docs**

In `docs/code_aster_installation.md`, add this verification block near the doctor command section:

```markdown
Use `--check` to prove the discovered runtime can find a Code_Aster runner
without starting a full solve:

```powershell
.\.venv\Scripts\python.exe -m tuba.solver.code_aster_doctor --check
```

If the check reports `blocked`, do not set `RUN_CODE_ASTER = True` in notebooks.
Keep the notebook in artifact-loading mode until the runtime check is ready.
```

- [ ] **Step 5: Run final Python checks**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_code_aster_runtime.py tests/test_code_aster_doctor.py tests/test_code_aster_notebook_loader.py tests/test_notebook_code_aster_results.py tests/test_notebook_backend.py tests/test_notebook_vscode_render.py tests/test_examples.py tests/test_operating_state_example.py tests/test_realtime_visualization_bundle.py tests/test_code_aster_docs.py -q
```

Expected: all tests pass, with `tests/test_notebook_vscode_render.py` skipped only if notebook/PyVista dependencies are missing.

- [ ] **Step 6: Run viewer checks**

Run:

```powershell
cd viewer
npm test
npm run build
cd ..
```

Expected: `node --test` reports all viewer tests pass, and Vite build completes.

- [ ] **Step 7: Run real-solver gate only when configured**

Run:

```powershell
$env:TUBA_RUN_CODE_ASTER_INTEGRATION = "1"
.\.venv\Scripts\python.exe -m pytest tests/integration/test_code_aster_real_smoke.py -q -rs
```

Expected when runtime is not configured: skip or bounded failure with a clear preflight reason. Expected when runtime is configured: pass with real Code_Aster artifacts.

- [ ] **Step 8: Commit**

```powershell
git add README.md docs/code_aster_installation.md tests/test_code_aster_docs.py
git commit -m "docs: document notebook runtime preflight"
```

---

## Final Verification Gate

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_code_aster_runtime.py tests/test_code_aster_doctor.py tests/test_code_aster_notebook_loader.py tests/test_notebook_code_aster_results.py tests/test_notebook_backend.py tests/test_notebook_vscode_render.py tests/test_examples.py tests/test_operating_state_example.py tests/test_realtime_visualization_bundle.py tests/test_visualization_web_export.py tests/test_visualization_results.py tests/test_visualizer_scenes.py tests/test_code_aster_docs.py -q
cd viewer
npm test
npm run build
cd ..
git status --short
```

Expected:

```text
all selected Python tests pass
viewer node tests pass
viewer build completes
git status shows only intentional changes before commit, then clean after commits
```

If a real Code_Aster runtime is configured, also run:

```powershell
$env:TUBA_RUN_CODE_ASTER_INTEGRATION = "1"
.\.venv\Scripts\python.exe -m pytest tests/integration/test_code_aster_real_smoke.py tests/integration/test_mixed_code_aster_runtime.py -q -rs
```

Expected: real smoke passes or mixed study skips only for explicit missing runtime support.

---

## Self-Review

Spec coverage:

- Runtime readiness preflight is covered by Tasks 1 and 2.
- VS Code notebook display regression is covered by Task 3.
- Artifact-backed notebook default mode is covered by Task 4.
- User-facing synthetic solver result cleanup is covered by Task 5.
- Documentation and final gates are covered by Task 6.
- B31J formula expansion is intentionally excluded because current project docs mark it blocked on licensed source text.

Placeholder scan:

- The plan uses exact file paths, exact function names, concrete test code, concrete implementation snippets, and exact commands.
- No task asks the implementer to invent unspecified validation or error handling.

Type consistency:

- `CodeAsterRuntimeCheck` is introduced in Task 1 and consumed by Task 2.
- `preflight_code_aster_runtimes(config)` is introduced in Task 1 and imported in Task 2.
- `require_code_aster_runtime(...)` is introduced in Task 2 and remains private to notebook loading.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-02-code-aster-notebook-cleanup.md`. Two execution options:

1. **Subagent-Driven (recommended)** - Dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints.
