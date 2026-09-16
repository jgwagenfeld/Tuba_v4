# Deep modules, Plan 1: the staged run and the publication profile

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One module writes an Analysis run's Evidence into a review bundle and reads it back, resolving every provenance file role against that run's own attestation. A second module declares what a bundle of each kind must hold, run by run. The Pages validator reads through both.

**Architecture:**
- **Staged run** (`tuba/analysis/staged_run.py`). `stage_runs` writes each operation's Evidence into `artifacts/<operation>/`; `read_staged_runs` reads a finished bundle back, and reading is validating. Its rule: every provenance role resolves to a file inside its own run's folder whose basename that run's attestation covers, and every file in the folder is attested. The attestation stays the only hash record, so `review.json` stops carrying `file_sha256` and `file_sizes`.
- **Publication profile** (`tuba/analysis/publication_profile.py`). Three bundle kinds — model review, mesh review, engineering review — each declaring the result families a run must show and the files its attestation must cover. A bundle is a list of runs, so every kind accepts any number of operations.
- **What stays in `scripts/build_pages.py`:** assembling the site, the catalog, the audience rules, geometry and source-script checks, the portability scans, and the verified-only rule. Its attestation lookup, its provenance-file checks, both of its `artifacts/` guards, its contact-rows join and its per-profile branch chain go.

**Tech Stack:** Python 3.12, pytest, standard library only.

**Spec:** `docs/superpowers/specs/2026-09-16-deep-modules-for-solve-and-publication-design.md`, decisions 14 to 18 and 22. It amends `2026-09-13-project-authoring-session-design.md` (decisions 14, 17) and follows ADR 0001 (no shims) and ADR 0002 (one publication owner, strict validation separate from legacy loading).

## Global Constraints

- **Worktree:** execute in `D:/tmp/tuba-p1` on branch `deep/1-staged-run`, which starts at `e1348b8` (the spec commit) on top of `main` at `6513a9b`.
  - Never commit in `D:/Gitprojects/Tuba_v4`: other sessions work there.
  - Never `git stash` (the stash stack is shared) and never `git pull`.
- **Python:** the worktree has no `.venv`. Run tests with the main repo's interpreter from the worktree root, as a module, so the worktree's `tuba` is imported first: `D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest <args>` (written `PY -m pytest` below).
- **Test runs finish inside your own turn.** A background run plus a monitor does not wake a subagent once its turn has ended.
  - Use foreground calls with timeout 600000, or a background run you keep checking within the turn.
  - The full suite takes 20 to 25 minutes, and `tests/test_official_viewer_publication.py` alone takes 10 to 19 minutes because it builds every Pages bundle. Split the suite by test-file ranges when one call cannot hold it, and make every test run exactly once.
- **Known failures:** two tests in `tests/test_package_release.py` fail in a fresh worktree with the npm build error ("'vite' is not recognized"), because the worktree has no `viewer/node_modules`. Ignore them. `test_clean_git_index_snapshot_rebuilds_identical_viewer_and_installed_launcher` can fail with "Access is denied" while another uv process runs; rerun it alone before calling it a regression.
- **Committed evidence is frozen, and Code_Aster never runs.**
  - Never write under `examples/*/evidence/` or `notebooks/code_aster_results/`.
  - Never run Code_Aster, never set `TUBA_RUN_CODE_ASTER_INTEGRATION`, and never run `scripts/build_pages.py` by hand.
  - There are nine committed Evidence folders, all executed through WSL, and five of them carry `study_contact.json`.
- **No fabricated bundles (spec decision 22).** A test that needs a bundle stages committed Evidence into `tmp_path` through this plan's own module. Do not write an attestation, a manifest or an `artifacts/` tree by hand, and do not add another role table.
- **Fingerprints and attestations are untouched.** This plan compiles nothing and re-solves nothing: `build_solver_input_identity`, every `compiler_inputs` dict, `study_manifest.json` and the `tuba.code_aster_execution.v1` attestation keep their exact content, so all nine committed Evidence folders stay valid.
- **Line numbers** cite the tree at `6513a9b`. Earlier tasks shift them, so locate code by the quoted text.
- **Also:** no new dependencies, no compatibility shims (ADR 0001), and no commit trailer.
- **Out of scope**, and owned by later plans:
  - P2: the Solver study module, the Code_Aster runtime adapter, the run reader, the reuse rule and the `allow_unattested` rename;
  - P3: the Study module, the Project review, per-operation staging by the Project rather than by study hooks, the bundle recording its own profile, the gallery record pointing at a project and study, and the CLI, studio and refresh;
  - P4: checking bundles where they are written, trust shown per run, the viewer's marker, and relaxing the builders;
  - P5: the authoring session.

