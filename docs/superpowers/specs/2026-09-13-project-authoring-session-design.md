# Project and authoring session: one owner for model scripts, solving and review freshness

Date: 2026-09-13
Status: accepted

Terms follow `CONTEXT.md` (Project, Model script, Generated and Authored model
script, Authoring session, Study, Standard review, Solver study, Evidence,
Model fingerprint, Stale review, Verified and Unverified result). Decisions
here respect ADR 0001 (beta API may break without shims), ADR 0002 (verified
results, one publication owner) and ADR 0003 (agents and engineers meet at the
project folder, on one machine).

## Problem

**The authoring session exists three times.** The MCP server keeps module
globals (`_ACTIVE_MODEL`, `_SCRIPT_TEXT`, `_PREVIEW_REVISION`), `StudioServer`
keeps `model`, `revision` and `baseline_fingerprint`, and `ProjectStudioServer`
adds `_review_model_hash` and its solve flags. Each has its own "was that my own
write?" guard and its own stale rule: the solver-input fingerprint of the first
load case, a sha256 of `to_dict()`, or none. The MCP broadcast sends
`scene_reloaded` with no bundle, so the viewer reloads an unchanged scene, and
an MCP solve never produces a review.

**Two model-script generators.** `tuba/mcp/server.py::_model_script` and
`preview/server.py::export_model_to_python` both write a `from_dict` snapshot.
Fixes landed in one of them each time (8b66cba, 24d6ec7). The studio's `pprint`
writes a bare `nan`, names containing `"` break the MCP script, the MCP
generator crashes on cable sections, and every generated element links to the
same "Defined by model.py:N" line.

**Three solve paths.** `examples/code_aster_artifact_review.py::solve_or_import`,
`scripts/refresh_code_aster_gallery.py::_refresh_study` and `TubaModel.solve`
(used by the friction and profile-orientation studies) reuse evidence
differently, and differ on `export_tensor_stress` (True vs False), which is part
of the model fingerprint. `build_review(force=)` is ignored by seven of nine
studies, and `OfficialGallery` re-exports six fields of `study.py`.

**Trust and freshness are judged in several places.** A Docker-executed run
imports as verified (`tuba/analysis/code_aster_artifacts.py:262`); only the
refresh rejects it. The studio's stale rule is not the rule Pages uses to
reject evidence.

## Objective

One deep module owns projects and authoring sessions. MCP tools, the studio's
HTTP/WebSocket routes, the CLI, the gallery refresh and the Pages bundle
producer become thin callers of it.

## Decisions

### Module and callers

1. `tuba/project/` (growing from `tuba/project.py`) is the only owner of:
   loading a project folder, running its model script, writing generated model
   scripts, solve-or-import with reuse, study checks, evidence layout, staging
   evidence into review bundles, the Standard review, freshness per operation,
   build and review bundle publishing, and the solve claim.
2. MCP tools become one call each and keep no module globals. The MCP process
   sends no viewer events.
3. The studio keeps its HTTP/WebSocket transport, a pure mapping from state
   changes to viewer events, and a watcher that calls `sync()`.
4. The CLI is `python -m tuba.project <folder> --output DIR [--force]`;
   `--artifact-dir` goes, because a solve that reuses matching evidence is an
   import. `python -m tuba.cli_studio` accepts a project folder only.

### Model scripts

5. Two kinds, decided by the generated header. A generated model script is
   owned by a session, which may rewrite it after each change. An authored
   model script opens read-only: inspect, solve and export work; edits refuse.
6. An edit applies to a copy of the model, generates the script, proves that
   running it reproduces an identical `to_dict()`, and only then writes.
7. A script save carries `based_on`, the hash of the text the browser last saw;
   a session never overwrites text that changed since.
8. Model-script runs never overlap within a process.
9. A generated model script is a hybrid: one public call per node, element,
   support, load case and operation (so source-line links work), plus one exact
   data block for records without a public call (groups, specs other than
   insulation, I-beam properties).

### Evidence

10. Evidence lives in `<project>/evidence/<operation>/`, always one folder per
    operation. `ARTIFACT_DIR` is retired. The five notebook-only evidence
    folders under `notebooks/code_aster_results/` stay where they are.
11. Every solve (studio, MCP, CLI, refresh) writes there once the study's
    checks pass. A failing check writes nothing.
12. Within a solve, files are promoted first and `study_execution.json` last;
    a solve writes all of its operations or none.
13. A solve reuses evidence whose attested fingerprint matches, unless forced.
    The studio's Solve solves only stale or absent operations; "Solve again"
    forces. A refresh is a forced solve.
14. The Project copies each operation's evidence into the review bundle's
    `artifacts/<operation>/` before any review hook runs.

### Freshness

15. A review is stale when, for any operation, the expected identity differs
    from the attested one. The expected identity comes from the current model
    plus the study's current solver options, computed by the same function the
    exporter uses, so a study-option change also makes a review stale.
16. On opening a session whose evidence is stale, Review shows the last
    published review bundle marked stale; without one it shows "not solved for
    this model" until Solve.

### Trust

17. One trust judgement: a run is verified when its attested inventory is
    complete for its profile and it was not executed through Docker. All 14
    committed evidence folders were executed through WSL and stay verified.
18. Unverified runs are written and shown visibly unverified; the viewer gains
    a marker, since it shows no trust information today. A refresh and the
    Pages producer require verified runs, so a refresh never writes an
    unverified run.
19. `export_tensor_stress=False` everywhere, matching the committed tee
    evidence.

### Concurrency

