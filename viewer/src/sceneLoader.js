import { loadOptionalReview } from "./reviewLoader.js";
import { visibilityPresetForTask } from "./workflowState.js";
import { createColoringState } from "./coloring.js";

const NODE_FS_PROMISES = "node:fs/promises";
const NODE_PATH = "node:path";

export async function loadSceneBundle(root) {
  const { readFile } = await import(/* @vite-ignore */ NODE_FS_PROMISES);
  const { join } = await import(/* @vite-ignore */ NODE_PATH);
  const readJson = async (relativePath) => JSON.parse(await readFile(join(root, relativePath), "utf8"));
  const scene = await readJson("scene.json");
  const objects = Array.isArray(scene.objects) ? scene.objects : await readJson("metadata/objects.json");
  const objectMap = await readJson("metadata/object_map.json");
  const overlays = Array.isArray(scene.overlays) ? scene.overlays : await readJson("metadata/overlays.json");
  const geometryAssets = Array.isArray(scene.geometry_assets)
    ? scene.geometry_assets
    : await readJson("geometry/geometry_assets.json");
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
    const url = `${normalized}/${relativePath}`;
    const response = await fetcher(url);
    if (!response.ok) {
      throw new Error(`Failed to load ${relativePath}: ${response.status} ${response.statusText}`);
    }
    const contentType = response.headers?.get?.("content-type") ?? "";
    if (contentType.toLowerCase().includes("text/html")) {
      throw new Error(
        `Expected JSON from ${url}, but received ${contentType.split(";")[0]}. ` +
          "The bundle URL points to a different application or server."
      );
    }
    return response.json();
  };
  const scene = await readJson("scene.json");
  const objects = Array.isArray(scene.objects) ? scene.objects : await readJson("metadata/objects.json");
  const objectMap = await readJson("metadata/object_map.json");
  const overlays = Array.isArray(scene.overlays) ? scene.overlays : await readJson("metadata/overlays.json");
  const geometryAssets = Array.isArray(scene.geometry_assets)
    ? scene.geometry_assets
    : await readJson("geometry/geometry_assets.json");
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
  const sceneLayers = Array.isArray(scene.layers) ? scene.layers : [];
  const layers = buildLayerRegistry(objects, overlays, objectLayerIds, sceneLayers);
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
    resultFields: Array.isArray(scene.result_fields) ? scene.result_fields : [],
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
  return {
    ...state,
    coloring: createColoringState(state),
    visibleObjectIds: getVisibleObjectIds(state)
  };
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

