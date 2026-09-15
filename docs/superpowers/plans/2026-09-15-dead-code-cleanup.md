# Dead Code and Unused Capabilities Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete the dead code the 2026-09-15 architecture review found, plus three documented but unused capabilities, without changing any live behaviour.

**Architecture:** Deletion only, in five tasks that each own a separate set of files: the viewer with its packaged build, Python dead code, the compliance-report channel, network routing with routing spaces, and the test-only scene features with BCF. Every item is searched for callers again before it goes, because the review's line numbers come from main at f0ebb82 and earlier tasks shift them.

**Tech Stack:** Python 3 with pytest; the browser viewer in plain JavaScript (Three.js), tested with `node --test` and built with Vite.

**Spec:** the 2026-09-15 architecture review (an HTML report in the session scratchpad, deliberately not committed) and the user's decisions below. The deletion evidence for each item comes from five read-only explorers run on main at f0ebb82.

## Decisions (the user, 2026-09-15)

- Delete Tier 1: code with no production caller.
- Delete from Tier 2: the compliance-report channel; network routing and routing spaces; the test-only scene features (agent proposals, external sources, runtime states, point clouds, scene materials and styles) together with BCF.
- Out of scope: legacy examples and facade trims (not chosen); the studio server's dead routes (wait for Plan 6a); model fragments, the future-ready demo chain and the small support-area duplicates (wait for support-attachment); `model_revision` (needs a re-solve); `parse_result_artifacts`, which is the test surface for validated parsing (the result-reader candidate replaces it); `has_wind_load`, which lives in `tuba/solver/aster_comm.py`.

## Global Constraints

- Deletion only. Remove each listed item and whatever exists only to serve it: imports, re-exports, `__all__` entries, tests, fixtures, docs rows. Change no live behaviour. Where an item is a pass-through, its callers call the target directly.
- Search before you delete. Run the item's search; if it finds a caller outside tests and docs that this plan does not name, keep the item and report it as a concern.
- ADR 0002 stays enforced. Keep `compliance_role: "visualization_only_not_asme_code_stress"` in `tuba/analysis/results.py` and `tuba/visualization/builders/_results.py`, and keep the viewer's notice for it: `getComplianceNotice` and `shouldShowComplianceNotice` in `viewer/src/coloring.js`, `renderComplianceNotice` in `viewer/src/app.js`.
- ADR 0002 legacy loading stays tolerant. `VisualizationScene.from_dict` must still load a scene dict that carries a removed key; the key lands in `extra` and comes back out of `to_dict`.
- Files owned by work in flight (Plan 6a, support-attachment) are not edited: `tuba/project/**`, `tuba/visualization/preview/server.py`, `tuba/mcp/server.py`, `scripts/build_pages.py`, `scripts/official_gallery.py`, `scripts/refresh_code_aster_gallery.py`, `tuba/patches.py`, `tuba/fragments.py`, `tuba/builder.py`, `tuba/validation.py`, `tuba/load_path.py`, `tuba/solver/aster_comm.py`, `tuba/solver/aster_contact.py`, `tuba/solver/aster_mesh.py`, `tuba/solver/aster_loads.py`, `tuba/solver/modelisation.py`, `tuba/solver/contact_results.py`, `examples/support-rack-review/**`, `examples/future_ready_semantic_workflow.py`, `tests/test_future_ready_integration.py`. One exception: Task 3 edits the compliance code in `tuba/reporting/tables.py` and nothing else in that file (its support rows, around lines 246-290, belong to support-attachment).
- History records stay as written: do not edit `docs/architecture/**` or `docs/superpowers/**`.
- Environment (Windows, worktree `D:/tmp/tuba-cleanup`): Python tests run from the worktree root with `D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest <paths> -q`. Viewer unit tests run in `viewer/` with `node --test`. The packaged viewer is rebuilt in `viewer/` with `node node_modules/vite/bin/vite.js build`, which rewrites `tuba/visualization/_viewer/`; commit the result. Searches over `viewer/` exclude `node_modules`. Never use `git stash`.
- Tests: run the tests your task lists. The controller runs the full suite (about 21 minutes) once, after Task 5.
- Commits: the repository's conventional style (for example `refactor(viewer): delete the live scene-diff path`), no trailers.

---

### Task 1: Viewer dead code, and the viewer side of the removed channels

