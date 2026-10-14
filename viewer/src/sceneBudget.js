// Receiving limits are independent of a bundle producer. Oversized data is rejected,
// never truncated: solver values and the engineering path remain unchanged.
export const SCENE_LIMITS = Object.freeze({
  responseBytes: 64 * 1024 * 1024, totalBytes: 128 * 1024 * 1024,
  objects: 10000, assets: 10000, points: 500000, faces: 500000, instances: 200000,
  generatedInstances: 150000, generatedVertices: 2500000, generatedFaces: 2000000,
  tubePoints: 256, tubularSegments: 2048, depth: 32, values: 4 * 1024 * 1024,
  labelCharacters: 256, texturePixels: 32 * 1024 * 1024
});

export class SceneBudgetError extends Error {
  constructor(message) { super(`Scene resource limit: ${message}`); this.name = "SceneBudgetError"; }
}

function limit(kind, count) {
  if (!Number.isFinite(count) || count > SCENE_LIMITS[kind]) {
    throw new SceneBudgetError(`${kind} exceeds ${SCENE_LIMITS[kind]}.`);
  }
}

function triangleCount(faces) {
  if (!Array.isArray(faces)) return 0;
  return faces.reduce((count, face) => count + (Array.isArray(face) ? (face.length === 4 ? 6 : face.length) : 1), 0) / 3;
}

export function tubeTessellation(config = {}) {
  const count = Array.isArray(config.points) ? config.points.length : 0;
  limit("tubePoints", count);
  const tubularSegments = Math.max(8, count * 12);
  limit("tubularSegments", tubularSegments);
  const radialSegments = Math.max(6, Math.min(48, Math.floor(Number(config.radial_segments) || 16)));
  const hollow = Number(config.inner_radius_m) > 0;
  const surfaces = hollow ? 2 : 1;
  return { tubularSegments, radialSegments,
    vertices: surfaces * (tubularSegments + 1) * (radialSegments + 1) + (hollow ? 4 * (radialSegments * 2 + 1) : 0),
    faces: surfaces * tubularSegments * radialSegments * 2 + (hollow ? radialSegments * 8 : 0) };
}

export function textTextureSize(text, width, height = 100, budget) {
  const count = String(text).length;
  limit("labelCharacters", count);
  // Reserve text width before rendering; actual font metrics must fit that reservation.
  const maximumWidth = Math.max(256, count * 64) + 44;
  width = Math.ceil(width ?? maximumWidth);
  height = Math.ceil(height);
  if (!Number.isFinite(width) || width < 1 || width > maximumWidth || !Number.isFinite(height) || height < 1 || height > 100) {
    throw new SceneBudgetError("text texture exceeds its reserved dimensions.");
  }
  const pixels = width * height;
  if (budget) limit("texturePixels", budget.pixels += pixels);
  return { width, height, pixels };
}

export function validateJsonBudget(value, budget = { values: 0 }) {
  budget.values ??= 0;
  const walk = (item, depth, counted = false) => {
    limit("depth", depth);
    if (!counted) limit("values", ++budget.values);
    if (Array.isArray(item)) {
      // Numerical payloads contain millions of primitive coordinates. Account
      // for their depth and count once, then recurse only into nested objects.
      if (item.length) limit("depth", depth + 1);
      limit("values", budget.values += item.length);
      for (const child of item) {
        if (child && typeof child === "object") walk(child, depth + 1, true);
      }
      return;
    }
    if (item && typeof item === "object") {
      for (const child of Object.values(item)) walk(child, depth + 1);
    }
  };
  walk(value, 0);
  return value;
}

