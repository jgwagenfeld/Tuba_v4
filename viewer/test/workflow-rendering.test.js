import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";

const viewerRoot = new URL("..", import.meta.url);

async function readViewerFile(...parts) {
  return readFile(new URL(path.posix.join(...parts), viewerRoot), "utf8");
}

test("workflow rendering styles horizontal tables and visible focus", async () => {
  const css = await readViewerFile("src/styles.css");

  // No tab strip any more: the rail is one scrollable column of sections.
  assert.doesNotMatch(css, /\[data-workflow-tabs\]/);
  assert.doesNotMatch(css, /\.task-button\b/);
  assert.match(css, /:focus-visible\s*\{[^}]*outline:\s*3px solid var\(--focus-on-dark\)/s);
  assert.match(css, /\.viewport\s+:focus-visible\s*\{[^}]*outline-color:\s*var\(--focus-on-light\)/s);
  assert.match(css, /\.visually-hidden\s*\{[^}]*position:\s*absolute[^}]*clip:/s);
  assert.match(css, /\[data-diagnostic-list\]\[hidden\]\s*\{[^}]*display:\s*none/s);
  assert.match(css, /@media\s*\(prefers-reduced-motion:\s*reduce\)/);
});

test("workflow rendering uses a scene-first responsive shell and preserves embed mode", async () => {
  const css = await readViewerFile("src/styles.css");

  // header / workspace. The status band and the coloring bar are gone: the
  // header chip carries the verdict and the Results task owns field choice.
  assert.match(css, /\.app-shell\s*\{[^}]*grid-template-rows:\s*auto minmax\(0, 1fr\)/s);
  assert.match(css, /\.app-header\s*\{[^}]*display:\s*flex/s);
  assert.match(css, /\.status-chip\s*\{[^}]*display:\s*flex/s);
  assert.doesNotMatch(css, /\.cockpit-status|\.coloring-bar/);
  assert.match(css, /\.viewer-workspace\s*\{[^}]*grid-template-areas:[^;]*"viewport inspector"/s);
  assert.match(css, /\.cockpit-rail\s*\{[^}]*position:\s*absolute[^}]*width:\s*var\(--controls-width\)/s);
  assert.match(css, /\.cockpit-rail\[hidden\]\s*\{[^}]*display:\s*none/s);
  assert.match(css, /@media\s*\(max-width:\s*1200px\)[\s\S]*\.inspector[\s\S]*position:\s*absolute/);
  assert.doesNotMatch(css, /grid-template-areas:[^;]*"rail viewport"/s);
  assert.match(css, /\[data-embed="true"\][\s\S]*grid-template-areas:\s*"viewport"/);
  assert.match(css, /body\[data-embed="true"\]\s+\.viewer-workspace,\s*body\[data-embed="true"\]\s+\.viewer-workspace:has\(\.inspector\[hidden\]\)\s*\{[^}]*grid-template-columns:\s*minmax\(0, 1fr\)[^}]*grid-template-rows:\s*minmax\(0, 1fr\)[^}]*grid-template-areas:\s*"viewport"/s);
});

