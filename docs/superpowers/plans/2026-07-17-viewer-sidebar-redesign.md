# Viewer Sidebar Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the viewer's flat wall of ~20 layer checkboxes and heading-heavy nav with four focused tasks, task-driven visibility presets, and one pinned Display strip whose layer controls are grouped by category with mesh groups collapsed.

**Architecture:** All changes live in the viewer front-end. Layer ids are already colon-namespaced (`analysis_mesh:group:GN_N0`, `overlay:clash`, `result:reaction`); we derive categories from those prefixes at render time — no Python/builder/bundle changes. Task activation applies a per-task category-visibility preset via the existing `setLayerVisibility` reducer path. Overlays are already registered as `overlay:` layers, so the separate overlay checkbox list is removed and folded into the layer categories.

**Tech Stack:** Vanilla ES modules, `node --test` (node:test/assert) for unit tests, Playwright `scripts/e2e-smoke.mjs` for browser smoke, Vite build. No frameworks, no new dependencies.

## Global Constraints

- **No new dependencies.** Vanilla JS + `node:test` only.
- **No Python / bundle-format changes.** Categories are derived in the viewer from existing `layer_ids`.
- **Primary gate is `cd viewer && npm test`** (runs `node --test`, node-only, fast). CI (`.github/workflows/tuba-pages.yml`) only builds the viewer — it does not run tests or e2e — so unit tests and e2e are local gates you must run yourself.
- **Working tree has uncommitted changes** (hover/orbit picking in `app.js`, `renderer.js`, `e2e-smoke.mjs`, etc.) plus two stashes. Do NOT stash, reset, or revert them — build on top. Only the spec commit (9081d31) is yours so far.
- **Line endings:** repo is LF; git may warn "LF will be replaced by CRLF" on Windows — this is expected, not an error.
- **Preserve accessibility:** every checkbox keeps a `<label>`; task buttons keep `aria-current`; keyboard nav (Arrow/Home/End) on the rail keeps working.
- **Two e2e scenarios are already stale** relative to the committed `app.js` (`code-aster-results` and `clash-review` reference tabs named "3D"/"Summary" and `engineering-3d-panel`, which the current UI does not render). Do NOT try to make them pass. Task 6 confirms the pre-existing baseline first, then only updates scenarios that pass today.

## File Structure

- `viewer/src/sceneLoader.js` — add pure `categoryForLayerId` + `categorizeLayers` helpers next to the existing `buildLayerRegistry`/`labelForLayer`. Category derivation belongs with the layer registry it describes.
- `viewer/src/workflowState.js` — trim the visible cockpit task set to 4, retarget legacy/default tabs, add `visibilityPresetForTask`.
- `viewer/src/app.js` — flat rail render (no headings), new `renderDisplayStrip`, preset application on task switch and initial load, remove `renderOverlays`.
- `viewer/index.html` — move layer/saved-view markup out of the task panel into a pinned `data-display-strip`; remove the overlay list.
- `viewer/src/styles.css` — style the display strip, category switches, and the collapsed tree; drop dead rail-heading rules if any.
- `viewer/test/scene-loader.test.js`, `viewer/test/workflow-state.test.js`, `viewer/test/workflow-rendering.test.js` — unit coverage.
- `viewer/scripts/e2e-smoke.mjs` — update the currently-passing scenarios that reference removed UI.

---

### Task 1: Derive layer categories (pure helpers)

**Files:**
- Modify: `viewer/src/sceneLoader.js` (add exports near `labelForLayer`, end of file)
- Test: `viewer/test/scene-loader.test.js`

**Interfaces:**
- Consumes: the `layers` registry shape from `buildLayerRegistry` — each layer is `{ id, label, visible, count, source, objectIds?, overlayIds?, overlayKind? }`.
- Produces:
  - `categoryForLayerId(layerId: string) -> "geometry"|"analysis_mesh"|"results"|"overlays"|"envelopes"|"other"`
  - `categorizeLayers(layers: Record<string, Layer>) -> Array<{ id, label, layerIds: string[], leaves: Array<{layerId,label,count}>, groups: Array<{label, leaves: Array<{layerId,label,count}>}> }>` — ordered geometry → analysis_mesh → results → overlays → envelopes → other; categories with no layers are omitted; within a category, ids matching `<something>:group:<name>` are collected under a single `{label:"Groups"}` node, all other layers are direct `leaves`; leaf label is the cleaned last colon-segment.

- [ ] **Step 1: Write the failing test**

Add to `viewer/test/scene-loader.test.js` (import the two new names in the existing top import from `../src/sceneLoader.js`):

