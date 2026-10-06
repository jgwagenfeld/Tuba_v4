import { applyResultFieldPreset, applyStageVisibilityPreset, getVisibleObjectIds, setLayerVisibility } from "./sceneLoader.js";
import {
  cycleBodyOpacity,
  cycleSubpointMode,
  cycleSubpointNodeId,
  cycleSubpointThreshold,
  getBodies,
  setBodyOpacity,
  setBodyVisibility,
  setOverlayVisibility,
  setSubpointMode,
  setSubpointNodeId,
  withDefaultBodyOpacity
} from "./bodies.js";
import { setUnitSystem } from "./units.js";
import { applySectionBox, focusIssue, restoreViewState } from "./controls.js";
import {
  fitSelection,
  findingFitSpan,
  focusFinding,
  hideSelected,
  isolateSelection,
  restoreVisibility,
  selectObject
} from "./selection.js";
import { recordDisposition } from "./reviewRecord.js";
import {
  setColoringComponent,
  setColoringField,
  setColoringLoadCase,
  withCoherentColoring
} from "./coloring.js";
import {
  coherentResultContext,
  setActiveFinding,
  setActiveGeometryState,
  setActiveLoadCase,
  setActiveResultState,
  setLegendBands,
  setLegendRange,
  resetLegendScale,
  setResultThreshold,
  setResultVectorScale,
  setUtilizationThreshold,
  setVisualDeformationScale
} from "./resultReview.js";

// The Build "FE mesh" button and Alt+M. Visibility only: Geometry opacity is
// the reviewer's own setting, and pressing the toggle twice used to leave it at
// 100 % whatever it was before. Mesh view shows what the solver received and
// nothing else - 1D lines, shells, solids - so showing it takes the same route
// as "View solved FE mesh" and hiding it brings the geometry back. It used to
// keep the geometry for line and mixed models, where the opaque pipes buried
// the centreline mesh.
function toggleFeMesh(state) {
  const showing = !(getBodies(state).find((body) => body.id === "analysis_mesh")?.visible ?? false);
  if (showing) return reduceViewerState(state, { type: "showAnalysisMesh" });
  return setBodyVisibility(setBodyVisibility(state, "analysis_mesh", false), "geometry", true);
}

