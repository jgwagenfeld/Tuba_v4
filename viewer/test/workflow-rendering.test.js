import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";

import { WORKFLOW_TABS, createWorkflowState, workflowTabForKey } from "../src/workflowState.js";

const viewerRoot = new URL("..", import.meta.url);

async function readViewerFile(...parts) {
  return readFile(new URL(path.posix.join(...parts), viewerRoot), "utf8");
}

test("workflow rendering exposes the seven engineer review tabs", () => {
  assert.deepEqual(
    WORKFLOW_TABS.map((tab) => tab.label),
    ["Review", "Model", "Load Cases", "Results", "Issues", "Display", "Compliance"]
  );
});

test("workflow rendering keyboard navigation wraps and supports Home and End", () => {
  const state = createWorkflowState({ review: { tables: {} } });

  assert.equal(workflowTabForKey(state, "summary", "ArrowLeft"), "diagnostics");
  assert.equal(workflowTabForKey(state, "diagnostics", "ArrowRight"), "summary");
  assert.equal(workflowTabForKey(state, "results", "Home"), "summary");
  assert.equal(workflowTabForKey(state, "results", "End"), "diagnostics");
  assert.equal(workflowTabForKey(state, "results", "Enter"), null);
});

test("workflow rendering styles real task buttons, horizontal tables, and visible focus", async () => {
  const css = await readViewerFile("src/styles.css");

  assert.match(css, /\[data-workflow-tabs\]\s*\{/s);
  assert.match(css, /\.review-table-scroll\s*\{[^}]*overflow-x:\s*auto/s);
  assert.match(css, /\.task-button\[aria-current="page"\]/);
  assert.doesNotMatch(css, /\.workflow-tab\b/);
  assert.match(css, /:focus-visible\s*\{[^}]*outline:\s*3px solid var\(--focus-on-light\)/s);
  assert.match(css, /\[data-workflow-tabs\]\s+:focus-visible,[\s\S]*outline-color:\s*var\(--focus-on-dark\)/s);
  assert.match(css, /\.visually-hidden\s*\{[^}]*position:\s*absolute[^}]*clip:/s);
  assert.match(css, /\[data-diagnostic-list\]\[hidden\]\s*\{[^}]*display:\s*none/s);
  assert.match(css, /@media\s*\(prefers-reduced-motion:\s*reduce\)/);
});

test("workflow rendering uses the responsive cockpit grid and preserves embed mode", async () => {
  const css = await readViewerFile("src/styles.css");

  assert.match(css, /\.app-shell\s*\{[^}]*grid-template-rows:\s*auto auto minmax\(0, 1fr\)/s);
  assert.match(css, /\.app-header\s*\{[^}]*grid-template-columns:\s*minmax\(12rem, 1fr\) minmax\(16rem, auto\) auto auto/s);
  assert.match(css, /\.cockpit-status\s*\{[^}]*display:\s*grid[^}]*grid-template-columns:\s*repeat\(5, minmax\(0, 1fr\)\)/s);
  assert.match(css, /\.viewer-workspace\s*\{[^}]*grid-template-areas:[^;]*"rail viewport inspector"[^;]*"rail evidence inspector"/s);
  assert.match(css, /@media\s*\(max-width:\s*1200px\)[\s\S]*\.inspector[\s\S]*position:\s*absolute/);
  assert.match(css, /@media\s*\(max-width:\s*1200px\)[\s\S]*\.evidence-dock:not\(\.expanded\)[^}]*max-height:\s*3\.25rem/s);
  assert.match(css, /@media\s*\(max-width:\s*1200px\)[\s\S]*\.evidence-dock\.expanded\s*\{[^}]*position:\s*absolute[^}]*height:\s*min\(60vh, 32rem\)/s);
  assert.match(css, /@media\s*\(max-width:\s*800px\)[\s\S]*\.cockpit-rail\s*\{[^}]*display:\s*flex[^}]*height:\s*auto[^}]*max-height:\s*8rem[^}]*overflow-x:\s*auto[^}]*overflow-y:\s*hidden/s);
  assert.match(css, /@media\s*\(max-width:\s*800px\)[\s\S]*\.cockpit-status\s*\{[^}]*grid-template-columns:\s*repeat\(5, minmax\(8rem, 1fr\)\)[^}]*overflow-x:\s*auto/s);
  assert.match(css, /\[data-embed="true"\][\s\S]*grid-template-areas:\s*"viewport"/);
  assert.match(css, /body\[data-embed="true"\]\s+\.viewer-workspace,\s*body\[data-embed="true"\]\s+\.viewer-workspace:has\(\.inspector\[hidden\]\)\s*\{[^}]*grid-template-columns:\s*minmax\(0, 1fr\)[^}]*grid-template-rows:\s*minmax\(0, 1fr\)[^}]*grid-template-areas:\s*"viewport"/s);
});

