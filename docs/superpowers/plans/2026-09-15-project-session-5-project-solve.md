# Project and Authoring Session, Plan 5: Project Solve

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One project solve brings a project's evidence up to date. It reuses evidence that still attests the current model and study, solves the rest through a solver port, runs the study's check, and then promotes every operation into `evidence/<operation>/`, or none. It runs under a claim that other processes respect. The studio's Solve and `python -m tuba.project` call it.

**Architecture:**
- `tuba/project/evidence.py` names evidence folders and promotes staged solves (decision 12).
- `tuba/project/claim.py` holds `<project>/.tuba/solve.lock` (decision 20).
- `tuba/project/solve.py` has the `Solver` port and `solve_project` (decisions 11, 13, 18). A solve:
  1. reuses evidence unless forced;
  2. exports the rest into `<project>/.tuba/staging/<operation>/` and solves each through the port;
  3. runs the study's `check`;
  4. promotes the new evidence and reports unverified operations.
- `CodeAsterSolver` is the production adapter. `tests/project_replay.py` is the test adapter: it replays committed real evidence.
- Publication stays strict: unverified runs are written and reported, and no builder accepts them. The `result_states=` review path now checks trust as well.
- The studio's Solve and the CLI call `solve_project`, then build the review from the project's evidence.

**Tech Stack:** Python 3.12, pytest, standard library only.

**Spec:** `docs/superpowers/specs/2026-09-13-project-authoring-session-design.md`: decisions 11–13, 18 and 20, the Interface and Testing sections, and roadmap step 5.

## Global Constraints

- **Worktree:** execute in `D:/tmp/tuba-plan5` on branch `project-session/5-project-solve` (created from `main` at `9745229`).
  - Never commit in `D:/Gitprojects/Tuba_v4`: another session works there.
  - Never `git stash` (the stash stack is shared) and never `git pull`.
- **Python:** the worktree has no `.venv`. Run tests with the main repo's interpreter from the worktree root, as a module, so the worktree's `tuba` is imported first: `D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest <args>` (written `PY -m pytest` below).
- **Known worktree failures:** two tests in `tests/test_package_release.py` fail in a fresh worktree with "'vite' is not recognized" (no `viewer/node_modules`); ignore them. The suite on `9745229`: 1091 passed / 34 skipped / 151 subtests / 1 pre-existing zmq warning, plus those two.
- **Line numbers** cite the files at `9745229`. Earlier tasks shift them, so locate code by the quoted text.
- **Committed evidence is frozen.**
  - Never write under `examples/*/evidence/` or `notebooks/code_aster_results/`, and never run Code_Aster.
  - Tests copy projects and their evidence into temporary folders.
  - `build_solver_input_identity` and every `compiler_inputs` dict stay exactly as they are.
- **No fabricated results:** project solves are tested through `tests/project_replay.py`, which copies committed real evidence whose attested identity matches the export. The one allowed alteration is relabelling a copied attestation's `execution_method` as `"docker"`, to test unverified runs.
- **Files not to edit:** `tuba/model.py`, `tuba/analysis/provenance.py` and `tuba/reporting/tables.py`. Another session's stashed work touches them.
- **Publication stays strict:** unverified runs are written and reported, and no builder accepts them in this plan.
- **Also:** no new dependencies, no compatibility shims (ADR 0001), and no commit trailer.
- **Out of scope:**
  - the gallery refresh, gallery records, and the Pages producer and validator (Plan 6);
  - the study contract beyond an optional `check(solved)`: `OPERATIONS`, `SOLVER_OPTIONS` absorbing `VOLUME_EXPORT`, `review(ctx)`, and retiring `LOAD_CASES`, `ARTIFACT_DIR` and `build_review` (Plan 6);
  - staging evidence into review bundles (decision 14) and removing `--artifact-dir` (Plan 6);
  - relaxing the builders and the viewer's unverified marker (Plan 6), and renaming `allow_unverified` (Plan 6);
  - the three copies of the volume `load_path` refusal in `tuba/solver/aster.py` (Plan 6);
  - a "Solve again" button, `open_session`, session state, `sync()` and MCP `solve_model` (Plan 7);
  - `CodeAsterSolver._attested_solve_matches`, which stays for direct `TubaModel.solve` users;
  - the notebook loader `load_or_run_code_aster_results`.

---

### Task 1: Reviews check trust on every path

**Files:**
- Modify: `tuba/reporting/builder.py:265-269`
- Modify: `tuba/solver/code_aster_runtime.py:15` and `:433`
- Modify: `tuba/project/freshness.py:10-16` and `:75`
- Modify: `tests/test_reporting_builder.py` (the fixture at `:67-70`, plus one test)
- Modify: `tests/test_reporting_compliance.py:52` and `tests/test_reporting_export.py:61`
- Modify: `docs/content/setup.md:157` and `:161`
- Modify: `docs/superpowers/plans/2026-09-14-project-session-4-freshness-and-trust.md:1001`

**Interfaces:**
- Produces: `tuba.solver.code_aster_runtime.execution_trust(attestation) -> Literal["verified", "unverified"]`.
- Produces: `build_engineering_review(result_states=...)` refuses any result state whose `result_trust` is not `"verified"`, with the existing message "requires a verified Code_Aster solve attestation".
  - Before this task it checked only that `solve_attestation` is a dict, so a Docker-executed run passed.
  - Imported runs always carry `result_trust`, which `import_code_aster_artifacts` sets.

- [ ] **Step 1: Write the failing test**

In `tests/test_reporting_builder.py`, add this test right after `test_unverified_result_state_cannot_build_engineering_review`:

```python
def test_a_docker_attested_result_state_cannot_build_engineering_review(
    review_model, code_aster_study, code_aster_result_state
):
    docker = replace(
        code_aster_result_state,
        metadata={
            **code_aster_result_state.metadata,
            "result_trust": "unverified",
            "solve_attestation": {"execution_method": "docker"},
        },
    )

    with pytest.raises(EngineeringReviewError, match="verified Code_Aster solve attestation"):
        build_engineering_review(review_model, studies=[code_aster_study], result_states=[docker])
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `PY -m pytest tests/test_reporting_builder.py::test_a_docker_attested_result_state_cannot_build_engineering_review -q`

Expected: FAIL with `DID NOT RAISE`.

- [ ] **Step 3: Implement the check and update the fixtures that stand for imported runs**

In `tuba/reporting/builder.py`, replace:

```python
        if not isinstance(state.metadata.get("solve_attestation"), dict):
```

with:

```python
        if (
            not isinstance(state.metadata.get("solve_attestation"), dict)
            or state.metadata.get("result_trust") != "verified"
        ):
```

The raise beneath it stays as it is.

These fixtures build reviews through `result_states=` and stand for imported, verified runs, which always carry `result_trust`. Add `"result_trust": "verified"` beside their `solve_attestation`:
- `tests/test_reporting_builder.py`, fixture `code_aster_result_state`: the metadata becomes

  ```python
          metadata={
              "parser_diagnostics": ["SIEQ table omitted one optional component."],
              "result_trust": "verified",
              "solve_attestation": {"fixture": "validated Code_Aster solve"},
          },
  ```

- `tests/test_reporting_compliance.py:52`: `metadata={"result_trust": "verified", "solve_attestation": {"fixture": "validated Code_Aster solve"}},`
- `tests/test_reporting_export.py:61`: the same line.

In `tuba/solver/code_aster_runtime.py`:
- change `from typing import Any, Mapping, Sequence` to `from typing import Any, Literal, Mapping, Sequence`;
- change `def execution_trust(attestation: Mapping[str, Any] | None) -> str:` to `def execution_trust(attestation: Mapping[str, Any] | None) -> Literal["verified", "unverified"]:`.

In `tuba/project/freshness.py`:
- change `from typing import Any` to `from typing import TYPE_CHECKING, Any`;
- add this after the imports:

  ```python
  if TYPE_CHECKING:
      from tuba.solver.aster import CodeAsterSolver
  ```

- replace the one-line `def _identity(solver: Any, model: TubaModel, operation: str, volume_export: Mapping[str, Any] | None) -> SolverInputIdentity:` with:

  ```python
  def _identity(
      solver: CodeAsterSolver,
      model: TubaModel,
      operation: str,
      volume_export: Mapping[str, Any] | None,
  ) -> SolverInputIdentity:
  ```

In `docs/content/setup.md`:
- replace the `TUBA_CODE_ASTER_DOCKER_IMAGE` row with `| `TUBA_CODE_ASTER_DOCKER_IMAGE` | Advanced fallback image; a run through it is always unverified |`;
- replace the paragraph starting "A Code_Aster run executed through Docker" with:

  ```markdown
  A Code_Aster run executed through Docker is always unverified: an engineering review refuses its results, and so does a scene built from analysis runs. A mutable or placeholder image name is not a production dependency.
  ```

In `docs/superpowers/plans/2026-09-14-project-session-4-freshness-and-trust.md:1001`, the sentence wrongly lists `_publish_scene`, which runs inside `_run_script`'s error handling. Change it to:

```markdown
  - `review_stale` runs outside error handling in the `else:` branches of `_prepare_review` and `_solve`. An unexpected exception there ends the thread without an event.
