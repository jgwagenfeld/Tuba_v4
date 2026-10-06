import { createViewerState } from "./sceneLoader.js";

const UNIT_SCALES = Object.freeze({ m: 1, mm: 0.001, cm: 0.01, inch: 0.0254 });
const DEFAULT_LIMIT = 16 * 1024 * 1024;

export function pythonLiteral(value) {
  if (value === null) return "None";
  if (typeof value === "boolean") return value ? "True" : "False";
  if (typeof value === "string") return JSON.stringify(value);
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  if (Array.isArray(value)) return `[${value.map(pythonLiteral).join(", ")}]`;
  if (value && typeof value === "object") return `{${Object.entries(value).map(([key, item]) => `${JSON.stringify(key)}: ${pythonLiteral(item)}`).join(", ")}}`;
  throw new Error("Selector contains a value that cannot be copied to Python.");
}

function finite(value, label) {
  if (value === "" || value == null || !Number.isFinite(Number(value))) throw new Error(`${label} must be finite.`);
  return Number(value);
}

export function geometryImportOptions({ id, unit, scale, origin, rotation, format }) {
  if (!/^[A-Za-z_][A-Za-z0-9_.-]{0,63}$/.test(id ?? "")) throw new Error("Component name must be 1–64 characters, start with a letter or underscore and use letters, numbers, dots, underscores or hyphens.");
  if (["STEP", "STP"].includes(String(format).toUpperCase()) && !["mm", "custom"].includes(unit)) throw new Error("STEP coordinates are normalized to millimetres. Choose Millimetres or an explicit custom scale.");
  const factor = unit === "custom" ? finite(scale, "Scale to metres") : UNIT_SCALES[unit];
  if (!(factor > 0)) throw new Error("Choose coordinate units or enter a positive scale to metres.");
  if (origin?.length !== 3 || rotation?.length !== 3) throw new Error("Placement requires three position and rotation values.");
  const position = origin.map(value => finite(value, "Position"));
  const angles = rotation.map(value => (finite(value, "Rotation") % 360) * Math.PI / 360);
  const [sx, sy, sz] = angles.map(Math.sin);
  const [cx, cy, cz] = angles.map(Math.cos);
  // Apply X, then Y, then Z rotations to source geometry, before translation.
  const quaternion = [cx * cy * cz + sx * sy * sz, sx * cy * cz - cx * sy * sz,
    cx * sy * cz + sx * cy * sz, cx * cy * sz - sx * sy * cz];
  return { id, unit_scale_to_m: factor, placement: { origin: position, rotation: quaternion } };
}

