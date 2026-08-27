# Visualization Architecture Deepening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` and `superpowers:test-driven-development`. Implement one task at a time; do not spawn further agents.

**Goal:** Centralize official gallery ownership, make `AnalysisRun` the high-level verified publication input, and route viewer UI state changes through the existing reducer.

**Architecture:** One immutable official-gallery record set will drive Pages publication and real Code_Aster refresh. The web review path will accept provenance-bearing `AnalysisRun` records and remove its raw `FEAResults` adapter; `FEAResults.plot_*()` remains the separate PyVista quick-look path. The existing `reduceViewerState` function will become the only UI state mutation seam without adding a store framework.

**Tech stack:** Python 3.10+, pytest, JavaScript ES modules, Node's built-in test runner, existing Code_Aster/runtime contracts

**Design source:** `docs/superpowers/specs/2026-07-29-visualization-publication-and-documentation-design.md`

## Global constraints

- Preserve the product sequence: Tuba model -> external Code_Aster solve -> attested artifact import -> processed result display.
- Keep exactly the two existing result-display paths: `tuba/plotting/` for PyVista quick-look/export and `tuba/visualization/` plus `viewer/` for reviewable web scenes.
- Never publish raw, fabricated, proxy, or export-only values as solved results.
- Reuse existing modules and dependencies. Add no framework, package, factory layer, or third visualization path.
- Treat this as a cleanup, not a compatibility exercise: trace every live caller, migrate it in the same task, and delete the superseded code instead of keeping aliases, wrappers, parallel lists, or deprecated entry points.
- Prefer a net reduction in executable LOC across each affected ownership area. Any unavoidable added line must replace caller knowledge or duplicated policy; reviewers must call out avoidable additions.
- Write each behavioral test first, run it, and record the expected RED before the minimum GREEN implementation.
- Preserve the untracked `logs_82787023332.zip`; do not stage, modify, or delete it.
- Work in the user's current `main` checkout as explicitly requested. Keep commits local and do not push.
- Each task must leave its focused tests green and create one local commit containing only its intended paths.

---

### Task 1: Make one official-gallery module authoritative

**Files:**
- Create: `scripts/official_gallery.py`
- Modify: `scripts/build_pages.py`
- Modify: `scripts/refresh_code_aster_gallery.py`
- Modify: `.github/workflows/ci.yml`
- Modify: `.github/workflows/release.yml`
- Modify: `CONTEXT.md`
- Test: `tests/test_code_aster_gallery_refresh.py`
- Test: `tests/test_pages_build.py`
- Test: `tests/test_official_viewer_publication.py`
- Test: `tests/test_release_metadata.py`

**Interfaces and ownership:**
- Define one frozen `OfficialGallery` record and one ordered `OFFICIAL_GALLERIES` tuple in `scripts/official_gallery.py`.
- Each record owns the existing facts needed by both consumers: bundle ID, audiences, publication profile, bundle producer, canonical Code_Aster artifact directory when engineering results are required, model/load-case producer when refreshable, and whether the existing volume export is required.
- Keep the five current bundle IDs and their current order. The imported-component model review remains non-refreshable.
- `scripts/build_pages.py` imports the record set and derives its Pages bundle IDs, required `viewer/<id>/scene.json` paths, and build iteration from it. Do not retain parallel hand-maintained gallery lists.
- Delete `OFFICIAL_EXAMPLES` and every separately maintained Pages/gallery ID or required-scene list after their consumers use the record set; do not re-export compatibility aliases for tests.
- `scripts/refresh_code_aster_gallery.py` selects the same records. Preserve `refresh_gallery(output, gallery=...)` for a single gallery and add `refresh_all_galleries()` plus CLI `--all` to use each record's canonical artifact directory.
- `--all` must reject `--gallery` or `--output`; single-gallery mode must retain explicit `--output` and reject a non-refreshable gallery.
- The attestation validator must continue to require matching non-null solver identities, `solver_name == "Code_Aster"`, non-empty solver version, and non-empty solve timestamp. Remove only the WSL-specific execution-method restriction so the existing native/runtime adapters remain valid.
- CI and release replace the four repeated refresh commands with one `uv run python scripts/refresh_code_aster_gallery.py --all` command before Pages validation/build.

- [ ] **Step 1: Write failing ownership and CLI tests**

Add behavioral tests proving that the ordered record set drives Pages IDs and required scene paths, all four engineering records have canonical artifact paths and refresh metadata, the model-only record cannot refresh, and `refresh_all_galleries()` passes every engineering record to the existing solve/import flow.

Update the attestation test so a real non-WSL execution method is accepted while missing solver name/version/timestamp or mismatched identity still fails. Update workflow assertions to require exactly one `--all` refresh command per solver-backed job.

- [ ] **Step 2: Run the tests and record RED**

Run:

```powershell
uv run python -m pytest tests/test_code_aster_gallery_refresh.py tests/test_pages_build.py tests/test_official_viewer_publication.py tests/test_release_metadata.py -q
```

Expected: FAIL because `scripts.official_gallery`, `refresh_all_galleries`, and CLI `--all` do not exist and the current validator rejects non-WSL attestations.

- [ ] **Step 3: Move existing gallery facts and producers into the authoritative record set**

Move the five existing `_build_*` producer functions out of `build_pages.py`; reuse their bodies unchanged except for record-owned canonical artifact selection. Move the existing gallery model/load-case selection behind the four refreshable records. Keep the volume-specific element IDs, mesh size, and export call on the existing tee path.

Use simple derived values in `build_pages.py`, for example:

```python
PAGES_GALLERIES = tuple(gallery for gallery in OFFICIAL_GALLERIES if "pages" in gallery.audiences)
PAGES_BUNDLE_IDS = tuple(gallery.id for gallery in PAGES_GALLERIES)
```

- [ ] **Step 4: Add all-gallery refresh and loosen only the runtime-adapter restriction**

Implement the small loop over refreshable records. Keep artifact deletion, real solver invocation, import, and full artifact-chain validation in `refresh_gallery`; do not introduce another solver path.

- [ ] **Step 5: Update CI, release, and domain vocabulary**

Replace the repeated workflow commands. Add an `Official gallery` entry to `CONTEXT.md` using the existing glossary format, defining it as the centrally registered, validated publication record and warning against parallel lists.

- [ ] **Step 6: Verify focused behavior**

Run the Step 2 command. Expected: PASS.

- [ ] **Step 7: Commit only Task 1 paths**

```powershell
git add scripts/official_gallery.py scripts/build_pages.py scripts/refresh_code_aster_gallery.py .github/workflows/ci.yml .github/workflows/release.yml CONTEXT.md tests/test_code_aster_gallery_refresh.py tests/test_pages_build.py tests/test_official_viewer_publication.py tests/test_release_metadata.py
git commit -m "refactor: centralize official gallery ownership"
```

---

### Task 2: Publish verified results through AnalysisRun

**Files:**
- Modify: `tuba/visualization/builders/_core.py`
- Modify: `tuba/visualization/builders/_results.py`
- Modify: `tuba/visualization/builders/_helpers.py` only if raw-result helpers become unused
- Modify: `tuba/reporting/builder.py`
- Modify: `examples/code_aster_artifact_review.py`
- Modify: `examples/code_aster_tee_volume_review.py`
- Test: `tests/test_visualization_results.py`
- Test: `tests/test_solver_input_provenance.py`
- Test: `tests/test_reporting_builder.py`
- Test: `tests/test_official_viewer_publication.py` only if example publication coverage requires it

**Interfaces and ownership:**
- Add keyword-only `analysis_runs: Iterable[AnalysisRun] = ()` to `build_visualization_scene` and `build_engineering_review`.
- In the scene builder, derive `result_states` and non-null `analysis_meshes` from the supplied runs, then use the existing ResultState/AnalysisMesh validation and rendering pipeline.
- In the review builder, derive studies, non-null analysis meshes, and result states from the supplied runs, then use the existing lineage validation and table pipeline.
- Reject mixing a non-empty `analysis_runs` input with the corresponding lower-level record inputs. Keep lower-level inputs for focused validation tests and historical/malformed record review.
- Remove `solver_results` and `result_deformation_scale` from the web scene public signature, delete `_build_solver_result_scene` and raw-`FEAResults`-only helpers/imports, and keep `FEAResults` in `tuba/plotting/` and `AnalysisRun.results`.
- Delete every helper that becomes unreachable with the raw web-result adapter; do not leave a dormant legacy path or a forwarding shim.
- Update the two solved official examples to pass `analysis_runs=[artifact]`; continue passing geometry states, notes, route/load-path context, timestamps, and package IDs exactly as before.

- [ ] **Step 1: Write failing AnalysisRun publication tests**

Add behavior tests that an imported/constructed valid `AnalysisRun` produces the same authoritative scene result-state and analysis-mesh records and the same review provenance/tables as the lower-level records. Add tests that mixing `analysis_runs` with lower records fails with a clear `ValueError` or `EngineeringReviewError`.

Replace raw solver-result scene tests with a public contract test that `solver_results=` is rejected by Python's signature and a ResultState/AnalysisRun test that still renders deformation, stress, and reaction overlays from verified records.

- [ ] **Step 2: Run the tests and record RED**

Run:

```powershell
uv run python -m pytest tests/test_visualization_results.py tests/test_solver_input_provenance.py tests/test_reporting_builder.py tests/test_official_viewer_publication.py -q
```

Expected: FAIL because neither builder accepts `analysis_runs` and the web scene still accepts raw `FEAResults`.

- [ ] **Step 3: Expand AnalysisRun at the two existing validation seams**

