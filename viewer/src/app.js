import {
  buildObjectTree,
  filterIssues,
  focusIssue,
  getIssueSummary,
  groupIssues,
  restoreViewState,
  saveViewState,
  searchObjects
} from "./controls.js";
import { applyHoverHighlight, createThreeViewport, pickRenderedObject } from "./renderer.js";
import {
  getGeometryStateOptions,
  getHotspots,
  getLoadCaseOptions,
  getResultStateOptions,
  getScalarLegend,
  setActiveGeometryState,
  setActiveLoadCase,
  setActiveResultState,
  setResultThreshold,
  setResultVectorScale,
  setUtilizationThreshold,
  setVisualDeformationScale
} from "./resultReview.js";
import { cockpitStatusViewModel, workflowViewModel } from "./reviewTables.js";
import { getReviewEntityAction, showReviewEntityIn3d } from "./reviewSelection.js";
import { applySceneDiffToState } from "./sceneDiff.js";
import { applyTaskVisibilityPreset, categorizeLayers, createViewerState, loadSceneBundleFromUrl, setLayerVisibility } from "./sceneLoader.js";
import { fitSelection, getPropertySections, hideSelected, isolateSelection, pickObjectAt, restoreVisibility, selectObject } from "./selection.js";
import { preserveViewerStateForReload, reduceViewerState } from "./viewerState.js";
import {
  WORKFLOW_TABS,
  createWorkflowState,
  evidenceTabForKey,
  evidenceTabForReload,
  getVisibleCockpitTaskIds,
  getVisibleEvidenceTabIds,
  workflowTabForKey
} from "./workflowState.js";

const dom = {
  appShell: document.querySelector("[data-embed]"),
  appHeader: document.querySelector("[data-app-header]"),
  status: document.querySelector("[data-status]"),
  sceneTitle: document.querySelector("[data-scene-title]"),
  sceneMeta: document.querySelector("[data-scene-meta]"),
  reportLink: document.querySelector("[data-report-link]"),
  cockpitStatus: document.querySelector("[data-cockpit-status]"),
  taskRail: document.querySelector("[data-task-rail]"),
  taskPanel: document.querySelector("[data-task-panel]"),
  workflowTabs: document.querySelector("[data-workflow-tabs]"),
  workflowPanel: document.querySelector("[data-workflow-panel]"),
  viewerWorkspace: document.querySelector("[data-viewer-workspace]"),
  evidenceDock: document.querySelector("[data-evidence-dock]"),
  evidenceExpand: document.querySelector("[data-evidence-expand]"),
  evidenceTabs: document.querySelector("[data-evidence-tabs]"),
  inspector: document.querySelector("[data-inspector]"),
  modelToolsHome: document.querySelector("[data-model-tools-home]"),
  issueToolsHome: document.querySelector("[data-issue-tools-home]"),
  displayStrip: document.querySelector("[data-display-strip]"),
  categorySwitches: document.querySelector("[data-category-switches]"),
  layerList: document.querySelector("[data-layer-list]"),
  resultTools: document.querySelector("[data-result-tools]"),
  resultToolsHome: document.querySelector("[data-result-tools-home]"),
  resultControls: document.querySelector("[data-result-controls]"),
  resultLegend: document.querySelector("[data-result-legend]"),
  hotspotList: document.querySelector("[data-hotspot-list]"),
  diagnosticList: document.querySelector("[data-diagnostic-list]"),
  searchInput: document.querySelector("[data-search]"),
  tree: document.querySelector("[data-tree]"),
  issueList: document.querySelector("[data-issue-list]"),
  objectList: document.querySelector("[data-object-list]"),
  savedViews: document.querySelector("[data-saved-views]"),
  properties: document.querySelector("[data-properties]"),
  propertyActions: document.querySelector("[data-property-actions]"),
  canvas: document.querySelector("[data-canvas]")
};

const startupParams = new URLSearchParams(window.location.search);
const startupConfig = Object.freeze({
  bundleUrl: startupParams.get("bundle") || "code-aster-review",
  embed: startupParams.get("embed") === "1",
  previewWebSocketUrl: startupParams.get("preview_ws")
});