```

- [ ] **Step 4: Run the covering tests**

Run: `PY -m pytest tests/test_reporting_builder.py tests/test_reporting_compliance.py tests/test_reporting_export.py tests/test_solver_input_provenance.py tests/test_code_aster_runtime.py tests/test_code_aster_artifact_import.py tests/test_project_freshness.py tests/test_visualization_results.py -q -p no:cacheprovider`

Expected: PASS. The provenance tests at `tests/test_solver_input_provenance.py:238` and `:420` still fail on their identity errors, which the builder raises before the trust check.

- [ ] **Step 5: Run the full suite**

Run `PY -m pytest -q -p no:cacheprovider` in the background, with bounded waits; commit only after it finishes.

Expected: no failures other than the two known vite tests.

- [ ] **Step 6: Commit**

```bash
git add tuba/reporting/builder.py tuba/solver/code_aster_runtime.py tuba/project/freshness.py tests/test_reporting_builder.py tests/test_reporting_compliance.py tests/test_reporting_export.py docs/content/setup.md docs/superpowers/plans/2026-09-14-project-session-4-freshness-and-trust.md
git commit -m "fix(reporting): refuse unverified result states on every review path

A result state passed straight to build_engineering_review needed only an
attestation, so a Docker-executed run could enter a review. It now needs
result_trust == 'verified', like analysis runs. execution_trust returns a
Literal, and the setup page says what an unverified run can reach."
```

---

### Task 2: Evidence folders, and promotion that lands all operations or none

**Files:**
- Create: `tuba/project/evidence.py`
- Create: `tests/test_project_evidence.py`

**Interfaces:**
- Produces: `tuba.project.evidence.evidence_dir(project_root: str | Path, operation: str) -> Path`.
  - It returns `<project>/evidence/<operation>`.
  - It raises `ValueError("Operation ... cannot name an evidence folder.")` for a name that cannot be a single folder name on both Windows and Linux.
- Produces: `tuba.project.evidence.promote_evidence(moves: Mapping[Path, Path]) -> None`. It moves each staged folder (the key) into its evidence folder (the value):
  1. it checks every staged attestation first;
  2. it removes the old attestations;
  3. it moves in the attested files and removes any other file in the evidence folder;
  4. it puts `study_execution.json` in place last.
- Produces: the constants `EVIDENCE = "evidence"` and `ATTESTATION = "study_execution.json"`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_project_evidence.py`:

```python
"""Evidence folders, and how a solve lands in them (spec decisions 10 and 12)."""

import os
import shutil
from pathlib import Path

import pytest

from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts
from tuba.project import evidence, load_project
from tuba.project.evidence import evidence_dir, promote_evidence
from tuba.solver.code_aster_runtime import load_code_aster_execution_attestation

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
RACK = EXAMPLES / "support-rack-review" / "evidence" / "Operating"
PROFILE = EXAMPLES / "profile-orientation-review" / "evidence"


def _files(folder: Path) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in folder.iterdir() if path.is_file()}


def test_each_operation_has_one_evidence_folder_named_after_it(tmp_path):
    assert evidence_dir(tmp_path, "Operating") == tmp_path / "evidence" / "Operating"
    assert evidence_dir(tmp_path, "Load case 1") == tmp_path / "evidence" / "Load case 1"
    for name in ("", ".", "..", "a/b", "a\\b", "Hot:Cold", "Hot?", "CON", "nul.txt", "Hot ", "Hot.", "tab\there"):
        with pytest.raises(ValueError, match="cannot name an evidence folder"):
            evidence_dir(tmp_path, name)


def test_promotion_keeps_only_attested_files_and_lands_the_attestation_last(tmp_path, monkeypatch):
    staged, target = tmp_path / "staged", tmp_path / "evidence" / "Operating"
    shutil.copytree(RACK, staged)
    target.mkdir(parents=True)
    shutil.copy2(RACK / "study_execution.json", target / "study_execution.json")
    (target / "study_sigm.csv").write_text("left by an older solve", encoding="utf-8")
    attested = set(load_code_aster_execution_attestation(RACK)["artifacts"])
    moved = []
    real_replace = os.replace

    def replace(source, destination):
        moved.append(Path(destination).name)
        real_replace(source, destination)

    monkeypatch.setattr(evidence.os, "replace", replace)

    promote_evidence({staged: target})

    assert moved[-1] == "study_execution.json"
    assert sorted(moved[:-1]) == sorted(attested)
    # The committed folder's unattested study.resu stays behind, and the stale table is gone.
    assert set(_files(target)) == attested | {"study_execution.json"}
    assert all((target / name).read_bytes() == (RACK / name).read_bytes() for name in attested)
    model = load_project(EXAMPLES / "support-rack-review").run_model()["model"]
    run = import_code_aster_artifacts(model=model, work_dir=target)
    assert run.result_state.metadata["result_trust"] == "verified"


def test_one_damaged_operation_promotes_none(tmp_path):
    moves = {}
    for case in ("global", "local"):
        staged, target = tmp_path / "staged" / case, tmp_path / "evidence" / case
        shutil.copytree(PROFILE / case, staged)
        shutil.copytree(PROFILE / case, target)
        moves[staged] = target
    (tmp_path / "staged" / "local" / "study.mess").write_text("damaged", encoding="utf-8")
    before = {target: _files(target) for target in moves.values()}

    with pytest.raises(ValueError, match="does not match"):
        promote_evidence(moves)

    assert {target: _files(target) for target in moves.values()} == before
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PY -m pytest tests/test_project_evidence.py -q -p no:cacheprovider`

Expected: collection error `ImportError: cannot import name 'evidence' from 'tuba.project'`.

- [ ] **Step 3: Implement the module**

Create `tuba/project/evidence.py`:

```python
"""Evidence folders: where a project's solved operations live, and how a solve lands there.

Spec decision 10: one folder per operation, ``<project>/evidence/<operation>/``. Decision 12: a solve
promotes its files first and ``study_execution.json`` last, and lands all of its operations or none.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from tuba.solver.code_aster_runtime import load_code_aster_execution_attestation

EVIDENCE = "evidence"
ATTESTATION = "study_execution.json"
_UNSAFE = frozenset('<>:"/\\|?*')
_RESERVED = frozenset({"CON", "PRN", "AUX", "NUL", *(f"COM{n}" for n in range(1, 10)), *(f"LPT{n}" for n in range(1, 10))})


def evidence_dir(project_root: str | Path, operation: str) -> Path:
    """``<project>/evidence/<operation>/``, refusing an operation name that cannot be one folder name.

    The rule is what Windows and Linux both accept: no separator or reserved character, no control
    character, no trailing space or dot, and no Windows device name.
    """
    if (
        not operation
        or operation[-1] in " ."
        or any(character in _UNSAFE or ord(character) < 32 for character in operation)
        or operation.split(".")[0].upper() in _RESERVED
    ):
        raise ValueError(f"Operation {operation!r} cannot name an evidence folder.")
    return Path(project_root) / EVIDENCE / operation


def promote_evidence(moves: Mapping[Path, Path]) -> None:
    """Move solved operations from their staging folders (keys) into their evidence folders (values).

    Every staged attestation is integrity-checked before anything moves, so one bad operation promotes
    none. Then the old attestations go, the attested files move in, every other file in an evidence
    folder is removed, and the new attestations land last. A folder is evidence only while it has an
    attestation: an interruption leaves operations unsolved, never new files under an old attestation.
    """
    inventories = {}
    for staged in moves:
        attestation = load_code_aster_execution_attestation(staged)
        if attestation is None:
            raise ValueError(f"{staged} holds no solve attestation to promote.")
        inventories[staged] = tuple(attestation["artifacts"])
    for target in moves.values():
        target.mkdir(parents=True, exist_ok=True)
        (target / ATTESTATION).unlink(missing_ok=True)
    for staged, target in moves.items():
        for name in inventories[staged]:
            os.replace(staged / name, target / name)
        for path in target.iterdir():
            if path.is_file() and path.name not in inventories[staged]:
                path.unlink()
    # ponytail: the attestations land one after another, so an interruption between two leaves the
    # later operations unsolved; a journal would make the set atomic if that ever matters.
    for staged, target in moves.items():
        os.replace(staged / ATTESTATION, target / ATTESTATION)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PY -m pytest tests/test_project_evidence.py tests/test_project.py -q -p no:cacheprovider`

Expected: PASS. No full suite: this task only adds a module and its tests.