**Files:**
- Delete: `viewer/src/sceneDiff.js`, `viewer/scripts/make_bundle.py`, `viewer/test/fixtures/patch_preview_scene/` (once nothing reads it)
- Modify: `viewer/src/app.js`, `viewer/src/viewerState.js`, `viewer/src/sceneLoader.js`, `viewer/src/controls.js`, `viewer/src/reviewTables.js`, `viewer/src/reviewSelection.js`, `viewer/src/renderer.js`, `viewer/src/selection.js`, `viewer/src/resultReview.js`, `viewer/src/workflowState.js`, `viewer/scripts/e2e-smoke.mjs`, `tuba/solver/mesh_study.py` (docstring only)
- Test: `viewer/test/viewer-state.test.js`, `viewer/test/controls.test.js`, `viewer/test/review-tables.test.js`, `viewer/test/review-selection.test.js`, `viewer/test/renderer.test.js`, `viewer/test/selection.test.js`, `viewer/test/scene-loader.test.js`, `viewer/test/workflow-rendering.test.js`
- Rebuild: `tuba/visualization/_viewer/**`

**Interfaces:**
- Consumes: nothing.
- Produces: a viewer that no longer reads `scene.scene_diffs`, `scene.agent_proposals`, the `code_compliance` review table, runtime-state overlays or `issue.external_refs.bcf`. Tasks 3 and 5 delete the Python producers of those.

- [ ] **Step 1: Confirm nothing sends the retired messages**

```bash
grep -rn -E "scene_diff|run_started|run_finished" tuba/visualization/preview/server.py tuba/mcp/server.py
grep -rn -E "live-preview|patch-preview|scene-diff" .github/workflows viewer/package.json
```
Expected: no output from either command. CI runs only the `section-camera`, `legacy-workflow`, `pages-catalog` and `pages-gallery` scenarios plus `e2e:pages`.

- [ ] **Step 2: Delete the live scene-diff path**

Delete `viewer/src/sceneDiff.js`; its reducer case in `viewer/src/viewerState.js` (around lines 61-87); the `scene_diff` message handler in `viewer/src/app.js` (around 2590-2611); the state fields in `viewer/src/sceneLoader.js` that only the diff path reads (`agentProposals` around line 149, `sceneDiffs` around 150, and any other field whose only reader was `sceneDiff.js`); the scene-diff tests in `viewer/test/viewer-state.test.js` (around 260-317 and 484-735); the `scene-diff` scenario in `viewer/scripts/e2e-smoke.mjs` (around 1486-1556).

```bash
grep -rn --exclude-dir=node_modules -E "sceneDiff|sceneDiffs|agentProposals|scene_diffs" viewer
```
Expected after the deletion: no output.

- [ ] **Step 3: Delete the retired preview messages**

Delete the `run_started`, `diagnostic` and `run_finished` handling in `viewer/src/app.js` (around 2538-2552 and 2612-2614); the `appendDiagnostic` reducer case in `viewer/src/viewerState.js` (around 142-143) once nothing dispatches it; the `__tubaViewerPreviewEvents` plumbing in `app.js` (around 200, 2352, 2534-2537 and 2581); the `live-preview` and `patch-preview` scenarios in `viewer/scripts/e2e-smoke.mjs` (around 1403-1485); the fake WebSocket helper (around 1712-1793) once no remaining scenario calls it; `viewer/test/fixtures/patch_preview_scene/` once no remaining test or scenario reads it.

```bash
grep -rn --exclude-dir=node_modules -E "run_started|run_finished|appendDiagnostic|__tubaViewerPreviewEvents|patch_preview_scene" viewer
```
Expected after the deletion: no output.

- [ ] **Step 4: Delete exports only tests use**

- `viewer/src/controls.js`: `searchObjects`, `filterObjects`, its own `setOverlayVisibility` (the reducer imports the one in `bodies.js`), `setRuntimeState` with `activeRuntimeState`, `measureDistanceBetweenObjects`, and helpers used only by these; their tests in `viewer/test/controls.test.js` (around 294-318 and 431-460).
- `viewer/src/reviewTables.js`: the helpers no module imports (around 30-83, `cellViewModel` through `isMapping`) and the governing summary fields only `viewer/test/review-tables.test.js` reads (around 111-147).
- `viewer/src/sceneLoader.js`: `loadSceneBundle` (around 5-6 and 15-29). Its tests in `viewer/test/scene-loader.test.js` call `loadSceneBundleFromUrl` with a fetcher that reads the fixture files from disk.
- `viewer/src/reviewSelection.js`: `showReviewEntityIn3d`, its reducer case and the `setWorkflowTab` case; their tests in `viewer/test/review-selection.test.js` (around 183-220).