test("workflow rendering uses explicit labeled status, verdict, and severity badges", async () => {
  const app = await readViewerFile("src/app.js");
  const css = await readViewerFile("src/styles.css");

  assert.match(app, /className\s*=\s*"task-button"/);
  assert.match(app, /className\s*=\s*"status-badge"/);
  assert.match(app, /className\s*=\s*"verdict"/);
  assert.match(app, /className\s*=\s*"severity-badge"/);
  assert.match(css, /\.status-badge\[data-status="solved"\]/);
  assert.match(css, /\.verdict\[data-pass="true"\]/);
  assert.match(css, /\.severity-badge\[data-severity="error"\]/);
});

test("workflow rendering keeps the viewport persistent and separates tasks from evidence tabs", async () => {
  const app = await readViewerFile("src/app.js");

  assert.match(app, /function renderTaskRail\(\)/);
  assert.match(app, /setAttribute\("aria-current", id === currentState\.activeTab \? "page" : "false"\)/);
  assert.match(app, /function renderEvidenceTabs\(\)/);
  assert.match(app, /\["summary", "Governing Results"\]/);
  assert.match(app, /\["diagnostics", "Warnings"\]/);
  assert.match(app, /\["compliance", "Compliance"\]/);
  assert.match(app, /\["reports", "Reports"\]/);
  assert.match(app, /let activeEvidenceTab\s*=\s*"summary"/);
  assert.match(app, /activeEvidenceTab\s*=\s*evidenceTabForReload\(currentState, activeEvidenceTab\)/);
  assert.match(app, /button\.setAttribute\("aria-selected", String\(id === activeEvidenceTab\)\)/);
  assert.match(app, /button\.tabIndex = id === activeEvidenceTab \? 0 : -1/);
  assert.match(app, /evidenceTabForKey\(currentState, id, event\.key\)/);
  assert.match(app, /activateEvidence\(nextId\)[\s\S]*data-evidence-tab="\$\{nextId\}"[\s\S]*\.focus\(\)/);
  assert.match(app, /const activeTab = activeEvidenceTab/);
  assert.doesNotMatch(app, /dom\.viewerWorkspace\.hidden\s*=/);
});

test("workflow rendering adds cockpit status, report links, saved views, and reverse selection highlighting", async () => {
  const app = await readViewerFile("src/app.js");
  const css = await readViewerFile("src/styles.css");

  assert.match(app, /cockpitStatusViewModel\(currentState\.review\)/);
  assert.match(app, /dom\.reportLink\.href\s*=\s*`\$\{currentBundleUrl\}\/index\.html`/);
  assert.match(app, /dom\.reportLink\.hidden\s*=\s*!currentState\.review/);
  assert.match(app, /dataset\.evidenceReportLink/);
  assert.match(app, /setAttribute\("aria-expanded", String\(evidenceExpanded\)\)/);
  assert.match(app, /status\.governingLocation/);
  assert.match(app, /saveViewState\(currentState, name\)/);
  assert.match(app, /restoreViewState\(currentState, view\)/);
  assert.match(app, /tableRow\.dataset\.selected\s*=\s*"true"/);
  assert.match(app, /dom\.inspector\.hidden\s*=\s*sections\.length === 0 && !issueSummary/);

  assert.match(css, /\.report-link\s*\{[^}]*color:\s*var\(--accent\)/s);
  assert.match(css, /\.report-link:focus-visible\s*\{[^}]*outline-color:\s*var\(--focus-on-dark\)/s);
});