export function reduceViewerState(state, action) {
  switch (action.type) {
    case "selectObjects":
      return withVisibility({
        ...state,
        selectedObjectIds: filterExistingObjectIds(state, action.objectIds ?? [])
      });
    case "selectObject":
      return selectObject(state, action.objectId, { additive: action.additive });
    case "setSourceMeshVisible": {
      const object = state.objects.find(candidate => candidate.id === action.objectId);
      const asset = state.geometryAssets.find(candidate => candidate.id === object?.geometry_asset_id);
      if (object?.kind !== "imported_component" || asset?.format !== "mesh" ||
          object.metadata?.geometry_representation === "bounds_envelope") return state;
      const ids = new Set(state.sourceMeshObjectIds ?? []);
      action.visible ? ids.add(object.id) : ids.delete(object.id);
      return { ...state, sourceMeshObjectIds: [...ids] };
    }
    // The F = / q = / μ = badges on loads and supports. Visibility only: the
    // renderer hides the sprites it already built, so no graph rebuild.
    case "setValueLabelsVisible":
      return { ...state, valueLabelsVisible: Boolean(action.visible) };
    case "setInterfaceMappingsVisible":
      return withVisibility({ ...state, interfaceMappingsVisible: Boolean(action.visible) });
    case "hideSelected":
      return hideSelected(state);
    case "setFocusSelection":
      return { ...state, focusSelection: Boolean(action.enabled) };
    case "isolateSelection":
      return isolateSelection(state);
    case "fitSelection":
      return fitSelection(state, { maxSpan: action.maxSpan });
    case "restoreVisibility":
      return restoreVisibility(state);
    case "applySectionBox":
      return applySectionBox(state, action.sectionBox);
    case "restoreViewState":
      return restoreViewState(state, action.view);
    case "focusIssue":
      return focusIssue(state, action.issueId);
    case "setLayerVisibility":
      return setLayerVisibility(state, action.layerId, action.visible);
    case "setOverlayVisibility":
      return setOverlayVisibility(state, action.overlayId, action.visible);
    case "setBodyVisibility":
      return setBodyVisibility(state, action.bodyId, action.visible);
    case "showAnalysisMesh":
      return {
        ...setBodyVisibility(setBodyVisibility(restoreVisibility(state), "analysis_mesh", true), "geometry", false),
        colorChannel: "model"
      };
    case "toggleFeMesh":
      return toggleFeMesh(state);
    case "setBodyOpacity":
      return setBodyOpacity(state, action.bodyId, action.opacity);
    case "cycleBodyOpacity":
      return cycleBodyOpacity(state, action.bodyId);
    case "cycleSubpointMode":
      return cycleSubpointMode(state);
    case "setSubpointMode":
      return setSubpointMode(state, action.mode);
    case "cycleSubpointThreshold":
      return cycleSubpointThreshold(state);
    case "setSubpointNodeId":
      return setSubpointNodeId(state, action.nodeId);
    case "cycleSubpointNodeId":
      return cycleSubpointNodeId(state);
    case "setUnitSystem":
      return setUnitSystem(state, action.unitSystem);
    case "setModelColorBy":
      // Picking a model property colour is choosing the model channel.
      return applyResultFieldPreset({ ...state, modelColorBy: action.colorBy ?? "default", colorChannel: "model" });
    case "setColorChannel":
      // The selector's own channel action, for a legacy scene whose results are
      // a solver overlay with no field catalogue to name.
      return applyResultFieldPreset({ ...state, colorChannel: action.colorChannel ?? state.colorChannel });
    case "setStage": {
      // A stage change, not a rail change: the stage picks the layer preset.
      // This used to be "enterBuild", which also forced a workflow tab - a
      // "build" entry in a table keyed by task id.
      //
      // Only Build has a preset; entering Review applies none, so the review is
      // drawn as the bundle declared it.
      return withVisibility(applyStageVisibilityPreset({ ...state, stage: action.stage }, action.stage));
    }
    case "resetLayerVisibility": {
      // Back from Build: every layer returns to what the bundle declared, so the
      // review the reader opened is the review they come back to.
      let declared = state;
      for (const layer of Object.values(state.layers ?? {})) {
        declared = setLayerVisibility(declared, layer.id, layer.defaultVisible !== false);
      }
      return withVisibility(applyResultFieldPreset(declared));
    }
    case "setContactNeutral":
      return withVisibility({ ...state, contactNeutral: action.neutral });
    case "setContactArrows":
      return { ...state, contactArrows: { ...state.contactArrows, [action.quantity]: action.visible } };
    case "setContactHistoryAxis":
      return { ...state, contactHistoryAxis: action.axis };
    case "setActiveResultState":
      return withVisibility(withCoherentColoring(setActiveResultState(state, action.resultStateId)));
    case "setActiveLoadCase":
      return withVisibility(setColoringLoadCase(setActiveLoadCase(state, action.loadCase), action.loadCase));
    case "setColoringField":
      return applyResultFieldPreset(setColoringField(state, action.fieldId));
    case "setColoringComponent":
      return setColoringComponent(state, action.component);
    case "setActiveGeometryState":
      return withVisibility(setActiveGeometryState(state, action.geometryStateId));
    case "setResultThreshold":
      return setResultThreshold(state, action.threshold);
    case "setUtilizationThreshold":
      return setUtilizationThreshold(state, action.threshold);
    case "setLegendBands":
      return setLegendBands(state, action.bands, action.scaleKey);
    case "setLegendRange":
      return setLegendRange(state, action.range, action.scaleKey);
    case "resetLegendScale":
      return resetLegendScale(state, action.scaleKey);
    case "setActiveFinding":
      return setActiveFinding(state, action.objectId);
    case "focusFinding":
      return focusFinding(state, action.objectId);
    case "setRunDiagramRun":
      return { ...state, runDiagramRunId: action.runId ?? null };
    case "setRunDiagramComponent":
      return { ...state, runDiagramComponent: action.component ?? null };
    case "setDisplacementVectorScale":
      return setResultVectorScale(state, "displacement", action.scale);
    case "setReactionVectorScale":
      return setResultVectorScale(state, "reaction", action.scale);
    case "setMomentVectorScale":
      return setResultVectorScale(state, "moment", action.scale);
    case "setVisualDeformationScale":
      return withVisibility(setVisualDeformationScale(state, action.scale));
    case "setIssueReviewStatus":
      // Routed through the record so a status set from the old inspector path
      // gets attribution and history too, rather than overwriting a bare field.
      return recordDisposition(state, {
        issueId: action.issueId,
        status: action.status,
        author: state.reviewerName ?? null,
        at: action.at ?? null
      });
    case "setIssueReviewComment":
      return recordDisposition(state, {
        issueId: action.issueId,
        comment: action.comment ?? "",
        author: state.reviewerName ?? null,
        at: action.at ?? null
      });
    case "recordDisposition":
      return recordDisposition(state, { ...action, author: action.author ?? state.reviewerName ?? null });
    case "setReviewerName":
      return { ...state, reviewerName: String(action.name ?? "").trim() || null };
    default:
      return state;
  }
}

