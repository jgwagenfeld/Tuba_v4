import {
  lineAtOffset,
  lineCount,
  lineStartOffset,
  replaceScriptLine,
  runLengthLiteral,
  scriptLine,
  withRunLength
} from "./codeLink.js";
import { relatedSelectionIds, selectionRepresentative } from "./reviewSelection.js";
import { deriveBundleSource } from "./bundleSource.js";
import { contactObjectId, renderContactReview } from "./contactReview.js";
import {
  buildObjectTree,
  getIssueSummary,
  groupIssues,
  saveViewState,
  sectionBoxDefaults,
  rankObjectMatches
} from "./controls.js";
import { bundleIdsOf, bundleKey, normalizeCatalog, renderGallery, shouldShowGallery } from "./gallery.js";
import {
  WEBGL2_UNAVAILABLE,
  applyHoverHighlight,
  createThreeCanvasRenderer,
  pickRenderedObject
} from "./renderer.js";
import {
  OPACITY_STEPS,
  VECTOR_SCALE_STEPS,
  cycleVectorScale,
  getBodies,
  getDiscretisationCheck,
  getOverlays,
  getSectionProfile,
  getSubpointLegend,
  getSubpointPeak,
  getSubpointStations,
  withDefaultBodyOpacity
} from "./bodies.js";

// One reducer action per vector family already exists; the chip picks the one
// its row belongs to rather than adding a fourth.
const VECTOR_SCALE_ACTIONS = Object.freeze({
  displacement: "setDisplacementVectorScale",
  moment: "setMomentVectorScale",
  reaction: "setReactionVectorScale"
});
import {
  componentIsSelectable,
  getActiveComponent,
  getActiveField,
  getComplianceNotice,
  getFieldOptions,
  shouldShowComplianceNotice
} from "./coloring.js";
import { MODEL_COLOR_MODES, getModelColoring } from "./modelColoring.js";
import {
  colorForScalarValue,
  getActiveLoadCaseDefinition,
  getGeometryStateOptions,
  getHotspots,
  getLoadCaseOptions,
  getResultStateOptions,
  getScalarLegend,
  isContactReview,
  getVisualDeformationDisplayScale
} from "./resultReview.js";
import {
  UNIT_SYSTEMS,
  displayUnit,
  formatElapsed,
  formatQuantity,
  formatValue,
  getUnitSystem,
  isConvertible,
  nextUnitSystem,
  toDisplay,
  toStored
} from "./units.js";
import { cockpitStatusViewModel, solverProvenanceLabel } from "./reviewTables.js";
import { categorizeLayers, createViewerState, loadSceneBundleFromUrl, resolveBundleId } from "./sceneLoader.js";
import { getPropertySections } from "./selection.js";
import { getSelectionSummary } from "./selectionSummary.js";
import { preserveViewerStateForReload, reduceViewerState } from "./viewerState.js";
import {
  colorChannelOf,
  createWorkflowState,
  openingStage,
  workspaceView
} from "./workflowState.js";

const dom = {
  appShell: document.querySelector("[data-embed]"),
  appHeader: document.querySelector("[data-app-header]"),
  status: document.querySelector("[data-runtime-status]"),
  sceneTitle: document.querySelector("[data-scene-title]"),
  sceneMeta: document.querySelector("[data-scene-meta]"),
  reportLink: document.querySelector("[data-report-link]"),
  statusChip: document.querySelector("[data-status-chip]"),
  statusStrip: document.querySelector("[data-status-strip]"),
  solverFact: document.querySelector("[data-solver-fact]"),
  selectionFact: document.querySelector("[data-selection-fact]"),
  stripUnits: document.querySelector("[data-strip-units]"),
  taskRail: document.querySelector("[data-task-rail]"),
  inspector: document.querySelector("[data-inspector]"),
  reviewDrawer: document.querySelector("[data-review-drawer]"),
  reviewTally: document.querySelector("[data-review-tally]"),
  contactTable: document.querySelector("[data-contact-table]"),
  contactDisplay: document.querySelector("[data-contact-display]"),
  reactionTable: document.querySelector("[data-reaction-table]"),
  objectsSection: document.querySelector("[data-objects-section]"),
  findTally: document.querySelector("[data-find-tally]"),
  findScope: document.querySelector("[data-find-scope]"),
  findDismiss: document.querySelector("[data-find-dismiss]"),
  railUtility: document.querySelector("[data-rail-utility]"),
  railPopover: document.querySelector("[data-rail-popover]"),
  displayStrip: document.querySelector("[data-display-strip]"),
  sectionBoxControls: document.querySelector("[data-section-box-controls]"),
  bodyList: document.querySelector("[data-body-list]"),
  projectionNote: document.querySelector("[data-projection-note]"),
  sectionProfile: document.querySelector("[data-section-profile]"),
  discretisationCheck: document.querySelector("[data-discretisation-check]"),
  viewportLegend: document.querySelector("[data-viewport-legend]"),
  bodyLegend: document.querySelector("[data-body-legend]"),
  bodyLegendToggle: document.querySelector("[data-body-legend-toggle]"),
  layerList: document.querySelector("[data-layer-list]"),
  layerTally: document.querySelector("[data-layer-tally]"),
  colorBy: document.querySelector("[data-color-by]"),
  colorLegend: document.querySelector("[data-color-legend]"),
  resultControls: document.querySelector("[data-result-controls]"),
  resultLegend: document.querySelector("[data-result-legend]"),
  resultShape: document.querySelector("[data-result-shape]"),
  overlaysBlock: document.querySelector("[data-overlays-block]"),
  overlayList: document.querySelector("[data-overlay-list]"),
  hotspotList: document.querySelector("[data-hotspot-list]"),
  diagnosticList: document.querySelector("[data-diagnostic-list]"),
  searchInput: document.querySelector("[data-search]"),

  issueList: document.querySelector("[data-issue-list]"),
  buildIssues: document.querySelector("[data-build-issues]"),
  objectList: document.querySelector("[data-object-list]"),
  savedViews: document.querySelector("[data-saved-views]"),
  properties: document.querySelector("[data-properties]"),
  propertyActions: document.querySelector("[data-property-actions]"),
  railToggle: document.querySelector("[data-rail-toggle]"),
  resetView: document.querySelector("[data-reset-view]"),
  cameraControls: document.querySelector("[data-camera-controls]"),
  canvas: document.querySelector("[data-canvas]"),
  workspace: document.querySelector("[data-viewer-workspace]"),
  viewport: document.querySelector(".viewport"),
  gallery: document.querySelector("[data-gallery]"),
  galleryLink: document.querySelector("[data-gallery-link]"),
  bundlePicker: document.querySelector("[data-bundle-picker]"),
  modeSwitch: document.querySelector("[data-mode-switch]"),
  codePane: document.querySelector("[data-code-pane]"),
  codeTabs: document.querySelector("[data-code-tabs]"),
  commText: document.querySelector("[data-comm-text]"),
  codeState: document.querySelector("[data-code-state]"),
  codeMeshToggle: document.querySelector("[data-code-mesh-toggle]"),
  codeRun: document.querySelector("[data-code-run]"),
  codeGutter: document.querySelector("[data-code-gutter]"),
  codeText: document.querySelector("[data-code-text]"),
  codeSelectionMark: document.querySelector('[data-code-mark="selection"]'),
  codeErrorMark: document.querySelector('[data-code-mark="error"]'),
  codeProblem: document.querySelector("[data-code-problem]"),
  codeFoot: document.querySelector("[data-code-foot]"),
  codeResize: document.querySelector("[data-code-resize]"),
  codeCallMark: document.querySelector('[data-code-mark="call"]'),
  codeRevealMark: document.querySelector('[data-code-mark="reveal"]'),
  solveButton: document.querySelector("[data-solve]"),
  reviewEmpty: document.querySelector("[data-review-empty]"),
  reviewEmptyText: document.querySelector("[data-review-empty-text]"),
  reviewEmptySolve: document.querySelector("[data-review-empty-solve]")
};

const startupParams = new URLSearchParams(window.location.search);
const startupConfig = Object.freeze({
  requestedBundle: startupParams.get("bundle"),
  embed: startupParams.get("embed") === "1",
  previewWebSocketUrl: startupParams.get("preview_ws")
});

let currentBundle = null;
let currentBundleUrl = ".";
let currentState = null;

function dispatch(action) {
  currentState = reduceViewerState(currentState, action);
  if (action.type === "selectObject") selectedObjectId = selectionRepresentative(currentState, action.objectId);
  if (action.type === "selectObjects") selectedObjectId = currentState.selectedObjectIds[0] ?? null;
  return currentState;
}

let selectedObjectId = null;
let currentSearch = "";
let issueFilters = { operatingOnly: false };
let railExpanded = true;
const savedViews = [];
// ponytail: linear ray picking at most 30 times/s; add a BVH if profiling warrants it.
let lastHoverPickTime = 0;
const ORBIT_CLICK_DRAG_THRESHOLD_PX = 4;
let viewportRenderer = null;
let viewportUnavailable = false;
let lastRenderGraph = null;
let hoveredObjectId = null;
let hoverFrameId = null;
let pendingHoverPoint = null;
let orbiting = false;
let pointerDownPoint = null;
let suppressNextCanvasClick = false;
const bootId = globalThis.__tubaViewerBootId ?? `boot:${Date.now()}:${Math.random().toString(16).slice(2)}`;
globalThis.__tubaViewerBootId = bootId;

// Build mode exists only when a studio server can run model.py. A static
// bundle - Pages, a report folder - is review-only and never shows it.
const studio = {
  available: false,
  // The script as last run. Line numbers in scene metadata refer to this text.
  ranCode: "",
  running: false,
  error: null,
  selectionLine: null,
  callLine: null,
  revealedObjectId: null,
  // The line a script link last revealed, marked until the selection or model.py changes.
  revealLine: null,
  // Whether the inspector was last drawn with the script's lines moved since the run.
  linesMoved: false,
  tabLeavesEditor: false,
  // The project studio (model.py + study.py) serves a review bundle beside the
  // live model, and can solve. Its /api/project answer; null outside a studio.
  project: null,
  hasReview: false,
  reviewStale: false,
  solving: false,
  // When the current solve or review import began, for the elapsed clock.
  solveStartedAt: null,
  // The studio is importing attested evidence at startup: a review is on its way.
  preparing: false,
  // Build's open file: null is model.py, otherwise the load case whose .comm is shown.
  codeTab: null,
  commRequest: 0
};

// A published bundle ships the model script that built it and the .comm each
// load case produced. The viewer shows them in the same Build workspace a
// studio edits; with no server here the pane is frozen read-only and the
// Results side is the review.
const sourceView = {
  available: false,
  baseUrl: ".",
  scriptUri: null,
  // [{ name: load case, uri: comm path }], in the study's order.
  loadCases: [],
  // Fetched files, keyed by bundle-relative URI, so switching tabs is free.
  text: new Map()
};

async function main() {
  const catalog = await loadBundleCatalog();
  document.body.dataset.embed = String(startupConfig.embed);
  dom.appShell.dataset.embed = String(startupConfig.embed);

  // The gallery is a navigation surface, not a view of a scene. Returning here
  // means the Three.js viewport is never constructed on the landing path.
  if (dom.gallery && shouldShowGallery({ ...startupConfig, catalog })) {
    document.body.dataset.view = "gallery";
    dom.gallery.hidden = false;
    renderGallery(dom.gallery, catalog);
    setStatus("Ready");
    return;
  }

  const bundleIds = bundleIdsOf(catalog);
  currentBundleUrl = resolveBundleId(startupConfig.requestedBundle, bundleIds);
  // A project studio opened without ?bundle= starts on its live model.
  if ((await loadStudioProject(catalog)) && !startupConfig.requestedBundle) {
    currentBundleUrl = "build";
  }
  document.body.dataset.view = "review";
  if (dom.galleryLink) {
    dom.galleryLink.hidden = bundleIds.length <= 1 || startupConfig.embed;
  }
  try {
    setStatus(`Loading ${currentBundleUrl}`);
    await loadBundle(currentBundleUrl, { preserve: false });
    setStatus("Ready");
    render();
    initBundlePicker(catalog);
    await initStudio(catalog);
    const previewSocketUrl = startupConfig.previewWebSocketUrl ?? (studio.available ? sameHostPreviewSocketUrl() : null);
    if (previewSocketUrl) {
      connectLivePreview(previewSocketUrl);
    }
  } catch (error) {
    setStatus(error.message, true);
  }
}

// The catalog owns gallery navigation. A standalone bundle does not need one.
async function loadBundleCatalog() {
  try {
    const response = await fetch("./bundles.json");
    if (response.ok) {
      const bundles = await response.json();
      return Array.isArray(bundles) ? bundles : [];
    }
  } catch {
    // A standalone bundle does not need a gallery catalog.
  }
  return [];
}

// Moving between reviews is one control. The gallery introduces the set and is
// the right landing page; once inside, a round trip through it to compare two
// models is friction, so the header keeps a direct switch.
function initBundlePicker(catalog) {
  if (startupConfig.embed || !dom.bundlePicker) {
    return;
  }
  const entries = normalizeCatalog(catalog);
  if (entries.length <= 1) {
    dom.bundlePicker.hidden = true;
    return;
  }
  const activeKey = bundleKey(currentBundleUrl);
  const options = entries.map((entry) => {
    const option = document.createElement("option");
    option.value = entry.id;
    option.textContent = entry.title;
    option.selected = bundleKey(entry.id) === activeKey;
    return option;
  });
  // A scene the catalog does not list - a fixture, a preview - still has to be
  // the one the control names, or the switcher reports the wrong model.
  if (activeKey && !options.some((option) => option.selected)) {
    const active = document.createElement("option");
    active.value = currentBundleUrl;
    active.textContent = activeKey;
    active.selected = true;
    options.unshift(active);
  }
  dom.bundlePicker.replaceChildren(...options);
  dom.bundlePicker.hidden = false;
  dom.bundlePicker.addEventListener("change", () => switchBundle(dom.bundlePicker.value));
}

async function switchBundle(bundleId) {
  currentBundleUrl = bundleId;
  const url = new URL(window.location.href);
  url.searchParams.set("bundle", bundleId);
  window.history.replaceState({}, "", url);
  setStatus(`Loading ${bundleId}`);
  try {
    await loadBundle(bundleId, { preserve: false });
    setStatus("Ready");
    render();
  } catch (error) {
    setStatus(error.message, true);
  }
}


async function loadBundle(bundleUrl, options = {}) {
  currentBundle = await loadSceneBundleFromUrl(bundleUrl);
  // A static bundle can show its origin script; a studio owns the live one, so
  // it must not be overwritten by whatever the bundle happens to carry.
  if (studio.project) {
    clearBundleSource();
  } else {
    await loadBundleSource(bundleUrl);
  }
  const viewerState = withDefaultBodyOpacity(createViewerState(currentBundle));
  const workflowState = createWorkflowState({
    review: viewerState.review,
    embed: startupConfig.embed
  });
  const nextState = { ...viewerState, ...workflowState };
  const loadedState = options.preserve && currentState ? preserveViewerStateForReload(currentState, nextState) : nextState;
  currentState = startupConfig.embed
    ? { ...loadedState, embed: true, stage: "embed" }
    : loadedState;
  // Load takes the scene as the bundle declared it. Arrival used to have to
  // resist a task preset deliberately; there is no task any more, so this is the
  // rule everywhere: changing stage or section changes the lens, never the
  // layers. The hazard is why - a review-less bundle used to land on a tab whose
  // preset hid analysis_mesh and results, so a composited
  // geometry/mesh/sub-point/deformed view opened with three of its four bodies
  // switched off.
}

function render() {
  // Almost every panel is rebuilt with replaceChildren(), which destroys the
  // focused element. Without this, keyboard-toggling a body checkbox or a scope
  // chip dropped focus to <body> and the next Tab restarted from the top of the
  // document.
  const focus = captureFocus();
  renderMode();
  renderHeader();
  renderStatusStrip();
  renderRailChrome();
  renderDisplayStrip();
  renderViewportLegend();
  renderResultControls();
  renderDiagnostics();
  renderIssues();
  renderBuildIssues();
  renderProperties();
  renderScriptSelection();
  renderCanvas();
  restoreFocus(focus);
}

// Controls rebuilt on every render carry a stable data-focus-key so the element
// that replaces them can be found again.
function captureFocus() {
  const active = document.activeElement;
  const key = active?.dataset?.focusKey;
  if (!key) {
    return null;
  }
  return {
    key,
    start: typeof active.selectionStart === "number" ? active.selectionStart : null,
    end: typeof active.selectionEnd === "number" ? active.selectionEnd : null
  };
}

function restoreFocus(focus) {
  if (!focus) {
    return;
  }
  // Something else claimed focus during the render - leave it alone.
  if (document.activeElement && document.activeElement !== document.body) {
    return;
  }
  // Focus keys are plain ASCII, so the fallback needs no escaping of its own.
  const escape = globalThis.CSS?.escape ?? ((value) => value);
  const next = document.querySelector(`[data-focus-key="${escape(focus.key)}"]`);
  if (!next) {
    return;
  }
  next.focus({ preventScroll: true });
  if (focus.start !== null && typeof next.setSelectionRange === "function") {
    try {
      next.setSelectionRange(focus.start, focus.end);
    } catch {
      // Some input types reject selection ranges; focus alone is the point.
    }
  }
}

// The rail's own chrome: whether it and its toggle are shown, and the header
// with them. There is no tab strip any more - the rail is one scrollable column
// whose sections do not swap, so nothing here claims a "current" lens.
function renderRailChrome() {
  const view = currentWorkspace();
  dom.taskRail.hidden = !view.railVisible;
  dom.reviewDrawer.hidden = isBuildMode() || currentState.embed;
  dom.railToggle.hidden = !view.railToggleVisible;
  dom.railToggle.setAttribute("aria-expanded", String(railExpanded));
  dom.railToggle.textContent = railExpanded ? "\u2039" : "\u203a";
  dom.railToggle.title = railExpanded ? "Hide controls" : "Show controls";
  dom.railToggle.setAttribute("aria-label", dom.railToggle.title);
  document.body.dataset.railOpen = String(railExpanded);
  dom.appHeader.hidden = !view.headerVisible;
}

