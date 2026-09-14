# Project and Authoring Session, Plan 3: Gallery Evidence Lives in Its Project

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the nine committed gallery evidence sets from `notebooks/code_aster_results/` into `examples/<project>/evidence/<operation>/`, byte for byte, and point every reader at their new folders.

**Architecture:** A pure move.
- **Nothing changes but the location.** `git mv` keeps every blob, so the attested bytes, the fingerprints and the published bundles stay the same.
  - Nothing inside the evidence records its folder: file names are bare, and the importer rebases them onto whatever folder it is given.
  - A copy experiment moved five sets covering four evidence profiles into this layout, and every rebuilt bundle was byte-identical and passed the validator.
- **Studies keep `ARTIFACT_DIR`** but point it inside their own project. Decision 23 removes the name in Plan 6.
- **Git must not rewrite the bytes.** One `.gitattributes` rule stops git from converting evidence line endings. New publication tests pin the layout, that rule and the attested bytes of all nine sets.

**Tech Stack:** Python 3.12, pytest, git.

**Spec:** `docs/superpowers/specs/2026-09-13-project-authoring-session-design.md` (decision 10; roadmap step 3)

## Global Constraints

- **Worktree:** execute in `D:/tmp/tuba-plan3` on branch `project-session/3-move-evidence` (created from `main` at `774d01f`). Never commit in `D:/Gitprojects/Tuba_v4`: another session works there with uncommitted changes. Never `git stash` (the stash stack is shared with other sessions).
- **Python:** the worktree has no `.venv`. Run tests with the main repo's interpreter from the worktree root, as a module so the worktree's `tuba` is imported first: `D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest <args>` (written `PY -m pytest` below).
- **Known worktree failures:** two tests in `tests/test_package_release.py` fail in a fresh worktree with "'vite' is not recognized" (no `viewer/node_modules`). Not caused by this plan; ignore them. The suite on `774d01f`: 1013 passed / 26 skipped / 1 pre-existing zmq warning, plus those two.
- **Evidence bytes are attested.** Move evidence only with `git mv`, and only after `.gitattributes` holds the new rule.
  - Never open and re-save an evidence file, never `git add` an evidence folder, and never run `git add --renormalize`.
  - Code_Aster is not run anywhere in this plan.
- **Folder names:** a gallery evidence folder is `examples/<project>/evidence/<operation>/`, where `<operation>` is the `solver_input_identity.load_case` its `study_execution.json` attests. The five notebook-only folders (`advanced_operating_hot`, `bim_operating`, `building_profile_end_force`, `stress_analysis_operating`, `structural_operating_hot`) stay in `notebooks/code_aster_results/` (decision 10).
- **Notebooks are nbformat JSON.** Change a path by replacing its text inside the existing JSON string; never re-serialise a notebook.
- **Dated design records stay as written:** do not edit files under `docs/superpowers/` other than this plan.
- **No compatibility shims** (ADR 0001), **no new dependencies**.
- **Commit attribution:** every commit message ends with `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`
- **Out of scope:**
  - removing `ARTIFACT_DIR`, `LOAD_CASES` and `build_review` (decision 23, Plan 6);
  - solves writing evidence into the project (decisions 11–13, Plan 5);
  - validating operation names as folder names (Plan 5, where solves create the folders);
  - the bundle's `artifacts/<operation>/` layout (decision 14, Plan 6);
  - how the friction study's Cold→Hot→Cold→Lift→Cold load path maps onto operations (Plan 6);
  - the stale `viewer/public/code-aster-review/artifacts/*` line in `.gitattributes`;
  - the solve-time absolute path recorded inside each `study.mess` (hashed text nothing parses).
- **Before pushing:** run the Linux Pages check (spec, "Migration roadmap"), because this step changes what Pages builds from. This plan ends at a local merge.

---

### Task 1: Gallery evidence lives in its project

Move the nine evidence sets and point every reader at their new folders, in one commit so the suite stays green.