let currentBundle = null;
let currentBundleUrl = ".";
let currentState = null;
let selectedObjectId = null;
let currentSearch = "";
let issueFilters = { operatingOnly: false };
let evidenceExpanded = false;
let activeEvidenceTab = "summary";
const savedViews = [];
// ponytail: dense-scene hover stays off until picking has a spatial index/BVH.
const MAX_HOVER_PICK_OBJECTS = 50;
const ORBIT_CLICK_DRAG_THRESHOLD_PX = 4;
let viewportRenderer = null;
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
  currentBundleUrl = startupConfig.bundleUrl;
  document.body.dataset.embed = String(startupConfig.embed);
  dom.appShell.dataset.embed = String(startupConfig.embed);
  try {
    setStatus(`Loading ${currentBundleUrl}`);
    await loadBundle(currentBundleUrl, { preserve: false });
    setStatus("Ready");
    render();
    if (startupConfig.previewWebSocketUrl) {
      connectLivePreview(startupConfig.previewWebSocketUrl);
    }
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function loadBundle(bundleUrl, options = {}) {
  currentBundle = await loadSceneBundleFromUrl(bundleUrl);
  const viewerState = createViewerState(currentBundle);
  const workflowState = createWorkflowState({
    review: viewerState.review,
    embed: startupConfig.embed
  });
  const nextState = { ...viewerState, ...workflowState };
  const loadedState = options.preserve && currentState ? preserveViewerStateForReload(currentState, nextState) : nextState;
  currentState = startupConfig.embed
    ? { ...loadedState, embed: true, activeTab: "3d" }
    : loadedState;
  if (!options.preserve) {
    currentState = applyTaskVisibilityPreset(currentState, currentState.activeTab);
  }
  activeEvidenceTab = evidenceTabForReload(currentState, activeEvidenceTab);
}

function render() {
  renderHeader();
  renderCockpitStatus();
  renderTaskRail();
  renderEvidenceTabs();
  renderDisplayStrip();
  renderResultControls();
  renderDiagnostics();
  renderTree();
  renderIssues();
  renderObjects();
  renderTaskPanel();
  renderProperties();
  renderWorkflow();
  renderCanvas();
}

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

function activateTask(id) {
  currentState = reduceViewerState(currentState, { type: "setWorkflowTab", tabId: id });
  currentState = applyTaskVisibilityPreset(currentState, id);
  selectedObjectId = currentState.selectedObjectIds[0] ?? selectedObjectId;
  render();
}

function renderEvidenceTabs() {
  dom.evidenceTabs.replaceChildren();
  dom.evidenceDock.hidden = currentState.embed;
  const labels = new Map([
    ["summary", "Governing Results"],
    ["diagnostics", "Warnings"],
    ["compliance", "Compliance"],
    ["reports", "Reports"]
  ]);
  const tabs = getVisibleEvidenceTabIds(currentState).map((id) => [id, labels.get(id)]);
  for (const [id, label] of tabs) {
    const button = document.createElement("button");
    button.type = "button";
    button.id = `evidence-tab-${id}`;
    button.setAttribute("role", "tab");
    button.setAttribute("aria-controls", dom.workflowPanel.id);
    button.setAttribute("aria-selected", String(id === activeEvidenceTab));
    button.tabIndex = id === activeEvidenceTab ? 0 : -1;
    button.textContent = label;
    button.addEventListener("click", () => activateEvidence(id));
    button.dataset.evidenceTab = id;
    button.addEventListener("keydown", (event) => {
      const nextId = evidenceTabForKey(currentState, id, event.key);
      if (!nextId || !dom.evidenceTabs.querySelector(`[data-evidence-tab="${nextId}"]`)) return;
      event.preventDefault();
      activateEvidence(nextId);
      dom.evidenceTabs.querySelector(`[data-evidence-tab="${nextId}"]`)?.focus();
    });
    dom.evidenceTabs.append(button);
  }
  dom.evidenceDock.classList.toggle("expanded", evidenceExpanded);
  dom.evidenceExpand.setAttribute("aria-expanded", String(evidenceExpanded));
  dom.evidenceExpand.textContent = evidenceExpanded ? "Collapse Evidence" : "Expand Evidence";
}

function activateEvidence(id) {
  if (!getVisibleEvidenceTabIds(currentState).includes(id)) return;
  activeEvidenceTab = id;
  render();
}

function renderTaskPanel() {
  dom.taskPanel.replaceChildren();
  const home = {
    model: dom.modelToolsHome,
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
      currentState = restoreViewState(currentState, view);
      selectedObjectId = currentState.selectedObjectIds[0] ?? null;
      render();
    });
    dom.savedViews.append(button);
  }
}