function renderSavedViews() {
  dom.savedViews.replaceChildren();
  const saveButton = document.createElement("button");
  saveButton.type = "button";
  saveButton.textContent = "Save Current View";
  saveButton.addEventListener("click", () => {
    const name = `View ${savedViews.length + 1}`;
    savedViews.push(saveViewState(currentState, name));
    render();
  });
  dom.savedViews.append(saveButton);
  for (const view of savedViews) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = view.name;
    button.addEventListener("click", () => {
      dispatch({ type: "restoreViewState", view });
      selectedObjectId = currentState.selectedObjectIds[0] ?? null;
      render();
    });
    dom.savedViews.append(button);
  }
}


// The one permanent line. Everything on it describes the session rather than a
// panel, which is why none of it belongs to the rail: the rail is hidden in
// Build mode and gone entirely in a narrow window, and the unit chip governing
// every readout on screen went with it.
function renderStatusStrip() {
  dom.statusStrip.hidden = currentState.embed;
  renderStatusChip();
  renderSolverFact();
  renderDiscretisationCheck();
  renderSelectionFact();
  dom.stripUnits.replaceChildren(...(currentState.embed ? [] : [unitSystemChip()]));
}

function renderSolverFact() {
  const label = solverProvenanceLabel(currentState.review);
  dom.solverFact.hidden = !label;
  dom.solverFact.textContent = label;
  dom.solverFact.title = label ? "Solver, runtime version and load cases behind this review" : "";
}

// What is selected, said once for the whole selection. The inspector describes
// the primary object only, and says nothing at all about the other five when a
// legend chip or a group header selects a set - so a multi-select was invisible
// outside the 3D view that drew it.
function renderSelectionFact() {
  const ids = currentState.selectedObjectIds ?? [];
  dom.selectionFact.hidden = ids.length === 0;
  if (ids.length === 0) return;
  const primaryId = selectedObjectId ?? ids[0];
  const primary = currentState.objects.find((obj) => obj.id === primaryId);
  const name = primary?.name || primaryId;
  dom.selectionFact.textContent = ids.length > 1 ? `${name} · ${ids.length} selected` : name;
  dom.selectionFact.title = `${ids.length} object${ids.length === 1 ? "" : "s"} selected`;
}

function renderStatusChip() {
  dom.statusChip.replaceChildren();
  if (studio.project && !currentState.embed) {
    renderProjectStatusChip();
    return;
  }
  dom.statusChip.hidden = currentState.embed || !currentState.review;
  if (dom.statusChip.hidden) return;
  const status = cockpitStatusViewModel(currentState.review);

  const verdict = document.createElement("span");
  verdict.className = "status-badge";
  verdict.dataset.status = String(status.analysisStatus);
  verdict.textContent = String(status.analysisStatus).replaceAll("_", " ");
  dom.statusChip.append(verdict);

  // Exceptions only: a clean review is not news, a warning is.
  const alerts = [
    status.warningCount > 0
      ? ["diagnostics", `${status.warningCount} warning${status.warningCount === 1 ? "" : "s"}`]
      : null
  ].filter(Boolean);
  for (const [, label] of alerts) {
    const alert = document.createElement("span");
    alert.className = "status-chip-alert";
    alert.textContent = label;
    dom.statusChip.append(alert);
  }

  const target = alerts.length > 0 ? "issues" : "colour";
  dom.statusChip.dataset.statusTarget = target;
  dom.statusChip.setAttribute(
    "aria-label",
    `Analysis ${status.analysisStatus}${alerts.length > 0 ? `, ${alerts.map(([, label]) => label).join(", ")}` : ""} - show the review rail`
  );
  dom.statusChip.onclick = () => {
    railExpanded = true;
    // setMode owns the stage move. This used to assign the studio's own mode
    // field directly, which for a published bundle sitting in Build set the
    // wrong driver and did nothing at all, while renderProjectStatusChip had
    // always gone through setMode.
    void setMode("review").then(() => {
      render();
      // The rail is one column now: bring the section the chip is talking about
      // into view rather than claiming a lens.
      const section = alerts.length > 0 ? dom.issueList : dom.colorBy;
      if (alerts.length > 0) dom.reviewDrawer.open = true;
      else dom.colorBy.closest("details").open = true;
      section?.scrollIntoView?.({ block: "start" });
    });
  };
}







// The colouring selector encodes the two channels as option values: a model
// mode carries MODEL_OPTION_PREFIX, a solver field is the field id verbatim
// (which already names its own namespace), and a legacy scene's results - a
// solver overlay with no catalogue entry to name - get the one stand-in value.
const MODEL_OPTION_PREFIX = "model:";
const LEGACY_RESULTS_OPTION = "results:legacy";

// One control for what colours the scene, and the legend for whichever channel
// owns it. The selector is pinned to the display strip rather than living in a
// task panel, so the channel is chosen independently of the lens you are in -
// the point of separating colouring from layer visibility.
function renderColorBy() {
  if (!dom.colorBy || !dom.colorLegend) return;
  dom.colorBy.replaceChildren();
  dom.colorLegend.replaceChildren();
  const channel = colorChannelOf(currentState);

  const modelOptions = MODEL_COLOR_MODES.map((mode) => ({
    id: `${MODEL_OPTION_PREFIX}${mode.id}`,
    label: mode.label,
    group: "Model"
  }));
  const fieldOptions = getFieldOptions(currentState).map((field) => ({
    id: field.id,
    label: field.label,
    group: "Results"
  }));
  // A legacy scene colours by a solver overlay with no field catalogue to name,
  // so the Results group would otherwise be empty while the channel is results.
  // One option stands in for it, labelled by the field actually tinting.
  if (fieldOptions.length === 0 && channel === "results") {
    fieldOptions.push({
      id: LEGACY_RESULTS_OPTION,
      label: getScalarLegend(currentState)?.field ?? "Results",
      group: "Results"
    });
  }
  const activeFieldId = getActiveField(currentState)?.id;
  const selected = channel === "results"
    ? (fieldOptions.some((option) => option.id === activeFieldId) ? activeFieldId : fieldOptions[0]?.id)
    : `model:${currentState.modelColorBy ?? "default"}`;
  dom.colorBy.append(colorBySelect([...modelOptions, ...fieldOptions], selected));

  if (channel === "results") {
    // The full legend is the ramp over the viewport; this is the name of what
    // is tinting the scene, stated where the choice is made.
    const legend = getScalarLegend(currentState);
    dom.colorLegend.append(metaLine(
      legend ? `${legend.field} - see the ramp in the viewport` : "No result field to colour by."
    ));
    return;
  }
  const mode = currentState.modelColorBy ?? "default";
  if (mode !== "default") {
    dom.colorLegend.append(modelLegendChips(mode));
  }
}

// A grouped selector: the two channels are optgroups, so a model property and a
// solver field sit in one list with one current value.
function colorBySelect(options, selected) {
  const wrapper = document.createElement("div");
  wrapper.className = "field-select";
  const select = document.createElement("select");
  select.setAttribute("aria-label", "Colour the scene by");
  focusKeyFor(select, "Colour by");
  for (const group of ["Model", "Results"]) {
    const members = options.filter((option) => option.group === group);
    if (members.length === 0) continue;
    const optgroup = document.createElement("optgroup");
    optgroup.label = group;
    for (const option of members) {
      const element = document.createElement("option");
      element.value = option.id;
      element.textContent = option.label;
      element.selected = option.id === selected;
      optgroup.append(element);
    }
    select.append(optgroup);
  }
  select.addEventListener("change", () => {
    const value = select.value;
    if (value.startsWith(MODEL_OPTION_PREFIX)) {
      dispatch({ type: "setModelColorBy", colorBy: value.slice(MODEL_OPTION_PREFIX.length) });
    } else if (value === LEGACY_RESULTS_OPTION) {
      // The legacy Results stand-in: no field to choose, just the channel.
      dispatch({ type: "setColorChannel", colorChannel: "results" });
    } else {
      dispatch({ type: "setColoringField", fieldId: value });
    }
    render();
  });
  wrapper.append(select);
  return wrapper;
}

// What the model colours mean, and a way to select every element carrying one.
function modelLegendChips(mode) {
  const coloring = getModelColoring(currentState, mode);
  if (coloring.items.length === 0) {
    return metaLine("No model elements found.");
  }
  const container = document.createElement("div");
  container.className = "model-legend-list";
  container.setAttribute("role", "list");
  container.setAttribute("aria-label", `Colouring legend by ${mode}`);

  for (const item of coloring.items) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "model-legend-chip";
    chip.setAttribute("role", "listitem");
    chip.title = `Click to select ${item.count} elements with ${mode} "${item.label}"`;

    const swatch = document.createElement("span");
    swatch.className = "model-legend-swatch";
    swatch.style.backgroundColor = item.color;

    const label = document.createElement("span");
    label.className = "model-legend-label";
    label.textContent = item.label;

    const tally = document.createElement("span");
    tally.className = "model-legend-tally";
    tally.textContent = String(item.count);

    chip.append(swatch, label, tally);
    chip.addEventListener("click", () => {
      dispatch({ type: "selectObjects", objectIds: item.objectIds });
      selectedObjectId = currentState.selectedObjectIds[0] ?? null;
      render();
    });
    container.append(chip);
  }
  return container;
}

function renderReactionTable() {
  dom.reactionTable.replaceChildren();
  const stateId = currentState.activeResultStateId;
  const rows = (currentState.review?.tables?.reactions?.rows ?? []).filter(row =>
    row.result_state_id === stateId && (!currentState.activeLoadCase || row.load_case === currentState.activeLoadCase));
  dom.reactionTable.parentElement.hidden = rows.length === 0;
  if (!rows.length) return;
  const table = document.createElement("table");
  const header = table.createTHead().insertRow();
  const columns = [["node_id", "Node"], ["support_ids", "Supports"],
    ["fx", "Fx", "N"], ["fy", "Fy", "N"], ["fz", "Fz", "N"],
    ["mx", "Mx", "N*m"], ["my", "My", "N*m"], ["mz", "Mz", "N*m"]];
  for (const [, label] of columns) {
    const cell = document.createElement("th"); cell.scope = "col"; cell.textContent = label; header.append(cell);
  }
  const body = table.createTBody();
  for (const row of rows) {
    const tr = body.insertRow();
    for (const [key, , unit] of columns) {
      const cell = tr.insertCell();
      if (key === "support_ids") {
        for (const id of row.support_ids ?? []) {
          const button = document.createElement("button");
          button.type = "button"; button.textContent = id;
          const objectId = contactObjectId(currentState, id);
          button.disabled = !objectId;
          button.dataset.focusKey = `reaction:${row.node_id}:${id}`;
          button.setAttribute("aria-pressed", String(currentState.selectedObjectIds.includes(objectId)));
          button.addEventListener("click", event => {
            dispatch({ type: "selectObject", objectId, additive: event.shiftKey }); render();
          });
          cell.append(button);
        }
      } else cell.textContent = unit ? formatQuantity(row[key], unit, getUnitSystem(currentState)) || "unavailable" : row[key];
    }
  }
  dom.reactionTable.append(table);
}

function renderResultControls() {
  dom.resultControls.replaceChildren();
  dom.resultLegend.replaceChildren();
  dom.resultShape.replaceChildren();
  dom.hotspotList.replaceChildren();

  for (const [part, host] of [["table", dom.contactTable], ["display", dom.contactDisplay]]) {
    host.replaceChildren();
    const panel = renderContactReview(currentState, dispatch, render, part);
    host.hidden = !panel;
    if (panel) host.append(panel);
  }
  renderReactionTable();
  const issueCount = (currentState.issues ?? []).length;
  dom.reviewTally.textContent = `${issueCount} issue${issueCount === 1 ? "" : "s"}`;
  const loadCases = getLoadCaseOptions(currentState);
  const resultStates = getResultStateOptions(currentState);
  const geometryStates = getGeometryStateOptions(currentState);
  const fieldOptions = getFieldOptions(currentState);
  if (
    loadCases.length === 0 &&
    resultStates.length === 0 &&
    geometryStates.length === 0 &&
    fieldOptions.length === 0
  ) {
    dom.resultControls.append(metaLine("No Code_Aster result overlays."));
    return;
  }

  // The field itself is chosen in the pinned "Colour by" control; what is left
  // here are the refinements that hang off it - the case and the component.
  const showComponent = fieldOptions.length > 0 && componentIsSelectable(currentState);
  if (loadCases.length > 0) {
    dom.resultControls.append(
      propertyRow(
        "Case",
        plainSelect(currentState.activeLoadCase ?? loadCases[0].id, loadCases, (value) => {
          dispatch({ type: "setActiveLoadCase", loadCase: value });
          render();
        })
      )
    );
  }
  if (showComponent) {
    const components = (getActiveField(currentState)?.components ?? ["magnitude"]).map((id) => ({ id, label: id }));
    dom.resultControls.append(
      propertyRow(
        "Component",
        plainSelect(getActiveComponent(currentState), components, (value) => {
          dispatch({ type: "setColoringComponent", component: value });
          render();
        })
      )
    );
  }
  // Case and converged step stay together, including contact histories.
  if (resultStates.length > 1 || (fieldOptions.length === 0 && resultStates.length > 0)) {
    dom.resultControls.append(
      propertyRow(
        "Step",
        plainSelect(currentState.activeResultStateId ?? resultStates[0].id, resultStates, (value) => {
          dispatch({ type: "setActiveResultState", resultStateId: value });
          render();
        })
      )
    );
  }

  // What the colour means. Its own element between the two bands: the legend is
  // read by name, and the compliance notice rides with it.
  const legend = getScalarLegend(currentState);
  if (legend) {
    const scale = document.createElement("div");
    const component = legend.component && legend.component !== "magnitude" ? ` ${legend.component}` : "";
    const system = getUnitSystem(currentState);
    const low = formatValue(legend.range.min, legend.unit, system);
    const high = formatQuantity(legend.range.max, legend.unit, system);
    scale.textContent = `${legend.field}${component}: ${low} - ${high}`.trim();
    dom.resultLegend.append(scale);
  }

  dom.resultShape.append(
    railGroup("Deformation", `\u00d7${formatScale(getVisualDeformationDisplayScale(currentState))}`)
  );
  // A contact review draws its own shape and offers no deformed state. A review
  // that merely lists its shoes keeps the control: the table is not the subject.
  if (!isContactReview(currentState) && geometryStates.length > 0) {
    dom.resultShape.append(
      propertyRow(
        "Deformed state",
        plainSelect(currentState.activeGeometryStateId ?? geometryStates[0].id, geometryStates, (value) => {
          stopDeformationAnimation();
          dispatch({ type: "setActiveGeometryState", geometryStateId: value });
          render();
        })
      )
    );
  }
  dom.resultShape.append(propertyRow("Deform", deformationControl()));
  dom.resultShape.append(filtersDrawer());

  const hotspots = getHotspots(currentState);
  dom.hotspotList.append(railGroup("Hotspots", hotspotTally(hotspots)));
  if (hotspots.length === 0) {
    const empty = document.createElement("div");
    empty.className = "meta";
    empty.textContent = "No hotspots above threshold.";
    dom.hotspotList.append(empty);
    return;
  }
  for (const hotspot of hotspots) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "hotspot-row";
    const identity = hotspot.elementId
      ? ` ${hotspot.elementId} row ${hotspot.rowIndex ?? "?"} subpoint ${hotspot.subpointIndex ?? "?"}`
      : "";
    const magnitude = formatQuantity(hotspot.value, hotspot.unit, getUnitSystem(currentState));
    // The dot is the colour the scene painted this value, off the same ramp, so
    // a row in the list and a spot on the model are recognisably the same thing.
    const dot = document.createElement("span");
    dot.className = "hotspot-dot";
    const color = colorForScalarValue(hotspot.value, legend);
    if (color !== null) dot.style.background = hexColor(color);
    const name = document.createElement("span");
    name.className = "hotspot-name";
    name.textContent = `${hotspot.objectName}${identity} `;
    const value = document.createElement("span");
    value.className = "hotspot-value";
    value.textContent = hotspot.utilization !== null ? `${magnitude} ` : magnitude;
    button.append(dot, name, value);
    if (hotspot.utilization !== null) {
      const utilization = document.createElement("span");
      utilization.className = "hotspot-util";
      utilization.textContent = `u=${formatScale(hotspot.utilization)}`;
      button.append(utilization);
    }
    button.addEventListener("click", () => {
      selectedObjectId = hotspot.objectId;
      dispatch({ type: "selectObject", objectId: hotspot.objectId });
      render();
    });
    dom.hotspotList.append(button);
  }
}

// The cut-off is stated on the heading as well as on the control, so folding the
// filters away never hides what the list is filtered by.
function hotspotTally(hotspots) {
  const stored = currentState.resultThreshold;
  if (!(Number(stored) > 0)) {
    return `${hotspots.length}`;
  }
  const unit = getScalarLegend(currentState)?.unit ?? "";
  return `${hotspots.length} above ${formatQuantity(stored, unit, getUnitSystem(currentState))}`;
}

// Thresholds and vector scales are set once and then in the way. Folded by
// default: the cut-off is restated in the summary and in the Hotspots heading,
// so nothing about what is being filtered depends on opening this.
let resultFiltersOpen = false;

