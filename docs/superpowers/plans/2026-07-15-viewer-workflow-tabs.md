# Viewer Workflow Tabs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing Three.js scene inspector into a piping-engineering review workflow that consumes optional `review.json`, while retaining all current 3D/result/issue capabilities and legacy scene-only bundles.

**Architecture:** Three.js remains the viewport renderer. New small JavaScript modules load and validate the review sidecar, derive workflow navigation state, render authoritative report tables, and translate table entity references into existing selection/camera actions. `app.js` orchestrates the modules; it does not calculate engineering results.

**Tech Stack:** Existing Vite + TypeScript entrypoint, browser-native ES modules, Three.js 0.184, Node test runner, Playwright smoke runner, CSS.

## Global Constraints

- Complete `docs/superpowers/plans/2026-07-15-engineering-review-package.md` first; this plan consumes its `engineering_review.v1` contract.
- Keep Three.js and the existing scene state/renderer; do not add another visualization path.
- Do not calculate stresses, utilization, maxima, or compliance in JavaScript.
- Treat `review.json` 404 as a supported legacy condition; surface other load/parse failures as diagnostics.
- Default to Summary when review data is present, 3D for scene-only bundles, and 3D for all `embed=1` loads.
- Preserve active load case/result state when moving from a table to 3D.
- Preserve current live preview, scene diff, issue review, overlays, layer visibility, vector/deformation scale, selection, and property inspection behavior.
- Use semantic buttons/tabs/tables with keyboard-visible focus and responsive/print-safe layout.

---

### Task 1: Load and normalize optional engineering review data

**Files:**

- Create: `viewer/src/reviewLoader.js`
- Create: `viewer/test/review-loader.test.js`
- Modify: `viewer/src/sceneLoader.js`
- Modify: `viewer/test/scene-loader.test.js`
- Create: `viewer/test/fixtures/code_aster_results/review.json`

- [ ] **Step 1: Write failing review-loader tests**

```javascript
import { loadOptionalReview, normalizeReview } from "../src/reviewLoader.js";

test("loads review.json beside the scene bundle", async () => {
  const fetcher = async (url) => new Response(JSON.stringify(reviewFixture), { status: 200 });
  const result = await loadOptionalReview("/bundle", fetcher);
  assert.equal(result.review.schema_version, "engineering_review.v1");
  assert.equal(result.legacy, false);
});

test("treats review.json 404 as a supported legacy bundle", async () => {
  const result = await loadOptionalReview("/legacy", async () => new Response("", { status: 404 }));
  assert.deepEqual(result, { review: null, diagnostics: [], legacy: true });
});

test("reports malformed review data without fabricating tables", async () => {
  const result = await loadOptionalReview("/bundle", async () => new Response("{}", { status: 200 }));
  assert.equal(result.review, null);
  assert.equal(result.diagnostics[0].code, "viewer.review.invalid_contract");
});
```

Also cover trailing slashes, network failure, stable table order, and lookup normalization from the JSON `tables` mapping.

- [ ] **Step 2: Run the focused test and confirm RED**

Run: `npm.cmd test -- --test-name-pattern="review"`

Working directory: `viewer`

Expected: FAIL because `reviewLoader.js` does not exist.

- [ ] **Step 3: Implement optional loading and normalization**

```javascript
export async function loadOptionalReview(baseUrl = ".", fetcher = globalThis.fetch) {
  const uri = `${String(baseUrl).replace(/\/$/, "")}/review.json`;
  try {
    const response = await fetcher(uri);
    if (response.status === 404) return { review: null, diagnostics: [], legacy: true };
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return { review: normalizeReview(await response.json()), diagnostics: [], legacy: false };
  } catch (error) {
    return {
      review: null,
      legacy: false,
      diagnostics: [{ severity: "error", code: "viewer.review.load_failed", source: "review.json", message: String(error) }]
    };
  }
}
```

`normalizeReview` must require `schema_version === "engineering_review.v1"`, `analysis_status`, and a tables mapping; retain table/row values as data, not HTML.

- [ ] **Step 4: Integrate the sidecar into scene bundle loading**

Have `loadSceneBundleFromUrl` load the existing scene files first and then the optional review. Return `review`, `reviewDiagnostics`, and `legacyReview` on the bundle. Extend `createViewerState` with those fields without altering existing scene-derived fields.

- [ ] **Step 5: Run loader and existing scene tests and confirm GREEN**

Run: `npm.cmd test -- --test-name-pattern="review|loads scene|creates viewer state"`

Working directory: `viewer`

Expected: PASS.

