# Review Cockpit Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the viewer's seven equal-weight pages and permanent debug inventory with the approved review cockpit while preserving the existing Code_Aster-backed tables, state reducers, Three.js viewport, and embed mode.

**Architecture:** Keep `activeTab` and the existing table/rendering functions as internal compatibility seams. Add one pure status view-model helper, reorganize the existing DOM into a persistent viewport with a task rail, contextual inspector, and evidence dock, then restyle it with CSS grid. Do not add a framework, dependency, router, or scene schema.

**Tech Stack:** Vanilla TypeScript/JavaScript, semantic HTML, CSS Grid, Three.js, Node test runner, Playwright smoke tests.

## Global Constraints

- Code_Aster-backed values remain authoritative; the browser must not calculate or fabricate solver/compliance results.
- Missing compliance is displayed as `Not available`, never `Pass` or `Fail`.
- Legacy scene-only bundles and `embed=1` retain usable 3D review.
- Reuse `workflowViewModel`, the existing reducers, result controls, selection bridge, and cached Three.js viewport.
- No new runtime dependency, UI framework, route state, chat surface, or editing feature.
- Preserve the unrelated modification in `notebooks/01_building_piping_systems.ipynb`.

---

### Task 1: Authoritative cockpit status view model

**Files:**
- Modify: `viewer/src/reviewTables.js`
- Test: `viewer/test/review-tables.test.js`

**Interfaces:**
- Consumes: `EngineeringReviewPackage` JSON already passed to `workflowViewModel(review, tabId)`.
- Produces: `cockpitStatusViewModel(review)` returning `{ analysisStatus, complianceStatus, governingLoadCase, warningCount, governingRatio, governingLocation }`, with absent values represented by `"Not available"`.

- [ ] **Step 1: Write failing status-model tests**

Add tests that pass a review containing `project_summary`, `result_summary`, `code_compliance`, and `diagnostics` tables, then assert exact values. Add a second test without `code_compliance` and assert `complianceStatus`, `governingRatio`, and `governingLocation` are `"Not available"`.