function filtersDrawer() {
  const drawer = document.createElement("details");
  drawer.className = "strip-drawer";
  drawer.dataset.resultFilters = "";
  drawer.open = resultFiltersOpen;
  drawer.addEventListener("toggle", () => {
    resultFiltersOpen = drawer.open;
  });

  const summary = document.createElement("summary");
  summary.append("Filters & vectors");
  const state = document.createElement("span");
  state.className = "drawer-state";
  state.textContent = vectorScaleSummary();
  summary.append(state);

  drawer.append(
    summary,
    thresholdControl(),
    numericControl("Utilization threshold", currentState.utilizationThreshold ?? "", "0.05", (value) => {
      dispatch({ type: "setUtilizationThreshold", threshold: value });
      render();
    }),
    rangeControl(
      `Displacement vector scale ${formatScale(currentState.resultVectorScales?.displacement ?? 1)}x`,
      currentState.resultVectorScales?.displacement ?? 1,
      0,
      20,
      0.5,
      (value) => {
        dispatch({ type: "setDisplacementVectorScale", scale: value });
        render();
      },
      "Displacement vector scale"
    ),
    rangeControl(
      // Its own control on purpose: a moment is not a force, and one shared
      // scale let whichever family had the larger numbers hide the other.
      `Moment vector scale ${formatScale(currentState.resultVectorScales?.moment ?? 1)}x`,
      currentState.resultVectorScales?.moment ?? 1,
      0,
      5,
      0.25,
      (value) => {
        dispatch({ type: "setMomentVectorScale", scale: value });
        render();
      },
      "Moment vector scale"
    ),
    rangeControl(
      `Reaction vector scale ${formatScale(currentState.resultVectorScales?.reaction ?? 1)}x`,
      currentState.resultVectorScales?.reaction ?? 1,
      0,
      5,
      0.25,
      (value) => {
        dispatch({ type: "setReactionVectorScale", scale: value });
        render();
      },
      "Reaction vector scale"
    )
  );
  return drawer;
}

function vectorScaleSummary() {
  const scales = [
    currentState.resultVectorScales?.displacement ?? 1,
    currentState.resultVectorScales?.moment ?? 1,
    currentState.resultVectorScales?.reaction ?? 1
  ];
  return scales.map((scale) => formatScale(scale)).join(" / ");
}

// The threshold filters the field that is currently colouring the scene, so it
// is denominated in that field's unit - and typed in whatever the unit chip is
// showing. The value reaching state is always the stored one: a threshold read
// in MPa but compared against pascals would silently filter out everything.
function thresholdControl() {
  const unit = getScalarLegend(currentState)?.unit ?? "";
  const system = getUnitSystem(currentState);
  const suffix = isConvertible(unit) ? ` (${displayUnit(unit, system)})` : unit ? ` (${unit})` : "";
  const stored = currentState.resultThreshold;
  const shown = Number.isFinite(Number(stored)) && stored !== null ? toDisplay(stored, unit, system) : "";
  const step = toDisplay(STORED_THRESHOLD_STEP_PA, unit === "Pa" ? unit : "", system) || 1;
  return numericControl(
    `Stress threshold${suffix}`,
    shown,
    String(step),
    (value) => {
      const typed = String(value).trim();
      dispatch({ type: "setResultThreshold", threshold: typed === "" ? 0 : toStored(typed, unit, system) });
      render();
    },
    "Stress threshold"
  );
}

// One megapascal, the granularity an engineer nudges a stress cut-off by.
const STORED_THRESHOLD_STEP_PA = 1e6;

function renderHeader() {
  // A studio's live build bundle has no review to name it: show the model, not the scene id.
  dom.sceneTitle.textContent = currentState.review?.project_name
    ?? (studio.project ? String(currentState.sceneId ?? "").replace(/^scene:/, "") : currentState.sceneId);
  // Deliberately no units here. This printed the bundle's storage units
  // (m / N / Pa) while every readout on screen follows the unit chip, which
  // defaults to mm / MPa - so the header asserted Pa in the same eyeful as the
  // legend's MPa. The chip is the one place display units are stated.
  // A review without a design standard is the normal case now that code checks
  // are gone; printing the separator regardless left a dangling "· Revision 0".
  dom.sceneMeta.textContent = currentState.review
    ? [currentState.review.model_standard, `Revision ${currentState.review.model_revision}`]
        .filter(Boolean)
        .join(" · ")
    : `${currentState.objects.length} objects | ${currentState.issues.length} issues`;
  dom.reportLink.hidden = !currentState.review;
  if (currentState.review) {
    dom.reportLink.href = `${currentBundleUrl}/index.html`;
    // The report prints stored SI so it stays byte-comparable with the CSVs and
    // review.json beside it; this viewer converts for display. Said on the way
    // out as well as on arrival, because a reader who has already crossed has
    // no reason to re-read the paragraph that explains the difference.
    dom.reportLink.title =
      "Engineering review tables. Printed in stored SI units (m, Pa, N), not the display units used here.";
    dom.reportLink.setAttribute(
      "aria-label",
      "Report - engineering review tables, printed in stored SI units rather than the display units used here"
    );
  } else {
    dom.reportLink.removeAttribute("href");
  }
}

function renderDisplayStrip() {
  dom.displayStrip.hidden = currentState.embed;
  // What is drawn stays on screen: the rail is one column of sections now, so
  // nothing is swapped out to make room and the Deformed toggle cannot vanish
  // while its own scale control is on screen.
  renderColorBy();
  renderBodyList();
  renderOverlayList();
  renderProjectionNote();
  renderSectionProfile();
  renderFindPane();
  renderLayerTree(categorizeLayers(currentState.layers));
  renderSectionBoxControls();
  renderSavedViews();
  renderRailPopover();
}

// The bodies panel answers "what is drawn"; the coloring bar above the viewport
// answers "what does it mean". Keeping them apart is the ParaView split the
// layer-structure design record adopted, and it is why nothing here selects a
// field and nothing up there toggles a body.
function renderBodyList() {
  dom.bodyList.replaceChildren();
  const bodies = getBodies(currentState);
  if (bodies.length === 0) {
    dom.bodyList.append(metaLine("This scene draws no result bodies."));
    return;
  }
  for (const body of bodies) {
    dom.bodyList.append(bodyRow(body));
  }
}

function bodyRow(body) {
  const row = document.createElement("div");
  row.className = "body-row";
  row.dataset.body = body.id;
  row.dataset.bodyVisible = String(body.visible);

  const head = document.createElement("div");
  head.className = "body-head";

  const toggle = document.createElement("label");
  toggle.className = "body-toggle";
  const input = document.createElement("input");
  input.type = "checkbox";
  input.checked = body.visible;
  input.indeterminate = body.partiallyVisible;
  input.setAttribute("aria-label", body.label);
  input.dataset.focusKey = `body:${body.id}`;
  input.addEventListener("change", () => {
    dispatch({
      type: "setBodyVisibility",
      bodyId: body.id,
      visible: input.checked
    });
    render();
  });
  const name = document.createElement("span");
  name.className = "body-name";
  name.textContent = body.label;
  toggle.append(input, name);

  const badge = document.createElement("span");
  badge.className = `body-badge body-badge-${body.badge.tone}`;
  badge.textContent = body.badge.text;

  head.append(toggle, badge);
  if (body.supportsOpacity) {
    head.append(opacityChip(body));
  }

  // The sublines are what a layer is made of - element counts, wall thickness,
  // sub-point grids. Useful when you ask, noise when you do not: four layers
  // put eight lines of mono under four checkboxes, and nothing outranked
  // anything. The row says what it is; the caret says what it is made of.
  if (body.metrics.length > 0) {
    const metrics = document.createElement("div");
    metrics.className = "body-metrics";
    metrics.id = `body-metrics-${body.id}`;
    metrics.hidden = !expandedBodies.has(body.id);
    for (const metric of body.metrics) {
      const line = document.createElement("p");
      line.className = "body-metric";
      line.textContent = metric;
      metrics.append(line);
    }

    const caret = document.createElement("button");
    caret.type = "button";
    caret.className = "body-caret";
    caret.dataset.focusKey = `metrics:${body.id}`;
    caret.setAttribute("aria-expanded", String(!metrics.hidden));
    caret.setAttribute("aria-controls", metrics.id);
    caret.setAttribute("aria-label", `${body.label} details`);
    caret.textContent = metrics.hidden ? "▸" : "▾";
    caret.addEventListener("click", () => {
      if (expandedBodies.has(body.id)) expandedBodies.delete(body.id);
      else expandedBodies.add(body.id);
      render();
    });
    head.append(caret);
    row.append(head, metrics);
    return row;
  }

  row.append(head);
  return row;
}

// Overlays share the body-row grammar - same checkbox, same badge slot, same
// chip position - because they answer the same question. What differs is the
// chip: a mark on the model has a scale, not an opacity.
function renderOverlayList() {
  const overlays = getOverlays(currentState);
  dom.overlaysBlock.hidden = overlays.length === 0;
  dom.overlayList.replaceChildren();
  for (const overlay of overlays) {
    dom.overlayList.append(overlayRow(overlay));
  }
}

function overlayRow(overlay) {
  const row = document.createElement("div");
  row.className = "body-row";
  row.dataset.overlay = overlay.id;
  row.dataset.bodyVisible = String(overlay.visible);

  const head = document.createElement("div");
  head.className = "body-head";

  const toggle = document.createElement("label");
  toggle.className = "body-toggle";
  const input = document.createElement("input");
  input.type = "checkbox";
  input.checked = overlay.visible;
  input.indeterminate = overlay.partiallyVisible;
  input.setAttribute("aria-label", overlay.label);
  input.dataset.focusKey = `overlay:${overlay.id}`;
  input.addEventListener("change", () => {
    dispatch({
      type: "setOverlayVisibility",
      overlayId: overlay.id,
      visible: input.checked
    });
    render();
  });
  const name = document.createElement("span");
  name.className = "body-name";
  name.textContent = overlay.label;
  name.title = overlay.description;
  toggle.append(input, name);

  head.append(toggle);
  // Chrome rows (the grid) gate no layer, so there is no count to state and an
  // empty badge would read as zero.
  if (overlay.count !== null) {
    const badge = document.createElement("span");
    badge.className = "body-badge body-badge-neutral";
    badge.textContent = String(overlay.count);
    head.append(badge);
  }
  if (overlay.vectorType) {
    head.append(scaleChip(overlay));
  }
  row.append(head);
  return row;
}

// The scale a vector family is drawn at belongs on the row that draws it. It
// used to be a slider in the result controls, one band away from the checkbox
// that decided whether the vectors were on the screen at all.
function scaleChip(overlay) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "body-scale";
  button.dataset.overlayScale = overlay.id;
  button.dataset.focusKey = `scale:${overlay.id}`;
  button.textContent = `${formatScale(overlay.scale)}x`;
  button.setAttribute(
    "aria-label",
    `${overlay.label} scale ${formatScale(overlay.scale)}x, cycles through ${VECTOR_SCALE_STEPS.map((step) => `${formatScale(step)}x`).join(", ")}`
  );
  button.addEventListener("click", () => {
    dispatch({
      type: VECTOR_SCALE_ACTIONS[overlay.vectorType],
      scale: cycleVectorScale(overlay.scale)
    });
    render();
  });
  return button;
}

function opacityChip(body) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "body-opacity";
  button.dataset.bodyOpacity = body.id;
  button.dataset.focusKey = `opacity:${body.id}`;
  const percent = Math.round(body.opacity * 100);
  button.textContent = `${percent}%`;
  button.setAttribute(
    "aria-label",
    `${body.label} opacity ${percent}%, cycles through ${OPACITY_STEPS.map((step) => `${Math.round(step * 100)}%`).join(", ")}`
  );
  button.addEventListener("click", () => {
    dispatch({ type: "cycleBodyOpacity", bodyId: body.id });
    render();
  });
  return button;
}

// Why the sub-points land where they do. Shown only when the scene actually
// carries projected sub-points, because otherwise it explains nothing on screen.
function renderProjectionNote() {
  const overlay = getSectionProfile(currentState);
  dom.projectionNote.hidden = !overlay;
  if (!overlay) {
    dom.projectionNote.textContent = "";
    return;
  }
  dom.projectionNote.textContent =
    "Sub-points are measured; the surface between them is interpolated.";
}

// The sub-point grid on one element node, drawn to scale from NSEC/NCOU rather
// than sketched. Sectors run from the display generatrice; layers run from the
// bore outward.
function renderSectionProfile() {
  dom.sectionProfile.replaceChildren();
  const profile = getSectionProfile(currentState);
  dom.sectionProfile.hidden = !profile;
  if (!profile) return;

  // Named with its own field: the rosette explains the sub-point grid whatever
  // is tinting the scene, so it must not read as the active legend.
  // "Wall section", not "Section": the strip already has a Section box, and that
  // one clips the scene rather than describing the pipe wall.
  // A 104px rosette plus four fact lines, permanently open, for a question
  // asked once per session: what the sub-point grid looks like.
  const heading = document.createElement("button");
  heading.type = "button";
  heading.className = "strip-heading strip-toggle";
  heading.dataset.focusKey = "section:wall";
  heading.setAttribute("aria-expanded", String(wallSectionOpen));
  heading.textContent = `${wallSectionOpen ? "▾" : "▸"} Wall section · ${getSubpointLegend(currentState)?.field ?? "sub-points"}`;
  heading.addEventListener("click", () => {
    wallSectionOpen = !wallSectionOpen;
    render();
  });
  dom.sectionProfile.append(heading);
  if (!wallSectionOpen) return;
  const body = document.createElement("div");
  body.className = "section-profile-body";
  body.append(sectionRosette(profile));

  const facts = document.createElement("div");
  facts.className = "section-facts";
  facts.append(
    metaLine(`NSEC ${profile.nsec} × NCOU ${profile.ncou}`),
    metaLine(`${profile.sectors} sectors × ${profile.layers} layers = ${profile.subpoints_per_node} per node`)
  );
  const peak = getSubpointPeak(currentState);
  if (peak) {
    const unit = getSubpointLegend(currentState)?.unit ?? peak.unit ?? "";
    const magnitude = formatQuantity(peak.value, unit, getUnitSystem(currentState));
    const line = metaLine(`peak ${magnitude}${peak.location ? ` · ${peak.location}` : ""}`.trim());
    line.classList.add("section-peak");
    facts.append(line);
  }
  const generatrice = profile.display_generatrice;
  if (Array.isArray(generatrice)) {
    facts.append(metaLine(`sector 0 on (${generatrice.join(", ")})`));
  }
  body.append(facts);
  dom.sectionProfile.append(body);
}

// Large enough that all 2·NSEC circumferential stations across 2·NCOU+1 wall
// layers stay individually visible rather than smearing into a ring.
const ROSETTE_SIZE = 118;
const ROSETTE_STATION_RADIUS = 1.1;
const ROSETTE_MEASURED_RADIUS = 2.4;

function sectionRosette(profile) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", `0 0 ${ROSETTE_SIZE} ${ROSETTE_SIZE}`);
  svg.setAttribute("width", String(ROSETTE_SIZE));
  svg.setAttribute("height", String(ROSETTE_SIZE));
  svg.setAttribute("class", "section-rosette");
  svg.setAttribute("role", "img");
  svg.setAttribute(
    "aria-label",
    `Pipe section: ${profile.sectors} circumferential sub-point stations across ${profile.layers} wall layers`
  );

  const centre = ROSETTE_SIZE / 2;
  const outer = centre - 6;
  const inner = outer * 0.62;
  for (const radius of [inner, outer]) {
    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("cx", String(centre));
    circle.setAttribute("cy", String(centre));
    circle.setAttribute("r", String(radius));
    circle.setAttribute("class", "rosette-wall");
    svg.append(circle);
  }

  const legend = getSubpointLegend(currentState);
  const byStation = new Map();
  for (const station of getSubpointStations(currentState)) {
    const key = `${station.sectorIndex}:${station.layerIndex}`;
    const previous = byStation.get(key);
    if (!previous || station.value > previous.value) byStation.set(key, station);
  }

  const lastSector = Math.max(profile.sectors - 1, 1);
  const lastLayer = Math.max(profile.layers - 1, 1);
  for (let layer = 0; layer < profile.layers; layer += 1) {
    const radius = inner + ((outer - inner) * layer) / lastLayer;
    for (let sector = 0; sector < profile.sectors; sector += 1) {
      // The last sector repeats the first (the grid closes on itself), so it is
      // not drawn twice.
      if (sector === profile.sectors - 1) continue;
      const angle = (2 * Math.PI * sector) / lastSector;
      const measured = byStation.get(`${sector}:${layer}`);
      const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      dot.setAttribute("cx", (centre + radius * Math.sin(angle)).toFixed(2));
      dot.setAttribute("cy", (centre - radius * Math.cos(angle)).toFixed(2));
      // A reported station has to be findable among the couple of hundred empty
      // ones, so it is drawn larger as well as coloured.
      dot.setAttribute("r", String(measured ? ROSETTE_MEASURED_RADIUS : ROSETTE_STATION_RADIUS));
      dot.setAttribute("class", measured ? "rosette-point" : "rosette-station");
      const colour = measured ? colorForScalarValue(measured.value, legend) : null;
      if (colour !== null) {
        dot.setAttribute("fill", hexColor(colour));
      }
      svg.append(dot);
    }
  }
  return svg;
}

// A geometric fidelity check on the mesh, not a code check: how far the straight
// chord falls inside the true bend arc, against a stated fraction of the radius.
//
// It reads as one line in the status strip now rather than a headed block in
// the rail foot. It kept its pinning either way - the verdict is sign-off
// evidence and must not be scrollable past - but the rail foot only pinned it
// inside a panel that Build mode hides and a narrow window closes, and the
// heading spent two rail rows saying what "Mesh" says here.
function renderDiscretisationCheck() {
  dom.discretisationCheck.replaceChildren();
  const check = getDiscretisationCheck(currentState);
  dom.discretisationCheck.hidden = !check;
  if (!check) return;

  const label = document.createElement("span");
  label.className = "check-label";
  label.textContent = "Mesh";
  const value = document.createElement("span");
  value.className = "check-value";
  // The scene states the check in metres (check.unit); the chip decides how it
  // reads, and the tolerance is a ratio, so it never converts.
  value.textContent = `${check.min_elements_per_bend}/bend · chord ${formatQuantity(check.max_chord_deviation, check.unit, getUnitSystem(currentState))}`;
  const badge = document.createElement("span");
  badge.className = `check-badge ${check.within_tolerance ? "check-ok" : "check-warn"}`;
  // The criterion travels with the verdict: a bare "OK" invites the reader to
  // assume a code check happened.
  badge.textContent = `${check.within_tolerance ? "OK" : "COARSE"} ≤ ${formatPercent(check.tolerance_ratio)} R`;
  dom.discretisationCheck.append(label, value, badge);

  const worst = check.worst_bend;
  if (worst && check.bend_count > 1) {
    const note = document.createElement("span");
    note.className = "check-worst";
    note.textContent = `worst of ${check.bend_count}: ${worst.source_element_id}`;
    dom.discretisationCheck.append(note);
  }
}

