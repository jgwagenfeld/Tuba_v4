import { getVisibleObjectIds } from "./sceneLoader.js";

export function selectObject(state, objectId, options = {}) {
  if (!state.objects.some((obj) => obj.id === objectId)) {
    return state;
  }
  const current = state.selectedObjectIds ?? [];
  const selectedObjectIds = options.additive
    ? [...current.filter((id) => id !== objectId), objectId]
    : [objectId];
  return { ...state, selectedObjectIds };
}

export function hideSelected(state) {
  const hidden = new Set([...(state.hiddenObjectIds ?? []), ...(state.selectedObjectIds ?? [])]);
  return withVisibility({ ...state, hiddenObjectIds: [...hidden] });
}

export function isolateSelection(state) {
  return withVisibility({ ...state, isolatedObjectIds: [...(state.selectedObjectIds ?? [])] });
}

export function restoreVisibility(state) {
  return withVisibility({ ...state, hiddenObjectIds: [], isolatedObjectIds: [], sectionBox: undefined });
}

export function getPropertySections(state, objectId) {
  const obj = state.objects.find((candidate) => candidate.id === objectId);
  if (!obj) {
    return [];
  }
  const asset = state.geometryAssets.find((candidate) => candidate.id === obj.geometry_asset_id);
  const attributes = { ...(obj.metadata?.attributes ?? {}) };
  if (obj.metadata?.insulation?.id) {
    attributes.insulation = obj.metadata.insulation.id;
    attributes.insulation_material = obj.metadata.insulation.material;
    attributes.insulation_thickness_m = obj.metadata.insulation.thickness_m;
  }
  const resultRows = resultRowsForObject(state, obj);
  const clashRows = clashRowsForObject(obj);
  const issueRows = issueRowsForObject(state, obj);
  const externalRows = externalRowsForObject(obj);
  const provenanceRows = provenanceRowsForObject(obj, asset);
  const profileRows = obj.metadata?.profile ?? {};

  return [
    {
      id: "identity",
      title: "Identity",
      rows: compactRows({ id: obj.id, entity_ref: obj.entity_ref, kind: obj.kind, name: obj.name })
    },
    {
      id: "geometry",
      title: "Geometry",
      rows: compactRows({ geometry_asset_id: obj.geometry_asset_id, asset_format: asset?.format, bounds: asset?.bounds })
    },
    {
      id: "attributes",
      title: "Attributes",
      rows: compactRows({ section: obj.metadata?.section, material: obj.metadata?.material, ...attributes })
    },
    { id: "profile", title: "Profile", rows: compactRows(profileRows) },
    { id: "physical", title: "Physical", rows: compactRows(obj.physical ?? {}) },
    { id: "quantities", title: "Quantities", rows: compactRows(obj.quantities ?? {}) },
    { id: "result_values", title: "Result Values", rows: compactRows(resultRows) },
    { id: "clash", title: "Clash", rows: compactRows(clashRows) },
    { id: "issues", title: "Issues", rows: compactRows(issueRows) },
    { id: "external_refs", title: "External Refs", rows: compactRows(externalRows) },
    { id: "provenance", title: "Provenance", rows: compactRows(provenanceRows) }
  ].filter((section) => Object.keys(section.rows).length > 0);
}

export function fitSelection(state) {
  const selected = new Set(state.selectedObjectIds ?? []);
  const selectedAssetIds = new Set(
    state.objects
      .filter((obj) => selected.has(obj.id))
      .map((obj) => obj.geometry_asset_id)
      .filter(Boolean)
  );
  const bounds = state.geometryAssets
    .filter((asset) => selectedAssetIds.has(asset.id) || (asset.object_ids ?? []).some((id) => selected.has(id)))
    .map((asset) => asset.bounds)
    .filter((bounds) => Array.isArray(bounds) && bounds.length === 6);
  if (bounds.length === 0) {
    return state;
  }
  const merged = mergeBounds(bounds);
  const target = [
    (merged[0] + merged[3]) / 2,
    (merged[1] + merged[4]) / 2,
    (merged[2] + merged[5]) / 2
  ];
  const distance = Math.max(Math.hypot(merged[3] - merged[0], merged[4] - merged[1], merged[5] - merged[2]), 1);
  return { ...state, camera: { ...state.camera, target, distance, fitBounds: merged } };
}

export function pickObjectAt(state, point, viewport) {
  const candidates = [];
  for (const asset of state.geometryAssets) {
    const visibleObjectIds = (asset.object_ids ?? []).filter((id) => state.visibleObjectIds.includes(id));
    if (visibleObjectIds.length === 0) {
      continue;
    }
    const projected = project(centerOfBounds(asset.bounds), state.bounds, viewport.width, viewport.height);
    const distance = Math.hypot(projected[0] - point.x, projected[1] - point.y);
    for (const objectId of visibleObjectIds) {
      candidates.push({ objectId, distance });
    }
  }
  candidates.sort((left, right) => left.distance - right.distance);
  return candidates[0]?.objectId ?? null;
}

