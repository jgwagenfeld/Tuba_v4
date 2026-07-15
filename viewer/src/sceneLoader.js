import { loadOptionalReview } from "./reviewLoader.js";

const NODE_FS_PROMISES = "node:fs/promises";
const NODE_PATH = "node:path";

export async function loadSceneBundle(root) {
  const { readFile } = await import(/* @vite-ignore */ NODE_FS_PROMISES);
  const { join } = await import(/* @vite-ignore */ NODE_PATH);
  const readJson = async (relativePath) => JSON.parse(await readFile(join(root, relativePath), "utf8"));
  const scene = await readJson("scene.json");
  const objects = await readJson("metadata/objects.json");
  const objectMap = await readJson("metadata/object_map.json");
  const overlays = await readJson("metadata/overlays.json");
  const geometryAssets = await readJson("geometry/geometry_assets.json");
  const geometryPayloads = await Promise.all(
    (scene.geometry_assets ?? geometryAssets)
      .filter((asset) => asset.uri)
      .map((asset) => readJson(asset.uri))
  );

  return { scene, objects, objectMap, overlays, geometryAssets, geometryPayloads };
}

export async function loadSceneBundleFromUrl(baseUrl = ".", fetcher = globalThis.fetch) {
  const normalized = String(baseUrl).replace(/\/+$/, "");
  const readJson = async (relativePath) => {
    const response = await fetcher(`${normalized}/${relativePath}`);
    if (!response.ok) {
      throw new Error(`Failed to load ${relativePath}: ${response.status} ${response.statusText}`);
    }
    return response.json();
  };
  const scene = await readJson("scene.json");
  const objects = await readJson("metadata/objects.json");
  const objectMap = await readJson("metadata/object_map.json");
  const overlays = await readJson("metadata/overlays.json");
  const geometryAssets = await readJson("geometry/geometry_assets.json");
  const geometryPayloads = await Promise.all(
    (scene.geometry_assets ?? geometryAssets)
      .filter((asset) => asset.uri)
      .map((asset) => readJson(asset.uri))
  );

  const reviewResult = await loadOptionalReview(normalized, fetcher);

  return {
    scene,
    objects,
    objectMap,
    overlays,
    geometryAssets,
    geometryPayloads,
    review: reviewResult.review,
    reviewDiagnostics: reviewResult.diagnostics,
    legacyReview: reviewResult.legacy
  };
}