// The coloring channel: one field, one component, one scale, plus the display
// deformation the deformed body is drawn at.
// One chip for the whole readout. Stored values never move; this only changes
// how they are stated, and every quantity on screen follows it together so the
// legend, the hotspots and the threshold can never disagree.
function unitSystemChip() {
  const active = UNIT_SYSTEMS.find((system) => system.id === getUnitSystem(currentState));
  const button = document.createElement("button");
  button.type = "button";
  button.className = "bar-button bar-units";
  button.dataset.unitSystem = active.id;
  button.dataset.focusKey = "unit-system";
  button.textContent = active.label;
  button.title = `${active.title} — click to switch`;
  button.setAttribute("aria-label", `Display units: ${active.title}`);
  button.addEventListener("click", () => {
    dispatch({
      type: "setUnitSystem",
      unitSystem: nextUnitSystem(currentState)
    });
    render();
  });
  return button;
}

function deformationControl() {
  const group = document.createElement("div");
  group.className = "deform-control";
  const scale = getVisualDeformationDisplayScale(currentState);
  const input = document.createElement("input");
  input.type = "range";
  input.min = "1";
  input.max = "100";
  input.step = "1";
  input.value = String(scale);
  input.setAttribute("aria-label", "Visual deformation scale (display only)");
  input.dataset.focusKey = "deform-scale";
  input.addEventListener("input", () => {
    stopDeformationAnimation();
    dispatch({ type: "setVisualDeformationScale", scale: input.value });
    readout.textContent = `×${formatScale(getVisualDeformationDisplayScale(currentState))}`;
    if (!viewportRenderer?.renderDeformation(currentState)) renderCanvas();
  });
  input.addEventListener("pointerdown", () => viewportRenderer?.setDeformationInteraction(true));
  input.addEventListener("change", () => {
    viewportRenderer?.setDeformationInteraction(false);
    render();
  });
  for (const eventName of ["pointerup", "pointercancel"]) {
    input.addEventListener(eventName, () => {
      if (viewportRenderer?.setDeformationInteraction(false)) render();
    });
  }
  const readout = document.createElement("span");
  readout.className = "bar-readout";
  readout.dataset.deformScale = "";
  readout.textContent = `×${formatScale(scale)}`;
  group.append(input, readout, animateButton());
  return group;
}

function animateButton() {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "bar-button";
  button.dataset.animateDeformation = "";
  const animating = deformationAnimation !== null;
  // Icon only: the word cost 60px of a 172px row and the slider needs it.
  button.replaceChildren(animating ? glyphIcon("pause") : glyphIcon("play"));
  button.setAttribute("aria-label", animating ? "Pause deformation animation" : "Animate deformation");
  button.setAttribute("aria-pressed", String(animating));
  // Nothing to animate when the scene carries no exaggerated shape: sweeping a
  // ×1 scale would just redraw the same picture at full cost.
  button.disabled = !animating && !hasExaggeratedDeformedState();
  button.addEventListener("click", toggleDeformationAnimation);
  return button;
}

function hasExaggeratedDeformedState() {
  return getGeometryStateOptions(currentState).some((option) => Number(option.visualScale) > 1);
}

// Legend and body key, pinned in the viewport rather than the results panel:
// the panel detaches under the Review/Model/Issues tasks while the scene stays
// colour-mapped, and a colour-mapped FE stress view whose "not code stress"
// caveat has scrolled away is the exact screenshot this prevents.
function renderViewportLegend() {
  dom.viewportLegend.replaceChildren();
  dom.bodyLegend.replaceChildren();
  const legend = getScalarLegend(currentState);
  dom.viewportLegend.hidden = !legend;
  if (legend) {
    const heading = document.createElement("div");
    heading.className = "legend-heading";
    const field = document.createElement("span");
    const component = legend.component && legend.component !== "magnitude" ? ` ${legend.component}` : "";
    field.textContent = `${legend.field}${component}`;
    const context = document.createElement("span");
    context.className = "legend-context";
    const system = getUnitSystem(currentState);
    context.textContent = [displayUnit(legend.unit, system), legend.loadCase].filter(Boolean).join(" · ");
    heading.append(field, context);

    const ramp = document.createElement("div");
    ramp.className = "legend-ramp";
    ramp.dataset.legendRamp = "";
    ramp.style.background = scalarRampGradient(legend);

    const ticks = document.createElement("div");
    ticks.className = "legend-ticks";
    const min = Number(legend.range?.min ?? 0);
    const max = Number(legend.range?.max ?? 0);
    // Ticks carry the number only; the heading states the unit once.
    for (const value of [min, (min + max) / 2, max]) {
      const tick = document.createElement("span");
      tick.textContent = formatValue(value, legend.unit, system);
      ticks.append(tick);
    }
    dom.viewportLegend.append(heading, ramp, ticks);
    renderComplianceNotice();
  }

  const bodies = getBodies(currentState).filter((body) => body.visible);
  const loadCase = getActiveLoadCaseDefinition(currentState);
  const visibleIds = new Set(currentState.visibleObjectIds ?? []);
  const visibleVectors = (currentState.objects ?? []).filter(
    (object) => visibleIds.has(object.id) && ["applied_load", "reaction_vector"].includes(object.kind)
  );
  const hasKey = bodies.length > 0 || Boolean(loadCase) || visibleVectors.length > 0;
  // Always-on, this key floated a seven-row panel over the scene and grew up
  // into the camera controls. It answers "what is that mark" once, so it is
  // asked for: the toggle stays, the panel opens on request.
  dom.bodyLegendToggle.hidden = currentState.embed || !hasKey;
  dom.bodyLegendToggle.setAttribute("aria-expanded", String(bodyLegendOpen));
  dom.bodyLegendToggle.title = bodyLegendOpen ? "Hide the viewport key" : "What the marks mean";
  dom.bodyLegendToggle.setAttribute("aria-label", dom.bodyLegendToggle.title);
  dom.bodyLegend.hidden = !hasKey || !bodyLegendOpen || currentState.embed;
  if (dom.bodyLegend.hidden) return;
  if (loadCase) {
    const system = getUnitSystem(currentState);
    const nodalCount = Number(loadCase.nodal_force_count ?? 0);
    appendViewportKeyRow(
      `${loadCase.load_case} inputs — ${loadCase.gravity ? "gravity on" : "gravity off"} · ` +
      `pressure ${formatQuantity(loadCase.internal_pressure_pa, "Pa", system)} · ` +
      `${formatQuantity(loadCase.temperature_c, "°C", system)} from ${formatQuantity(loadCase.ref_temperature_c, "°C", system)} · ` +
      `${nodalCount ? `${nodalCount} imposed nodal force${nodalCount === 1 ? "" : "s"}` : "no imposed nodal forces"}`
    );
  }
  const vectorKeys = new Map();
  for (const object of visibleVectors) {
    const resultType = object.metadata?.result_type;
    const vectorKind = object.metadata?.vector_kind;
    const key = object.kind === "applied_load" ? `applied_${vectorKind}` : resultType;
    const label = {
      applied_force: "Applied force — authored input",
      applied_moment: "Applied moment — authored input, right-hand rule",
      applied_line_load: "Applied line load — authored input",
      reaction_force: "Reaction force — Code_Aster result",
      reaction_moment: "Reaction moment — Code_Aster result, right-hand rule"
    }[key];
    if (!label || vectorKeys.has(key)) continue;
    const asset = currentState.geometryAssets.find((candidate) => candidate.id === object.geometry_asset_id);
    vectorKeys.set(key, { label, color: asset?.generation_config?.color });
  }
  for (const { label, color } of vectorKeys.values()) appendViewportKeyRow(label, color);
  for (const body of bodies) {
    appendViewportKeyRow(
      `${body.label} — ${BODY_LEGEND_NOTE[body.id] ?? body.badge.text}`,
      null,
      `body-legend-${body.id}`
    );
  }
}

function appendViewportKeyRow(label, color = null, swatchClass = "") {
  const row = document.createElement("div");
  row.className = "body-legend-row";
  if (color || swatchClass) {
    const swatch = document.createElement("span");
    swatch.className = `body-legend-swatch ${swatchClass}`.trim();
    if (color) swatch.style.background = color;
    row.append(swatch);
  }
  const text = document.createElement("span");
  text.textContent = label;
  row.append(text);
  dom.bodyLegend.append(row);
}

// What the mark in the viewport is actually reporting, which is not the same
// question as what the body is.
const BODY_LEGEND_NOTE = Object.freeze({
  geometry: "surface, interpolated",
  analysis_mesh: "cell values",
  subpoints: "measured",
  deformed: "display scale only"
});

// Sampled from the function that actually tints the scene, so the bar cannot
// drift from the colours on screen.
function scalarRampGradient(legend) {
  const min = Number(legend.range?.min ?? 0);
  const max = Number(legend.range?.max ?? 1);
  const stops = [];
  const steps = 12;
  for (let index = 0; index <= steps; index += 1) {
    const ratio = index / steps;
    const colour = colorForScalarValue(min + (max - min) * ratio, legend);
    if (colour === null) continue;
    stops.push(`${hexColor(colour)} ${(ratio * 100).toFixed(0)}%`);
  }
  return stops.length > 1 ? `linear-gradient(90deg, ${stops.join(", ")})` : "none";
}

// Called only from renderViewportLegend, and unconditional there on purpose:
// the caveat qualifies the legend it sits in, so the two must never appear
// apart. The older gate on results-layer visibility was for the days when the
// badge lived in the display strip and the legend did not.
function renderComplianceNotice() {
  const notice = getComplianceNotice(currentState);
  if (!notice) {
    return;
  }
  const badge = document.createElement("div");
  badge.className = "compliance-notice";
  badge.dataset.complianceNotice = "";
  badge.textContent = `⚠ ${notice}`;
  dom.viewportLegend.append(badge);
}

function renderSectionBoxControls() {
  dom.sectionBoxControls.replaceChildren();
  const section = document.createElement("section");
  section.className = "section-box-controls";
  const heading = document.createElement("h3");
  heading.textContent = "Section";
  const enabled = document.createElement("input");
  enabled.type = "checkbox";
  enabled.checked = Boolean(currentState.sectionBox);
  enabled.id = "section-enabled";
  const enabledLabel = document.createElement("label");
  enabledLabel.htmlFor = enabled.id;
  enabledLabel.append(enabled, " Enable section");
  const box = currentState.sectionBox ?? sectionBoxDefaults(currentState.bounds);
  const fields = [];
  const grid = document.createElement("div");
  grid.className = "section-box-grid";
  for (const [axis, index] of [["X", 0], ["Y", 1], ["Z", 2]]) {
    for (const side of ["min", "max"]) {
      const label = document.createElement("label");
      label.textContent = `${axis} ${side}`;
      const input = document.createElement("input");
      input.type = "number";
      input.step = "any";
      input.value = String(box[side][index]);
      input.disabled = !enabled.checked;
      input.setAttribute("aria-label", `Section ${axis} ${side}`);
      fields.push({ input, index, side });
      label.append(input);
      grid.append(label);
    }
  }
  const update = () => {
    const next = { min: [], max: [] };
    let valid = true;
    for (const field of fields) {
      const value = Number(field.input.value);
      const finite = field.input.value.trim() !== "" && Number.isFinite(value);
      field.input.setCustomValidity(finite ? "" : "Enter a finite number.");
      if (!finite) valid = false;
      next[field.side][field.index] = value;
    }
    for (let index = 0; index < 3; index += 1) {
      if (next.min[index] >= next.max[index]) {
        fields.find((field) => field.index === index && field.side === "max").input.setCustomValidity("Maximum must be greater than minimum.");
        valid = false;
      }
    }
    if (!valid) return;
    dispatch({ type: "applySectionBox", sectionBox: next });
    updateSectionBoxControlValues(next, true);
    renderCanvas();
  };
  enabled.addEventListener("change", () => {
    if (enabled.checked) {
      update();
    } else {
      dispatch({ type: "applySectionBox" });
      updateSectionBoxControlValues(sectionBoxDefaults(currentState.bounds), false);
      renderCanvas();
    }
  });
  for (const { input } of fields) input.addEventListener("change", update);
  const reset = document.createElement("button");
  reset.type = "button";
  reset.textContent = "Reset section";
  reset.addEventListener("click", () => {
    dispatch({ type: "applySectionBox" });
    updateSectionBoxControlValues(sectionBoxDefaults(currentState.bounds), false);
    renderCanvas();
  });
  section.append(heading, enabledLabel, grid, reset);
  dom.sectionBoxControls.append(section);

  function updateSectionBoxControlValues(nextBox, active) {
    enabled.checked = active;
    for (const field of fields) {
      field.input.value = String(nextBox[field.side][field.index]);
      field.input.disabled = !active;
      field.input.setCustomValidity("");
    }
  }
}

// A short column, not a row of nine. The view gizmo in the corner already
// orbits to any axis - including the four this omits - so spelling every one
// out as a button spent the top of the viewport on a duplicate control.
const CAMERA_BUTTONS = [
  { glyph: "ISO", label: "Isometric", view: "iso" },
  { glyph: "+X", label: "+X", view: "positiveX" },
  { glyph: "+Z", label: "+Z", view: "positiveZ" },
  { glyph: "+", label: "Zoom in", zoom: 1.25 },
  { glyph: "−", label: "Zoom out", zoom: 0.8 }
];

function renderCameraControls() {
  dom.cameraControls.replaceChildren();
  for (const spec of CAMERA_BUTTONS) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = spec.glyph;
    // The glyph is short enough to be ambiguous, so the accessible name spells
    // the action out rather than reading as "plus".
    button.setAttribute("aria-label", spec.label);
    button.dataset.focusKey = `camera:${spec.view ?? spec.label}`;
    button.title = spec.label;
    button.addEventListener("click", () =>
      spec.view ? viewportRenderer?.setStandardView(spec.view) : viewportRenderer?.zoomBy(spec.zoom)
    );
    dom.cameraControls.append(button);
  }
  // Moved in beside them: one column of view controls reads as one control,
  // where a separate floating button read as a second, unrelated one. The
  // accessible name stays "Reset 3D view" - only the visible label shortens.
  dom.resetView.textContent = "⤢";
  dom.resetView.title = "Reset view — fit the full scene";
  dom.cameraControls.append(dom.resetView);
}


function renderLayerTree(categories) {
  dom.layerList.replaceChildren();
  // Both numbers on the closed row: how many layers there are, and how many are
  // drawn. The second is the one that answers "why can I not see it".
  const layerIds = categories.flatMap((category) => category.layerIds);
  const shown = layerIds.filter((layerId) => currentState.layers[layerId]?.visible !== false).length;
  dom.layerTally.textContent = layerIds.length > 0 ? `${shown} of ${layerIds.length}` : "";
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
  // Classed so the row can carry a pointer-target floor: the checkbox itself is
  // 13px, and the label is what a click actually lands on.
  label.className = "layer-toggle";
  const input = document.createElement("input");
  input.type = "checkbox";
  input.checked = layer?.visible !== false;
  input.addEventListener("change", () => {
    dispatch({ type: "setLayerVisibility", layerId: leaf.layerId, visible: input.checked });
    render();
  });
  label.append(input, ` ${leaf.label} (${leaf.count})`);
  return label;
}

function renderDiagnostics() {
  dom.diagnosticList.replaceChildren();
  dom.diagnosticList.className = "diagnostics-workflow";
  const reviewDiagnostics = currentState.review?.tables?.diagnostics?.rows ?? currentState.review?.diagnostics ?? [];
  const allSceneDiagnostics = currentState.diagnostics ?? [];
  const previewDiagnostics = allSceneDiagnostics.filter(isLoadOrPreviewDiagnostic);
  const sceneDiagnostics = allSceneDiagnostics.filter((diagnostic) => !isLoadOrPreviewDiagnostic(diagnostic));
  const loadDiagnostics = [...(currentState.reviewDiagnostics ?? []), ...previewDiagnostics];
  const provenance = (currentState.review?.provenance ?? []).map((record) => ({
    severity: "info",
    code: `PROVENANCE_${String(record.kind ?? "record").toUpperCase()}`,
    source: record.solver_name ?? record.kind ?? "review package",
    target: record.id ?? record.load_case ?? "review",
    message: `${record.load_case ? `Load case ${record.load_case}; ` : ""}${Object.keys(record.files ?? {}).length} linked artifact(s).`
  }));
  const issues = (currentState.issues ?? []).map((issue) => ({
    severity: issue.severity ?? "warning",
    code: issue.id ?? "SCENE_ISSUE",
    source: "scene issue",
    target: (issue.entity_ref ?? issue.load_case ?? (issue.object_ids ?? []).join(", ")) || "scene",
    message: issue.title ?? issue.message ?? "Scene issue without detail."
  }));

  renderDiagnosticGroup("Review diagnostics", reviewDiagnostics);
  renderDiagnosticGroup("Review provenance", provenance);
  renderDiagnosticGroup("Scene diagnostics", sceneDiagnostics);
  renderDiagnosticGroup("Scene issues", issues);
  renderDiagnosticGroup("Load and preview diagnostics", loadDiagnostics);
  // The evidence dock used to decide this; the list now lives in the Issues
  // task and shows itself whenever it has something to say.
  dom.diagnosticList.hidden = dom.diagnosticList.childElementCount === 0;
}

function isLoadOrPreviewDiagnostic(diagnostic) {
  const code = String(diagnostic?.code ?? "").toLowerCase();
  return code.startsWith("viewer.review.") || code.includes("preview");
}

