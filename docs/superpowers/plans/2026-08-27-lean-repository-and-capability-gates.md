# Lean Repository and Capability Gates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Windows IFC fail-closed and green, keep optional capabilities from blocking unrelated tests, return JavaScript assertions to Node, and consolidate Tuba-owned disposable outputs under `.build/`.

**Architecture:** Keep the existing Ubuntu all-extras matrix and real Code_Aster gate. Add one focused Windows IFC lane with an import smoke, make general collection tolerant of absent optional packages, move the Playwright configuration test into the viewer suite, and change only output defaults owned by Tuba.

**Tech Stack:** Python 3.11-3.12, uv, pytest, IfcOpenShell 0.8.4.post1, GitHub Actions, Node 22 built-in test runner, Playwright configuration, Git

**Spec:** `docs/superpowers/specs/2026-08-27-lean-repository-and-capability-gates-design.md`

## Global Constraints

- Support Python `>=3.11,<3.13`; do not claim Python 3.13 until every required capability is green there.
- Pin both the `ifc` and `course` extras to `ifcopenshell==0.8.4.post1`; keep `uv.lock` as the only lock file.
- Windows IFC must fail on an import error; its dedicated CI lane may not turn the missing capability into a passing skip.
- General development collection may skip tests whose optional package is absent.
- Keep the existing Ubuntu Python 3.11/3.12 all-extras matrix and the self-hosted real-Code_Aster workflow.
- Preserve `notebooks/code_aster_results/**`; those are canonical attested solver artifacts, not disposable output.
- Put Tuba-owned disposable defaults under `.build/`; keep standard tool-owned caches and package directories native and ignored.
- Add no container requirement, cleanup daemon, dependency wrapper, compatibility alias, custom test runner, or dead-code framework.
- Preserve the product flow: Tuba model -> real Code_Aster solve -> attested artifact import -> processed result display.
- Before every task, run `git status --short -- <task paths>`. The current shared checkout has overlapping WIP in `tests/test_ifc.py`, `examples/code_aster_artifact_review.py`, and `examples/code_aster_tee_volume_review.py`; do not edit, stage, or commit those paths until their existing owner has settled them.
- Never use `git add -A` or commit unrelated working-tree changes. Stage only the paths listed by the task.
- The tee fixture correction is already in commit `1749fae`; verify `tests/test_tee_sif.py`, but do not recreate or recommit the fix.

---

### Task 1: Bound the runtime and make Windows IFC a required capability

**Files:**
- Create: `tests/test_ifc_optional_dependency.py`
- Modify: `pyproject.toml:10,55-57,71-90`
- Modify: `uv.lock`
- Modify: `tuba/external/ifc.py:15-34`
- Modify: `tests/test_package_release.py:126-147`
- Modify: `tests/test_release_metadata.py:66-94`
- Modify: `tests/test_ifc.py:1-6`
- Modify: `tests/test_ifc_mapping.py:1-5`
- Modify: `tests/test_ifc_pipe_systems.py:1-6`
- Modify: `tests/test_ifc_placements.py:1-10,32,71`
- Modify: `tests/test_code_aster_artifact_import.py:1-10`
- Modify: `tests/test_notebook_course_didactics.py:1-6`
- Modify: `.github/workflows/ci.yml` after the `python` job

**Interfaces:**
- Consumes: the existing `IfcExporter`, `IfcImporter`, `_HAS_IFCOPENSHELL`, pytest suite, uv extras, and CI workflow.
- Produces: Python support range `>=3.11,<3.13`; extras `ifcopenshell==0.8.4.post1`; a graceful `tuba.external.ifc` import without the extra; CI job `ifc-windows`; unchanged IFC exporter/importer APIs when the extra is installed.

- [ ] **Step 1: Verify task paths are available and record the current focused baseline**

Run:

```powershell
git status --short -- pyproject.toml uv.lock tuba/external/ifc.py tests/test_package_release.py tests/test_release_metadata.py tests/test_ifc.py tests/test_ifc_mapping.py tests/test_ifc_pipe_systems.py tests/test_ifc_placements.py tests/test_code_aster_artifact_import.py tests/test_notebook_course_didactics.py .github/workflows/ci.yml
uv run --python 3.12 python -m pytest tests/test_package_release.py tests/test_release_metadata.py tests/test_tee_sif.py -q
```

