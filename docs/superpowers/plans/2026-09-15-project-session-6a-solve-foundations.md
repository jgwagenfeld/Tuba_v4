# Project and Authoring Session, Plan 6a: Solve Foundations

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Solves and the studio's command preview export through one helper. A solve checks the study's operations and solver options once, when it loads the study. The Pages validator finds each run's attestation through its provenance, so it is ready for per-operation artifact folders.

**Architecture:**
- **Export helper.** `tuba/project/freshness.py` gains `export_study`, beside `_identity`, so the volume-or-beam export choice lives in one place. `solve_project` and the studio's `code_aster_commands` call it.
- **Study settings.** `tuba/project/study.py`'s `study_settings(study)` returns validated `StudySettings(operations, solver_options, volume_export)`, read from today's study names (`LOAD_CASES`, `SOLVER_OPTIONS`, `VOLUME_EXPORT`). `solve_project` and `python -m tuba.project` use it. `evidence_dir` closes its Windows name gaps.
- **Pages validator.** `scripts/build_pages.py` reads each run's attestation from the folder its result's `files.execution` names, and the contact profile reads `study_contact.json` from that same folder, instead of assuming `artifacts/`.
- **Where 6a sits.** Plan 6a is the part of roadmap step 6 that cannot collide with the support-attachment session, whose next tasks re-solve gallery evidence through today's refresh. Two plans follow:
  - 6b, once support-attachment has merged: the study-contract switch, Standard review, staging, the CLI and the refresh.
  - 6c, last: trust presentation.

**Tech Stack:** Python 3.12, pytest, standard library only.

**Spec:** `docs/superpowers/specs/2026-09-13-project-authoring-session-design.md`: decisions 10, 14, 19 and 23, and roadmap step 6.

## Global Constraints

- **Worktree:** execute in `D:/tmp/tuba-plan6` on branch `project-session/6-study-contract` (created from `main` at `f0ebb82`).
  - Never commit in `D:/Gitprojects/Tuba_v4`: another session works there.
  - Never `git stash` (the stash stack is shared) and never `git pull`.
- **Python:** the worktree has no `.venv`. Run tests with the main repo's interpreter from the worktree root, as a module, so the worktree's `tuba` is imported first: `D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest <args>` (written `PY -m pytest` below).
- **Known worktree failures:** two tests in `tests/test_package_release.py` fail in a fresh worktree with "'vite' is not recognized" (no `viewer/node_modules`); ignore them. The suite on `f0ebb82`: 1138 passed / 34 skipped / 151 subtests / 1 pre-existing zmq warning, plus those two.
  - `test_clean_git_index_snapshot_rebuilds_identical_viewer_and_installed_launcher` can fail with "Access is denied" while another uv process holds uv's shared cache. Rerun it alone before calling it a regression.
- **Line numbers** cite the files at `f0ebb82`. Earlier tasks shift them, so locate code by the quoted text.
- **Committed evidence is frozen, and Code_Aster never runs.**
  - Never write under `examples/*/evidence/` or `notebooks/code_aster_results/`.
  - Never run Code_Aster or set `TUBA_RUN_CODE_ASTER_INTEGRATION`.
  - Never run `python -m tuba.project` or `tuba.project.main` without an injected solver.
  - Tests copy projects and their evidence into temporary folders.
  - `build_solver_input_identity` and every `compiler_inputs` dict stay exactly as they are.
- **No fabricated results:** project solves are tested through `tests/project_replay.py`, which copies committed real evidence whose attested identity matches the export. A solver double may only refuse to solve.
- **Files not to edit:**
  - `tuba/model.py`, `tuba/analysis/provenance.py`, `tuba/reporting/tables.py`, touched by another session's stashed work;
  - the files the support-attachment session is about to change: `tuba/solver/*`, `tuba/builder.py`, `tuba/mcp/server.py`, `tuba/schema.py`, `tuba/validation.py`, `scripts/official_gallery.py`, `scripts/refresh_code_aster_gallery.py`, every `examples/*` file, and `docs/content/examples.md`.