function renderDiagnosticGroup(title, diagnostics) {
  const section = document.createElement("section");
  section.className = "diagnostic-group";
  const heading = document.createElement("h2");
  heading.textContent = `${title} (${diagnostics.length})`;
  section.append(heading);

  if (diagnostics.length === 0) {
    const empty = document.createElement("p");
    empty.className = "meta";
    empty.textContent = "None reported.";
    section.append(empty);
    dom.diagnosticList.append(section);
    return;
  }

  for (const diagnostic of diagnostics) {
    const item = document.createElement("article");
    item.className = "diagnostic-item";
    const badge = document.createElement("span");
    badge.className = "severity-badge";
    badge.dataset.severity = String(diagnostic.severity ?? "info").toLowerCase();
    badge.textContent = String(diagnostic.severity ?? "info").toUpperCase();
    const message = document.createElement("p");
    message.textContent = diagnostic.message ?? "No detail supplied.";
    const trace = document.createElement("dl");
    appendTraceField(trace, "Source", diagnostic.source ?? "Not supplied");
    appendTraceField(trace, "Code", diagnostic.code ?? "diagnostic");
    appendTraceField(trace, "Target", diagnostic.target ?? "Not supplied");
    item.append(badge, message, trace);
    section.append(item);
  }
  dom.diagnosticList.append(section);
}

function appendTraceField(parent, labelText, valueText) {
  const term = document.createElement("dt");
  term.textContent = labelText;
  const value = document.createElement("dd");
  value.textContent = String(valueText);
  parent.append(term, value);
}

// Object navigation remains beside the result and display controls.
const FIND_SCOPES = [
  { id: "body", label: "Body" },
  { id: "kind", label: "Kind" },
  { id: "material", label: "Material" },
  { id: "route", label: "Route" },
  { id: "group", label: "Group" },
  { id: "source", label: "Source" }
];

const BODY_GROUP_LABELS = {
  geometry: "Geometry",
  analysis_mesh: "Analysis mesh",
  subpoints: "Sub-points",
  deformed: "Deformed mesh",
  other: "Other (not a body)"
};

let findGroupBy = "group";

function openFind() {
  dom.objectsSection.open = true;
  render();
}

function closeFind() {
  dom.searchInput.blur();
}

function renderFindPane() {
  dom.findDismiss.hidden = currentSearch.trim() === "";

  dom.findScope.replaceChildren();
  for (const scope of FIND_SCOPES) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "scope-chip";
    button.dataset.findScopeId = scope.id;
    button.dataset.focusKey = `scope:${scope.id}`;
    button.setAttribute("aria-pressed", String(scope.id === findGroupBy));
    button.textContent = scope.label;
    button.addEventListener("click", () => {
      findGroupBy = scope.id;
      render();
    });
    dom.findScope.append(button);
  }
  renderObjects();
}

function renderObjects() {
  dom.objectList.replaceChildren();
  const matches = rankObjectMatches(currentState, currentSearch);
  const byId = new Map(matches.map((match) => [match.object.id, match]));
  const visible = new Set(currentState.visibleObjectIds ?? []);
  const selectedIds = new Set(relatedSelectionIds(currentState, currentState.selectedObjectIds ?? []));
  const tree = buildObjectTree(currentState, { groupBy: findGroupBy });

  let shown = 0;
  let hidden = 0;
  for (const group of tree.children) {
    const members = group.objectIds.filter((id) => byId.has(id));
    if (members.length === 0) continue;
    const drawn = members.filter((id) => visible.has(id));
    const notDrawn = members.filter((id) => !visible.has(id));
    shown += drawn.length;
    hidden += notDrawn.length;

    dom.objectList.append(groupHeader({ ...group, objectIds: members }, members.length, selectedIds));
    for (const id of drawn) {
      dom.objectList.append(objectRow(byId.get(id), true, selectedIds));
    }
    // Never silently dropped. The old list skipped anything not currently drawn,
    // so searching for something in a body you had switched off returned an
    // empty pane with no explanation.
    if (notDrawn.length > 0) {
      dom.objectList.append(hiddenReveal(notDrawn, byId));
    }
  }

  if (shown === 0 && hidden === 0) {
    dom.objectList.append(metaLine(currentSearch.trim() ? "No object matches that." : "This scene has no objects."));
  }
  renderRailUtility(shown, hidden);
}

function groupHeader(group, count, selected) {
  const header = document.createElement("button");
  header.type = "button";
  header.className = "group-header";
  header.dataset.groupId = group.id;
  header.dataset.focusKey = `group:${group.id}`;
  const label = document.createElement("span");
  label.textContent = findGroupBy === "body" ? BODY_GROUP_LABELS[group.label] ?? group.label : group.label;
  const tally = document.createElement("span");
  tally.className = "group-count";
  tally.textContent = String(count);
  header.append(label, tally);
  header.title = "Select every matching object in this group";
  header.setAttribute("aria-pressed", String(group.objectIds.every(id => selected.has(id))));
  header.addEventListener("click", () => {
    dispatch({ type: "selectObjects", objectIds: group.objectIds });
    selectedObjectId = currentState.selectedObjectIds[0] ?? selectedObjectId;
    render();
  });
  return header;
}

function objectRow(match, drawn, selectedIds) {
  const object = match.object;
  const button = document.createElement("button");
  button.type = "button";
  button.className = "object-row";
  button.dataset.objectId = object.id;
  button.dataset.focusKey = `object:${object.id}`;
  // Two spans concatenate into "Smoke pipepipe - element:..." with no separator
  // in the accessible name, so state it explicitly.
  button.setAttribute("aria-label", `${object.name || object.id} - ${object.kind}`);
  const selected = selectedIds.has(object.id);
  button.classList.toggle("selected", selected);
  button.setAttribute("aria-pressed", String(selected));
  if (!drawn) button.classList.add("not-drawn");

  const name = document.createElement("span");
  name.className = "object-name";
  appendHighlighted(name, object.name || object.id, match);
  const meta = document.createElement("span");
  meta.className = "object-meta";
  meta.textContent = [object.kind, refLabel(object.entity_ref)].filter(Boolean).join(" · ");
  button.append(name, meta);

  // Say which field the hit landed in whenever it was not one the row shows,
  // so a result never looks arbitrary.
  if (match.field && !["name", "id"].includes(match.field)) {
    const chip = document.createElement("span");
    chip.className = "match-chip";
    chip.textContent = `matched ${match.field}`;
    button.append(chip);
  }
  button.addEventListener("click", (event) => {
    selectedObjectId = object.id;
    dispatch({ type: "selectObject", objectId: object.id, additive: event.shiftKey });
    render();
  });
  return button;
}

function hiddenReveal(objectIds, byId) {
  const row = document.createElement("button");
  row.type = "button";
  row.className = "hidden-reveal";
  row.dataset.hiddenReveal = String(objectIds.length);
  row.textContent = `${objectIds.length} more hidden — show`;
  row.title = "These match but belong to a body that is switched off";
  row.addEventListener("click", () => {
    const layerIds = new Set();
    for (const id of objectIds) {
      for (const layerId of currentState.objectLayerIds?.[id] ?? []) layerIds.add(layerId);
    }
    for (const layerId of layerIds) dispatch({ type: "setLayerVisibility", layerId, visible: true });
    render();
  });
  return row;
}

function appendHighlighted(element, text, match) {
  const usable = match?.field === "name" && match.start >= 0 && match.end <= text.length;
  if (!usable) {
    element.textContent = text;
    return;
  }
  element.append(
    document.createTextNode(text.slice(0, match.start)),
    Object.assign(document.createElement("mark"), { textContent: text.slice(match.start, match.end) }),
    document.createTextNode(text.slice(match.end))
  );
}

function refLabel(ref) {
  if (typeof ref === "string") return ref;
  return ref?.kind && ref?.id ? `${ref.kind}:${ref.id}` : "";
}

// View utilities stay available while searching for objects.
function renderRailUtility(shown = 0, hidden = 0) {
  dom.railUtility.replaceChildren();
  {
    // "All layers" is not here any more - the tree moved into the Display
    // strip, as the last row of the list whose curated rows it backs up.
    for (const [id, label] of [["section", "Section box"], ["views", "Saved views"]]) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "utility-button";
      button.dataset.railTool = id;
      button.dataset.focusKey = `tool:${id}`;
      button.setAttribute("aria-expanded", String(openPopoverId === id));
      button.textContent = label;
      button.addEventListener("click", () => {
        openPopoverId = openPopoverId === id ? null : id;
        render();
      });
      dom.railUtility.append(button);
    }
  }
  dom.findTally.textContent = hidden > 0 ? `${shown} drawn / ${hidden} hidden` : `${shown} objects`;
  // The unit chip used to end this row. It governs every quantity on screen,
  // including the inspector's in Build mode where this rail does not exist, so
  // it belongs to the session line at the bottom rather than to the rail.
}

let openPopoverId = null;
const expandedBodies = new Set();
let wallSectionOpen = false;
let bodyLegendOpen = false;

function renderRailPopover() {
  dom.railPopover.hidden = openPopoverId === null;
  if (dom.railPopover.hidden) return;
  for (const [id, node] of [
    ["section", dom.sectionBoxControls],
    ["views", dom.savedViews]
  ]) {
    if (node) node.hidden = id !== openPopoverId;
  }
}

function renderIssues() {
  dom.issueList.replaceChildren();
  const filterLabel = document.createElement("label");
  const filterInput = document.createElement("input");
  filterInput.type = "checkbox";
  filterInput.checked = issueFilters.operatingOnly;
  filterInput.addEventListener("change", () => {
    issueFilters = { ...issueFilters, operatingOnly: filterInput.checked };
    renderIssues();
  });
  filterLabel.append(filterInput, " Operating-only");
  dom.issueList.append(filterLabel);

  const groups = groupIssues(currentState, issueFilters);
  if (groups.length === 0) {
    const empty = document.createElement("div");
    empty.className = "meta";
    empty.textContent = "No issues.";
    dom.issueList.append(empty);
    return;
  }
  for (const group of groups) {
    const header = document.createElement("div");
    header.className = "tree-row";
    header.textContent = `${group.severity.toUpperCase()} - ${group.loadCase} - ${group.status} (${group.issues.length})`;
    dom.issueList.append(header);
    for (const issue of group.issues) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = issue.id === currentState.activeIssueId ? "selected" : "";
      button.textContent = `${issue.severity.toUpperCase()} - ${issue.title}`;
      button.addEventListener("click", () => {
        dispatch({ type: "focusIssue", issueId: issue.id });
        const marker = currentState.selectedObjectIds
          .map((objectId) => currentState.objects.find((obj) => obj.id === objectId))
          .find((obj) => obj?.kind === "clash_marker");
        selectedObjectId = marker?.id ?? currentState.selectedObjectIds[0] ?? null;
        render();
      });
      dom.issueList.append(button);
    }
  }
}


function renderBuildIssues() {
  // Build mode hides the rail, so the live model's own issues would have no
  // list UI at all. They surface here, in the code pane: one row per issue,
  // each focusing the 3D camera exactly like its review-rail twin. Review
  // bundles keep their rail list; each mode shows its own bundle's issues.
  dom.buildIssues.replaceChildren();
  const issues = isBuildMode() ? (currentState.issues ?? []) : [];
  dom.buildIssues.hidden = issues.length === 0;
  if (issues.length === 0) return;
  const heading = document.createElement("h2");
  heading.textContent = `Model issues (${issues.length})`;
  dom.buildIssues.append(heading);
  for (const issue of issues) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = issue.id === currentState.activeIssueId ? "selected" : "";
    button.dataset.focusKey = `build-issue:${issue.id}`;
    button.textContent = `${String(issue.severity ?? "warning").toUpperCase()} - ${issue.title ?? issue.id}`;
    button.addEventListener("click", () => {
      dispatch({ type: "focusIssue", issueId: issue.id });
      const marker = currentState.selectedObjectIds
        .map((objectId) => currentState.objects.find((obj) => obj.id === objectId))
        .find((obj) => obj?.kind === "clash_marker");
      selectedObjectId = marker?.id ?? currentState.selectedObjectIds[0] ?? null;
      render();
    });
    dom.buildIssues.append(button);
  }
}


function renderProperties() {
  // The script links below are drawn against this; model.py's input listener redraws when it flips.
  studio.linesMoved = scriptLinesMoved();
  const summary = getSelectionSummary(currentState, selectedObjectId);
  dom.propertyActions.replaceChildren();
  dom.properties.replaceChildren();
  const issueSummary = currentState.activeIssueId ? getIssueSummary(currentState, currentState.activeIssueId) : null;
  dom.inspector.hidden = !summary && !issueSummary;
  if (!summary) {
    if (issueSummary) {
      dom.properties.append(renderPropertySection({ title: "Issue", rows: issueSummary }));
    } else {
      const empty = document.createElement("div");
      empty.className = "meta";
      empty.textContent = "Select an object.";
      dom.properties.append(empty);
    }
    return;
  }
  const sections = summary.sections;
  const selectedObject = currentState.objects.find((obj) => obj.id === selectedObjectId);
  if (selectedObject?.entity_ref && currentState.selectedObjectIds.length === 1) {
    const copyButton = document.createElement("button");
    copyButton.type = "button";
    copyButton.textContent = "Copy Entity Ref";
    copyButton.addEventListener("click", () => {
      // Announced only once the write resolved. This used to swallow the
      // rejection and report "Copied" regardless, so on a non-secure origin the
      // reviewer was told the ref was on the clipboard when it was not.
      const write = navigator.clipboard?.writeText(selectedObject.entity_ref);
      if (!write) {
        setStatus("Clipboard unavailable in this browser - select the value to copy it", true);
        return;
      }
      void write.then(
        () => setStatus(`Copied ${selectedObject.entity_ref}`),
        () => setStatus("Could not copy - select the value to copy it", true)
      );
    });
    dom.propertyActions.append(copyButton);
  }
  const fitButton = document.createElement("button");
  fitButton.type = "button";
  fitButton.textContent = "Fit selected";
  fitButton.addEventListener("click", () => {
    dispatch({ type: "fitSelection" });
    render();
  });
  const hideButton = document.createElement("button");
  hideButton.type = "button";
  hideButton.textContent = "Hide selected";
  hideButton.addEventListener("click", () => {
    dispatch({ type: "hideSelected" });
    render();
  });
  const isolateButton = document.createElement("button");
  isolateButton.type = "button";
  isolateButton.textContent = "Isolate selected";
  isolateButton.addEventListener("click", () => {
    dispatch({ type: "isolateSelection" });
    render();
  });
  dom.propertyActions.append(fitButton, hideButton, isolateButton);
  const clearButton = document.createElement("button");
  clearButton.type = "button";
  clearButton.textContent = "Clear selection";
  clearButton.addEventListener("click", () => { dispatch({ type: "selectObjects", objectIds: [] }); render(); });
  dom.propertyActions.append(clearButton);
  if ((currentState.selectedObjectIds ?? []).length > 1) {
    const objects = currentState.selectedObjectIds.map(id => currentState.objects.find(o => o.id === id)).filter(Boolean);
    const groups = [...new Set(objects.flatMap(o => o.group_ids ?? o.metadata?.groups ?? []))];
    dom.properties.append(renderEvidenceHead({
      title: `${objects.length} objects selected`,
      lede: groups.length ? `Groups: ${groups.join(", ")}` : "Multiple objects",
      meta: "Fit, hide and isolate apply to the whole selection."
    }));
    for (const object of objects) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = object.name || object.id;
      button.addEventListener("click", () => { dispatch({ type: "selectObject", objectId: object.id }); render(); });
      dom.properties.append(button);
    }
    return;
  }
  dom.properties.append(renderEvidenceHead(summary));
  // A load arrow's entity ref names its node, so it is recognised by kind.
  if (isBuildMode() && (/^(element|support):/.test(selectedObject?.entity_ref ?? "") || selectedObject?.kind === "applied_load")) {
    dom.properties.append(renderScriptLink(selectedObject));
  }
  if (summary.dofs) {
    dom.properties.append(renderRestraintStrip(summary.dofs, summary.restraintLine));
  }
  for (const section of sections) {
    dom.properties.append(renderEvidenceSection(section));
  }
  if (issueSummary) {
    dom.properties.append(renderPropertySection({ title: "Issue", rows: issueSummary }));
    appendIssueReviewActions(issueSummary);
  }
  const contact = renderContactReview(currentState, dispatch, render, "selection", selectedObjectId);
  if (contact) dom.properties.append(contact);
  if (Object.keys(summary.reference).length > 0) {
    dom.properties.append(renderReference(summary.reference));
  }
}

// What was selected, in words, before any number. The lede is the panel's one
// sentence of prose; the meta line carries the name, node and position that
// used to arrive as four separate id rows.
function renderEvidenceHead(summary) {
  const head = document.createElement("div");
  head.className = "evidence-head";
  const titleRow = document.createElement("div");
  titleRow.className = "evidence-title-row";
  const title = document.createElement("div");
  title.className = "evidence-title";
  title.textContent = summary.title;
  titleRow.append(title);
  if (summary.badge) {
    const badge = document.createElement("span");
    badge.className = "evidence-badge";
    badge.textContent = summary.badge;
    titleRow.append(badge);
  }
  head.append(titleRow);
  if (summary.lede) {
    const lede = document.createElement("p");
    lede.className = "evidence-lede";
    lede.textContent = summary.lede;
    head.append(lede);
  }
  if (summary.meta) {
    const meta = document.createElement("div");
    meta.className = "evidence-meta";
    meta.textContent = summary.meta;
    head.append(meta);
  }
  return head;
}

// Option A from the design canvas: one cell per degree of freedom, so the
// filled cells make a shape you can compare across supports without reading.
// A cell is too narrow for a word longer than "one-way", so spring and one-way
// carry a glyph as well - and the state word underneath is the glyph's key.
const DOF_GLYPHS = Object.freeze({
  spring: "M1 5h1.6l1.6-3.4 2.4 6.8 2.4-6.8L10.6 5H13",
  "one-way": "M6 1.5l4 6H2z M0.5 9.5h11"
});