- [ ] **Step 5: Commit**

```bash
git add tuba/project/evidence.py tests/test_project_evidence.py
git commit -m "feat(project): name evidence folders and promote a solve all or nothing

Spec decisions 10 and 12. An operation's evidence lives in
evidence/<operation>/, and names that cannot be a folder are refused.
Promotion checks every staged attestation first, keeps only attested files,
and lands study_execution.json last."
```

---

### Task 3: The solve claim

**Files:**
- Create: `tuba/project/claim.py`
- Create: `tests/test_project_claim.py`

**Interfaces:**
- Produces: `tuba.project.claim.claim_solve(project_root, *, heartbeat_s=15.0, stale_after_s=60.0)`, a context manager.
  - It holds `<project>/.tuba/solve.lock` for the block, creating `.tuba/.gitignore` with `*` on first use.
  - It raises `SolveBusy("<name> is already being solved.")` while a live solve holds the claim.
  - It breaks a claim nobody has touched for `stale_after_s`.
- Produces: `tuba.project.claim.solve_claimed(project_root, *, stale_after_s=60.0) -> bool`.
- Produces: `class SolveBusy(RuntimeError)`.
- The claim creates nothing until a solve starts, so a studio that opens a project leaves the folder as it was (`tests/test_studio_project.py:93`).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_project_claim.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PY -m pytest tests/test_project_claim.py -q -p no:cacheprovider`

Expected: collection error `ModuleNotFoundError: No module named 'tuba.project.claim'`.

- [ ] **Step 3: Implement the claim**

Create `tuba/project/claim.py`:

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PY -m pytest tests/test_project_claim.py -q -p no:cacheprovider`

Expected: PASS. No full suite: this task only adds a module and its tests.

- [ ] **Step 5: Commit**

```bash
git add tuba/project/claim.py tests/test_project_claim.py
git commit -m "feat(project): claim a project's solve across processes

Spec decision 20. A solve holds .tuba/solve.lock, created atomically and
touched by a heartbeat. Another solve of the same folder is busy, and a
claim untouched for a minute belonged to a crashed solve and is broken."
```

---

### Task 4: The solver port, and a project solve that reuses unless forced

**Files:**
- Create: `tuba/project/solve.py`
- Create: `tests/project_replay.py`
- Create: `tests/test_project_solve.py`

**Interfaces:**
- Consumes: from Task 2, `evidence_dir` and `promote_evidence`; from Task 3, `claim_solve`; from `tuba/project/freshness.py`, `expected_identity(model, operation, *, solver_options, volume_export)`.
- Produces: `tuba.project.solve.Solver`, a `Protocol` with `solve_exported_study(model, study) -> AnalysisRun`.
  - It solves the study exported in `study.work_dir` and returns the run imported from that folder.
  - `CodeAsterSolver` already satisfies it.
- Produces: `tuba.project.solve.ProjectSolve`, a frozen dataclass:
  - `runs: dict[str, AnalysisRun]` holds every operation's run, imported from its evidence folder;
  - `solved`, `reused` and `unverified` are `tuple[str, ...]`, in study order.
- Produces: `tuba.project.solve.solve_project(project, namespace=None, *, study_file="study.py", force=False, solver=None) -> ProjectSolve`.
  - `study_file` picks the study, as `Project.load_study` does. The tee project also has `mesh_study.py`.
  - The operations are the study's `LOAD_CASES`, and the options are its `SOLVER_OPTIONS` and `VOLUME_EXPORT`.
  - It raises `ValueError("<name> has no study operations to solve.")` without them, and `SolveBusy` while another solve holds the claim.
  - A failed solve writes nothing to `evidence/`.
- Produces: `tests.project_replay.ReplaySolver(*evidence_roots, execution_method=None)`, whose `.solved` lists the operations it was asked to solve.
- The solve exports with `CodeAsterSolver(**SOLVER_OPTIONS)`, the compiler options, into a fresh staging folder. The production port is that same solver, so its per-folder reuse probe never hits there.

- [ ] **Step 1: Write the replay adapter and the failing tests**

Create `tests/project_replay.py`:

```python
"""A solver port for tests that replays committed real Code_Aster evidence (spec Testing).

No result is made up. The replay answers an exported study with the committed run that attests exactly
its solver input, and the import re-hashes every attested file, so an export that drifted from that run
fails loudly.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts


class ReplaySolver:
    """Solve by copying the committed run whose attested solver input identity matches the study.

    *evidence_roots* are searched for ``study_execution.json``. *execution_method*, when given, relabels
    the copied attestation, so ``"docker"`` turns real results into an unverified run. ``solved`` lists
    the operations this solver was asked to solve.
    """

    def __init__(self, *evidence_roots: Path, execution_method: str | None = None) -> None:
        self.runs = [path.parent for root in evidence_roots for path in sorted(Path(root).rglob("study_execution.json"))]
        self.execution_method = execution_method
        self.solved: list[str] = []

    def solve_exported_study(self, model, study):
        work = Path(study.work_dir)
        identity = study.solver_input_identity.to_dict()
        for folder in self.runs:
            attestation = json.loads((folder / "study_execution.json").read_text(encoding="utf-8"))
            if attestation["solver_input_identity"] != identity:
                continue
            for name in attestation["artifacts"]:
                if not (work / name).exists():
                    shutil.copy2(folder / name, work / name)
            if self.execution_method is None:
                shutil.copy2(folder / "study_execution.json", work / "study_execution.json")
            else:
                attestation["execution_method"] = self.execution_method
                (work / "study_execution.json").write_text(json.dumps(attestation, indent=2, sort_keys=True), encoding="utf-8")
            self.solved.append(study.load_case)
            return import_code_aster_artifacts(model=model, work_dir=work, study=study)
        raise LookupError(f"No committed evidence attests solver input {identity['fingerprint']}.")
```

Create `tests/test_project_solve.py`:

```python
"""Project solve: reuse, force, staging and promotion through the solver port (spec decisions 11-13, 18, 20)."""

import json
import shutil
from pathlib import Path

import pytest

from tests.project_replay import ReplaySolver
from tuba.project import load_project
from tuba.project.claim import SolveBusy, claim_solve, solve_claimed
from tuba.project.solve import solve_project
from tuba.solver.code_aster_runtime import load_code_aster_execution_attestation

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
RACK = EXAMPLES / "support-rack-review"
PROFILE = EXAMPLES / "profile-orientation-review"
VOLUME_MODEL = """from tuba import Model

model = Model("ProjectVolume")
model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0)
model.add_pipe_section("Pipe", OD=0.1, WT=0.01)
n0 = model.add_node([0.0, 0.0, 0.0])
n1 = model.add_node([0.2, 0.0, 0.0])
model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="Pipe", material="Steel")
model.add_support(n0, type="anchor")
model.define_load_case("Pressure", gravity=False, pressure=1.0e6)
"""
VOLUME_STUDY = """LOAD_CASES = ("Pressure",)
SOLVER_OPTIONS = {}
VOLUME_EXPORT = {"element_ids": ("pipe_0",), "max_element_size": 0.005}
"""


def _copy(tmp_path: Path, source: Path, *, evidence: bool = True):
    """A project copied into *tmp_path*, with or without its committed evidence."""
    root = tmp_path / source.name
    shutil.copytree(source, root, ignore=None if evidence else shutil.ignore_patterns("evidence"))
    return load_project(root)


def _files(folder: Path) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in folder.iterdir() if path.is_file()}


class _Exported(Exception):
    pass


class _RefuseToSolve:
    def solve_exported_study(self, model, study):
        raise _Exported(study)


def test_a_solve_lands_the_evidence_a_real_run_attested(tmp_path):
    project = _copy(tmp_path, RACK, evidence=False)
    solver = ReplaySolver(RACK / "evidence")

    outcome = solve_project(project, solver=solver)

    assert (outcome.solved, outcome.reused, outcome.unverified) == (("Operating",), (), ())
    assert solver.solved == ["Operating"]
    landed = project.root / "evidence" / "Operating"
    committed = RACK / "evidence" / "Operating"
    attested = load_code_aster_execution_attestation(committed)["artifacts"]
    assert set(_files(landed)) == {*attested, "study_execution.json"}
    assert all((landed / name).read_bytes() == (committed / name).read_bytes() for name in attested)
    run = outcome.runs["Operating"]
    assert run.result_state.metadata["result_trust"] == "verified"
    assert Path(run.study.work_dir).resolve() == landed.resolve()
    assert not (project.root / ".tuba" / "staging").exists()
    assert not solve_claimed(project.root)


def test_matching_evidence_is_reused_and_force_solves_again(tmp_path):
    project = _copy(tmp_path, RACK)
    solver = ReplaySolver(RACK / "evidence")

    reused = solve_project(project, solver=solver)
    assert (reused.solved, reused.reused, solver.solved) == ((), ("Operating",), [])
    assert reused.runs["Operating"].result_state.metadata["result_trust"] == "verified"

    forced = solve_project(project, solver=solver, force=True)
    assert (forced.solved, forced.reused, solver.solved) == (("Operating",), (), ["Operating"])


@pytest.mark.parametrize(
    ("script", "old", "new"),
    [
        ("model.py", "(-2.0, -1.0, 3.0)", "(-2.5, -1.0, 3.0)"),
        ("study.py", "SOLVER_OPTIONS: dict = {}", 'SOLVER_OPTIONS: dict = {"line_segments": 4}'),
    ],
)
def test_a_changed_model_or_study_solves_again_and_a_failed_solve_writes_nothing(tmp_path, script, old, new):
    project = _copy(tmp_path, RACK)
    path = project.root / script
    path.write_text(path.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")
    before = _files(project.root / "evidence" / "Operating")

    # No committed run attests the changed input, so the replay refuses: the solve was attempted, and it failed.
    with pytest.raises(LookupError, match="No committed evidence"):
        solve_project(project, solver=ReplaySolver(RACK / "evidence"))

    assert _files(project.root / "evidence" / "Operating") == before
    assert not (project.root / ".tuba" / "staging").exists()
    assert not solve_claimed(project.root)


def test_every_operation_of_a_study_lands(tmp_path):
    project = _copy(tmp_path, PROFILE, evidence=False)

    outcome = solve_project(project, solver=ReplaySolver(PROFILE / "evidence"))

    assert outcome.solved == ("global", "local")
    for case in ("global", "local"):
        assert load_code_aster_execution_attestation(project.root / "evidence" / case) is not None
        assert outcome.runs[case].result_state.metadata["result_trust"] == "verified"


def test_an_unverified_run_is_written_and_reported(tmp_path):
    project = _copy(tmp_path, RACK, evidence=False)

    outcome = solve_project(project, solver=ReplaySolver(RACK / "evidence", execution_method="docker"))

    assert outcome.unverified == ("Operating",)
    written = project.root / "evidence" / "Operating" / "study_execution.json"
    assert json.loads(written.read_text(encoding="utf-8"))["execution_method"] == "docker"


def test_a_project_another_solve_claims_is_busy(tmp_path):
    project = _copy(tmp_path, RACK, evidence=False)

    with claim_solve(project.root):
        with pytest.raises(SolveBusy):
            solve_project(project, solver=ReplaySolver(RACK / "evidence"))

    assert not (project.root / "evidence").exists()


def test_a_study_without_operations_has_nothing_to_solve(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    shutil.copy2(RACK / "model.py", root / "model.py")
    (root / "study.py").write_text("LOAD_CASES = ()\n", encoding="utf-8")

    with pytest.raises(ValueError, match="no study operations"):
        solve_project(load_project(root))


def test_a_volume_study_exports_its_solids_without_the_tensor_stress_table(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "model.py").write_text(VOLUME_MODEL, encoding="utf-8")
    (root / "study.py").write_text(VOLUME_STUDY, encoding="utf-8")

    with pytest.raises(_Exported) as exported:
        solve_project(load_project(root), solver=_RefuseToSolve())

    study = exported.value.args[0]
    assert study.metadata["volume_analysis"]
    assert study.metadata["compiler_inputs"]["export_tensor_stress"] is False
    assert not (root / "evidence").exists()
    assert not (root / ".tuba" / "staging").exists()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PY -m pytest tests/test_project_solve.py -q -p no:cacheprovider`

Expected: collection error `ModuleNotFoundError: No module named 'tuba.project.solve'`.

- [ ] **Step 3: Implement the project solve**

Create `tuba/project/solve.py`:

```python
"""Project solve: bring a project's evidence up to date with its model and study.

Spec decision 13: evidence whose attested solver input matches what the model and study would compile now
is reused, unless the solve is forced. Decision 11: the rest is solved and lands in ``evidence/<operation>/``
(decision 12: all operations or none). Decision 18: an unverified run is written and reported. Decision 20:
the solve holds the project's claim throughout.
"""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts
from tuba.analysis.provenance import SolverInputIdentity
from tuba.analysis.run import AnalysisRun
from tuba.analysis.study import AnalysisStudy
from tuba.model import TubaModel
from tuba.project import STUDY_SCRIPT, Project
from tuba.project.claim import claim_solve
from tuba.project.evidence import evidence_dir, promote_evidence
from tuba.project.freshness import expected_identity
from tuba.solver.aster import CodeAsterSolver
from tuba.solver.code_aster_runtime import load_code_aster_execution_attestation

STAGING = Path(".tuba") / "staging"


class Solver(Protocol):
    """The solver port: solve the study exported in ``study.work_dir`` and return the run imported from there.

    ``CodeAsterSolver`` is the production adapter; tests replay committed real evidence.
    """

    def solve_exported_study(self, model: TubaModel, study: AnalysisStudy) -> AnalysisRun: ...


@dataclass(frozen=True)
class ProjectSolve:
    """What a project solve did. ``runs`` holds every operation's run, imported from its evidence folder."""

    runs: dict[str, AnalysisRun]
    solved: tuple[str, ...]
    reused: tuple[str, ...]
    unverified: tuple[str, ...]


def solve_project(
    project: Project,
    namespace: Mapping[str, Any] | None = None,
    *,
    study_file: str = STUDY_SCRIPT,
    force: bool = False,
    solver: Solver | None = None,
) -> ProjectSolve:
    """Solve the study's operations whose evidence no longer matches the model and study, or all with *force*.

    *namespace* is the model script's globals, ``project.run_model()`` when omitted; a caller that already ran
    the script passes that snapshot. *study_file* picks the study, as :meth:`Project.load_study` does.
    *solver* defaults to Code_Aster. Nothing reaches ``evidence/`` before every solve has finished, so a
    solve that raises leaves the evidence as it was.
    """
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
    with claim_solve(project.root):
        solve = operations if force else tuple(
            operation
            for operation in operations
            if not _evidence_attests(
                folders[operation],
                expected_identity(model, operation, solver_options=options, volume_export=volume_export),
            )
        )
        staging = project.root / STAGING
        shutil.rmtree(staging, ignore_errors=True)
        try:
            port = solver or exporter
            for operation in solve:
                folder = staging / operation
                folder.mkdir(parents=True)
                exported = (
                    exporter.export_volume_study(model, operation, folder, **dict(volume_export), export_tensor_stress=False)
                    if volume_export
                    else exporter.export_analysis_study(model, operation, folder)
                )
                port.solve_exported_study(model, exported)
            promote_evidence({staging / operation: folders[operation] for operation in solve})
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        runs = {operation: import_code_aster_artifacts(model=model, work_dir=folders[operation]) for operation in operations}
    return ProjectSolve(
        runs=runs,
        solved=solve,
        reused=tuple(operation for operation in operations if operation not in solve),
        unverified=tuple(
            operation for operation, run in runs.items() if run.result_state.metadata.get("result_trust") != "verified"
        ),
    )


def _evidence_attests(folder: Path, identity: SolverInputIdentity) -> bool:
    """Whether *folder* holds intact evidence attesting *identity*. Damaged evidence is solved again, not trusted."""
    try:
        attestation = load_code_aster_execution_attestation(folder)
    except ValueError:
        return False
    return attestation is not None and SolverInputIdentity.from_dict(attestation["solver_input_identity"]) == identity
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PY -m pytest tests/test_project_solve.py tests/test_project_evidence.py tests/test_project_claim.py tests/test_project_freshness.py -q -p no:cacheprovider`

Expected: PASS. No full suite: this task only adds modules and their tests.

- [ ] **Step 5: Commit**

```bash
git add tuba/project/solve.py tests/project_replay.py tests/test_project_solve.py
git commit -m "feat(project): solve a project through a solver port, reusing matching evidence

Spec decisions 11, 13, 18 and 20. solve_project reuses evidence whose attested
solver input matches the model and study, unless forced. It solves the rest
into .tuba/staging through the solver port, promotes every operation or none,
and reports unverified runs. Tests replay committed real evidence."
```

---

### Task 5: The study's check runs before a solve becomes evidence

**Files:**
- Modify: `tuba/project/solve.py` (the try block of `solve_project`)
- Modify: `examples/native-friction-review/study.py:58-82`
- Modify: `examples/profile-orientation-review/study.py` (add `check` after `check_solved_response`)
- Modify: `examples/pipe-tee-volume-review/study.py:16-32`
- Modify: `tests/test_project_solve.py` (two tests)

**Interfaces:**
- Consumes: `solve_project` (Task 4).
- Produces: a study may define `check(solved)` (spec Interface).
  - `solved.model` is the model, `solved.namespace` the model script's globals, and `solved.runs[operation]` each operation's run, solved or reused.
  - `solve_project` calls it after every solve and before promotion. A check that raises keeps the solve out of the evidence.