- [ ] **Step 6: Commit optional review loading**

```powershell
git add viewer/src/reviewLoader.js viewer/src/sceneLoader.js viewer/test/review-loader.test.js viewer/test/scene-loader.test.js viewer/test/fixtures/code_aster_results/review.json
git commit -m "feat: load engineering review sidecars"
```

### Task 2: Add workflow navigation state and default rules

**Files:**

- Create: `viewer/src/workflowState.js`
- Create: `viewer/test/workflow-state.test.js`
- Modify: `viewer/src/viewerState.js`
- Modify: `viewer/test/viewer-state.test.js`

- [ ] **Step 1: Write failing tab/default tests**

```javascript
const WORKFLOW_TABS = ["summary", "model", "load-cases", "results", "compliance", "3d", "diagnostics"];

test("full review defaults to summary", () => {
  assert.equal(createWorkflowState({ review: reviewFixture, embed: false }).activeTab, "summary");
});

test("legacy and embed modes default to 3d", () => {
  assert.equal(createWorkflowState({ review: null, embed: false }).activeTab, "3d");
  assert.equal(createWorkflowState({ review: reviewFixture, embed: true }).activeTab, "3d");
});

test("legacy hides data tabs but retains diagnostics and 3d", () => {
  assert.deepEqual(getVisibleWorkflowTabs({ review: null }), ["3d", "diagnostics"]);
});
```

Also assert `setWorkflowTab` rejects hidden/unknown tabs and `preserveViewerStateForReload` keeps a still-valid active tab.

- [ ] **Step 2: Run state tests and confirm RED**

Run: `npm.cmd test -- --test-name-pattern="workflow|viewer state"`

Working directory: `viewer`

Expected: FAIL because the workflow module/actions do not exist.

- [ ] **Step 3: Implement workflow state as pure functions**

```javascript
export const WORKFLOW_TABS = Object.freeze([
  { id: "summary", label: "Summary", requiresReview: true },
  { id: "model", label: "Model", requiresReview: true },
  { id: "load-cases", label: "Load Cases", requiresReview: true },
  { id: "results", label: "Results", requiresReview: true },
  { id: "compliance", label: "Compliance", requiresReview: true },
  { id: "3d", label: "3D", requiresReview: false },
  { id: "diagnostics", label: "Diagnostics", requiresReview: false }
]);

export function defaultWorkflowTab({ review, embed }) {
  return embed || !review ? "3d" : "summary";
}
```

Add `setWorkflowTab` to `reduceViewerState`; keep selection/load-case/result-state fields untouched.

- [ ] **Step 4: Run workflow/viewer state tests and confirm GREEN**

Run: `npm.cmd test -- --test-name-pattern="workflow|viewer state"`

Working directory: `viewer`

Expected: PASS.

- [ ] **Step 5: Commit navigation state**

```powershell
git add viewer/src/workflowState.js viewer/src/viewerState.js viewer/test/workflow-state.test.js viewer/test/viewer-state.test.js
git commit -m "feat: add viewer workflow navigation state"
```

### Task 3: Render authoritative workflow summaries and tables

**Files:**

- Create: `viewer/src/reviewTables.js`
- Create: `viewer/test/review-tables.test.js`
- Modify: `viewer/index.html`
- Modify: `viewer/src/app.js`
- Modify: `viewer/test/scaffold.test.js`

- [ ] **Step 1: Write failing table-model tests**

Keep rendering logic testable without a DOM by producing view models and cell strings.

```javascript
test("maps workflow tabs to stable authoritative table ids", () => {
  assert.deepEqual(tableIdsForWorkflow("model"), ["nodes", "line_list", "section_schedule", "materials", "supports"]);
  assert.deepEqual(tableIdsForWorkflow("load-cases"), ["load_cases", "studies"]);
  assert.deepEqual(tableIdsForWorkflow("results"), ["result_summary", "displacements", "reactions", "element_forces", "fe_stress"]);
  assert.deepEqual(tableIdsForWorkflow("compliance"), ["code_compliance"]);
});

test("keeps FE stress basis visible", () => {
  const model = tableViewModel(reviewFixture.tables.fe_stress);
  assert.match(JSON.stringify(model), /FE Von Mises \(not piping-code stress\)/);
});

test("returns an explicit unavailable state", () => {
  assert.equal(workflowViewModel(modelOnlyReview, "results").unavailableReason, "Analysis has not been solved.");
});
```

Also test formatting of `null`, booleans, arrays/maps, units, pass/fail cells, diagnostics severity, governing entity refs, and absence of raw HTML injection.

