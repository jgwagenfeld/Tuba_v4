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
pure state transition.

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

GREEN verification:

- Focused bridge/state tests: 36 passed, 0 failed.
- Full viewer suite: 93 passed, 0 failed.
- `npm.cmd run build`: succeeded with Vite 8.0.16.
- `npm.cmd run e2e -- code-aster-results`: succeeded with 7 rendered objects
  and 170/2500 varied WebGL samples.

The existing Code_Aster E2E fixture does not publish an entity-bearing review
row, so that gate verifies the unchanged result-bundle workflow and nonblank
3D rendering. The row action itself is covered by pure resolution, context
preservation, app-wiring, camera-pipeline, reload, and SceneDiff regressions.

## Scope

No engineering values are calculated in the browser, no solver/result
contracts are changed, no Task 5 files or ledger entries are modified, and no
new visualization path is introduced.

Commit message: `feat: link review rows to 3d selection`