export function validateSceneBudget(bundle = {}, generatedAssets) {
  const scene = bundle.scene ?? bundle;
  const objects = scene.objects?.length ? scene.objects : bundle.objects ?? scene.objects ?? [];
  const assets = scene.geometry_assets?.length ? scene.geometry_assets : bundle.geometryAssets ?? scene.geometry_assets ?? [];
  const payloads = bundle.geometryPayloads ?? [];
  limit("objects", objects.length);
  limit("assets", assets.length);
  limit("assets", payloads.length);
  const totals = { points: 0, faces: 0, instances: 0, generatedVertices: 0, generatedFaces: 0, texturePixels: 0 };
  let values = 0;
  const seen = new Set();
  const walk = (item, depth = 0, counted = false) => {
    limit("depth", depth);
    if (!counted) limit("values", ++values);
    if (!item || typeof item !== "object" || seen.has(item)) return;
    seen.add(item);
    if (Array.isArray(item)) {
      if (item.length) limit("depth", depth + 1);
      limit("values", values += item.length);
      for (const child of item) {
        if (child && typeof child === "object") walk(child, depth + 1, true);
      }
      return;
    }
    for (const [key, child] of Object.entries(item)) {
      if (Array.isArray(child)) {
        if (["points", "vertices", "base_points", "base_vertices", "cold_points", "volume_vertices", "starts", "ends", "start_points", "end_points", "arrow_starts", "arrow_ends", "crest_points"].includes(key)) totals.points += child.length;
        if (["faces", "triangles", "indices", "surface_edge_indices", "volume_edge_indices"].includes(key)) totals.faces += triangleCount(child);
        if (["instances", "samples", "stations", "glyphs", "starts", "start_points", "arrow_starts"].includes(key)) totals.instances += child.length;
        for (const kind of ["points", "faces", "instances"]) limit(kind, totals[kind]);
      }
      walk(child, depth + 1);
    }
  };
  walk(scene);
  walk(objects);
  walk(assets);
  walk(payloads);
  const byId = new Map(payloads.map((payload) => [payload.asset_id, payload]));
  const generating = new Set(generatedAssets ?? assets);
  let generatedInstances = 0;
  for (const asset of assets) {
    const payload = byId.get(asset.id) ?? {};
    const config = { ...(payload.generation_config ?? {}), ...(asset.generation_config ?? {}) };
    const format = String(asset.format ?? "").toLowerCase();
    // Hard per-asset limits cover hidden data too; cumulative costs describe
    // only the assets this graph will allocate, not other result/geometry states.
    const labelPixels = format === "label" ? textTextureSize(config.text ?? "").pixels : 0;
    const badgePixels = config.badge_text ? textTextureSize(config.badge_text).pixels : 0;
    const tubeCost = ["tube", "tube_envelope"].includes(format) ? tubeTessellation(config) : null;
    if (!generating.has(asset)) continue;
    totals.texturePixels += labelPixels + (config.show_badge !== false ? badgePixels : 0);
    limit("texturePixels", totals.texturePixels);
    const morphCopies = config.base_points || config.base_vertices ? 2 : 1;
    if (tubeCost) {
      totals.generatedVertices += tubeCost.vertices * morphCopies;
      totals.generatedFaces += tubeCost.faces * morphCopies;
    } else if (format === "mesh") {
      const faces = triangleCount(config.triangles ?? config.faces ?? config.indices ?? payload.faces ?? payload.indices ?? config.mesh?.faces);
      // Crease splitting and the user-toggleable triangle wireframe can duplicate positions.
      totals.generatedVertices += Math.max(faces * 9, (config.vertices ?? payload.vertices ?? config.mesh?.vertices)?.length ?? 0) * morphCopies;
      totals.generatedVertices += (config.volume_vertices?.length ?? 0) + (config.volume_edge_indices?.length ?? 0) * 2;
      totals.generatedFaces += faces * morphCopies;
    } else if (format === "tuyau_subpoint_glyphs") {
      const count = (config.starts ?? config.start_points)?.length ?? 0;
      // A received payload can be referenced by more than one rendered asset.
      limit("generatedInstances", generatedInstances += count);
      const radial = Math.max(4, Math.min(16, Math.floor(Number(config.radial_segments) || 8)));
      // InstancedMesh shares one cylinder; each instance allocates only a
      // 16-float matrix and 3-float color. Instance and radial caps also bound
      // draw work to at most 150,000 * 64 instanced triangles per scene.
      totals.generatedVertices += 6 * radial + 4 + count * Math.ceil(19 / 3);
      totals.generatedFaces += 4 * radial;
    } else {
      // Covers bounded primitive glyphs and swept profiles as well as line assets.
      const instances = Math.max(1, config.instances?.length ?? 0, config.samples?.length ?? 0,
        config.stations?.length ?? 0, config.points?.length ?? 0, config.arrow_starts?.length ?? 0,
        (config.starts ?? config.start_points)?.length ?? 0);
      const perInstance = config.support_type ? 8192 : format === "vector" ? 2048 : 512;
      totals.generatedVertices += instances * perInstance * morphCopies;
      totals.generatedFaces += instances * perInstance * morphCopies;
      if (format === "line_load_comb") totals.generatedVertices += (config.crest_points ?? config.arrow_starts)?.length ?? 0;
    }
    limit("generatedVertices", totals.generatedVertices);
    limit("generatedFaces", totals.generatedFaces);
  }
  return totals;
}

export async function readBoundedJson(response, budget = { bytes: 0 }, parse = (bytes) => validateJsonBudget(JSON.parse(new TextDecoder().decode(bytes)), budget)) {
  const declared = Number(response.headers?.get?.("content-length"));
  if (Number.isFinite(declared) && declared > SCENE_LIMITS.responseBytes) {
    await response.body?.cancel?.();
    throw new SceneBudgetError("response bytes exceed 64 MiB.");
  }
  if (!response.body?.getReader) throw new SceneBudgetError("a bounded response stream is required.");
  const reader = response.body.getReader();
  const chunks = [];
  let size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      budget.bytes += value.byteLength;
      if (size > SCENE_LIMITS.responseBytes || budget.bytes > SCENE_LIMITS.totalBytes) {
        throw new SceneBudgetError("response/aggregate bytes exceed 64/128 MiB.");
      }
      chunks.push(value);
    }
  } catch (error) {
    await reader.cancel();
    throw error;
  } finally { reader.releaseLock(); }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  return parse(bytes);
}