```js
import {
  createViewerState,
  loadSceneBundle,
  loadSceneBundleFromUrl,
  setLayerVisibility,
  categoryForLayerId,
  categorizeLayers
} from "../src/sceneLoader.js";

test("categoryForLayerId maps namespaces to display categories", () => {
  assert.equal(categoryForLayerId("pipe"), "geometry");
  assert.equal(categoryForLayerId("imported_components"), "geometry");
  assert.equal(categoryForLayerId("analysis_mesh:nodes"), "analysis_mesh");
  assert.equal(categoryForLayerId("analysis_mesh:group:GN_N0"), "analysis_mesh");
  assert.equal(categoryForLayerId("result:reaction"), "results");
  assert.equal(categoryForLayerId("solver_result:tuyau_subpoints"), "results");
  assert.equal(categoryForLayerId("deformed:mesh"), "results");
  assert.equal(categoryForLayerId("overlay:clash"), "overlays");
  assert.equal(categoryForLayerId("physical_envelope:insulation"), "envelopes");
  assert.equal(categoryForLayerId("weird:namespace"), "other");
});

test("categorizeLayers orders categories and collapses mesh groups", () => {
  const layers = {
    pipe: { id: "pipe", label: "Pipe", visible: true, count: 105, source: "object" },
    "analysis_mesh:nodes": { id: "analysis_mesh:nodes", label: "Analysis Mesh Nodes", visible: true, count: 71, source: "object" },
    "analysis_mesh:group:GN_N0": { id: "analysis_mesh:group:GN_N0", label: "Analysis Mesh Group GN N0", visible: true, count: 1, source: "object" },
    "analysis_mesh:group:MAT_Steel": { id: "analysis_mesh:group:MAT_Steel", label: "Analysis Mesh Group MAT Steel", visible: true, count: 105, source: "object" },
    "overlay:clash": { id: "overlay:clash", label: "Overlay Clash", visible: true, count: 2, source: "overlay", overlayKind: "clash" }
  };

  const categories = categorizeLayers(layers);
  assert.deepEqual(categories.map((category) => category.id), ["geometry", "analysis_mesh", "overlays"]);

  const geometry = categories.find((category) => category.id === "geometry");
  assert.deepEqual(geometry.layerIds, ["pipe"]);
  assert.deepEqual(geometry.leaves, [{ layerId: "pipe", label: "Pipe", count: 105 }]);
  assert.deepEqual(geometry.groups, []);

  const mesh = categories.find((category) => category.id === "analysis_mesh");
  assert.deepEqual(mesh.layerIds, ["analysis_mesh:nodes", "analysis_mesh:group:GN_N0", "analysis_mesh:group:MAT_Steel"]);
  assert.deepEqual(mesh.leaves, [{ layerId: "analysis_mesh:nodes", label: "Nodes", count: 71 }]);
  assert.equal(mesh.groups.length, 1);
  assert.equal(mesh.groups[0].label, "Groups");
  assert.deepEqual(mesh.groups[0].leaves, [
    { layerId: "analysis_mesh:group:GN_N0", label: "GN N0", count: 1 },
    { layerId: "analysis_mesh:group:MAT_Steel", label: "MAT Steel", count: 105 }
  ]);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd viewer && node --test test/scene-loader.test.js`
Expected: FAIL — `categoryForLayerId is not a function` / `categorizeLayers is not a function`.

- [ ] **Step 3: Write minimal implementation**

Append to `viewer/src/sceneLoader.js` (after `labelForLayer`):

```js
const CATEGORY_ORDER = [
  { id: "geometry", label: "Geometry" },
  { id: "analysis_mesh", label: "Analysis mesh" },
  { id: "results", label: "Results" },
  { id: "overlays", label: "Overlays" },
  { id: "envelopes", label: "Envelopes" },
  { id: "other", label: "Other" }
];

export function categoryForLayerId(layerId) {
  const id = String(layerId);
  if (id.startsWith("overlay:")) return "overlays";
  if (id.startsWith("analysis_mesh:")) return "analysis_mesh";
  if (id.startsWith("result:") || id.startsWith("solver_result:") || id.startsWith("deformed:")) return "results";
  if (id.startsWith("physical_envelope:")) return "envelopes";
  if (!id.includes(":")) return "geometry";
  return "other";
}

export function categorizeLayers(layers) {
  const byCategory = new Map(CATEGORY_ORDER.map((category) => [category.id, []]));
  for (const layer of Object.values(layers ?? {})) {
    byCategory.get(categoryForLayerId(layer.id)).push(layer);
  }
  const result = [];
  for (const category of CATEGORY_ORDER) {
    const members = byCategory.get(category.id);
    if (members.length === 0) continue;
    const leaves = [];
    const groupLeaves = [];
    for (const layer of members) {
      const entry = { layerId: layer.id, label: leafLabel(layer.id), count: layer.count };
      if (/:group:[^:]+$/.test(layer.id)) {
        groupLeaves.push(entry);
      } else {
        leaves.push(entry);
      }
    }
    result.push({
      id: category.id,
      label: category.label,
      layerIds: members.map((layer) => layer.id),
      leaves,
      groups: groupLeaves.length > 0 ? [{ label: "Groups", leaves: groupLeaves }] : []
    });
  }
  return result;
}

function leafLabel(layerId) {
  const last = String(layerId).split(":").at(-1);
  return last
    .split(/[_-]+/)
    .map((part) => `${part.slice(0, 1).toUpperCase()}${part.slice(1)}`)
    .join(" ");
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd viewer && node --test test/scene-loader.test.js`
Expected: PASS (all tests in file green).