- [ ] **Step 2: Run table tests and confirm RED**

Run: `npm.cmd test -- --test-name-pattern="review table|workflow tables"`

Working directory: `viewer`

Expected: FAIL because `reviewTables.js` does not exist.

- [ ] **Step 3: Implement data-only view models**

```javascript
const WORKFLOW_TABLES = Object.freeze({
  summary: ["project_summary", "result_summary"],
  model: ["nodes", "line_list", "section_schedule", "materials", "supports"],
  "load-cases": ["load_cases", "studies"],
  results: ["result_summary", "displacements", "reactions", "element_forces", "fe_stress"],
  compliance: ["code_compliance"],
  diagnostics: ["diagnostics"]
});

export function workflowViewModel(review, workflowId) {
  const tableIds = WORKFLOW_TABLES[workflowId] ?? [];
  const tables = tableIds.map((id) => review?.tables?.[id]).filter(Boolean).map(tableViewModel);
  if (tables.length > 0) return { workflowId, tables, unavailableReason: null };
  const unavailableReason = review?.analysis_status === "not_solved"
    ? "Analysis has not been solved."
    : workflowId === "compliance"
      ? "Code compliance is unavailable because no ComplianceReport was supplied."
      : "No review data is available for this workflow.";
  return { workflowId, tables: [], unavailableReason };
}
```

Return labels and plain cell strings. Leave DOM creation to `app.js` and assign values through `textContent`.

- [ ] **Step 4: Replace the top-level HTML inventory with a workflow shell**

Use semantic tabs and panels:

```html
<main class="app-shell" data-embed="false">
  <header class="app-header">
    <div><strong>Tuba Engineering Review</strong><span data-scene-title>Scene</span></div>
    <div data-scene-meta></div><div data-status>Starting</div>
  </header>
  <nav class="workflow-tabs" role="tablist" aria-label="Engineering review" data-workflow-tabs></nav>
  <section class="workflow-panel" role="tabpanel" data-workflow-panel></section>
  <section class="viewer-workspace" data-viewer-workspace hidden>
    <aside class="sidebar" data-scene-tools>
      <section data-layer-list></section><section data-overlay-list></section>
      <section data-result-controls></section><section data-result-legend></section>
      <section data-hotspot-list></section><section data-tree></section>
      <section data-issue-list></section><input type="search" data-search aria-label="Search objects">
      <section data-object-list></section>
    </aside>
    <section class="viewport"><canvas data-canvas width="1280" height="800"></canvas></section>
    <aside class="inspector">
      <div data-property-actions></div><div data-properties>Select an object.</div>
    </aside>
  </section>
  <section hidden data-diagnostic-list></section>
</main>
```

Move, rather than duplicate, the existing layer/overlay/result/hotspot/tree/issue/search/object/property elements into the 3D workspace. Keep every existing `data-*` hook.

- [ ] **Step 5: Add app orchestration for tabs and tables**

Render tab buttons from state. On click dispatch `setWorkflowTab`. Render Summary cards from `project_summary`/`result_summary`; render other review workflows as semantic tables. Results and Load Cases must retain existing active load-case/result-state controls above their tables. Compliance without a table must explicitly state that no `ComplianceReport` was supplied.

- [ ] **Step 6: Run table/scaffold/all unit tests and confirm GREEN**

Run:

```powershell
npm.cmd test -- --test-name-pattern="review table|workflow tables|scaffold"
npm.cmd test
```

Working directory: `viewer`

Expected: PASS, including all pre-existing scene/result/selection tests.

- [ ] **Step 7: Commit workflow rendering**

```powershell
git add viewer/src/reviewTables.js viewer/src/app.js viewer/index.html viewer/test/review-tables.test.js viewer/test/scaffold.test.js
git commit -m "feat: render engineering review workflows"
```

### Task 4: Bridge report rows to existing 3D selection and camera state

**Files:**

- Create: `viewer/src/reviewSelection.js`
- Create: `viewer/test/review-selection.test.js`
- Modify: `viewer/src/app.js`
- Modify: `viewer/src/selection.js`
- Modify: `viewer/test/selection.test.js`

- [ ] **Step 1: Write failing entity-resolution and state-preservation tests**

```javascript
test("resolves report entity refs to scene object ids", () => {
  assert.equal(resolveEntityObjectId(state, "element:pipe_0"), "object:element:pipe_0");
});

test("show in 3d selects, fits, and preserves result context", () => {
  const next = showReviewEntityIn3d(state, "element:pipe_0");
  assert.equal(next.activeWorkflowTab, "3d");
  assert.deepEqual(next.selectedObjectIds, ["object:element:pipe_0"]);
  assert.equal(next.activeLoadCase, state.activeLoadCase);
  assert.equal(next.activeResultStateId, state.activeResultStateId);
  assert.notDeepEqual(next.camera, state.camera);
});
```