export function createViewerState(bundle) {
  const scene = bundle.scene;
  const objects = scene.objects?.length ? scene.objects : bundle.objects ?? [];
  const geometryAssets = scene.geometry_assets?.length ? scene.geometry_assets : bundle.geometryAssets ?? [];
  const overlays = scene.overlays?.length ? scene.overlays : bundle.overlays ?? [];
  const objectLayerIds = Object.fromEntries(objects.map((obj) => [obj.id, layerIdsForObject(obj)]));
  const layers = buildLayerRegistry(objects, overlays, objectLayerIds);
  const resultStates = overlays.filter((overlay) => overlay.kind === "result_state");
  const geometryStates = overlays.filter((overlay) => overlay.kind === "geometry_state");
  const activeResultState = resultStates[0] ?? null;
  const activeGeometryState = geometryStates[0] ?? null;

  const state = {
    sceneId: scene.scene_id,
    modelId: scene.model_id,
    schemaVersion: scene.schema_version,
    units: scene.units ?? {},
    coordinateSystem: scene.coordinate_system ?? {},
    objects,
    objectMap: bundle.objectMap ?? {},
    geometryAssets,
    geometryPayloads: bundle.geometryPayloads ?? [],
    overlays,
    issues: scene.issues ?? [],
    routeReviews: scene.route_reviews ?? [],
    agentProposals: scene.agent_proposals ?? [],
    sceneDiffs: scene.scene_diffs ?? [],
    sceneDiagnostics: scene.diagnostics ?? [],
    review: bundle.review ?? null,
    reviewDiagnostics: bundle.reviewDiagnostics ?? [],
    legacyReview: bundle.legacyReview ?? false,
    views: scene.views ?? [],
    diagnostics: [...(scene.diagnostics ?? []), ...validateScene(objects, geometryAssets, overlays)],
    layers,
    objectLayerIds,
    bounds: mergeBounds(geometryAssets.map((asset) => asset.bounds)),
    camera: { mode: "orbit", target: [0, 0, 0], distance: 1 },
    selectedObjectIds: [],
    hiddenObjectIds: [],
    isolatedObjectIds: [],
    activeIssueId: null,
    activeOverlayIds: [],
    resultStates,
    geometryStates,
    activeLoadCase: activeResultState?.data?.load_case ?? activeGeometryState?.data?.load_case ?? null,
    activeResultStateId: activeResultState?.data?.id ?? activeResultState?.id ?? null,
    activeGeometryStateId: activeGeometryState?.data?.id ?? activeGeometryState?.id ?? null,
    displacementVectorScale: 1,
    reactionVectorScale: 1,
    resultThreshold: null,
    resultVectorScales: { displacement: 1, reaction: 1 },
    utilizationThreshold: null,
    visualDeformationScale: Number(activeGeometryState?.data?.visual_scale ?? activeGeometryState?.data?.displacement_scale ?? 1),
    visibleOverlayIds: overlays.filter((overlay) => overlay.visible !== false).map((overlay) => overlay.id),
    visibleObjectIds: []
  };
  return { ...state, visibleObjectIds: getVisibleObjectIds(state) };
}

export function setLayerVisibility(state, layerId, visible) {
  const layers = {
    ...state.layers,
    [layerId]: { ...state.layers[layerId], visible }
  };
  let overlays = state.overlays;
  const layer = layers[layerId];
  if (layer?.source === "overlay") {
    overlays = state.overlays.map((overlay) =>
      overlay.kind === layer.overlayKind ? { ...overlay, visible } : overlay
    );
  }
  const next = {
    ...state,
    layers,
    overlays,
    visibleOverlayIds: overlays.filter((overlay) => overlay.visible !== false).map((overlay) => overlay.id)
  };
  return { ...next, visibleObjectIds: getVisibleObjectIds(next) };
}

export function getVisibleObjectIds(state) {
  const hidden = new Set(state.hiddenObjectIds ?? []);
  const isolated = new Set(state.isolatedObjectIds ?? []);
  const hiddenOverlayObjectIds = overlayHiddenObjectIds(state);
  return state.objects
    .filter((obj) => objectLayersVisible(state, obj))
    .filter((obj) => !hidden.has(obj.id))
    .filter((obj) => !hiddenOverlayObjectIds.has(obj.id))
    .filter((obj) => isolated.size === 0 || isolated.has(obj.id))
    .filter((obj) => objectIntersectsSectionBox(state, obj.id))
    .map((obj) => obj.id);
}

export function mergeBounds(boundsList) {
  const valid = boundsList.filter((bounds) => Array.isArray(bounds) && bounds.length === 6);
  if (valid.length === 0) {
    return [0, 0, 0, 0, 0, 0];
  }
  const mins = [Number.POSITIVE_INFINITY, Number.POSITIVE_INFINITY, Number.POSITIVE_INFINITY];
  const maxs = [Number.NEGATIVE_INFINITY, Number.NEGATIVE_INFINITY, Number.NEGATIVE_INFINITY];
  for (const bounds of valid) {
    for (let i = 0; i < 3; i += 1) {
      mins[i] = Math.min(mins[i], bounds[i]);
      maxs[i] = Math.max(maxs[i], bounds[i + 3]);
    }
  }
  return [...mins, ...maxs];
}