```js
test("cockpit status exposes authoritative governing evidence", () => {
  const status = cockpitStatusViewModel(reviewWithCompliance);
  assert.deepEqual(status, {
    analysisStatus: "compliance_complete",
    complianceStatus: "Pass",
    governingLoadCase: "Operating",
    warningCount: 2,
    governingRatio: "0.82",
    governingLocation: "element:pipe_b04"
  });
});

test("cockpit status keeps missing compliance neutral", () => {
  const status = cockpitStatusViewModel(reviewWithoutCompliance);
  assert.equal(status.complianceStatus, "Not available");
  assert.equal(status.governingLoadCase, "Not available");
  assert.equal(status.governingRatio, "Not available");
  assert.equal(status.governingLocation, "Not available");
});
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `cd viewer && npm.cmd test -- --test-name-pattern="cockpit status"`

Expected: FAIL because `cockpitStatusViewModel` is not exported.

- [ ] **Step 3: Implement the minimal pure helper**

Use the existing normalized `columns` and `rows` table contract. Read cell values by column ID; do not infer engineering values from scene objects.

```js
export function cockpitStatusViewModel(review) {
  const unavailable = "Not available";
  const table = (id) => review?.tables?.[id] ?? null;
  const compliance = table("code_compliance");
  const complianceRows = compliance?.rows ?? [];
  const governing = complianceRows.reduce((best, row) => {
    const candidates = [
      { ratio: Number(row.sustained_ratio), kind: "Sustained" },
      { ratio: Number(row.expansion_ratio), kind: "Expansion" }
    ].filter(({ ratio }) => Number.isFinite(ratio));
    const candidate = candidates.sort((left, right) => right.ratio - left.ratio)[0];
    return candidate && (!best || candidate.ratio > best.ratio) ? { ...candidate, row } : best;
  }, null);
  const diagnostics = table("diagnostics");
  const compliancePassed = complianceRows.every((row) => row.sustained_pass === true && row.expansion_pass === true);
  return {
    analysisStatus: review?.analysis_status ?? unavailable,
    complianceStatus: complianceRows.length === 0 ? unavailable : compliancePassed ? "Pass" : "Fail",
    governingLoadCase: governing?.row?.load_case ?? unavailable,
    warningCount: (diagnostics?.rows ?? []).filter((row) => row.severity === "warning").length,
    governingRatio: governing ? String(governing.ratio) : unavailable,
    governingLocation: governing?.row?.entity_ref ?? unavailable
  };
}
```

- [ ] **Step 4: Run the focused test and verify GREEN**

Run: `cd viewer && npm.cmd test -- --test-name-pattern="cockpit status"`

Expected: both cockpit-status tests PASS.

- [ ] **Step 5: Commit Task 1**

```text
git add -- viewer/src/reviewTables.js viewer/test/review-tables.test.js
git commit -m feat-viewer-cockpit-status
```

---

### Task 2: Persistent cockpit DOM and interaction flow

**Files:**
- Modify: `viewer/index.html`
- Modify: `viewer/src/app.js`
- Modify: `viewer/src/workflowState.js`
- Modify: `viewer/src/reviewSelection.js`
- Reuse: `viewer/src/controls.js` (`saveViewState`, `restoreViewState`)
- Test: `viewer/test/scaffold.test.js`
- Test: `viewer/test/workflow-state.test.js`
- Test: `viewer/test/workflow-rendering.test.js`
- Test: `viewer/test/review-selection.test.js`

**Interfaces:**
- Consumes: `cockpitStatusViewModel(review)`, existing `activeTab`, `setWorkflowTab`, `workflowViewModel`, `showReviewEntityIn3d`, and selection functions.
- Produces: DOM regions `[data-cockpit-status]`, `[data-task-rail]`, `[data-task-panel]`, `[data-evidence-dock]`, persistent `[data-viewer-workspace]`, and contextual `[data-inspector]`.

- [ ] **Step 1: Write failing scaffold and state tests**

Assert that the HTML contains the five approved regions and no top-level `.workflow-tabs`. Update workflow state expectations so the same internal IDs render in cockpit order and labels:

```js
assert.deepEqual(
  WORKFLOW_TABS.map(({ id, label }) => [id, label]),
  [
    ["summary", "Review"],
    ["model", "Model"],
    ["load-cases", "Load Cases"],
    ["results", "Results"],
    ["diagnostics", "Issues"],
    ["3d", "Display"],
    ["compliance", "Compliance"]
  ]
);
assert.equal(createWorkflowState({ review: reviewFixture }).activeTab, "summary");
```

Compliance remains an evidence-dock destination and is omitted from the primary task-rail button set. Export `getVisibleCockpitTaskIds(state)` for `summary`, `model`, `load-cases`, `results`, `diagnostics`, and `3d`; make `workflowTabForKey` use that list so keyboard navigation never focuses the hidden Compliance destination. Legacy state still exposes `3d` and `diagnostics`.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `cd viewer && node --test test/scaffold.test.js test/workflow-state.test.js test/workflow-rendering.test.js`

Expected: FAIL on missing cockpit regions and old labels/order.

- [ ] **Step 3: Restructure `index.html` using existing elements**

Move, rather than duplicate, the current controls. Wrap raw layer, overlay, tree, and object inventories in native `<details>` elements so they start collapsed. The resulting structure is:

```html
<header class="app-header" data-app-header>
  <div class="app-identity"><span class="app-kicker">TUBA / ENGINEERING REVIEW</span><strong data-scene-title>Scene</strong></div>
  <div class="meta" data-scene-meta></div>
  <a class="report-link" data-report-link>Open Report</a>
  <div class="runtime-status" data-status role="status" aria-live="polite">Starting</div>
</header>
<section class="cockpit-status" aria-label="Engineering review status" data-cockpit-status></section>
<section class="viewer-workspace" data-viewer-workspace>
  <aside class="cockpit-rail" data-task-rail>
    <nav aria-label="Engineering review tasks" data-workflow-tabs></nav>
    <div class="task-panel" data-task-panel>
      <!-- existing result, issue, tree, search, object, layer, and overlay homes -->
    </div>
  </aside>
  <section class="viewport">
    <canvas data-canvas tabindex="0" aria-label="Interactive 3D engineering review viewport" width="1280" height="800"></canvas>
  </section>
  <aside class="inspector" data-inspector hidden>
    <h2>Selected Evidence</h2>
    <div class="property-actions" data-property-actions></div>
    <div class="property-sections" data-properties></div>
  </aside>
  <section class="evidence-dock" aria-label="Engineering evidence" data-evidence-dock>
    <button type="button" data-evidence-expand>Expand Evidence</button>
    <nav class="evidence-tabs" aria-label="Evidence views" data-evidence-tabs></nav>
    <div class="workflow-panel" data-workflow-panel></div>
  </section>