Test object IDs, `entity_ref`, object-map fallback, missing entities, and nodes represented only by vector/marker objects.

- [ ] **Step 2: Run selection tests and confirm RED**

Run: `npm.cmd test -- --test-name-pattern="show in 3d|entity ref|selection"`

Working directory: `viewer`

Expected: FAIL because the review selection bridge does not exist.

- [ ] **Step 3: Implement the pure selection bridge**

```javascript
export function showReviewEntityIn3d(state, entityRef) {
  const objectId = resolveEntityObjectId(state, entityRef);
  if (!objectId) return state;
  const selected = selectObject(state, objectId);
  return fitSelection(Object.assign({}, selected, { activeWorkflowTab: "3d" }));
}
```

Do not modify active load/result fields. Return unchanged state for unresolved refs and let the app show a nonfatal status message.

- [ ] **Step 4: Render `Show in 3D` only for resolvable rows**

Rows with `entity_ref` or `governing_entity_ref` get a button in an Actions column. The handler updates the store using the bridge, re-renders, and calls the existing renderer/camera update. Use the accessible name `Show <entity> in 3D`.

- [ ] **Step 5: Run selection and all viewer unit tests and confirm GREEN**

Run: `npm.cmd test`

Working directory: `viewer`

Expected: PASS.

- [ ] **Step 6: Commit table-to-3D navigation**

```powershell
git add viewer/src/reviewSelection.js viewer/src/app.js viewer/src/selection.js viewer/test/review-selection.test.js viewer/test/selection.test.js
git commit -m "feat: link review rows to 3d selection"
```

### Task 5: Finish responsive workflow styling, diagnostics, and embed behavior

**Files:**

- Modify: `viewer/src/styles.css`
- Modify: `viewer/src/app.js`
- Modify: `viewer/index.html`
- Modify: `viewer/test/scaffold.test.js`
- Create: `viewer/test/workflow-rendering.test.js`

- [ ] **Step 1: Write failing structural behavior tests**

Assert the HTML/CSS/app contract includes `role="tablist"`, keyboard-operable tab buttons, the seven labels, responsive table overflow, status badges, visible focus, and an embed selector that hides non-3D workflow chrome. Add a pure keyboard helper test for ArrowLeft/ArrowRight/Home/End.

- [ ] **Step 2: Run workflow rendering tests and confirm RED**

Run: `npm.cmd test -- --test-name-pattern="workflow rendering|scaffold"`

Working directory: `viewer`

Expected: FAIL on the new styling/keyboard/embed assertions.

- [ ] **Step 3: Implement the workflow visual hierarchy**

Style a compact header, sticky workflow tabs, status/provenance summary cards, horizontally scrollable tables, severity/pass/fail badges, and the existing three-column 3D workspace. At narrow widths stack the 3D sidebars below the viewport. Add `:focus-visible` outlines and `prefers-reduced-motion` handling.

```css
.review-table-scroll { overflow-x: auto; }
.workflow-tab[aria-selected="true"] { border-color: var(--accent); color: var(--accent); }
.status-badge[data-status="solved"], .verdict[data-pass="true"] { color: var(--success); }
[data-embed="true"] .app-header,
[data-embed="true"] .workflow-tabs { display: none; }
```

- [ ] **Step 4: Consolidate diagnostics**

The Diagnostics workflow lists review diagnostics, review provenance, scene diagnostics, issues, and preview/load diagnostics with source/code/target. Keep the existing scene issue controls in the 3D tools; do not duplicate issue state.

- [ ] **Step 5: Enforce embed behavior at startup and reload**

Parse `embed=1` once, keep the active workflow on 3D after scene reload/live preview, and retain the existing compact canvas behavior.

- [ ] **Step 6: Run unit tests and production build**

Run:

```powershell
npm.cmd test
npm.cmd run build
```

Working directory: `viewer`

Expected: PASS; Vite build exits 0 with no unresolved import or oversized-chunk regression beyond the configured limit.

- [ ] **Step 7: Commit styling/embed behavior**

```powershell
git add viewer/src/styles.css viewer/src/app.js viewer/index.html viewer/test/scaffold.test.js viewer/test/workflow-rendering.test.js
git commit -m "feat: finish responsive review viewer workflow"
```

### Task 6: Add browser workflow coverage and publish the review-enabled viewer artifact