Expected: the tests pass. If an overlapping path is dirty, stop this task until that WIP is committed or otherwise settled; do not absorb it into this task.

- [ ] **Step 2: Write failing runtime, optional-import, and CI ownership tests**

Add to `tests/test_package_release.py`:

```python
def test_supported_python_and_ifc_versions_are_explicit():
    project = _project()

    assert project["requires-python"] == ">=3.11,<3.13"
    for extra in ("ifc", "course"):
        assert "ifcopenshell==0.8.4.post1" in project["optional-dependencies"][extra]
    assert "pyyaml>=6" in project["optional-dependencies"]["dev"]
```

Create `tests/test_ifc_optional_dependency.py`:

```python
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_ifc_module_defers_missing_dependency_until_use():
    script = r'''
import sys

class BlockIfcOpenShell:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "ifcopenshell" or fullname.startswith("ifcopenshell."):
            raise ModuleNotFoundError("blocked for optional-dependency test", name=fullname)
        return None

sys.meta_path.insert(0, BlockIfcOpenShell())
from tuba.external.ifc import IfcExporter, _HAS_IFCOPENSHELL

assert _HAS_IFCOPENSHELL is False
try:
    IfcExporter()
except ImportError as exc:
    assert "tuba[ifc]" in str(exc)
else:
    raise AssertionError("IfcExporter accepted a missing IfcOpenShell runtime")
'''
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
```

Add to `tests/test_release_metadata.py`:

```python
def test_windows_ifc_job_fails_closed_on_the_locked_runtime():
    workflow = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    )
    job = workflow["jobs"]["ifc-windows"]
    commands = [step["run"] for step in job["steps"] if "run" in step]

    assert job["runs-on"] == "windows-latest"
    assert any(
        step.get("uses") == "astral-sh/setup-uv@v6"
        and step.get("with", {}).get("python-version") == "3.12"
        for step in job["steps"]
    )
    assert "uv sync --extra dev --extra ifc --locked" in commands
    assert 'uv run python -c "import ifcopenshell"' in commands
    assert (
        "uv run python -m pytest tests/test_ifc.py tests/test_ifc_mapping.py "
        "tests/test_ifc_pipe_systems.py tests/test_ifc_placements.py "
        "tests/test_code_aster_artifact_import.py -q"
    ) in commands
```

- [ ] **Step 3: Run the new tests and record the expected RED**

Run:

```powershell
uv run --python 3.12 python -m pytest tests/test_package_release.py::test_supported_python_and_ifc_versions_are_explicit tests/test_ifc_optional_dependency.py tests/test_release_metadata.py::test_windows_ifc_job_fails_closed_on_the_locked_runtime -q
```

Expected: three failures. Package metadata is unbounded, `tuba.external.ifc` imports `ifc_mapping` before its guard, and `ifc-windows` does not exist.

- [ ] **Step 4: Tighten package metadata and regenerate the one lock file**

Change the relevant `pyproject.toml` entries to:

```toml
requires-python = ">=3.11,<3.13"

ifc = [
    "ifcopenshell==0.8.4.post1",
]

course = [
    "jupyterlab>=3",
    "nbclient>=0.10",
    "nbformat>=5.10",
    "ipykernel>=6",
    "ipywidgets",
    "pyvista[all]>=0.48",
    "trame>=3",
    "trame-vtk>=2",
    "trame-vuetify>=3",
    "jupyter-server-proxy",
    "meshio>=5.0",
    "h5py>=3.10",
    "ifcopenshell==0.8.4.post1",
    "trimesh>=4.0",
    "python-fcl>=0.7.0.11",
    "scipy>=1.10",
]

dev = [
    "pytest>=8",
    "pyyaml>=6",
]
```

Keep the other `course` entries unchanged, then run:

```powershell
uv lock
```

Expected: `uv.lock` resolves IfcOpenShell 0.8.4.post1 and excludes Python 3.13 through the project requirement.

- [ ] **Step 5: Move all IfcOpenShell-dependent imports behind the existing use boundary**