</section>
```

- [ ] **Step 4: Convert tab rendering into task-rail rendering**

Keep `activeTab` and reducer actions. Render primary task buttons with `aria-current="page"` instead of top-level tab roles. Render Compliance as a dock tab. The persistent viewport is never hidden for a review bundle.

```js
function renderTaskRail() {
  dom.workflowTabs.replaceChildren();
  const primaryIds = currentState.review
    ? ["summary", "model", "load-cases", "results", "diagnostics", "3d"]
    : ["3d", "diagnostics"];
  for (const id of primaryIds) {
    const task = WORKFLOW_TABS.find((candidate) => candidate.id === id);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "task-button";
    button.dataset.task = id;
    button.setAttribute("aria-current", id === currentState.activeTab ? "page" : "false");
    button.textContent = task.label;
    button.addEventListener("click", () => activateTask(id));
    dom.workflowTabs.append(button);
  }
}
```

`activateTask(id)` dispatches the existing `setWorkflowTab` action and calls `render()`. Arrow, Home, and End behavior stays in `workflowTabForKey` for the ordered primary tasks.

`renderEvidenceTabs()` exposes `summary` as Governing Results, `diagnostics` as Warnings, and `compliance` as Compliance. These buttons use tab semantics because they change the dock panel; task-rail buttons use normal navigation semantics.

- [ ] **Step 5: Render status, contextual tools, and evidence dock**

Add `renderCockpitStatus()` using `cockpitStatusViewModel`. Move existing DOM nodes among their single homes based on `activeTab`: model uses tree/search/objects, results uses result controls/hotspots, issues uses issue/diagnostic content, display uses layers/overlays. Group the existing task buttons under Review, Explore, and Display headings. Do not clone controls.

Update `renderHeader()` from authoritative top-level review metadata:

```js
dom.sceneTitle.textContent = currentState.review?.project_name ?? currentState.sceneId;
dom.sceneMeta.textContent = currentState.review
  ? `${currentState.review.model_standard} · Revision ${currentState.review.model_revision} · ${currentState.review.units.length} / ${currentState.review.units.force} / ${currentState.review.units.stress}`
  : `${currentState.objects.length} objects | ${currentState.issues.length} issues`;
```

Wire the already-implemented `saveViewState` and `restoreViewState` helpers into Display with one in-memory `savedViews` array. `Save Current View` creates `View 1`, `View 2`, and so on; clicking a saved-view button restores it. Do not add persistence or a naming dialog.

```js
function renderCockpitStatus() {
  dom.cockpitStatus.replaceChildren();
  if (!currentState.review) return;
  const status = cockpitStatusViewModel(currentState.review);
  for (const [label, value] of [
    ["Analysis", status.analysisStatus],
    ["Compliance", status.complianceStatus],
    ["Governing case", status.governingLoadCase],
    ["Attention", `${status.warningCount} warning(s)`],
    ["Governing ratio", status.governingRatio]
  ]) {
    dom.cockpitStatus.append(renderOverviewCard(label, value, label === "Analysis" ? "status" : "text"));
  }
}
```

`renderProperties()` sets `dom.inspector.hidden = sections.length === 0 && !issueSummary`. Change `showReviewEntityIn3d()` to select and fit without replacing `activeTab`; the persistent viewport no longer needs a page switch. Update its test to assert `next.activeTab === state.activeTab`.

When `renderReviewTable()` resolves a row action whose `objectId` is in `currentState.selectedObjectIds`, set `tableRow.dataset.selected = "true"`. This is the reverse 3D-to-evidence highlight and uses the existing selection bridge.

Set `[data-report-link].href` to `${currentBundleUrl}/index.html`. The evidence expand button toggles one `evidenceExpanded` boolean and the `.expanded` class; it introduces no reducer or persisted state.

- [ ] **Step 6: Run focused tests and verify GREEN**

Run: `cd viewer && node --test test/scaffold.test.js test/workflow-state.test.js test/workflow-rendering.test.js test/review-selection.test.js`

Expected: all selected tests PASS.

- [ ] **Step 7: Commit Task 2**

```text
git add -- viewer/index.html viewer/src/app.js viewer/src/workflowState.js viewer/src/reviewSelection.js viewer/test/scaffold.test.js viewer/test/workflow-state.test.js viewer/test/workflow-rendering.test.js viewer/test/review-selection.test.js
git commit -m feat-viewer-review-cockpit
```

---

### Task 3: Cockpit layout and responsive behavior

**Files:**
- Modify: `viewer/src/styles.css`
- Test: `viewer/test/workflow-rendering.test.js`

**Interfaces:**
- Consumes: the Task 2 region classes and `hidden` attributes.
- Produces: full desktop grid, inspector drawer below 1200 px, collapsed rail below 800 px, unchanged full-viewport embed mode.

- [ ] **Step 1: Add failing CSS-contract tests**

Assert these exact layout contracts:

```js
assert.match(css, /\.app-shell\s*\{[^}]*grid-template-rows:\s*auto auto minmax\(0, 1fr\)/s);
assert.match(css, /\.viewer-workspace\s*\{[^}]*grid-template-areas:[^;]*"rail viewport inspector"[^;]*"rail evidence inspector"/s);
assert.match(css, /@media\s*\(max-width:\s*1200px\)[\s\S]*\.inspector[\s\S]*position:\s*absolute/);
assert.match(css, /@media\s*\(max-width:\s*800px\)[\s\S]*\.cockpit-rail/);
assert.match(css, /\[data-embed="true"\][\s\S]*grid-template-areas:\s*"viewport"/);
```

- [ ] **Step 2: Run the CSS test and verify RED**

Run: `cd viewer && node --test test/workflow-rendering.test.js`

Expected: FAIL because cockpit selectors do not exist.

- [ ] **Step 3: Replace the old page/tab layout with the cockpit grid**

Use native CSS only:

```css
.viewer-workspace {
  position: relative;
  display: grid;
  grid-template-columns: 12rem minmax(24rem, 1fr) minmax(16rem, 20rem);
  grid-template-rows: minmax(0, 1fr) minmax(8rem, 28vh);
  grid-template-areas:
    "rail viewport inspector"
    "rail evidence inspector";
  min-height: 0;
}

