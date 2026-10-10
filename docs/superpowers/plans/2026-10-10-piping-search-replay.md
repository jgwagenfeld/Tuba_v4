# Piping Search Replay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deliver M2 interactive, evidence-backed search replay in the existing viewer.

**Architecture:** A read-only Python exporter composes M1 history and native scene/review bundles. A focused viewer module projects events at a cursor and owns the replay panel; `app.js` connects its navigation and findings to the existing scene loader and selection/result controls. The existing launcher serves the package.

**Tech Stack:** Existing Python/SQLite/JSON/pytest and JavaScript/Three.js/Node test/Playwright/Vite. No additional dependency.

**Spec:** [Interactive piping search replay](../specs/2026-10-10-piping-search-replay-design.md).

**Execution:** All three tasks completed. Fresh final review and regression-driven
fixes are recorded with source/build/native-artifact provenance in
`D:/tuba-runs/Tuba_v4/search-replay-m2-20261010/qualification.json`.

## Global Constraints

- Python support remains `>=3.11,<3.15`.
- Use `tuba/visualization/` and `viewer/`; no new renderer or frontend dependency.
- Authored procedural source and the retained search archive are read-only.
- Engineering results come only from inventory-verified, publication-validated native Code_Aster artifacts. A missing artifact disables that result view.
- Commit locally; never push. Reuse the existing isolated worktree, dependencies and shared caches; generated packages/builds/logs remain outside tracked source.

## Review Focus

1. A timeline cursor precedes evaluation or selection: future checks/results/outcomes must not leak (Task 2).
2. An interrupted attempt precedes a successful retry: earlier scope and missing artifacts remain distinct (Tasks 1 and 2).
3. A candidate has no geometry, a missing parent or a cyclic ancestry record: retain readable records without stale geometry or an infinite walk (Tasks 1 and 2).
4. A bundle/evidence URL uses traversal, encoded traversal or an active scheme: refuse it before fetch/navigation (Tasks 2 and 3).
5. Rapid candidate switches or a cold check after a hot check: the displayed candidate, operation/state and highlight must remain coherent (Tasks 2 and 3).

### Task 1: Native replay package and CLI

**Files:** create `tuba/search/replay.py`, `tests/test_search_replay.py`; modify `tuba/search/__init__.py`, `tuba/search/__main__.py`.

**Interfaces:** consumes `export_history`, `inspect_history`, `write_candidate_review`, native `SceneRequest`/`write_scene_bundle`; produces `write_search_replay(run_dir: Path, output_dir: Path) -> Path` and `python -m tuba.search replay --run-dir <run> --output <new-dir>`.

- [ ] Write failing tests using `tests.test_search_export.completed`: export retains both candidates and scoped attempts, previews contain no result fields, native review operations remain intact, history bytes are unchanged, unavailable geometry/evidence is explicit, existing output is refused, CLI works without `StudySettings.solver`.

```python
manifest = write_search_replay(completed(tmp_path), tmp_path / "replay")
data = json.loads(manifest.read_text())
assert data["schema"] == "tuba.search.viewer.v1"
assert len(data["candidates"]) == 2
assert data["candidates"][0]["attempt_reviews"][0]["availability"] == "available"
```

- [ ] Run `python -m pytest tests/test_search_replay.py -q`; confirm missing API fails.
- [ ] Implement native previews, existing review composition, per-attempt diagnostics, common magnitude ranges and CLI/public API. The exporter never solves.
- [ ] Run `tests/test_search_replay.py tests/test_search_export.py tests/test_search_cli.py`; read the actual totals.
- [ ] Commit owned paths as `feat(search): export native interactive replay packages`.

### Task 2: Temporal projection and replay panel

**Files:** create `viewer/src/searchReplay.js`, `viewer/src/searchReplayPanel.js`, `viewer/test/search-replay.test.js`.

**Interfaces:** consumes `tuba.search.viewer.v1`; produces `loadSearchReplay(url, fetcher)`, `replayAt(manifest, sequence)`, `parameterDiff(candidate, reference)`, `safeReplayUrl(base, relative)`, `initSearchReplay(container, {manifest, baseUrl, showView, highlight, getState})`.

- [ ] Write Node tests for events before/after proposal/evaluation/selection, every attempt's own decision, missing/cyclic parents, parameter changes and strict URL confinement.

```javascript
const at = replayAt(manifest, beforeSelection);
assert.equal(at.candidates.find(c => c.id === "C1").outcome, "feasible_retained");
assert.equal(at.candidates.some(c => c.id === "C2"), false);
assert.throws(() => safeReplayUrl(base, "%2e%2e/secret"));
```

- [ ] Run `node --test test/search-replay.test.js`; confirm missing module fails.
- [ ] Implement bounded manifest validation/projection; build accessible DOM controls with `textContent`, scoped check/evidence links, parent/reference navigation, event/attempt stepping and latest-request protection. No new rendering canvas.
- [ ] Run Node replay, review-selection, result-review, viewer-state and scene-loader tests.
- [ ] Commit owned paths as `feat(viewer): project retained search events and explanations`.

### Task 3: Integrate, launch and qualify M2

**Files:** modify `viewer/src/app.js`, `viewer/index.html`, `viewer/src/styles.css`, `tuba/visualization/viewer.py`, `tests/test_viewer_launcher.py`, `docs/content/piping-search.md`, `docs/architecture/piping-search-roadmap.md`; create `viewer/scripts/search-replay-smoke.mjs`.

**Interfaces:** panel `showView` loads a scoped bundle with the existing loader; `highlight` uses existing entity resolution/result-state actions; launcher adds the `search` query parameter and safe default native scene.

- [ ] Write launcher tests for replay packages, no-viewable-scene records, malformed manifest and confined default scene paths. Write browser assertions for hot rejection C0005, force rejection C0007, selected C0009, an interrupted retry, cold geometry, event causality, parameter comparisons and rapid switches.
- [ ] Run launcher tests and browser test against the previous viewer build; confirm the missing replay behavior fails.
- [ ] Wire the existing viewer, add a Search section/style, preserve camera/units/common magnitude scale, clear stale views, select exact finding states and safely serve replay packages.
- [ ] Build once to `D:/tuba-runs/Tuba_v4/search-replay-m2-20261010/viewer-build` using the shared npm dependencies and browser runtime cache, without rewriting tracked packaged assets. Generate the real replay once from qualification archive 03, run the smoke test and preserve screenshots/logs.
- [ ] Run all affected Node tests plus Python replay/export/CLI/launcher tests. Update the guide/roadmap with measured validation and run commands.
- [ ] Commit owned paths as `feat(viewer): launch and qualify interactive piping search replay`.

## Final review and handoff

Use one fresh final reviewer for the M2 commit range only. Fix Important/Critical findings in one regression-driven pass; defer Minor findings explicitly. Preserve final source, manifests, small logs, screenshots and native replay package outside source. Keep the local isolated branch; report measured retained bytes and drive free space. The previous cleanup policy rejection is retained as evidence; do not bypass it.