- [ ] **Step 5: Commit**

```bash
git add viewer/src/sceneLoader.js viewer/test/scene-loader.test.js
git commit -m "feat(viewer): derive layer display categories from namespaced ids"
```

---

### Task 2: Trim task set + define visibility presets

**Files:**
- Modify: `viewer/src/workflowState.js`
- Test: `viewer/test/workflow-state.test.js`

**Interfaces:**
- Consumes: `{ review, embed }` context objects (unchanged shape).
- Produces:
  - `getVisibleCockpitTaskIds({review})` → review: `["summary","model","results","diagnostics"]`; legacy: `["model","diagnostics"]`.
  - `getVisibleWorkflowTabs({review})` → legacy set becomes `["model","diagnostics"]` (review set unchanged: all `WORKFLOW_TABS` ids).
  - `defaultWorkflowTab({review,embed})` → embed: `"3d"`; review: `"summary"`; legacy: `"model"`.
  - `visibilityPresetForTask(taskId: string) -> Record<categoryId, boolean> | null` — returns the category→visible map for `summary`/`model`/`results`/`diagnostics`; `null` for unknown/embed `"3d"`.
- `WORKFLOW_TABS` array stays intact (still holds `load-cases`, `3d`, `compliance` for `setWorkflowTab` validation and embed).

- [ ] **Step 1: Write the failing test**

Replace the two existing task-set tests and add preset coverage in `viewer/test/workflow-state.test.js`. Update the import line to add `defaultWorkflowTab, getVisibleWorkflowTabs, visibilityPresetForTask`:

```js
import {
  WORKFLOW_TABS,
  createWorkflowState,
  defaultWorkflowTab,
  getVisibleCockpitTaskIds,
  getVisibleWorkflowTabs,
  visibilityPresetForTask,
  workflowTabForKey,
  setWorkflowTab
} from "../src/workflowState.js";
```

Replace the `"legacy workflow hides data tabs..."` and `"cockpit tasks omit the evidence-only compliance destination"` tests with:

```js
test("cockpit tasks are the four focused destinations in review mode", () => {
  assert.deepEqual(
    getVisibleCockpitTaskIds({ review: reviewFixture }),
    ["summary", "model", "results", "diagnostics"]
  );
});

test("legacy mode keeps model and issues tasks and defaults to model", () => {
  assert.deepEqual(getVisibleCockpitTaskIds({ review: null }), ["model", "diagnostics"]);
  assert.deepEqual(getVisibleWorkflowTabs({ review: null }), ["model", "diagnostics"]);
  assert.equal(defaultWorkflowTab({ review: null, embed: false }), "model");
  assert.equal(createWorkflowState({ review: null, embed: false }).activeTab, "model");
});

test("embed still defaults to the 3d canvas destination", () => {
  assert.equal(defaultWorkflowTab({ review: reviewFixture, embed: true }), "3d");
});

test("visibility presets hide analysis mesh everywhere and scope results/overlays per task", () => {
  assert.deepEqual(visibilityPresetForTask("summary"), {
    geometry: true, analysis_mesh: false, results: true, overlays: true, envelopes: false
  });
  assert.deepEqual(visibilityPresetForTask("model"), {
    geometry: true, analysis_mesh: false, results: false, overlays: false, envelopes: false
  });
  assert.deepEqual(visibilityPresetForTask("results"), {
    geometry: true, analysis_mesh: false, results: true, overlays: true, envelopes: false
  });
  assert.deepEqual(visibilityPresetForTask("diagnostics"), {
    geometry: true, analysis_mesh: false, results: false, overlays: true, envelopes: false
  });
  assert.equal(visibilityPresetForTask("3d"), null);
  assert.equal(visibilityPresetForTask("unknown"), null);
});
```