---

### Task 1: Stage every operation into its own bundle folder

**Files:**
- Create: `tuba/analysis/staged_run.py`
- Create: `tests/test_staged_run.py`
- Modify: `tuba/analysis/code_aster_artifacts.py:25-210` (the stager and its private helpers move out)
- Modify: `tuba/project/evidence.py:19-41` (the operation-name rule moves in from one place to the other)
- Modify the five staging call sites:
  - `examples/code_aster_artifact_review.py:123`
  - `examples/native-friction-review/study.py:91`
  - `examples/pipe-tee-volume-review/study.py:41`
  - `examples/profile-orientation-review/study.py:112`
  - `examples/code_aster_tee_mixed_review.py:62`
- Modify: `tests/test_official_viewer_publication.py:16` (import), `:165-173` (the catalog's staged-path pins), `:412`, `:561`, `:589`, `:605` (the stager's own tests)
- Modify: `tests/test_code_aster_profile_orientation.py:22`, `:53`

**Interfaces:**
- Produces `tuba.analysis.staged_run.stage_runs(runs, bundle_root) -> dict[str, AnalysisRun]`.
  - `runs` maps an operation name to the Analysis run solved for it.
  - Each run's Evidence lands in `<bundle_root>/artifacts/<operation>/`, and nowhere else.
  - The returned runs carry bundle-relative POSIX references, with `work_dir` cleared.
  - It raises `ValueError` when: a key is not that run's attested operation; an operation cannot name one folder; two runs claim one operation; a run has no attestation, or one that disagrees with its recorded `solve_attestation`; a study, mesh, result-state or history identity disagrees with the attestation; an inventory file is missing; or the staged copy does not reload equal to its source.
  - A role whose basename the attestation does not cover is not staged. That is what drops `stdout`, `stderr` and `study.resu` today, and it stays.
- Produces `tuba.analysis.staged_run.operation_folder_name(operation) -> str`, the one rule for using an operation as a folder name: no separator or reserved character, no control character, no trailing space or dot, no Windows device name, and at most 255 UTF-8 bytes.
  - `tuba/project/evidence.py`'s `evidence_dir` calls it instead of keeping its own copy, and keeps its own message.
  - It lives here because `tuba.project` already imports `tuba.analysis`, and the reverse arrow would be new.
- Task 2 adds the reading half to the same module. Nothing in this task reads a bundle back.
- `stage_code_aster_artifact_evidence` is deleted, not kept as a wrapper (ADR 0001).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_staged_run.py`:

```python
"""Staging an Analysis run's Evidence into a review bundle (spec decisions 14 and 22)."""

import shutil
from pathlib import Path

import pytest

from tuba.analysis.code_aster_artifacts import import_code_aster_artifacts
from tuba.analysis.staged_run import operation_folder_name, stage_runs
from tuba.project import load_project

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def _run(tmp_path, example, operation):
    """One committed Evidence folder, copied out of the repository and imported."""
    source = EXAMPLES / example / "evidence" / operation
    work_dir = tmp_path / "evidence" / operation
    shutil.copytree(source, work_dir)
    model = load_project(EXAMPLES / example).run_model()["model"]
    return import_code_aster_artifacts(model=model, work_dir=work_dir)


def test_a_run_lands_in_the_folder_its_operation_names(tmp_path):
    run = _run(tmp_path, "support-rack-review", "Operating")
    bundle = tmp_path / "bundle"

    staged = stage_runs({"Operating": run}, bundle)

    folder = bundle / "artifacts" / "Operating"
    attested = set(run.result_state.metadata["solve_attestation"]["artifacts"])
    assert {path.name for path in folder.iterdir()} == attested | {"study_execution.json"}
    assert staged["Operating"].study.work_dir is None
    assert staged["Operating"].result_state.files["execution"] == "artifacts/Operating/study_execution.json"
    # Unattested files stay behind: the solver's own listing and its logs.
    assert not (folder / "study.resu").exists()


def test_every_operation_gets_its_own_folder(tmp_path):
    runs = {case: _run(tmp_path, "profile-orientation-review", case) for case in ("global", "local")}
    bundle = tmp_path / "bundle"

    staged = stage_runs(runs, bundle)

    assert sorted(path.name for path in (bundle / "artifacts").iterdir()) == ["global", "local"]
    for case in ("global", "local"):
        assert staged[case].result_state.files["mess"] == f"artifacts/{case}/study.mess"


