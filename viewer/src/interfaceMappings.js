// Ownership is published by the compiler/scene builder, never inferred from proximity.
export function getInterfaceMappings(state, objectId) {
  const objects = state.objects ?? [];
  const selected = objects.find(object => object.id === objectId);
  if (!selected) return [];
  return objects.filter(object => object.kind === "interface_mapping" &&
    (object.id === objectId || Array.isArray(object.metadata?.owner_refs) &&
      object.metadata.owner_refs.includes(selected.entity_ref)));
}

export function selectedInterfaceMappingIds(state) {
  return new Set((state.selectedObjectIds ?? []).flatMap(id => getInterfaceMappings(state, id).map(object => object.id)));
}