Also update the existing keyboard-nav tests that assumed the old order:
- In `"workflow keyboard navigation wraps across visible tabs"`, change expected wrap targets to the new 4-task ring:
```js
  assert.equal(workflowTabForKey(state, "summary", "ArrowLeft"), "diagnostics");
  assert.equal(workflowTabForKey(state, "summary", "ArrowRight"), "model");
  assert.equal(workflowTabForKey(state, "diagnostics", "ArrowRight"), "summary");
```
- In `"workflow keyboard navigation supports Home and End in legacy mode"`, change to the legacy `["model","diagnostics"]` ring:
```js
  assert.equal(workflowTabForKey(state, "diagnostics", "Home"), "model");
  assert.equal(workflowTabForKey(state, "model", "End"), "diagnostics");
  assert.equal(workflowTabForKey(state, "model", "Enter"), null);
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd viewer && node --test test/workflow-state.test.js`
Expected: FAIL — `visibilityPresetForTask is not a function` and the deep-equal task-set assertions mismatch the old `load-cases`/`3d` values.

- [ ] **Step 3: Write minimal implementation**

In `viewer/src/workflowState.js`:

Replace `getVisibleWorkflowTabs`, `getVisibleCockpitTaskIds`, `defaultWorkflowTab`:

```js
export function getVisibleWorkflowTabs({ review } = {}) {
  return review ? WORKFLOW_TABS.map((tab) => tab.id) : ["model", "diagnostics"];
}

export function getVisibleCockpitTaskIds({ review } = {}) {
  return review ? ["summary", "model", "results", "diagnostics"] : ["model", "diagnostics"];
}

export function defaultWorkflowTab({ review, embed } = {}) {
  if (embed) return "3d";
  return review ? "summary" : "model";
}
```

Add after `defaultWorkflowTab`:

```js
const TASK_VISIBILITY_PRESETS = Object.freeze({
  summary: { geometry: true, analysis_mesh: false, results: true, overlays: true, envelopes: false },
  model: { geometry: true, analysis_mesh: false, results: false, overlays: false, envelopes: false },
  results: { geometry: true, analysis_mesh: false, results: true, overlays: true, envelopes: false },
  diagnostics: { geometry: true, analysis_mesh: false, results: false, overlays: true, envelopes: false }
});

export function visibilityPresetForTask(taskId) {
  return TASK_VISIBILITY_PRESETS[taskId] ?? null;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd viewer && node --test test/workflow-state.test.js`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add viewer/src/workflowState.js viewer/test/workflow-state.test.js