function renderRestraintStrip(dofs, sourceLine) {
  const section = document.createElement("section");
  section.className = "property-section";
  const heading = document.createElement("h3");
  heading.textContent = "Restraint";
  const chip = scriptLineChip(sourceLine);
  if (chip) heading.append(chip);
  const strip = document.createElement("div");
  strip.className = "restraint-strip";
  for (const dof of dofs) {
    const column = document.createElement("div");
    column.className = "restraint-dof";
    const cell = document.createElement("div");
    cell.className = `restraint-cell is-${dof.state.replace(/\s+/g, "-")}`;
    const axis = document.createElement("span");
    axis.textContent = dof.axis;
    cell.append(axis);
    const path = DOF_GLYPHS[dof.state];
    if (path) {
      const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      svg.setAttribute("viewBox", "0 0 14 11");
      svg.setAttribute("width", "14");
      svg.setAttribute("height", "11");
      svg.setAttribute("fill", "none");
      svg.setAttribute("stroke", "currentColor");
      svg.setAttribute("stroke-width", "1.3");
      svg.setAttribute("stroke-linejoin", "round");
      svg.setAttribute("aria-hidden", "true");
      const shape = document.createElementNS("http://www.w3.org/2000/svg", "path");
      shape.setAttribute("d", path);
      svg.append(shape);
      cell.append(svg);
    }
    const word = document.createElement("div");
    word.className = `restraint-word is-${dof.state.replace(/\s+/g, "-")}`;
    word.textContent = dof.state;
    // The cell is decorative once the word is read out with it, so the pair
    // announces as one thing rather than as "X" then "one-way".
    column.setAttribute("role", "group");
    column.setAttribute("aria-label", `${dof.axis} ${dof.state}`);
    column.append(cell, word);
    strip.append(column);
  }
  section.append(heading, strip);
  return section;
}

function renderEvidenceSection(section) {
  const wrapper = document.createElement("section");
  wrapper.className = "property-section";
  const heading = document.createElement("h3");
  heading.textContent = section.title;
  const headingChip = scriptLineChip(section.sourceLine);
  if (headingChip) heading.append(headingChip);
  wrapper.append(heading);
  const table = document.createElement("table");
  table.className = "property-table";
  const body = document.createElement("tbody");
  for (const line of section.lines) {
    if (line.kind === "note") {
      continue;
    }
    const row = document.createElement("tr");
    const label = document.createElement("th");
    label.scope = "row";
    label.textContent = line.label;
    const cell = document.createElement("td");
    cell.textContent = formatPropertyValue(line.value);
    const chip = scriptLineChip(line.sourceLine);
    if (chip) cell.append(chip);
    row.append(label, cell);
    body.append(row);
  }
  table.append(body);
  wrapper.append(table);
  for (const line of section.lines.filter((entry) => entry.kind === "note")) {
    const note = document.createElement("p");
    note.className = "evidence-note";
    note.textContent = line.label;
    wrapper.append(note);
  }
  return wrapper;
}

// The ids, folded away, and only the ones nothing else derives.
function renderReference(reference) {
  const details = document.createElement("details");
  details.className = "evidence-reference";
  const summary = document.createElement("summary");
  summary.textContent = "Reference";
  details.append(summary);
  details.append(renderPropertySection({ title: "", rows: reference }));
  return details;
}

function renderPropertySection(section) {
  const wrapper = document.createElement("section");
  wrapper.className = "property-section";
  const heading = document.createElement("h3");
  heading.textContent = section.title;
  // A titleless section is the Reference well: its <summary> is the heading.
  heading.hidden = !section.title;
  const table = document.createElement("table");
  table.className = "property-table";
  const body = document.createElement("tbody");
  for (const [key, value] of Object.entries(section.rows ?? {})) {
    const row = document.createElement("tr");
    const label = document.createElement("th");
    label.scope = "row";
    label.textContent = key;
    const cell = document.createElement("td");
    cell.textContent = formatPropertyValue(value);
    row.append(label, cell);
    body.append(row);
  }
  table.append(body);
  wrapper.append(heading, table);
  return wrapper;
}

function formatPropertyValue(value) {
  if (Array.isArray(value) || (value && typeof value === "object")) {
    return JSON.stringify(value);
  }
  return String(value);
}

function appendIssueReviewActions(issueSummary) {
  const status = document.createElement("select");
  status.setAttribute("aria-label", "Issue Status");
  for (const option of ["open", "reviewing", "resolved"]) {
    const element = document.createElement("option");
    element.value = option;
    element.textContent = option;
    element.selected = option === issueSummary.status;
    status.append(element);
  }
  status.addEventListener("change", () => {
    dispatch({ type: "setIssueReviewStatus", issueId: issueSummary.id, status: status.value });
    render();
  });

  const comment = document.createElement("textarea");
  comment.setAttribute("aria-label", "Issue Comment");
  comment.value = issueSummary.comment ?? "";
  comment.addEventListener("change", () => {
    dispatch({ type: "setIssueReviewComment", issueId: issueSummary.id, comment: comment.value });
  });

  const restoreButton = document.createElement("button");
  restoreButton.type = "button";
  restoreButton.textContent = "Restore view";
  restoreButton.addEventListener("click", () => {
    dispatch({ type: "restoreVisibility" });
    render();
  });

  dom.propertyActions.append(status, comment, restoreButton);
}

function renderCanvas() {
  if (viewportUnavailable) {
    setStatus("Results ready · 3D unavailable", true);
    return;
  }
  try {
    viewportRenderer ??= createThreeCanvasRenderer(dom.canvas);
  } catch (error) {
    if (error?.code !== WEBGL2_UNAVAILABLE) throw error;
    viewportUnavailable = true;
    renderViewportUnavailable();
    setStatus("Results ready · 3D unavailable", true);
    return;
  }
  renderCameraControls();
  const graph = viewportRenderer.render(currentState);
  const result = graph;
  applyHoverHighlight(graph, hoveredObjectId);
  if (hoveredObjectId) viewportRenderer.redraw();
  lastRenderGraph = result;
  // What is actually drawn, not what the graph could draw. The scene-graph
  // cache stopped rebuilding when only visibility changes, so a hidden object
  // stays in renderableObjects with visible=false - and this diagnostic is read
  // as "what is on screen" by the layer-state and profile checks, which is the
  // question it has to answer.
  const objectIds = [...new Set(result.renderableObjects
    .filter((object) => object.visible !== false)
    .flatMap((object) => object.userData.objectIds ?? []))];
  globalThis.__tubaViewer = {
    bootId,
    state: currentState,
    lastRender: {
      diagnostics: result.diagnostics,
      objectIds,
      renderableCount: result.renderableObjects.length
    },
    resultReview: {
      hotspots: getHotspots(currentState),
      legend: getScalarLegend(currentState)
    }
  };
  if (result.diagnostics.length > 0) {
    setStatus(`Ready with ${result.diagnostics.length} render warning(s)`, "warn");
  } else {
    setStatus("Ready");
  }
}

function renderViewportUnavailable() {
  dom.viewport.dataset.renderer = "unavailable";
  const panel = document.createElement("section");
  panel.className = "viewport-unavailable";
  panel.dataset.viewportUnavailable = "";
  panel.setAttribute("aria-label", "3D view unavailable");

  const heading = document.createElement("h2");
  heading.textContent = "3D view unavailable";
  const explanation = document.createElement("p");
  explanation.textContent = "This browser could not start WebGL2. The review report carries the processed result tables.";
  const action = document.createElement("p");
  action.textContent = "Try a current browser with graphics acceleration enabled, then reload this review.";
  panel.append(heading, explanation, action);
  dom.viewport.append(panel);
}

// The canvas carries tabindex="0" and an aria-label announcing an "Interactive
// 3D engineering review viewport", but had no keyboard path to the camera at
// all: OrbitControls.listenToKeyEvents was never called and nothing bound a
// keydown. Focusing it and pressing a key did nothing.
const ORBIT_KEY_STEP_RAD = Math.PI / 24;
const CANVAS_KEY_ACTIONS = {
  ArrowLeft: () => viewportRenderer?.orbitBy(-ORBIT_KEY_STEP_RAD, 0),
  ArrowRight: () => viewportRenderer?.orbitBy(ORBIT_KEY_STEP_RAD, 0),
  ArrowUp: () => viewportRenderer?.orbitBy(0, -ORBIT_KEY_STEP_RAD),
  ArrowDown: () => viewportRenderer?.orbitBy(0, ORBIT_KEY_STEP_RAD),
  "+": () => viewportRenderer?.zoomBy(1.25),
  "=": () => viewportRenderer?.zoomBy(1.25),
  "-": () => viewportRenderer?.zoomBy(0.8),
  _: () => viewportRenderer?.zoomBy(0.8),
  Home: () => viewportRenderer?.resetView(),
  "0": () => viewportRenderer?.resetView(),
  x: () => viewportRenderer?.setStandardView("positiveX"),
  X: () => viewportRenderer?.setStandardView("negativeX"),
  y: () => viewportRenderer?.setStandardView("positiveY"),
  Y: () => viewportRenderer?.setStandardView("negativeY"),
  z: () => viewportRenderer?.setStandardView("positiveZ"),
  Z: () => viewportRenderer?.setStandardView("negativeZ"),
  i: () => viewportRenderer?.setStandardView("iso"),
  I: () => viewportRenderer?.setStandardView("iso")
};

dom.canvas.addEventListener("keydown", (event) => {
  if (event.ctrlKey || event.metaKey || event.altKey) return;
  const action = CANVAS_KEY_ACTIONS[event.key];
  if (!action) return;
  // Arrow keys would otherwise scroll the workspace out from under the canvas.
  event.preventDefault();
  action();
});

dom.canvas.addEventListener("click", (event) => {
  if (suppressNextCanvasClick) {
    suppressNextCanvasClick = false;
    return;
  }
  if (!currentState) {
    return;
  }
  if (viewportRenderer?.handleGizmoClick(event)) {
    return;
  }
  const rect = dom.canvas.getBoundingClientRect();
  const point = { x: event.clientX - rect.left, y: event.clientY - rect.top };
  const objectId = pickRenderedObject(lastRenderGraph, point, { width: rect.width, height: rect.height });
  if (objectId) {
    selectedObjectId = objectId;
    dispatch({ type: "selectObject", objectId, additive: event.shiftKey });
    render();
  }
});

dom.resetView.addEventListener("click", () => viewportRenderer?.resetView());
dom.bodyLegendToggle.addEventListener("click", () => {
  bodyLegendOpen = !bodyLegendOpen;
  render();
});

dom.canvas.addEventListener("pointerdown", (event) => {
  orbiting = true;
  pointerDownPoint = { x: event.clientX, y: event.clientY };
  suppressNextCanvasClick = false;
  pendingHoverPoint = null;
});

dom.canvas.addEventListener("pointermove", (event) => {
  if (!pointerDownPoint) return;
  const deltaX = event.clientX - pointerDownPoint.x;
  const deltaY = event.clientY - pointerDownPoint.y;
  if (deltaX * deltaX + deltaY * deltaY > ORBIT_CLICK_DRAG_THRESHOLD_PX ** 2) {
    suppressNextCanvasClick = true;
  }
});

globalThis.addEventListener("pointerup", () => {
  orbiting = false;
  pointerDownPoint = null;
});

globalThis.addEventListener("pointercancel", () => {
  orbiting = false;
  pointerDownPoint = null;
  suppressNextCanvasClick = false;
});

dom.canvas.addEventListener("mousemove", (event) => {
  if (
    orbiting ||
    !currentState ||
    !lastRenderGraph
  ) return;
  pendingHoverPoint = { x: event.clientX, y: event.clientY };
  if (hoverFrameId !== null) return;
  hoverFrameId = requestAnimationFrame(function pickHover() {
    hoverFrameId = null;
    if (orbiting || !pendingHoverPoint || !lastRenderGraph) return;
    if (performance.now() - lastHoverPickTime < 32) {
      hoverFrameId = requestAnimationFrame(pickHover);
      return;
    }
    lastHoverPickTime = performance.now();
    const rect = dom.canvas.getBoundingClientRect();
    const objectId = pickRenderedObject(
      lastRenderGraph,
      { x: pendingHoverPoint.x - rect.left, y: pendingHoverPoint.y - rect.top },
      { width: rect.width, height: rect.height }
    );
    pendingHoverPoint = null;
    if (objectId === hoveredObjectId) return;
    hoveredObjectId = objectId;
    dom.canvas.dataset.hoverObjectId = objectId ?? "";
    applyHoverHighlight(lastRenderGraph, objectId);
    viewportRenderer.redraw();
  });
});

// Without this a highlight outlives the pointer. A stale hover used to be wiped
// by the next render; now that hover outranks selection - so a render while the
// cursor rests on an object cannot drop it - the leave has to clear it itself,
// or the last object hovered stayed tinted after the cursor left the canvas.
dom.canvas.addEventListener("mouseleave", () => {
  pendingHoverPoint = null;
  if (hoveredObjectId === null) return;
  hoveredObjectId = null;
  dom.canvas.dataset.hoverObjectId = "";
  if (lastRenderGraph) applyHoverHighlight(lastRenderGraph, null);
  viewportRenderer?.redraw();
});

// Severity is three-valued, not two. It was a boolean, so a render warning had
// to pass `true` and came out in the error treatment: a red-bordered chip that
// was the loudest thing in the header, for diagnostics that do not stop
// anything. And because the auto-hide keys on the literal text "Ready", a
// message like "Ready with 2 render warning(s)" never hid either, so the
// loudest element on screen was also permanent.
//
// `true` still means error, so the fifteen call sites that pass it keep working.
function setStatus(message, severity = false) {
  const level = severity === true ? "error" : severity || "ok";
  // [data-runtime-status] is role="status" aria-live="polite": rewriting announces.
  // renderCanvas ends with setStatus("Ready") on every render, so without this
  // guard a screen reader said "Ready" after every checkbox, tab, slider nudge
  // and opacity click.
  if (dom.status.textContent === message && dom.status.dataset.level === level) {
    return;
  }
  dom.status.textContent = message;
  dom.status.dataset.level = level;
  dom.status.dataset.error = String(level === "error");
  dom.status.dataset.ready = String(level === "ok" && message === "Ready");
}

function connectLivePreview(wsUrl) {
  const socket = new WebSocket(wsUrl);
  socket.addEventListener("open", () => setStatus("Live preview connected"));
  socket.addEventListener("message", (event) => {
    void handleLivePreviewEvent(event.data);
  });
  socket.addEventListener("error", () => setStatus("Live preview connection failed", true));
  socket.addEventListener("close", () => {
    if (currentState) {
      setStatus("Live preview disconnected", true);
    }
  });
}

async function handleLivePreviewEvent(raw) {
  let message;
  try {
    message = JSON.parse(raw);
  } catch {
    setStatus("Live preview sent invalid JSON", true);
    return;
  }
  // model.py was saved from another editor and failed to run.
  if (message.type === "script_error") {
    if (studio.available) showScriptError(message);
    return;
  }
  if (["solve_started", "solve_failed", "solve_finished", "review_ready", "review_failed"].includes(message.type)) {
    await handleSolveEvent(message);
    return;
  }
  if (message.type === "scene_reloaded") {
    if (message.bundle) {
      // A project studio rebuilt one of its two bundles; the one not on screen
      // only moves the status.
      studio.reviewStale = Boolean(message.review_stale);
      // A Run here or a save elsewhere: the open .comm follows the model that just ran.
      if (message.bundle === "build") void loadComm();
      if (bundleKey(currentBundleUrl) !== message.bundle) {
        await refreshScriptFromDisk();
        render();
        return;
      }
    }
    const bundleUrl = message.bundle ?? message.bundle_url ?? currentBundleUrl;
    currentBundleUrl = bundleUrl;
    try {
      await loadBundle(bundleUrl, { preserve: true });
      await refreshScriptFromDisk();
      render();
      // In the studio the script pane already says what ran; a revision number
      // parked in the header only reads as jargon.
      setStatus(studio.available ? "Ready" : `Preview reloaded ${message.bundle_revision ?? ""}`.trim());
    } catch (error) {
      setStatus(error.message, true);
    }
    return;
  }
}

function metaLine(text) {
  const line = document.createElement("div");
  line.className = "meta";
  line.textContent = text;
  return line;
}

// A band heading that carries the state it is set to. Uppercase name, mono
// value: the name says which control group this is, the value says what it is
// doing to the scene when the group itself has scrolled out of the pane.
function railGroup(labelText, stateText = "") {
  const band = document.createElement("div");
  band.className = "rail-group";
  const heading = document.createElement("h2");
  heading.textContent = labelText;
  band.append(heading);
  if (stateText) {
    const state = document.createElement("span");
    state.className = "rail-group-state";
    state.textContent = stateText;
    band.append(state);
  }
  return band;
}

// One label, one control, on one line. The label-above-control stack this
// replaces cost 56px for the same pair, which is what filled the rail. A single
// form control is wrapped so the row label names it; a cluster of controls
// (slider plus button, a row of chips) is not, because a label may only name one
// thing - those carry their own aria-label.
function propertyRow(labelText, control) {
  const isControl = control.tagName === "SELECT" || control.tagName === "INPUT";
  const row = document.createElement(isControl ? "label" : "div");
  row.className = "prow";
  const name = document.createElement("span");
  name.className = "pname";
  name.textContent = labelText;
  if (isControl) focusKeyFor(control, labelText);
  row.append(name, control);
  return row;
}

// Every panel is replaceChildren()d on render, which destroys whatever the
// reviewer was inside. This is how restoreFocus puts them back.
function focusKeyFor(control, name) {
  control.dataset.focusKey = `bar:${name}`;
}

function plainSelect(value, options, onChange) {
  const select = document.createElement("select");
  for (const option of options) {
    const normalized = typeof option === "string" ? { id: option, label: option } : option;
    const element = document.createElement("option");
    element.value = normalized.id;
    element.textContent = normalized.label;
    element.selected = normalized.id === value;
    select.append(element);
  }
  select.title = select.options[select.selectedIndex]?.textContent ?? "";
  select.addEventListener("change", () => onChange(select.value));
  return select;
}

function glyphIcon(name) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("width", "8");
  svg.setAttribute("height", "9");
  svg.setAttribute("viewBox", "0 0 8 9");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("focusable", "false");
  for (const attributes of name === "pause"
    ? [{ x: "0", width: "3" }, { x: "5", width: "3" }]
    : []) {
    const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    rect.setAttribute("x", attributes.x);
    rect.setAttribute("y", "0");
    rect.setAttribute("width", attributes.width);
    rect.setAttribute("height", "9");
    rect.setAttribute("fill", "currentColor");
    svg.append(rect);
  }
  if (name === "play") {
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", "M0 0l8 4.5L0 9z");
    path.setAttribute("fill", "currentColor");
    svg.append(path);
  }
  return svg;
}