**Files:**
- Modify: `.gitattributes` (lines 9–22)
- Move: eight folders out of `notebooks/code_aster_results/` (Step 4)
- Modify: the `ARTIFACT_DIR` line of `examples/{autorouted-expansion-loop,code-aster-review,elements-supports-review,guyed-mast-review,native-friction-review,pipe-tee-volume-review,profile-orientation-review,support-rack-review}/study.py`
- Modify: `examples/code_aster_artifact_review.py:111`
- Modify: `notebooks/04_visualization_gallery.ipynb:162`, `notebooks/10_interactive_postprocessor.ipynb:10,120`, `notebooks/visualize_elements_and_supports.ipynb:251`
- Modify: `tests/test_official_viewer_publication.py` (after line 31; lines 307–326), `tests/test_notebook_code_aster_results.py:147-176`, `tests/test_plotting_rmed.py:12-19`, `tests/test_code_aster_profile_orientation.py:36`, `tests/test_code_aster_gallery_refresh.py:402`, `tests/test_operating_clash.py:87`, `tests/test_code_aster_friction_example.py:41`

**Interfaces:**
- **Consumes:** the `build_pages.OFFICIAL_GALLERIES` records (`scripts/official_gallery.py:37-63`, built at `:134-175`):
  - `artifact_dir: Path | None` is the study's `ARTIFACT_DIR`;
  - `refresh_load_cases: tuple[str, ...]` is the study's `LOAD_CASES` when it has more than one, else `()`;
  - `project: str | None` is `"examples/<id>"`.

  The gallery refresh writes a single-case gallery's evidence straight into `artifact_dir`, and a multi-case gallery's into `artifact_dir/<case>` (`scripts/refresh_code_aster_gallery.py:53-56`).
- **Produces:**
  - Every gallery study's `ARTIFACT_DIR` points inside its own project: `Path(__file__).resolve().parent / "evidence" / LOAD_CASES[0]` for a single-case study, and `Path(__file__).resolve().parent / "evidence"` for `profile-orientation-review`, whose study appends each case.
  - `run_example`'s default evidence is `examples/code-aster-review/evidence/Operating`.
  - Nothing that consumes `ARTIFACT_DIR` changes shape.

- [ ] **Step 1: Write the failing tests**

In `tests/test_official_viewer_publication.py`, after `PAGES_BUNDLES = build_pages.PAGES_BUNDLE_IDS` (line 31), add:

```python
REPO_ROOT = Path(__file__).resolve().parents[1]


def _gallery_evidence_roots(gallery) -> list[Path]:
    """The evidence folders a gallery imports: one per case when it has several, else its artifact_dir."""
    return [gallery.artifact_dir / case for case in gallery.refresh_load_cases] or [gallery.artifact_dir]


def _committed_evidence_sets() -> list[Path]:
    """Every committed gallery evidence set, relative to the repository root."""
    return sorted(
        {
            Path(root).resolve().relative_to(REPO_ROOT)
            for gallery in build_pages.OFFICIAL_GALLERIES
            if gallery.artifact_dir is not None
            for root in _gallery_evidence_roots(gallery)
        }
    )
```

Replace `test_committed_gallery_artifact_bytes_match_the_execution_attestation` and its `parametrize` decorator (lines 307–326) with:

```python
@pytest.mark.parametrize("artifact_root", _committed_evidence_sets(), ids=lambda root: root.as_posix())
def test_committed_gallery_artifact_bytes_match_the_execution_attestation(
    artifact_root: Path,
) -> None:
    attestation = json.loads((REPO_ROOT / artifact_root / "study_execution.json").read_text(encoding="utf-8"))

    for filename, expected in attestation["artifacts"].items():
        path = (artifact_root / filename).as_posix()
        content = subprocess.check_output(["git", "show", f":{path}"], cwd=REPO_ROOT)
        assert len(content) == expected["size_bytes"], filename
        assert sha256(content).hexdigest() == expected["sha256"], filename


def test_gallery_evidence_lives_in_its_project_one_folder_per_operation() -> None:
    """Evidence is kept in the project it belongs to, one folder per attested operation (spec decision 10)."""
    for gallery in build_pages.OFFICIAL_GALLERIES:
        if gallery.artifact_dir is None:
            continue
        evidence = (REPO_ROOT / gallery.project / "evidence").resolve()
        for root in _gallery_evidence_roots(gallery):
            root = Path(root).resolve()
            assert root.parent == evidence, f"{gallery.id}: {root} is not in {evidence}"
            attestation = json.loads((root / "study_execution.json").read_text(encoding="utf-8"))
            assert attestation["solver_input_identity"]["load_case"] == root.name, gallery.id

    tracked = subprocess.check_output(["git", "ls-files", "notebooks/code_aster_results"], cwd=REPO_ROOT, text=True)
    assert {Path(line).parts[2] for line in tracked.splitlines()} == {
        "advanced_operating_hot",
        "bim_operating",
        "building_profile_end_force",
        "stress_analysis_operating",
        "structural_operating_hot",
    }


def test_git_never_converts_the_line_endings_of_committed_evidence() -> None:
    """Attestation hashes bind exact bytes, and a checkout under core.autocrlf would rewrite them."""
    listed = subprocess.check_output(
        ["git", "ls-files", "-z", "--", ":(glob)examples/*/evidence/**", ":(glob)notebooks/code_aster_results/**"],
        cwd=REPO_ROOT,
    )
    files = [name for name in listed.decode("utf-8").split("\0") if name]
    output = subprocess.run(
        ["git", "check-attr", "-z", "--stdin", "text"],
        input=("\0".join(files) + "\0").encode("utf-8"),
        capture_output=True,
        check=True,
        cwd=REPO_ROOT,
    ).stdout.decode("utf-8").split("\0")
    values = dict(zip(output[0::3], output[2::3]))  # -z output is path, attribute, value, repeated

    assert files
    assert {name: values.get(name) for name in files if values.get(name) != "unset"} == {}
```

In `tests/test_notebook_code_aster_results.py`, replace `test_artifact_backed_notebooks_default_to_load_existing_results` (lines 147–176) with:

```python
    def test_artifact_backed_notebooks_default_to_load_existing_results(self):
        repo_root = Path(__file__).resolve().parents[1]
        artifact_backed = {
            "00_welcome_and_setup.ipynb": "notebooks/code_aster_results/stress_analysis_operating",
            "01_building_piping_systems.ipynb": "notebooks/code_aster_results/building_profile_end_force",
            "03_stress_analysis_and_compliance.ipynb": "notebooks/code_aster_results/stress_analysis_operating",
            "04_visualization_gallery.ipynb": "examples/code-aster-review/evidence/Operating",
            "06_structural_frames_and_optimization.ipynb": "notebooks/code_aster_results/structural_operating_hot",
            "07_bim_data_exchange.ipynb": "notebooks/code_aster_results/bim_operating",
            "10_interactive_postprocessor.ipynb": "examples/code-aster-review/evidence/Operating",
            "advanced_piping_design_and_bim.ipynb": "notebooks/code_aster_results/advanced_operating_hot",
            "visualize_elements_and_supports.ipynb": "examples/elements-supports-review/evidence/LoadCase1",
        }
        offenders: list[str] = []

        for notebook_name, artifact_dir in artifact_backed.items():
            artifact_root = repo_root / artifact_dir
            self.assertTrue((artifact_root / "study_depl.csv").exists(), artifact_root)
            attestation = json.loads((artifact_root / "study_execution.json").read_text(encoding="utf-8"))
            for artifact_name, expected in attestation["artifacts"].items():
                content = (artifact_root / artifact_name).read_bytes()
                self.assertEqual(expected["size_bytes"], len(content), artifact_name)
                self.assertEqual(expected["sha256"], hashlib.sha256(content).hexdigest(), artifact_name)
            text = (repo_root / "notebooks" / notebook_name).read_text(encoding="utf-8")
            code = "".join(
                "".join(cell.get("source", []))
                for cell in json.loads(text).get("cells", [])
                if cell.get("cell_type") == "code"
            )
            # The notebook must import this very folder, not merely one that happens to exist.
            folder = "REPO_ROOT / " + " / ".join(f'"{part}"' for part in artifact_dir.split("/"))
            self.assertIn(folder, code, notebook_name)
            if (
                "RUN_CODE_ASTER = False" not in text
                and "TUBA_NOTEBOOK_RUN_CODE_ASTER" not in text
            ):
                offenders.append(notebook_name)

        self.assertEqual([], offenders)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
PY -m pytest "tests/test_official_viewer_publication.py::test_gallery_evidence_lives_in_its_project_one_folder_per_operation" "tests/test_official_viewer_publication.py::test_git_never_converts_the_line_endings_of_committed_evidence" "tests/test_official_viewer_publication.py::test_committed_gallery_artifact_bytes_match_the_execution_attestation" "tests/test_notebook_code_aster_results.py::TestNotebookResultProvenance::test_artifact_backed_notebooks_default_to_load_existing_results" -q
```