In `tuba/external/ifc.py`, retain placement imports outside the guard and move the mapping and pipe helper imports into the existing `try` block:

```python
try:
    import ifcopenshell
    import ifcopenshell.guid
    import ifcopenshell.util.representation

    from tuba.external.ifc_mapping import IfcGuidRegistry, ifc_property
    from tuba.external.ifc_pipes import export_pipe_products

    _HAS_IFCOPENSHELL = True
except ImportError:
    _HAS_IFCOPENSHELL = False
```

Delete the former top-level imports of `ifc_mapping` and `ifc_pipes`. Update the existing error boundary to point at the supported extra:

```python
def _require_ifcopenshell():
    if not _HAS_IFCOPENSHELL:
        raise ImportError(
            "ifcopenshell is required for IFC integration. "
            "Install it via: pip install 'tuba[ifc]'"
        )
```

Do not add placeholder definitions for the guarded helper names; exporter and importer constructors already stop before those helpers can be used.

- [ ] **Step 6: Make optional test modules collection-safe**

In each of `tests/test_ifc.py`, `tests/test_ifc_mapping.py`, `tests/test_ifc_pipe_systems.py`, and `tests/test_code_aster_artifact_import.py`, replace the eager import with:

```python
import pytest

ifcopenshell = pytest.importorskip("ifcopenshell")
```

In `tests/test_ifc_placements.py`, put the skip before importing Tuba's IFC module:

```python
import pytest

pytest.importorskip("ifcopenshell")

from tuba.placements import PlacementFrame
```

Delete the `_HAS_IFCOPENSHELL` import and all three `@unittest.skipUnless(...)` decorators; the module-level skip now owns the condition.

In `tests/test_notebook_course_didactics.py`, replace the eager import with:

```python
import pytest

nbformat = pytest.importorskip("nbformat")
```

- [ ] **Step 7: Add the focused Windows IFC job**

Add this job to `.github/workflows/ci.yml` after `python`:

```yaml
  ifc-windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
        with:
          python-version: "3.12"
      - run: uv sync --extra dev --extra ifc --locked
      - run: uv run python -c "import ifcopenshell"
      - run: >-
          uv run python -m pytest tests/test_ifc.py tests/test_ifc_mapping.py
          tests/test_ifc_pipe_systems.py tests/test_ifc_placements.py
          tests/test_code_aster_artifact_import.py -q
```

The import command is deliberately separate from pytest. It makes a broken wheel fail even though general test modules use `importorskip()`.

- [ ] **Step 8: Run focused and isolated capability verification**

Run:

```powershell
uv run --python 3.12 python -m pytest tests/test_package_release.py tests/test_ifc_optional_dependency.py tests/test_release_metadata.py::test_windows_ifc_job_fails_closed_on_the_locked_runtime tests/test_tee_sif.py -q
uv run --isolated --python 3.12 --extra dev python -m pytest --collect-only -q
uv run --isolated --python 3.12 --extra dev --extra ifc python -c "import ifcopenshell; assert ifcopenshell.version == '0.8.4.post1'"
uv run --isolated --python 3.12 --extra dev --extra ifc python -m pytest tests/test_ifc.py tests/test_ifc_mapping.py tests/test_ifc_pipe_systems.py tests/test_ifc_placements.py tests/test_code_aster_artifact_import.py -q
```

Expected: all commands pass. The dev-only collection reports the IFC and notebook modules as skipped rather than collection errors; the IFC environment imports 0.8.4.post1 and runs the focused tests without an IfcOpenShell skip.

- [ ] **Step 9: Commit the runtime capability slice**

Run:

```powershell
git add pyproject.toml uv.lock tuba/external/ifc.py tests/test_ifc_optional_dependency.py tests/test_package_release.py tests/test_release_metadata.py tests/test_ifc.py tests/test_ifc_mapping.py tests/test_ifc_pipe_systems.py tests/test_ifc_placements.py tests/test_code_aster_artifact_import.py tests/test_notebook_course_didactics.py .github/workflows/ci.yml
git diff --cached --check
git commit -m "fix: make Windows IFC a required capability"
```

Expected: the commit contains only the listed runtime, test, and CI paths.