function hexColor(value) {
  return `#${Number(value).toString(16).padStart(6, "0")}`;
}


function formatPercent(ratio) {
  const value = Number(ratio) * 100;
  if (!Number.isFinite(value)) return "";
  return `${value >= 1 ? value.toFixed(0) : value.toFixed(2)}%`;
}

const DEFORMATION_RADIANS_PER_MS = 0.003;
let deformationAnimation = null;

function toggleDeformationAnimation() {
  if (deformationAnimation) {
    stopDeformationAnimation();
    render();
    return;
  }
  const base = getVisualDeformationDisplayScale(currentState);
  if (!(base > 1)) return;
  deformationAnimation = { base, frameId: null, startedAt: null };
  viewportRenderer?.setDeformationInteraction(true);
  deformationAnimation.frameId = requestAnimationFrame(stepDeformationAnimation);
  render();
}

function stopDeformationAnimation() {
  if (!deformationAnimation) return;
  const { base, frameId } = deformationAnimation;
  if (frameId !== null) cancelAnimationFrame(frameId);
  deformationAnimation = null;
  viewportRenderer?.setDeformationInteraction(false);
  // Put the scale back where the reviewer left it, so pausing never silently
  // changes the exaggeration a screenshot was taken at.
  dispatch({ type: "setVisualDeformationScale", scale: base });
}

function stepDeformationAnimation(timestamp = 0) {
  if (!deformationAnimation) return;
  deformationAnimation.frameId = requestAnimationFrame(stepDeformationAnimation);
  deformationAnimation.startedAt ??= timestamp;
  const phase = (timestamp - deformationAnimation.startedAt) * DEFORMATION_RADIANS_PER_MS;
  // Swings between the true displacement and the chosen exaggeration rather
  // than through zero: x1 is the honest shape, and that is the useful anchor.
  const sweep = (1 - Math.cos(phase)) / 2;
  dispatch({ type: "setVisualDeformationScale", scale: 1 + (deformationAnimation.base - 1) * sweep });
  if (!viewportRenderer?.renderDeformation(currentState)) renderCanvas();
}

globalThis.addEventListener("beforeunload", stopDeformationAnimation);

// The focus key is passed rather than taken from the label, because these labels
// carry their own value ("Displacement vector scale 1.5x") and the unit they are
// denominated in. A key derived from that text changes on the very edit whose
// render it has to survive, so restoreFocus could never find the control again.
function numericControl(labelText, value, step, onChange, key = labelText) {
  const label = document.createElement("label");
  const input = document.createElement("input");
  input.type = "number";
  input.min = "0";
  input.step = step;
  input.value = String(value);
  focusKeyFor(input, key);
  input.addEventListener("change", () => onChange(input.value));
  label.append(labelText, input);
  return label;
}

// On change, not input. onChange re-renders, and a render replaceChildren()s the
// pane this lives in - so firing per input event destroyed the element under the
// pointer at the drag's first step, and dropped keyboard focus to <body> after
// one arrow press, because these were the only rebuilt controls without a focus
// key. The thumb still tracks the pointer during the drag; the scene catches up
// on release, and the focus key puts the caret back after the render.
function rangeControl(labelText, value, min, max, step, onChange, key = labelText) {
  const label = document.createElement("label");
  const input = document.createElement("input");
  input.type = "range";
  input.min = String(min);
  input.max = String(max);
  input.step = String(step);
  input.value = String(value);
  focusKeyFor(input, key);
  input.addEventListener("change", () => onChange(input.value));
  label.append(labelText, input);
  return label;
}


function formatScale(value) {
  const number = Number(value);
  return Number.isFinite(number) ? String(Math.round(number * 1000) / 1000) : "1";
}

// Typing opens the finder. The field used to filter a list inside a collapsed
// disclosure, so typing in it changed nothing you could see.
dom.searchInput.addEventListener("input", () => {
  currentSearch = dom.searchInput.value;
  openFind();
});

dom.searchInput.addEventListener("focus", openFind);

dom.findDismiss.addEventListener("click", () => {
  currentSearch = "";
  dom.searchInput.value = "";
  closeFind();
  render();
});

dom.searchInput.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  // First Escape clears a query, second leaves the finder - so a mistyped
  // query never costs you the pane.
  if (currentSearch.trim()) {
    currentSearch = "";
    dom.searchInput.value = "";
    render();
    return;
  }
  closeFind();
});

dom.railToggle.addEventListener("click", () => {
  railExpanded = !railExpanded;
  renderRailChrome();
});

// -- Build mode: model.py beside the scene ----------------------------------

// The studio CLI opens the viewer with ?preview_ws=; a loopback page with no
// gallery catalog is the same server opened by hand. Anything else is a static
// bundle, where probing would only log a 404.
function mayBeStudio(catalog) {
  const loopback = ["127.0.0.1", "localhost", "[::1]"].includes(window.location.hostname);
  return !startupConfig.embed && Boolean(startupConfig.previewWebSocketUrl || (loopback && catalog.length === 0));
}

// Null for anything that is not a studio's JSON: a static host 404s, and the dev
// server answers unknown paths with its index page.
async function fetchStudioJson(path) {
  try {
    const response = await fetch(path, { cache: "no-store" });
    return response.ok ? await response.json() : null;
  } catch {
    return null;
  }
}

async function loadStudioProject(catalog) {
  if (!mayBeStudio(catalog)) return false;
  const info = await fetchStudioJson("/api/project");
  if (!info?.ok) return false;
  studio.project = info;
  studio.hasReview = Boolean(info.has_review);
  studio.reviewStale = Boolean(info.review_stale);
  studio.solving = Boolean(info.solving);
  studio.preparing = Boolean(info.preparing_review);
  return true;
}

async function initStudio(catalog) {
  if (!mayBeStudio(catalog)) return;
  const result = await fetchStudioJson("/api/script");
  if (typeof result?.code !== "string") return;
  studio.available = true;
  // loadStudioProject settled hasReview/reviewStale a few lines earlier, so the
  // rule itself lives in workflowState with the rest of the stage tree and is
  // tested there rather than through a browser.
  const stage = openingStage(studio);
  setScriptText(result.code);
  await showStudioBundle(stage);
  dispatch({ type: "setStage", stage });
  // The rail opens on workflowState's default tab - Results for a solved review,
  // Issues otherwise - so nothing here claims a task. This decides which stage
  // opens, not what the rail opens on.
  render();
}

function sameHostPreviewSocketUrl() {
  return `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}/preview/ws`;
}

// What is on screen, derived in one place from the session's facts. Every
// render site below asks this rather than recombining the mode globals, the
// rail flag and the embed flag for itself - which is how the opening stage
// came to be hardcoded in initStudio where nothing could test it.
function currentWorkspace() {
  return workspaceView(currentState ?? {}, { railExpanded });
}

// The stage lives in the scene state, so moving stages is a dispatch. studio
// and sourceView keep only what is theirs - whether they are available, what
// they can solve - and no longer carry a second copy of which stage we are in.
function currentStage() {
  return currentWorkspace().stage;
}

function isBuildMode() {
  return currentWorkspace().stage === "build";
}

// -- A published bundle's model.py and .comm, read-only -----------------------

async function loadBundleSource(baseUrl) {
  clearBundleSource();
  const derived = deriveBundleSource(currentBundle?.scene, currentBundle?.review);
  if (!derived) return;
  const root = String(baseUrl).replace(/\/+$/, "");
  let script;
  try {
    script = await fetchBundleText(root, derived.scriptUri);
  } catch {
    // A bundle that names a script it does not ship has nothing to show; the
    // review stands on its own.
    return;
  }
  sourceView.available = true;
  sourceView.baseUrl = root;
  sourceView.scriptUri = derived.scriptUri;
  sourceView.loadCases = derived.loadCases;
  sourceView.text.set(derived.scriptUri, script);
  setScriptText(script);
}

function clearBundleSource() {
  sourceView.available = false;
  sourceView.baseUrl = ".";
  sourceView.scriptUri = null;
  sourceView.loadCases = [];
  sourceView.text.clear();
  if (!studio.available) studio.codeTab = null;
}

async function fetchBundleText(baseUrl, uri) {
  const response = await fetch(`${baseUrl}/${uri}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Failed to load ${uri}: ${response.status} ${response.statusText}`);
  }
  const contentType = response.headers?.get?.("content-type") ?? "";
  if (contentType.toLowerCase().includes("text/html")) {
    throw new Error(`Expected text from ${uri}, but received HTML.`);
  }
  return response.text();
}

function renderMode() {
  const view = currentWorkspace();
  document.body.dataset.studio = String(studio.available);
  document.body.dataset.mode = view.stage === "build" ? "build" : "review";
  // The stage decides whether a dragged script width applies, so it is applied
  // where the stage is decided rather than once at startup.
  syncCodePaneWidth();
  dom.modeSwitch.hidden = !(studio.available || sourceView.available) || currentState.embed;
  for (const button of dom.modeSwitch.querySelectorAll("[data-mode]")) {
    button.setAttribute("aria-pressed", String(button.dataset.mode === document.body.dataset.mode));
  }
  dom.codePane.hidden = !view.scriptVisible;
  dom.codeText.readOnly = !studio.available;
  dom.codeRun.hidden = !studio.available;
  if (!studio.available) dom.codeState.textContent = "Read-only";
  renderCodeTabs();
  renderCodeMeshToggle();
  renderSolveControls();
}

function renderCodeMeshToggle() {
  if (!dom.codeMeshToggle) return;
  const meshBody = getBodies(currentState).find((candidate) => candidate.id === "analysis_mesh");
  if (!meshBody) {
    dom.codeMeshToggle.hidden = true;
    return;
  }
  dom.codeMeshToggle.hidden = false;
  const isVisible = meshBody.visible;
  dom.codeMeshToggle.setAttribute("aria-pressed", String(isVisible));
  dom.codeMeshToggle.title = isVisible
    ? "Hide 1D analysis mesh (Alt+M)"
    : "Show 1D analysis mesh elements and nodes (Alt+M)";
}

// -- Build mode's file tabs: model.py is the source, every .comm is generated --

// A studio owns the load cases in its study.py; a published bundle carries them
// in its scene and review. Both feed the same tab strip.
function codePaneCases() {
  return studio.available ? (studio.project?.load_cases ?? []) : sourceView.loadCases.map((entry) => entry.name);
}

function renderCodeTabs() {
  const cases = codePaneCases();
  if (!cases.includes(studio.codeTab)) studio.codeTab = null;
  const { codeTab } = studio;
  const key = `${studio.available ? "studio" : "bundle"}\n${cases.join("\n")}`;
  if (dom.codeTabs.dataset.cases !== key || !dom.codeTabs.children.length) {
    dom.codeTabs.dataset.cases = key;
    dom.codeTabs.replaceChildren(
      codeTabButton(null, "model.py", "source", "The source: every other file here is generated from it"),
      ...cases.map((name) =>
        codeTabButton(name, `${name}.comm`, "generated", "Generated from model.py and study.py: the Code_Aster commands a Solve would run now. Read-only.")
      )
    );
  }
  for (const button of dom.codeTabs.children) {
    button.setAttribute("aria-pressed", String((button.dataset.codeTab || null) === codeTab));
  }
  dom.codeGutter.hidden = codeTab !== null;
  dom.codeText.parentElement.hidden = codeTab !== null;
  dom.commText.hidden = codeTab === null;
}

function codeTabButton(tab, file, role, title) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "code-file";
  button.dataset.codeTab = tab ?? "";
  button.title = title;
  const tag = document.createElement("span");
  tag.className = `code-role code-role-${role}`;
  tag.textContent = role;
  button.append(file, tag);
  button.addEventListener("click", () => showCodeTab(tab));
  return button;
}

function showCodeTab(tab) {
  if (studio.codeTab === tab) return;
  studio.codeTab = tab;
  renderCodeTabs();
  renderCodeFoot();
  if (tab === null) {
    renderCodeMarks();
  } else {
    dom.commText.textContent = studio.available ? "Generating…" : "Loading…";
    void loadComm();
  }
}

async function loadComm() {
  const tab = studio.codeTab;
  if (tab === null) return;
  const request = ++studio.commRequest;
  let result;
  if (studio.available) {
    try {
      const response = await fetch(`/api/comm?case=${encodeURIComponent(tab)}`, { cache: "no-store" });
      result = await response.json().catch(() => ({ error: `Studio answered ${response.status}` }));
    } catch (error) {
      result = { error: error.message };
    }
  } else {
    const entry = sourceView.loadCases.find((candidate) => candidate.name === tab);
    try {
      if (!entry) throw new Error("This review ships no .comm for that load case.");
      const cached = sourceView.text.get(entry.uri);
      const code = cached ?? (await fetchBundleText(sourceView.baseUrl, entry.uri));
      if (!cached) sourceView.text.set(entry.uri, code);
      result = { ok: true, code };
    } catch (error) {
      result = { error: error.message };
    }
  }
  // A later request, or another tab, owns the pane now.
  if (request !== studio.commRequest || tab !== studio.codeTab) return;
  const { scrollTop } = dom.commText;
  dom.commText.dataset.state = result.ok ? "ready" : "error";
  dom.commText.textContent = result.ok
    ? result.code
    : studio.available
      ? `${tab}.comm could not be generated.\n\n${result.error ?? ""}`
      : `${tab}.comm is not part of this review.\n\n${result.error ?? ""}`;
  dom.commText.scrollTop = scrollTop;
}

function renderSolveControls() {
  const project = studio.project;
  const canSolve = Boolean(project?.can_solve) && !currentState.embed;
  const label = studio.solving ? "Solving…" : project?.solves ? "Solve" : "Build review";
  for (const button of [dom.solveButton, dom.reviewEmptySolve]) {
    button.hidden = !canSolve;
    button.disabled = studio.solving || studio.preparing;
    button.textContent = label;
  }
  dom.reviewEmpty.hidden = !(project && currentStage() === "review" && !studio.hasReview);
  dom.reviewEmptyText.textContent = studio.preparing
    ? "Importing the review…"
    : studio.solving
      ? "Solving model.py. The review opens here when Code_Aster finishes."
      : project?.solves
        ? "Not solved yet. Solve runs Code_Aster on model.py."
        : "No review yet.";
}

// A Code_Aster solve runs for minutes and the server emits solve_started and
// solve_finished with nothing in between, so the header said the same three
// words for the whole run: a solve in progress and a hung solve were the same
// picture. Wall-clock elapsed is the one honest signal available without a
// protocol change - it cannot say how far along a run is, but it does say the
// run is still a run.
// ponytail: wall clock only. A real fraction needs the runtime to broadcast
// per-operation progress, and a Cancel needs solve_project to hold the
// subprocess handle so it can be killed without orphaning the solve claim.
let solveClockTimer = null;

function solveElapsedLabel() {
  if (!studio.solveStartedAt) return null;
  return formatElapsed(Date.now() - studio.solveStartedAt);
}

function trackSolveClock(busy) {
  if (busy && !studio.solveStartedAt) studio.solveStartedAt = Date.now();
  if (!busy) studio.solveStartedAt = null;
  if (busy && !solveClockTimer) {
    // Redraws the chip alone; the full render is far too expensive to tick.
    solveClockTimer = setInterval(renderStatusChip, 1000);
  } else if (!busy && solveClockTimer) {
    clearInterval(solveClockTimer);
    solveClockTimer = null;
  }
}

function renderProjectStatusChip() {
  const busy = studio.solving || studio.preparing;
  trackSolveClock(busy);
  if (!studio.project.solves && !studio.reviewStale) {
    dom.statusChip.hidden = true;
    return;
  }
  const [status, alert] = studio.preparing
    ? ["preparing", "Importing the review"]
    : studio.solving
    ? ["solving", "Code_Aster is running"]
    : !studio.hasReview
      ? ["not_solved", null]
      : studio.reviewStale
        ? ["stale", "Model changed since the last solve"]
        : ["solved", null];
  dom.statusChip.hidden = false;
  const verdict = document.createElement("span");
  verdict.className = "status-badge";
  verdict.dataset.status = status;
  verdict.textContent = status.replaceAll("_", " ");
  dom.statusChip.append(verdict);
  if (alert) {
    const note = document.createElement("span");
    note.className = "status-chip-alert";
    note.textContent = alert;
    dom.statusChip.append(note);
  }
  const elapsed = busy ? solveElapsedLabel() : null;
  if (elapsed) {
    const clock = document.createElement("span");
    clock.className = "status-chip-clock";
    clock.textContent = elapsed;
    dom.statusChip.append(clock);
  }
  // The clock is deliberately left out of the label: the chip is a button, not
  // a live region, but rebuilding it every second would still leave a screen
  // reader reading a running count if it ever became one.
  dom.statusChip.setAttribute("aria-label", `Review ${status.replaceAll("_", " ")}${alert ? `, ${alert}` : ""} - show the review`);
  dom.statusChip.onclick = () => void setMode("review");
}

async function solveProject() {
  if (studio.solving || !studio.project?.can_solve) return;
  studio.solving = true;
  render();
  const response = await fetch("/api/solve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}"
  }).catch((error) => ({ ok: false, status: 0, json: async () => ({ error: error.message }) }));
  if (response.ok) return; // solve_started / solve_finished arrive over the live connection
  const result = await response.json().catch(() => ({}));
  // 409: someone else's solve is running, so the button stays busy.
  studio.solving = response.status === 409;
  setStatus(result.error ?? `Solve refused (${response.status})`, true);
  render();
}