```bash
grep -rn -E "\b(searchObjects|filterObjects|setRuntimeState|activeRuntimeState|measureDistanceBetweenObjects|showReviewEntityIn3d|loadSceneBundle|cellViewModel|isMapping)\b" viewer/src viewer/scripts viewer/e2e viewer/test
```
Expected before the deletion: definitions and tests only. After: no output.

- [ ] **Step 5: Delete the pass-throughs and the flat pick fallback**

- `createThreeViewport` in `viewer/src/renderer.js` (around 466-504) only delegates: move its visible-object filtering to its one caller in `viewer/src/app.js` (around 2328) and delete it.
- Delete `buildRenderableScene` from `renderer.js` with its test in `viewer/test/renderer.test.js` (around 542-560).
- Delete `dispose()` in `renderer.js` (around 370-381): nothing calls it, and it references `startInteraction` and `endInteraction`, which are defined nowhere.
- Delete `pickObjectAt` with its `project` and `centerOfBounds` helpers in `viewer/src/selection.js` (around 118), the fallback call in `app.js` (around 2426-2430) and its test in `viewer/test/selection.test.js` (around 257-264). The fallback only runs when WebGL2 failed, and it selects objects that are not drawn.

- [ ] **Step 6: Delete mirrors and leftovers**

- `displacementVectorScale` and `reactionVectorScale` copy `resultVectorScales`. Point every read at the matching `resultVectorScales` entry, then delete both fields: `viewer/src/resultReview.js` (around 262-274 and 350-351), the reload list in `viewer/src/viewerState.js`, and `SCENE_GRAPH_STATE_KEYS` in `viewer/src/renderer.js`. What is drawn must not change.
- Delete `resultsStale`: `viewer/src/sceneLoader.js` (around 131-132 and 139), `viewer/src/viewerState.js` (around 195-197), and the stale branches in `viewer/src/app.js` (around 499-533). Nothing writes `results_stale` into a scene. Keep `renderProjectStatusChip`.
- `viewer/src/workflowState.js`: delete the `summary`, `load-cases` and `compliance` tabs, the unused `requiresReview`, the summary preset and the duplicate `getVisibleWorkflowTabs`; delete the dead `summary` target in `app.js` (around 529) and the tab pin in `viewer/test/workflow-rendering.test.js` (around 14-19). The rail offers only the model, results and diagnostics tabs.
- `viewer/src/app.js`: delete the unused DOM keys `viewerWorkspace`, `resultTools` and `layersBlock`, the unused `filterIssues` import and the test-only `sourceUri` (around 13, 100, 120 and 125). Reword the "plain model.json studio" comment (around 220) to describe the project studio.

- [ ] **Step 7: Delete the viewer side of the compliance-report channel, BCF and runtime states**

- `viewer/src/reviewTables.js`: delete the summary computed from `code_compliance` rows (`complianceStatus` and its governing row, around 1-28).
- `viewer/src/app.js`: delete the "Compliance fail" status chip fed by `complianceStatus` (around 505-517), and the "Export BCF" button (around 2304-2309). Keep the status, comment and restore controls appended beside it (around 2319).
- `viewer/src/controls.js`: delete the `bcf` field of the issue summary (around 193) once the button was its only reader.
- Keep the FE-stress notice (see Global Constraints).

```bash
grep -rn -E "code_compliance|complianceStatus|Export BCF|\.bcf\b" viewer/src viewer/test
grep -rn -E "getComplianceNotice|shouldShowComplianceNotice|renderComplianceNotice" viewer/src
```
Expected: the first command prints nothing; the second still finds all three names.

- [ ] **Step 8: Delete the retired bundle script**

Delete `viewer/scripts/make_bundle.py` (it writes model-JSON bundles nothing reads) and remove its mention from the docstring in `tuba/solver/mesh_study.py` (around line 66).

```bash
grep -rn --exclude-dir=node_modules "make_bundle" .
```
Expected: no output.

- [ ] **Step 9: Run the viewer tests**

