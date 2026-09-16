# Deep modules for solve and publication

Date: 2026-09-16
Status: accepted

Amends `docs/superpowers/specs/2026-09-13-project-authoring-session-design.md`: it supersedes parts of
decisions 1, 13, 14, 17, 19, 23 and 24, and replaces roadmap steps 6 and 7 (see "What this supersedes").
Everything else in that spec stands, and ADRs 0001 (beta API may break, no shims), 0002 (verified results,
one publication owner) and 0003 (agents and engineers meet at the project folder) bind this one too.

Terms follow `CONTEXT.md`, including the four this spec adds: Solver choices, Code_Aster runtime,
Staged run and Publication profile.

## Problem

Roadmap step 6 was executed as Plan 6a, and its review rounds kept finding the same shape of defect:
a rule that no module owns, restated wherever it is needed.

- **The study loader restates the solver's rules.** It keeps hand-written key sets copied from
  `CodeAsterSolver`'s signatures. One of them classed `timeout_seconds` as a machine setting, which
  capped every project solve at 7200 s, and had to be amended (4ca2ff4). A probe showed the loader still
  accepts four option sets that compiling then refuses or silently ignores: `load_step: 5`,
  `load_step: "x"`, `load_path: []` and `load_path: ["Operating"]`. The last two leave the operation
  stale for good.
- **The Pages validator restates what staging knew.** Task 3 made it find each run's attestation through
  provenance; its review then found that evidence could sit anywhere in the bundle, so a guard pinned the
  folder name back (906f0a3). A probe showed that guard does not close the class: decoy `rmed`, `depl`
  and mesh `mail` files still validate, before and after it, and machine paths in `metadata/`, `reports/`
  and root JSON files are never scanned at all.
- **The same knowledge sits on both sides of every seam.** Eleven production modules read a study's
  names, each with its own defaults, and validation reaches two of them. The volume-or-beam export choice
  is written five times. Trust is re-decided in seven places and never checked by Pages. A publication
  profile is a name in three scripts plus a branch chain that allows exactly one run per bundle, so a
  multi-operation Standard review fits no profile at all.

Fixing each finding where it surfaced moved rules between callers. It did not give any rule an owner.

## Objective

Eight deep modules own what is today spread across callers. Each is named by what it owns, and every
other module becomes a thin caller of it.

1. **Solver study** (`tuba/solver/choices.py`): a study's Solver choices, every refusal rule, the
   beam-or-volume dispatch, the Model fingerprint, and compiling a Solver study.
2. **Code_Aster runtime**: how Code_Aster runs on this machine, and the Solver port's production adapter.
3. **Study** (`tuba/project/study.py`): one loaded, validated Study value with its operations, choices
   and hooks.
4. **Project review** (`tuba/project/`): solve or reuse, check, stage, then the study's review hook.
5. **Staged run** (`tuba/analysis/staged_run.py`): an Analysis run's Evidence written into a review
   bundle, and read back out of one.
6. **Publication profile**: what a bundle of one kind must hold, run by run.
7. **Run reader**: importing a run and the one trust judgement.
8. **Bundle checks where bundles are written**: the Project review checks what it writes; Pages keeps
   only its own rules.

## Decisions

### Solver choices and the Solver study module

1. A study's Solver choices are one flat, typed declaration with defaults, owned by the Solver study
   module. `SolverChoices()` is a complete declaration, and a study's `SOLVER_OPTIONS` is exactly its
   keyword set. Today's `VOLUME_EXPORT` keys are absorbed into it (`element_ids`, `max_element_size`,
   `element_order`), and `model.solve()` and the MCP take the same vocabulary. The three spellings go.
2. Three steps, and no caller may skip one:
   - `SolverChoices.parse(mapping)`, or typed construction, refuses everything answerable without a
     model;
   - `choices.plan(model, operation)` refuses what needs the model, and carries the Model fingerprint
     that compiling will attest;
   - `plan.compile(folder)` writes the Solver study into a folder the caller names, stamping that
     fingerprint.
   Nothing meshes, writes or solves before `compile`, so asking for a fingerprint is free of effect
   (this keeps decision 15 structurally rather than by two helpers agreeing).
3. Two error types, both `ValueError` subclasses:
   - `InvalidSolverChoices` means the study is broken as written, and always raises;
   - `UncompilableOperation` means this model cannot run these choices now; freshness counts that
     operation stale and keeps the reason, and a solve raises.
   Callers stop deciding by where the error came from.
4. Runtime settings and `export_tensor_stress` are not choices. They are refused by name, naming the
   module that owns them. `tuba/project/study.py`'s `_RUNTIME`, `_VOLUME_REQUIRED` and `_VOLUME` sets are
   deleted, not moved.
5. Model fingerprints stay byte-identical. Filled defaults never reach `compiler_inputs`, and
   `build_solver_input_identity` is untouched, so every committed Evidence folder stays fresh. A test
   pins each gallery project's expected identity against its committed attestation.
6. The beam-or-volume dispatch is internal to the module. The mixed STEP exporter is not a Solver study,
   because a solve can never run it: it keeps its exporter class and its one example caller, and
   `CodeAsterSolver.export_mixed_analysis_study` goes. The mixed 1D/3D volume study stays covered.