- The friction, profile and tee checks move into their studies' `check`, and their `build_review` still runs them.
  - `validate_for_publication` stays in `build_review`, not in `check`: an unverified run is written (decision 18), and publication refuses it.
  - Every other gallery study has no check.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_project_solve.py`:

```python
def test_a_failing_study_check_keeps_the_solve_out_of_the_evidence(tmp_path):
    project = _copy(tmp_path, RACK, evidence=False)
    study = project.root / "study.py"
    study.write_text(
        study.read_text(encoding="utf-8") + '\n\ndef check(solved):\n    raise RuntimeError(f"rejected {sorted(solved.runs)}")\n',
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match=r"rejected \['Operating'\]"):
        solve_project(project, solver=ReplaySolver(RACK / "evidence"))

    assert not (project.root / "evidence").exists()
    assert not (project.root / ".tuba" / "staging").exists()
    assert not solve_claimed(project.root)


def test_the_study_check_sees_the_model_its_script_globals_and_every_run(tmp_path):
    project = _copy(tmp_path, RACK)
    study = project.root / "study.py"
    study.write_text(
        study.read_text(encoding="utf-8")
        + "\n\ndef check(solved):\n"
        + "    import json\n"
        + "    record = {'model': solved.model.project_name, 'script': Path(solved.namespace['__file__']).name, 'runs': sorted(solved.runs)}\n"
        + "    (Path(__file__).parent / 'checked.json').write_text(json.dumps(record), encoding='utf-8')\n",
        encoding="utf-8",
    )

    solve_project(project, solver=ReplaySolver(RACK / "evidence"))

    assert json.loads((project.root / "checked.json").read_text(encoding="utf-8")) == {
        "model": "SupportRackReview",
        "script": "model.py",
        "runs": ["Operating"],
    }
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PY -m pytest tests/test_project_solve.py -q -p no:cacheprovider -k check`

Expected:
- `test_a_failing_study_check_keeps_the_solve_out_of_the_evidence` fails with `DID NOT RAISE`.
- `test_the_study_check_sees_the_model_its_script_globals_and_every_run` fails with `FileNotFoundError` for `checked.json`.

- [ ] **Step 3: Call the check, and move the studies' checks into it**

In `tuba/project/solve.py`, add `from types import SimpleNamespace` to the imports. Then replace the whole `try:` / `finally:` block and the `runs = {...}` line after it with:

```python
        try:
            port = solver or exporter
            runs = {}
            for operation in solve:
                folder = staging / operation
                folder.mkdir(parents=True)
                exported = (
                    exporter.export_volume_study(model, operation, folder, **dict(volume_export), export_tensor_stress=False)
                    if volume_export
                    else exporter.export_analysis_study(model, operation, folder)
                )
                runs[operation] = port.solve_exported_study(model, exported)
            for operation in operations:
                if operation not in runs:
                    runs[operation] = import_code_aster_artifacts(model=model, work_dir=folders[operation])
            check = getattr(study, "check", None)
            if check is not None:
                check(SimpleNamespace(model=model, namespace=namespace, runs={operation: runs[operation] for operation in operations}))
            promote_evidence({staging / operation: folders[operation] for operation in solve})
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        # A solved run was imported from staging, which is gone: read it again from its evidence folder.
        runs = {
            operation: import_code_aster_artifacts(model=model, work_dir=folders[operation]) if operation in solve else runs[operation]
            for operation in operations
        }
```

Also extend the `solve_project` docstring's last sentence to: "Nothing reaches ``evidence/`` before every solve has finished and the study's ``check(solved)`` has passed, so a solve or check that raises leaves the evidence as it was."

In `examples/native-friction-review/study.py`:
- add `from types import SimpleNamespace` after `from pathlib import Path`.
- Insert this function before `build_review`. Its body is lines 65–82 of today's `build_review`, moved verbatim, with `run` taken from `solved`:

```python
def check(solved):
    """The contact behaviour this comparison exists to show; a solve that misses it never becomes evidence."""
    run = solved.runs[LOAD_CASES[0]]
    friction_contacts = lambda state: {key: value for key, value in state.contact_results.items() if key.startswith("F_")}
    statuses = {contact.status for state in run.result_states for contact in friction_contacts(state).values()}
    if not {"open", "sticking", "sliding"} <= statuses:
        raise RuntimeError(f"Solved example did not resolve all required friction contact states: {sorted(statuses)}")
    hot = next(state for state in run.result_states if math.isclose(state.metadata["pseudo_time"], 2.0))
    cooled = next(state for state in run.result_states if math.isclose(state.metadata["pseudo_time"], 3.0))
    if not any(sum(a*b for a,b in zip(contact.tangential_force, friction_contacts(cooled)[key].tangential_force)) < 0
               for key,contact in friction_contacts(hot).items()):
        raise RuntimeError("Solved example did not demonstrate contact-force reversal on cooling.")
    uplift = next(state for state in run.result_states if math.isclose(state.metadata["pseudo_time"], 4.0))
    if not (uplift.contact_results["F_S1"].status != "open" and uplift.contact_results["F_S2"].status == "open"
            and 0 < uplift.contact_results["F_S2"].gap < 0.01):
        raise RuntimeError("Uplift must open the friction-copy S2 by less than 10 mm while S1 remains seated.")
    if any(contact.status == "open" for contact in run.result_states[-1].contact_results.values()):
        raise RuntimeError("The final Cold stage must reseat all four shoes.")
    if any(math.hypot(*contact.tangential_force) >= 1e-8 for state in run.result_states
           for key, contact in state.contact_results.items() if key.startswith("NF_")):
        raise RuntimeError("The frictionless copy produced a nonzero tangential contact force.")
```

- In `build_review`, replace the moved lines (from `friction_contacts = lambda state: ...` through the `raise RuntimeError("The frictionless copy produced a nonzero tangential contact force.")`) with the single line `    check(SimpleNamespace(model=model, namespace=namespace, runs={LOAD_CASES[0]: run}))`. It goes directly after `run.validate_for_publication(model)`.

In `examples/profile-orientation-review/study.py`, insert after `check_solved_response`:

```python
def check(solved):
    """Rolled stiffness, force basis and rotation sign must match beam theory before a solve becomes evidence."""
    check_solved_response(
        solved.model,
        [solved.runs[case] for case in LOAD_CASES],
        rolls=solved.namespace["ROLLS"],
        length=solved.namespace["LENGTH"],
    )
```

Its `build_review` stays as it is: it calls `check_solved_response` itself for the rows it writes to `orientation-checks.json`.

In `examples/pipe-tee-volume-review/study.py`:
- add `from types import SimpleNamespace` after `from pathlib import Path`;
- insert before `build_review`:

  ```python
  def check(solved):
      """The tee is reviewed as native 3D solids; a run without its volume mesh never becomes evidence."""
      run = solved.runs[LOAD_CASES[0]]
      if not run.study.metadata.get("volume_analysis") or run.analysis_mesh is None:
          raise RuntimeError("The tee review requires an attested native pipe-volume Code_Aster study.")
  ```

- in `build_review`, replace the two lines `if not artifact.study.metadata.get("volume_analysis") or artifact.analysis_mesh is None:` / `raise RuntimeError(...)` with `    check(SimpleNamespace(model=model, namespace=namespace, runs={LOAD_CASES[0]: artifact}))`.

- [ ] **Step 4: Run the covering tests**

Run: `PY -m pytest tests/test_project_solve.py tests/test_official_viewer_publication.py tests/test_code_aster_profile_orientation.py tests/test_code_aster_friction_example.py tests/test_code_aster_tee_volume_reference.py -q -p no:cacheprovider`

Expected: PASS.
- `test_every_operation_of_a_study_lands` now also runs the real profile check over both replayed runs.
- `build_examples` in `tests/test_official_viewer_publication.py` builds the friction, tee and profile reviews from committed evidence, and so runs their moved checks.

- [ ] **Step 5: Run the full suite**

Run `PY -m pytest -q -p no:cacheprovider` in the background, with bounded waits; commit only after it finishes.

Expected: no failures other than the two known vite tests.

- [ ] **Step 6: Commit**

```bash
git add tuba/project/solve.py examples/native-friction-review/study.py examples/profile-orientation-review/study.py examples/pipe-tee-volume-review/study.py tests/test_project_solve.py
git commit -m "feat(project): run the study's check before a solve becomes evidence