---

### Task 2: Return Playwright configuration assertions to Node

**Files:**
- Create: `viewer/test/playwright-config.test.js`
- Modify: `tests/test_release_metadata.py:1-7,339-376`

**Interfaces:**
- Consumes: the default export of `viewer/playwright.config.js` and `TUBA_PAGES_SITE_ROOT`.
- Produces: the same default/prebuilt web-server and snapshot-path assertions under `npm test`; Python release metadata no longer launches Node.

- [ ] **Step 1: Verify task paths and record the old owner green**

Run:

```powershell
git status --short -- viewer/test/playwright-config.test.js tests/test_release_metadata.py viewer/playwright.config.js
uv run --python 3.12 python -m pytest tests/test_release_metadata.py::test_playwright_pages_gate_can_serve_the_prebuilt_workflow_artifact -q
```

Expected: the existing Python-owned behavior test passes. Stop if either modified path has unrelated WIP.

- [ ] **Step 2: Add the equivalent Node-owned characterization test**

Create `viewer/test/playwright-config.test.js`:

```javascript
import assert from "node:assert/strict";
import test from "node:test";

let importSequence = 0;

async function loadConfig(siteRoot) {
  const previous = process.env.TUBA_PAGES_SITE_ROOT;
  if (siteRoot === undefined) {
    delete process.env.TUBA_PAGES_SITE_ROOT;
  } else {
    process.env.TUBA_PAGES_SITE_ROOT = siteRoot;
  }

  try {
    const url = new URL("../playwright.config.js", import.meta.url);
    url.searchParams.set("test", String(importSequence++));
    return (await import(url.href)).default;
  } finally {
    if (previous === undefined) {
      delete process.env.TUBA_PAGES_SITE_ROOT;
    } else {
      process.env.TUBA_PAGES_SITE_ROOT = previous;
    }
  }
}

test("Playwright serves the built Pages artifact or an explicit prebuilt root", async () => {
  const defaultConfig = await loadConfig(undefined);
  assert.equal(
    defaultConfig.snapshotPathTemplate,
    "{testDir}/snapshots/{testFilePath}/{platform}/{arg}{ext}",
  );
  assert.match(
    defaultConfig.webServer.command,
    /scripts\/build_pages\.py pages --output \.build\/pages-check/,
  );
  assert.match(defaultConfig.webServer.command, /\.\.\/\.build\/pages-check/);

  const prebuiltConfig = await loadConfig("../_site");
  assert.match(prebuiltConfig.webServer.command, /\.\.\/_site/);
  assert.match(prebuiltConfig.webServer.command, /configFile: false/);
  assert.doesNotMatch(prebuiltConfig.webServer.command, /scripts\/build_pages\.py/);
});
```

This is a test-owner move, not new production behavior. A RED phase would require inventing an unnecessary production seam, so use old-green -> new-green -> delete-old.

- [ ] **Step 3: Run the new owner before deleting the old one**

Run from `viewer/`:

```powershell
node --test test/playwright-config.test.js
```

Expected: one passing Node test with both environment branches covered.

- [ ] **Step 4: Delete the Python-owned duplicate**

Delete `test_playwright_pages_gate_can_serve_the_prebuilt_workflow_artifact()` from `tests/test_release_metadata.py`. Remove the now-unused imports:

```python
import json
import os
```

Keep `subprocess`; the release-tag contract still uses it.

- [ ] **Step 5: Verify both owning suites**

Run:

```powershell
uv run --python 3.12 python -m pytest tests/test_release_metadata.py -q
Set-Location viewer
npm.cmd test
Set-Location ..
```

Expected: release metadata passes without spawning Node and the full viewer suite passes with the new Playwright configuration test.

- [ ] **Step 6: Commit the ownership move**

Run:

```powershell
git add viewer/test/playwright-config.test.js tests/test_release_metadata.py
git diff --cached --check
git commit -m "test: move Playwright config checks to Node"
```

Expected: one new Node test and a net deletion from the Python test file.

---

### Task 3: Consolidate disposable output and enforce clean test jobs