export function preserveViewerStateForReload(previousState, nextState, { reviewDefaultColor = false } = {}) {
  const objectIds = new Set(nextState.objects.map((obj) => obj.id));
  const layers = { ...nextState.layers };
  for (const [id, previousLayer] of Object.entries(previousState.layers ?? {})) {
    if (layers[id]) {
      layers[id] = { ...layers[id], visible: previousLayer.visible };
    }
  }
  const overlays = (nextState.overlays ?? []).map((overlay) => {
    const previous = (previousState.overlays ?? []).find((candidate) => candidate.id === overlay.id);
    if (previous) {
      return { ...overlay, visible: previous.visible };
    }
    const overlayLayer = layers[`overlay:${overlay.kind || "overlay"}`];
    return overlayLayer ? { ...overlay, visible: overlayLayer.visible } : overlay;
  });
  const geometryStateIds = new Set((nextState.geometryStates ?? []).map((overlay) => overlay.data?.id ?? overlay.id));
  const resultContext = coherentResultContext(previousState, nextState);
  const retainedGeometryStateId = geometryStateIds.has(previousState.activeGeometryStateId)
    ? previousState.activeGeometryStateId
    : nextState.activeGeometryStateId;
  const coherentState = setActiveLoadCase(
    { ...nextState, activeResultStateId: resultContext.activeResultStateId, activeGeometryStateId: retainedGeometryStateId },
    resultContext.activeLoadCase
  );
  const preserved = {
    ...nextState,
    layers,
    overlays,
    camera: previousState.camera ?? nextState.camera,
    selectedObjectIds: (previousState.selectedObjectIds ?? []).filter((id) => objectIds.has(id)),
    interfaceMappingsVisible: previousState.interfaceMappingsVisible ?? true,
    sourceMeshObjectIds: (previousState.sourceMeshObjectIds ?? []).filter(id =>
      nextState.objects.some(object => object.id === id && object.kind === "imported_component" &&
        object.metadata?.geometry_representation !== "bounds_envelope")),
    hiddenObjectIds: (previousState.hiddenObjectIds ?? []).filter((id) => objectIds.has(id)),
    isolatedObjectIds: (previousState.isolatedObjectIds ?? []).filter((id) => objectIds.has(id)),
    activeLoadCase: coherentState.activeLoadCase,
    activeResultStateId: resultContext.activeResultStateId ?? coherentState.activeResultStateId,
    activeGeometryStateId: coherentState.activeGeometryStateId,
    resultThreshold: previousState.resultThreshold ?? nextState.resultThreshold,
    resultVectorScales: previousState.resultVectorScales ?? nextState.resultVectorScales,
    utilizationThreshold: previousState.utilizationThreshold ?? nextState.utilizationThreshold,
    reviewDispositions: previousState.reviewDispositions ?? nextState.reviewDispositions,
    visualDeformationScale: previousState.visualDeformationScale ?? nextState.visualDeformationScale,
    bodyOpacity: previousState.bodyOpacity ?? nextState.bodyOpacity,
    referenceGridVisible: previousState.referenceGridVisible ?? nextState.referenceGridVisible,
    valueLabelsVisible: previousState.valueLabelsVisible ?? nextState.valueLabelsVisible,
    unitSystem: previousState.unitSystem ?? nextState.unitSystem,
    modelColorBy: reviewDefaultColor ? nextState.modelColorBy : previousState.modelColorBy ?? nextState.modelColorBy ?? "default",
    // Which channel tints the scene is the reader's choice, so a reload keeps it.
    colorChannel: reviewDefaultColor ? nextState.colorChannel : previousState.colorChannel ?? nextState.colorChannel,
    stage: previousState.stage ?? nextState.stage,
    // Carried over so a reload keeps the user's field selection, then snapped
    // back onto what the new scene actually offers.
    coloring: reviewDefaultColor ? nextState.coloring : previousState.coloring ?? nextState.coloring,
    visibleOverlayIds: overlays.filter((overlay) => overlay.visible !== false).map((overlay) => overlay.id)
  };
  return withDefaultBodyOpacity(withVisibility(withCoherentColoring(preserved)));
}

function withVisibility(state) {
  return { ...state, visibleObjectIds: getVisibleObjectIds(state) };
}

function filterExistingObjectIds(state, objectIds) {
  const existing = new Set(state.objects.map((obj) => obj.id));
  return unique(objectIds.filter((id) => existing.has(id)));
}

function unique(values) {
  return [...new Set(values)];
}
