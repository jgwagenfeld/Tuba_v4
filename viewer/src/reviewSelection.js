import { fitSelection, selectObject } from "./selection.js";

export function resolveEntityObjectId(state, entityRef) {
  if (typeof entityRef !== "string" || entityRef.length === 0) {
    return null;
  }
  const objects = Array.isArray(state?.objects) ? state.objects : [];
  const objectsById = new Map(objects.map((obj) => [obj.id, obj]));

  if (objectsById.has(entityRef)) {
    return entityRef;
  }

  const canonicalObjectId = `object:${entityRef}`;
  if (objectsById.has(canonicalObjectId)) {
    return canonicalObjectId;
  }

  const mappedObjectIds = mappedObjectIdsForEntity(state?.objectMap, entityRef, objectsById);
  const geometryAssetsById = new Map((state?.geometryAssets ?? []).map((asset) => [asset.id, asset]));
  const candidates = [];
  for (const obj of objects) {
    const entityMatch = obj.entity_ref === entityRef || obj.metadata?.entity_ref === entityRef;
    const mappedMatch = mappedObjectIds.has(obj.id);
    const structuredAnalysisMatch = matchesStructuredAnalysisNode(obj, entityRef, geometryAssetsById);
    if (!entityMatch && !mappedMatch && !structuredAnalysisMatch) {
      continue;
    }
    const asset = geometryAssetsById.get(obj.geometry_asset_id);
    candidates.push({
      id: obj.id,
      rank: isFallbackRepresentation(obj, asset) || structuredAnalysisMatch ? 1 : 0
    });
  }
  candidates.sort((left, right) => left.rank - right.rank || compareIds(left.id, right.id));
  return candidates[0]?.id ?? null;
}

export function getReviewEntityAction(state, entityRef) {
  const objectId = resolveEntityObjectId(state, entityRef);
  if (!objectId) {
    return null;
  }
  return {
    entityRef,
    objectId,
    accessibleName: `Show ${entityRef} in 3D`
  };
}

export function showReviewEntityIn3d(state, entityRef) {
  const objectId = resolveEntityObjectId(state, entityRef);
  if (!objectId) {
    return state;
  }
  const selected = selectObject(state, objectId);
  return fitSelection(selected);
}

function mappedObjectIdsForEntity(objectMap, entityRef, objectsById) {
  const matches = new Set();
  if (!objectMap || typeof objectMap !== "object" || Array.isArray(objectMap)) {
    return matches;
  }

  const direct = objectMap[entityRef];
  const directObjectId = typeof direct === "string"
    ? direct
    : direct?.object_id ?? direct?.objectId ?? direct?.id;
  if (objectsById.has(directObjectId)) {
    matches.add(directObjectId);
  }

  for (const [objectId, mapping] of Object.entries(objectMap)) {
    if (!objectsById.has(objectId)) {
      continue;
    }
    const mappedEntityRef = typeof mapping === "string"
      ? mapping
      : mapping?.entity_ref ?? mapping?.entityRef ?? mapping?.metadata?.entity_ref;
    if (mappedEntityRef === entityRef) {
      matches.add(objectId);
    }
  }
  return matches;
}

function matchesStructuredAnalysisNode(obj, entityRef, geometryAssetsById) {
  const prefix = "analysis_node:";
  if (!entityRef.startsWith(prefix)) {
    return false;
  }
  const memberId = entityRef.slice(prefix.length);
  if (!memberId) {
    return false;
  }
  const source = obj.source?.analysis_mesh;
  const isAnalysisNode = obj.kind === "analysis_mesh_node" || source?.member_type === "node";
  const memberMatches = obj.metadata?.member_id === memberId || source?.member_id === memberId;
  const asset = geometryAssetsById.get(obj.geometry_asset_id);
  return isAnalysisNode && memberMatches && ["point", "marker", "vector"].includes(asset?.format);
}

function isFallbackRepresentation(obj, asset) {
  const kind = String(obj.kind ?? "");
  return (
    kind.includes("analysis_mesh") ||
    kind.includes("marker") ||
    kind.endsWith("_vector") ||
    kind === "deformed_centerline" ||
    kind === "physical_envelope" ||
    ["point", "marker", "vector"].includes(asset?.format)
  );
}

function compareIds(left, right) {
  if (left === right) {
    return 0;
  }
  return left < right ? -1 : 1;
}