function renderWorkflow() {
  dom.workflowPanel.replaceChildren();
  const activeTab = activeEvidenceTab;
  dom.workflowPanel.setAttribute("aria-labelledby", `evidence-tab-${activeTab}`);
  const headingLabels = {
    summary: "Governing Results",
    diagnostics: "Warnings",
    compliance: "Compliance",
    reports: "Reports"
  };
  const heading = document.createElement("h1");
  heading.textContent = headingLabels[activeTab] ?? "Engineering review";
  dom.workflowPanel.append(heading);

  if (activeTab === "diagnostics") {
    dom.diagnosticList.hidden = false;
    dom.workflowPanel.append(dom.diagnosticList);
    return;
  }

  if (activeTab === "reports") {
    const link = document.createElement("a");
    link.className = "report-link evidence-report-link";
    link.dataset.evidenceReportLink = "";
    link.href = `${currentBundleUrl}/index.html`;
    link.textContent = "Open printable engineering report";
    dom.workflowPanel.append(link);
    return;
  }

  if (!currentState.review) {
    return;
  }
  const model = workflowViewModel(currentState.review, activeTab);
  if (model.unavailableReason) {
    const unavailable = document.createElement("p");
    unavailable.className = "workflow-unavailable";
    unavailable.textContent = model.unavailableReason;
    dom.workflowPanel.append(unavailable);
    return;
  }

  if (activeTab === "summary") {
    dom.workflowPanel.append(renderReviewOverview(currentState.review));
    for (const table of model.tables) {
      dom.workflowPanel.append(table.id === "result_summary" ? renderReviewTable(table) : renderSummaryTable(table));
    }
    return;
  }
  for (const table of model.tables) {
    dom.workflowPanel.append(renderReviewTable(table));
  }
}

function renderReviewOverview(review) {
  const overview = document.createElement("section");
  overview.className = "review-overview";
  overview.setAttribute("aria-label", "Review status and provenance");
  overview.append(
    renderOverviewCard("Analysis status", review.analysis_status, "status"),
    renderOverviewCard("Package", review.package_id ?? "Not identified"),
    renderOverviewCard("Model revision", review.model_revision ?? "Not stated"),
    renderOverviewCard("Provenance records", String(review.provenance?.length ?? 0))
  );
  return overview;
}

function renderCockpitStatus() {
  dom.cockpitStatus.replaceChildren();
  dom.cockpitStatus.hidden = currentState.embed;
  if (!currentState.review) return;
  const status = cockpitStatusViewModel(currentState.review);
  for (const [label, value] of [
    ["Analysis", status.analysisStatus],
    ["Compliance", status.complianceStatus],
    ["Governing case", status.governingLoadCase],
    ["Attention", `${status.warningCount} warning(s)`],
    [
      "Governing ratio",
      status.governingRatio === "Not available"
        ? status.governingRatio
        : `${status.governingRatio} at ${status.governingLocation}`
    ]
  ]) {
    dom.cockpitStatus.append(renderOverviewCard(label, value, label === "Analysis" ? "status" : "text"));
  }
}