Materialize each iterable once. Keep all existing model revision, compiler identity, mesh identity, solve attestation, and Code_Aster lineage checks; do not copy or weaken them.

- [ ] **Step 4: Delete the raw web-result adapter and update solved examples**

Remove only helpers exclusively reachable from `_build_solver_result_scene`. Do not alter ResultState overlay construction or the PyVista plotting API.

- [ ] **Step 5: Verify focused behavior**

Run the Step 2 command. Expected: PASS.

- [ ] **Step 6: Commit only Task 2 paths**

```powershell
git add tuba/visualization/builders/_core.py tuba/visualization/builders/_results.py tuba/visualization/builders/_helpers.py tuba/reporting/builder.py examples/code_aster_artifact_review.py examples/code_aster_tee_volume_review.py tests/test_visualization_results.py tests/test_solver_input_provenance.py tests/test_reporting_builder.py tests/test_official_viewer_publication.py
git commit -m "refactor: publish verified analysis runs"
```

---

### Task 3: Route viewer UI mutations through the reducer

**Files:**
- Modify: `viewer/src/viewerState.js`
- Modify: `viewer/src/app.js`
- Test: `viewer/test/viewer-state.test.js`
- Test: `viewer/test/workflow-rendering.test.js` only for an app-visible regression

**Interfaces and ownership:**
- Keep `reduceViewerState(state, action)` as the sole UI state mutation seam. Add only the action cases required by current `app.js` behavior.
- Reuse existing pure functions from `controls.js`, `selection.js`, `sceneLoader.js`, `coloring.js`, `resultReview.js`, `units.js`, and `sceneDiff.js`; do not move their domain logic into the reducer.
- Route selection, hide/isolate/restore, section box, layer/task visibility, result controls, coloring, active geometry/load/result state, unit/body controls, issue review, and live-preview scene diff/diagnostic changes through reducer actions.
- Camera renderer methods, transient DOM-only controls, WebSocket lifecycle, hover state, validation messages, and render calls are not viewer-state mutations and stay in `app.js`.
- Delete the unused `createViewerStore`; add no Redux-style store or dependency.
- Delete direct app imports that are superseded by reducer actions and collapse repeated dispatch boilerplate into the one local `dispatch` function only when it reduces LOC.
- Preserve existing action names when available. Add direct action names such as `selectObject`, `hideSelected`, `isolateSelection`, `setSectionBox`, `applyTaskVisibilityPreset`, and `appendDiagnostic` only where `app.js` currently invokes the corresponding existing pure helper.

- [ ] **Step 1: Write failing reducer behavior tests**

Extend `viewer-state.test.js` with compact state-transition tests for the current app mutations that bypass the reducer: additive selection, hide/isolate/restore, section box set/clear, task visibility preset, active geometry state, and preview diagnostic append. Assert observable state and visibility results, not source text or internal implementation.

- [ ] **Step 2: Run the reducer tests and record RED**

Run from `viewer/`:

```powershell
npm.cmd test -- --runInBand viewer-state.test.js
```

Expected: FAIL because the new actions are not handled.

- [ ] **Step 3: Add minimal reducer actions by delegating to existing pure helpers**

Import only the helpers needed by action cases. Keep the reducer pure and return the original state for unknown actions.

- [ ] **Step 4: Replace app-level state helper calls and object-spread mutations with reducer dispatches**

Use a tiny local function if it reduces repetition:

```javascript
function dispatch(action) {
  currentState = reduceViewerState(currentState, action);
  return currentState;
}
```

Do not introduce subscriptions, middleware, or a new state object. Remove imports from `app.js` when their only use moved behind the reducer.

- [ ] **Step 5: Verify viewer behavior**

Run from `viewer/`:

```powershell
npm.cmd test
```

Expected: all viewer tests PASS.

- [ ] **Step 6: Commit only Task 3 paths**

```powershell
git add viewer/src/viewerState.js viewer/src/app.js viewer/test/viewer-state.test.js viewer/test/workflow-rendering.test.js
git commit -m "refactor: centralize viewer state mutations"
```

---

## Final verification

After all three task reviews approve:

```powershell
uv run python -m pytest tests/test_code_aster_gallery_refresh.py tests/test_pages_build.py tests/test_official_viewer_publication.py tests/test_release_metadata.py tests/test_visualization_results.py tests/test_solver_input_provenance.py tests/test_reporting_builder.py -q
```

```powershell
Set-Location viewer
npm.cmd test
```

Also run `git diff --check`, inspect `git status --short`, and confirm `logs_82787023332.zip` remains untouched. A final independent reviewer must inspect the complete implementation diff against this plan before completion is claimed.

The final review must also run `rg` for deleted legacy symbols (`OFFICIAL_EXAMPLES`, `_build_solver_result_scene`, `solver_results=`, `result_deformation_scale`, and `createViewerStore`) in live source/tests, explain any intentional historical-document match, and compare executable-line additions/deletions for avoidable growth.