Spec decision 11. A study may define check(solved), which receives the model,
the script's globals and every operation's run. A check that raises leaves the
evidence untouched. The friction, profile and tee studies move their result
checks into it, and build_review still runs them."
```

---

### Task 6: The studio's Solve goes through the project solve

**Files:**
- Modify: `tuba/visualization/preview/server.py`, in these places:
  - the `/api/solve` route `:243-254`;
  - in `ProjectStudioServer`: `__init__` `:530-564`, `_produce_review` `:722-732`, `project_info` `:734-746`, `start_solve` `:748-759` and `_solve` `:761-779`.
- Modify: `tuba/project/evidence.py` (add `study_artifact_dir`)
- Modify: `tests/test_studio_project.py`

**Interfaces:**
- Consumes: `solve_project` and `ProjectSolve.unverified` (Tasks 4–5); `solve_claimed` (Task 3); `evidence_dir` and `EVIDENCE` (Task 2).
- Produces: `tuba.project.evidence.study_artifact_dir(project_root, operations) -> Path`, the folder a study's `build_review` imports evidence from.
  - For one operation it is `evidence/<operation>`; for several it is `evidence/`, which holds one folder per operation.
  - That is how today's studies set `ARTIFACT_DIR`.
- Produces: `ProjectStudioServer(..., solver=None)`. `solver` is the port handed to `solve_project`: `None` means Code_Aster, and a test passes a replay.
- Produces: `POST /api/solve` takes an optional boolean `force` (default `false`); any other body is a 400. The viewer already sends `{}`.
- Produces: a Solve depends on whether the study has operations:
  - with study operations, it runs `solve_project(project, namespace, force=force, solver=solver)`, then builds the review from the project's evidence;
  - without any, it builds the review alone and claims nothing.
- Produces: `/api/project` gains `"unverified"`, the operations the last solve left unverified.
- Produces: `"solving"` is also true while another process holds the claim, and `start_solve` then answers 409 "Another process is solving this project."
- An unverified solve is written, and its review then fails in the builders, so the studio emits `solve_failed` and reports `unverified`.

- [ ] **Step 1: Rewrite the studio tests**

Replace the whole of `tests/test_studio_project.py` with the file below. Here is what changes:
- The stub study becomes model-only (`LOAD_CASES = ()`), so the tests that are not about solving never reach Code_Aster. The stub's review is then built at startup.
- `_rack_server` replaces the copy-and-start setup the two support-rack tests duplicated.
- There are three new tests: evidence lands, is reused, and a forced solve runs again; another process's claim makes the studio busy; an unverified solve is written and reported.

```python
import json
import shutil
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError
from urllib.request import Request, urlopen

SUPPORT_RACK = Path(__file__).resolve().parents[1] / "examples" / "support-rack-review"

MODEL = """from tuba import Model

model = Model("StudioProject")
model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0, alpha=1.2e-5)
model.add_pipe_section("DN100", OD=0.1143, WT=0.00602)
model.define_load_case("Operating", gravity=True, pressure=1.0e6)
with model.pipe(section="DN100", material="Steel") as builder:
    builder.start([0.0, 0.0, 0.0], support="anchor")
    builder.run(2.0)
    builder.end(support="anchor")
"""

STUDY = """import threading
from pathlib import Path

from tuba.visualization import build_visualization_scene, write_scene_bundle

LOAD_CASES = ()
SOLVER_OPTIONS = {}
ARTIFACT_DIR = None
VOLUME_EXPORT = None
#: Cleared by a test to hold a review build open.
GATE = threading.Event()
GATE.set()


def build_review(namespace, output, *, artifact_dir=None, force=False):
    GATE.wait(10)
    root = Path(output) / "review_scene"
    write_scene_bundle(build_visualization_scene(namespace["model"]), root)
    return root
"""