Expected, before anything moves:
- `test_gallery_evidence_lives_in_its_project_one_folder_per_operation` FAILS on `autorouted-expansion-loop`: its `notebooks/code_aster_results/autorouted_expansion_hot` folder is not in `examples/autorouted-expansion-loop/evidence`.
- `test_artifact_backed_notebooks_default_to_load_existing_results` FAILS at `04_visualization_gallery.ipynb`: `examples/code-aster-review/evidence/Operating` has no `study_depl.csv` yet.
- `test_git_never_converts_the_line_endings_of_committed_evidence` PASSES. It is a guard, and Step 9 proves it catches a missing rule.
- `test_committed_gallery_artifact_bytes_match_the_execution_attestation` PASSES for all nine sets at their current folders. It covered four sets before; now it is a guard over all nine.

- [ ] **Step 3: Protect the evidence paths from line-ending conversion**

In `.gitattributes`, replace lines 9–22 with the following. Line 23, `viewer/public/code-aster-review/artifacts/* -text -whitespace`, stays as it is.

```
# Solver attestation hashes bind exact bytes; never rewrite their line endings.
examples/*/evidence/** -text -whitespace
notebooks/code_aster_results/stress_analysis_operating/* -text -whitespace
notebooks/code_aster_results/structural_operating_hot/* -text -whitespace
notebooks/code_aster_results/bim_operating/* -text -whitespace
notebooks/code_aster_results/advanced_operating_hot/* -text -whitespace
notebooks/code_aster_results/building_profile_end_force/* -text -whitespace
```

- [ ] **Step 4: Move the evidence**

Run from the worktree root:

```bash
mkdir -p examples/autorouted-expansion-loop/evidence examples/code-aster-review/evidence examples/elements-supports-review/evidence examples/guyed-mast-review/evidence examples/native-friction-review/evidence examples/pipe-tee-volume-review/evidence examples/support-rack-review/evidence
git mv notebooks/code_aster_results/autorouted_expansion_hot examples/autorouted-expansion-loop/evidence/Hot
git mv notebooks/code_aster_results/viz_gallery_operating examples/code-aster-review/evidence/Operating
git mv notebooks/code_aster_results/elements_supports_loadcase1 examples/elements-supports-review/evidence/LoadCase1
git mv notebooks/code_aster_results/guyed_mast_wind examples/guyed-mast-review/evidence/Wind
git mv notebooks/code_aster_results/native-friction-review examples/native-friction-review/evidence/Cold
git mv notebooks/code_aster_results/tee_volume_operating examples/pipe-tee-volume-review/evidence/Operating
git mv notebooks/code_aster_results/profile-orientation-review examples/profile-orientation-review/evidence
git mv notebooks/code_aster_results/support_rack_operating examples/support-rack-review/evidence/Operating
```

`profile-orientation-review` moves as a whole folder. Its `global/` and `local/` subfolders become `examples/profile-orientation-review/evidence/global/` and `.../evidence/local/`.

Check the move:

```bash
git diff --cached -M --name-status | grep -c "^R100"
git diff --cached -M --name-status | grep -vc "^R100"
git status --short -- examples notebooks/code_aster_results | grep -v "^R  "
```

Expected:
- `112`: every evidence file is a 100% rename.
- `0`: nothing else is staged.
- No output: no evidence file shows as modified.

If an evidence file shows as modified, stop and report it; do not stage it.

- [ ] **Step 5: Point the studies and `run_example` at the project evidence**