def test_a_key_that_is_not_the_runs_operation_is_refused(tmp_path):
    run = _run(tmp_path, "support-rack-review", "Operating")

    with pytest.raises(ValueError, match="Operating"):
        stage_runs({"Hot": run}, tmp_path / "bundle")


@pytest.mark.parametrize("name", ["", "a/b", "Hot:Cold", "CON", "Hot ", "x" * 256])
def test_an_operation_that_cannot_name_a_folder_is_refused(name):
    with pytest.raises(ValueError, match="cannot name"):
        operation_folder_name(name)
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `PY -m pytest tests/test_staged_run.py -q -p no:cacheprovider`

Expected: a collection error, `ModuleNotFoundError: No module named 'tuba.analysis.staged_run'`.

- [ ] **Step 3: Move the stager into the new module**

Create `tuba/analysis/staged_run.py` holding:
- `operation_folder_name(operation)`, the name rule moved from `tuba/project/evidence.py:29-41`, raising `ValueError(f"Operation {operation!r} cannot name a folder.")`;
- `stage_runs(runs, bundle_root)`, which loops over the mapping and, for each entry:
  - checks the key against the run's attested load case, and that no two runs claim one operation;
  - calls the moved body of `stage_code_aster_artifact_evidence` with the destination `bundle_root / "artifacts" / operation_folder_name(operation)`;
- the private helpers moved unchanged from `tuba/analysis/code_aster_artifacts.py`: `_evidence_root` (`:163-166`), `_artifact_source` (`:169-183`), `_path_components` (`:186-192`), `_sha256` (`:195-200`) and `_portable_metadata` (`:203-210`).

Keep every check the stager has today, in the same order: the attestation load and its comparison with the recorded `solve_attestation`; the four identity cross-checks and the history-state checks; the copy loop with its basename-collision guard and symlink and traversal refusals; the completeness check; and the reload of the staged attestation. The `artifact_subdir` parameter goes: the folder is derived, never passed.

In `tuba/analysis/code_aster_artifacts.py`, delete `stage_code_aster_artifact_evidence` and the five helpers above, and keep `_artifact_files` and everything the importer uses.

In `tuba/project/evidence.py`, `evidence_dir` calls `operation_folder_name(operation)` and keeps its own message; delete its `_UNSAFE` and `_RESERVED` constants and the inline checks.

Update the five call sites to `stage_runs({<operation>: run}, <bundle root>)`:
- `examples/code_aster_artifact_review.py:123` stages the one run it built, keyed by its result state's load case;
- `examples/native-friction-review/study.py:91`, `examples/pipe-tee-volume-review/study.py:41` and `examples/code_aster_tee_mixed_review.py:62` do the same;
- `examples/profile-orientation-review/study.py:112` drops its `artifact_subdir=f"artifacts/{run.result_state.load_case}"`, which is now the default.

- [ ] **Step 4: Update the tests that named the old function**

- `tests/test_official_viewer_publication.py`: the import at `:16`, and the four stager tests at `:412`, `:561`, `:589` and `:605`, call `stage_runs({...}: run}, bundle)`.
- The catalog pins at `:165-173` become the per-operation paths: every value starts `artifacts/Operating/`, `execution` is `artifacts/Operating/study_execution.json`, `mess` is `artifacts/Operating/study.mess`, and the directory listing reads `(tmp_path / "code-aster-review" / "artifacts" / "Operating")`.
- `tests/test_code_aster_profile_orientation.py:22`, `:53`: the escape-guard test now proves that a bad operation name is refused, because there is no subdirectory argument left to escape with.

- [ ] **Step 5: Run the covering tests**

Run: `PY -m pytest tests/test_staged_run.py tests/test_code_aster_profile_orientation.py tests/test_code_aster_artifact_import.py -q -p no:cacheprovider`

Expected: PASS.

- [ ] **Step 6: Run the publication file and the full suite**

Run `PY -m pytest tests/test_official_viewer_publication.py -q -p no:cacheprovider` (10 to 19 minutes; it rebuilds every Pages bundle), then the full suite, both inside your turn.

Expected: no failures other than the two known vite tests.

- [ ] **Step 7: Commit**

```bash
git add tuba/analysis/staged_run.py tuba/analysis/code_aster_artifacts.py tuba/project/evidence.py tests/test_staged_run.py tests/test_official_viewer_publication.py tests/test_code_aster_profile_orientation.py examples/
git commit -m "refactor(analysis): stage every operation into its own bundle folder

stage_runs writes each operation's evidence into artifacts/<operation>/,
deriving the folder from the run's own attested operation instead of a
subdirectory its caller picks. The operation-name rule moves beside it,
and evidence_dir now calls it."
```