function withVisibility(state) {
  return { ...state, visibleObjectIds: getVisibleObjectIds(state) };
}

function compactRows(rows) {
  return Object.fromEntries(
    Object.entries(rows).filter(([_key, value]) => value !== undefined && value !== null && value !== "")
  );
}

function resultRowsForObject(state, obj) {
  const rows = {};
  for (const overlay of state.overlays ?? []) {
    if (!["solver_result", "result_state"].includes(overlay.kind)) {
      continue;
    }
    const data = overlay.data ?? {};
    const field = data.field || data.result_type || overlay.name || overlay.id;
    if (data.values?.[obj.id] !== undefined) {
      rows[field] = data.values[obj.id];
      if (data.unit) {
        rows[`${field}_unit`] = data.unit;
      }
    }
    if (data.element_results?.[obj.id]) {
      Object.assign(rows, data.element_results[obj.id]);
    }
  }
  return rows;
}

function clashRowsForObject(obj) {
  const metadata = obj.metadata ?? {};
  const review = metadata.review ?? {};
  const clash = metadata.clash ?? metadata.clash_metadata ?? {};
  return {
    left: metadata.left ?? clash.left ?? review.object_pair?.[0],
    right: metadata.right ?? clash.right ?? review.object_pair?.[1],
    distance_m: metadata.distance_m ?? clash.distance_m,
    penetration_m: metadata.penetration_m ?? clash.penetration_m,
    cold_distance_m: metadata.cold_distance_m ?? clash.cold_distance_m,
    operating_distance_m: metadata.operating_distance_m ?? clash.operating_distance_m,
    envelope_type: metadata.envelope_type ?? clash.envelope_type ?? review.envelope_type
  };
}

function issueRowsForObject(state, obj) {
  const issueIds = (state.issues ?? [])
    .filter((issue) =>
      (issue.object_ids ?? []).includes(obj.id) ||
      (issue.entity_refs ?? []).includes(obj.entity_ref) ||
      issue.id === obj.metadata?.issue_id
    )
    .map((issue) => issue.id);
  return { issue_ids: issueIds.join(", ") };
}

function externalRowsForObject(obj) {
  return {
    ...(obj.external_refs ?? {}),
    ...(obj.metadata?.external_refs ?? {}),
    ifc_guid: obj.ifc_guid ?? obj.metadata?.ifc_guid ?? obj.external_refs?.ifc_guid ?? obj.metadata?.external_refs?.ifc_guid
  };
}

function provenanceRowsForObject(obj, asset) {
  return {
    source_ref: obj.metadata?.source_ref ?? asset?.generation_config?.source_ref ?? asset?.generation_config?.entity_ref,
    source: obj.metadata?.source ?? asset?.generation_config?.source,
    role: obj.metadata?.role ?? asset?.generation_config?.role,
    mesh_id: obj.metadata?.mesh_id ?? obj.source?.analysis_mesh?.id ?? asset?.generation_config?.mesh_id,
    member_type: obj.source?.analysis_mesh?.member_type,
    member_id: obj.source?.analysis_mesh?.member_id
  };
}

function mergeBounds(boundsList) {
  const mins = [Number.POSITIVE_INFINITY, Number.POSITIVE_INFINITY, Number.POSITIVE_INFINITY];
  const maxs = [Number.NEGATIVE_INFINITY, Number.NEGATIVE_INFINITY, Number.NEGATIVE_INFINITY];
  for (const bounds of boundsList) {
    for (let i = 0; i < 3; i += 1) {
      mins[i] = Math.min(mins[i], bounds[i]);
      maxs[i] = Math.max(maxs[i], bounds[i + 3]);
    }
  }
  return [...mins, ...maxs];
}

function centerOfBounds(bounds) {
  if (!Array.isArray(bounds) || bounds.length !== 6) {
    return [0, 0, 0];
  }
  return [(bounds[0] + bounds[3]) / 2, (bounds[1] + bounds[4]) / 2, (bounds[2] + bounds[5]) / 2];
}

function project(point, bounds, width, height) {
  const pad = 32;
  const minX = bounds[0];
  const maxX = bounds[3];
  const minY = bounds[1];
  const maxY = bounds[4];
  const spanX = Math.max(maxX - minX, 1e-9);
  const spanY = Math.max(maxY - minY, 1e-9);
  const x = pad + ((point[0] - minX) / spanX) * (width - pad * 2);
  const y = height - pad - ((point[1] - minY) / spanY) * (height - pad * 2);
  return [x, y];
}
