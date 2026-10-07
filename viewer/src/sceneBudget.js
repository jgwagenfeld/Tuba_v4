// Receiving limits are independent of a bundle producer. Oversized data is rejected,
// never truncated: solver values and the engineering path remain unchanged.
export const SCENE_LIMITS = Object.freeze({
  responseBytes: 32 * 1024 * 1024, totalBytes: 128 * 1024 * 1024,
  objects: 10000, assets: 10000, points: 500000, faces: 500000, instances: 50000,
  generatedVertices: 2000000, generatedFaces: 2000000,
  tubePoints: 256, tubularSegments: 2048, depth: 32, values: 4000000
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

export function validateJsonBudget(value, budget = { values: 0 }) {
  budget.values ??= 0;
  const walk = (item, depth) => {
    limit("depth", depth);
    budget.values += 1;
    limit("values", budget.values);
    if (item && typeof item === "object") {
      for (const child of Array.isArray(item) ? item : Object.values(item)) walk(child, depth + 1);
    }
  };
  walk(value, 0);
  return value;
}

export function validateSceneBudget(bundle = {}) {
  const scene = bundle.scene ?? bundle;
  const objects = scene.objects?.length ? scene.objects : bundle.objects ?? scene.objects ?? [];
  const assets = scene.geometry_assets?.length ? scene.geometry_assets : bundle.geometryAssets ?? scene.geometry_assets ?? [];
  const payloads = bundle.geometryPayloads ?? [];
  limit("objects", objects.length);
  limit("assets", assets.length);
  limit("assets", payloads.length);
  const totals = { points: 0, faces: 0, instances: 0, generatedVertices: 0, generatedFaces: 0 };
  let values = 0;
  const seen = new Set();
  const walk = (item, depth = 0) => {
    limit("depth", depth);
    limit("values", ++values);
    if (!item || typeof item !== "object" || seen.has(item)) return;
    seen.add(item);
    if (Array.isArray(item)) {
      for (const child of item) walk(child, depth + 1);
      return;
    }
    for (const [key, child] of Object.entries(item)) {
      if (Array.isArray(child)) {
        if (["points", "vertices", "base_points", "base_vertices", "cold_points", "volume_vertices", "starts", "ends", "start_points", "end_points"].includes(key)) totals.points += child.length;
        if (["faces", "triangles", "indices", "surface_edge_indices", "volume_edge_indices"].includes(key)) totals.faces += triangleCount(child);
        if (["instances", "samples", "stations", "glyphs", "starts", "start_points"].includes(key)) totals.instances += child.length;
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
  for (const asset of assets) {
    const payload = byId.get(asset.id) ?? {};
    const config = { ...(payload.generation_config ?? {}), ...(asset.generation_config ?? {}) };
    const format = String(asset.format ?? "").toLowerCase();
    const morphCopies = config.base_points || config.base_vertices ? 2 : 1;
    if (["tube", "tube_envelope"].includes(format)) {
      const cost = tubeTessellation(config);
      totals.generatedVertices += cost.vertices * morphCopies;
      totals.generatedFaces += cost.faces * morphCopies;
    } else if (format === "mesh") {
      const faces = triangleCount(config.triangles ?? config.faces ?? config.indices ?? payload.faces ?? payload.indices ?? config.mesh?.faces);
      // Crease splitting and the user-toggleable triangle wireframe can duplicate positions.
      totals.generatedVertices += Math.max(faces * 9, (config.vertices ?? payload.vertices ?? config.mesh?.vertices)?.length ?? 0) * morphCopies;
      totals.generatedVertices += (config.volume_vertices?.length ?? 0) + (config.volume_edge_indices?.length ?? 0) * 2;
      totals.generatedFaces += faces * morphCopies;
    } else if (format === "tuyau_subpoint_glyphs") {
      const count = (config.starts ?? config.start_points)?.length ?? 0;
      const radial = Math.max(4, Math.min(16, Math.floor(Number(config.radial_segments) || 8)));
      totals.generatedVertices += count * (4 * radial + 6);
      totals.generatedFaces += count * 4 * radial;
    } else {
      // Covers bounded primitive glyphs and swept profiles as well as line assets.
      const instances = Math.max(1, config.instances?.length ?? 0, config.samples?.length ?? 0,
        config.stations?.length ?? 0, config.points?.length ?? 0, (config.starts ?? config.start_points)?.length ?? 0);
      const perInstance = config.support_type ? 8192 : format === "vector" ? 2048 : 512;
      totals.generatedVertices += instances * perInstance * morphCopies;
      totals.generatedFaces += instances * perInstance * morphCopies;
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
    throw new SceneBudgetError("response bytes exceed 32 MiB.");
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
        throw new SceneBudgetError("response/aggregate bytes exceed 32/128 MiB.");
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