---

### Task 2: Read a bundle's staged runs back, and make reading validating

**Files:**
- Modify: `tuba/analysis/staged_run.py` (add the reading half)
- Modify: `tests/test_staged_run.py` (add the reading tests)

**Interfaces:**
- Consumes `stage_runs` from Task 1.
- Produces `tuba.analysis.staged_run.read_staged_runs(bundle_root) -> tuple[StagedRun, ...]`, ordered by operation.
  - A bundle with no `review.json` holds no runs and yields `()`. That is the right answer for a model review and a mesh review, not an error.
  - Reading is validating: there is no lenient mode and no `validate=` flag.
- Produces the frozen record each caller reads instead of re-deriving:

  ```python
  @dataclass(frozen=True)
  class StagedRun:
      operation: str                       # the attested load case; also the folder name
      folder: str                          # "artifacts/<operation>", bundle-relative POSIX
      identity: SolverInputIdentity        # from the attestation, never from review.json
      trust: Literal["verified", "unverified"]
      modelization: str | None             # compiler_inputs.pipe_modelization, when the study names one
      contact: bool                        # the attested inventory carries the contact rows
      inventory: tuple[str, ...]           # attested basenames, sorted
      files: Mapping[str, str]             # role -> bundle-relative POSIX path, every one attested

      def path(self, role: str) -> Path: ...   # absolute; KeyError for a role this run does not carry
  ```

- **What reading enforces**, each raising `ValueError` naming the operation and the role at fault:
  1. Provenance records group into runs by their `solver_input_identity`; a record without one, or a group missing its study, mesh or result-state record, is an error. N runs is the ordinary case, so no caller has to fake one-run documents.
  2. The run's folder is the folder holding the file that its result-state record's `execution` role names.
  3. `load_code_aster_execution_attestation(folder)` returns a payload, which re-hashes every inventory file, so one flipped byte fails here.
  4. The folder's name equals the attestation's load case, so a renamed or foreign folder is refused. This replaces Plan 6a's `artifacts/` guard.
  5. Every file in the folder is in the inventory or is `study_execution.json`, so a decoy dropped beside real evidence fails even when `review.json` never names it.
  6. Every role of every record in the group resolves to a file inside that run's folder whose basename the inventory covers, or is the envelope. Two roles may share one attested file: `sieq` and `tuyau_subpoints` both name `study_sieq.csv`.
  7. No hash is read from `review.json`. The attestation is the only hash record.
- `modelization` and `contact` are read from the staged `study_manifest.json` and the inventory, never from a profile name a caller passes: `contact` is `"study_contact.json" in inventory`. A run can be TUYAU and contact at once, so contact is not a kind.
- **Not in this task:** the report-versus-refuse split for the studio and the CLI. Those callers arrive in P4, and their functions land with them.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_staged_run.py`, with one helper that builds a real bundle through the real producers:

```python
import json

from tuba.analysis.staged_run import read_staged_runs
from tuba.reporting import build_engineering_review
from tuba.visualization import build_visualization_scene, write_engineering_review_with_scene


def _bundle(tmp_path, example="support-rack-review", operation="Operating"):
    """A real review bundle: committed Evidence, staged, with a scene and a review written over it."""
    run = _run(tmp_path, example, operation)
    model = load_project(EXAMPLES / example).run_model()["model"]
    root = tmp_path / "bundle"
    staged = stage_runs({operation: run}, root)[operation]
    scene = build_visualization_scene(model, analysis_runs=[staged], scene_id="scene:test")
    review = build_engineering_review(model, analysis_runs=[staged], package_id="review:test")
    write_engineering_review_with_scene(review, root, scene=scene, title="Staged run test")
    return root


def _repoint(bundle, role, uri):
    review = json.loads((bundle / "review.json").read_text(encoding="utf-8"))
    record = next(item for item in review["provenance"] if item["kind"] == "result_state")
    record["files"][role] = uri
    (bundle / "review.json").write_text(json.dumps(review), encoding="utf-8")


def test_a_staged_bundle_reads_back_as_its_runs(tmp_path):
    bundle = _bundle(tmp_path)

    (run,) = read_staged_runs(bundle)

    assert (run.operation, run.folder) == ("Operating", "artifacts/Operating")
    assert run.trust == "verified"
    assert run.contact is True                      # the rack rests on friction shoes
    assert "study.rmed" in run.inventory
    assert run.path("mess").read_text(encoding="utf-8", errors="ignore")


