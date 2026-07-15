import { createViewerState, getVisibleObjectIds } from "./sceneLoader.js";
import { defaultWorkflowTab, getVisibleWorkflowTabs } from "./workflowState.js";

export function applySceneDiffToState(state, diffPayload) {
  const diff = normalizeDiff(diffPayload);
  if (!diff?.diff_id || !diff.base_scene_id) {
    return { applied: false, requiresFullReload: true, reason: "invalid_scene_diff", state };
  }
  if (diff.base_scene_id !== state.sceneId) {
    return { applied: false, requiresFullReload: true, reason: "base_scene_mismatch", state };
  }

  const objects = applyObjectUpdates(state.objects ?? [], diff);
  const objectIds = new Set(objects.map((obj) => obj.id));
  const geometryAssets = pruneGeometryAssets(
    upsertRecords(state.geometryAssets ?? [], diff.added_geometry_assets ?? [], "id"),
    objectIds,
  );
  const overlays = pruneOverlayObjectRefs(upsertRecords(state.overlays ?? [], diff.updated_overlays ?? [], "id"), objectIds);
  const nextState = createViewerState({
    scene: {
      schema_version: state.schemaVersion,
      scene_id: state.sceneId,
      model_id: state.modelId,
      units: state.units ?? {},
      coordinate_system: state.coordinateSystem ?? {},
      objects,
      geometry_assets: geometryAssets,
      overlays,
      issues: upsertRecords(state.issues ?? [], diff.updated_issues ?? [], "id"),
      route_reviews: upsertRecords(state.routeReviews ?? [], diff.updated_route_reviews ?? [], "request_id"),
      agent_proposals: upsertRecords(state.agentProposals ?? [], diff.updated_agent_proposals ?? [], "proposal_id"),
      views: state.views ?? [],
      scene_diffs: [...(state.sceneDiffs ?? []), diff],
      diagnostics: [...(state.sceneDiagnostics ?? []), ...(diff.diagnostics ?? [])]
    },
    geometryPayloads: state.geometryPayloads ?? [],
    review: state.review ?? null,
    reviewDiagnostics: state.reviewDiagnostics ?? [],
    legacyReview: state.legacyReview ?? false
  });

  return {
    applied: true,
    requiresFullReload: false,
    reason: null,
    state: {
      ...preserveInteractiveState(state, nextState),
      lastSceneDiffStatus: { applied: true, requiresFullReload: false, reason: null, diffId: diff.diff_id }
    }
  };
}

function normalizeDiff(diffPayload) {
  return diffPayload?.payload ?? diffPayload?.diff ?? diffPayload?.scene_diff ?? diffPayload;
}

function applyObjectUpdates(objects, diff) {
  const removed = new Set(diff.removed_object_ids ?? []);
  const updates = new Map([...(diff.updated_objects ?? []), ...(diff.added_objects ?? [])].map((obj) => [obj.id, obj]));
  const result = objects.filter((obj) => !removed.has(obj.id)).map((obj) => updates.get(obj.id) ?? obj);
  const existing = new Set(result.map((obj) => obj.id));
  for (const obj of diff.added_objects ?? []) {
    if (!existing.has(obj.id)) {
      result.push(obj);
    }
  }
  return result;
}

function upsertRecords(records, updates, key) {
  const updateMap = new Map((updates ?? []).map((record) => [record[key], record]));
  const result = records.map((record) => updateMap.get(record[key]) ?? record);
  const existing = new Set(result.map((record) => record[key]));
  for (const update of updates ?? []) {
    if (!existing.has(update[key])) {
      result.push(update);
    }
  }
  return result;
}

function pruneGeometryAssets(assets, objectIds) {
  const result = [];
  for (const asset of assets) {
    const ids = asset.object_ids ?? [];
    if (ids.length === 0) {
      result.push(asset);
      continue;
    }
    const survivingIds = ids.filter((id) => objectIds.has(id));
    if (survivingIds.length > 0) {
      result.push({ ...asset, object_ids: survivingIds });
    }
  }
  return result;
}

function pruneOverlayObjectRefs(overlays, objectIds) {
  return overlays.map((overlay) => ({
    ...overlay,
    object_ids: (overlay.object_ids ?? []).filter((id) => objectIds.has(id))
  }));
}

function preserveInteractiveState(previousState, nextState) {
  const objectIds = new Set(nextState.objects.map((obj) => obj.id));
  const issueIds = new Set((nextState.issues ?? []).map((issue) => issue.id));
  const embed = previousState.embed ?? nextState.embed ?? false;
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
  const preserved = {
    ...nextState,
    layers,
    overlays,
    camera: previousState.camera ?? nextState.camera,
    selectedObjectIds: (previousState.selectedObjectIds ?? []).filter((id) => objectIds.has(id)),
    hiddenObjectIds: (previousState.hiddenObjectIds ?? []).filter((id) => objectIds.has(id)),
    isolatedObjectIds: (previousState.isolatedObjectIds ?? []).filter((id) => objectIds.has(id)),
    activeIssueId: issueIds.has(previousState.activeIssueId) ? previousState.activeIssueId : nextState.activeIssueId,
    activeResultStateId: previousState.activeResultStateId ?? nextState.activeResultStateId,
    activeGeometryStateId: previousState.activeGeometryStateId ?? nextState.activeGeometryStateId,
    activeLoadCase: previousState.activeLoadCase ?? nextState.activeLoadCase,
    displacementVectorScale: previousState.displacementVectorScale ?? nextState.displacementVectorScale,
    reactionVectorScale: previousState.reactionVectorScale ?? nextState.reactionVectorScale,
    resultThreshold: previousState.resultThreshold ?? nextState.resultThreshold,
    resultVectorScales: previousState.resultVectorScales ?? nextState.resultVectorScales,
    utilizationThreshold: previousState.utilizationThreshold ?? nextState.utilizationThreshold,
    issueReviewState: previousState.issueReviewState ?? nextState.issueReviewState,
    visualDeformationScale: previousState.visualDeformationScale ?? nextState.visualDeformationScale,
    embed,
    activeTab: getVisibleWorkflowTabs(nextState).includes(previousState.activeTab)
      ? previousState.activeTab
      : defaultWorkflowTab({ review: nextState.review, embed }),
    visibleOverlayIds: overlays.filter((overlay) => overlay.visible !== false).map((overlay) => overlay.id)
  };
  return { ...preserved, visibleObjectIds: getVisibleObjectIds(preserved) };
}