**Files:**

- Modify: `viewer/scripts/e2e-smoke.mjs`
- Modify: `viewer/test/fixtures/code_aster_results/review.json`
- Modify: `viewer/public/code-aster-review/review.json`
- Modify: `viewer/public/code-aster-review/report_manifest.json`
- Modify: `viewer/public/code-aster-review/index.html`
- Modify: `viewer/public/code-aster-review/reports/*.csv`
- Modify: `docs/site/index.html`
- Modify: `docs/tuba-workflow.md`

- [ ] **Step 1: Add failing Playwright scenarios**

Add `review-workflow`, `legacy-workflow`, and `embedded-review` scenarios:

```javascript
"review-workflow": {
  bundle: "/test/fixtures/code_aster_results",
  minimumObjects: 7,
  async run(page) {
    await page.getByRole("tab", { name: "Summary" }).waitFor();
    await page.getByRole("tab", { name: "Model" }).click();
    await page.getByRole("tab", { name: "Load Cases" }).click();
    await page.getByRole("tab", { name: "Results" }).click();
    await page.getByRole("button", { name: /Show element:pipe:hot in 3D/ }).click();
    await page.waitForFunction(() => window.__tubaViewer?.state?.selectedObjectIds?.includes("object:pipe:hot"));
  }
}
```

Legacy must open on 3D without a review-load error. Embed must hide workflow tabs and render a nonblank WebGL frame. Reuse the existing pixel/hash frame assertion.

- [ ] **Step 2: Run new E2E and confirm RED**

Run:

```powershell
npm.cmd run e2e -- review-workflow
npm.cmd run e2e -- legacy-workflow
npm.cmd run e2e -- embedded-review
```

Working directory: `viewer`

Expected: FAIL until scenario routing/fixtures and UI behavior are complete.

- [ ] **Step 3: Complete scenario routing and fixtures**

Add the scenarios to the E2E runner's scenario registry. Ensure the review fixture uses the same IDs as the code-aster scene fixture and contains FE—not compliance—stress unless a real compliance table is deliberately included.

- [ ] **Step 4: Run all browser scenarios and confirm GREEN**

Run:

```powershell
npm.cmd run e2e -- review-workflow
npm.cmd run e2e -- legacy-workflow
npm.cmd run e2e -- embedded-review
npm.cmd run e2e -- code-aster-results
npm.cmd run e2e -- clash-review
npm.cmd run e2e -- scene-inspection
```

Working directory: `viewer`

Expected: PASS with nonblank WebGL proof and preserved result/issue behavior.

- [ ] **Step 5: Regenerate and copy the public Code_Aster review package**

Run from repository root: `python examples/code_aster_artifact_review.py`

Copy the generated review directory into `viewer/public/code-aster-review/` using PowerShell `Copy-Item -Recurse -Force`, then inspect the diff. This is generated artifact publication, not permission to alter unrelated public assets.

- [ ] **Step 6: Update public docs**

In `docs/site/index.html` and `docs/tuba-workflow.md`, describe the viewer as the interactive consumer of the engineering review package. Show Summary/Model/Load Cases/Results/Compliance/3D/Diagnostics and retain the distinction between PyVista quick-look and the Three.js review bundle.

- [ ] **Step 7: Run final viewer and cross-boundary gates**

Run:

```powershell
python -m pytest tests/test_reporting_model.py tests/test_reporting_tables.py tests/test_reporting_builder.py tests/test_reporting_compliance.py tests/test_reporting_export.py tests/test_visualization_reports.py tests/test_visualization_static_report.py tests/test_code_aster_artifact_import.py -q
Set-Location viewer
npm.cmd test
npm.cmd run build
npm.cmd run e2e -- review-workflow
npm.cmd run e2e -- legacy-workflow
npm.cmd run e2e -- embedded-review
Set-Location ..
```

Expected: all PASS. Run the repository-documented real Code_Aster smoke command when its runtime is configured; otherwise record the exact runtime blocker rather than treating the generated/export-only fixture as solver proof.

- [ ] **Step 8: Commit the workflow release slice**

```powershell
git add viewer/scripts/e2e-smoke.mjs viewer/test/fixtures/code_aster_results/review.json viewer/public/code-aster-review docs/site/index.html docs/tuba-workflow.md
git commit -m "feat: publish workflow-oriented engineering viewer"
```

- [ ] **Step 9: Verify the final branch state**

Run:

```powershell
git status --short
git log --oneline -10
```

Expected: clean status except explicitly preserved user-owned changes; recent commits show the review package before the viewer workflow.