test("build mode lists the live model's issues in the code pane, not the rail", async () => {
  const app = await readViewerFile("src/app.js");
  const html = await readViewerFile("index.html");
  const css = await readViewerFile("src/styles.css");

  // The rail stays a review surface: it remains hidden in the Build workspace,
  // whether a studio edits model.py or a published bundle shows it frozen.
  // That rule is workflowState's now - workflow-state.test.js exercises it
  // directly - so what this file checks is that the renderer asks rather than
  // recomputing it from the mode globals, the rail flag and the embed flag.
  assert.match(app, /dom\.taskRail\.hidden = !view\.railVisible;/);
  assert.match(app, /dom\.railToggle\.hidden = !view\.railToggleVisible;/);
  assert.match(app, /dom\.codePane\.hidden = !view\.scriptVisible;/);
  assert.doesNotMatch(app, /function buildWorkspaceMode\(\)/, "the ad-hoc mode derivation is gone");
  // Entering Build is one transition. The studio path used to dispatch
  // activateTask("model") while the published path dispatched enterBuild, so
  // the same move took two actions and only the published one was tested.
  const setMode = app.slice(app.indexOf("async function setMode("), app.indexOf("async function showStudioBundle("));
  assert.equal(
    (setMode.match(/type: "setStage"/g) ?? []).length, 1,
    "one stage transition serves the studio and the published bundle alike"
  );
  assert.doesNotMatch(setMode, /activateTask", tabId: "model"/, "entering Build does not claim a task");
  assert.doesNotMatch(app, /studio\.mode|sourceView\.mode/, "the stage is not duplicated into the session");
  // Build issues surface in the code pane instead, one row per issue with the
  // same camera-focusing click as the rail list.
  assert.match(html, /<div class="build-issues" data-build-issues hidden><\/div>/);
  assert.match(app, /function renderBuildIssues\(\)/);
  assert.match(app, /dom\.buildIssues\.hidden = issues\.length === 0/);
  assert.match(app, /dispatch\(\{ type: "focusIssue", issueId: issue\.id \}\);/);
  assert.match(css, /\.build-issues\[hidden\]\s*\{[^}]*display:\s*none/s);
  assert.match(css, /\.build-issues button\.selected/);
});

test("workflow rendering uses explicit labeled status, verdict, and severity badges", async () => {
  const app = await readViewerFile("src/app.js");
  const css = await readViewerFile("src/styles.css");

  assert.match(app, /className\s*=\s*"status-badge"/);
  assert.match(app, /className\s*=\s*"severity-badge"/);
  assert.match(css, /\.status-badge\[data-status="solved"\]/);
  assert.match(css, /\.severity-badge\[data-severity="error"\]/);
});

test("workflow rendering adds cockpit status, report links, saved views, and reverse selection highlighting", async () => {
  const app = await readViewerFile("src/app.js");
  const css = await readViewerFile("src/styles.css");

  assert.match(app, /cockpitStatusViewModel\(currentState\.review\)/);
  assert.match(app, /dom\.statusChip\.dataset\.statusTarget/);
  assert.match(app, /dom\.reportLink\.href\s*=\s*`\$\{currentBundleUrl\}\/index\.html`/);
  assert.match(app, /dom\.reportLink\.hidden\s*=\s*!currentState\.review/);
  assert.match(app, /saveViewState\(currentState, name\)/);
  assert.match(app, /dom\.inspector\.hidden\s*=\s*!summary && !issueSummary/);

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
});

test("the drawer tally names both counters, and one source for the warnings", async () => {
  const app = await readViewerFile("src/app.js");
  const tally = app.slice(
    app.indexOf("function reviewTallyLabel()"),
    app.indexOf("function renderDiagnostics()")
  );

  // Review diagnostics and scene issues are different things. Naming only the
  // latter made a warning-free review of a clashing model announce "0 issues"
  // beside a status chip that said "2 warnings".
  assert.match(tally, /cockpitStatusViewModel\(currentState\.review\)\.warningCount/);
  assert.match(tally, /currentState\.issues/);
  assert.match(tally, /warning/);
  assert.match(tally, /issue/);
  // Whatever is empty stays out of the way rather than reading as a finding.
  assert.match(tally, /parts\.join/);
  assert.match(tally, /"0 issues"/);
});

test("empty diagnostic groups are not drawn, so the disclosure can hide", async () => {
  const app = await readViewerFile("src/app.js");
  const group = app.slice(
    app.indexOf("function renderDiagnosticGroup("),
    app.indexOf("function appendTraceField(")
  );
  const render = app.slice(
    app.indexOf("function renderDiagnostics()"),
    app.indexOf("function isLoadOrPreviewDiagnostic(")
  );

  // The old shape appended a <section> per group even when it was empty, so
  // `childElementCount === 0` could never fire and the disclosure always
  // opened on five headings and five "None reported." lines - which reads as
  // five problems rather than as none. Asserted on the literal, not the
  // comment above this paragraph, which describes the same thing.
  assert.match(group, /if \(diagnostics\.length === 0\) return;/);
  assert.doesNotMatch(group, /textContent = "None reported\."/);

  // And the <details> around the list hides with it: an empty disclosure is
  // not a quiet absence, it is an invitation to click and find nothing.
  assert.match(render, /const nothingToShow = dom\.diagnosticList\.childElementCount === 0/);
  assert.match(render, /disclosure\.hidden = nothingToShow/);
});

test("workflow rendering parses embed once and pins reloads to the display workflow", async () => {
  const app = await readViewerFile("src/app.js");
  const css = await readViewerFile("src/styles.css");

  assert.equal((app.match(/new URLSearchParams/g) ?? []).length, 1);
  assert.match(app, /const startupConfig\s*=/);
  // The embed destination is a stage, not a tab: carrying it no longer needs a
  // task id no rail could ever offer.
  assert.match(app, /stage:\s*"embed"/);
  assert.doesNotMatch(app, /EMBED_TASK_ID/);
  assert.match(css, /\[data-embed="true"\]\s+\.app-header[\s\S]*display:\s*none/);
  assert.match(css, /\[data-embed="true"\]\s+\.cockpit-rail[\s\S]*display:\s*none/);
});

test("app renders a pinned display strip of bodies the reader owns", async () => {
  const app = await readViewerFile("src/app.js");
  assert.match(app, /data-display-strip|data-body-list/);
  assert.match(app, /renderDisplayStrip/);
  assert.match(app, /renderBodyList/);
  // Rail no longer groups tasks under Review/Explore/Display headings:
  assert.doesNotMatch(app, /\["Explore", \[/);
});

test("the colouring channel is one pinned control, not a per-task panel", async () => {
  const app = await readViewerFile("src/app.js");
  // One control writes both channels, and it lives in the pinned strip, so the
  // channel is chosen independently of the lens that is open.
  const colorBy = app.slice(
    app.indexOf("function renderColorBy()"),
    app.indexOf("function modelLegendChips(")
  );
  assert.ok(colorBy.length > 0);
  assert.match(colorBy, /setModelColorBy/);
  assert.match(colorBy, /setColoringField/);
  assert.match(colorBy, /getFieldOptions\(currentState\)/);
  // A legacy scene has no field catalogue, so a stand-in option keeps the
  // Results channel reachable instead of leaving the selector stuck on Model.
  assert.match(colorBy, /LEGACY_RESULTS_OPTION/);
  assert.match(colorBy, /setColorChannel/);
  // The result panel keeps only what hangs off the field, never the field.
  const resultControls = app.slice(
    app.indexOf("function renderResultControls()"),
    app.indexOf("function thresholdControl()")
  );
  assert.ok(resultControls.length > 0);
  assert.doesNotMatch(resultControls, /setColoringField/);
  assert.match(resultControls, /setColoringComponent/);
  assert.match(resultControls, /setActiveLoadCase/);
  assert.match(resultControls, /deformationControl\(\)/);
  assert.doesNotMatch(app, /function renderModelControls\(\)/);
  assert.doesNotMatch(app, /function renderColoringBar\(\)/);
  assert.doesNotMatch(app, /data-coloring-bar/);
});

test("the viewport key is asked for, and camera controls share the gizmo's corner", async () => {
  const app = await readViewerFile("src/app.js");
  const css = await readViewerFile("src/styles.css");

  // Always-on, the key floated a seven-row panel over the scene and grew into
  // the camera column. It is reference material, so it opens on request.
  assert.match(app, /dom\.bodyLegend\.hidden = !hasKey \|\| !bodyLegendOpen/);
  assert.match(app, /dom\.bodyLegendToggle\.setAttribute\("aria-expanded", String\(bodyLegendOpen\)\)/);
  assert.match(css, /\.legend-toggle\s*\{[^}]*position:\s*absolute[^}]*top:/s);

  // Two corners for one job: the button column sat top-right while the
  // orientation gizmo the renderer draws sat bottom-right.
  assert.match(css, /\.camera-controls\s*\{[^}]*bottom:\s*0\.6rem/s);
  assert.doesNotMatch(css, /body\[data-rail-open="true"\] \.body-legend/);
});

test("the compliance caveat renders in the viewport, where the colour map is", async () => {
  const app = await readViewerFile("src/app.js");
  const css = await readViewerFile("src/styles.css");
  const legend = app.slice(app.indexOf("function renderViewportLegend()"), app.indexOf("const BODY_LEGEND_NOTE"));
  assert.match(legend, /renderComplianceNotice\(\)/);
  // The panel that used to carry it detaches under Review/Model/Issues while
  // the scene stays colour-mapped, so the badge follows the colours.
  assert.match(css, /\.viewport-legend\s*\{[^}]*position:\s*absolute|\.viewport-legend,\s*\.body-legend\s*\{[^}]*position:\s*absolute/s);
});

test("display units convert at the boundary and never in stored state", async () => {
  const units = await readViewerFile("src/units.js");
  const app = await readViewerFile("src/app.js");

  // A threshold read in one unit and compared in another silently filters out
  // everything, so the input has to round-trip through toStored.
  const threshold = app.slice(app.indexOf("function thresholdControl()"), app.indexOf("function renderHeader()"));
  assert.match(threshold, /toDisplay\(/);
  assert.match(threshold, /toStored\(/);

  // Nothing may reach into the reducers with a converted value.
  assert.doesNotMatch(units, /setResultThreshold|getColoringValues|overlays/);
  // Unrecognised units pass through rather than being rescaled on a guess.
  assert.match(units, /const UNIT_QUANTITY = Object\.freeze\(\{/);
});

test("the legend ramp is sampled from the function that tints the scene", async () => {
  const app = await readViewerFile("src/app.js");
  // A hand-written gradient is a second source of truth for the colour map and
  // will drift from the pixels it claims to explain.
  assert.match(app, /function scalarRampGradient\(legend\)[\s\S]*colorForScalarValue\(/);
});

test("the rail is one scrollable column of sections, not swapped panels", async () => {
  const css = await readViewerFile("src/styles.css");
  // Rail is a flex column: lookup tools on top, the sections below.
  assert.match(css, /\.cockpit-rail\s*\{[^}]*display:\s*flex[^}]*flex-direction:\s*column/s);
  // No task panel and no tab strip: nothing swaps, so nothing needs hiding to
  // make room, and the Deformed toggle never vanishes while its scale control
  // is on screen.
  assert.doesNotMatch(css, /\.task-panel/);
  const app = await readViewerFile("src/app.js");
  assert.doesNotMatch(app, /function renderTaskRail|function renderTaskPanel|function activateTask/);
  assert.doesNotMatch(app, /dom\.layersBlock\.hidden/);
  // Two bands, not one list: bodies have extent and carry an opacity, overlays
  // are marks on the model and carry a scale.
  const markup = await readViewerFile("index.html");
  assert.match(markup, /data-layers-block[\s\S]*data-body-list[\s\S]*data-overlays-block[\s\S]*data-overlay-list/);
  assert.match(app, /function renderOverlayList\(\)[\s\S]*getOverlays\(currentState\)/);
  // The layer tree is the last row of that same list, not a popover pinned to
  // the rail foot. Reaching supports or reaction forces used to mean opening
  // the popover, opening All layers, then finding the right category.
  assert.match(markup, /data-overlay-list[\s\S]*class="strip-drawer layer-tree"[\s\S]*data-layer-list/);
  assert.doesNotMatch(markup, /rail-popover[\s\S]*data-layer-list/);
  assert.doesNotMatch(app, /\["layers", "All layers"\]/);
  // Issues are a companion, not a destination: the list follows the layers in
  // the same column, so a clash row and a result field are read together.
  assert.match(markup, /data-layers-block[\s\S]*data-issue-list/);
  assert.doesNotMatch(markup, /data-task-panel|data-workflow-tabs|data-result-tools-home/);
  // The strip takes the remaining height. A fixed cap here showed a third of
  // the bodies list through a 395px window.
  assert.match(css, /^\.display-strip\s*\{[^}]*flex:\s*1 1 auto[^}]*min-height:\s*0/ms);
  // The wide layout must not cap it. The narrow layout still does, deliberately,
  // because there the rail is a horizontal strip above the viewport.
  assert.doesNotMatch(css, /^\.display-strip\s*\{[^}]*max-height/ms);
});

test("the status chip carries exceptions only, and routes into the rail", async () => {
  const app = await readViewerFile("src/app.js");
  const chip = app.slice(app.indexOf("function renderStatusChip()"), app.indexOf("function renderResultControls("));
  // A clean review is not news; a warning is.
  assert.match(chip, /status\.warningCount > 0/);
  assert.doesNotMatch(chip, /governingLoadCase|governingRatio/);

  // The chip moves stage through setMode rather than assigning a driver's mode
  // by hand, and brings the rail section it is talking about into view - there
  // is no tab list to claim a lens in any more.
  assert.match(chip, /void setMode\("review"\)/);
  assert.match(chip, /scrollIntoView/);
  assert.doesNotMatch(chip, /activateTask/);
  assert.doesNotMatch(app, /activateEvidence|evidenceExpanded/);
});

test("workflow rendering core palette meets WCAG AA text contrast", async () => {
  const css = await readViewerFile("src/styles.css");
  const tokens = Object.fromEntries(
    [...css.matchAll(/--([a-z0-9-]+):\s*(#[0-9a-f]{6})\s*;/gi)].map((match) => [match[1], match[2]])
  );

  for (const [foreground, background, minimum] of [
    // --paper-raised is the app's real light ground: the buttons, inputs and
    // viewport chips that sit on the renderer's light canvas. --paper was the
    // nominal one and was never used by a single rule.
    ["text", "paper-raised", 4.5],
    ["muted", "paper-raised", 4.5],
    ["chrome-text", "graphite", 4.5],
    ["accent", "graphite", 3],
    ["focus-on-light", "paper-raised", 3],
    ["focus-on-dark", "graphite-raised", 3],
    ["focus-on-dark", "sidebar-control", 3],
    ["danger", "danger-surface", 4.5],
    ["success", "success-surface", 4.5],
    // The rail's own text roles, and the danger that reads on it. --danger is a
    // light-theme value and measured 2.26:1 where the contact table used it.
    // -1 is the body-prose grey the landing gallery and the header meta share;
    // it was an untokenised literal in both and a digit apart between them.
    ["chrome-text-1", "graphite-raised", 4.5],
    ["chrome-text-1", "graphite", 4.5],
    ["chrome-text-2", "graphite-raised", 4.5],
    ["chrome-text-3", "graphite-raised", 4.5],
    ["danger-on-dark", "graphite-raised", 4.5]
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

test("controls rebuilt on every render carry a stable focus key", async () => {
  const app = await readViewerFile("src/app.js");
  // render() replaceChildren()s almost every panel, which destroys the focused
  // element; these keys are how it is put back.
  assert.match(app, /function captureFocus\(\)/);
  assert.match(app, /function restoreFocus\(focus\)/);
  for (const key of [
    "body:", "opacity:", "scope:", "object:", "bar:", "camera:",
    // Every control that re-renders on click. Without a key, keyboard-toggling
    // one drops focus to <body> and the next Tab restarts from the top of the
    // document - which is what made the layer tree and the property actions
    // unusable without a mouse.
    "layer:", "hotspot:", "issue:", "legend:", "action:", "saved-view:",
    "issue-filter", "issue-status", "issue-comment", "issue-restore", "deform-animate"
  ]) {
    // Either form is fine: a row that builds its own key assigns it, a row
    // that shares a builder (issueRow) passes it as an argument. Matched on the
    // opening delimiter only - these keys are prefixes of longer keys
    // ("action:" of "action:copy"), so a closing quote would miss them all.
    const assigned = app.includes(`focusKey = \`${key}`) || app.includes(`focusKey = "${key}`);
    const passed = app.includes(`focusKey: \`${key}`) || app.includes(`focusKey: "${key}`);
    assert.ok(assigned || passed, `no focus key for ${key}`);
  }
});

test("the status live region is only written when it changes", async () => {
  const app = await readViewerFile("src/app.js");
  // role="status" announces on every write, and renderCanvas calls setStatus
  // ("Ready") on every render, so the write has to be conditional.
  assert.match(app, /function setStatus\(message, severity = false\)[\s\S]{0,900}?if \(dom\.status\.textContent === message/);
});

test("a render warning is not dressed as an error", async () => {
  const app = await readViewerFile("src/app.js");
  const css = await readViewerFile("src/styles.css");

  // Severity was a boolean, so render diagnostics - which stop nothing - had to
  // pass `true` and came out in the error treatment: a red chip that was the
  // loudest element in the header, and permanent, because the auto-hide keys on
  // the literal text "Ready".
  assert.match(app, /render warning\(s\)`, "warn"\)/);
  assert.match(css, /\.runtime-status\[data-level="warn"\][\s\S]{0,120}?--warning-on-dark/);
  // `true` must keep meaning error: fifteen call sites still pass it.
  assert.match(app, /severity === true \? "error"/);
});

test("the viewport canvas has a keyboard path to the camera", async () => {
  const app = await readViewerFile("src/app.js");
  const html = await readViewerFile("index.html");
  // The canvas is focusable and announced as interactive, so it must do
  // something when a key is pressed.
  assert.match(html, /<canvas[^>]*tabindex="0"/);
  assert.match(app, /dom\.canvas\.addEventListener\("keydown"/);
  assert.match(app, /CANVAS_KEY_ACTIONS/);
  for (const key of ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home"]) {
    assert.ok(app.includes(`${key}:`), `no canvas binding for ${key}`);
  }
});

test("gallery panel never overrides the hidden attribute", async () => {
  const css = await readViewerFile("src/styles.css");

  // `.gallery { display: ... }` is an author rule and beats the UA
  // `[hidden] { display: none }`, which left an empty full-viewport panel on
  // top of every review. A <main> is block already; it needs no display rule.
  // Bounded by this rule's own closing brace. It used to slice to the next
  // selector it expected to find, so adding any .gallery-* rule with a display
  // between them failed this for the wrong reason; only the .gallery rule
  // itself can override [hidden].
  const start = css.indexOf("\n.gallery {");
  assert.notEqual(start, -1, "no .gallery rule found");
  const block = css.slice(start, css.indexOf("}", start) + 1);
  assert.doesNotMatch(block, /display\s*:/, "the .gallery rule must not set display");
});

test("no rule hides a surface through a class when the hidden attribute does it", async () => {
  const css = await readViewerFile("src/styles.css");

  // An author `display` beats the UA `[hidden]` rule. This file has fallen
  // into that trap three times - .gallery left a dead panel over every review,
  // .bundle-picker left an empty select, and .gallery-card-image once stacked
  // both pieces of card art - each time because an element that toggles
  // `hidden` also sat under a class setting display. The three explicit
  // [hidden] overrides below are the fix; what is asserted here is that a
  // fourth such element does not arrive without one.
  assert.match(css, /\.gallery\s*\{[^}]*\}/);
  assert.match(css, /\.bundle-picker\[hidden\]\s*\{[^}]*display:\s*none/s);
  assert.match(css, /\.code-pane \.code-run\[hidden\]\s*\{[^}]*display:\s*none/s);
});

test("the file tabs show their own overflow", async () => {
  const css = await readViewerFile("src/styles.css");
  const start = css.indexOf("\n.code-tabs {");
  assert.notEqual(start, -1, "no .code-tabs rule found");
  const block = css.slice(start, css.indexOf("}", start) + 1);
  const stateStart = css.indexOf("\n.code-state {");
  const state = css.slice(stateStart, css.indexOf("}", stateStart) + 1);

  // model.py plus one tab per load case. A hidden scrollbar left the tabs past
  // the right edge with no indication they existed - a trackpad-only
  // affordance, and an invisible one for keyboard and screen-reader users.
  // Matched with the trailing semicolon so the comment above it, which names
  // the rule this replaced, is not read as the rule itself.
  assert.match(block, /overflow-x:\s*auto/);
  assert.doesNotMatch(block, /scrollbar-width:\s*none\s*;/);

  // And the tabs must actually get the room. They carried no flex declaration
  // while .code-state held the remainder, so one ellipsized status word kept
  // the space and the second tab was unreachable. basis 0 is what makes a
  // flexible scroll container: room is whatever the siblings leave.
  assert.match(block, /flex:\s*1 1 0/);
  assert.match(block, /min-width:\s*0/);
  assert.doesNotMatch(state, /flex:\s*1 1 auto/);

  // The one sibling that is allowed to give way rather than squeeze a tab. The
  // Ctrl+Enter hint inside Run is 62px - most of what still pushed the second
  // tab out of view after the flex fix - and it is worth exactly that when the
  // pane is wide. A container query rather than a media query: the pane is
  // user-resizable and its width is persisted, so only the strip knows whether
  // it is tight.
  assert.match(css, /container-type:\s*inline-size/);
  assert.match(css, /@container \(max-width: 38rem\)\s*\{[^}]*\.code-run kbd\s*\{[^}]*display:\s*none/s);
});

test("the status strip owns the session facts the header and the rail used to split", async () => {
  const app = await readViewerFile("src/app.js");
  const css = await readViewerFile("src/styles.css");

  // One render entry point for the whole line, so a segment cannot be drawn by
  // one path and left stale by another.
  assert.match(app, /function renderStatusStrip\(\)/);
  assert.match(app, /dom\.statusStrip\.hidden = currentState\.embed;/);
  const stripBody = app.slice(app.indexOf("function renderStatusStrip()"), app.indexOf("function renderSolverFact()"));
  for (const call of ["renderStatusChip()", "renderSolverFact()", "renderDiscretisationCheck()", "renderSelectionFact()"]) {
    assert.ok(stripBody.includes(call), `${call} must be drawn by the status strip`);
  }
  assert.match(app, /solverProvenanceLabel\(currentState\.review\)/);

  // The unit chip governs every readout in every mode, so it may not go back
  // into the rail foot, which Build mode hides.
  assert.match(app, /dom\.stripUnits\.replaceChildren\(/);
  assert.doesNotMatch(app, /dom\.railUtility\.append\(unitSystemChip\(\)\)/);

  assert.match(css, /\.app-shell\s*\{[^}]*grid-template-rows:\s*auto minmax\(0, 1fr\) auto/s);
  assert.match(css, /\.status-strip\s*\{[^}]*display:\s*flex/s);
  assert.match(css, /\[data-embed="true"\][^{]*\.status-strip[^{]*\{[^}]*display:\s*none/s);
  // The verdict and the mesh check are the last segments to give way, because
  // nothing else on screen carries them.
  assert.match(css, /@media \(max-width: 900px\)[\s\S]*?\[data-solver-fact\],\s*\.status-strip \.strip-selection\s*\{[^}]*display:\s*none/s);
});

test("a studio opens a solved project on its results, not on the script", async () => {
  const app = await readViewerFile("src/app.js");
  const init = app.slice(app.indexOf("async function initStudio("), app.indexOf("function sameHostPreviewSocketUrl("));

  // Build used to be the unconditional front door, so a project with a finished
  // review still opened on model.py - and Build hides the rail *and* its
  // toggle, so nothing on screen said the review was there at all.
  //
  // Which stage that is now belongs to workflowState, where it is a pure
  // function with its own tests instead of a branch reachable only by driving
  // a browser and forging the project request.
  assert.ok(init.includes("const stage = openingStage(studio);"), "the opening stage is asked for, not decided here");
  assert.ok(init.includes('dispatch({ type: "setStage", stage });'), "and is carried by the scene state");
  assert.doesNotMatch(init, /studio\.mode/, "the stage is not kept in a second place");
  assert.doesNotMatch(init, /hasReview && !studio\.reviewStale/, "nor re-derived inline");
  // The bundle has to follow the mode, or Results would draw the live model.
  assert.ok(init.includes("await showStudioBundle(stage);"), "the bundle follows the stage");
  // The rail's opening task comes from workflowState's default now, so the
  // studio no longer claims one here.
  assert.doesNotMatch(init, /activateTask/, "the studio does not claim a rail task");
});