function overlayHiddenObjectIds(state) {
  const ids = new Set();
  const overlayOwnedKinds = new Set([
    "physical_envelope",
    "clash_marker",
    "rule_marker",
    "route_candidate",
    "displacement_vector",
    "reaction_vector"
  ]);
  for (const overlay of state.overlays ?? []) {
    if (overlay.visible !== false) {
      continue;
    }
    for (const objectId of overlay.object_ids ?? []) {
      const obj = state.objects.find((candidate) => candidate.id === objectId);
      if (obj && overlayOwnedKinds.has(obj.kind)) {
        ids.add(objectId);
      }
    }
  }
  return ids;
}

function buildLayerRegistry(objects, overlays, objectLayerIds) {
  const layers = {};
  for (const obj of objects) {
    for (const id of objectLayerIds[obj.id] ?? [obj.kind || "object"]) {
      layers[id] ??= { id, label: labelForLayer(id), visible: true, count: 0, source: "object", objectIds: [] };
      layers[id].count += 1;
      layers[id].objectIds.push(obj.id);
    }
  }
  for (const overlay of overlays) {
    const id = `overlay:${overlay.kind || "overlay"}`;
    layers[id] ??= {
      id,
      label: labelForLayer(id),
      visible: overlay.visible !== false,
      count: 0,
      source: "overlay",
      overlayKind: overlay.kind || "overlay",
      overlayIds: []
    };
    layers[id].count += 1;
    layers[id].overlayIds.push(overlay.id);
    if (overlay.visible === false) {
      layers[id].visible = false;
    }
  }
  return layers;
}

function layerIdsForObject(obj) {
  return Array.isArray(obj.layer_ids) && obj.layer_ids.length > 0 ? [...obj.layer_ids] : [obj.kind || "object"];
}

function objectLayersVisible(state, obj) {
  const layerIds = state.objectLayerIds?.[obj.id] ?? layerIdsForObject(obj);
  return layerIds.every((layerId) => state.layers[layerId]?.visible !== false);
}

function objectIntersectsSectionBox(state, objectId) {
  if (!state.sectionBox) {
    return true;
  }
  const asset = state.geometryAssets.find((candidate) => (candidate.object_ids ?? []).includes(objectId));
  if (!asset?.bounds || asset.bounds.length !== 6) {
    return true;
  }
  const bounds = asset.bounds;
  const min = state.sectionBox.min;
  const max = state.sectionBox.max;
  return (
    bounds[3] >= min[0] &&
    bounds[0] <= max[0] &&
    bounds[4] >= min[1] &&
    bounds[1] <= max[1] &&
    bounds[5] >= min[2] &&
    bounds[2] <= max[2]
  );
}

function validateScene(objects, geometryAssets, overlays) {
  const diagnostics = [];
  const assetIds = new Set(geometryAssets.map((asset) => asset.id));
  const objectIds = new Set(objects.map((obj) => obj.id));
  for (const obj of objects) {
    if (obj.geometry_asset_id && !assetIds.has(obj.geometry_asset_id)) {
      diagnostics.push({
        code: "viewer.missing_geometry_asset",
        severity: "warning",
        message: `Object ${obj.id} references missing geometry asset ${obj.geometry_asset_id}.`,
        object_id: obj.id,
        asset_id: obj.geometry_asset_id
      });
    }
  }
  for (const overlay of overlays) {
    for (const objectId of overlay.object_ids ?? []) {
      if (!objectIds.has(objectId)) {
        diagnostics.push({
          code: "viewer.overlay_missing_object",
          severity: "warning",
          message: `Overlay ${overlay.id} references missing object ${objectId}.`,
          overlay_id: overlay.id,
          object_id: objectId
        });
      }
    }
  }
  return diagnostics;
}

function labelForLayer(key) {
  return key
    .replace(/^overlay:/, "overlay:")
    .split(/[:_-]+/)
    .map((part) => `${part.slice(0, 1).toUpperCase()}${part.slice(1)}`)
    .join(" ");
}