test("workflow rendering consolidates diagnostics, provenance, issues, and load diagnostics with trace fields", async () => {
  const app = await readViewerFile("src/app.js");

  assert.match(app, /renderDiagnosticGroup/);
  assert.match(app, /review\?\.provenance/);
  assert.match(app, /currentState\.issues/);
  for (const field of ["source", "code", "target"]) {
    assert.match(app, new RegExp(`diagnostic\\.${field}`));
  }
  assert.match(app, /if \(activeTab === "diagnostics"\)[\s\S]*return;/);
});

test("workflow rendering parses embed once and pins reloads to the display workflow", async () => {
  const app = await readViewerFile("src/app.js");
  const css = await readViewerFile("src/styles.css");

  assert.equal((app.match(/new URLSearchParams/g) ?? []).length, 1);
  assert.match(app, /const startupConfig\s*=/);
  assert.match(app, /activeTab:\s*"3d"/);
  assert.match(css, /\[data-embed="true"\]\s+\.app-header[\s\S]*display:\s*none/);
  assert.match(css, /\[data-embed="true"\]\s+\.cockpit-rail[\s\S]*display:\s*none/);
});

test("app renders a pinned display strip with category switches and applies presets", async () => {
  const app = await readViewerFile("src/app.js");
  assert.match(app, /data-display-strip|data-category-switches/);
  assert.match(app, /renderDisplayStrip/);
  assert.match(app, /applyTaskVisibilityPreset/);
  // Rail no longer groups tasks under Review/Explore/Display headings:
  assert.doesNotMatch(app, /\["Explore", \[/);
});

test("display strip is pinned at the bottom of a scrolling cockpit rail", async () => {
  const css = await readViewerFile("src/styles.css");
  // Rail is a flex column so the strip can pin below a scrolling task panel.
  assert.match(css, /\.cockpit-rail\s*\{[^}]*display:\s*flex[^}]*flex-direction:\s*column/s);
  assert.match(css, /\.cockpit-rail\s+\.task-panel\s*\{[^}]*overflow-y:\s*auto/s);
  // Strip does not shrink away, so it stays visible even when the panel is tall.
  assert.match(css, /\.display-strip\s*\{[^}]*flex-shrink:\s*0/s);
});

test("workflow rendering core palette meets WCAG AA text contrast", async () => {
  const css = await readViewerFile("src/styles.css");
  const tokens = Object.fromEntries(
    [...css.matchAll(/--([a-z-]+):\s*(#[0-9a-f]{6})\s*;/gi)].map((match) => [match[1], match[2]])
  );

  for (const [foreground, background, minimum] of [
    ["text", "paper", 4.5],
    ["muted", "paper", 4.5],
    ["chrome-text", "graphite", 4.5],
    ["accent", "graphite", 3],
    ["focus-on-light", "paper", 3],
    ["focus-on-dark", "graphite-raised", 3],
    ["focus-on-dark", "sidebar-control", 3],
    ["danger", "danger-surface", 4.5],
    ["success", "success-surface", 4.5]
  ]) {
    assert.ok(tokens[foreground], `missing --${foreground}`);
    assert.ok(tokens[background], `missing --${background}`);
    const ratio = contrastRatio(tokens[foreground], tokens[background]);
    assert.ok(ratio >= minimum, `${foreground} on ${background} contrast ${ratio.toFixed(2)} must be >= ${minimum}`);
  }
});

function contrastRatio(foreground, background) {
  const lighter = Math.max(relativeLuminance(foreground), relativeLuminance(background));
  const darker = Math.min(relativeLuminance(foreground), relativeLuminance(background));
  return (lighter + 0.05) / (darker + 0.05);
}

function relativeLuminance(hex) {
  const channels = hex.match(/[0-9a-f]{2}/gi).map((channel) => Number.parseInt(channel, 16) / 255);
  const [red, green, blue] = channels.map((channel) =>
    channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4
  );
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
}