- **Study names stay:** studies and gallery records keep today's names in this plan (`LOAD_CASES`, `ARTIFACT_DIR`, `VOLUME_EXPORT`, `build_review`). The studio's own reads of those names stay as they are.
- **Also:** no new dependencies, no compatibility shims (ADR 0001), and no commit trailer.
- **Out of scope:**
  - Plan 6b: `OPERATIONS` and `review(ctx)`, the Standard review, staging into `artifacts/<operation>/`, removing `--artifact-dir`, the refresh as a forced solve, and gallery record changes;
  - Plan 6c: the Pages trust gate, relaxing the builders, the viewer's unverified marker, renaming `allow_unverified`, and revisiting the verified-only reuse rule;
  - Plan 7: `open_session`, studio state and the MCP's `solve_model`.

---

### Task 1: One export helper for solves and the studio's command preview

**Files:**
- Modify: `tuba/project/freshness.py` (add `export_study` above `_identity`, `:78`)
- Modify: `tuba/project/solve.py:28` (import) and `:97-101` (export)
- Modify: `tuba/visualization/preview/server.py:789-800` (`code_aster_commands`)
- Modify: `tests/test_project_freshness.py:11` (import) and `:53-68` (two tests export through the helper)
- Modify: `tests/test_project_solve.py:18` (one constant) and one new test after `:175`

**Interfaces:**
- Produces: `tuba.project.freshness.export_study(solver, model, operation, output_dir, volume_export) -> AnalysisStudy`.
  - A study with a volume export compiles 3D solids, passing `export_tensor_stress=False` explicitly (spec decision 19).
  - Every other study compiles its beams and pipes.
  - The choice is the one `_identity` makes, so an exported study attests the identity `expected_identity` computes.
- The gallery refresh and `examples/code_aster_artifact_review.py` keep their own copies of this choice until Plan 6b deletes them. Neither file may be edited in this plan.
- `test_a_volume_study_exports_its_solids_without_the_tensor_stress_table` stays as it is. It asserts the compiled `export_tensor_stress` input, so it fails if a solve ever exports the table, whatever the exporter's default.

- [ ] **Step 1: Write the tests**

In `tests/test_project_freshness.py`:
- change the import line to `from tuba.project.freshness import attested_identities, expected_identity, export_study, stale_operations`;
- in `test_expected_identity_is_the_identity_a_beam_export_writes`, replace `study = CodeAsterSolver(**options).export_analysis_study(model, "Hot", tmp_path)` with `study = export_study(CodeAsterSolver(**options), model, "Hot", tmp_path, None)`;
- in `test_expected_identity_is_the_identity_a_volume_export_writes`, replace `study = CodeAsterSolver().export_volume_study(model, "Pressure", tmp_path, **volume)` with `study = export_study(CodeAsterSolver(), model, "Pressure", tmp_path, volume)`.

Beam and volume identities carry different compiler ids (`tuba.code_aster.v2`, `tuba.code_aster.volume.v2`), so each equality also proves the helper chose the right exporter.

In `tests/test_project_solve.py`, add `TEE = EXAMPLES / "pipe-tee-volume-review"` after `PROFILE`, and add after `test_a_volume_study_exports_its_solids_without_the_tensor_stress_table`:

```python
def test_a_volume_project_reuses_its_committed_evidence_without_exporting(tmp_path):
    project = _copy(tmp_path, TEE)

    outcome = solve_project(project, solver=_RefuseToSolve())

    assert (outcome.solved, outcome.reused, outcome.unverified) == ((), ("Operating",), ())
    assert outcome.runs["Operating"].study.metadata["volume_analysis"]
```

- A solve that failed to reuse the tee's evidence would mesh with Gmsh and then raise `_Exported`.
- The tee's study `check` also runs on the reused run, so the volume evidence passes the check it must pass to land.
- The test copies about 200 MB of committed evidence, so it is slower than its neighbours.

- [ ] **Step 2: Run the tests**

Run: `PY -m pytest tests/test_project_freshness.py tests/test_project_solve.py -q -p no:cacheprovider`

Expected:
- `tests/test_project_freshness.py` errors at collection with `ImportError: cannot import name 'export_study'`.
- The new tee test passes already: it guards the reuse that this task and Task 2 must keep.

- [ ] **Step 3: Add the helper and use it**

In `tuba/project/freshness.py`, add `from tuba.analysis.study import AnalysisStudy` to the `if TYPE_CHECKING:` block, and add above `_identity`:

```python
def export_study(
    solver: CodeAsterSolver,
    model: TubaModel,
    operation: str,
    output_dir: str | Path,
    volume_export: Mapping[str, Any] | None,
) -> AnalysisStudy:
    """Export what a solve of *operation* compiles into *output_dir*, choosing as :func:`_identity` does.

    A study with a volume export compiles 3D solids without the tensor-stress table (spec decision 19);
    every other study compiles its beams and pipes. Solves and the studio's command preview share this choice.
    """
    if volume_export:
        return solver.export_volume_study(model, operation, output_dir, **dict(volume_export), export_tensor_stress=False)
    return solver.export_analysis_study(model, operation, output_dir)
```

In `tuba/project/solve.py`:
- change `from tuba.project.freshness import expected_identity` to `from tuba.project.freshness import expected_identity, export_study`;
- replace the five-line `exported = (...)` expression with `exported = export_study(exporter, model, operation, folder, volume_export)`.

In `tuba/visualization/preview/server.py`'s `code_aster_commands`:
- add `from tuba.project.freshness import export_study` beside its `from tuba.solver.aster import CodeAsterSolver`;
- delete the line `volume_export = getattr(self.study, "VOLUME_EXPORT", None)`;
- replace the five-line `study = (...)` expression with `study = export_study(solver, model, case, work, getattr(self.study, "VOLUME_EXPORT", None))`.

- [ ] **Step 4: Run the covering tests**

Run: `PY -m pytest tests/test_project_freshness.py tests/test_project_solve.py tests/test_studio_project.py -q -p no:cacheprovider`

Expected: PASS. The studio's `/api/comm` test covers `code_aster_commands`.

- [ ] **Step 5: Run the full suite**

Run `PY -m pytest -q -p no:cacheprovider` in the background, with bounded waits; commit only after it finishes.

Expected: no failures other than the two known vite tests.

- [ ] **Step 6: Commit**

```bash
git add tuba/project/freshness.py tuba/project/solve.py tuba/visualization/preview/server.py tests/test_project_freshness.py tests/test_project_solve.py
git commit -m "refactor(project): choose the volume or beam export in one place

Solves and the studio's command preview now export through export_study,
beside the identity code that makes the same choice, so an export attests
the identity its study expects. A volume project reuses its committed
evidence without exporting."
```

---

### Task 2: Check a study's settings once, when it loads

**Files:**
- Create: `tuba/project/study.py`
- Create: `tests/test_project_study.py`
- Modify: `tuba/project/evidence.py:19-36` (the name rule)
- Modify: `tuba/project/solve.py:62-79` (docstring, and read the settings)
- Modify: `tuba/project/__init__.py:104-110` (the CLI reads the settings)
- Modify: `tests/test_project_evidence.py:23-28`
- Modify: `tests/test_project_solve.py` (one new test after `test_a_study_without_operations_has_nothing_to_solve`)
- Modify: `tests/test_project.py` (one new test at the end)

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces:
  - `tuba.project.study.StudySettings`, a frozen dataclass with `operations: tuple[str, ...]`, `solver_options: dict[str, Any]` and `volume_export: dict[str, Any] | None`.
  - `tuba.project.study.study_settings(study) -> StudySettings`. *study* is what `Project.load_study()` returns: None, or a namespace in which a missing name takes its default.
  - `study_settings` raises `ValueError` for a study that cannot be solved as written (listed under "Why each refusal").
  - `evidence_dir` also refuses `COM0`, `LPT0`, `COM¹`-`COM³`, `LPT¹`-`LPT³`, `CONIN$`, `CONOUT$`, and names longer than 255 UTF-8 bytes.
- The studio keeps reading the study's names itself. Its Solve reaches `study_settings` through `solve_project`. Plan 6b moves the studio onto the settings together with the new names.

**Why each refusal:** today each of these fails late, if at all.
- **Operations that are not a tuple or list of strings.** A string would be read as one operation per letter.
- **A name that cannot be an evidence folder.** Spec decision 10 gives every operation one folder.
- **Two names sharing a folder,** equal or differing only in case. `solve_project` collapses them into one dict entry, and the second `mkdir` raises `FileExistsError` after the first operation has solved.
- **`SOLVER_OPTIONS` that choose how Code_Aster runs on this machine** (`work_dir`, `exec_method`, `docker_image`, `wsl_distro`, `runner_command`, `bridge_python`, `timeout_seconds`).
  - These are machine choices, outside the solver input identity.
  - A study naming `exec_method="docker"` would make every run it solves unverified.