class StudioProjectModeTest(unittest.TestCase):
    def _server(self, root: Path, study: str = STUDY):
        from tuba.visualization.preview.server import ProjectStudioServer

        project = root / "project"
        project.mkdir()
        (project / "model.py").write_text(MODEL, encoding="utf-8")
        (project / "study.py").write_text(study, encoding="utf-8")
        server = ProjectStudioServer(project, root / "out", port=0, poll_interval_s=0.05, debounce_s=0.05)
        self.addCleanup(server.stop)
        return server

    def _start(self, root: Path):
        return self._server(root).start()

    def _rack_server(self, root: Path, *, evidence: bool = True, study_edit=lambda text: text, solver=None):
        """A studio on a copy of the support-rack project, started and settled after its startup import."""
        from tuba.visualization.preview.server import ProjectStudioServer

        project = root / "project"
        shutil.copytree(SUPPORT_RACK, project, ignore=None if evidence else shutil.ignore_patterns("evidence"))
        study = project / "study.py"
        study.write_text(study_edit(study.read_text(encoding="utf-8")), encoding="utf-8")
        server = ProjectStudioServer(project, root / "out", port=0, poll_interval_s=0.05, debounce_s=0.05, solver=solver)
        self.addCleanup(server.stop)
        server.start()
        self._wait(lambda: self._idle(server), "the startup import never settled", timeout=120.0)
        return server, project

    def _get(self, server, path: str) -> dict:
        with urlopen(server.base_url + path, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))

    def _post(self, server, path: str, payload: dict | None = None, **headers):
        request = Request(
            server.base_url + path,
            data=json.dumps(payload or {}).encode("utf-8"),
            headers={"Content-Type": "application/json", **headers},
            method="POST",
        )
        try:
            with urlopen(request, timeout=10) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def _wait(self, condition, message: str, timeout: float = 10.0) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if condition():
                return
            time.sleep(0.05)
        self.fail(message)

    def _events(self, server, kind: str) -> int:
        return sum(event.get("type") == kind for event in server.broker.events)

    def _idle(self, server) -> bool:
        info = self._get(server, "api/project")
        return not info["preparing_review"] and not info["solving"]

    def test_a_model_only_study_builds_its_review_at_startup_and_again_on_solve(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        server = self._start(root)

        self.assertTrue((root / "out" / "build" / "scene.json").is_file())
        self._wait(lambda: self._idle(server), "the model-only review was never built")
        info = self._get(server, "api/project")
        keys = ("name", "has_study", "can_solve", "solves", "has_review", "review_stale", "solving", "unverified")
        self.assertEqual(
            {key: info[key] for key in keys},
            {"name": "project", "has_study": True, "can_solve": True, "solves": False, "has_review": True,
             "review_stale": False, "solving": False, "unverified": []},
        )

        self.assertEqual(self._post(server, "api/solve", Origin="http://evil.example")[0], 403)
        self.assertEqual(self._post(server, "api/solve", {"force": "yes"})[0], 400)

        self.assertEqual(self._post(server, "api/solve"), (202, {"ok": True}))
        self._wait(lambda: self._events(server, "solve_finished") == 1 and self._idle(server), "the solve never finished")
        # Nothing had to be solved, so nothing was claimed, staged or promoted.
        self.assertEqual(sorted(path.name for path in (root / "project").iterdir()), ["model.py", "study.py"])

        # This study's review carries no solver evidence, so nothing in it can go stale (spec decision 15).
        status, payload = self._post(server, "api/script", {"code": MODEL.replace("run(2.0)", "run(3.0)")})
        self.assertEqual(status, 200, payload)
        self.assertFalse(payload["review_stale"])
        self.assertFalse(self._get(server, "api/project")["review_stale"])

    def test_an_imported_review_goes_stale_only_when_its_solver_input_changes(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        server, project = self._rack_server(root)
        # Saves judge staleness from the identities read when the review was produced.
        (server.out_dir / "review" / "scene.json").write_text("not json", encoding="utf-8")
        self.assertIsNone(server.review_error)
        self.assertFalse(self._get(server, "api/project")["review_stale"])

        model = (project / "model.py").read_text(encoding="utf-8")
        renamed = model.replace('Model("SupportRackReview")', 'Model("RenamedRack")') + (
            'model.define_load_case("Hydrotest", gravity=True, pressure=2.0e6)\n'
        )
        status, payload = self._post(server, "api/script", {"code": renamed})
        self.assertEqual(status, 200, payload)
        self.assertFalse(payload["review_stale"])

        moved = model.replace("(-2.0, -1.0, 3.0)", "(-2.5, -1.0, 3.0)")
        status, payload = self._post(server, "api/script", {"code": moved})
        self.assertEqual(status, 200, payload)
        self.assertTrue(payload["review_stale"])
        self.assertTrue(self._get(server, "api/project")["review_stale"])

    def test_invalid_study_solver_options_keep_the_studio_usable_and_mark_the_review_stale(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        server, project = self._rack_server(
            root,
            study_edit=lambda text: text.replace("SOLVER_OPTIONS: dict = {}", 'SOLVER_OPTIONS: dict = {"line_segments": 0}'),
        )

        self.assertIsNone(server.review_error)
        info = self._get(server, "api/project")
        self.assertTrue(info["has_review"])
        self.assertTrue(info["review_stale"])
        status, payload = self._post(server, "api/script", {"code": (project / "model.py").read_text(encoding="utf-8")})
        self.assertEqual(status, 200, payload)
        self.assertTrue(payload["review_stale"])

    def test_attested_evidence_imports_after_startup_without_holding_it_up(self):
        tmpdir = self.enterContext(TemporaryDirectory())
        server = self._server(Path(tmpdir), STUDY.replace("ARTIFACT_DIR = None", "ARTIFACT_DIR = Path(__file__).parent"))
        server.study.GATE.clear()
        server.start()

        info = self._get(server, "api/project")
        self.assertEqual((info["preparing_review"], info["has_review"], info["solving"]), (True, False, False))
        self.assertEqual(self._post(server, "api/solve")[0], 409)

        server.study.GATE.set()
        self._wait(lambda: any(event.get("type") == "review_ready" for event in server.broker.events), "no review_ready")
        self._wait(lambda: self._idle(server), "the import never released")
        info = self._get(server, "api/project")
        self.assertEqual((info["preparing_review"], info["has_review"], info["solving"]), (False, True, False))

    def test_a_second_solve_waits_for_the_first(self):
        tmpdir = self.enterContext(TemporaryDirectory())
        server = self._start(Path(tmpdir))
        self._wait(lambda: self._idle(server), "the model-only review was never built")
        server.study.GATE.clear()
        self.assertEqual(self._post(server, "api/solve")[0], 202)
        self.assertEqual(self._post(server, "api/solve")[0], 409)
        server.study.GATE.set()
        self._wait(lambda: self._idle(server), "the solve never released")
        self.assertEqual(self._events(server, "solve_finished"), 1)
        self.assertEqual(self._post(server, "api/solve")[0], 202)
        self._wait(lambda: self._events(server, "solve_finished") == 2, "the second solve never finished")

    def test_solve_lands_evidence_reuses_it_and_a_forced_solve_runs_again(self):
        from tests.project_replay import ReplaySolver

        root = Path(self.enterContext(TemporaryDirectory()))
        solver = ReplaySolver(SUPPORT_RACK / "evidence")
        server, project = self._rack_server(root, evidence=False, solver=solver)

        for count, body, solved in (
            (1, None, ["Operating"]),
            (2, None, ["Operating"]),  # the evidence still matches: reused, not solved
            (3, {"force": True}, ["Operating", "Operating"]),
        ):
            self.assertEqual(self._post(server, "api/solve", body), (202, {"ok": True}))
            self._wait(
                lambda count=count: self._events(server, "solve_finished") == count and self._idle(server),
                f"solve {count} never finished",
                timeout=120.0,
            )
            self.assertEqual(solver.solved, solved)
        self.assertTrue((project / "evidence" / "Operating" / "study_execution.json").is_file())
        info = self._get(server, "api/project")
        self.assertEqual(
            (info["has_review"], info["review_stale"], info["review_error"], info["unverified"]),
            (True, False, None, []),
        )

    def test_a_solve_another_process_holds_makes_the_studio_busy(self):
        from tuba.project.claim import claim_solve

        root = Path(self.enterContext(TemporaryDirectory()))
        server = self._start(root)
        self._wait(lambda: self._idle(server), "the model-only review was never built")

        with claim_solve(root / "project"):
            self.assertTrue(self._get(server, "api/project")["solving"])
            status, payload = self._post(server, "api/solve")
            self.assertEqual(status, 409)
            self.assertIn("Another process", payload["error"])
        self.assertFalse(self._get(server, "api/project")["solving"])

    def test_an_unverified_solve_is_written_and_reported_but_not_published(self):
        from tests.project_replay import ReplaySolver

        root = Path(self.enterContext(TemporaryDirectory()))
        replay = ReplaySolver(SUPPORT_RACK / "evidence", execution_method="docker")
        server, project = self._rack_server(root, evidence=False, solver=replay)

        self.assertEqual(self._post(server, "api/solve")[0], 202)
        self._wait(
            lambda: self._events(server, "solve_failed") == 1 and self._idle(server),
            "the unverified solve never failed",
            timeout=120.0,
        )
        written = json.loads((project / "evidence" / "Operating" / "study_execution.json").read_text(encoding="utf-8"))
        self.assertEqual(written["execution_method"], "docker")
        info = self._get(server, "api/project")
        self.assertEqual(info["unverified"], ["Operating"])
        self.assertIn("result_trust == 'verified'", info["review_error"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PY -m pytest tests/test_studio_project.py -q -p no:cacheprovider`

Expected:
- the support-rack tests fail with `TypeError: ... unexpected keyword argument 'solver'`;
- the model-only test fails on the missing `"unverified"` key, or on the `400` for `{"force": "yes"}`;
- the busy test fails because `solving` is false.

- [ ] **Step 3: Add the review folder rule and route Solve through the project solve**

In `tuba/project/evidence.py`, change `from collections.abc import Mapping` to `from collections.abc import Mapping, Sequence` and add after `evidence_dir`:

```python
def study_artifact_dir(project_root: str | Path, operations: Sequence[str]) -> Path:
    """The folder a study's ``build_review`` imports the project's evidence from.

    A single-operation study imports its operation's folder, and a study of several imports the evidence
    folder holding one folder per operation, as today's studies set ``ARTIFACT_DIR``.
    """
    if len(operations) == 1:
        return evidence_dir(project_root, operations[0])
    return Path(project_root) / EVIDENCE
```

In `tuba/visualization/preview/server.py`, make these changes.

**1. The `/api/solve` route.** Replace

```python
                if length > 0:
                    self.rfile.read(length)
                status, result = solve_handler()
```

with:

```python
                body = self.rfile.read(length) if length > 0 else b"{}"
                try:
                    payload = json.loads(body.decode("utf-8"))
                    force = payload.get("force", False) if isinstance(payload, dict) else None
                    if not isinstance(force, bool):
                        raise ValueError('a solve takes an optional boolean "force"')
                except ValueError as exc:
                    status, result = 400, {"ok": False, "error": str(exc)}
                else:
                    status, result = solve_handler(force=force)
```

**2. `ProjectStudioServer.__init__`.**
- After `debounce_s: float = 0.2,`, add the parameter `solver: Any = None,`.
- At the end of the body, add:

```python
        # The solver port a Solve hands to the project solve: Code_Aster when None, a replay in tests.
        self.solver = solver
        #: The operations the last Solve left unverified (spec decision 18).
        self.unverified: tuple[str, ...] = ()
```

**3. `_produce_review`.** Nothing passes `force` to it any more, so change its signature to `def _produce_review(self, namespace: dict[str, Any], *, artifact_dir: Path | None) -> None:` and its call to `root = self.study.build_review(namespace, work, artifact_dir=artifact_dir)`.

**4. `project_info`.**
- Add `from tuba.project.claim import solve_claimed` as its first line.
- Replace its `"solving"` entry with `"solving": (self._solving and not self._preparing) or solve_claimed(self.project.root),`.
- Add `"unverified": list(self.unverified),` after `"preparing_review"`.

**5. `start_solve`.** Replace with:

```python
    def start_solve(self, force: bool = False) -> tuple[int, dict[str, Any]]:
        from tuba.project.claim import solve_claimed

        if self.study is None:
            return 400, {"ok": False, "error": f"{self.project.name} has no study.py to solve."}
        if self.namespace is None:
            return 400, {"ok": False, "error": "model.py has not run successfully yet."}
        with self._solve_lock:
            if self._solving:
                busy = "The review is still being imported." if self._preparing else "A solve is already running."
                return 409, {"ok": False, "error": busy}
            if solve_claimed(self.project.root):
                return 409, {"ok": False, "error": "Another process is solving this project."}
            self._solving = True
        threading.Thread(
            target=self._solve, args=(self.namespace, force), name="tuba-studio-solve", daemon=True
        ).start()
        return 202, {"ok": True}
```

**6. The start of `_solve`.** Replace everything from its signature through `self._produce_review(namespace, artifact_dir=None, force=True)` with the block below. Its `except` / `else` / `finally` branches stay as they are.

```python
    def _solve(self, namespace: dict[str, Any], force: bool = False) -> None:
        from tuba.project.evidence import study_artifact_dir
        from tuba.project.solve import solve_project

        self.broker.broadcast({"type": "solve_started"})
        try:
            operations = tuple(getattr(self.study, "LOAD_CASES", None) or ())
            artifact_dir = None
            if operations:
                # Spec decisions 11 and 13: bring the project's evidence up to date, then review it.
                self.unverified = solve_project(self.project, namespace, force=force, solver=self.solver).unverified
                artifact_dir = study_artifact_dir(self.project.root, operations)
            self._produce_review(namespace, artifact_dir=artifact_dir)
```

- [ ] **Step 4: Run the covering tests**

Run: `PY -m pytest tests/test_studio_project.py tests/test_studio_server.py tests/test_project_solve.py tests/test_project_evidence.py -q -p no:cacheprovider`

Expected: PASS. `tests/test_studio_server.py` holds the studio's transport tests, including the POST routes' Origin refusal.

- [ ] **Step 5: Run the full suite**

Run `PY -m pytest -q -p no:cacheprovider` in the background, with bounded waits; commit only after it finishes.

Expected: no failures other than the two known vite tests.

- [ ] **Step 6: Commit**

```bash
git add tuba/visualization/preview/server.py tuba/project/evidence.py tests/test_studio_project.py
git commit -m "feat(studio): solve into the project's evidence through the project solve

Spec decisions 11, 13, 18 and 20. Solve reuses evidence that still matches,
and an optional force solves again. The review is built from the project's
evidence afterwards. Another process's claim makes the studio busy, and
/api/project reports the operations the last solve left unverified."
```

---

### Task 7: The project command solves into the project's evidence

**Files:**
- Modify: `tuba/project/__init__.py`: the module docstring `:8-13`, the imports, and `main` `:89-105`
- Modify: `tests/test_project.py` (two tests)
- Modify: `docs/content/examples.md:145`
- Modify: `docs/content/examples/native-friction.md:13` and `:21`
- Modify: `docs/content/examples/profile-orientation.md:27-31`

**Interfaces:**
- Consumes: `solve_project(..., study_file=...)` (Task 4), `study_artifact_dir` (Task 6) and `SolveBusy` (Task 3).
- Produces: `tuba.project.main(argv=None, *, solver=None) -> int`.
  - Without `--artifact-dir`, a study with operations is first solved into the project's evidence: matching evidence is reused, and `--force` solves again. The review is then built from that evidence.
  - `--artifact-dir` still imports the folder it names without solving.
  - A project another solve holds prints the reason to stderr and returns 1.

- [ ] **Step 1: Write the failing tests**

In `tests/test_project.py`, add `import shutil` to the imports and `SUPPORT_RACK = Path(__file__).resolve().parents[1] / "examples" / "support-rack-review"` after `MODEL`. Then add:

```python
def test_the_project_command_solves_into_the_project_evidence_and_reuses_it(tmp_path):
    from tests.project_replay import ReplaySolver
    from tuba.project import main

    project = tmp_path / "support-rack-review"
    shutil.copytree(SUPPORT_RACK, project, ignore=shutil.ignore_patterns("evidence"))
    solver = ReplaySolver(SUPPORT_RACK / "evidence")

    assert main([str(project), "--output", str(tmp_path / "first")], solver=solver) == 0
    assert solver.solved == ["Operating"]
    assert (project / "evidence" / "Operating" / "study_execution.json").is_file()
    assert (tmp_path / "first" / "review_scene" / "scene.json").is_file()

    assert main([str(project), "--output", str(tmp_path / "again")], solver=solver) == 0
    assert solver.solved == ["Operating"]

    assert main([str(project), "--output", str(tmp_path / "forced"), "--force"], solver=solver) == 0
    assert solver.solved == ["Operating", "Operating"]


def test_the_project_command_reports_a_busy_project(tmp_path, capsys):
    from tuba.project import main
    from tuba.project.claim import claim_solve

    project = tmp_path / "support-rack-review"
    shutil.copytree(SUPPORT_RACK, project, ignore=shutil.ignore_patterns("evidence"))

    with claim_solve(project):
        assert main([str(project), "--output", str(tmp_path / "review")]) == 1

    assert "already being solved" in capsys.readouterr().err
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PY -m pytest tests/test_project.py -q -p no:cacheprovider -k solves_into_the_project_evidence`

Expected: FAIL with `TypeError: main() got an unexpected keyword argument 'solver'`.

Do not run `test_the_project_command_reports_a_busy_project` before Step 3. The old `main` builds the support-rack review by solving it, which launches real Code_Aster on a machine that has a runtime.

- [ ] **Step 3: Solve before building the review**

In `tuba/project/__init__.py`:
- add `import sys` after `import runpy`;
- replace the last paragraph of the module docstring with:

```python
Build a project's review from the command line (from the repository root)::

    python -m tuba.project examples/native-friction-review --output .build/friction
    python -m tuba.project examples/native-friction-review --output .build/friction \\
        --artifact-dir examples/native-friction-review/evidence/Cold

The first form solves the study's operations into the project's ``evidence/`` first, reusing evidence that
still matches the model and study (``--force`` solves again). The second imports the folder it names.
"""
```

- replace `main` with:

```python
def main(argv: list[str] | None = None, *, solver: Any = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a project's review: solve what its evidence no longer matches, or import attested evidence."
    )
    parser.add_argument("project", help="Folder holding model.py and study.py")
    parser.add_argument("--output", required=True, type=Path, help="Directory to write the review into")
    parser.add_argument("--artifact-dir", type=Path, help="Import this attested evidence instead of solving")
    parser.add_argument("--force", action="store_true", help="Solve again even if matching evidence exists")
    parser.add_argument("--study", default=STUDY_SCRIPT, help="Study file inside the project (default: study.py)")
    args = parser.parse_args(argv)
    project = load_project(args.project)
    study = project.load_study(args.study)
    if study is None:
        parser.error(f"{project.root} has no {args.study}.")
    namespace = project.run_model()
    artifact_dir = args.artifact_dir
    operations = tuple(getattr(study, "LOAD_CASES", None) or ())
    if artifact_dir is None and operations:
        from tuba.project.claim import SolveBusy
        from tuba.project.evidence import study_artifact_dir
        from tuba.project.solve import solve_project

        try:
            solve_project(project, namespace, study_file=args.study, force=args.force, solver=solver)
        except SolveBusy as exc:
            print(exc, file=sys.stderr)
            return 1
        artifact_dir = study_artifact_dir(project.root, operations)
    root = study.build_review(namespace, args.output, artifact_dir=artifact_dir)
    print(root)
    return 0
```

In the docs:
- `docs/content/examples.md:145`: replace the paragraph with:

  ```markdown
  `tuba.project` imports the attested evidence given with `--artifact-dir`, such as the project's own `evidence/<operation>/` folder. Without it, it first solves the study's operations into that folder, reusing evidence that still matches the model and study (`--force` solves again), and builds the review from there.
  ```

- `docs/content/examples/native-friction.md:13`: replace the opening sentence "Build shows `model.py` beside the scene, and Solve runs Code_Aster again." with "Build shows `model.py` beside the scene. Solve reuses the committed evidence while it still matches the model, and runs Code_Aster once an edit changes the solver input." Keep the rest of the paragraph.
- `docs/content/examples/native-friction.md:21`: replace "Leave out `--artifact-dir` to solve with Code_Aster instead." with "Leave out `--artifact-dir` to solve into the project's `evidence/Cold/` instead; evidence that still matches is reused unless you add `--force`."
- `docs/content/examples/profile-orientation.md:27-31`: replace the lines from "The model is" through "the attested `global` and `local` folders." with:

  ```markdown
  The model is `examples/profile-orientation-review/model.py` and its review is
  `study.py` beside it. `python -m tuba.project examples/profile-orientation-review
  --output <dir>` solves both cases into the project's `evidence/global` and
  `evidence/local` folders, reusing evidence that still matches (`--force` solves
  again); add `--artifact-dir examples/profile-orientation-review/evidence` to import
  the attested `global` and `local` folders without solving.
  ```

  The sentence that follows, "The bundle includes both complete evidence chains under ...", stays as it is.

- [ ] **Step 4: Run the covering tests**

Run: `PY -m pytest tests/test_project.py tests/test_project_solve.py tests/test_static_site_docs.py tests/test_current_api_docs.py tests/test_code_aster_docs.py -q -p no:cacheprovider`

Expected: PASS.

- [ ] **Step 5: Run the full suite**

Run `PY -m pytest -q -p no:cacheprovider` in the background, with bounded waits; commit only after it finishes.

Expected: no failures other than the two known vite tests.

- [ ] **Step 6: Commit**

```bash
git add tuba/project/__init__.py tests/test_project.py docs/content/examples.md docs/content/examples/native-friction.md docs/content/examples/profile-orientation.md
git commit -m "feat(project): the project command solves into the project's evidence

Spec decisions 11 and 13. Without --artifact-dir, python -m tuba.project
solves what the project's evidence no longer matches (--force solves
everything), then builds the review from that evidence. A busy project
exits with 1."
```

---

## Finish

- [ ] If `main` has moved, rebase the branch onto it. Then run `PY -m pytest -q -p no:cacheprovider` on the tip and compare with the per-task results.
- [ ] Run `git log --oneline main..HEAD` and confirm the plan commit plus the seven task commits.
- [ ] Report to the user. The branch merges into `main` only with the user's approval, and a push is the user's own decision. `docs/content` changed, so the push also needs the strict docs build.