7. A declared choice that this model's compile never consumes is reported, not silently ignored. Today
   `load_step: 5` is both accepted and ignored.

### The Code_Aster runtime

8. The runtime module owns every machine setting, the timeout included, read once from the
   `TUBA_CODE_ASTER_*` environment variables with explicit overrides in code. No study may name one, so
   the study-level `timeout_seconds` of 4ca2ff4 is retired.
9. `CodeAsterSolver` becomes the name of the Solver port's production adapter and keeps
   `solve_exported_study`. It sheds the compile half, its eight export entry points and its own
   identity-only reuse probe, which today reuses a Docker run the Project would refuse.

### The Study

10. `Project.load_study` returns one Study value: its validated operations (each able to own an Evidence
    folder, with no two sharing one), its Solver choices, and its hooks. Every reader asks the Study;
    no module reads study names directly. The studio and the refresh stop acting on a view a solve would
    refuse, and renaming a study's names becomes a one-file change.
11. An Official gallery record points at a project and its study, and keeps only its card, audience and
    profile. Refresh metadata moves to the Study, and `CONTEXT.md`'s definition changes with it.

### The Project review

12. One Project review takes the project, its Study and the model snapshot; it solves or reuses, runs the
    study's check, stages every operation's run into the bundle, and hands those runs to the study's
    review hook. The CLI, the studio's Solve and startup, and the gallery producer each become one call.
    `ARTIFACT_DIR`, `study_artifact_dir`, `solve_or_import` and `build_review(force=)` go, and a run is
    imported once per solve instead of three times.
13. A solve reuses any Evidence whose attestation matches the expected fingerprint, which restores
    decision 13 as written, and reports unverified runs as unverified. A refresh is a forced solve and
    stays verified-only, and Pages stays verified-only.

### The staged run

14. `stage_runs(runs, bundle)` writes every operation's Evidence into `artifacts/<operation>/`, and
    `read_staged_runs(bundle)` reads them back. Reading is validating; there is no lenient mode.
15. The rule that makes a bundle checkable: every provenance role resolves to a file inside its own run's
    folder whose basename the attestation covers, and every file in that folder is attested. The
    attestation is the only hash record, so `review.json` stops carrying `file_sha256` and `file_sizes`.
16. A staged run exposes attested facts: operation, folder, identity, trust, modelization, contact and
    inventory, derived from the staged manifest. "Contact" means the attested inventory holds the contact
    rows; it is not a separate kind, because a run can be TUYAU and contact at once.

### Publication profiles

17. Three bundle kinds — model review, mesh review and engineering review — are declared in one module
    with each run's required result families and attested files. A bundle is a list of runs, so every
    profile accepts N operations and the beam profile stops faking one-run documents. Contact rows may be
    required only where the attestation covers them.
18. A bundle records its own profile in `scene.json`. Pages checks that it matches the gallery record,
    and the studio and CLI can check their own bundles.

### The run reader and trust

19. One run reader owns importing a run, the attestation check and the single trust judgement.
    `allow_unverified` becomes `allow_unattested`, because it only ever permitted a missing attestation.
    Callers read a run's trust instead of re-deriving it.
20. Trust is visible. Each result state in `scene.json` carries its run's trust and `review.json` keeps it
    in provenance metadata; the review and scene builders accept unverified runs and label them; the
    viewer marks them; the CLI prints a warning; Pages refuses them.

### Checks where bundles are written

21. The Project review checks every bundle it writes, through the staged run and profile modules, and the
    portability rule walks every file the bundle holds except attested solver text, which cannot be
    rewritten. A structurally invalid bundle raises: the studio shows the error and keeps its last good
    review, the CLI exits 1, and Pages refuses. `scripts/build_pages.py` keeps the catalog, the audience
    rules and the verified-only gate.

### Tests

22. Replace, don't layer. When a deep module's interface test covers a behaviour, the test of the shallow
    code it replaced is deleted in the same plan. Publication tests build bundles from committed Evidence
    through the staged run: no fabricated bundles, no hand-written attestations, and no calls into private
    validator helpers.

## Interfaces

**Solver study** (`tuba/solver/choices.py`):

```python
@dataclass(frozen=True)
class SolverChoices:
    pipe_modelization: PipeModelization | str = PipeModelization.TUYAU_3M
    line_segments: int = 8
    load_path: Sequence[str] | None = None
    load_step: float = 0.1
    element_ids: Sequence[str] = ()
    max_element_size: float | None = None
    element_order: int = 2

    @classmethod
    def parse(cls, options: Mapping[str, Any] | None) -> "SolverChoices": ...
    def plan(self, model: TubaModel, operation: str | None = None) -> "SolverStudyPlan": ...


@dataclass(frozen=True)
class SolverStudyPlan:
    choices: SolverChoices
    operation: str
    identity: SolverInputIdentity      # what compiling will attest
    inert: tuple[str, ...]             # declared choices this compile does not consume

    def compile(self, folder: str | Path) -> AnalysisStudy: ...


class InvalidSolverChoices(ValueError): ...    # the study is broken as written
class UncompilableOperation(ValueError): ...   # this model cannot run these choices now
```