```bash
cd viewer && node --test
cd viewer && node scripts/e2e-smoke.mjs section-camera
cd viewer && node scripts/e2e-smoke.mjs legacy-workflow
```
Expected: `node --test` passes every test. The two scenarios pass; if Playwright's browser is missing, say so in the report and do not install one.

- [ ] **Step 10: Rebuild the packaged viewer**

```bash
cd viewer && node node_modules/vite/bin/vite.js build
git status --short tuba/visualization/_viewer
```
Expected: the build succeeds and `git status` lists the rebuilt `index.html` and assets.

- [ ] **Step 11: Run the Python tests that read the packaged viewer**

```bash
D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_package_release.py tests/test_viewer_launcher.py tests/test_studio_server.py tests/test_official_viewer_publication.py -q
```
Expected: all pass.

- [ ] **Step 12: Commit**

Commit in logical pieces; the last commit carries the rebuilt packaged viewer.

```bash
git add viewer/src viewer/test viewer/scripts
git commit -m "refactor(viewer): delete the live scene-diff path and retired preview messages"
git add -A viewer tuba/visualization/_viewer tuba/solver/mesh_study.py
git commit -m "refactor(viewer): delete test-only exports, mirrors and the removed channels' views"
```

---

### Task 2: Python dead code in the model, solver, plotting and extension helpers

**Files:**
- Delete: `tuba/clash/report.py`, `tests/test_realtime_visualization_bundle.py`
- Modify: `tuba/model.py`, `tuba/schema.py`, `tuba/solver/aster.py`, `tuba/solver/base.py`, `tuba/plotting/export.py`, `tuba/plotting/pipeline.py`, `tuba/clash/__init__.py`, `tuba/geometry/spatial.py`, `tuba/geometry/deformed.py`, `tuba/quantities.py`, `tuba/rules.py`, `.gitignore`, `.gitattributes`, `docs/content/developer.md`
- Test: `tests/test_tuba_core.py`, `tests/test_code_aster_study.py`, `tests/test_clash_engine.py`, `tests/test_spatial_index.py`, `tests/test_deformed_performance.py`, `tests/test_quantities.py`, `tests/test_rules.py`, `tests/test_realtime_visualization_fixture.py`, `tests/test_mixed_code_aster_export.py`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing later tasks use.

- [ ] **Step 1: Search for callers**

```bash
grep -rn -E "\b(get_allowable|corroded_Z|_try_load_rmed|raw_mesh|export_screenshot|get_section_radius|clash_report_to_dict|clash_report_to_markdown|bounds_overlap|build_deformed_envelope_index|wind_loads|rule_report_to_markdown)\b" tuba scripts examples notebooks docs/content README.md tests
grep -rn -E "(^|[^_a-zA-Z])operation\(" tuba scripts examples notebooks docs/content tests
```
Expected: the definitions, their re-exports and the tests named in the steps below; nothing else. The second command finds only the `TubaModel.operation` alias.

- [ ] **Step 2: Model**

In `tuba/model.py` delete `Material.get_allowable` (around 109-131) with its test in `tests/test_tuba_core.py` (around 25-31), `PipeSection.corroded_Z` (around 184-193) and the `TubaModel.operation` alias of `define_operation` (around 1110-1112).

- [ ] **Step 3: Solver and PLY export**

Delete `CodeAsterSolver._try_load_rmed` (`tuba/solver/aster.py`, around 1267-1284) and `FEAResults.raw_mesh` (`tuba/solver/base.py`, around 122-123) with the test that only covers them (`tests/test_code_aster_study.py`, around 542-563). Delete the `scalar` parameter of `export_ply` (`tuba/plotting/export.py`, around line 91, which hard-codes "VMIS" around line 111) and its pass-through in `tuba/solver/base.py` (around 198-201); update any caller that passes it.

- [ ] **Step 4: The duplicate schema definition**

`MODEL_SCHEMA_V4` defines `"bendGeometry"` twice in one `$defs` literal (around 346-367 and 513-534). Confirm the two are identical:

```bash
D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe - <<'EOF'
import ast, pathlib
tree = ast.parse(pathlib.Path("tuba/schema.py").read_text(encoding="utf-8"))
for node in ast.walk(tree):
    if isinstance(node, ast.Dict):
        hits = [(k.lineno, ast.dump(v)) for k, v in zip(node.keys, node.values)
                if isinstance(k, ast.Constant) and k.value == "bendGeometry"]
        if len(hits) > 1:
            print([line for line, _ in hits], "identical" if len({d for _, d in hits}) == 1 else "DIFFERENT")
EOF
```
Expected: one line such as `[346, 513] identical`. Delete the later copy. If the output says `DIFFERENT`, delete the earlier copy instead (the later one is the one Python uses) and report it.