**Files:**
- Modify: `tuba/benchmarks.py:10-40,126-134`
- Modify: `examples/realtime_visualization_review.py:16`
- Modify: `examples/operating_state_clash.py:32`
- Modify: `examples/code_aster_artifact_review.py:35-40`
- Modify: `examples/code_aster_tee_volume_review.py:52-56`
- Modify: `tests/test_model_indexes.py`
- Modify: `tests/test_examples.py`
- Modify: `tests/test_release_metadata.py`
- Modify: `.github/workflows/ci.yml`
- Modify: `docs/content/examples.md` after the local example command

**Interfaces:**
- Consumes: existing benchmark and example call signatures, the four test-only CI jobs, and Git's native clean/diff commands.
- Produces: default root `.build/benchmarks`; explicit output arguments remain unchanged; test-only jobs end with `git diff --exit-code`; canonical solver artifacts remain untouched.

- [ ] **Step 1: Verify path ownership and current output behavior**

Run:

```powershell
git status --short -- tuba/benchmarks.py examples/realtime_visualization_review.py examples/operating_state_clash.py examples/code_aster_artifact_review.py examples/code_aster_tee_volume_review.py tests/test_model_indexes.py tests/test_examples.py tests/test_release_metadata.py .github/workflows/ci.yml docs/content/examples.md
uv run --python 3.12 python -m pytest tests/test_model_indexes.py tests/test_examples.py tests/test_release_metadata.py -q
```

Expected: tests pass. The two Code_Aster review examples must be clean before this task starts; do not absorb active AnalysisRun publication WIP.

- [ ] **Step 2: Add failing default-output and clean-tree contract tests**

Add this pytest function to `tests/test_model_indexes.py`:

```python
def test_benchmark_summary_defaults_to_build_root(tmp_path, monkeypatch):
    model = Model(project_name="DefaultBenchmarkRoot")
    model.add_node((0.0, 0.0, 0.0))
    monkeypatch.chdir(tmp_path)

    path = Path(write_model_benchmark_summary(model))

    assert path.parent == Path(".build/benchmarks")
    assert path.is_file()
```

Add imports to `tests/test_examples.py`:

```python
from inspect import signature

from examples.code_aster_artifact_review import run_example as run_artifact_review
from examples.code_aster_tee_volume_review import run_example as run_tee_volume_review
from examples.operating_state_clash import run_example as run_operating_clash
from examples.realtime_visualization_review import run_example as run_realtime_review
```

Add this method to `TestExamples`:

```python
    def test_generated_example_defaults_use_build_root(self):
        expected = {
            run_artifact_review: ".build/benchmarks/code_aster_artifact_review",
            run_tee_volume_review: ".build/benchmarks/code_aster_tee_volume_review",
            run_operating_clash: ".build/benchmarks/operating_state_clash_example",
            run_realtime_review: ".build/benchmarks/realtime_visualization_review",
        }

        for runner, output_dir in expected.items():
            with self.subTest(runner=runner.__module__):
                self.assertEqual(
                    signature(runner).parameters["output_dir"].default,
                    output_dir,
                )
```

Add to `tests/test_release_metadata.py`:

```python
def test_test_only_ci_jobs_end_with_clean_tree_check():
    workflow = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    )

    for job_name in ("python", "notebooks-and-docs", "viewer", "assembled-pages"):
        commands = [
            step["run"]
            for step in workflow["jobs"][job_name]["steps"]
            if "run" in step
        ]
        assert commands[-1] == "git diff --exit-code"

    for job_name in ("distribution", "code-aster-integration"):
        commands = [
            step["run"]
            for step in workflow["jobs"][job_name]["steps"]
            if "run" in step
        ]
        assert "git diff --exit-code" not in commands
```

- [ ] **Step 3: Run the new tests and record the expected RED**

Run:

```powershell
uv run --python 3.12 python -m pytest tests/test_model_indexes.py::test_benchmark_summary_defaults_to_build_root tests/test_examples.py::TestExamples::test_generated_example_defaults_use_build_root tests/test_release_metadata.py::test_test_only_ci_jobs_end_with_clean_tree_check -q
```

Expected: all three tests fail because current defaults use `.benchmarks` and the test-only jobs lack a final clean-tree step.

- [ ] **Step 4: Change the central benchmark defaults once**

