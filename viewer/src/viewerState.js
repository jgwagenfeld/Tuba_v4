import { getVisibleObjectIds, setLayerVisibility } from "./sceneLoader.js";
import { applySceneDiffToState } from "./sceneDiff.js";
import { getVisibleWorkflowTabs, setWorkflowTab } from "./workflowState.js";
import {
  coherentResultContext,
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
    case "hideObjects":
      return withVisibility({
        ...state,
        hiddenObjectIds: unique([...(state.hiddenObjectIds ?? []), ...filterExistingObjectIds(state, action.objectIds ?? [])])
      });
    case "setLayerVisibility":
      return setLayerVisibility(state, action.layerId, action.visible);
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
    case "setActiveOverlayIds":
      return { ...state, activeOverlayIds: [...(action.overlayIds ?? [])] };
    case "setWorkflowTab":
      return setWorkflowTab(state, action.tabId);
    case "setActiveResultState":
      return setActiveResultState(state, action.resultStateId);
    case "setActiveLoadCase":
      return setActiveLoadCase(state, action.loadCase);
    case "setActiveGeometryState": {
      return {
        ...state,
        activeGeometryStateId: action.geometryStateId ?? null
      };
    }
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
    case "restoreVisibility":
      return withVisibility({ ...state, hiddenObjectIds: [], isolatedObjectIds: [], sectionBox: undefined });
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
    return previous ? { ...overlay, visible: previous.visible } : overlay;
  });
  const geometryStateIds = new Set((nextState.geometryStates ?? []).map((overlay) => overlay.data?.id ?? overlay.id));
  const resultContext = coherentResultContext(previousState, nextState);
  const preserved = {
    ...nextState,
    layers,
    overlays,
    camera: previousState.camera ?? nextState.camera,
    selectedObjectIds: (previousState.selectedObjectIds ?? []).filter((id) => objectIds.has(id)),
    hiddenObjectIds: (previousState.hiddenObjectIds ?? []).filter((id) => objectIds.has(id)),
    isolatedObjectIds: (previousState.isolatedObjectIds ?? []).filter((id) => objectIds.has(id)),
    ...resultContext,
    activeGeometryStateId: geometryStateIds.has(previousState.activeGeometryStateId) ? previousState.activeGeometryStateId : nextState.activeGeometryStateId,
    displacementVectorScale: previousState.displacementVectorScale ?? nextState.displacementVectorScale,
    reactionVectorScale: previousState.reactionVectorScale ?? nextState.reactionVectorScale,
    resultThreshold: previousState.resultThreshold ?? nextState.resultThreshold,
    resultVectorScales: previousState.resultVectorScales ?? nextState.resultVectorScales,
    utilizationThreshold: previousState.utilizationThreshold ?? nextState.utilizationThreshold,
    issueReviewState: previousState.issueReviewState ?? nextState.issueReviewState,
    visualDeformationScale: previousState.visualDeformationScale ?? nextState.visualDeformationScale,
    activeTab: getVisibleWorkflowTabs(nextState).includes(previousState.activeTab)
      ? previousState.activeTab
      : nextState.activeTab,
    visibleOverlayIds: overlays.filter((overlay) => overlay.visible !== false).map((overlay) => overlay.id)
  };
  return withVisibility(preserved);
}

export function createViewerStore(initialState) {
  let state = initialState;
  const listeners = new Set();
  return {
    dispatch(action) {
      state = reduceViewerState(state, action);
      for (const listener of listeners) {
        listener(state, action);
      }
      return state;
    },
    getState() {
      return state;
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    }
  };
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