- [ ] **Step 5: Plotting**

Delete `export_screenshot` (`tuba/plotting/export.py`, around 164-171). In `tuba/plotting/pipeline.py`, replace `get_section_radius` (around 50-54) with direct `collision_radius_for_section` calls, and delete the branches after the early return around line 558 that can no longer run (around 577-582, 584-586 and 617-624). Prove each branch unreachable from the control flow before deleting it, and write the proof in the report.

- [ ] **Step 6: Extension helpers only tests use**

- Delete `tuba/clash/report.py`, its exports in `tuba/clash/__init__.py`, the tests in `tests/test_clash_engine.py` (around 63-75) and the mention in `docs/content/developer.md` (around line 25).
- Delete `bounds_overlap` (`tuba/geometry/spatial.py`, around 67-74) and its test (`tests/test_spatial_index.py`, around 34-35).
- Delete `build_deformed_envelope_index` (`tuba/geometry/deformed.py`, around 74-75) and its test (`tests/test_deformed_performance.py`, around 53-63).
- Delete `wind_loads` (`tuba/quantities.py`, around 77-90; its docstring already says the solver applies something else) and its test (`tests/test_quantities.py`, around 36-45).
- Delete `rule_report_to_markdown` (`tuba/rules.py`, around 117-125) and its test (`tests/test_rules.py`, around 38-45).
- Remove any re-export of these names from package `__init__` files.

- [ ] **Step 7: Duplicate and unreachable tests**

- Fold `tests/test_realtime_visualization_bundle.py` into `tests/test_realtime_visualization_fixture.py`: move any assertion the fixture test lacks, then delete the file.
- Delete the gmsh-missing skips in `tests/test_mixed_code_aster_export.py` (around 74-75 and 226-227). gmsh is a core dependency: `pyproject.toml` lists `"gmsh>=4.11"`.
- Keep the scipy and trimesh import guards in `tests/test_public_api.py`; they pin a dependency boundary.

- [ ] **Step 8: Ignore rules for paths nothing writes**

For each rule below, search `tuba/`, `scripts/`, `examples/`, `tests/`, `viewer/` (without `node_modules`) and `notebooks/*.ipynb` for a writer of that path. Remove the rule only when nothing writes the path; list every kept rule with its writer in the report.
- `.gitignore`: `!docs/site/**`, `code_aster_study/`, `generated/`, `/viewer/public/bundles.json`, the ten `/viewer/public/<gallery>/` rules, the four notebook-output rules for export_demo, visual_check and tuyau_subpoints, `/imported_component_mixed_demo/browser_checks/`, `/piping_model.json`, `/blender_import_tuba.py`, `code_aster_smoke_debug/`, `.benchmarks/`, `/=2.2`.
- `.gitattributes`: `viewer/public/code-aster-review/artifacts/*`.

- [ ] **Step 9: Run the tests**

```bash
D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_tuba_core.py tests/test_code_aster_study.py tests/test_clash_engine.py tests/test_spatial_index.py tests/test_deformed_performance.py tests/test_quantities.py tests/test_rules.py tests/test_realtime_visualization_fixture.py tests/test_mixed_code_aster_export.py tests/test_schema.py tests/test_public_api.py tests/test_static_site_docs.py -q
D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_plotting*.py -q
grep -rln "export_ply" tests
```
Expected: both runs pass. Run every test file the last command lists as well.

- [ ] **Step 10: Commit**

```bash
git add -A tuba tests docs/content
git commit -m "refactor: delete model, solver, plotting and extension code nothing calls"
git add .gitignore .gitattributes
git commit -m "chore: drop ignore rules for paths nothing writes"
```

---

### Task 3: The compliance-report channel

**Files:**
- Delete: `tuba/reporting/compliance.py`, `tests/test_reporting_compliance.py`
- Modify: `tuba/reporting/builder.py`, `tuba/reporting/tables.py` (compliance code only), `tuba/reporting/export.py`, `tuba/reporting/__init__.py`, `docs/content/reference/public-api.md`
- Test: `tests/test_reporting_builder.py`, `tests/test_reporting_export.py`, `tests/test_reporting_model.py`

