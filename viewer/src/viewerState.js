import { applyTaskVisibilityPreset, getVisibleObjectIds, setLayerVisibility } from "./sceneLoader.js";
import { cycleBodyOpacity, setBodyOpacity, setBodyVisibility, setOverlayVisibility, withDefaultBodyOpacity } from "./bodies.js";
import { setUnitSystem } from "./units.js";
import { getVisibleCockpitTaskIds, setWorkflowTab } from "./workflowState.js";
import { applySectionBox, focusIssue, restoreViewState } from "./controls.js";
import { fitSelection, hideSelected, isolateSelection, restoreVisibility, selectObject } from "./selection.js";
import {
  setColoringComponent,
  setColoringField,
  setColoringLoadCase,
  withCoherentColoring
} from "./coloring.js";
import {
  coherentResultContext,
  setActiveGeometryState,
  setActiveLoadCase,
  setActiveResultState,
  setResultThreshold,
  setResultVectorScale,
  setUtilizationThreshold,
  setVisualDeformationScale
} from "./resultReview.js";

export function reduceViewerState(state, action) {
  switch (action.type) {
    case "selectObjects":
      return withVisibility({
        ...state,
        selectedObjectIds: filterExistingObjectIds(state, action.objectIds ?? [])
      });
    case "selectObject":
      return selectObject(state, action.objectId, { additive: action.additive });
    case "hideSelected":
      return hideSelected(state);
    case "isolateSelection":
      return isolateSelection(state);
    case "fitSelection":
      return fitSelection(state);
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
    case "setBodyOpacity":
      return setBodyOpacity(state, action.bodyId, action.opacity);
    case "cycleBodyOpacity":
      return cycleBodyOpacity(state, action.bodyId);
    case "setUnitSystem":
      return setUnitSystem(state, action.unitSystem);
    case "setModelColorBy":
      return { ...state, modelColorBy: action.colorBy ?? "default" };
    case "activateTask":
      return applyTaskVisibilityPreset(setWorkflowTab(state, action.tabId), action.tabId);
    case "enterBuild":
      // Build is a stage, not a task: it takes its own layer preset and leaves
      // the review's task alone, so a detour through the script returns you
      // where you were. It used to set activeTab "model" only to get past a
      // preset table keyed by task id - a tab the reader was not on, claimed
      // to satisfy a lookup. workspaceView reports no active task outside the
      // review stage, so there is nothing left to satisfy.
      return applyTaskVisibilityPreset(state, "build");
    case "resetLayerVisibility": {
      // Back from Build: every layer returns to what the bundle declared, so the
      // review the reader opened is the review they come back to.
      let declared = state;
      for (const layer of Object.values(state.layers ?? {})) {
        declared = setLayerVisibility(declared, layer.id, layer.defaultVisible !== false);
      }
      return withVisibility(declared);
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
      return setColoringField(state, action.fieldId);
    case "setColoringComponent":
      return setColoringComponent(state, action.component);
    case "setActiveGeometryState":
      return withVisibility(setActiveGeometryState(state, action.geometryStateId));
    case "setResultThreshold":
      return setResultThreshold(state, action.threshold);
    case "setUtilizationThreshold":
      return setUtilizationThreshold(state, action.threshold);
    case "setDisplacementVectorScale":
      return setResultVectorScale(state, "displacement", action.scale);
    case "setReactionVectorScale":
      return setResultVectorScale(state, "reaction", action.scale);
    case "setMomentVectorScale":
      return setResultVectorScale(state, "moment", action.scale);
    case "setVisualDeformationScale":
      return withVisibility(setVisualDeformationScale(state, action.scale));
    case "setIssueReviewStatus":
      return {
        ...state,
        issueReviewState: {
          ...(state.issueReviewState ?? {}),
          [action.issueId]: {
            ...(state.issueReviewState?.[action.issueId] ?? {}),
            status: action.status
          }
        }
      };
    case "setIssueReviewComment":
      return {
        ...state,
        issueReviewState: {
          ...(state.issueReviewState ?? {}),
          [action.issueId]: {
            ...(state.issueReviewState?.[action.issueId] ?? {}),
            comment: action.comment ?? ""
          }
        }
      };
    default:
      return state;
  }
}

export function preserveViewerStateForReload(previousState, nextState) {
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
    { ...nextState, activeGeometryStateId: retainedGeometryStateId },
    resultContext.activeLoadCase
  );
  const preserved = {
    ...nextState,
    layers,
    overlays,
    camera: previousState.camera ?? nextState.camera,
    selectedObjectIds: (previousState.selectedObjectIds ?? []).filter((id) => objectIds.has(id)),
    hiddenObjectIds: (previousState.hiddenObjectIds ?? []).filter((id) => objectIds.has(id)),
    isolatedObjectIds: (previousState.isolatedObjectIds ?? []).filter((id) => objectIds.has(id)),
    activeLoadCase: coherentState.activeLoadCase,
    activeResultStateId: resultContext.activeResultStateId ?? coherentState.activeResultStateId,
    activeGeometryStateId: coherentState.activeGeometryStateId,
    resultThreshold: previousState.resultThreshold ?? nextState.resultThreshold,
    resultVectorScales: previousState.resultVectorScales ?? nextState.resultVectorScales,
    utilizationThreshold: previousState.utilizationThreshold ?? nextState.utilizationThreshold,
    issueReviewState: previousState.issueReviewState ?? nextState.issueReviewState,
    visualDeformationScale: previousState.visualDeformationScale ?? nextState.visualDeformationScale,
    bodyOpacity: previousState.bodyOpacity ?? nextState.bodyOpacity,
    referenceGridVisible: previousState.referenceGridVisible ?? nextState.referenceGridVisible,
    unitSystem: previousState.unitSystem ?? nextState.unitSystem,
    modelColorBy: previousState.modelColorBy ?? nextState.modelColorBy ?? "default",
    activeTab: getVisibleCockpitTaskIds(nextState).includes(previousState.activeTab)
      ? previousState.activeTab
      : nextState.activeTab,
    // Carried over so a reload keeps the user's field selection, then snapped
    // back onto what the new scene actually offers.
    coloring: previousState.coloring ?? nextState.coloring,
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