.cockpit-rail { grid-area: rail; overflow: auto; }
.viewport { grid-area: viewport; min-width: 0; min-height: 0; }
.inspector { grid-area: inspector; overflow: auto; }
.evidence-dock { grid-area: evidence; min-width: 0; overflow: auto; }
.inspector[hidden] { display: none; }
```

When the inspector is hidden, set the workspace column template through `:has(.inspector[hidden])` so the viewport takes its space. This is a native browser feature in the supported Chromium E2E runtime; no JavaScript measurement is added.

- [ ] **Step 4: Add responsive and embed rules**

At 1200 px, make the inspector an absolute right drawer and default the evidence dock to a shorter row. At 800 px, reduce the rail to a compact horizontal launcher above the viewport. Preserve the existing embed rules so only the canvas/viewport is visible.

- [ ] **Step 5: Run the CSS test and verify GREEN**

Run: `cd viewer && node --test test/workflow-rendering.test.js`

Expected: PASS.

- [ ] **Step 6: Commit Task 3**

```text
git add -- viewer/src/styles.css viewer/test/workflow-rendering.test.js
git commit -m style-viewer-review-cockpit
```

---

### Task 4: Browser workflow and regression proof

**Files:**
- Modify: `viewer/scripts/e2e-smoke.mjs`
- Test: existing viewer unit and browser suites

**Interfaces:**
- Consumes: cockpit DOM and state from Tasks 1-3.
- Produces: browser proof for review default, task navigation, persistent 3D, contextual inspector, evidence selection, responsive drawer, legacy mode, and embed mode.

- [ ] **Step 1: Update the public review smoke expectations**

Replace top-level tab assertions with cockpit assertions. Keep the existing 216-object, 213-asset, 7-overlay, empty-diagnostic, and nonblank-WebGL checks.

```js
const reviewTask = page.getByRole("button", { name: "Review", exact: true });
await reviewTask.waitFor();
assert.equal(await reviewTask.getAttribute("aria-current"), "page");
assert.equal(await page.locator("[data-viewer-workspace]").isVisible(), true);
assert.equal(await page.locator("[data-cockpit-status]").isVisible(), true);
assert.equal(await page.locator("[data-inspector]").isHidden(), true);
```

After clicking a governing row's Show in 3D button, assert the existing object ID is selected, load/result state is preserved, the canvas remains visible, and the inspector opens.

- [ ] **Step 2: Add the narrow breakpoint assertion**

Set the page viewport to 1024 x 768, select an object, and assert the inspector overlaps as a drawer without reducing the canvas below 480 px width. Then restore 1440 x 900 for the remaining checks.

- [ ] **Step 3: Run focused browser smokes**

Run:

```text
cd viewer
npm.cmd run e2e -- review-workflow
npm.cmd run e2e -- public-code-aster-review
npm.cmd run e2e -- legacy-workflow
npm.cmd run e2e -- embedded-review
```

Expected: all four workflows report `ok`; public review still renders 213 objects with varied WebGL samples.

- [ ] **Step 4: Run full viewer verification**

Run:

```text
cd viewer
npm.cmd test
npm.cmd run build
npm.cmd run e2e -- layer-state
npm.cmd run e2e -- default-public-review
```

Expected: zero test failures, Vite build exit 0, layer-state and default-public-review `ok`.

- [ ] **Step 5: Check scope and commit Task 4**

Run `git diff --check` and `git status --short`. Confirm the unrelated notebook remains unstaged and no `.superpowers/` companion files are staged.

```text
git add -- viewer/scripts/e2e-smoke.mjs
git commit -m test-viewer-review-cockpit
```

---

## Final Verification

- [ ] Run `cd viewer && npm.cmd test`.
- [ ] Run `cd viewer && npm.cmd run build`.
- [ ] Run `cd viewer && npm.cmd run e2e -- public-code-aster-review`.
- [ ] Run `cd viewer && npm.cmd run e2e -- layer-state`.
- [ ] Run `git diff --check`.
- [ ] Confirm `notebooks/01_building_piping_systems.ipynb` remains untouched and unstaged.
- [ ] Request independent code review before claiming completion.