**Interfaces:**
- Consumes: Task 1, after which the viewer no longer reads the `code_compliance` table.
- Produces: Engineering reviews without a `code_compliance` table. Task 5 edits `tuba/reporting/export.py` after this task.

- [ ] **Step 1: Search for callers**

```bash
grep -rn -E "ComplianceReport|compliance_reports|code_compliance|build_code_compliance_table|compliance_report\b" tuba scripts examples notebooks docs/content README.md tests viewer/src
grep -rn "compliance_role" tuba
```
Expected: the first command finds only `tuba/reporting/*`, the tests named below and `docs/content/reference/public-api.md`. The second still finds `tuba/analysis/results.py` and `tuba/visualization/builders/_results.py`; those stay.

- [ ] **Step 2: Delete the channel**

- Delete `tuba/reporting/compliance.py`.
- `tuba/reporting/builder.py`: delete the `compliance_reports` parameter (around 44) and everything that carries or checks it (around 70, 90-98 including the `build_code_compliance_table` call, 127, 278-305 and 365-377). Where a condition combined compliance with other checks, keep the other checks exactly.
- `tuba/reporting/tables.py`: delete the `compliance_reports` parameters and loops (around 406, 421, 542 and 625-680) and `build_code_compliance_table` (around 685-769, including its SIF and flexibility columns). Change nothing else in this file.
- `tuba/reporting/export.py`: delete the `code_compliance` and `compliance_report` handling (around 233, 386-387 and 580-584).
- Remove the names from `tuba/reporting/__init__.py` and from the pinned `__all__` list in `tests/test_reporting_model.py` (around 164).

- [ ] **Step 3: Tests and docs**

Delete `tests/test_reporting_compliance.py`. Remove the compliance cases from `tests/test_reporting_builder.py` (around 330 and 702) and `tests/test_reporting_export.py` (around 202-226). Remove the compliance-report rows from `docs/content/reference/public-api.md` (around 131-135).

- [ ] **Step 4: Run the tests**

```bash
D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_reporting_*.py tests/test_official_viewer_publication.py tests/test_static_site_docs.py tests/test_public_api.py -q
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add -A tuba/reporting tests docs/content
git commit -m "refactor(reporting): delete the compliance-report channel nothing produces"
```

---

### Task 4: Network routing and routing spaces

**Files:**
- Delete: `tuba/routing/network.py`, `tuba/routing/spaces.py`, `examples/autoroute_network.py`, `tests/test_routing_network.py`, `tests/test_routing_spaces.py`, `tests/test_pipe_autorouting.py`
- Modify: `tuba/routing/__init__.py`, `tuba/routing/types.py`, `tuba/routing/report.py`, `tuba/routing/thermal.py`, `docs/content/autorouting.md`, `docs/content/examples.md`, `docs/content/developer.md`
- Test: `tests/test_routing_report.py`, `tests/test_routing_thermal.py`, `tests/test_routing_astar.py`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing later tasks use. Single-pipe routing and the autorouted expansion-loop project stay.

- [ ] **Step 1: Search for callers**

```bash
grep -rn -E "NetworkRouter|NetworkRouteRequest|NetworkRouteResult|RoutingSpace|RoutingZone|_network_route_markdown|estimate_free_expansion|autoroute_network" tuba scripts examples notebooks docs/content README.md tests viewer/src
```
Expected: only the files listed in this task.

- [ ] **Step 2: Check the duplicate test**

Read `tests/test_pipe_autorouting.py` beside `tests/test_routing_astar.py` (around 37-44). If `test_pipe_autorouting.py` asserts anything `test_routing_astar.py` lacks, move that assertion into `test_routing_astar.py` first.

- [ ] **Step 3: Delete the code**

Delete `tuba/routing/network.py` and `tuba/routing/spaces.py`; `NetworkRouteRequest` and `NetworkRouteResult` in `tuba/routing/types.py` (around 115-135); `_network_route_markdown` and any branch that dispatches to it in `tuba/routing/report.py` (around 141-171); `estimate_free_expansion` in `tuba/routing/thermal.py` (around 55-60); their exports in `tuba/routing/__init__.py`; `examples/autoroute_network.py`.

- [ ] **Step 4: Tests and docs**