git commit -m "feat(viewer): four-task cockpit set with per-task visibility presets"
```

---

### Task 3: Apply presets over layer categories

**Files:**
- Modify: `viewer/src/sceneLoader.js` (new export)
- Test: `viewer/test/scene-loader.test.js`

**Interfaces:**
- Consumes: `visibilityPresetForTask` (Task 2), `categorizeLayers` + `setLayerVisibility` (Task 1 / existing).
- Produces: `applyTaskVisibilityPreset(state, taskId) -> state` — for each category present in `categorizeLayers(state.layers)` whose id appears in the task preset, sets every layer id in that category to the preset's boolean via `setLayerVisibility`; categories absent from the preset (e.g. `other`) are left untouched; unknown/embed task ids (`null` preset) return state unchanged. Recomputes `visibleObjectIds` (via `setLayerVisibility`).

- [ ] **Step 1: Write the failing test**

Add to `viewer/test/scene-loader.test.js` (add `applyTaskVisibilityPreset` to the import):

```js
test("applyTaskVisibilityPreset toggles categories to match the task preset", () => {
  const layers = {
    pipe: { id: "pipe", label: "Pipe", visible: true, count: 3, source: "object", objectIds: [] },
    "analysis_mesh:nodes": { id: "analysis_mesh:nodes", label: "Nodes", visible: true, count: 5, source: "object", objectIds: [] },
    "overlay:clash": { id: "overlay:clash", label: "Overlay Clash", visible: true, count: 1, source: "overlay", overlayKind: "clash", overlayIds: [] }
  };
  const state = { objects: [], overlays: [], hiddenObjectIds: [], isolatedObjectIds: [], geometryAssets: [], layers };

  const modelState = applyTaskVisibilityPreset(state, "model");
  assert.equal(modelState.layers.pipe.visible, true);
  assert.equal(modelState.layers["analysis_mesh:nodes"].visible, false);
  assert.equal(modelState.layers["overlay:clash"].visible, false);

  const resultsState = applyTaskVisibilityPreset(modelState, "results");
  assert.equal(resultsState.layers["overlay:clash"].visible, true);
  assert.equal(resultsState.layers["analysis_mesh:nodes"].visible, false);

  assert.equal(applyTaskVisibilityPreset(state, "3d"), state);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd viewer && node --test test/scene-loader.test.js`
Expected: FAIL — `applyTaskVisibilityPreset is not a function`.

- [ ] **Step 3: Write minimal implementation**

In `viewer/src/sceneLoader.js`: add the import at the top (there is currently only the `reviewLoader` import — add a second):

```js
import { visibilityPresetForTask } from "./workflowState.js";
```

Add export (near `categorizeLayers`):

```js
export function applyTaskVisibilityPreset(state, taskId) {
  const preset = visibilityPresetForTask(taskId);
  if (!preset) return state;
  let next = state;
  for (const category of categorizeLayers(state.layers)) {
    if (!(category.id in preset)) continue;
    const visible = preset[category.id];
    for (const layerId of category.layerIds) {
      next = setLayerVisibility(next, layerId, visible);
    }
  }
  return next;
}
```

Note: `setLayerVisibility` already recomputes `visibleObjectIds`/overlay flags each call. `ponytail:` O(layers) sequential setLayerVisibility calls; batch into one pass only if layer counts ever make this hot.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd viewer && node --test test/scene-loader.test.js`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add viewer/src/sceneLoader.js viewer/test/scene-loader.test.js
git commit -m "feat(viewer): apply per-task visibility presets across layer categories"
```

---

### Task 4: Pinned Display strip markup

**Files:**
- Modify: `viewer/index.html`

**Interfaces:**
- Produces DOM hooks consumed by Task 5: `data-display-strip` (always-visible container in the rail), `data-category-switches`, `data-layer-list` (moved, now the collapsed tree body), `data-saved-views` (moved). Removes `data-overlay-list` and the `data-display-tools-home` wrapper.

- [ ] **Step 1: Move the layer/saved-view markup into a pinned strip**

In `viewer/index.html`, delete the entire `<div data-display-tools-home>…</div>` block (lines ~53–66: Layers `<details>`, Overlays `<details>`, Saved Views `<section>`).

Then, immediately **after** the closing `</div>` of `.task-panel` (the `data-task-panel` div) and **before** `</aside>` of `.cockpit-rail`, insert:

```html
<div class="display-strip" data-display-strip>
  <h2>Display</h2>
  <div class="category-switches" data-category-switches></div>
  <details class="layer-tree">
    <summary>All layers</summary>
    <div data-layer-list></div>
  </details>
  <section class="saved-views-block">
    <h2>Saved Views</h2>
    <div data-saved-views></div>
  </section>
</div>
```

- [ ] **Step 2: Verify the build still parses the HTML**

Run: `cd viewer && npm run build`
Expected: build succeeds; no reference errors for removed ids at build time (JS still references `data-overlay-list` until Task 5 — that resolves to `null` at runtime, not a build failure).

- [ ] **Step 3: Commit**

```bash
git add viewer/index.html
git commit -m "refactor(viewer): pin display controls in an always-visible strip"
```

---

### Task 5: Flat rail, display-strip render, preset wiring

**Files:**
- Modify: `viewer/src/app.js`
- Test: `viewer/test/workflow-rendering.test.js`

**Interfaces:**
- Consumes: `categorizeLayers`, `applyTaskVisibilityPreset` from `./sceneLoader.js`; `visibilityPresetForTask` indirectly via `applyTaskVisibilityPreset`.
- Produces: no new module exports; behavioral — rail renders a flat button list (no `<section>`/`<h2>` groups), `renderDisplayStrip` renders category tri-state switches + tree + saved views, task activation applies the preset, initial load applies the default task's preset.

- [ ] **Step 1: Write the failing test (source-shape assertions)**

`workflow-rendering.test.js` asserts against source text (it reads `src/app.js`/`styles.css` as strings). Add:

```js
test("app renders a pinned display strip with category switches and applies presets", async () => {
  const app = await readFile(new URL("src/app.js", viewerRoot), "utf8");
  assert.match(app, /data-display-strip|data-category-switches/);
  assert.match(app, /renderDisplayStrip/);
  assert.match(app, /applyTaskVisibilityPreset/);
  // Rail no longer groups tasks under Review/Explore/Display headings:
  assert.doesNotMatch(app, /\["Explore", \[/);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd viewer && node --test test/workflow-rendering.test.js`
Expected: FAIL — `renderDisplayStrip`/`applyTaskVisibilityPreset` absent; `["Explore", [` still present.

- [ ] **Step 3: Update imports and dom refs**

In `viewer/src/app.js`:

Add to the `./sceneLoader.js` import:
```js
import { applyTaskVisibilityPreset, categorizeLayers, createViewerState, loadSceneBundleFromUrl, setLayerVisibility } from "./sceneLoader.js";
```

In the `dom` object: remove the `overlayList` and `displayToolsHome` entries; add:
```js
  displayStrip: document.querySelector("[data-display-strip]"),
  categorySwitches: document.querySelector("[data-category-switches]"),
```
(Keep `layerList` and `savedViews` — they still exist, relocated.)

- [ ] **Step 4: Flatten the rail render**

Replace the `for (const [headingText, ids] of [...])` grouping loop in `renderTaskRail` with a flat render over the visible ids (no `<section>`/`<h2>`):

```js
function renderTaskRail() {
  dom.workflowTabs.replaceChildren();
  dom.taskRail.hidden = currentState.embed;
  dom.appHeader.hidden = currentState.embed;
  for (const id of getVisibleCockpitTaskIds(currentState)) {
    const task = WORKFLOW_TABS.find((candidate) => candidate.id === id);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "task-button";
    button.dataset.task = id;
    button.setAttribute("aria-current", id === currentState.activeTab ? "page" : "false");
    button.textContent = task.label;
    button.addEventListener("click", () => activateTask(id));
    button.addEventListener("keydown", (event) => {
      const nextId = workflowTabForKey(currentState, id, event.key);
      if (!nextId) return;
      event.preventDefault();
      activateTask(nextId);
      dom.workflowTabs.querySelector(`[data-task="${nextId}"]`)?.focus();
    });
    dom.workflowTabs.append(button);
  }
}
```

Import `getVisibleCockpitTaskIds` — confirm it is already in the `./workflowState.js` import block (it is). Remove the now-unused `getVisibleCockpitTaskIds` heading grouping only; keep the import.

- [ ] **Step 5: Apply preset on task switch and drop displayToolsHome from the panel map**

In `activateTask`:
```js
function activateTask(id) {
  currentState = reduceViewerState(currentState, { type: "setWorkflowTab", tabId: id });
  currentState = applyTaskVisibilityPreset(currentState, id);
  selectedObjectId = currentState.selectedObjectIds[0] ?? selectedObjectId;
  render();
}
```

In `renderTaskPanel`, remove the `"3d": dom.displayToolsHome` line from the `home` map (and the `if (currentState.activeTab === "3d") renderSavedViews();` line — saved views now render in the strip). The map becomes:
```js
  const home = {
    model: dom.modelToolsHome,
    results: dom.resultToolsHome,
    diagnostics: dom.issueToolsHome
  }[currentState.activeTab];
  if (home) dom.taskPanel.append(home);
```

- [ ] **Step 6: Replace renderOverlays with renderDisplayStrip; render it in `render()`**

In `render()`, delete the `renderLayers();` line and replace the `renderOverlays();` line with a single `renderDisplayStrip();` — the strip drives both the category switches and the tree, so `render()` no longer calls `renderLayers`/`renderLayerTree` directly.

Delete both the `renderOverlays` and the old flat `renderLayers` functions. Add `renderDisplayStrip`, `renderLayerTree`, and `layerToggle` (below); `renderLayerTree` renders the hierarchical tree into `dom.layerList`:

```js
function renderDisplayStrip() {
  dom.displayStrip.hidden = currentState.embed;
  dom.categorySwitches.replaceChildren();
  const categories = categorizeLayers(currentState.layers);
  for (const category of categories) {
    const label = document.createElement("label");
    label.className = "category-switch";
    const input = document.createElement("input");
    input.type = "checkbox";
    const visibles = category.layerIds.map((id) => currentState.layers[id]?.visible !== false);
    input.checked = visibles.every(Boolean);
    input.indeterminate = !input.checked && visibles.some(Boolean);
    input.addEventListener("change", () => {
      let next = currentState;
      for (const layerId of category.layerIds) {
        next = setLayerVisibility(next, layerId, input.checked);
      }
      currentState = next;
      render();
    });
    label.append(input, ` ${category.label}`);
    dom.categorySwitches.append(label);
  }
  renderLayerTree(categories);
  renderSavedViews();
}

function renderLayerTree(categories) {
  dom.layerList.replaceChildren();
  for (const category of categories) {
    const group = document.createElement("section");
    const heading = document.createElement("h3");
    heading.textContent = category.label;
    group.append(heading);
    for (const leaf of category.leaves) {
      group.append(layerToggle(leaf));
    }
    for (const sub of category.groups) {
      const details = document.createElement("details");
      const summary = document.createElement("summary");
      summary.textContent = `${sub.label} (${sub.leaves.length})`;
      details.append(summary);
      for (const leaf of sub.leaves) {
        details.append(layerToggle(leaf));
      }
      group.append(details);
    }
    dom.layerList.append(group);
  }
}

function layerToggle(leaf) {
  const layer = currentState.layers[leaf.layerId];
  const label = document.createElement("label");
  const input = document.createElement("input");
  input.type = "checkbox";
  input.checked = layer?.visible !== false;
  input.addEventListener("change", () => {
    currentState = setLayerVisibility(currentState, leaf.layerId, input.checked);
    render();
  });
  label.append(input, ` ${leaf.label} (${leaf.count})`);
  return label;
}
```

Note: the layer-state / code-aster e2e uses `getByLabel(/Deformed Visual Centerline/)` etc. — those leaf labels come from `leafLabel` now. `deformed:visual_centerline` → "Visual Centerline"; the object-kind fallback layer label may differ from before. Task 6 reconciles e2e label expectations.

- [ ] **Step 7: Apply the default preset on initial load only**

In `loadBundle`, after `currentState` is assigned and before `activeEvidenceTab` is set, apply the preset for the active tab when this is a fresh load (not a live-preview preserve):

```js
  if (!options.preserve) {
    currentState = applyTaskVisibilityPreset(currentState, currentState.activeTab);
  }
```

- [ ] **Step 8: Run tests**

Run: `cd viewer && node --test test/workflow-rendering.test.js && node --test`
Expected: the new rendering test passes; run the full `node --test` suite — all node unit tests pass (fix any assertion in other test files that referenced removed functions like a direct `renderOverlays`; none should import from app.js since it has no exports).

- [ ] **Step 9: Commit**

```bash
git add viewer/src/app.js viewer/test/workflow-rendering.test.js
git commit -m "feat(viewer): flat task rail + display strip with categorized layer tree"
```

---

### Task 6: Style the strip and reconcile e2e

**Files:**
- Modify: `viewer/src/styles.css`
- Modify: `viewer/scripts/e2e-smoke.mjs`

**Interfaces:**
- Consumes: DOM hooks `data-display-strip`, `data-category-switches`, `.layer-tree`, `.category-switch` from Tasks 4–5.
- Produces: styling only + updated e2e scenarios that reflect the new task labels and layer controls.

- [ ] **Step 1: Establish the pre-existing e2e baseline**

Run each scenario and record which pass **before** your changes are relevant (do this against your Task-5 branch). Focus on the scenarios that exercise the changed UI:

```bash
cd viewer
npm run e2e review-workflow
npm run e2e public-code-aster-review
npm run e2e legacy-workflow
npm run e2e layer-state
npm run e2e embedded-review
```

Expected before this task: `legacy-workflow`, `layer-state`, and any scenario clicking `"Display"`/`"Load Cases"` buttons or `[data-display-tools-home]`/`[data-overlay-list]` will FAIL (those selectors/labels no longer exist). `code-aster-results` and `clash-review` were already failing pre-redesign (stale "3D"/"Summary" tabs) — leave them.

- [ ] **Step 2: Style the display strip**

Add to `viewer/src/styles.css` (follow existing `.cockpit-rail` token usage — reuse existing custom properties for color/spacing; match the `.task-panel` look):

```css
.display-strip {
  border-top: 1px solid var(--rail-border, rgba(255, 255, 255, 0.12));
  padding: 0.5rem 0.75rem;
  display: grid;
  gap: 0.5rem;
}
.display-strip[hidden] { display: none; }
.category-switches {
  display: grid;
  gap: 0.25rem;
}
.category-switch { display: flex; align-items: center; gap: 0.35rem; }
.layer-tree > summary { cursor: pointer; }
.layer-tree section { margin: 0.25rem 0 0.25rem 0.25rem; }
.layer-tree h3 {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  opacity: 0.7;
  margin: 0.4rem 0 0.2rem;
}
.layer-tree details { margin-left: 0.5rem; }
```

Adjust the exact custom-property names to those already defined in `styles.css` (grep for `--rail`/existing border tokens; if none, reuse the color used by other `.cockpit-rail` borders).

- [ ] **Step 3: Update e2e scenarios**

In `viewer/scripts/e2e-smoke.mjs`:

`layer-state` scenario — replace the `[data-display-tools-home] details … Layers` open logic (the strip's tree is `<details class="layer-tree">`) and the `getByLabel(/Overlay Clash/)` per-overlay toggle:
```js
    async run(page) {
      const layers = page.locator(".layer-tree");
      await layers.evaluate((details) => { details.open = true; });
      assert.equal(await layers.evaluate((details) => details.open), true);
      await page.getByLabel(/Deformed Visual Centerline/).uncheck();
      await page.waitForFunction(() => {
        const ids = window.__tubaViewer?.lastRender?.objectIds ?? [];
        return ids.length === 2 && ids.includes("object:cold") && ids.includes("object:clash") && !ids.includes("object:deformed");
      });
      await page.getByLabel(/^\s*Overlays\s*$/).uncheck(); // category switch hides overlay:* layers
      await page.waitForFunction(() => {
        const ids = window.__tubaViewer?.lastRender?.objectIds ?? [];
        return ids.length === 1 && ids[0] === "object:cold";
      });
    }
```
(Confirm the actual leaf label the fixture produces by reading `test/fixtures/layer_state_scene` layer ids; adjust the `getByLabel` regexes to the cleaned labels `leafLabel` yields. If the fixture's overlay is the only overlay, the "Overlays" category switch is the reliable off-toggle.)

`legacy-workflow` scenario — the default task is now **Model**, not Display:
```js
    async run(page) {
      const modelTask = page.getByRole("button", { name: "Model", exact: true });
      await modelTask.waitFor();
      assert.equal(await modelTask.getAttribute("aria-current"), "page");
      assert.equal(await page.getByRole("button", { name: "Issues", exact: true }).count(), 1);
      assert.equal(await page.getByRole("button", { name: "Review", exact: true }).count(), 0);
      assert.equal(await page.getByRole("button", { name: "Display", exact: true }).count(), 0);
      // …keep the tab/report/canvas assertions…
      const legacyState = await page.evaluate(() => ({
        activeTab: window.__tubaViewer?.state?.activeTab,
        legacyReview: window.__tubaViewer?.state?.legacyReview,
        review: window.__tubaViewer?.state?.review,
        reviewDiagnostics: window.__tubaViewer?.state?.reviewDiagnostics
      }));
      assert.deepEqual(legacyState, { activeTab: "model", legacyReview: true, review: null, reviewDiagnostics: [] });
    }
```

`review-workflow` scenario — remove the clicks on `"Load Cases"` and `"Display"` task buttons (lines that do `getByRole("button", { name: "Load Cases" })` and `{ name: "Display" }`); keep the `Model` and `Results` clicks. The canvas-identity assertions around them stay, just drop the two removed destinations.

`code-aster-results` (`getByLabel(/Deformed Visual Centerline/)` / `/Deformed Physical Centerline/`) — these labels still exist as leaves under Results; open `.layer-tree` first if the details is collapsed:
```js
      await page.locator(".layer-tree").evaluate((details) => { details.open = true; });
```
before the `.uncheck()` calls. (This scenario is otherwise already stale — only fix if you choose to revive it; not required by this plan.)

- [ ] **Step 4: Run the reconciled scenarios**

Run:
```bash
cd viewer
npm run e2e review-workflow
npm run e2e public-code-aster-review
npm run e2e legacy-workflow
npm run e2e layer-state
npm run e2e embedded-review
```
Expected: all five PASS. If a `getByLabel` regex misses, read the fixture's layer ids and correct the cleaned label.

- [ ] **Step 5: Full unit suite + build**

Run: `cd viewer && node --test && npm run build`
Expected: all unit tests PASS; build succeeds.

- [ ] **Step 6: Commit**

```bash
git add viewer/src/styles.css viewer/scripts/e2e-smoke.mjs
git commit -m "style(viewer): display strip styling and e2e reconciliation"
```

---

### Task 7: Manual verification

**Files:** none (verification only)

- [ ] **Step 1: Launch the dev server against the demo bundle**

Run: `cd viewer && npm run dev`, open the printed URL with `?bundle=code-aster-review`.

- [ ] **Step 2: Confirm the redesign end to end**

Verify:
- Rail shows exactly four buttons: Review, Model, Results, Issues — no group headings, no "Load Cases"/"Display".
- On load (Review active) the scene shows geometry + results + overlays; analysis-mesh nodes/elements/groups are hidden (no mesh wall in the viewport).
- Switching to Model hides result overlays; Results restores them; Issues shows markers. Each switch visibly changes the scene.
- The Display strip is pinned at the bottom and always visible: five (or fewer) category switches with correct checked/indeterminate state, an "All layers" collapsed tree whose Analysis mesh section nests mesh groups under a single collapsible "Groups (N)" node with clean labels ("GN N0", not "Analysis Mesh Group GN N0"), and Saved Views.
- Toggling a category switch flips all its layers; toggling one leaf sets the parent switch indeterminate.
- Embed mode (`&embed=1`) still hides the rail and strip and fills the viewport.

- [ ] **Step 3: Report results** — summarize what was verified and any deviations. This plan is complete when Tasks 1–6 are committed and Step 2 checks pass.