function renderOverviewCard(labelText, valueText, kind = "text") {
  const card = document.createElement("article");
  card.className = "review-overview-card";
  const label = document.createElement("span");
  label.className = "review-overview-label";
  label.textContent = labelText;
  const value = document.createElement("strong");
  value.textContent = String(valueText).replaceAll("_", " ");
  if (kind === "status") {
    value.className = "status-badge";
    value.dataset.status = String(valueText);
  }
  card.append(label, value);
  return card;
}

function renderSummaryTable(model) {
  const section = document.createElement("section");
  section.className = "review-summary-card";
  const heading = document.createElement("h2");
  heading.textContent = model.title;
  section.append(heading);
  appendTableSource(section, model.source);

  if (model.rows.length === 0) {
    const empty = document.createElement("p");
    empty.textContent = model.unavailableReason ?? "No rows.";
    section.append(empty);
    return section;
  }
  for (const row of model.rows) {
    const action = getReviewEntityAction(currentState, row.entityRef);
    const values = document.createElement("dl");
    for (let index = 0; index < model.columns.length; index += 1) {
      const term = document.createElement("dt");
      term.textContent = model.columns[index].label;
      const value = document.createElement("dd");
      value.append(renderCellValue(row.cells[index]));
      values.append(term, value);
    }
    section.append(values);
    if (action) {
      section.append(createShowIn3dButton(action));
    }
  }
  return section;
}

function renderReviewTable(model) {
  const section = document.createElement("section");
  section.className = "review-table-section";
  const heading = document.createElement("h2");
  heading.textContent = model.title;
  section.append(heading);
  appendTableSource(section, model.source);

  if (model.rows.length === 0) {
    const empty = document.createElement("p");
    empty.textContent = model.unavailableReason ?? "No rows.";
    section.append(empty);
    return section;
  }

  const tableScroll = document.createElement("div");
  tableScroll.className = "review-table-scroll";
  tableScroll.tabIndex = 0;
  tableScroll.setAttribute("role", "region");
  tableScroll.setAttribute("aria-label", `${model.title} table`);
  const table = document.createElement("table");
  const head = document.createElement("thead");
  const headerRow = document.createElement("tr");
  const rowActions = model.rows.map((row) => getReviewEntityAction(currentState, row.entityRef));
  const hasActions = rowActions.some(Boolean);
  for (const column of model.columns) {
    const cell = document.createElement("th");
    cell.scope = "col";
    cell.textContent = column.label;
    if (column.description) {
      cell.title = column.description;
    }
    headerRow.append(cell);
  }
  if (hasActions) {
    const actionsHeader = document.createElement("th");
    actionsHeader.scope = "col";
    actionsHeader.textContent = "Actions";
    headerRow.append(actionsHeader);
  }
  head.append(headerRow);

  const body = document.createElement("tbody");
  for (let rowIndex = 0; rowIndex < model.rows.length; rowIndex += 1) {
    const row = model.rows[rowIndex];
    const tableRow = document.createElement("tr");
    const action = rowActions[rowIndex];
    if (action && currentState.selectedObjectIds.includes(action.objectId)) {
      tableRow.dataset.selected = "true";
    }
    if (row.entityRef) {
      tableRow.dataset.entityRef = row.entityRef;
    }
    for (const cellModel of row.cells) {
      const cell = document.createElement("td");
      cell.append(renderCellValue(cellModel));
      if (cellModel.tone) {
        cell.dataset.tone = cellModel.tone;
      }
      tableRow.append(cell);
    }
    if (hasActions) {
      const actionCell = document.createElement("td");
      if (action) {
        actionCell.append(createShowIn3dButton(action));
      }
      tableRow.append(actionCell);
    }
    body.append(tableRow);
  }
  table.append(head, body);
  tableScroll.append(table);
  section.append(tableScroll);
  return section;
}

function renderCellValue(cellModel) {
  const value = document.createElement("span");
  value.textContent = cellModel.text;
  if (cellModel.tone === "pass" || cellModel.tone === "fail") {
    value.className = "verdict";
    value.dataset.pass = String(cellModel.tone === "pass");
  } else if (["error", "warning", "info"].includes(cellModel.tone)) {
    value.className = "severity-badge";
    value.dataset.severity = cellModel.tone;
  } else if (cellModel.columnId === "analysis_status") {
    value.className = "status-badge";
    value.dataset.status = cellModel.text;
  }
  return value;
}