def test_a_bundle_without_a_review_holds_no_runs(tmp_path):
    (tmp_path / "empty").mkdir()

    assert read_staged_runs(tmp_path / "empty") == ()


def test_a_role_pointing_outside_its_run_is_refused(tmp_path):
    bundle = _bundle(tmp_path)
    decoy = bundle / "artifacts" / "decoy"
    decoy.mkdir(parents=True)
    (decoy / "study.rmed").write_bytes((bundle / "artifacts" / "Operating" / "study.rmed").read_bytes())
    _repoint(bundle, "rmed", "artifacts/decoy/study.rmed")

    with pytest.raises(ValueError, match="rmed"):
        read_staged_runs(bundle)


def test_an_unattested_file_in_the_folder_is_refused(tmp_path):
    bundle = _bundle(tmp_path)
    (bundle / "artifacts" / "Operating" / "study.resu").write_text("left behind", encoding="utf-8")

    with pytest.raises(ValueError, match="study.resu"):
        read_staged_runs(bundle)


def test_a_renamed_folder_is_refused(tmp_path):
    bundle = _bundle(tmp_path)
    (bundle / "artifacts" / "Operating").rename(bundle / "artifacts" / "Renamed")
    review = json.loads((bundle / "review.json").read_text(encoding="utf-8"))
    for record in review["provenance"]:
        record["files"] = {role: uri.replace("artifacts/Operating/", "artifacts/Renamed/") for role, uri in record["files"].items()}
    (bundle / "review.json").write_text(json.dumps(review), encoding="utf-8")

    with pytest.raises(ValueError, match="Renamed"):
        read_staged_runs(bundle)


def test_one_changed_byte_is_refused(tmp_path):
    bundle = _bundle(tmp_path)
    mess = bundle / "artifacts" / "Operating" / "study.mess"
    mess.write_bytes(mess.read_bytes() + b"\n")

    with pytest.raises(ValueError, match="study.mess"):
        read_staged_runs(bundle)


def test_two_operations_read_back_as_two_runs(tmp_path):
    runs = {case: _run(tmp_path, "profile-orientation-review", case) for case in ("global", "local")}
    model = load_project(EXAMPLES / "profile-orientation-review").run_model()["model"]
    root = tmp_path / "bundle"
    staged = stage_runs(runs, root)
    scene = build_visualization_scene(model, analysis_runs=list(staged.values()), scene_id="scene:two")
    review = build_engineering_review(model, analysis_runs=list(staged.values()), package_id="review:two")
    write_engineering_review_with_scene(review, root, scene=scene, title="Two operations")

    assert [run.operation for run in read_staged_runs(root)] == ["global", "local"]
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `PY -m pytest tests/test_staged_run.py -q -p no:cacheprovider`

Expected: the Task 1 tests pass; every test added here fails at import with `ImportError: cannot import name 'read_staged_runs'`.

- [ ] **Step 3: Implement the reading half**

In `tuba/analysis/staged_run.py` add `StagedRun` and `read_staged_runs`, with the seven rules above. Shape:

```python
def read_staged_runs(bundle_root: str | Path) -> tuple[StagedRun, ...]:
    """Every run staged in this bundle, ordered by operation; reading is validating."""
    root = Path(bundle_root)
    review = root / "review.json"
    if not review.is_file():
        return ()                       # a model or mesh review holds no runs
    records = _records_by_identity(json.loads(review.read_text(encoding="utf-8")))
    return tuple(sorted((_read_one(root, group) for group in records), key=lambda run: run.operation))
```

`_read_one` resolves the folder from the group's result-state `execution` role, loads and integrity-checks the attestation there, compares the folder name with the attested load case, checks the folder holds nothing unattested, resolves every role of every record in the group against the inventory, and reads `modelization` from the staged `study_manifest.json`. Reuse the existing helpers rather than writing new ones:
- `load_code_aster_execution_attestation` for the attestation and its re-hash;
- `execution_trust` for `trust`;
- the traversal and escape refusals already in this module.

- [ ] **Step 4: Run the covering tests**

Run: `PY -m pytest tests/test_staged_run.py tests/test_code_aster_artifact_import.py -q -p no:cacheprovider`

Expected: PASS.

- [ ] **Step 5: Run the full suite**

Run it inside your turn, split if needed. Expected: no failures other than the two known vite tests. Nothing else calls the reading half yet, so this task cannot change what Pages validates.

- [ ] **Step 6: Commit**