function buildLayerRegistry(objects, overlays, objectLayerIds, sceneLayers = []) {
  const declared = new Map(sceneLayers.map((layer) => [layer.id, layer]));
  const layers = {};
  const decorate = (id) => {
    const spec = declared.get(id);
    return spec ? { category: spec.category, label: spec.label || labelForLayer(id), meshIdentity: spec.mesh_identity } : {};
  };
  // The scene says what it wants shown on arrival. This used to be read only for
  // layers that draw nothing, so every layer that actually draws something came
  // up visible whatever the bundle declared.
  const declaredVisible = (id) => declared.get(id)?.default_visible !== false;

  for (const obj of objects) {
    for (const id of objectLayerIds[obj.id] ?? [obj.kind || "object"]) {
      layers[id] ??= {
        id,
        label: labelForLayer(id),
        visible: declaredVisible(id),
        count: 0,
        source: "object",
        objectIds: [],
        ...decorate(id)
      };
      layers[id].count += 1;
      layers[id].objectIds.push(obj.id);
    }
  }
  for (const overlay of overlays) {
    const id = `overlay:${overlay.kind || "overlay"}`;
    layers[id] ??= {
      id,
      label: labelForLayer(id),
      visible: overlay.visible !== false && declaredVisible(id),
      count: 0,
      source: "overlay",
      overlayKind: overlay.kind || "overlay",
      overlayIds: [],
      ...decorate(id)
    };
    layers[id].count += 1;
    layers[id].overlayIds.push(overlay.id);
    if (overlay.visible === false) {
      layers[id].visible = false;
    }
  }
  // Layers the scene declares but no object or overlay populates - the mesh
  // identity badge is one, since it describes the mesh rather than drawing it.
  for (const spec of sceneLayers) {
    layers[spec.id] ??= {
      id: spec.id,
      label: spec.label || labelForLayer(spec.id),
      visible: spec.default_visible !== false,
      count: 0,
      source: "scene",
      category: spec.category,
      meshIdentity: spec.mesh_identity
    };
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

// Four categories, each a rule rather than a bucket: what was authored, what
// was solved, what came back, what comments on it. The scene states these
// directly (SceneLayer.category); the prefix rules below are only a fallback
// for bundles written before the contract carried them.
const CATEGORY_ORDER = [
  { id: "design", label: "Design" },
  { id: "analysis_mesh", label: "Analysis mesh" },
  { id: "results", label: "Results" },
  { id: "annotations", label: "Annotations" }
];

const LEGACY_CATEGORY_REMAP = {
  geometry: "design",
  envelopes: "design",
  analysis_mesh: "analysis_mesh",
  results: "results",
  overlays: "annotations",
  other: "annotations"
};

export function legacyCategoryForLayerId(layerId) {
  const id = String(layerId);
  if (id === "overlay:physical_envelope") return "envelopes";
  if (id === "overlay:solver_result") return "results";
  if (id.startsWith("overlay:")) return "overlays";
  if (id.startsWith("analysis_mesh:")) return "analysis_mesh";
  if (id.startsWith("result:") || id.startsWith("solver_result:") || id.startsWith("deformed:")) return "results";
  if (id.startsWith("physical_envelope:")) return "envelopes";
  if (!id.includes(":")) return "geometry";
  return "other";
}

export function categoryForLayerId(layerId, declaredCategory = null) {
  if (declaredCategory && CATEGORY_ORDER.some((category) => category.id === declaredCategory)) {
    return declaredCategory;
  }
  return LEGACY_CATEGORY_REMAP[legacyCategoryForLayerId(layerId)] ?? "annotations";
}

export function categorizeLayers(layers) {
  const byCategory = new Map(CATEGORY_ORDER.map((category) => [category.id, []]));
  for (const layer of Object.values(layers ?? {})) {
    byCategory.get(categoryForLayerId(layer.id, layer.category)).push(layer);
  }
  const result = [];
  for (const category of CATEGORY_ORDER) {
    const members = byCategory.get(category.id);
    if (members.length === 0) continue;
    // Metadata-only layers describe content rather than gating it (the mesh
    // identity badge is one). They must stay out of the tree and out of the
    // master toggle, or they show up as a phantom leaf that toggles nothing.
    const gates = members.filter((layer) => !isMetadataLayer(layer));
    const metadata = members.filter(isMetadataLayer);
    if (gates.length === 0 && metadata.length === 0) continue;
    const leaves = [];
    const groupLeaves = [];
    for (const layer of gates) {
      const entry = { layerId: layer.id, label: leafLabel(layer.id), count: layer.count };
      if (/:group:[^:]+$/.test(layer.id)) {
        groupLeaves.push(entry);
      } else {
        leaves.push(entry);
      }
    }
    result.push({
      id: category.id,
      label: category.label,
      layerIds: gates.map((layer) => layer.id),
      leaves,
      groups: groupLeaves.length > 0 ? [{ label: "Groups", leaves: groupLeaves }] : [],
      meshIdentity: metadata.map((layer) => layer.meshIdentity).find(Boolean) ?? null
    });
  }
  return result;
}

function isMetadataLayer(layer) {
  return layer.source === "scene" && !layer.count;
}

export function applyTaskVisibilityPreset(state, taskId) {
  const preset = visibilityPresetForTask(taskId);
  if (!preset) return state;
  let next = state;
  for (const category of categorizeLayers(state.layers)) {
    if (!(category.id in preset)) continue;
    const visible = preset[category.id];
    for (const layerId of category.layerIds) {
      next = setLayerVisibility(next, layerId, visible);
    }
  }
  return next;
}

function leafLabel(layerId) {
  const last = String(layerId).split(":").at(-1);
  return last
    .split(/[_-]+/)
    .map((part) => `${part.slice(0, 1).toUpperCase()}${part.slice(1)}`)
    .join(" ");
}