export async function uploadGeometry(action, file, options, { fetcher = fetch, maxBytes = DEFAULT_LIMIT } = {}) {
  if (!["preview", "store"].includes(action)) throw new Error("Unknown geometry action.");
  if (!file || !/\.(stl|step|stp)$/i.test(file.name)) throw new Error("Choose an STL, STEP or STP file.");
  if (file.size < 1 || file.size > maxBytes) throw new Error(`Geometry file must be 1 byte to ${Math.floor(maxBytes / 1024 / 1024)} MiB.`);
  const response = await fetcher(`/api/geometry/${action}`, {
    method: "POST", headers: { "Content-Type": "application/octet-stream",
      "X-Geometry-Name": encodeURIComponent(file.name), "X-Geometry-Options": JSON.stringify(options) }, body: file
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok || result.ok !== true) throw new Error(result.error || `Geometry ${action} refused (${response.status}).`);
  return result;
}

export function geometryPreviewState(preview) {
  const vertices = preview.metadata?.mesh_vertices_local;
  const faces = preview.metadata?.mesh_faces;
  if (!Array.isArray(vertices) || vertices.length < 3 || !vertices.every(point => Array.isArray(point) && point.length === 3 && point.every(Number.isFinite)) ||
      !Array.isArray(faces) || !faces.length || !faces.every(face => Array.isArray(face) && face.length === 3 && face.every(index => Number.isInteger(index) && index >= 0 && index < vertices.length))) {
    throw new Error("Studio returned no valid actual surface mesh.");
  }
  const factor = preview.unit_scale_to_m;
  const origin = preview.placement?.origin ?? [0, 0, 0];
  const quaternion = preview.placement?.rotation ?? [1, 0, 0, 0];
  if (!(factor > 0) || !Number.isFinite(factor) || origin.length !== 3 || !origin.every(Number.isFinite) || quaternion.length !== 4 || !quaternion.every(Number.isFinite)) throw new Error("Studio returned invalid placement or scale.");
  const norm = Math.hypot(...quaternion);
  if (!(norm > 1e-12) || !Number.isFinite(norm)) throw new Error("Studio returned an invalid rotation quaternion.");
  const [w, x, y, z] = quaternion.map(value => value / norm);
  const placed = vertices.map(point => {
    const [a, b, c] = point.map(value => value * factor);
    return [origin[0] + (1 - 2 * (y * y + z * z)) * a + 2 * (x * y - z * w) * b + 2 * (x * z + y * w) * c,
      origin[1] + 2 * (x * y + z * w) * a + (1 - 2 * (x * x + z * z)) * b + 2 * (y * z - x * w) * c,
      origin[2] + 2 * (x * z - y * w) * a + 2 * (y * z + x * w) * b + (1 - 2 * (x * x + y * y)) * c];
  });
  const bounds = [Infinity, Infinity, Infinity, -Infinity, -Infinity, -Infinity];
  for (const point of placed) for (let axis = 0; axis < 3; axis++) {
    bounds[axis] = Math.min(bounds[axis], point[axis]); bounds[axis + 3] = Math.max(bounds[axis + 3], point[axis]);
  }
  if (!bounds.every(Number.isFinite)) throw new Error("Placed geometry coordinates must be finite.");
  const objectId = `object:component:${preview.component_id}`;
  const assetId = `geometry:component:${preview.component_id}`;
  return createViewerState({ scene: {
    schema_version: "visualization.scene.v1", scene_id: "geometry_import_preview", model_id: "geometry_import_preview", bounds,
    objects: [{ id: objectId, entity_ref: `component:${preview.component_id}`, kind: "imported_component", name: preview.component_id,
      geometry_asset_id: assetId, layer_ids: ["imported_components"], metadata: { role: preview.role, status: "preview" } }],
    geometry_assets: [{ id: assetId, format: "mesh", bounds, object_ids: [objectId], generation_config: {
      vertices: placed, faces, color: "#64748b", opacity: 0.8, transparent: true, source: "studio.geometry.preview" } }],
    overlays: [], diagnostics: preview.diagnostics ?? []
  } });
}

export function initGeometryImport(dialog, { project, previewSurface, openEditor, fetcher = fetch }) {
  const form = dialog.querySelector("[data-geometry-options]");
  const fileInput = dialog.querySelector("[data-geometry-file]");
  const previewButton = dialog.querySelector("[data-geometry-preview]");
  const storeButton = dialog.querySelector("[data-geometry-store]");
  const output = dialog.querySelector("[data-geometry-details]");
  const status = dialog.querySelector("[data-geometry-status]");
  const snippet = dialog.querySelector("[data-geometry-python]");
  const saved = dialog.querySelector("[data-geometry-saved]");
  const viewport = dialog.querySelector("[data-geometry-viewport]");
  let capability = project?.geometry;
  let preview = null;
  let busy = false;

  function controls() {
    const available = Boolean(project && capability?.available);
    for (const field of form.elements) field.disabled = !available || busy;
    const step = /\.(step|stp)$/i.test(fileInput.files?.[0]?.name ?? "");
    for (const option of form.elements.units.options) option.disabled = step && !["", "mm", "custom"].includes(option.value);
    if (step && !["", "mm", "custom"].includes(form.elements.units.value)) form.elements.units.value = "";
    dialog.querySelector("[data-geometry-units-help]").textContent = step
      ? "STEP declared file units are normalized to millimetres. Choose Millimetres (0.001 m per coordinate), or Custom scale to deliberately override this."
      : "STL coordinates have no declared units. Choose the units used by the source model. STEP coordinates are normalized to millimetres by the importer.";
    previewButton.disabled = !available || busy;
    storeButton.disabled = !available || busy || !preview;
    dialog.querySelector("[data-geometry-custom-scale]").hidden = form.elements.units.value !== "custom";
    if (!available) status.textContent = capability?.reason || "Geometry import requires Tuba Studio.";
  }
  function invalidate() {
    preview = null; output.replaceChildren(); saved.hidden = true; viewport.hidden = true;
    status.textContent = ""; controls();
  }
  function options() {
    return geometryImportOptions({ id: form.elements.component_id.value.trim(), unit: form.elements.units.value,
      format: fileInput.files?.[0]?.name.split(".").at(-1),
      scale: form.elements.scale.value, origin: ["x", "y", "z"].map(axis => form.elements[`origin_${axis}`].value),
      rotation: ["x", "y", "z"].map(axis => form.elements[`rotation_${axis}`].value) });
  }
  function describe(result, placedBounds) {
    output.replaceChildren();
    const summary = document.createElement("p");
    const inspection = result.metadata?.inspection ?? {};
    summary.textContent = `${result.format} · ${result.role === "reference" ? "Reference geometry" : "STEP geometry for review"} · ${inspection.triangle_count ?? result.metadata.mesh_faces.length} triangles · ${inspection.vertex_count ?? result.metadata.mesh_vertices_local.length} vertices`;
    const bounds = document.createElement("p"); bounds.textContent = `Placed bounds (m): ${placedBounds.map(value => Number(value.toPrecision(6))).join(", ")}`;
    output.append(summary, bounds);
    const facts = document.createElement("p");
    facts.textContent = Object.entries(inspection).filter(([key]) => !["triangle_count", "vertex_count"].includes(key)).map(([key, value]) => `${key.replaceAll("_", " ")}: ${value}`).join(" · ");
    if (facts.textContent) output.append(facts);
    for (const diagnostic of result.diagnostics ?? []) {
      const row = document.createElement("p"); row.textContent = `${diagnostic.severity}: ${diagnostic.message}`; output.append(row);
    }
    for (const port of result.ports ?? []) {
      const row = document.createElement("p"); row.textContent = `Interface ${port.id ?? port.name ?? "candidate"}: ${port.status ?? "candidate"} · ${port.kind ?? ""}`; output.append(row);
    }
    if (result.ports?.length) {
      const note = document.createElement("p"); note.textContent = "Detected interfaces are candidates. Define and confirm the intended connections in Python."; output.append(note);
    }
  }
  async function run(action) {
    if (busy) return;
    busy = true; controls();
    try { await action(); } catch (error) { status.textContent = error.message; } finally { busy = false; controls(); }
  }
  fileInput.addEventListener("change", () => {
    const file = fileInput.files?.[0];
    if (file) form.elements.component_id.value = (file.name.replace(/\.(stl|step|stp)$/i, "").replace(/[^A-Za-z0-9_.-]/g, "_").replace(/^(?=[^A-Za-z_])/, "geometry_") || "geometry").slice(0, 64);
    invalidate();
  });
  form.addEventListener("input", invalidate);
  form.addEventListener("change", invalidate);
  form.addEventListener("submit", event => event.preventDefault());
  previewButton.addEventListener("click", () => run(async () => {
    const result = await uploadGeometry("preview", fileInput.files?.[0], options(), { fetcher, maxBytes: capability?.max_upload_bytes });
    const state = geometryPreviewState(result);
    describe(result, state.bounds); viewport.hidden = false;
    previewSurface(state, dialog.querySelector("[data-geometry-canvas]"));
    preview = result;
    status.textContent = "Preview ready.";
  }));
  storeButton.addEventListener("click", () => run(async () => {
    if (!preview) throw new Error("Preview this file and placement first.");
    const result = await uploadGeometry("store", fileInput.files?.[0], options(), { fetcher, maxBytes: capability?.max_upload_bytes });
    if (result.content_digest !== preview.content_digest || typeof result.python !== "string" || !result.python || typeof result.path !== "string") throw new Error("Stored geometry does not match the preview or has no Python call.");
    snippet.value = result.python; saved.hidden = false;
    dialog.querySelector("[data-geometry-path]").textContent = result.path;
    status.textContent = "Source stored.";
  }));
  dialog.querySelector("[data-geometry-copy]").addEventListener("click", () => run(async () => {
    if (!navigator.clipboard?.writeText) { snippet.focus(); snippet.select(); throw new Error("Select and copy the shown Python call."); }
    await navigator.clipboard.writeText(snippet.value); status.textContent = "Import call copied.";
  }));
  dialog.querySelector("[data-geometry-editor]").addEventListener("click", async () => { dialog.close(); await openEditor(); });
  controls();
  return async function refresh() {
    if (!project) return;
    try {
      const response = await fetcher("/api/project", { cache: "no-store" });
      const result = await response.json();
      if (!response.ok || result.ok !== true || !result.geometry) throw new Error("Studio geometry capability is unavailable.");
      capability = result.geometry; controls();
    } catch (error) { capability = null; controls(); status.textContent = error.message; }
  };
}