20. A solve claims `<project>/.tuba/solve.lock` (atomic create, heartbeat);
    another process gets `busy` and both report `solving`. A claim with no
    heartbeat for 60 s counts as a crash and is broken. `.tuba/` is ignored by
    git.
21. Edits continue during a solve; the solve works on a snapshot, and its
    review arrives already stale if the model changed meanwhile.
22. A review build that fails records its inputs, so the watcher does not
    retry the same failure every tick.

### Study contract (`study.py`, every name optional)

23. `OPERATIONS` (default: every operation of the model), `SOLVER_OPTIONS`
    (absorbs `VOLUME_EXPORT`), `check(solved)` and `review(ctx)`, each hook
    taking one object. `ctx.standard_review(**options)` writes the Standard
    review. Without a study: every operation, default options, Standard review.
    `LOAD_CASES`, `ARTIFACT_DIR`, `VOLUME_EXPORT` and `build_review` are retired.
24. `run_example` moves into `tuba` as the Standard review; five of nine
    studies shrink to declarations.

### Deleted surfaces

25. Plain `StudioServer`, `/api/patch`, `/api/model`, the WebSocket
    `client_patch`/`client_model_update` messages, MCP sessions saved as
    `model.json`, and the file form of `cli_studio`.
26. `python -m tuba.visualization.preview watch|watch-patch`,
    `PatchPreviewServer`, the subprocess runner (`_runner.py`) and the `show_*`
    capture helpers.

### Scope

27. One machine, both processes in the same environment (both Windows or both
    WSL), a project folder on a local disk (ADR 0003).

## Interface

```python
session = open_session(folder, *, create=None, study="study.py", bundles=None, solver=None)
session.state                     # frozen State; `solving` is also true while another process holds the claim
session.run(code, *, based_on)    # an engineer's script save
session.edit(change)              # a tool edit; generated model scripts only
session.solve(*, force=False, wait=True)
session.sync()                    # adopt outside edits and newly landed evidence
```

`State` carries at least: project name, script text, `read_only`, `revision`,
the last good model, script error and line, `operations`, `unsolved` (absent or
stale), `unverified`, `solving`, solve error, `reviewing`, review bundle path
and revision, review error, and `review_stale` (derived).

`solver` is a port with two adapters: Code_Aster runtime discovery (python
bridge, command, WSL, Docker) in production, and a replay adapter in tests that
copies committed real evidence whose fingerprint matches.

```python
# study.py
OPERATIONS = ("Cold",)
SOLVER_OPTIONS = {"pipe_modelization": "POU_D_T", "load_path": ...}
def check(solved): ...            # solved.model, solved.namespace, solved.runs[operation]
def review(ctx): ctx.standard_review(title="...")   # ctx.runs already point into bundle/artifacts/<op>/
```

Error modes: a script error is reported with its line and keeps the last good
model; an outside edit, an edit on a read-only session and a busy solve raise
without writing; a missing Code_Aster runtime or a failed study check fails the
solve and writes no evidence; an unverified run is written and flagged.

## Testing

- No fabricated results: the Project solve is tested through the replay
  adapter over committed real evidence (support-rack, 1.2 MB).
- Deleted with their code: the JSON-route, `PatchPreviewServer`, subprocess
  runner and `StudioServer` patch/staleness tests.
- Kept as transport tests with real sockets: cross-origin refusal, an idle
  WebSocket surviving, port refusal, one studio smoke test.
- Rewritten against the session: studio project tests, MCP tool tests, the
  gallery refresh tests, `test_examples.py` and
  `test_code_aster_artifact_import.py`, and the Pages catalog test.
- New: expected identity equals the committed attestation for every gallery
  project; stale after a model edit and after a study-option change; a failed
  check writes nothing; reuse vs force; unverified written but refused by a
  refresh; a second solve on one folder is busy; `based_on` refusal; read-only
  authored session; last review bundle adopted on open; state-to-event mapping
  as a table; generated-script round trip for every example project.
- Real Code_Aster suites stay as they are.

## Migration roadmap

Seven plans, each written after the previous one lands so it cites the real
code. Each step keeps the suite green and gets its own commits.

1. Retire the JSON editing and script-preview surfaces (decisions 25–26).
2. One generated-model-script module (decisions 5–6, 9).
3. Move gallery evidence to `examples/<id>/evidence/<operation>/` (decision 10).
4. Freshness and trust: expected identity, one trust judgement,
   `export_tensor_stress=False` (decisions 15, 17, 19).
5. Project solve: solver port, reuse and force, study checks, promotion,
   solve claim (decisions 11–13, 18, 20).
6. Study contract and Standard review, staging, gallery, refresh, CLI, Pages
   validator, viewer unverified marker (decisions 4, 14, 23–24).
7. Authoring session: `open_session`, MCP and studio as callers, viewer tweaks
   (decisions 1–3, 7–8, 16, 21–22).

Run the Linux Pages check before pushing steps 3 and 6, since both change what
Pages builds.

## Out of scope

- The Ground grid overlay toggle not hiding the grid, `imposed_displacement`
  being accepted but never serialized or applied, and `model_revision` always
  being 0.
- Authoring across machines (ADR 0003).
- The viewer's live `scene_diff` WebSocket handling, which no Python process
  sends once the MCP broadcast is gone.

## Open questions

- `tuba.visualization.live_preview` (`preview_json_patch`,
  `preview_python_script`) has no production caller after plan 1 but is a
  public export with its own tests. Delete it, or keep it as the dry-run API for
  agent proposals?