In each of these seven studies, replace the `ARTIFACT_DIR = Path(__file__).resolve().parents[2] / "notebooks" / "code_aster_results" / "<folder>"` line with the line below. Each study declares exactly one load case in `LOAD_CASES` just above `ARTIFACT_DIR`.

```python
ARTIFACT_DIR = Path(__file__).resolve().parent / "evidence" / LOAD_CASES[0]
```

- `examples/autorouted-expansion-loop/study.py:10`
- `examples/code-aster-review/study.py:9`
- `examples/elements-supports-review/study.py:9`
- `examples/guyed-mast-review/study.py:9`
- `examples/native-friction-review/study.py:19`
- `examples/pipe-tee-volume-review/study.py:11`
- `examples/support-rack-review/study.py:10`

In `examples/profile-orientation-review/study.py`, replace line 18 with the following, and keep the comment on line 15:

```python
ARTIFACT_DIR = Path(__file__).resolve().parent / "evidence"
```

In `examples/code_aster_artifact_review.py`, replace line 111 (`        else ROOT / "notebooks" / "code_aster_results" / "viz_gallery_operating"`) with:

```python
        else DEFAULT_PROJECT / "evidence" / "Operating"
```

- [ ] **Step 6: Point the notebooks at the project evidence**

The notebook sources are JSON strings, so each quote in these lines is written `\"` in the file. Replace text only, with an exact-string editor.

In `notebooks/04_visualization_gallery.ipynb` (line 162) and `notebooks/10_interactive_postprocessor.ipynb` (line 120), replace:

```
REPO_ROOT / \"notebooks\" / \"code_aster_results\" / \"viz_gallery_operating\"
```

with:

```
REPO_ROOT / \"examples\" / \"code-aster-review\" / \"evidence\" / \"Operating\"
```