function createShowIn3dButton(action) {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = "Show in 3D";
  button.setAttribute("aria-label", action.accessibleName);
  button.addEventListener("click", () => showReviewEntity(action.entityRef));
  return button;
}

function showReviewEntity(entityRef) {
  const nextState = showReviewEntityIn3d(currentState, entityRef);
  if (nextState === currentState) {
    setStatus(`No 3D object is available for ${entityRef}.`);
    return;
  }
  currentState = nextState;
  selectedObjectId = currentState.selectedObjectIds[0] ?? null;
  render();
}

function appendTableSource(parent, source) {
  if (!source) {
    return;
  }
  const provenance = document.createElement("p");
  provenance.className = "meta";
  provenance.textContent = `Source: ${source}`;
  parent.append(provenance);
}

function renderResultControls() {
  dom.resultControls.replaceChildren();
  dom.resultLegend.replaceChildren();
  dom.hotspotList.replaceChildren();

  const loadCases = getLoadCaseOptions(currentState);
  const resultStates = getResultStateOptions(currentState);
  const geometryStates = getGeometryStateOptions(currentState);
  if (loadCases.length === 0 && resultStates.length === 0 && geometryStates.length === 0) {
    const empty = document.createElement("div");
    empty.className = "meta";
    empty.textContent = "No Code_Aster result overlays.";
    dom.resultControls.append(empty);
    return;
  }

  if (loadCases.length > 0) {
    dom.resultControls.append(
      selectControl("Load case", currentState.activeLoadCase ?? loadCases[0].id, loadCases, (value) => {
        currentState = setActiveLoadCase(currentState, value);
        render();
      })
    );
  }

  if (resultStates.length > 0) {
    dom.resultControls.append(
      selectControl("Result state", currentState.activeResultStateId ?? resultStates[0].id, resultStates, (value) => {
        currentState = setActiveResultState(currentState, value);
        render();
      })
    );
  }

  if (geometryStates.length > 0) {
    dom.resultControls.append(
      selectControl("Deformed state", currentState.activeGeometryStateId ?? geometryStates[0].id, geometryStates, (value) => {
        currentState = setActiveGeometryState(currentState, value);
        render();
      })
    );
  }

  dom.resultControls.append(
    numericControl("Stress threshold", currentState.resultThreshold ?? "", "1000000", (value) => {
      currentState = setResultThreshold(currentState, value);
      render();
    })
  );
  dom.resultControls.append(
    numericControl("Utilization threshold", currentState.utilizationThreshold ?? "", "0.05", (value) => {
      currentState = setUtilizationThreshold(currentState, value);
      render();
    })
  );
  dom.resultControls.append(
    rangeControl(
      `Displacement vector scale ${formatScale(currentState.resultVectorScales?.displacement ?? currentState.displacementVectorScale ?? 1)}x`,
      currentState.resultVectorScales?.displacement ?? currentState.displacementVectorScale ?? 1,
      0,
      20,
      0.5,
      (value) => {
        currentState = setResultVectorScale(currentState, "displacement", value);
        render();
      }
    )
  );
  dom.resultControls.append(
    rangeControl(
      `Reaction vector scale ${formatScale(currentState.resultVectorScales?.reaction ?? currentState.reactionVectorScale ?? 1)}x`,
      currentState.resultVectorScales?.reaction ?? currentState.reactionVectorScale ?? 1,
      0,
      5,
      0.25,
      (value) => {
        currentState = setResultVectorScale(currentState, "reaction", value);
        render();
      }
    )
  );
  dom.resultControls.append(
    rangeControl(
      `Visual deformation scale (display-only) ${formatScale(currentState.visualDeformationScale ?? 1)}x`,
      currentState.visualDeformationScale ?? 1,
      1,
      100,
      1,
      (value) => {
        currentState = setVisualDeformationScale(currentState, value);
        render();
      }
    )
  );

  const legend = getScalarLegend(currentState);
  if (legend) {
    dom.resultLegend.textContent = `${legend.field}: ${formatEngineeringValue(legend.range.min)} - ${formatEngineeringValue(legend.range.max)} ${legend.unit}`.trim();
  }

  const hotspots = getHotspots(currentState);
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
    button.textContent = `${hotspot.objectName} ${formatEngineeringValue(hotspot.value)} ${hotspot.unit}${hotspot.utilization !== null ? ` u=${formatScale(hotspot.utilization)}` : ""}`;
    button.addEventListener("click", () => {
      selectedObjectId = hotspot.objectId;
      currentState = selectObject(currentState, hotspot.objectId);
      render();
    });
    dom.hotspotList.append(button);
  }
}