```bash
git add tuba/analysis/staged_run.py tests/test_staged_run.py
git commit -m "feat(analysis): read a bundle's staged runs back, validating as it reads

read_staged_runs groups provenance into runs by solver input identity and
resolves every file role against that run's own attestation: a role outside
its folder, an unattested file beside real evidence, a renamed folder and a
changed byte are all refused. Reading is the only mode."
```

---

### Task 3: The Pages validator reads bundles through their staged runs

**Files:**
- Modify: `scripts/build_pages.py`
  - `validate_official_bundle` (`:283-359`), the result-profile half
  - `_validate_beam_review` (`:362-404`), its per-load-case attestation call at `:392`
  - delete `_validate_execution_attestation` (`:585-604`), `_validate_portable_provenance_files` (`:621-644`) and `_file_hash` (`:680-685`)
  - `_validate_embedded_portability` (`:607-618`), its `artifacts/` existence check only
- Modify: `tuba/analysis/staged_run.py` (stop stamping `file_sha256` and `file_sizes`)
- Modify: `tests/test_official_viewer_publication.py` (the fixture's folder and URIs, the catalog's two hash assertions, and the tests Task 2 now owns)

**Interfaces:**
- Consumes `read_staged_runs` and `StagedRun` from Task 2.
- `validate_official_bundle` keeps its signature and its six profile names; only how it reaches a run's evidence changes. The profile names themselves move in Task 5.
- Produces one private helper in `scripts/build_pages.py`:
  `_run_for(runs: Sequence[StagedRun], identity: Mapping[str, Any]) -> StagedRun`, the staged run whose attested identity equals a provenance record's, raising `ValueError("Engineering-review provenance names no staged run.")` otherwise.
- After this task nothing outside `tuba/analysis/staged_run.py` resolves a bundle path for evidence, re-hashes an evidence file, or names the `artifacts/` folder. The scene, geometry, source-script and portability scans stay exactly as they are.
- `review.json` stops carrying `file_sha256` and `file_sizes`. The attestation is the only hash record, and `read_staged_runs` re-hashes every inventory file on every read.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_staged_run.py`, proving the validator now refuses what the probe got past it:

```python
def test_the_pages_validator_refuses_a_decoy_result_file(tmp_path):
    from scripts.build_pages import validate_official_bundle

    bundle = _bundle(tmp_path)
    decoy = bundle / "artifacts" / "decoy"
    decoy.mkdir(parents=True)
    (decoy / "study.rmed").write_bytes((bundle / "artifacts" / "Operating" / "study.rmed").read_bytes())
    _repoint(bundle, "rmed", "artifacts/decoy/study.rmed")

    with pytest.raises(ValueError, match="rmed"):
        validate_official_bundle(bundle, "engineering-review")
```

- [ ] **Step 2: Run it to see it fail**

Run: `PY -m pytest tests/test_staged_run.py -q -p no:cacheprovider -k pages_validator`

Expected: FAIL with `DID NOT RAISE`. Today the validator re-hashes that decoy against the hash `review.json` itself restates, which the probe showed passes.

- [ ] **Step 3: Rewire the validator**

In `validate_official_bundle`, read the runs once, before the profile branches:

```python
    runs = read_staged_runs(root)
```

Then:
- the non-beam result branch (`:343-357`) becomes: `identity = _validate_engineering_provenance(scene, review)`, `run = _run_for(runs, identity)`, and for the contact profile `contacts = run.path("contact")` in place of the `posixpath.join` at `:348`;
- `_validate_beam_review` takes `runs` and, for each load-case state, uses `_run_for(runs, reference)` in place of the `_validate_execution_attestation` call at `:392`;
- the call to `_validate_portable_provenance_files` at `:358` goes;
- `_validate_embedded_portability` keeps both scans and loses its "require an `artifacts/` directory" check at `:609-610`: a bundle with runs has one, and a model or mesh review legitimately has none.

Delete `_validate_execution_attestation`, `_validate_portable_provenance_files` and `_file_hash`. Add `_run_for`, and import `read_staged_runs` and `StagedRun` from `tuba.analysis.staged_run`.

In `tuba/analysis/staged_run.py`, delete the three `"file_sha256"`/`"file_sizes"` stamps on the study, result-state and history metadata, and the hash and size maps `stage_files` returns for them. The attested hashes are already in the attestation; nothing else reads these maps.

- [ ] **Step 4: Update the tests that pinned the old shape**

- `tests/test_official_viewer_publication.py`:
  - `_write_engineering_bundle` (`:754-843`) writes its evidence into `artifacts/Operating/` and points every provenance URI there, because a staged run's folder is its operation. Its synthesized `file_sha256`/`file_sizes` maps (`:804-815`) go.
  - The catalog test's two hash assertions (`:174-175`) go; its path assertions were already updated in Task 1.
  - Delete the tests Task 2 now owns on real bundles: the attestation-inventory omission (`:476`), the attestation identity cross-check (`:488`), and Plan 6a's two folder tests (`:500-535`). Their subject is the staged-run module, and `tests/test_staged_run.py` covers each on committed Evidence.
  - Keep every test whose subject is a scene, a review or portability.

- [ ] **Step 5: Run the covering tests**

Run: `PY -m pytest tests/test_staged_run.py tests/test_official_viewer_publication.py tests/test_pages_build.py tests/test_reporting_builder.py tests/test_reporting_model.py -q -p no:cacheprovider`

Expected: PASS. This includes the catalog build, so allow 10 to 19 minutes and keep the wait inside your turn.

- [ ] **Step 6: Run the full suite**

Expected: no failures other than the two known vite tests.

- [ ] **Step 7: Commit**

```bash
git add scripts/build_pages.py tuba/analysis/staged_run.py tests/test_staged_run.py tests/test_official_viewer_publication.py
git commit -m "refactor(pages): validate bundles through their staged runs