- **`SOLVER_OPTIONS` the solver rejects.** Today an unknown key raises `TypeError` and a bad value raises `ValueError`, both inside `solve_project`.
- **`VOLUME_EXPORT` keys other than `element_ids`, `max_element_size` and `element_order`, or missing either of the first two.**
  - Today an unknown or missing key raises `TypeError` while computing the identity.
  - An `export_tensor_stress` key passes the identity and then breaks the export with "multiple values" (spec decision 19 keeps that flag out of a study's hands).
- **A `VOLUME_EXPORT` with a `load_path`.**
  - The volume exporter refuses it inside the solve.
  - Freshness counts it as stale forever.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_project_study.py`:

```python
"""A study's settings are checked once, when the study loads (spec decisions 10, 19 and 23)."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from tuba.project import load_project
from tuba.project.study import StudySettings, study_settings

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
VOLUME = {"element_ids": ("pipe_0",), "max_element_size": 0.005}


@pytest.mark.parametrize("script", sorted(EXAMPLES.glob("*/*study.py")), ids=lambda path: f"{path.parent.name}/{path.name}")
def test_every_gallery_study_loads(script):
    study = load_project(script.parent).load_study(script.name)

    assert study_settings(study).operations == tuple(study.LOAD_CASES)


def test_a_missing_study_or_name_takes_its_default():
    assert study_settings(None) == study_settings(SimpleNamespace()) == StudySettings((), {}, None)


def test_the_settings_are_the_study_names():
    beam = SimpleNamespace(LOAD_CASES=["Hot", "Cold"], SOLVER_OPTIONS={"line_segments": 4})
    volume = SimpleNamespace(LOAD_CASES=("Pressure",), SOLVER_OPTIONS={}, VOLUME_EXPORT=VOLUME)

    assert study_settings(beam) == StudySettings(("Hot", "Cold"), {"line_segments": 4}, None)
    assert study_settings(volume) == StudySettings(("Pressure",), {}, VOLUME)


@pytest.mark.parametrize(
    ("names", "error"),
    [
        ({"LOAD_CASES": "Operating"}, "tuple of operation names"),
        ({"LOAD_CASES": ("Operating", 2)}, "tuple of operation names"),
        ({"LOAD_CASES": ("CON",)}, "cannot name an evidence folder"),
        ({"LOAD_CASES": ("Hot", "Hot")}, "twice"),
        ({"LOAD_CASES": ("Hot", "hot")}, "twice"),
        ({"SOLVER_OPTIONS": {"exec_method": "docker"}}, "runs on this machine: exec_method"),
        ({"SOLVER_OPTIONS": {"work_dir": "scratch", "timeout_seconds": 60}}, "runs on this machine: timeout_seconds, work_dir"),
        ({"SOLVER_OPTIONS": {"line_segment": 4}}, "line_segment'"),
        ({"SOLVER_OPTIONS": {"line_segments": 0}}, "line_segments must be a positive integer"),
        ({"VOLUME_EXPORT": {"element_ids": ("pipe_0",)}}, "needs max_element_size"),
        ({"VOLUME_EXPORT": {**VOLUME, "export_tensor_stress": True}}, "cannot set export_tensor_stress"),
        ({"VOLUME_EXPORT": {**VOLUME, "mesh_size": 0.01}}, "cannot set mesh_size"),
        ({"SOLVER_OPTIONS": {"pipe_modelization": "POU_D_T", "load_path": ["Hot", "Cold"]}, "VOLUME_EXPORT": VOLUME}, "load_path"),
    ],
)
def test_a_study_that_cannot_be_solved_as_written_is_refused_when_it_loads(names, error):
    with pytest.raises(ValueError, match=error):
        study_settings(SimpleNamespace(**names))
```

In `tests/test_project_evidence.py`, replace `test_each_operation_has_one_evidence_folder_named_after_it` with:

```python
def test_each_operation_has_one_evidence_folder_named_after_it(tmp_path):
    assert evidence_dir(tmp_path, "Operating") == tmp_path / "evidence" / "Operating"
    assert evidence_dir(tmp_path, "Load case 1") == tmp_path / "evidence" / "Load case 1"
    assert evidence_dir(tmp_path, "x" * 255) == tmp_path / "evidence" / ("x" * 255)
    for name in (
        "", ".", "..", "a/b", "a\\b", "Hot:Cold", "Hot?", "CON", "nul.txt", "Hot ", "Hot.", "tab\there",
        # The rest of Windows' device names, and a name over Linux's limit of 255 bytes (not characters).
        "COM0", "lpt0", "COM¹", "LPT³.log", "CONIN$", "conout$", "é" * 128,
    ):
        with pytest.raises(ValueError, match="cannot name an evidence folder"):
            evidence_dir(tmp_path, name)
```

In `tests/test_project_solve.py`, add after `test_a_study_without_operations_has_nothing_to_solve`:

```python
def test_a_study_naming_one_operation_twice_is_refused_before_the_model_runs(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "model.py").write_text('raise AssertionError("model.py must not run")\n', encoding="utf-8")
    (root / "study.py").write_text('LOAD_CASES = ("Operating", "operating")\n', encoding="utf-8")

    # Both names would share one evidence folder on Windows: nothing runs, is claimed or is written.
    with pytest.raises(ValueError, match="twice"):
        solve_project(load_project(root), solver=_RefuseToSolve())

    assert sorted(path.name for path in root.iterdir()) == ["model.py", "study.py"]
```

In `tests/test_project.py`, add at the end:

```python
def test_the_project_command_refuses_a_study_it_cannot_solve_before_running_the_model(tmp_path, capsys):
    from tests.project_replay import ReplaySolver
    from tuba.project import main

    study = 'LOAD_CASES = ("Operating",)\nSOLVER_OPTIONS = {"exec_method": "docker"}\n'
    project = _project(tmp_path, 'raise AssertionError("model.py must not run")\n', study)

    with pytest.raises(SystemExit) as exited:
        main([str(project), "--output", str(tmp_path / "review")], solver=ReplaySolver(SUPPORT_RACK / "evidence"))

    assert exited.value.code == 2
    assert "study.py: SOLVER_OPTIONS cannot choose how Code_Aster runs on this machine: exec_method" in capsys.readouterr().err
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `PY -m pytest tests/test_project_study.py tests/test_project_evidence.py tests/test_project_solve.py tests/test_project.py -q -p no:cacheprovider`

Expected:
- `tests/test_project_study.py` errors at collection with `ModuleNotFoundError: No module named 'tuba.project.study'`.
- `test_each_operation_has_one_evidence_folder_named_after_it` fails at `"COM0"` with `DID NOT RAISE`.
- The solve test and the CLI test fail with `AssertionError: model.py must not run`.

- [ ] **Step 3: Implement**

Create `tuba/project/study.py`:

```python
"""A study's settings, checked once when the study loads.

A study names the operations it solves (``LOAD_CASES``), how the model compiles (``SOLVER_OPTIONS``) and which
elements a volume study meshes as solids (``VOLUME_EXPORT``). What a solve could only fail on later is refused
here, before the model runs:
- names that cannot each own an evidence folder (spec decision 10);
- options that choose how Code_Aster runs on this machine, or that the solver rejects;
- volume exports the exporter refuses (decision 19: the tensor-stress table is never a study's choice).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tuba.project.evidence import evidence_dir
from tuba.solver.aster import CodeAsterSolver

#: How Code_Aster runs on this machine: not the study's choice, and not part of the solver input identity.
_RUNTIME = frozenset({"work_dir", "exec_method", "docker_image", "wsl_distro", "runner_command", "bridge_python", "timeout_seconds"})
_VOLUME_REQUIRED = ("element_ids", "max_element_size")
_VOLUME = frozenset({*_VOLUME_REQUIRED, "element_order"})


@dataclass(frozen=True)
class StudySettings:
    """A study's validated settings; ``volume_export`` is None for a study of beams and pipes."""

    operations: tuple[str, ...]
    solver_options: dict[str, Any]
    volume_export: dict[str, Any] | None


def study_settings(study: Any) -> StudySettings:
    """The validated settings of *study*, as :meth:`Project.load_study` returns it.

    Without a study, or without one of its names, that setting takes its default. Raises ValueError for a
    study that cannot be solved as written.
    """
    names = getattr(study, "LOAD_CASES", None) or ()
    if not isinstance(names, (tuple, list)) or not all(isinstance(name, str) for name in names):
        raise ValueError(f"LOAD_CASES must be a tuple of operation names, got {names!r}.")
    for name in names:
        evidence_dir(".", name)  # raises for a name that cannot be an evidence folder
    if len({name.casefold() for name in names}) != len(names):
        raise ValueError(f"LOAD_CASES names an operation twice (names differing only in case share a folder): {names!r}.")
    options = dict(getattr(study, "SOLVER_OPTIONS", None) or {})
    if runtime := sorted(_RUNTIME & set(options)):
        raise ValueError(f"SOLVER_OPTIONS cannot choose how Code_Aster runs on this machine: {', '.join(runtime)}.")
    try:
        CodeAsterSolver(**options)
    except (TypeError, ValueError) as exc:  # an unknown option, or a value the solver refuses
        raise ValueError(f"SOLVER_OPTIONS: {exc}") from exc
    volume = dict(getattr(study, "VOLUME_EXPORT", None) or {}) or None
    if volume is not None:
        if unknown := sorted(set(volume) - _VOLUME):
            raise ValueError(f"VOLUME_EXPORT cannot set {', '.join(unknown)}; it takes element_ids, max_element_size and element_order.")
        if missing := [key for key in _VOLUME_REQUIRED if key not in volume]:
            raise ValueError(f"VOLUME_EXPORT needs {' and '.join(missing)}.")
        if options.get("load_path") is not None:
            raise ValueError("VOLUME_EXPORT cannot follow a load_path: native contact load paths need POU_D_T beams.")
    return StudySettings(tuple(names), options, volume)
```

In `tuba/project/evidence.py`:
- replace the `_RESERVED = ...` line with:

  ```python
  # Windows device names, alone or before an extension: no folder can take one.
  _RESERVED = frozenset(
      {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$", *(f"{port}{digit}" for port in ("COM", "LPT") for digit in "0123456789¹²³")}
  )
  ```

- in `evidence_dir`, add `or len(operation.encode("utf-8")) > 255` as the last condition of the `if`;
- end its docstring's rule sentence with "no Windows device name, and no more than 255 UTF-8 bytes (Linux's limit)."

In `tuba/project/solve.py`:
- add `from tuba.project.study import study_settings` after the `tuba.project.freshness` import;
- add a sentence to `solve_project`'s docstring, after the one about *solver*: "A study that cannot be solved as written raises ValueError before the model runs (:func:`tuba.project.study.study_settings`).";
- replace these lines:

  ```python
      study = project.load_study(study_file)
      operations = tuple(getattr(study, "LOAD_CASES", None) or ())
      if not operations:
          raise ValueError(f"{project.name} has no study operations to solve.")
      namespace = project.run_model() if namespace is None else namespace
      model = namespace["model"]
      options = dict(getattr(study, "SOLVER_OPTIONS", None) or {})
      volume_export = getattr(study, "VOLUME_EXPORT", None) or None
      folders = {operation: evidence_dir(project.root, operation) for operation in operations}
      exporter = CodeAsterSolver(**options)  # options the solver rejects raise here, before anything is claimed
  ```

  with:

  ```python
      study = project.load_study(study_file)
      settings = study_settings(study)
      operations, options, volume_export = settings.operations, settings.solver_options, settings.volume_export
      if not operations:
          raise ValueError(f"{project.name} has no study operations to solve.")
      namespace = project.run_model() if namespace is None else namespace
      model = namespace["model"]
      folders = {operation: evidence_dir(project.root, operation) for operation in operations}
      exporter = CodeAsterSolver(**options)
  ```

In `tuba/project/__init__.py`'s `main`, replace:

```python
    namespace = project.run_model()
    artifact_dir = args.artifact_dir
    operations = tuple(getattr(study, "LOAD_CASES", None) or ())
```

with:

```python
    from tuba.project.study import study_settings

    try:
        operations = study_settings(study).operations
    except ValueError as exc:
        parser.error(f"{args.study}: {exc}")
    namespace = project.run_model()
    artifact_dir = args.artifact_dir
```

- [ ] **Step 4: Run the covering tests**

Run: `PY -m pytest tests/test_project_study.py tests/test_project_evidence.py tests/test_project_solve.py tests/test_project.py tests/test_project_freshness.py tests/test_studio_project.py -q -p no:cacheprovider`

Expected: PASS.

- [ ] **Step 5: Run the full suite**

Run `PY -m pytest -q -p no:cacheprovider` in the background, with bounded waits; commit only after it finishes.

Expected: no failures other than the two known vite tests.

- [ ] **Step 6: Commit**

```bash
git add tuba/project/study.py tuba/project/evidence.py tuba/project/solve.py tuba/project/__init__.py tests/test_project_study.py tests/test_project_evidence.py tests/test_project_solve.py tests/test_project.py
git commit -m "feat(project): check a study's settings once, when it loads

study_settings reads a study's operations, solver options and volume
export, and refuses what a solve could only fail on later: names that
cannot each own an evidence folder, options that choose how Code_Aster
runs or that the solver rejects, and volume exports the exporter refuses.
Project solves and the project command read their settings through it,
and evidence_dir refuses the remaining Windows device names and names
longer than 255 bytes."
```

---

### Task 3: The Pages validator finds each run's attestation through its provenance

**Files:**
- Modify: `scripts/build_pages.py:9` (import), `:336-355` (the profiles with results), `:390-394` (beam), `:587-593` (`_validate_execution_attestation`)
- Modify: `tests/test_official_viewer_publication.py` (one new test after `test_engineering_profile_cross_checks_attestation_identity`, `:488-497`)

**Interfaces:**
- Consumes: nothing from Tasks 1 and 2.
- Produces: `_validate_execution_attestation(root, identity, result) -> str`.
  - *result* is a bundle's result-state provenance record.
  - It checks the attestation in the folder holding the file that `result["files"]["execution"]` names.
  - It returns that folder's bundle URI (`"artifacts"`, or `"artifacts/<operation>"`).
- Every profile with results reads its attestation this way. The contact profile reads `study_contact.json` from the same folder, whose attestation covers that file (the inventory includes it whenever it is present).
- `_validate_embedded_portability` (`:596-599`) still requires an `artifacts/` directory, and both layouts have one.
- **Why now:** spec decision 14 stages every operation into `artifacts/<operation>/`. Plan 6b moves the bundles, so the validator must accept both layouts first. The beam profile already finds its folders this way (`:390-394`); every other profile assumes `artifacts/` (`:338`, `:588`).
- **Coverage of the flat layout:**
  - `test_pages_catalog_contains_the_validated_official_bundles` builds and validates every Pages bundle, including the contact gallery (`native-friction-review`) and the volume one;
  - `test_beam_comparison_validates_each_load_case_evidence` covers the beam profile's per-operation folders.

- [ ] **Step 1: Write the failing test**

In `tests/test_official_viewer_publication.py`, add after `test_engineering_profile_cross_checks_attestation_identity`:

```python
def test_engineering_profile_reads_the_attestation_in_the_folder_its_result_names(tmp_path: Path) -> None:
    """Catches a validator that assumes a flat artifacts/ folder (spec decision 14 stages artifacts/<operation>/)."""
    _write_engineering_bundle(tmp_path, evidence=True)
    flat, operation = tmp_path / "artifacts", tmp_path / "artifacts" / "Operating"
    operation.mkdir()
    for path in [path for path in flat.iterdir() if path.is_file()]:
        path.rename(operation / path.name)
    scene, review = _scene(tmp_path), _review(tmp_path)
    for record in review["provenance"]:
        record["files"] = {role: uri.replace("artifacts/", "artifacts/Operating/") for role, uri in record["files"].items()}
    _save_bundle(tmp_path, scene, review)

    validate_official_bundle(tmp_path, "engineering-review")

    # A valid flat copy does not stand in for the run the result names.
    for path in operation.iterdir():
        (flat / path.name).write_bytes(path.read_bytes())
    execution = json.loads((operation / "study_execution.json").read_text(encoding="utf-8"))
    execution["solver_input_identity"]["fingerprint"] = "b" * 64
    (operation / "study_execution.json").write_text(json.dumps(execution), encoding="utf-8")
    with pytest.raises(ValueError, match="identity"):
        validate_official_bundle(tmp_path, "engineering-review")
```

- [ ] **Step 2: Run the test to see it fail**

Run: `PY -m pytest tests/test_official_viewer_publication.py -q -p no:cacheprovider -k folder_its_result_names`

Expected: FAIL at the first `validate_official_bundle` with `ValueError: Engineering-review bundles require a validated Code_Aster execution attestation.`, because the validator looks in `artifacts/`.

- [ ] **Step 3: Implement**

In `scripts/build_pages.py`, add `import posixpath` after `import os`.

Replace `_validate_execution_attestation` with:

```python
def _validate_execution_attestation(root: Path, identity: dict[str, Any], result: dict[str, Any]) -> str:
    """Check the attestation beside *result*'s execution envelope against *identity*; return that folder's URI.

    The folder is the one the envelope's reference names, so a run staged in ``artifacts/`` and runs staged in
    ``artifacts/<operation>/`` (spec decision 14) validate alike.
    """
    files = result.get("files")
    execution_uri = files.get("execution") if isinstance(files, dict) else None
    if not isinstance(execution_uri, str):
        raise ValueError("Engineering-review result requires its execution envelope.")
    attestation = load_code_aster_execution_attestation(_bundle_path(root, execution_uri).parent)
    if attestation is None:
        raise ValueError("Engineering-review bundles require a validated Code_Aster execution attestation.")
    if attestation["solver_input_identity"] != identity:
        raise ValueError("Engineering-review execution attestation identity must match provenance.")
    return posixpath.dirname(execution_uri)
```

In `_validate_beam_review`, replace:

```python
        execution_uri = by_kind["result_state"].get("files", {}).get("execution")
        if not isinstance(execution_uri, str):
            raise ValueError("Beam result requires its execution envelope.")
        artifacts = _bundle_path(root, execution_uri).parent
        _validate_execution_attestation(root, reference, artifacts_root=artifacts)
```

with:

```python
        _validate_execution_attestation(root, reference, by_kind["result_state"])
```

In `validate_official_bundle`, replace:

```python
    if profile == "contact-engineering-review":
        _validate_contact_result_fields(scene)
        raw_contacts = json.loads(_bundle_path(root, "artifacts/study_contact.json").read_text(encoding="utf-8"))
        solved_steps = {(row["support_id"], row["instant"]) for row in raw_contacts}
        displayed_steps = {
            (support_id, overlay["data"]["metadata"]["pseudo_time"])
            for overlay in scene["overlays"] if overlay.get("kind") == "result_state"
            for support_id in overlay["data"]["contact_results"]
        }
        if solved_steps != displayed_steps:
            raise ValueError("Contact review must display every attested shoe increment.")
    elif profile == "beam-engineering-review":
        _validate_beam_review(root, scene, review)
    else:
        _validate_engineering_result_fields(scene, volume=profile == "volume-engineering-review")
    if profile != "beam-engineering-review":
        identity = _validate_engineering_provenance(scene, review)
        _validate_execution_attestation(root, identity)
        if profile == "contact-engineering-review":
            _validate_contact_provenance(scene, review, identity)
```

with:

```python
    if profile == "contact-engineering-review":
        _validate_contact_result_fields(scene)
    elif profile == "beam-engineering-review":
        _validate_beam_review(root, scene, review)
    else:
        _validate_engineering_result_fields(scene, volume=profile == "volume-engineering-review")
    if profile != "beam-engineering-review":
        identity = _validate_engineering_provenance(scene, review)
        result = next(record for record in review["provenance"] if isinstance(record, dict) and record.get("kind") == "result_state")
        evidence = _validate_execution_attestation(root, identity, result)
        if profile == "contact-engineering-review":
            contacts = _bundle_path(root, posixpath.join(evidence, "study_contact.json"))
            solved_steps = {(row["support_id"], row["instant"]) for row in json.loads(contacts.read_text(encoding="utf-8"))}
            displayed_steps = {
                (support_id, overlay["data"]["metadata"]["pseudo_time"])
                for overlay in scene["overlays"] if overlay.get("kind") == "result_state"
                for support_id in overlay["data"]["contact_results"]
            }
            if solved_steps != displayed_steps:
                raise ValueError("Contact review must display every attested shoe increment.")
            _validate_contact_provenance(scene, review, identity)
```

- `_validate_engineering_provenance` has already required exactly one result-state record, so `next(...)` always finds it.
- The contact increments are now compared after the attestation is checked, so they are read from attested evidence.

- [ ] **Step 4: Run the covering tests**

Run: `PY -m pytest tests/test_official_viewer_publication.py -q -p no:cacheprovider`

Expected: PASS. That file holds every test of the validator, including the Pages catalog build.

- [ ] **Step 5: Run the full suite**

Run `PY -m pytest -q -p no:cacheprovider` in the background, with bounded waits; commit only after it finishes.

Expected: no failures other than the two known vite tests.

- [ ] **Step 6: Commit**

```bash
git add scripts/build_pages.py tests/test_official_viewer_publication.py
git commit -m "feat(pages): validate each run's attestation where its provenance puts it

Every profile with results now reads its attestation from the folder its
result's execution envelope names, as the beam profile already did, and
the contact profile reads study_contact.json from that folder. A bundle
staged under artifacts/<operation>/ validates like a flat one."
```
