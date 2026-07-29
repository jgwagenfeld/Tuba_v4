# Viewer Review Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make sectioning real, expose native keyboard-operable camera controls, and make current field/component/deformed-state behavior truthful.

**Architecture:** Reuse `state.sectionBox`, `applySectionBox`, the renderer graph cache, native HTML controls, and `e2e-smoke.mjs`. Add no dependency, state store, camera framework, clipping library, or visualization path.

**Tech Stack:** Three.js 0.184, native HTML/CSS, Node test runner, Playwright, Vite.

## Global Constraints

- Preserve the existing task rail, evidence dock, artifact picker, and result-control hierarchy.
- Keep task mode and evidence destination independent.
- Complete sectioning with Three.js clipping planes; whole-object AABB filtering remains only a coarse optimization.
- Native controls must be keyboard operable and visibly labelled.
- Keep legacy bundles without `result_fields`, `layers`, or `review.json` usable.
- Do not add a third visualization path or fabricated result data.
- Do not modify the user's uncommitted `README.md` in this plan.

---

## File Map

- `viewer/src/renderer.js`: clipping planes, standard camera views, zoom facade, geometry-state asset gating.
- `viewer/src/app.js`: section and camera native-control rendering and validation.
- `viewer/src/resultReview.js`: load-case-consistent result and geometry state transitions.
- `viewer/index.html`: static homes for section and camera controls.
- `viewer/src/styles.css`: compact responsive control layout and focus presentation.
- `viewer/test/renderer.test.js`: clipping, camera, zoom, and geometry-state tests.
- `viewer/test/result-review.test.js`: load-case and selector consistency tests.
- `viewer/test/scaffold.test.js`: accessible static-control contract.
- `viewer/scripts/e2e-smoke.mjs`: current engineering and keyboard-control browser scenarios.

### Task 1: Apply real renderer clipping

**Files:**
- Modify: `viewer/src/renderer.js`
- Modify: `viewer/test/renderer.test.js`

**Interfaces:**
- Consumes: `state.sectionBox` with `{min: [x,y,z], max: [x,y,z]}`.
- Produces: `sectionBoxClippingPlanes(sectionBox) -> Plane[]`.
- Produces: `applySectionBoxClipping(graph, sectionBox) -> void`.

- [ ] **Step 1: Write failing clipping-plane tests**

```javascript
const planes = sectionBoxClippingPlanes({
  min: [-1, -2, -3],
  max: [4, 5, 6],
});

assert.equal(planes.length, 6);
assert.ok(planes.every((plane) =>
  plane.distanceToPoint(new Vector3(0, 0, 0)) <= 0
));
assert.ok(planes.some((plane) =>
  plane.distanceToPoint(new Vector3(7, 0, 0)) > 0
));
```

Build a test graph containing mesh and line materials, apply a section box, and assert every material receives six clipping planes. Apply `undefined` and assert the planes are removed.

- [ ] **Step 2: Run the focused tests and verify failure**

Run from `viewer/`: `npm.cmd test -- --test-name-pattern "section box|clipping"`

Expected: FAIL because the renderer exports no clipping-plane functions.

- [ ] **Step 3: Implement the two functions**

Use upper planes `Plane(+axis, -max)` and lower planes `Plane(-axis, min)`. Traverse `graph.root`, not the complete Three.js scene, so the grid, axes, lights, and orientation helper remain unclipped. Handle material arrays as well as single materials.

- [ ] **Step 4: Enable local clipping without invalidating the graph cache**

Set `renderer.localClippingEnabled = true` in `createThreeCanvasRenderer()`. In `render(state)`, immediately after `updateSceneGraphVisibility(graph, state)`, call:

```javascript
applySectionBoxClipping(graph, state.sectionBox);
```

Do not add `sectionBox` to `SCENE_GRAPH_STATE_KEYS`. Preserve `objectIntersectsSectionBox()` as the coarse rejection for wholly external objects.

- [ ] **Step 5: Run renderer tests**

Run from `viewer/`: `npm.cmd test -- --test-name-pattern "section box|clipping|scene graph"`

Expected: PASS, including a crossing pipe that remains in the graph and is fragment-clipped.

- [ ] **Step 6: Commit**

```text
git add viewer/src/renderer.js viewer/test/renderer.test.js
git commit -m "feat: apply real viewer section clipping"
```

### Task 2: Add native section and camera controls

**Files:**
- Modify: `viewer/index.html`
- Modify: `viewer/src/app.js`
- Modify: `viewer/src/renderer.js`
- Modify: `viewer/src/styles.css`
- Modify: `viewer/test/scaffold.test.js`
- Modify: `viewer/test/renderer.test.js`
- Modify: `viewer/scripts/e2e-smoke.mjs`

**Interfaces:**
- Produces: `STANDARD_VIEW_DIRECTIONS` with `iso`, `positiveX`, `negativeX`, `positiveY`, `negativeY`, `positiveZ`, `negativeZ`.
- Produces: `setCameraToStandardView(camera, bounds, controls, viewId) -> void`.
- Extends viewport facade with `setStandardView(viewId)` and `zoomBy(factor)`.
- Reuses: `applySectionBox(state, box)` and `applySectionBox(state, undefined)`.

- [ ] **Step 1: Add failing scaffold and camera tests**

Assert the HTML has:

```html
<div data-section-box-controls></div>
<div class="camera-controls" role="group" aria-label="Standard camera views" data-camera-controls></div>
```

Unit-test standard direction, preserved target/distance, positive zoom clamping, projection-matrix updates, and stable camera-up vectors for `positiveZ` and `negativeZ`.

- [ ] **Step 2: Run focused tests and verify failure**

Run from `viewer/`:

```text
npm.cmd test -- --test-name-pattern "camera|section|scaffold"
```

Expected: FAIL because controls and camera facade methods do not exist.

- [ ] **Step 3: Add the two static control homes**

Put the section controls inside the pinned Display strip and the camera group inside `.viewport`. Keep the canvas label and current status/live-region elements.

- [ ] **Step 4: Render and validate native section inputs**

Add `renderSectionBoxControls()` and call it from `renderDisplayStrip()`. Render an enable checkbox, X/Y/Z min and max number inputs, and Reset section. Use `currentState.bounds` as defaults. Reject non-finite values or any `min >= max` with `setCustomValidity`; do not mutate state until all six inputs are valid. Reset through `applySectionBox(currentState, undefined)`. Saved-view behavior remains unchanged because the existing view-state functions already carry `sectionBox`.

- [ ] **Step 5: Add standard camera and zoom operations**

```javascript
export const STANDARD_VIEW_DIRECTIONS = {
  iso: [1, -1, 0.65],
  positiveX: [1, 0, 0],
  negativeX: [-1, 0, 0],
  positiveY: [0, 1, 0],
  negativeY: [0, -1, 0],
  positiveZ: [0, 0, 1],
  negativeZ: [0, 0, -1],
};
```

`setCameraToStandardView` reuses `fitCameraToBounds()` for target, distance, near/far, and orthographic extent, then applies the requested direction. The viewport facade renders after `setStandardView`. `zoomBy(factor)` updates orthographic `camera.zoom`, clamps it to `0.05..20`, updates the projection matrix, and redraws.

- [ ] **Step 6: Render native camera buttons**

Render Isometric, +X, -X, +Y, -Y, +Z, -Z, Zoom in, and Zoom out buttons. Use native button keyboard behavior; do not add a custom keyboard dispatcher. Update viewport guidance to mention these controls.

- [ ] **Step 7: Add the `section-camera` E2E scenario**

The scenario must keyboard-activate +Z, verify `canvas.dataset.cameraDirection`, zoom in, enable sectioning, change X max through labelled inputs, confirm a crossing pipe remains in `lastRender.objectIds` while the framebuffer changes, reset sectioning, and confirm the original fingerprint returns within the existing deterministic tolerance.

- [ ] **Step 8: Run unit and browser tests**

Run from `viewer/`:

```text
npm.cmd test -- --test-name-pattern "camera|section|scaffold"
npm.cmd run e2e -- section-camera
```

Expected: PASS.

- [ ] **Step 9: Commit**

```text
git add viewer/index.html viewer/src/app.js viewer/src/renderer.js viewer/src/styles.css viewer/test/scaffold.test.js viewer/test/renderer.test.js viewer/scripts/e2e-smoke.mjs
git commit -m "feat: add accessible viewer section and camera controls"
```

### Task 3: Keep result and deformed-state selectors truthful

**Files:**
- Modify: `viewer/src/resultReview.js`
- Modify: `viewer/src/renderer.js`
- Modify: `viewer/test/result-review.test.js`
- Modify: `viewer/test/renderer.test.js`
- Modify: `viewer/scripts/e2e-smoke.mjs`

**Interfaces:**
- Consumes: scene `result_fields`, result-state overlays, geometry-state overlays, and geometry asset `generation_config.geometry_state_id`.
- Produces: load-case-consistent result/geometry state selection.
- Produces: shared internal `assetMatchesActiveGeometryState(asset, payload, activeGeometryStateId)` predicate.

- [ ] **Step 1: Write failing selector and renderer tests**

Cover these exact cases:

- load-case changes cannot leave a result state or geometry state on another case;
- physical selection excludes visual-state assets;
- visual selection excludes physical-state assets;
- assets without `geometry_state_id` remain visible;
- visual selection retains the undeformed grey reference.

- [ ] **Step 2: Run focused tests and verify failure**

Run from `viewer/`: `npm.cmd test -- --test-name-pattern "load case|geometry state|deformed"`

Expected: FAIL because geometry-state selection does not gate assets.

- [ ] **Step 3: Make state transitions load-case consistent**

Filter `getGeometryStateOptions(state, loadCase)` to the active load case. In `setActiveLoadCase()`, choose a compatible result state and geometry state together. Preserve the physical/visual purpose when that purpose exists for the new case; otherwise use the first state for that case.

- [ ] **Step 4: Gate geometry-state assets through one predicate**

Read `geometry_state_id` from payload or asset `generation_config`. Assets without it remain visible; assets with it render only when it equals `state.activeGeometryStateId`. Reuse the predicate in `createThreeSceneGraph()`, `hasAllVisibleAssets()`, and visual-reference detection.

- [ ] **Step 5: Update the current engineering E2E contract**

In `public-code-aster-review`, require eight overlays, 37 layers, and four result fields. Verify Load case = Operating; Field replaces legacy Result state; Component is absent for scalar stress, appears for displacement, and selecting DZ updates both state and legend. Switch physical/visual Deformed state and assert mutually exclusive state asset IDs. Keep the FE VMIS “not ASME code stress” notice. Do not alter `legacy-workflow` expectations.

- [ ] **Step 6: Run all viewer unit and focused E2E tests**

Run from `viewer/`:

```text
npm.cmd test
npm.cmd run e2e -- public-code-aster-review
npm.cmd run e2e -- legacy-workflow
```

Expected: PASS.

- [ ] **Step 7: Commit**

```text
git add viewer/src/resultReview.js viewer/src/renderer.js viewer/test/result-review.test.js viewer/test/renderer.test.js viewer/scripts/e2e-smoke.mjs
git commit -m "fix: align viewer result and geometry state controls"
```