The validator asks the staged-run module for a bundle's runs instead of
resolving folders, re-hashing files and joining filenames itself. Its
attestation lookup, its provenance-file checks, both artifacts/ guards and
its contact-rows join go, and review.json stops restating hashes the
attestation already holds."
```

---

### Task 4: Publication tests build real bundles instead of writing their own

**Files:**
- Create: `tests/publication_bundles.py` (the one helper that builds a real bundle)
- Modify: `tests/test_official_viewer_publication.py` (its remaining fixture-driven tests, and the two fixture builders at `:754-942`)
- Modify: `tests/test_staged_run.py` (use the shared helper instead of its local `_bundle`)
- Modify: `tests/test_pages_build.py:108-112`, `:359-368` (the two private-helper calls)

**Interfaces:**
- Consumes `stage_runs` and `read_staged_runs`.
- Produces `tests/publication_bundles.py`:

  ```python
  def staged_bundle(tmp_path, example="support-rack-review", operations=("Operating",)) -> Path:
      """A real review bundle: committed Evidence copied out, staged, with a scene and review written."""
  ```

  It copies each operation's committed Evidence into `tmp_path`, imports it, stages it, builds the scene and the review through the real producers, and writes the bundle. It takes no flags for damage: a test that wants a broken bundle mutates the one it gets.
- After this task, no test writes an attestation, a manifest, an `artifacts/` tree or a role table by hand, and no test calls a private `_validate_*` helper. That is spec decision 22 for the publication seam, matching the rule the Project solve already follows.

- [ ] **Step 1: Move the remaining tests onto real bundles**

In `tests/test_official_viewer_publication.py`, each surviving fixture-driven test takes `staged_bundle(tmp_path)` and mutates it:
- unsafe or non-portable references, the geometry hash, the geometry payload rehash, error diagnostics, deceptive result labels, and the three provenance-identity tests all mutate `scene.json` or `review.json` exactly as they do now;
- the two stager tests that need a broken source (`:561` collisions and symlinks, `:589` a Windows-relative path) build their input with `tmp_path` files, not with `_artifact_with_files`.

Then delete `_write_engineering_bundle` (`:754-843`), `_artifact_with_files` (`:846-942`) and the helpers only they used, including their two role tables and `_write_study_manifest`.

In `tests/test_pages_build.py`, the two tests that reach into `build_pages._validate_contact_result_fields` (`:108-112`) and `_validate_source_script` (`:359-368`) call `validate_official_bundle` on a real bundle instead: the contact case uses `staged_bundle(tmp_path, "native-friction-review", ("Cold",))`, and the source-script case mutates the `source.py` of a staged bundle.

- [ ] **Step 2: Run the tests**

Run: `PY -m pytest tests/test_official_viewer_publication.py tests/test_pages_build.py tests/test_staged_run.py -q -p no:cacheprovider`

Expected: PASS, with the same number of tests as before minus those Task 3 deleted. The file no longer contains the strings `_write_engineering_bundle`, `_artifact_with_files` or `build_pages._validate`.

- [ ] **Step 3: Run the full suite, then commit**

```bash
git add tests/publication_bundles.py tests/test_official_viewer_publication.py tests/test_pages_build.py tests/test_staged_run.py
git commit -m "test(pages): build publication bundles from committed evidence