function renderHeader() {
  dom.sceneTitle.textContent = currentState.review?.project_name ?? currentState.sceneId;
  dom.sceneMeta.textContent = currentState.review
    ? `${currentState.review.model_standard} · Revision ${currentState.review.model_revision} · ${currentState.review.units.length} / ${currentState.review.units.force} / ${currentState.review.units.stress}`
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

function renderObjects() {
  dom.objectList.replaceChildren();
  const sourceObjects = currentSearch ? searchObjects(currentState, currentSearch) : currentState.objects;
  for (const obj of sourceObjects) {
    if (!currentState.visibleObjectIds.includes(obj.id)) {
      continue;
    }
    const button = document.createElement("button");
    button.type = "button";
    button.className = obj.id === selectedObjectId ? "selected" : "";
    button.textContent = `${obj.name || obj.id} - ${obj.kind}`;
    button.addEventListener("click", (event) => {
      selectedObjectId = obj.id;
      currentState = selectObject(currentState, obj.id, { additive: event.shiftKey });
      render();
    });
    dom.objectList.append(button);
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
        currentState = focusIssue(currentState, issue.id);
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

function renderTree() {
  dom.tree.replaceChildren();
  const tree = buildObjectTree(currentState, { groupBy: "kind" });
  for (const group of tree.children) {
    const row = document.createElement("div");
    row.className = "tree-row";
    row.textContent = `${group.label} (${group.objectIds.length})`;
    dom.tree.append(row);
  }
}

function renderProperties() {
  const sections = getPropertySections(currentState, selectedObjectId);
  dom.propertyActions.replaceChildren();
  dom.properties.replaceChildren();
  const issueSummary = currentState.activeIssueId ? getIssueSummary(currentState, currentState.activeIssueId) : null;
  dom.inspector.hidden = sections.length === 0 && !issueSummary;
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
      void navigator.clipboard?.writeText(selectedObject.entity_ref).catch(() => {});
      setStatus(`Copied ${selectedObject.entity_ref}`);
    });
    dom.propertyActions.append(copyButton);
  }
  const fitButton = document.createElement("button");
  fitButton.type = "button";
  fitButton.textContent = "Fit selected";
  fitButton.addEventListener("click", () => {
    currentState = fitSelection(currentState);
    render();
  });
  const hideButton = document.createElement("button");
  hideButton.type = "button";
  hideButton.textContent = "Hide selected";
  hideButton.addEventListener("click", () => {
    currentState = hideSelected(currentState);
    render();
  });
  const isolateButton = document.createElement("button");
  isolateButton.type = "button";
  isolateButton.textContent = "Isolate selected";
  isolateButton.addEventListener("click", () => {
    currentState = isolateSelection(currentState);
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
    currentState = reduceViewerState(currentState, { type: "setIssueReviewStatus", issueId: issueSummary.id, status: status.value });
    render();
  });

  const comment = document.createElement("textarea");
  comment.setAttribute("aria-label", "Issue Comment");
  comment.value = issueSummary.comment ?? "";
  comment.addEventListener("change", () => {
    currentState = reduceViewerState(currentState, { type: "setIssueReviewComment", issueId: issueSummary.id, comment: comment.value });
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
    currentState = restoreVisibility(currentState);
    render();
  });

  dom.propertyActions.append(status, comment, bcfButton, restoreButton);
}

