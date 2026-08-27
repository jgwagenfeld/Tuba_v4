import { applyTaskVisibilityPreset, getVisibleObjectIds, setLayerVisibility } from "./sceneLoader.js";
import { cycleBodyOpacity, setBodyVisibility, withDefaultBodyOpacity } from "./bodies.js";
import { setUnitSystem } from "./units.js";
import { applySceneDiffToState } from "./sceneDiff.js";
import { getVisibleWorkflowTabs, setWorkflowTab } from "./workflowState.js";
import { applySectionBox, focusIssue, restoreViewState } from "./controls.js";
import { hideSelected, isolateSelection, restoreVisibility, selectObject } from "./selection.js";
import { showReviewEntityIn3d } from "./reviewSelection.js";
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
    case "restoreVisibility":
      return restoreVisibility(state);
    case "applySectionBox":
      return applySectionBox(state, action.sectionBox);
    case "restoreViewState":
      return restoreViewState(state, action.view);
    case "focusIssue":
      return focusIssue(state, action.issueId);
    case "showReviewEntityIn3d":
      return showReviewEntityIn3d(state, action.entityRef);
    case "setLayerVisibility":
      return setLayerVisibility(state, action.layerId, action.visible);
    case "setBodyVisibility":
      return setBodyVisibility(state, action.bodyId, action.visible);
    case "cycleBodyOpacity":
      return cycleBodyOpacity(state, action.bodyId);
    case "setUnitSystem":
      return setUnitSystem(state, action.unitSystem);
    case "applySceneDiff": {
      const result = applySceneDiffToState(state, action.diff ?? action.sceneDiff);
      if (result.applied) {
        return {
          ...result.state,
          lastSceneDiffStatus: {
            applied: true,
            diffId: (action.diff ?? action.sceneDiff)?.diff_id ?? null
          }
        };
      }
      return {
        ...state,
        diagnostics: [
          ...(state.diagnostics ?? []),
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
    }
    case "activateTask":
      return applyTaskVisibilityPreset(setWorkflowTab(state, action.tabId), action.tabId);
    case "setWorkflowTab":
      return setWorkflowTab(state, action.tabId);
    case "setActiveResultState":
      return setActiveResultState(state, action.resultStateId);
    case "setActiveLoadCase":
      return setColoringLoadCase(setActiveLoadCase(state, action.loadCase), action.loadCase);
    case "setColoringField":
      return setColoringField(state, action.fieldId);
    case "setColoringComponent":
      return setColoringComponent(state, action.component);
    case "setActiveGeometryState":
      return setActiveGeometryState(state, action.geometryStateId);
    case "setResultThreshold":
      return setResultThreshold(state, action.threshold);
    case "setUtilizationThreshold":
      return setUtilizationThreshold(state, action.threshold);
    case "setDisplacementVectorScale":
      return setResultVectorScale(state, "displacement", action.scale);
    case "setReactionVectorScale":
      return setResultVectorScale(state, "reaction", action.scale);
    case "setVisualDeformationScale":
      return setVisualDeformationScale(state, action.scale);
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
    case "appendDiagnostic":
      return { ...state, diagnostics: [...(state.diagnostics ?? []), action.diagnostic] };
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
    displacementVectorScale: previousState.displacementVectorScale ?? nextState.displacementVectorScale,
    reactionVectorScale: previousState.reactionVectorScale ?? nextState.reactionVectorScale,
    resultThreshold: previousState.resultThreshold ?? nextState.resultThreshold,
    resultVectorScales: previousState.resultVectorScales ?? nextState.resultVectorScales,
    utilizationThreshold: previousState.utilizationThreshold ?? nextState.utilizationThreshold,
    issueReviewState: previousState.issueReviewState ?? nextState.issueReviewState,
    visualDeformationScale: previousState.visualDeformationScale ?? nextState.visualDeformationScale,
    bodyOpacity: previousState.bodyOpacity ?? nextState.bodyOpacity,
    unitSystem: previousState.unitSystem ?? nextState.unitSystem,
    activeTab: getVisibleWorkflowTabs(nextState).includes(previousState.activeTab)
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