The publication tests stage real evidence through the staged-run module and
mutate the bundle they get, instead of hand-writing an attestation, a
manifest and a role table of their own. The second producer and the calls
into private validator helpers are gone."
```

---

### Task 5: Publication profiles as declarations, checked run by run

**Files:**
- Create: `tuba/analysis/publication_profile.py`
- Create: `tests/test_publication_profile.py`
- Modify: `scripts/build_pages.py` (`validate_official_bundle` `:283-359`, `_validate_beam_review` `:362-404`, `_validate_contact_result_fields` `:473-499`, `_validate_engineering_result_fields` `:502-546`)
- Modify: `scripts/official_gallery.py:27-34` (the badge table reads the profile module), `:97-100`
- Modify: `scripts/refresh_code_aster_gallery.py:78` (its `beam=` flag derives from the run, not the profile name)

**Interfaces:**
- Produces `tuba.analysis.publication_profile`:

  ```python
  @dataclass(frozen=True)
  class PublicationProfile:
      name: str                              # "model-review" | "mesh-review" | "engineering-review"
      badge: str                             # the gallery card's evidence line
      runs: bool                             # does a bundle of this kind carry runs?
      marker: str | None                     # the diagnostic code a no-results bundle must carry

      def check(self, bundle_root: Path, scene: Mapping, review: Mapping | None,
                runs: Sequence[StagedRun]) -> None: ...

  PROFILES: Mapping[str, PublicationProfile]
  ```

- **A bundle is a list of runs.** The engineering kind accepts any number, and each run's required result families come from that run's own facts: a volume run shows the volume families, a contact run shows its history families, every other run shows the beam and pipe families. The one-run rule and the beam profile's fake one-run documents go.
- **Required files per run** come from the run's attested inventory, so a profile may require contact rows only where the attestation covers them. This is the gap Plan 6a recorded and deferred: the contact profile never required the contact law it reads.
- The six old names collapse to three kinds. `volume-engineering-review`, `contact-engineering-review` and `beam-engineering-review` become the engineering kind, because what differs between them is the runs, not the bundle.
- `scripts/official_gallery.py` keeps its ten records; each record's `profile` is now one of the three names, and `PROFILE_EVIDENCE` reads its badge from `PROFILES`.
- The bundle recording its own profile is P3's, together with the Project review that writes bundles.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_publication_profile.py`, over real bundles from `tests/publication_bundles.py`:

```python
def test_an_engineering_bundle_of_two_operations_validates(tmp_path):
    bundle = staged_bundle(tmp_path, "profile-orientation-review", ("global", "local"))

    validate_official_bundle(bundle, "engineering-review")     # no beam profile, no fake documents


def test_a_contact_run_must_attest_its_contact_rows(tmp_path):
    bundle = staged_bundle(tmp_path, "native-friction-review", ("Cold",))
    ...                                                        # drop the contact role from review.json

    with pytest.raises(ValueError, match="contact"):
        validate_official_bundle(bundle, "engineering-review")


def test_a_model_review_carries_its_marker_and_no_runs(tmp_path):
    ...                                                        # the imported-component demo bundle
```

- [ ] **Step 2: Run them to see them fail**

Expected: `ModuleNotFoundError: No module named 'tuba.analysis.publication_profile'`, and the two-operation case failing today's one-run rule.

- [ ] **Step 3: Implement the profile module and route the validator through it**

`validate_official_bundle` becomes: read the scene, run the generic checks, read the runs, look the profile up, and call `profile.check(...)`. The per-profile branch chain, the one-record provenance rule and the beam profile's document faking go; `_validate_engineering_result_fields` moves into the module as the per-run family rule.

- [ ] **Step 4: Run the covering tests, then the full suite, then commit**

```bash
git add tuba/analysis/publication_profile.py tests/test_publication_profile.py scripts/build_pages.py scripts/official_gallery.py scripts/refresh_code_aster_gallery.py tests/test_official_viewer_publication.py
git commit -m "feat(pages): declare publication profiles, checked run by run

Three bundle kinds replace six names and a branch chain. Each run's
required families and attested files come from the run itself, so a bundle
of any number of operations validates, the beam profile stops faking
one-run documents, and contact rows are required only where the
attestation covers them."
```

---

## Notes for the executor

- **Order matters.** Task 3 cannot land before Task 2, and Task 4 before Task 3, because each consumes the previous one's interface. Task 5 depends on Tasks 2 and 4.
- **The catalog test is the slow gate.** It builds every Pages bundle and takes 10 to 19 minutes. Tasks 1, 3, 4 and 5 all change what it builds, so each runs it.
- **Before the merge:** a Linux Pages check, because this plan changes where evidence sits inside every published bundle.
