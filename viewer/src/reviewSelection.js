import { fitSelection, selectObject } from "./selection.js";

export function resolveEntityObjectId(state, entityRef) {
  if (typeof entityRef !== "string" || entityRef.length === 0) {
    return null;
  }
  const objects = Array.isArray(state?.objects) ? state.objects : [];
  const objectIds = new Set(objects.map((obj) => obj.id));

  if (objectIds.has(entityRef)) {
    return entityRef;
  }

  const mappedObjectId = resolveFromObjectMap(state?.objectMap, entityRef, objectIds);
  if (mappedObjectId) {
    return mappedObjectId;
  }

  return objects.find((obj) => obj.entity_ref === entityRef || obj.metadata?.entity_ref === entityRef)?.id ?? null;
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
  return fitSelection({ ...selected, activeTab: "3d" });
}

function resolveFromObjectMap(objectMap, entityRef, objectIds) {
  if (!objectMap || typeof objectMap !== "object" || Array.isArray(objectMap)) {
    return null;
  }

  const direct = objectMap[entityRef];
  const directObjectId = typeof direct === "string"
    ? direct
    : direct?.object_id ?? direct?.objectId ?? direct?.id;
  if (objectIds.has(directObjectId)) {
    return directObjectId;
  }

  for (const [objectId, mapping] of Object.entries(objectMap)) {
    if (!objectIds.has(objectId)) {
      continue;
    }
    const mappedEntityRef = typeof mapping === "string"
      ? mapping
      : mapping?.entity_ref ?? mapping?.entityRef ?? mapping?.metadata?.entity_ref;
    if (mappedEntityRef === entityRef) {
      return objectId;
    }
  }
  return null;
}
