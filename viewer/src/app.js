import {
  buildObjectTree,
  filterIssues,
  focusIssue,
  getIssueSummary,
  groupIssues,
  searchObjects,
  setOverlayVisibility
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
import { workflowViewModel } from "./reviewTables.js";
import { getReviewEntityAction, showReviewEntityIn3d } from "./reviewSelection.js";
import { applySceneDiffToState } from "./sceneDiff.js";
import { createViewerState, loadSceneBundleFromUrl, setLayerVisibility } from "./sceneLoader.js";
import { fitSelection, getPropertySections, hideSelected, isolateSelection, pickObjectAt, restoreVisibility, selectObject } from "./selection.js";
import { preserveViewerStateForReload, reduceViewerState } from "./viewerState.js";
import { WORKFLOW_TABS, createWorkflowState, getVisibleWorkflowTabs, workflowTabForKey } from "./workflowState.js";

const dom = {
  appShell: document.querySelector("[data-embed]"),
  appHeader: document.querySelector("[data-app-header]"),
  status: document.querySelector("[data-status]"),
  sceneTitle: document.querySelector("[data-scene-title]"),
  sceneMeta: document.querySelector("[data-scene-meta]"),
  workflowTabs: document.querySelector("[data-workflow-tabs]"),
  workflowPanel: document.querySelector("[data-workflow-panel]"),
  viewerWorkspace: document.querySelector("[data-viewer-workspace]"),
  layerList: document.querySelector("[data-layer-list]"),
  overlayList: document.querySelector("[data-overlay-list]"),
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
  properties: document.querySelector("[data-properties]"),
  propertyActions: document.querySelector("[data-property-actions]"),
  canvas: document.querySelector("[data-canvas]")
};

let currentBundle = null;
let currentBundleUrl = ".";
let currentState = null;
let selectedObjectId = null;
let currentSearch = "";
let issueFilters = { operatingOnly: false };
let viewportRenderer = null;
let lastRenderGraph = null;
let hoveredObjectId = null;
const bootId = globalThis.__tubaViewerBootId ?? `boot:${Date.now()}:${Math.random().toString(16).slice(2)}`;
globalThis.__tubaViewerBootId = bootId;
globalThis.__tubaViewerPreviewEvents ??= [];

async function main() {
  const params = new URLSearchParams(window.location.search);
  currentBundleUrl = params.get("bundle") || ".";
  const embed = params.get("embed") === "1";
  if (embed) {
    document.body.dataset.embed = "true";
  }
  dom.appShell.dataset.embed = String(embed);
  try {
    setStatus(`Loading ${currentBundleUrl}`);
    await loadBundle(currentBundleUrl, { preserve: false, embed });
    setStatus("Ready");
    render();
    if (params.get("preview_ws")) {
      connectLivePreview(params.get("preview_ws"));
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
    embed: options.embed ?? currentState?.embed ?? false
  });
  const nextState = { ...viewerState, ...workflowState };
  currentState = options.preserve && currentState ? preserveViewerStateForReload(currentState, nextState) : nextState;
}

function render() {
  renderHeader();
  renderWorkflowTabs();
  renderLayers();
  renderOverlays();
  renderResultControls();
  renderDiagnostics();
  renderTree();
  renderIssues();
  renderObjects();
  renderProperties();
  renderWorkflow();
  renderCanvas();
}

function renderWorkflowTabs() {
  dom.workflowTabs.replaceChildren();
  dom.workflowTabs.hidden = currentState.embed;
  dom.appHeader.hidden = currentState.embed;
  const visibleTabs = new Set(getVisibleWorkflowTabs(currentState));
  for (const tab of WORKFLOW_TABS) {
    if (!visibleTabs.has(tab.id)) {
      continue;
    }
    const button = document.createElement("button");
    button.type = "button";
    button.id = `workflow-tab-${tab.id}`;
    button.setAttribute("role", "tab");
    button.setAttribute("aria-controls", tab.id === "3d" ? dom.viewerWorkspace.id : dom.workflowPanel.id);
    button.setAttribute("aria-selected", String(tab.id === currentState.activeTab));
    button.tabIndex = tab.id === currentState.activeTab ? 0 : -1;
    button.textContent = tab.label;
    button.addEventListener("click", () => {
      currentState = reduceViewerState(currentState, { type: "setWorkflowTab", tabId: tab.id });
      render();
    });
    button.addEventListener("keydown", (event) => {
      const nextTabId = workflowTabForKey(currentState, tab.id, event.key);
      if (!nextTabId) {
        return;
      }
      event.preventDefault();
      currentState = reduceViewerState(currentState, { type: "setWorkflowTab", tabId: nextTabId });
      render();
      document.getElementById(`workflow-tab-${nextTabId}`)?.focus();
    });
    dom.workflowTabs.append(button);
  }
}

function renderWorkflow() {
  dom.workflowPanel.replaceChildren();
  dom.resultToolsHome.append(dom.resultTools);
  dom.diagnosticList.hidden = true;
  dom.appShell.append(dom.diagnosticList);

  const activeTab = currentState.activeTab;
  const isThreeDimensional = activeTab === "3d";
  dom.viewerWorkspace.hidden = !isThreeDimensional;
  dom.workflowPanel.hidden = isThreeDimensional || currentState.embed;
  if (isThreeDimensional || currentState.embed) {
    dom.workflowPanel.removeAttribute("aria-labelledby");
    return;
  }

  dom.workflowPanel.setAttribute("aria-labelledby", `workflow-tab-${activeTab}`);
  const tab = WORKFLOW_TABS.find((candidate) => candidate.id === activeTab);
  const heading = document.createElement("h1");
  heading.textContent = tab?.label ?? "Engineering review";
  dom.workflowPanel.append(heading);

  if (activeTab === "results" || activeTab === "load-cases") {
    dom.workflowPanel.append(dom.resultTools);
  }
  if (activeTab === "diagnostics") {
    dom.diagnosticList.hidden = false;
    dom.workflowPanel.append(dom.diagnosticList);
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
    for (const table of model.tables) {
      dom.workflowPanel.append(renderSummaryTable(table));
    }
    return;
  }
  for (const table of model.tables) {
    dom.workflowPanel.append(renderReviewTable(table));
  }
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
      value.textContent = row.cells[index].text;
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
    if (row.entityRef) {
      tableRow.dataset.entityRef = row.entityRef;
    }
    for (const cellModel of row.cells) {
      const cell = document.createElement("td");
      cell.textContent = cellModel.text;
      if (cellModel.tone) {
        cell.dataset.tone = cellModel.tone;
      }
      tableRow.append(cell);
    }
    if (hasActions) {
      const actionCell = document.createElement("td");
      const action = rowActions[rowIndex];
      if (action) {
        actionCell.append(createShowIn3dButton(action));
      }
      tableRow.append(actionCell);
    }
    body.append(tableRow);
  }
  table.append(head, body);
  section.append(table);
  return section;
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
  dom.sceneTitle.textContent = currentState.sceneId;
  dom.sceneMeta.textContent = `${currentState.objects.length} objects | ${currentState.issues.length} issues`;
}

