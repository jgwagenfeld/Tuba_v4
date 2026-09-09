import { contactObjectId, contactRecords, renderContactReview } from "./contactReview.js";
import {
  buildObjectTree,
  filterIssues,
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
  createThreeViewport,
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
import {
  colorForScalarValue,
  getActiveLoadCaseDefinition,
  getGeometryStateOptions,
  getHotspots,
  getLoadCaseOptions,
  getResultStateOptions,
  getScalarLegend,
  getVisualDeformationDisplayScale
} from "./resultReview.js";
import {
  UNIT_SYSTEMS,
  displayUnit,
  formatQuantity,
  formatValue,
  getUnitSystem,
  isConvertible,
  nextUnitSystem,
  toDisplay,
  toStored
} from "./units.js";
import { cockpitStatusViewModel } from "./reviewTables.js";
import { categorizeLayers, createViewerState, loadSceneBundleFromUrl, resolveBundleId } from "./sceneLoader.js";
import { getPropertySections, pickObjectAt } from "./selection.js";
import { preserveViewerStateForReload, reduceViewerState } from "./viewerState.js";
import {
  WORKFLOW_TABS,
  createWorkflowState,
  getVisibleCockpitTaskIds,
  workflowTabForKey
} from "./workflowState.js";

const dom = {
  appShell: document.querySelector("[data-embed]"),
  appHeader: document.querySelector("[data-app-header]"),
  status: document.querySelector("[data-runtime-status]"),
  sceneTitle: document.querySelector("[data-scene-title]"),
  sceneMeta: document.querySelector("[data-scene-meta]"),
  reportLink: document.querySelector("[data-report-link]"),
  statusChip: document.querySelector("[data-status-chip]"),
  taskRail: document.querySelector("[data-task-rail]"),
  taskPanel: document.querySelector("[data-task-panel]"),
  workflowTabs: document.querySelector("[data-workflow-tabs]"),
  viewerWorkspace: document.querySelector("[data-viewer-workspace]"),
  inspector: document.querySelector("[data-inspector]"),
  issueToolsHome: document.querySelector("[data-issue-tools-home]"),
  bodiesPane: document.querySelector("[data-bodies-pane]"),
  findPane: document.querySelector("[data-find-pane]"),
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
  resultTools: document.querySelector("[data-result-tools]"),
  resultToolsHome: document.querySelector("[data-result-tools-home]"),
  resultControls: document.querySelector("[data-result-controls]"),
  resultLegend: document.querySelector("[data-result-legend]"),
  resultShape: document.querySelector("[data-result-shape]"),
  layersBlock: document.querySelector("[data-layers-block]"),
  overlaysBlock: document.querySelector("[data-overlays-block]"),
  overlayList: document.querySelector("[data-overlay-list]"),
  hotspotList: document.querySelector("[data-hotspot-list]"),
  diagnosticList: document.querySelector("[data-diagnostic-list]"),
  searchInput: document.querySelector("[data-search]"),

  issueList: document.querySelector("[data-issue-list]"),
  objectList: document.querySelector("[data-object-list]"),
  savedViews: document.querySelector("[data-saved-views]"),
  properties: document.querySelector("[data-properties]"),
  propertyActions: document.querySelector("[data-property-actions]"),
  railToggle: document.querySelector("[data-rail-toggle]"),
  resetView: document.querySelector("[data-reset-view]"),
  cameraControls: document.querySelector("[data-camera-controls]"),
  canvas: document.querySelector("[data-canvas]"),
  viewport: document.querySelector(".viewport"),
  gallery: document.querySelector("[data-gallery]"),
  galleryLink: document.querySelector("[data-gallery-link]"),
  bundlePicker: document.querySelector("[data-bundle-picker]")
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
  return currentState;
}

let selectedObjectId = null;
let currentSearch = "";
let issueFilters = { operatingOnly: false };
let railExpanded = true;
const savedViews = [];
// ponytail: dense-scene hover stays off until picking has a spatial index/BVH.
const MAX_HOVER_PICK_OBJECTS = 50;
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
globalThis.__tubaViewerPreviewEvents ??= [];

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
    if (startupConfig.previewWebSocketUrl) {
      connectLivePreview(startupConfig.previewWebSocketUrl);
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
  const viewerState = withDefaultBodyOpacity(createViewerState(currentBundle));
  const workflowState = createWorkflowState({
    review: viewerState.review,
    embed: startupConfig.embed
  });
  const nextState = { ...viewerState, ...workflowState };
  const loadedState = options.preserve && currentState ? preserveViewerStateForReload(currentState, nextState) : nextState;
  currentState = startupConfig.embed
    ? { ...loadedState, embed: true, activeTab: "3d" }
    : loadedState;
  // Deliberately NOT applying the task preset on arrival. A preset scopes the
  // view when the reviewer switches task - an explicit act. Applying it at load
  // overrode whatever the bundle declared, and because a review-less bundle
  // lands on "model" (which hides analysis_mesh and results), the composited
  // geometry/mesh/sub-point/deformed view opened with three of its four bodies
  // switched off on the very screen built to show them overlaid.
}

function render() {
  // Almost every panel is rebuilt with replaceChildren(), which destroys the
  // focused element. Without this, keyboard-toggling a body checkbox or a scope
  // chip dropped focus to <body> and the next Tab restarted from the top of the
  // document.
  const focus = captureFocus();
  renderHeader();
  renderStatusChip();
  renderTaskRail();
  renderDisplayStrip();
  renderViewportLegend();
  renderResultControls();
  renderDiagnostics();
  renderIssues();
  renderTaskPanel();
  renderProperties();
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

function renderTaskRail() {
  dom.workflowTabs.replaceChildren();
  dom.taskRail.hidden = currentState.embed || !railExpanded;
  dom.railToggle.hidden = currentState.embed;
  dom.railToggle.setAttribute("aria-expanded", String(railExpanded));
  dom.railToggle.textContent = railExpanded ? "\u2039" : "\u203a";
  dom.railToggle.title = railExpanded ? "Hide controls" : "Show controls";
  dom.railToggle.setAttribute("aria-label", dom.railToggle.title);
  document.body.dataset.railOpen = String(railExpanded);
  dom.appHeader.hidden = currentState.embed;
  for (const id of getVisibleCockpitTaskIds(currentState)) {
    const task = WORKFLOW_TABS.find((candidate) => candidate.id === id);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "task-button";
    button.dataset.task = id;
    button.dataset.focusKey = `task:${id}`;
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

function activateTask(id) {
  dispatch({ type: "activateTask", tabId: id });
  selectedObjectId = currentState.selectedObjectIds[0] ?? selectedObjectId;
  render();
}



function renderTaskPanel() {
  dom.taskPanel.replaceChildren();
  // No model home any more: Tree, Search and Objects used to live there, and the
  // bodies panel below is what the Model task actually shows.
  const home = {
    results: dom.resultToolsHome,
    diagnostics: dom.issueToolsHome
  }[currentState.activeTab];
  if (home) dom.taskPanel.append(home);
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


function renderStatusChip() {
  dom.statusChip.replaceChildren();
  dom.statusChip.hidden = currentState.embed || !currentState.review;
  if (dom.statusChip.hidden) return;
  const status = cockpitStatusViewModel(currentState.review);

  const verdict = document.createElement("span");
  verdict.className = "status-badge";
  verdict.dataset.status = String(status.analysisStatus);
  verdict.textContent = String(status.analysisStatus).replaceAll("_", " ");
  dom.statusChip.append(verdict);

  // Exceptions only. A passing or unavailable compliance verdict is not news;
  // a failing one must never be something you have to open a tab to discover.
  const alerts = [
    status.complianceStatus === "Fail" ? ["compliance", "Compliance fail"] : null,
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

  const target = alerts.length > 0 ? "diagnostics" : "summary";
  dom.statusChip.dataset.statusTarget = target;
  dom.statusChip.setAttribute(
    "aria-label",
    `Analysis ${status.analysisStatus}${alerts.length > 0 ? `, ${alerts.map(([, label]) => label).join(", ")}` : ""} - show the review tasks`
  );
  dom.statusChip.onclick = () => {
    railExpanded = true;
    const visible = getVisibleCockpitTaskIds(currentState);
    activateTask(visible.includes(target) ? target : visible[0]);
  };
}







function renderResultControls() {
  dom.resultControls.replaceChildren();
  dom.resultLegend.replaceChildren();
  dom.resultShape.replaceChildren();
  dom.hotspotList.replaceChildren();

  const contactPanel = renderContactReview(currentState, (action) => {
    dispatch(action);
    selectedObjectId = currentState.selectedObjectIds[0] ?? selectedObjectId;
  }, render);
  if (contactPanel) dom.resultControls.append(contactPanel);
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

  dom.resultControls.append(railGroup("Colouring"));
  if (fieldOptions.length > 0) {
    const field = getActiveField(currentState);
    // The one control here that keeps a full-width row: it is the longest string
    // in the rail, and every other control on the task hangs off it.
    dom.resultControls.append(
      fieldSelect(field?.id ?? fieldOptions[0].id, fieldOptions, (value) => {
        dispatch({ type: "setColoringField", fieldId: value });
        render();
      })
    );
  }
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
  if (fieldOptions.length > 0 && componentIsSelectable(currentState)) {
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
  // Only offered when the scene carries no field catalogue; with one, the field
  // selector already picks the result state through its load case. A contact
  // review names its own result state either way.
  if ((contactPanel || fieldOptions.length === 0) && resultStates.length > 0) {
    dom.resultControls.append(
      propertyRow(
        "Result state",
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
  // A contact review draws its own shape and offers no deformed state.
  if (!contactPanel && geometryStates.length > 0) {
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
  const chips = resultBodyChips();
  if (chips) {
    dom.resultShape.append(propertyRow("Draw", chips));
  }
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

// The two bodies a reviewer dims while reading a field travel with the field.
// The rest of the layer list is what the Model task is for.
const RESULT_BODY_IDS = Object.freeze(["deformed", "subpoints"]);

function resultBodyChips() {
  const bodies = getBodies(currentState).filter((body) => RESULT_BODY_IDS.includes(body.id));
  if (bodies.length === 0) {
    return null;
  }
  const row = document.createElement("div");
  row.className = "body-chips";
  for (const body of bodies) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "scope-chip body-chip";
    button.dataset.bodyChip = body.id;
    button.dataset.focusKey = `chip:${body.id}`;
    button.setAttribute("aria-pressed", String(body.visible));
    button.textContent = body.label;
    button.addEventListener("click", () => {
      dispatch({ type: "setBodyVisibility", bodyId: body.id, visible: !body.visible });
      render();
    });
    row.append(button);
  }
  return row;
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
      `Displacement vector scale ${formatScale(currentState.resultVectorScales?.displacement ?? currentState.displacementVectorScale ?? 1)}x`,
      currentState.resultVectorScales?.displacement ?? currentState.displacementVectorScale ?? 1,
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
      `Reaction vector scale ${formatScale(currentState.resultVectorScales?.reaction ?? currentState.reactionVectorScale ?? 1)}x`,
      currentState.resultVectorScales?.reaction ?? currentState.reactionVectorScale ?? 1,
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
    currentState.resultVectorScales?.displacement ?? currentState.displacementVectorScale ?? 1,
    currentState.resultVectorScales?.moment ?? 1,
    currentState.resultVectorScales?.reaction ?? currentState.reactionVectorScale ?? 1
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
  dom.sceneTitle.textContent = currentState.review?.project_name ?? currentState.sceneId;
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
  } else {
    dom.reportLink.removeAttribute("href");
  }
}

function renderDisplayStrip() {
  dom.displayStrip.hidden = currentState.embed;
  // What is drawn stays on screen whatever the task is. Hiding it on Results
  // was a workaround for the result controls being capped at 30% of the rail;
  // the cap is gone (.task-panel is flex: 0 0 auto and the strip scrolls), and
  // the cost was that the Deformed toggle vanished exactly while its own scale
  // control was on screen.
  renderBodyList();
  renderOverlayList();
  renderProjectionNote();
  renderSectionProfile();
  renderDiscretisationCheck();
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
function renderDiscretisationCheck() {
  dom.discretisationCheck.replaceChildren();
  const check = getDiscretisationCheck(currentState);
  dom.discretisationCheck.hidden = !check;
  if (!check) return;

  dom.discretisationCheck.append(stripHeading("Discretisation check"));
  dom.discretisationCheck.append(
    checkRow("Elements per bend", `${check.min_elements_per_bend}`),
    // The scene states the check in metres (check.unit); the chip decides how
    // it reads, and the tolerance is a ratio, so it never converts.
    checkRow("Chord deviation", formatQuantity(check.max_chord_deviation, check.unit, getUnitSystem(currentState)), {
      ok: check.within_tolerance,
      criterion: `≤ ${formatPercent(check.tolerance_ratio)} R`
    })
  );
  const worst = check.worst_bend;
  if (worst && check.bend_count > 1) {
    dom.discretisationCheck.append(metaLine(`worst of ${check.bend_count} bends: ${worst.source_element_id}`));
  }
}

function checkRow(labelText, valueText, verdict = null) {
  const row = document.createElement("div");
  row.className = "check-row";
  const label = document.createElement("span");
  label.className = "check-label";
  label.textContent = labelText;
  const value = document.createElement("span");
  value.className = "check-value";
  value.textContent = valueText;
  row.append(label, value);
  if (verdict) {
    const badge = document.createElement("span");
    badge.className = `check-badge ${verdict.ok ? "check-ok" : "check-warn"}`;
    // The criterion travels with the verdict: a bare "OK" invites the reader to
    // assume a code check happened.
    badge.textContent = `${verdict.ok ? "OK" : "COARSE"} ${verdict.criterion}`;
    row.append(badge);
  }
  return row;
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

// The finder. One pane, swapped into the rail beside the bodies rather than
// overlaid on it, so nothing focusable is ever hidden behind an opaque surface.
//
// It replaces three things that used to be separate: a read-only Tree grouped
// only by kind, a flat Objects list, and a search field rendered outside the
// list it filtered. The grouping the Tree could not offer is here as scope
// chips, and the search field now actually drives what is on screen.
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

let findOpen = false;
let findGroupBy = "body";

// Always renders. An early return when already open froze the result list at
// whatever the focus event had drawn, so every keystroke after the first
// changed nothing on screen.
function openFind() {
  findOpen = true;
  render();
}

function closeFind() {
  if (!findOpen) return;
  findOpen = false;
  render();
}

function renderFindPane() {
  const open = findOpen || currentSearch.trim() !== "";
  dom.findPane.hidden = !open;
  dom.bodiesPane.hidden = open;
  dom.findDismiss.hidden = !open;

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

    dom.objectList.append(groupHeader(group, members.length));
    for (const id of drawn) {
      dom.objectList.append(objectRow(byId.get(id), true));
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

function groupHeader(group, count) {
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
  header.title = "Select every object in this group";
  header.addEventListener("click", () => {
    dispatch({ type: "selectObjects", objectIds: group.objectIds });
    selectedObjectId = currentState.selectedObjectIds[0] ?? selectedObjectId;
    render();
  });
  return header;
}

function objectRow(match, drawn) {
  const object = match.object;
  const button = document.createElement("button");
  button.type = "button";
  button.className = "object-row";
  button.dataset.objectId = object.id;
  button.dataset.focusKey = `object:${object.id}`;
  // Two spans concatenate into "Smoke pipepipe - element:..." with no separator
  // in the accessible name, so state it explicitly.
  button.setAttribute("aria-label", `${object.name || object.id} - ${object.kind}`);
  if (object.id === selectedObjectId) button.classList.add("selected");
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

// The 28px slot under the mesh check. Its contents follow the pane, so the two
// states never differ in height.
function renderRailUtility(shown = 0, hidden = 0) {
  dom.railUtility.replaceChildren();
  if (dom.findPane.hidden) {
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
  } else {
    const tally = document.createElement("span");
    tally.className = "find-tally";
    tally.dataset.findTally = "";
    tally.textContent = hidden > 0 ? `${shown} drawn · ${hidden} hidden` : `${shown} of ${currentState.objects.length}`;
    dom.railUtility.append(tally);
  }
  // Pinned in the rail foot rather than a band: it restates every quantity on
  // screen at once, so it belongs to the whole rail, not to the results task.
  if (!currentState.embed) dom.railUtility.append(unitSystemChip());
}

let openPopoverId = null;
const expandedBodies = new Set();
let wallSectionOpen = false;
let bodyLegendOpen = false;

function renderRailPopover() {
  dom.railPopover.hidden = openPopoverId === null || !dom.findPane.hidden;
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


function renderProperties() {
  const sections = getPropertySections(currentState, selectedObjectId);
  dom.propertyActions.replaceChildren();
  dom.properties.replaceChildren();
  const issueSummary = currentState.activeIssueId ? getIssueSummary(currentState, currentState.activeIssueId) : null;
  // The contact panel already owns shoe details; keep the viewport available
  // when selecting its row, especially on narrow screens.
  const contactSelection = currentState.activeTab === "results" && Object.keys(contactRecords(currentState))
    .some(id => contactObjectId(currentState, id) === selectedObjectId);
  dom.inspector.hidden = contactSelection || (sections.length === 0 && !issueSummary);
  if (contactSelection) return;
  if (sections.length === 0) {
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
  const selectedObject = currentState.objects.find((obj) => obj.id === selectedObjectId);
  if (selectedObject?.entity_ref) {
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
  for (const section of sections) {
    dom.properties.append(renderPropertySection(section));
  }
  if (issueSummary) {
    dom.properties.append(renderPropertySection({ title: "Issue", rows: issueSummary }));
    appendIssueReviewActions(issueSummary);
  }
}

function renderPropertySection(section) {
  const wrapper = document.createElement("section");
  wrapper.className = "property-section";
  const heading = document.createElement("h3");
  heading.textContent = section.title;
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

  const bcfButton = document.createElement("button");
  bcfButton.type = "button";
  bcfButton.textContent = "Export BCF";
  bcfButton.addEventListener("click", () => {
    setStatus(issueSummary.bcf ? `BCF ready ${issueSummary.id}` : `BCF export path unavailable for ${issueSummary.id}`);
  });

  const restoreButton = document.createElement("button");
  restoreButton.type = "button";
  restoreButton.textContent = "Restore view";
  restoreButton.addEventListener("click", () => {
    dispatch({ type: "restoreVisibility" });
    render();
  });

  dom.propertyActions.append(status, comment, bcfButton, restoreButton);
}

function renderCanvas() {
  if (viewportUnavailable) {
    setStatus("Results ready · 3D unavailable", true);
    return;
  }
  try {
    viewportRenderer ??= createThreeViewport(dom.canvas);
  } catch (error) {
    if (error?.code !== WEBGL2_UNAVAILABLE) throw error;
    viewportUnavailable = true;
    renderViewportUnavailable();
    setStatus("Results ready · 3D unavailable", true);
    return;
  }
  renderCameraControls();
  const result = viewportRenderer.setState(currentState);
  lastRenderGraph = result;
  const objectIds = [...new Set(result.renderableObjects.flatMap((object) => object.userData.objectIds ?? []))];
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
    },
    previewEvents: [...globalThis.__tubaViewerPreviewEvents]
  };
  if (result.diagnostics.length > 0) {
    setStatus(`Ready with ${result.diagnostics.length} render warning(s)`, true);
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
  const objectId =
    pickRenderedObject(lastRenderGraph, point, { width: rect.width, height: rect.height }) ??
    pickObjectAt(currentState, point, { width: rect.width, height: rect.height });
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
    !lastRenderGraph ||
    lastRenderGraph.renderableObjects.length > MAX_HOVER_PICK_OBJECTS
  ) return;
  pendingHoverPoint = { x: event.clientX, y: event.clientY };
  if (hoverFrameId !== null) return;
  hoverFrameId = requestAnimationFrame(() => {
    hoverFrameId = null;
    if (orbiting || !pendingHoverPoint || !lastRenderGraph) return;
    const rect = dom.canvas.getBoundingClientRect();
    const objectId = pickRenderedObject(
      lastRenderGraph,
      { x: pendingHoverPoint.x - rect.left, y: pendingHoverPoint.y - rect.top },
      { width: rect.width, height: rect.height },
      { projectedFallback: false }
    );
    pendingHoverPoint = null;
    if (objectId === hoveredObjectId) return;
    hoveredObjectId = objectId;
    dom.canvas.dataset.hoverObjectId = objectId ?? "";
    applyHoverHighlight(lastRenderGraph, objectId);
    viewportRenderer.render();
  });
});

function setStatus(message, error = false) {
  const flag = error ? "true" : "false";
  // [data-runtime-status] is role="status" aria-live="polite": rewriting announces.
  // renderCanvas ends with setStatus("Ready") on every render, so without this
  // guard a screen reader said "Ready" after every checkbox, tab, slider nudge
  // and opacity click.
  if (dom.status.textContent === message && dom.status.dataset.error === flag) {
    return;
  }
  dom.status.textContent = message;
  dom.status.dataset.error = flag;
  dom.status.dataset.ready = String(!error && message === "Ready");
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
  globalThis.__tubaViewerPreviewEvents.push(message);
  if (globalThis.__tubaViewer) {
    globalThis.__tubaViewer.previewEvents = [...globalThis.__tubaViewerPreviewEvents];
  }
  if (message.type === "run_started") {
    setStatus(message.revision === undefined ? "Preview run started" : `Preview run ${message.revision} started`);
    return;
  }
  if (message.type === "diagnostic") {
    const diagnostic = message.payload ?? message.diagnostic ?? {
      severity: message.severity ?? "error",
      code: "visualization.preview.diagnostic",
      message: message.message ?? "Preview diagnostic"
    };
    dispatch({ type: "appendDiagnostic", diagnostic });
    renderDiagnostics();
    setStatus(diagnostic.message, true);
    return;
  }
  if (message.type === "scene_reloaded") {
    const bundleUrl = message.bundle_url ?? currentBundleUrl;
    currentBundleUrl = bundleUrl;
    try {
      await loadBundle(bundleUrl, { preserve: true });
      render();
      globalThis.__tubaViewerPreviewEvents = [...globalThis.__tubaViewerPreviewEvents];
      setStatus(`Preview reloaded ${message.bundle_revision ?? ""}`.trim());
    } catch (error) {
      setStatus(error.message, true);
    }
    return;
  }
  if (message.type === "scene_diff") {
    dispatch({ type: "applySceneDiff", diff: message.payload ?? message.diff ?? message.scene_diff ?? message });
    if (currentState.lastSceneDiffStatus.applied) {
      render();
      setStatus(`Preview diff applied ${message.revision ?? ""}`.trim());
      return;
    }
    if (message.bundle_url) {
      currentBundleUrl = message.bundle_url;
      try {
        await loadBundle(message.bundle_url, { preserve: true });
        render();
        setStatus(`Preview diff fallback reloaded ${message.revision ?? ""}`.trim());
      } catch (error) {
        setStatus(error.message, true);
      }
      return;
    }
    renderDiagnostics();
    setStatus("Preview diff requires full reload", true);
    return;
  }
  if (message.type === "run_finished") {
    setStatus(message.ok === false ? "Preview run failed" : "Preview run finished", message.ok === false);
  }
}

function metaLine(text) {
  const line = document.createElement("div");
  line.className = "meta";
  line.textContent = text;
  return line;
}

function stripHeading(text) {
  const heading = document.createElement("h3");
  heading.className = "strip-subheading";
  heading.textContent = text;
  return heading;
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

function fieldSelect(value, options, onChange) {
  const wrapper = document.createElement("div");
  wrapper.className = "field-select";
  const select = plainSelect(value, options, onChange);
  // The band above names the group; the control still needs a name of its own.
  select.setAttribute("aria-label", "Field");
  focusKeyFor(select, "Field");
  wrapper.append(select);
  return wrapper;
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
  renderTaskRail();
});

main();