**Staged run** (`tuba/analysis/staged_run.py`):

```python
def stage_runs(runs: Mapping[str, AnalysisRun], bundle_root: str | Path) -> dict[str, AnalysisRun]: ...
def read_staged_runs(bundle_root: str | Path) -> tuple[StagedRun, ...]: ...
def check_staged_runs(runs: Iterable[StagedRun]) -> tuple[str, ...]: ...   # report; studio and CLI
def require_staged_runs(runs: Iterable[StagedRun]) -> None: ...            # refuse; Pages


@dataclass(frozen=True)
class StagedRun:
    operation: str
    folder: str                                 # "artifacts/<operation>", bundle-relative
    identity: SolverInputIdentity
    trust: Literal["verified", "unverified"]
    modelization: str | None
    contact: bool                               # the attested inventory holds the contact rows
    inventory: tuple[str, ...]
    files: Mapping[str, str]                    # role -> bundle-relative path, every one attested

    def path(self, role: str) -> Path: ...
```

**The others, in the shape their plans will refine:**

```python
study = project.load_study()                               # operations, choices, check, review
outcome = review_project(project, study, namespace)        # solve or reuse, check, stage, then the hook
profile = PROFILES[bundle_kind]                            # families and inventory per run
run = import_code_aster_artifacts(model=model, work_dir=folder)   # trust stamped once, by the reader
```

## Testing

- **No fabricated results**, unchanged: a Project solve is tested through the replay adapter over
  committed Evidence.
- **Publication follows the same rule.** Bundles under test are built from committed Evidence through the
  staged run. The hand-written bundle producers and the calls into private validator helpers are deleted.
- **New properties, each at one interface:**
  - `parse` accepts a choice set if and only if `plan` would accept it for a model-free reason, over a
    table that includes the four sets the probe found;
  - `plan(model, operation).identity` equals the attested identity in every committed Evidence folder;
  - `compile` stamps `plan.identity` into the study, the sidecar and the Analysis mesh;
  - a decoy role, an unattested file in a run's folder, a renamed folder and one flipped byte each fail
    `read_staged_runs`;
  - a bundle holding two operations validates against the engineering profile;
  - an unverified run is written, labelled in the scene and the review, and refused by Pages.
- **Replaced tests are deleted with the code they covered**, including the private result-parser calls,
  the equality test between the two freshness helpers, and the study loader's list of error strings.

## Roadmap

Five plans. Each gets its own worktree and branch, subagent-driven execution, a final whole-branch review
and a fast-forward merge on the user's approval. The Linux Pages check runs before pushing whenever what
Pages builds changes, which is P1, P3 and P4.

1. **P1, the publication side:** the staged run and the publication profile modules, with the Pages
   validator reading through them, `review.json` losing its per-file hashes, and publication tests built
   from committed Evidence.
2. **P2, the solver side:** the Solver study module, the Code_Aster runtime adapter and the run reader,
   with the one vocabulary, the reuse rule, the `allow_unattested` rename, and the tutorial and workflow
   docs rewritten.
3. **P3, the project side:** the Study module and the Project review, with per-operation staging, the
   review hook receiving runs, the profile recorded in the bundle, the gallery record pointing at a
   project and study, and the CLI, studio and refresh switched over.
4. **P4, checks and trust:** bundles checked where they are written, trust shown per run, the viewer's
   marker, and the builders relaxed to label rather than refuse.
5. **P5, the authoring session:** `open_session`, the MCP and studio as thin callers, and the viewer
   tweaks. This is the old roadmap's step 7, unchanged in scope.

## What this supersedes

| In the 2026-09-13 spec | Now |
|---|---|
| 1, one module owns projects and sessions | Kept, and split into the eight named modules; `tuba/project/` stays the owner of project work |
| 13, reuse matching evidence | Restored as written: reuse any matching attestation and report unverified runs (decision 13 here) |
| 14, stage into `artifacts/<operation>/` | Kept, owned by the staged run module (decisions 14-16) |
| 17, one trust judgement | Kept, and given an owner; "complete for its profile" becomes the profile module's declared inventory (19-20) |
| 19, `export_tensor_stress=False` everywhere | Kept, as a refusal: it is never a study's choice (decision 4) |
| 23, the study contract | Kept; `SOLVER_OPTIONS` is exactly the Solver choices keyword set, absorbing `VOLUME_EXPORT` (1, 10) |
| 24, the Standard review | Kept; the hook receives staged runs rather than a folder (12) |
| Roadmap steps 6 and 7 | Replaced by P1-P5 above |

## Out of scope

- The Ground grid overlay toggle, `imposed_displacement` being accepted but never applied, and
  `model_revision` always being 0, all unchanged from the spec this amends.
- Authoring across machines (ADR 0003).
- A second solver. There is one compiler, so the module takes no registry of alternatives.
- Deleting the mixed STEP example. The exporter stays with its one caller; only its place in the Solver
  study vocabulary goes.