In `notebooks/10_interactive_postprocessor.ipynb` (line 10, the introduction's markdown), replace:

```
`notebooks/code_aster_results/viz_gallery_operating`
```

with:

```
`examples/code-aster-review/evidence/Operating`
```

In `notebooks/visualize_elements_and_supports.ipynb` (line 251), replace:

```
REPO_ROOT / \"notebooks\" / \"code_aster_results\" / \"elements_supports_loadcase1\"
```

with:

```
REPO_ROOT / \"examples\" / \"elements-supports-review\" / \"evidence\" / \"LoadCase1\"
```

Check that the three notebooks still parse and that only those lines changed:

```bash
PY -c "import json, sys; [json.load(open(path, encoding='utf-8')) for path in sys.argv[1:]]" notebooks/04_visualization_gallery.ipynb notebooks/10_interactive_postprocessor.ipynb notebooks/visualize_elements_and_supports.ipynb
git diff --numstat -- notebooks/04_visualization_gallery.ipynb notebooks/10_interactive_postprocessor.ipynb notebooks/visualize_elements_and_supports.ipynb
```

Expected:
- The first command prints nothing.
- The second prints `1	1`, `2	2` and `1	1` for the three notebooks, in that order.

- [ ] **Step 7: Point the tests that read evidence directly at the new folders**

In `tests/test_plotting_rmed.py`, replace lines 12–19 (`RMED = ...` through the closing parenthesis of `MIXED_RMED`) with:

```python
RMED = ROOT / "examples" / "code-aster-review" / "evidence" / "Operating" / "study.rmed"
MIXED_RMED = ROOT / "examples" / "elements-supports-review" / "evidence" / "LoadCase1" / "study.rmed"
```

In `tests/test_code_aster_profile_orientation.py`, replace line 36 with:

```python
    roots = Path(__file__).resolve().parents[1] / "examples/profile-orientation-review/evidence"
```

In `tests/test_code_aster_gallery_refresh.py`, replace line 402 with:

```python
    source = Path(__file__).resolve().parents[1] / "examples" / "code-aster-review" / "evidence" / "Operating"
```

In `tests/test_operating_clash.py`, replace line 87 with:

```python
            work_dir=Path("examples/autorouted-expansion-loop/evidence/Hot"),
```

In `tests/test_code_aster_friction_example.py`, replace line 41 with:

```python
        artifacts = Path("examples/native-friction-review/evidence/Cold")
```

- [ ] **Step 8: Run the tests to verify they pass**

Run (about ten minutes, because `test_pages_catalog_contains_the_validated_official_bundles` builds every Pages bundle):

```bash
PY -m pytest tests/test_official_viewer_publication.py tests/test_notebook_code_aster_results.py tests/test_plotting_rmed.py tests/test_code_aster_profile_orientation.py tests/test_code_aster_gallery_refresh.py tests/test_operating_clash.py tests/test_code_aster_friction_example.py tests/test_code_aster_artifact_import.py tests/test_studio_project.py tests/test_examples.py -q
```

Expected: PASS. The friction integration test stays skipped without `TUBA_RUN_CODE_ASTER_INTEGRATION`.

- [ ] **Step 9: Prove the line-ending test guards the rule**

1. Delete the line `examples/*/evidence/** -text -whitespace` from `.gitattributes`. Do not run `git add` while it is missing.
2. Run:

   ```bash
   PY -m pytest "tests/test_official_viewer_publication.py::test_git_never_converts_the_line_endings_of_committed_evidence" -q
   ```

   Expected: FAIL, listing the moved evidence files with the value `unspecified`.
3. Restore the line, so that `git diff -- .gitattributes` shows exactly the Step 3 change again.
4. Run the same command. Expected: PASS.

- [ ] **Step 10: Run the full suite**

Run `PY -m pytest -q -p no:cacheprovider`. It takes about 15 minutes, so run it in the background and wait in bounded stretches; commit only after it finishes.

Expected: 1020 passed / 26 skipped / 1 pre-existing zmq warning, plus only the two known vite failures. The 1020 is the 1013 before this plan, plus five more parameters of the attestation-bytes test, plus the two new tests.

- [ ] **Step 11: Commit**

The renames are already staged by `git mv`; stage only the edited files:

```bash
git add .gitattributes examples/code_aster_artifact_review.py examples/autorouted-expansion-loop/study.py examples/code-aster-review/study.py examples/elements-supports-review/study.py examples/guyed-mast-review/study.py examples/native-friction-review/study.py examples/pipe-tee-volume-review/study.py examples/profile-orientation-review/study.py examples/support-rack-review/study.py notebooks/04_visualization_gallery.ipynb notebooks/10_interactive_postprocessor.ipynb notebooks/visualize_elements_and_supports.ipynb tests/test_official_viewer_publication.py tests/test_notebook_code_aster_results.py tests/test_plotting_rmed.py tests/test_code_aster_profile_orientation.py tests/test_code_aster_gallery_refresh.py tests/test_operating_clash.py tests/test_code_aster_friction_example.py
git diff --cached -M --stat | tail -1
```

Expected: `132 files changed`: 112 renames plus 20 edited files.

```bash
git commit -m "refactor(examples): keep gallery evidence in its project

Each gallery project's committed Code_Aster evidence moves from
notebooks/code_aster_results/ into examples/<project>/evidence/<operation>/,
byte for byte, and the studies, run_example's default, three notebooks and the
tests follow it. One .gitattributes rule keeps git from converting evidence
line endings; new publication tests pin the layout, that rule and the attested
bytes of all nine sets. The five notebook-only evidence folders stay.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: The docs name the evidence's new home

**Files:**
- Modify: `docs/content/examples.md:117-118,141,144`
- Modify: `docs/content/examples/native-friction.md:18`
- Modify: `docs/content/examples/profile-orientation.md:30`
- Modify: `tuba/project/__init__.py:12`
- Modify: `examples/elements-supports-review/model.py:8-11`

**Interfaces:**
- Consumes: the Task 1 layout.
- Produces: text only; no behaviour changes.

- [ ] **Step 1: Update the text**

In `docs/content/examples.md`, replace lines 117–118 with:

```
Committed Code_Aster evidence is engineering evidence, never a cleanup target:
each gallery project keeps its own under `examples/<project>/evidence/<operation>/`,
and the notebooks keep theirs under `notebooks/code_aster_results/`.
```

Replace line 141 with:

```
python -m tuba.project examples/code-aster-review --output .build/code-aster-review --artifact-dir examples/code-aster-review/evidence/Operating
```

Replace line 144 with:

```
`tuba.project` imports the attested evidence given with `--artifact-dir`, such as the project's own `evidence/<operation>/` folder; without it, it launches Code_Aster.
```

In `docs/content/examples/native-friction.md`, replace line 18 with:

```
python -m tuba.project examples/native-friction-review --output .build/native-friction-import --artifact-dir examples/native-friction-review/evidence/Cold
```

In `docs/content/examples/profile-orientation.md`, on line 30, replace `` `--artifact-dir notebooks/code_aster_results/profile-orientation-review` `` with `` `--artifact-dir examples/profile-orientation-review/evidence` ``. The study appends each case, `global` and `local`, to that folder.

In `tuba/project/__init__.py`, replace line 12 with:

```
        --artifact-dir examples/native-friction-review/evidence/Cold
```

In `examples/elements-supports-review/model.py`, replace lines 8–11 of the module docstring with these four lines:

```
The model must stay byte-identical to the one that produced its committed
evidence in ``evidence/LoadCase1``: the imported artifacts are matched on a
solver-input fingerprint, so any drift here makes the committed evidence
unusable rather than merely stale.
```

- [ ] **Step 2: Check that nothing names the old gallery folders**

Run:

```bash
git grep -n -E "autorouted_expansion_hot|viz_gallery_operating|elements_supports_loadcase1|guyed_mast_wind|tee_volume_operating|support_rack_operating|code_aster_results/(native-friction-review|profile-orientation-review)" -- . ":(exclude)docs/superpowers"
```

Expected: no output.

- [ ] **Step 3: Run the docs and project tests**

Run: `PY -m pytest tests/test_static_site_docs.py tests/test_current_api_docs.py tests/test_project.py -q`
Expected: PASS.

- [ ] **Step 4: Run the full suite**

Run `PY -m pytest -q -p no:cacheprovider`, in the background with bounded waits; commit only after it finishes.

Expected: the same as Task 1's result, with only the two known vite failures.

- [ ] **Step 5: Commit**

```bash
git add docs/content/examples.md docs/content/examples/native-friction.md docs/content/examples/profile-orientation.md tuba/project/__init__.py examples/elements-supports-review/model.py
git commit -m "docs: point evidence commands at each project's evidence folder

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Finish

- [ ] Run `PY -m pytest -q -p no:cacheprovider` once more on the branch tip and compare with Task 1's result.
- [ ] Run `git log --oneline main..HEAD` and confirm the plan commit plus the two task commits.
- [ ] Report to the user. The branch merges into `main` only with the user's approval, and it is not pushed before the Linux Pages check has run.

---

## As executed (2026-09-14)

Rulings taken while executing this plan, which amend the text above:

- **No commit trailer.** During execution the repository history was rewritten to strip Claude co-author trailers, and commit attribution was disabled. No commit of this plan carries `Co-Authored-By`: that supersedes "Commit attribution" and the trailers in Tasks 1–2's commit commands.
- **Notebook edits** were exact byte replacements made by a small script, because the Edit tool refuses `.ipynb` files and a notebook editor re-serialises the JSON.
- **Task 2 also changed:**
  - `notebooks/10_interactive_postprocessor.ipynb` line 57, a markdown sentence naming `viz_gallery_operating` that the plan missed;
  - `tests/test_official_viewer_publication.py`, adding `assert _committed_evidence_sets()` so an empty registry cannot pass silently.
- **Task 2's grep guard** also excludes `":(exclude,glob)examples/*/evidence/**"`: line 2 of every `study.mess` records its solve-time path, which is attested text.
- **What changes on the published site:** evidence bundles stay byte-identical except the elements-supports bundle's `source.py` (its docstring). Notebook 10 and three docs pages change too. The Linux Pages check before pushing should expect exactly these differences.
- **Final review follow-ups (one later commit):**
  - the elements-supports docstring and the `examples.md` evidence paragraph are reworded;
  - the layout test also refuses an evidence folder that no gallery imports.