In `tuba/benchmarks.py`, add one private constant and reuse it:

```python
_DEFAULT_BENCHMARK_DIRECTORY = ".build/benchmarks"


def write_model_benchmark_summary(
    model: TubaModel,
    *,
    directory: str | Path = _DEFAULT_BENCHMARK_DIRECTORY,
) -> str:
```

- [ ] **Step 5: Move the four example defaults under the same root**

Use these exact defaults and change no other example behavior:

```python
".build/benchmarks/realtime_visualization_review"
".build/benchmarks/operating_state_clash_example"
".build/benchmarks/code_aster_artifact_review"
".build/benchmarks/code_aster_tee_volume_review"
```

- [ ] **Step 6: Add clean-tree assertions only to test-only jobs**

Append this final step to `python`, `notebooks-and-docs`, `viewer`, and `assembled-pages` in `.github/workflows/ci.yml`:

```yaml
      - run: git diff --exit-code
```

Do not add it to `distribution` or `code-aster-integration`; those jobs intentionally assemble or refresh artifacts.

- [ ] **Step 7: Document the single Tuba-owned output root**

After the local example command in `docs/content/examples.md`, add:

````markdown
Tuba-owned benchmark and review outputs default to `.build/`. When no Tuba
command is running, remove all ignored Tuba build output with:

```powershell
git clean -fdX -- .build
```

Canonical Code_Aster artifacts under `notebooks/code_aster_results/` are
committed engineering evidence and are not cleanup targets.
````

- [ ] **Step 8: Run focused verification and the tracked-default sweep**

Run:

```powershell
uv run --python 3.12 python -m pytest tests/test_model_indexes.py tests/test_examples.py tests/test_release_metadata.py tests/test_tee_sif.py -q
rg -n "\.benchmarks" tuba examples tests docs/content README.md
git diff --check
```

Expected: tests pass; ripgrep returns no matches; `git diff --check` returns zero. `.gitignore` and the approved design/plan may retain historical `.benchmarks` text and are intentionally outside this sweep.

- [ ] **Step 9: Run final capability and product verification**

Run:

```powershell
uv run --isolated --python 3.12 --extra dev python -m pytest --collect-only -q
uv run --isolated --python 3.12 --extra dev --extra ifc python -c "import ifcopenshell; assert ifcopenshell.version == '0.8.4.post1'"
uv run --isolated --python 3.12 --extra dev --extra ifc python -m pytest tests/test_ifc.py tests/test_ifc_mapping.py tests/test_ifc_pipe_systems.py tests/test_ifc_placements.py tests/test_code_aster_artifact_import.py -q
uv sync --python 3.12 --all-extras --locked
uv run python -m pytest -q
Set-Location viewer
npm.cmd test
Set-Location ..
```

Expected: dev-only collection succeeds with optional skips; Windows IFC imports and passes focused tests; the broad Python and viewer suites pass. Do not report Code_Aster readiness from these commands.

On the self-hosted Code_Aster runner, run:

```powershell
uv run python -m tuba.solver.code_aster_doctor --check
uv run python -m pytest tests/test_code_aster_real_smoke.py
uv run python scripts/refresh_code_aster_gallery.py --all
uv run python scripts/build_pages.py pages --output .build/code-aster-pages
```

Expected: the real solver check, solve, artifact refresh, attestation, import, and Pages build pass. If that runner is unavailable, record the external runtime blocker and do not claim the real-solver gate green.

- [ ] **Step 10: Commit the disposable-output slice and verify a clean task tree**

Run:

```powershell
git add tuba/benchmarks.py examples/realtime_visualization_review.py examples/operating_state_clash.py examples/code_aster_artifact_review.py examples/code_aster_tee_volume_review.py tests/test_model_indexes.py tests/test_examples.py tests/test_release_metadata.py .github/workflows/ci.yml docs/content/examples.md
git diff --cached --check
git commit -m "chore: consolidate disposable outputs"
git diff --exit-code
git diff --cached --exit-code
```

Expected: the commit contains only the listed output, test, workflow, and documentation paths. In an isolated execution worktree both final diff commands return zero; in the shared checkout, compare only task paths and preserve unrelated WIP.