async function handleSolveEvent(message) {
  studio.solving = message.type === "solve_started";
  studio.preparing = false;
  if (message.type === "solve_failed" || message.type === "review_failed") {
    const what = message.type === "solve_failed" ? "Solve" : "Review import";
    setStatus(`${what} failed: ${String(message.error ?? "").split("\n")[0]}`, true);
  }
  if (message.type === "solve_finished" || message.type === "review_ready") {
    studio.hasReview = true;
    studio.reviewStale = Boolean(message.review_stale);
    if (currentStage() === "review") {
      if (bundleKey(currentBundleUrl) === "review") {
        // A re-solve replaced the review on screen: reload it in place.
        try {
          await loadBundle("review", { preserve: true });
        } catch (error) {
          setStatus(error.message, true);
        }
      } else {
        await showStudioBundle("review");
      }
    }
  }
  render();
}

// One stage transition, whether a studio runs model.py or a published bundle
// shows the same pane frozen. The two used to be separate branches holding
// separate copies of which stage we were in, and they had drifted: the studio
// forced a workflow tab while the published path dispatched enterBuild, so the
// same move took two actions and only one was tested.
async function setMode(stage) {
  if (!studio.available && !sourceView.available) return;
  if (currentStage() === stage) return;
  // Only a studio has a second bundle to swap in; a published bundle shipped
  // one scene that is both the built model and the review.
  if (studio.available) {
    await showStudioBundle(stage);
  } else if (stage === "build") {
    studio.codeTab = null;
  }
  dispatch({ type: "setStage", stage });
  if (stage !== "build" && !studio.available) {
    // The review opens on what the bundle declared; leaving Build restores it
    // so the authored solid and its mesh are not both drawing at once.
    dispatch({ type: "resetLayerVisibility" });
  }
  render();
}

// Build shows the live model; Review shows the review bundle once there is one.
// Object ids match between the two, so the selection and camera carry over.
async function showStudioBundle(mode) {
  if (!studio.project) return;
  const bundle = mode === "review" && studio.hasReview ? "review" : "build";
  if (bundleKey(currentBundleUrl) === bundle) return;
  currentBundleUrl = bundle;
  const url = new URL(window.location.href);
  url.searchParams.set("bundle", bundle);
  window.history.replaceState({}, "", url);
  try {
    await loadBundle(bundle, { preserve: true });
  } catch (error) {
    setStatus(error.message, true);
  }
}

function setScriptText(code) {
  dom.codeText.value = code;
  studio.ranCode = code;
  studio.revealLine = null;
  renderGutter();
  renderCodeFoot();
}

function scriptLinesMoved() {
  // ponytail: a changed line count is the "did my line numbers move" test; an
  // edit that swaps two lines keeps the count and fools it until the next run.
  return lineCount(dom.codeText.value) !== lineCount(studio.ranCode);
}

async function runScript() {
  if (studio.running || !studio.available) return;
  studio.running = true;
  dom.codeRun.disabled = true;
  dom.codeState.textContent = "Running…";
  const code = dom.codeText.value;
  try {
    const response = await fetch("/api/script", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code })
    });
    const result = await response.json().catch(() => ({ ok: false, error: `Studio answered ${response.status}` }));
    if (!result.ok) {
      showScriptError(result);
      return;
    }
    studio.ranCode = code;
    studio.error = null;
    studio.reviewStale = Boolean(result.review_stale);
    dom.codeProblem.hidden = true;
    await loadBundle(currentBundleUrl, { preserve: true });
    render();
    const elements = Number(result.elements);
    dom.codeState.textContent = Number.isFinite(elements) ? `Ran · ${elements} element${elements === 1 ? "" : "s"}` : "Ran";
    setStatus("Ready");
  } catch (error) {
    showScriptError({ error: error.message });
  } finally {
    studio.running = false;
    dom.codeRun.disabled = false;
    renderCodeFoot();
  }
}

function showScriptError({ error, line } = {}) {
  const message = String(error ?? "model.py failed");
  studio.error = { message, line: Number.isInteger(line) && line > 0 ? line : null };
  dom.codeProblem.hidden = false;
  dom.codeProblem.textContent = studio.error.line ? `Line ${studio.error.line}: ${message}` : message;
  dom.codeState.textContent = "Failed · 3D shows the last good run";
  // The problem bar is where the error is read; the header status stays free
  // for the viewer's own trouble.
  if (studio.error.line) revealScriptLine(studio.error.line);
  renderCodeMarks();
}

// A save from another editor reruns the script on the server; the textarea
// follows unless it holds edits of its own.
async function refreshScriptFromDisk() {
  if (!studio.available || studio.running || dom.codeText.value !== studio.ranCode) return;
  try {
    const response = await fetch("/api/script", { cache: "no-store" });
    const result = response.ok ? await response.json() : null;
    if (typeof result?.code !== "string" || result.code === studio.ranCode) return;
    const { scrollTop } = dom.codeText;
    setScriptText(result.code);
    dom.codeText.scrollTop = scrollTop;
    studio.error = null;
    dom.codeProblem.hidden = true;
  } catch {
    // The scene already reloaded; an editor one save behind is the lesser problem.
  }
}

function renderGutter() {
  const count = lineCount(dom.codeText.value);
  if (dom.codeGutter.dataset.lines === String(count)) return;
  dom.codeGutter.dataset.lines = String(count);
  dom.codeGutter.textContent = Array.from({ length: count }, (_, index) => index + 1).join("\n");
}

function renderCodeFoot() {
  if (!studio.available) {
    const note = document.createElement("span");
    note.textContent = studio.codeTab === null
      ? "Shipped with this review · read-only"
      : "Generated from model.py + study.py · read-only · solver input, not results";
    dom.codeFoot.replaceChildren(note);
    return;
  }
  if (studio.codeTab !== null) {
    const note = document.createElement("span");
    note.textContent = "Generated from model.py + study.py · read-only · solver input, not results";
    dom.codeFoot.replaceChildren(note);
    return;
  }
  const text = dom.codeText;
  const saved = document.createElement("span");
  saved.textContent = text.value === studio.ranCode ? "Saved to model.py" : "Edited · Ctrl+Enter runs and saves";
  const position = document.createElement("span");
  position.textContent = `Ln ${lineAtOffset(text.value, text.selectionStart ?? 0)}`;
  const foot = [saved, position];
  if (studio.available && (studio.project?.load_cases ?? []).length === 0) {
    // Model-only project: a single model.py tab with no .comm beside it. Say why,
    // instead of leaving the missing tabs unexplained.
    const hint = document.createElement("span");
    hint.dataset.noStudyHint = "";
    hint.textContent = "No study.py load cases — add LOAD_CASES to study.py for .comm tabs and Solve";
    foot.push(hint);
  }
  dom.codeFoot.replaceChildren(...foot);
}

function renderScriptSelection() {
  if (!isBuildMode()) return;
  const object = currentState.objects.find((candidate) => candidate.id === selectedObjectId);
  const line = Number(object?.metadata?.source_line);
  studio.selectionLine = Number.isInteger(line) && line > 0 && !scriptLinesMoved() ? line : null;
  const callLine = Number(object?.metadata?.source_call_line);
  studio.callLine = studio.selectionLine && Number.isInteger(callLine) && callLine > 0 ? callLine : null;
  // A revealed line belongs to the selection its link was clicked from.
  if (studio.revealedObjectId !== (object?.id ?? null)) studio.revealLine = null;
  if (studio.selectionLine && studio.revealedObjectId !== object.id) {
    revealScriptLine(studio.selectionLine);
  }
  studio.revealedObjectId = object?.id ?? null;
  renderCodeMarks();
}

function renderCodeMarks() {
  placeCodeMark(dom.codeCallMark, studio.callLine);
  placeCodeMark(dom.codeRevealMark, studio.revealLine);
  placeCodeMark(dom.codeSelectionMark, studio.selectionLine);
  placeCodeMark(dom.codeErrorMark, studio.error?.line ?? null);
}

function placeCodeMark(mark, line) {
  mark.hidden = !line;
  if (!line) return;
  const style = getComputedStyle(dom.codeText);
  const top = parseFloat(style.paddingTop) + (line - 1) * parseFloat(style.lineHeight) - dom.codeText.scrollTop;
  mark.style.transform = `translateY(${top}px)`;
}

function revealScriptLine(line, { focus = false } = {}) {
  const text = dom.codeText;
  const lineHeight = parseFloat(getComputedStyle(text).lineHeight);
  const top = (line - 1) * lineHeight;
  if (top < text.scrollTop || top > text.scrollTop + text.clientHeight - 2 * lineHeight) {
    text.scrollTop = Math.max(0, top - text.clientHeight / 3);
  }
  dom.codeGutter.scrollTop = text.scrollTop;
  if (focus) {
    const offset = lineStartOffset(text.value, line) + /^\s*/.exec(scriptLine(text.value, line))[0].length;
    text.focus({ preventScroll: true });
    text.setSelectionRange(offset, offset);
    renderCodeFoot();
  }
  renderCodeMarks();
}

// The inspector's half of the link: the line that built the selection and, for
// a literal run length, the one number worth changing without hunting for it.
function renderScriptLink(object) {
  const section = document.createElement("section");
  section.className = "property-section script-link";
  const heading = document.createElement("h3");
  heading.textContent = "Defined by";
  section.append(heading);
  const line = Number(object.metadata?.source_line);
  if (!Number.isInteger(line) || line < 1) {
    section.append(metaLine(studio.available
      ? "Run model.py to link this to the line that builds it."
      : "This review records no source line for the selection."));
    return section;
  }
  if (scriptLinesMoved()) {
    section.append(metaLine(`model.py:${line} when last run. Lines have moved since; run again to relink.`));
    return section;
  }
  const source = scriptLine(dom.codeText.value, line);
  section.append(scriptLineButton(line, `model.py:${line}`));
  // A helper called more than once - one call per pipe copy - tells the copies apart by the call.
  const callLine = Number(object.metadata?.source_call_line);
  if (Number.isInteger(callLine) && callLine > 0) {
    section.append(scriptLineButton(callLine, `called from model.py:${callLine}`));
  }

  // A published bundle's pane is frozen: the link reveals the line, but there
  // is nothing here that could rewrite it and run.
  if (!studio.available) return section;

  const length = runLengthLiteral(source);
  if (length === null) return section;
  const row = document.createElement("label");
  row.className = "script-link-param";
  const name = document.createElement("span");
  name.textContent = "Length";
  const input = document.createElement("input");
  input.type = "number";
  input.step = "any";
  input.value = String(length);
  input.dataset.focusKey = "script-link-length";
  const unit = document.createElement("span");
  unit.className = "script-link-unit";
  unit.textContent = "m";
  input.addEventListener("change", () => {
    const next = Number(input.value);
    if (input.value === "" || !Number.isFinite(next) || next === length) {
      input.value = String(length);
      return;
    }
    // The inspector was drawn against these line numbers; typing in the
    // editor since may have moved them.
    if (scriptLinesMoved() || scriptLine(dom.codeText.value, line) !== source) {
      render();
      return;
    }
    dom.codeText.value = replaceScriptLine(dom.codeText.value, line, withRunLength(source, next));
    renderGutter();
    void runScript();
  });
  row.append(name, input, unit);
  const note = document.createElement("p");
  note.className = "script-link-note";
  note.textContent = "Changing it rewrites this line and runs model.py.";
  section.append(row, note);
  return section;
}

function scriptLineButton(line, label) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "script-link-reveal";
  button.dataset.focusKey = `script-link:${line}`;
  button.title = "Show this line in model.py";
  const where = document.createElement("span");
  where.className = "script-link-where";
  where.textContent = label;
  const code = document.createElement("code");
  code.textContent = scriptLine(dom.codeText.value, line).trim();
  button.append(where, code);
  button.addEventListener("click", () => revealLineInScript(line));
  return button;
}

function revealLineInScript(line) {
  // The link was drawn against the run's line numbers; typing since may have moved them.
  if (scriptLinesMoved()) {
    render();
    return;
  }
  studio.revealLine = line;
  showCodeTab(null); // a hidden textarea has no height to scroll to the line
  revealScriptLine(line, { focus: true });
}

// A property's half of the link: the model.py line that defines it, as a quiet
// number beside the value it explains. Build mode only, and only while the
// script's lines still match the run that recorded them; otherwise null.
function scriptLineChip(line) {
  if (!isBuildMode() || !Number.isInteger(line) || line < 1 || scriptLinesMoved()) return null;
  const chip = document.createElement("button");
  chip.type = "button";
  chip.className = "script-line-chip";
  chip.dataset.focusKey = `script-line-chip:${line}`;
  chip.textContent = `:${line}`;
  chip.title = `model.py:${line}  ${scriptLine(dom.codeText.value, line).trim()}`;
  chip.setAttribute("aria-label", `Show model.py line ${line}`);
  chip.addEventListener("click", () => revealLineInScript(line));
  return chip;
}

for (const button of dom.modeSwitch.querySelectorAll("[data-mode]")) {
  button.addEventListener("click", () => void setMode(button.dataset.mode));
}

for (const button of [dom.solveButton, dom.reviewEmptySolve]) {
  button.addEventListener("click", () => void solveProject());
}

dom.codeMeshToggle?.addEventListener("click", () => {
  if (!currentState) return;
  const meshBody = getBodies(currentState).find((candidate) => candidate.id === "analysis_mesh");
  const nextVisible = !(meshBody?.visible ?? false);
  dispatch({
    type: "setBodyVisibility",
    bodyId: "analysis_mesh",
    visible: nextVisible
  });
  dispatch({
    type: "setBodyOpacity",
    bodyId: "geometry",
    opacity: nextVisible ? 0.35 : 1.0
  });
  render();
});

dom.codeRun.addEventListener("click", () => void runScript());

// -- Script pane resize: drag the right edge; double-click resets to the default --
const CODE_PANE_MIN_PX = 300;
const CODE_PANE_WIDTH_KEY = "tuba.codePaneWidthPx";

// The width has to be set on the workspace, not the pane. The workspace's
// padding-left reserves the same --controls-width the pane is drawn at, so a
// width set on the pane alone moved the pane and left the reservation behind:
// the strip between the two showed as a band beside the viewport that never
// gave the scene any room.
function clampCodePaneWidth(px) {
  return Math.min(Math.max(Math.round(px), CODE_PANE_MIN_PX), Math.floor(window.innerWidth * 0.75));
}

function storedCodePaneWidth() {
  try {
    const stored = Number.parseInt(window.localStorage.getItem(CODE_PANE_WIDTH_KEY) ?? "", 10);
    return Number.isFinite(stored) ? clampCodePaneWidth(stored) : null;
  } catch {
    return null;
  }
}

let codePaneWidthPx = storedCodePaneWidth();

// Build only: the width is the script pane's, and Review's rail keeps its own
// default rather than taking a width dragged for a different panel.
function syncCodePaneWidth() {
  if (codePaneWidthPx != null && document.body.dataset.mode === "build") {
    dom.workspace.style.setProperty("--controls-width", `${codePaneWidthPx}px`);
  } else {
    dom.workspace.style.removeProperty("--controls-width");
  }
}

function applyCodePaneWidth(px) {
  codePaneWidthPx = clampCodePaneWidth(px);
  syncCodePaneWidth();
  try {
    window.localStorage.setItem(CODE_PANE_WIDTH_KEY, String(codePaneWidthPx));
  } catch {
    // Private browsing and the like: the drag still works for this visit.
  }
}

function resetCodePaneWidth() {
  codePaneWidthPx = null;
  syncCodePaneWidth();
  try {
    window.localStorage.removeItem(CODE_PANE_WIDTH_KEY);
  } catch {
    // Nothing persisted, nothing to clear.
  }
}

dom.codeResize.addEventListener("pointerdown", (event) => {
  if (event.button !== 0) return;
  event.preventDefault();
  dom.codeResize.setPointerCapture(event.pointerId);
  dom.codeResize.dataset.dragging = "";
  const move = (moveEvent) => {
    applyCodePaneWidth(moveEvent.clientX - dom.codePane.getBoundingClientRect().left);
  };
  const stop = () => {
    delete dom.codeResize.dataset.dragging;
    dom.codeResize.removeEventListener("pointermove", move);
    dom.codeResize.removeEventListener("pointerup", stop);
    dom.codeResize.removeEventListener("pointercancel", stop);
  };
  dom.codeResize.addEventListener("pointermove", move);
  dom.codeResize.addEventListener("pointerup", stop);
  dom.codeResize.addEventListener("pointercancel", stop);
});

dom.codeResize.addEventListener("dblclick", resetCodePaneWidth);

dom.codeText.addEventListener("input", () => {
  studio.revealLine = null;
  renderGutter();
  renderCodeFoot();
  // Redraw the inspector when its script links stop (or start again) matching the lines.
  if (scriptLinesMoved() !== studio.linesMoved) render();
  renderScriptSelection();
});

dom.codeText.addEventListener("scroll", () => {
  dom.codeGutter.scrollTop = dom.codeText.scrollTop;
  renderCodeMarks();
});

for (const type of ["click", "keyup"]) {
  dom.codeText.addEventListener(type, renderCodeFoot);
}

dom.codeText.addEventListener("focus", () => {
  studio.tabLeavesEditor = false;
});

dom.codeText.addEventListener("keydown", (event) => {
  const modifier = event.ctrlKey || event.metaKey;
  if (modifier && (event.key === "Enter" || event.key.toLowerCase() === "s")) {
    event.preventDefault();
    void runScript();
    return;
  }
  // Tab indents, so Escape is the way out: Escape, then Tab, leaves the editor.
  if (event.key === "Escape") {
    studio.tabLeavesEditor = true;
    return;
  }
  if (event.altKey && event.key.toLowerCase() === "m") {
    event.preventDefault();
    dom.codeMeshToggle?.click();
    return;
  }
  if (event.key !== "Tab" || event.shiftKey || modifier || event.altKey || studio.tabLeavesEditor) return;
  event.preventDefault();
  // insertText keeps the browser's undo history; setRangeText is the fallback.
  if (!document.execCommand("insertText", false, "    ")) {
    dom.codeText.setRangeText("    ", dom.codeText.selectionStart, dom.codeText.selectionEnd, "end");
    renderGutter();
  }
});

window.addEventListener("keydown", (event) => {
  if (event.altKey && event.key.toLowerCase() === "m" && isBuildMode()) {
    event.preventDefault();
    dom.codeMeshToggle?.click();
  }
});

main();