Delete `tests/test_routing_network.py`, `tests/test_routing_spaces.py` and `tests/test_pipe_autorouting.py`. Remove the network cases from `tests/test_routing_report.py` (around 115-152) and the `estimate_free_expansion` cases from `tests/test_routing_thermal.py` (around 7-15). Remove network routing and routing spaces from `docs/content/autorouting.md` (around 12, 17, 177-200 and 226), `docs/content/examples.md` (around 126 and 151) and `docs/content/developer.md` (around 14, 100 and 102).

- [ ] **Step 5: Run the tests**

```bash
D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_routing_*.py tests/test_examples.py tests/test_static_site_docs.py tests/test_public_api.py -q
```
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add -A tuba/routing examples tests docs/content
git commit -m "refactor(routing): delete network routing and routing spaces"
```

---

### Task 5: Test-only scene features, scene diffs and BCF

**Files:**
- Delete: `tuba/visualization/bcf.py`, `tests/test_visualization_bcf.py`, `tests/test_visualization_agent_proposals.py`, `tests/test_visualization_federation.py`, `tests/test_visualization_digital_twin.py`
- Modify: `tuba/visualization/scene.py`, `tuba/visualization/schema.py`, `tuba/visualization/web_export.py`, `tuba/visualization/__init__.py`, `tuba/visualization/builders/__init__.py`, `tuba/visualization/builders/_core.py`, `tuba/visualization/builders/_review.py`, `tuba/visualization/builders/_helpers.py`, `tuba/visualization/builders/_layers.py`, `tuba/reporting/export.py` (the bundle inventory entry only), `docs/content/reference/public-api.md`
- Test: `tests/test_visualization_scene.py`, `tests/test_visualization_builders.py`

**Interfaces:**
- Consumes: Task 1 (the viewer no longer reads `agent_proposals` or `scene_diffs`) and Task 3 (its `tuba/reporting/export.py` edits have landed).
- Produces: scenes without agent proposals, scene diffs, external sources, runtime states, point clouds, materials or styles.

- [ ] **Step 1: Search for callers**

```bash
grep -rn -E "agent_proposals|AgentProposal|SceneDiff|scene_diffs|external_sources|runtime_states|runtime_state|point_clouds|SceneMaterial|SceneStyle|export_bcf_topics|import_bcf_topics|validate_scene_dict|rule_results|clash_results|support_plan|structure_plan|patch_preview" tuba scripts examples notebooks docs/content README.md tests
grep -rn -E "style_id|material_id" tuba/visualization viewer/src
```
Expected: the first command finds only `tuba/visualization/**`, the `metadata/scene_diffs.json` inventory entry in `tuba/reporting/export.py`, the tests named in this task and `docs/content/reference/public-api.md`. The second shows whether anything besides `scene.py` sets or reads `style_id` or `material_id`.

- [ ] **Step 2: Write the legacy-loading test first**

Add to the test class in `tests/test_visualization_scene.py`:

```python
    def test_scene_with_retired_keys_still_loads_and_round_trips(self):
        data = {
            "scene_id": "legacy",
            "model_id": "model",
            "materials": [{"id": "steel"}],
            "styles": [{"id": "pipe", "material_id": "steel"}],
            "agent_proposals": [{"proposal_id": "p1"}],
            "scene_diffs": [{"diff_id": "d1", "base_scene_id": "legacy"}],
        }
        scene = VisualizationScene.from_dict(data)
        scene.validate()
        restored = scene.to_dict()
        for key in ("materials", "styles", "agent_proposals", "scene_diffs"):
            self.assertEqual(restored[key], data[key])
```

```bash
D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_visualization_scene.py -q -k retired_keys
```
Record the result in the report. It may fail today, because these keys are still parsed into typed records; it must pass after Steps 3-6.

- [ ] **Step 3: Delete agent proposals and scene diffs**

- `tuba/visualization/builders/_review.py`: delete `_build_agent_proposal_preview` (around 406-471).
- `tuba/visualization/builders/_helpers.py`: delete its patch-preview helper (around 100-104).
- `tuba/visualization/builders/_core.py`: delete the `agent_proposals` parameter and handling (around 59 and 299-310) and the `scene_diffs` collection (around 168, 307 and 345).
- `tuba/visualization/scene.py`: delete `AgentProposal` and `SceneDiff` with their `from_dict` helpers (around 494-562 and 620-688), and the `agent_proposals` and `scene_diffs` fields of `VisualizationScene` from its dataclass, `known`, `from_dict` and `to_dict`.
- `tuba/visualization/web_export.py`: delete the metadata writes for them (around 86-87).
- `tuba/reporting/export.py`: delete `metadata/scene_diffs.json` from the bundle inventory (around 33).
- Delete `tests/test_visualization_agent_proposals.py` and the `SceneDiff` round-trip test in `tests/test_visualization_scene.py` (around 124-135).

- [ ] **Step 4: Delete external sources, runtime states and point clouds**

- External sources: delete the scene builder in `_review.py` (around 472-530), `_helpers.py` (around 358-371) and `_core.py` (the `external_sources` parameter around 62 and its loop around 312-316).
- Runtime states: delete the overlay in `_review.py` (around 605-630), `_core.py` (the `runtime_states` parameter around 65 and its handling around 324-325) and the `"runtime_state"` entry in `_layers.py` (around 84).
- Point clouds: delete the point-cloud part of the field-context scene in `_review.py` (around 537-568) and `_core.py` (the `point_clouds` parameter around 63, and its use around 318-319). `field_notes` keeps working.
- Delete `tests/test_visualization_federation.py`, `tests/test_visualization_digital_twin.py` and any point-cloud cases in the field-notes tests.

- [ ] **Step 5: Delete scene materials, styles and unused route-review fields**

- `tuba/visualization/scene.py`: delete `SceneMaterial` and `SceneStyle` (around 46-101) with the `materials` and `styles` scene fields, their `from_dict` and `to_dict` handling and their validation (around 788-797 and 823-829).
- If Step 1 showed that nothing outside `scene.py` sets or reads `style_id` or `material_id`, delete those fields and their checks too.
- Delete the `RouteReview` fields `rule_results`, `clash_results`, `support_plan`, `structure_plan` and `patch_preview` (around 443-447, 458-462 and their `from_dict`/`to_dict` lines).
- Remove `SceneMaterial`, `SceneStyle`, `SceneDiff` and `AgentProposal` from `tuba/visualization/__init__.py`.

- [ ] **Step 6: Delete BCF and the small leftovers**

- Delete `tuba/visualization/bcf.py`, `tests/test_visualization_bcf.py`, and `export_bcf_topics` and `import_bcf_topics` in `tuba/visualization/__init__.py`. Reword the package docstring (around line 6, "BIM interop (BCF/IFC)") to what the package does now.
- Delete `validate_scene_dict` from `tuba/visualization/schema.py`. Keep `SceneValidationError` there, because `tuba/visualization/labels.py` and `scene.py` import it. In `tests/test_visualization_scene.py` (around 113 and 161), call `VisualizationScene.from_dict(data).validate()` instead.
- Delete the `_find_element` re-export in `tuba/visualization/builders/__init__.py` (around line 4); `tests/test_visualization_builders.py` (around line 8) imports it from its defining module.
- Delete the `"tuyau_subpoint_field"` overlay-kind branch in `tuba/visualization/builders/_layers.py` (around 241). That kind is only ever an object kind (`_results.py`, around 864).
- Remove rows for the deleted names from `docs/content/reference/public-api.md`.

- [ ] **Step 7: Run the tests**

```bash
D:/Gitprojects/Tuba_v4/.venv/Scripts/python.exe -m pytest tests/test_visualization_*.py tests/test_reporting_export.py tests/test_official_viewer_publication.py tests/test_public_api.py tests/test_static_site_docs.py tests/test_viewer_launcher.py -q
```
Expected: all pass, including `test_scene_with_retired_keys_still_loads_and_round_trips`.

- [ ] **Step 8: Commit**

```bash
git add -A tuba/visualization tuba/reporting/export.py tests docs/content
git commit -m "refactor(visualization): delete agent proposals, scene diffs, federated sources, runtime states, point clouds, scene styles and BCF"
```

---

## After Task 5 (controller)

- Run the full suite from the worktree root and compare with the f0ebb82 baseline (1138 passed, 34 skipped, 151 subtests): fewer tests (deleted ones), no failures.
- Final whole-branch review, then the finishing options. If Plan 6a or support-attachment has landed on main by then, rebase first; conflicts are possible only in `tuba/reporting/tables.py` and `docs/content/`.
- After the merge, if Task 2 removed the `/=2.2` rule, delete the stray untracked `=2.2` file in the main checkout.
