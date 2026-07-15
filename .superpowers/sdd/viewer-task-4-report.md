# Viewer Workflow Task 4 Report

## Outcome

Implemented the report-row to 3D selection bridge on the existing `activeTab`
workflow contract. Resolvable report rows now expose accessible `Show in 3D`
actions that select the published scene object, switch to the 3D workflow, and
fit the existing camera pipeline without changing engineering review context.

## Resolution contract

- Accepts direct scene object IDs.
- Resolves `entity_ref` and `governing_entity_ref` values through canonical
  object-map entries, scene object fields, and object metadata mappings.
- Supports both observed object-map shapes: entity-to-object strings and
  object-to-metadata records.
- Ranks duplicates deterministically: exact object ID, canonical
  `object:${entityRef}`, primary scene object/entity matches, then spatial
  vector/marker/analysis representations. Object-map iteration order cannot
  displace a canonical model object.
- Resolves Code_Aster `analysis_node:*` rows only when structured
  `analysis_mesh_node` / `member_id` or `source.analysis_mesh` metadata matches
  an actual point, marker, or vector geometry asset.
- Selects node/support representations that exist only as result vectors or
  markers.
- Validates every resolved ID against actual scene objects; it never invents
  an entity.
- Returns the identical state for unresolved references. The app's fallback
  status is nonfatal.

## State and camera preservation

The bridge changes only `activeTab`, `selectedObjectIds`, and camera fit state.
Tests verify preservation of active load case, result and geometry state,
overlay state, vector/deformation scales, thresholds, visibility/isolation,
issue review state, review data, and embed state.

`objectMap` is now part of viewer state. Full reload uses the newly loaded map,
while compatible SceneDiff reconstruction carries the existing map. Selection
fit also falls back to an object's `geometry_asset_id` when an asset omits
`object_ids`. Selected bounds are routed through the existing
`fitCameraToBounds` renderer path so the browser camera visibly follows the
pure state transition. Each fit emits a monotonic request ID. The live renderer
applies the initial whole-scene fit once and each changed request once; ordinary
re-renders with the same request retain the user's live camera position and
OrbitControls target.

## TDD evidence

RED was observed before implementation:

- `npm.cmd test -- --test-name-pattern="show in 3d|entity ref|selection"`
  exited 1 because `reviewSelection.js` did not exist.
- The focused selection regression exited 1 because camera target remained
  `[0, 0, 0]` when `object_ids` were absent.
- Viewer-state regressions exited 1 because `objectMap` was undefined after
  viewer-state creation/reload and SceneDiff reconstruction.
- The renderer regression exited 1 because whole-scene bounds were used
  instead of requested selection bounds.
- Post-review live-camera regressions exited 1 because the renderer lacked a
  one-shot request controller and reapplied persistent bounds.
- Real-shaped Code_Aster regressions exited 1 for structured analysis nodes and
  canonical duplicate ranking.
- The committed-package baseline probe found 65 unresolved displacement refs
  out of 71 and resolved `element:pipe_bend_0` to analysis segment `...s0`.

GREEN verification:

- Focused bridge/state tests: 36 passed, 0 failed.
- Full viewer suite after review corrections: 99 passed, 0 failed.
- `npm.cmd run build`: succeeded with Vite 8.0.16.
- `npm.cmd run e2e -- code-aster-results`: succeeded with 7 rendered objects
  and 170/2500 varied WebGL samples.
- The direct committed-package probe now resolves all 71 displacement refs,
  resolves `analysis_node:pipe_bend_0_n1` to its published analysis-mesh point,
  and resolves `element:pipe_bend_0` to `object:element:pipe_bend_0`.

The existing Code_Aster E2E fixture does not publish an entity-bearing review
row, so that gate verifies the unchanged result-bundle workflow and nonblank
3D rendering. The row action itself is covered by pure resolution, context
preservation, app-wiring, camera-pipeline, reload, and SceneDiff regressions.

## Scope

No engineering values are calculated in the browser, no solver/result
contracts are changed, no Task 5 files or ledger entries are modified, and no
new visualization path is introduced.

Commits:

- `feat: link review rows to 3d selection`
- `fix: stabilize review row 3d navigation`