function renderLayers() {
  dom.layerList.replaceChildren();
  for (const layer of Object.values(currentState.layers)) {
    const label = document.createElement("label");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = layer.visible;
    input.addEventListener("change", () => {
      currentState = setLayerVisibility(currentState, layer.id, input.checked);
      render();
    });
    label.append(input, ` ${layer.label} (${layer.count})`);
    dom.layerList.append(label);
  }
}

function renderOverlays() {
  dom.overlayList.replaceChildren();
  const overlays = currentState.overlays ?? [];
  if (overlays.length === 0) {
    const empty = document.createElement("div");
    empty.className = "meta";
    empty.textContent = "No overlays.";
    dom.overlayList.append(empty);
    return;
  }
  for (const overlay of overlays) {
    const label = document.createElement("label");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = overlay.visible !== false;
    input.addEventListener("change", () => {
      currentState = setOverlayVisibility(currentState, overlay.id, input.checked);
      render();
    });
    label.append(input, ` ${overlay.name || overlay.id}`);
    dom.overlayList.append(label);
  }
}

function renderDiagnostics() {
  dom.diagnosticList.replaceChildren();
  const diagnostics = [
    ...(currentState.diagnostics ?? []),
    ...(currentState.reviewDiagnostics ?? []),
    ...(currentState.review?.diagnostics ?? [])
  ];
  if (diagnostics.length === 0) {
    const empty = document.createElement("div");
    empty.className = "meta";
    empty.textContent = "No diagnostics.";
    dom.diagnosticList.append(empty);
    return;
  }
  for (const diagnostic of diagnostics) {
    const row = document.createElement("div");
    row.className = "tree-row";
    row.textContent = `${diagnostic.severity || "info"} - ${diagnostic.code || "diagnostic"}: ${diagnostic.message || "No detail supplied."}`;
    dom.diagnosticList.append(row);
  }
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

dom.canvas.addEventListener("mousemove", (event) => {
  if (!currentState || !lastRenderGraph) {
    return;
  }
  const rect = dom.canvas.getBoundingClientRect();
  const objectId = pickRenderedObject(
    lastRenderGraph,
    { x: event.clientX - rect.left, y: event.clientY - rect.top },
    { width: rect.width, height: rect.height }
  );
  if (objectId === hoveredObjectId) {
    return;
  }
  hoveredObjectId = objectId;
  dom.canvas.dataset.hoverObjectId = objectId ?? "";
  applyHoverHighlight(lastRenderGraph, objectId);
  viewportRenderer.render();
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

main();