function renderCanvas() {
  viewportRenderer ??= createThreeViewport(dom.canvas);
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

dom.canvas.addEventListener("click", (event) => {
  if (suppressNextCanvasClick) {
    suppressNextCanvasClick = false;
    return;
  }
  if (!currentState) {
    return;
  }
  const rect = dom.canvas.getBoundingClientRect();
  const point = { x: event.clientX - rect.left, y: event.clientY - rect.top };
  const objectId =
    pickRenderedObject(lastRenderGraph, point, { width: rect.width, height: rect.height }) ??
    pickObjectAt(currentState, point, { width: rect.width, height: rect.height });
  if (objectId) {
    selectedObjectId = objectId;
    currentState = selectObject(currentState, objectId, { additive: event.shiftKey });
    render();
  }
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
  dom.status.textContent = message;
  dom.status.dataset.error = error ? "true" : "false";
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
    currentState = {
      ...currentState,
      diagnostics: [...(currentState.diagnostics ?? []), diagnostic]
    };
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
    const result = applySceneDiffToState(currentState, message.payload ?? message.diff ?? message.scene_diff ?? message);
    if (result.applied) {
      const diffId = (message.payload ?? message.diff ?? message.scene_diff ?? message)?.diff_id ?? null;
      currentState = {
        ...result.state,
        lastSceneDiffStatus: {
          applied: true,
          diffId
        }
      };
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
    currentState = {
      ...currentState,
      diagnostics: [
        ...(currentState.diagnostics ?? []),
        {
          severity: "warning",
          code: "visualization.scene_diff.fallback_required",
          message: result.reason ?? "SceneDiff could not be applied."
        }
      ],
      lastSceneDiffStatus: {
        applied: false,
        reason: result.reason
      }
    };
    renderDiagnostics();
    setStatus("Preview diff requires full reload", true);
    return;
  }
  if (message.type === "run_finished") {
    setStatus(message.ok === false ? "Preview run failed" : "Preview run finished", message.ok === false);
  }
}

function selectControl(labelText, value, options, onChange) {
  const label = document.createElement("label");
  const select = document.createElement("select");
  for (const option of options) {
    const normalized = typeof option === "string" ? { id: option, label: option } : option;
    const element = document.createElement("option");
    element.value = normalized.id;
    element.textContent = normalized.label;
    element.selected = normalized.id === value;
    select.append(element);
  }
  select.addEventListener("change", () => onChange(select.value));
  label.append(labelText, select);
  return label;
}

function numericControl(labelText, value, step, onChange) {
  const label = document.createElement("label");
  const input = document.createElement("input");
  input.type = "number";
  input.min = "0";
  input.step = step;
  input.value = String(value);
  input.addEventListener("change", () => onChange(input.value));
  label.append(labelText, input);
  return label;
}

function rangeControl(labelText, value, min, max, step, onChange) {
  const label = document.createElement("label");
  const input = document.createElement("input");
  input.type = "range";
  input.min = String(min);
  input.max = String(max);
  input.step = String(step);
  input.value = String(value);
  input.addEventListener("input", () => onChange(input.value));
  label.append(labelText, input);
  return label;
}

function formatEngineeringValue(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return "";
  }
  if (Math.abs(number) >= 1_000_000) {
    return number.toExponential(2);
  }
  return String(Math.round(number * 1000) / 1000);
}

function formatScale(value) {
  const number = Number(value);
  return Number.isFinite(number) ? String(Math.round(number * 1000) / 1000) : "1";
}

dom.searchInput.addEventListener("input", () => {
  currentSearch = dom.searchInput.value;
  renderObjects();
});

dom.evidenceExpand.addEventListener("click", () => {
  evidenceExpanded = !evidenceExpanded;
  renderEvidenceTabs();
});

main();
