// The bodies axis: which of the overlaid things on screen you are looking at.
//
// Layer categories answer "where did this come from" - authored, solved,
// returned, commented on. Bodies answer a different question, and the four are
// not a re-cut of the four categories: sub-points and the deformed shape both
// come back from the solver, yet a reviewer dims them independently, so they
// are separate bodies.
//
// Deformed is deliberately not a fourth solid. It is a transform of the 1D mesh
// drawn over the undeformed geometry, so it carries visibility but no opacity
// of its own - there is nothing behind it to see through to.
//
// Every number a body reports comes from the scene. A body the scene does not
// populate is omitted rather than shown empty, and a metric the bundle does not
// carry is dropped rather than guessed at.

import { categoryForLayerId, setLayerVisibility } from "./sceneLoader.js";
import { getVisualDeformationDisplayScale } from "./resultReview.js";
import { displayUnit, formatNumber, formatQuantity, formatValue, getUnitSystem } from "./units.js";

// What the opacity chip cycles through. 100% reads as "this is the subject",
// 60% as "this is context you can see through", 30% as "this is a ghost".
export const OPACITY_STEPS = Object.freeze([1, 0.6, 0.3]);

// The opacity geometry starts at when there is something underneath it worth
// seeing. Chosen once, at load: an opacity that shifted as you toggled other
// bodies would be impossible to reason about.
const GEOMETRY_CONTEXT_OPACITY = 0.6;

const BODY_SPECS = Object.freeze([
  {
    id: "geometry",
    label: "Geometry",
    description: "What the engineer authored. Real surface, real wall.",
    supportsOpacity: true
  },
  {
    id: "analysis_mesh",
    label: "Analysis mesh",
    description: "Elements on the centerline. No surface exists - the tube is swept from section properties.",
    supportsOpacity: true
  },
  {
    id: "subpoints",
    label: "Sub-points",
    description: "Where the stress actually lives. Projected onto the wall at their shell display positions.",
    supportsOpacity: true
  },
  {
    id: "deformed",
    label: "Deformed mesh",
    description: "A transform of the mesh, not a fourth body - it overlays the undeformed geometry.",
    supportsOpacity: false
  }
]);

export const BODY_ORDER = Object.freeze(BODY_SPECS.map((spec) => spec.id));

// Sub-points and deformed are picked out by name before the category rule runs,
// because both are "results" and the category alone cannot separate them.
export function bodyIdForLayerId(layerId, declaredCategory = null) {
  const id = String(layerId);
  if (id.includes("tuyau_subpoint")) return "subpoints";
  if (id.startsWith("deformed:")) return "deformed";
  const category = categoryForLayerId(id, declaredCategory);
  if (category === "design") return "geometry";
  if (category === "analysis_mesh") return "analysis_mesh";
  // Vectors, clashes, proposals and the rest are drawn, but they are not one of
  // the composited bodies. They stay reachable in the full layer tree.
  return null;
}

export function getBodies(state) {
  const claimed = new Map(BODY_ORDER.map((id) => [id, []]));
  for (const layer of Object.values(state.layers ?? {})) {
    const bodyId = bodyIdForLayerId(layer.id, layer.category);
    if (bodyId) claimed.get(bodyId).push(layer);
  }
  const bodies = [];
  for (const spec of BODY_SPECS) {
    const layers = claimed.get(spec.id);
    // A layer that gates nothing (the mesh identity badge) describes the body
    // rather than drawing it, so it must not make an absent body look present.
    const gates = layers.filter((layer) => layer.count > 0);
    if (gates.length === 0) continue;
    const visibles = gates.map((layer) => layer.visible !== false);
    bodies.push({
      ...spec,
      layerIds: gates.map((layer) => layer.id),
      visible: visibles.every(Boolean),
      partiallyVisible: !visibles.every(Boolean) && visibles.some(Boolean),
      opacity: spec.supportsOpacity ? bodyOpacity(state, spec.id) : 1,
      badge: badgeForBody(state, spec.id),
      metrics: metricsForBody(state, spec.id)
    });
  }
  return bodies;
}

export function setBodyVisibility(state, bodyId, visible) {
  const body = getBodies(state).find((candidate) => candidate.id === bodyId);
  if (!body) return state;
  let next = state;
  for (const layerId of body.layerIds) {
    next = setLayerVisibility(next, layerId, visible);
  }
  return next;
}

export function setBodyOpacity(state, bodyId, opacity) {
  const value = Number(opacity);
  if (!Number.isFinite(value)) return state;
  return {
    ...state,
    bodyOpacity: { ...(state.bodyOpacity ?? {}), [bodyId]: clamp(value, 0, 1) }
  };
}

export function cycleBodyOpacity(state, bodyId) {
  const current = bodyOpacity(state, bodyId);
  const index = OPACITY_STEPS.findIndex((step) => Math.abs(step - current) < 1e-9);
  const next = OPACITY_STEPS[(index + 1) % OPACITY_STEPS.length];
  return setBodyOpacity(state, bodyId, next);
}

export function bodyOpacity(state, bodyId) {
  const stored = Number(state.bodyOpacity?.[bodyId]);
  return Number.isFinite(stored) ? clamp(stored, 0, 1) : 1;
}

// Seed the defaults once, on load. Left to itself the state has no bodyOpacity
// and every body reads as fully opaque, which is the right answer for a scene
// with nothing to see through to.
export function withDefaultBodyOpacity(state) {
  return state.bodyOpacity ? state : { ...state, bodyOpacity: createBodyOpacityState(state) };
}

export function createBodyOpacityState(state) {
  const present = new Set();
  for (const layer of Object.values(state.layers ?? {})) {
    if (!(layer.count > 0)) continue;
    const bodyId = bodyIdForLayerId(layer.id, layer.category);
    if (bodyId) present.add(bodyId);
  }
  const seesThrough = present.has("analysis_mesh") || present.has("subpoints");
  return {
    geometry: seesThrough ? GEOMETRY_CONTEXT_OPACITY : 1,
    analysis_mesh: 1,
    subpoints: 1
  };
}

// Called once per asset while the scene graph is built: which body owns this,
// and how far down has the reviewer dimmed it?
export function bodyOpacityForObjectIds(state, objectIds = []) {
  for (const objectId of objectIds) {
    for (const layerId of state.objectLayerIds?.[objectId] ?? []) {
      const bodyId = bodyIdForLayerId(layerId, state.layers?.[layerId]?.category);
      const spec = BODY_SPECS.find((candidate) => candidate.id === bodyId);
      if (spec?.supportsOpacity) {
        return bodyOpacity(state, bodyId);
      }
    }
  }
  return null;
}

// --- what the scene says about each body -----------------------------------

export function getMeshIdentity(state) {
  return Object.values(state.layers ?? {}).find((layer) => layer.meshIdentity)?.meshIdentity ?? null;
}

export function getSubpointOverlay(state) {
  return (state.overlays ?? []).find((overlay) => overlay.data?.result_type === "tuyau_subpoints") ?? null;
}

export function getSectionProfile(state) {
  return getSubpointOverlay(state)?.data?.section_profile ?? null;
}

// The section panel explains the sub-point field, whichever field happens to be
// tinting the scene right now. Colouring its rosette against the active legend
// would clamp every station to one end of a range that belongs to a different
// quantity, and label the peak with that quantity's unit.
export function getSubpointLegend(state) {
  const data = getSubpointOverlay(state)?.data;
  if (!data) return null;
  const range = data.legend?.range ?? data.range;
  if (!range || !Number.isFinite(Number(range.min)) || !Number.isFinite(Number(range.max))) return null;
  return {
    field: data.legend?.field ?? data.field ?? "TUYAU sub-point",
    unit: data.legend?.unit ?? data.unit ?? "",
    range: { min: Number(range.min), max: Number(range.max) }
  };
}

// The bend-chord check, as the scene states it. Null whenever the mesh has no
// bends: there is no vacuous pass to report.
export function getDiscretisationCheck(state) {
  return getMeshIdentity(state)?.discretisation ?? null;
}

function badgeForBody(state, bodyId) {
  if (bodyId === "geometry") return { text: "3D solid", tone: "neutral" };
  if (bodyId === "analysis_mesh") {
    const dim = getMeshIdentity(state)?.topological_dim;
    return Number.isFinite(dim) && dim >= 0
      ? { text: `${dim}D`, tone: "accent" }
      : { text: "mesh", tone: "neutral" };
  }
  if (bodyId === "subpoints") {
    // 1D topology, results recovered around and through the wall. "2.5D" is
    // the shorthand the layer-structure design record uses for exactly this.
    return { text: "2.5D", tone: "accent" };
  }
  const stateType = deformedGeometryState(state)?.data?.state_type;
  return { text: stateType ? String(stateType).toUpperCase() : "deformed", tone: "neutral" };
}

function metricsForBody(state, bodyId) {
  if (bodyId === "geometry") return geometryMetrics(state);
  if (bodyId === "analysis_mesh") return meshMetrics(state);
  if (bodyId === "subpoints") return subpointMetrics(state);
  return deformedMetrics(state);
}

function geometryMetrics(state) {
  const objectIds = new Set();
  for (const layer of Object.values(state.layers ?? {})) {
    if (bodyIdForLayerId(layer.id, layer.category) !== "geometry") continue;
    for (const objectId of layer.objectIds ?? []) objectIds.add(objectId);
  }
  // Only things that are actually drawn. Result-state and geometry-state records
  // are metadata objects carrying no geometry, and a legacy bundle with no
  // declared layers files them under design, where they would otherwise be
  // tallied as authored content ("2 geometry state - 1 result state").
  const objects = (state.objects ?? []).filter((obj) => objectIds.has(obj.id) && obj.geometry_asset_id);
  const counts = new Map();
  for (const obj of objects) {
    const kind = obj.kind || "object";
    counts.set(kind, (counts.get(kind) ?? 0) + 1);
  }
  const tally = [...counts.entries()]
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
    .slice(0, 3)
    .map(([kind, count]) => `${count} ${kind.replace(/_/g, " ")}`)
    .join(" · ");

  const metrics = [];
  if (tally) metrics.push(tally);
  const section = sectionDimensions(objects, getUnitSystem(state));
  if (section) metrics.push(section);
  return metrics;
}

// Profile dimensions are stored in metres; the unit chip decides how they read.
function sectionDimensions(objects, system) {
  const profile = objects.map((obj) => obj.metadata?.profile).find((candidate) => candidate?.outer_diameter_m);
  if (!profile) return null;
  const lengths = [["OD", profile.outer_diameter_m], ["WT", profile.wall_thickness_m]];
  const bend = objects.map((obj) => obj.metadata?.bend_geometry).find((candidate) => candidate?.radius);
  if (bend) lengths.push(["R", bend.radius]);
  // Three lengths in a row, so the unit is stated once at the end rather than
  // repeated after each: "OD 114.3 · WT 6.02 · R 342.9 mm".
  const parts = lengths
    .filter(([, value]) => Number.isFinite(Number(value)))
    .map(([label, value]) => `${label} ${formatValue(value, "m", system)}`);
  return parts.length > 0 ? `${parts.join(" · ")} ${displayUnit("m", system)}` : null;
}

function meshMetrics(state) {
  const identity = getMeshIdentity(state);
  if (!identity) return [];
  const parts = [];
  const family = identity.element_families?.[0];
  if (family) {
    parts.push(`${family.element_count} ${family.family}`);
  } else if (Number.isFinite(identity.element_count)) {
    parts.push(`${identity.element_count} elements`);
  }
  if (Number.isFinite(identity.node_count)) parts.push(`${identity.node_count} nodes`);
  const modelisations = (identity.modelisations ?? []).map((entry) => entry.modelisation).filter(Boolean);
  if (modelisations.length > 0) parts.push(modelisations.join(" + "));
  return parts.length > 0 ? [parts.join(" · ")] : [];
}

function subpointMetrics(state) {
  const overlay = getSubpointOverlay(state);
  if (!overlay) return [];
  const data = overlay.data ?? {};
  const metrics = [];
  const profile = data.section_profile;
  if (profile) {
    metrics.push(`${profile.sectors} sectors × ${profile.layers} layers · NSEC ${profile.nsec} · NCOU ${profile.ncou}`);
  }
  const rendered = Number(data.rendered_count);
  const total = Number(data.total_count);
  if (Number.isFinite(rendered)) {
    // Say so when the scene drew fewer than it read: a silently truncated field
    // reads as complete coverage.
    metrics.push(
      Number.isFinite(total) && total > rendered
        ? `${rendered} of ${total} points drawn`
        : `${rendered} points`
    );
  }
  return metrics;
}

function deformedMetrics(state) {
  const metrics = [];
  const peak = peakDisplacement(state);
  if (peak) {
    const magnitude = formatQuantity(peak.value, "m", getUnitSystem(state));
    metrics.push(`max |D| ${magnitude}${peak.nodeId ? ` at ${peak.nodeId}` : ""}`);
  }
  // The scale the shape is *drawn* at, not the one the bundle was built at: the
  // deform slider overrides the latter, and a body claiming x50 while the bar
  // reads x1 is the kind of mismatch a screenshot carries away.
  const scale = getVisualDeformationDisplayScale(state);
  if (scale > 1) {
    metrics.push(`drawn at ×${formatNumber(scale)} (display only)`);
  }
  return metrics;
}

function peakDisplacement(state) {
  const overlay = (state.overlays ?? []).find((candidate) => candidate.data?.result_type === "displacement");
  const values = overlay?.data?.values ?? {};
  let best = null;
  for (const [nodeId, raw] of Object.entries(values)) {
    const value = Array.isArray(raw) ? Math.hypot(...raw.slice(0, 3).map(Number)) : Number(raw);
    if (!Number.isFinite(value)) continue;
    if (!best || value > best.value) best = { nodeId, value };
  }
  return best;
}

// The deformed body draws whichever geometry state carries deformed layers, so
// its badge and scale must describe that state. Reading the *active* state made
// the body announce itself as COLD whenever the cold state happened to be
// selected, which is the one thing it is definitely not showing.
function deformedGeometryState(state) {
  const states = state.geometryStates ?? [];
  const isDeformed = (overlay) => {
    const data = overlay.data ?? {};
    return data.purpose === "visualization" || !["cold", "design"].includes(String(data.state_type ?? ""));
  };
  const active = states.find((overlay) => (overlay.data?.id ?? overlay.id) === state.activeGeometryStateId);
  if (active && isDeformed(active)) return active;
  return states.find(isDeformed) ?? active ?? states[0] ?? null;
}

// --- the coloured-scale readout the panel shares with the legend ------------

export function getSubpointPeak(state) {
  const peak = getSubpointOverlay(state)?.data?.peak;
  if (!peak) return null;
  const parts = [];
  if (peak.element_id) parts.push(peak.element_id);
  if (Number.isFinite(Number(peak.angle_deg))) parts.push(`${formatNumber(peak.angle_deg)}°`);
  if (peak.wall_position) parts.push(String(peak.wall_position).replace(/_/g, " "));
  return { ...peak, location: parts.join(" · ") };
}

// Where each drawn sub-point sits on the rosette, for the section diagram.
// Returns an empty list when the bundle has no decoded stations - the diagram
// then draws the grid alone rather than inventing placements.
export function getSubpointStations(state) {
  const overlay = getSubpointOverlay(state);
  if (!overlay) return [];
  const asset = (state.geometryAssets ?? []).find((candidate) =>
    (candidate.object_ids ?? []).some((id) => (overlay.object_ids ?? []).includes(id))
  );
  if (!asset) return [];
  // A sub-point asset's bulk config is written to its own payload file and the
  // scene entry keeps only a pointer, so the two have to be merged the same way
  // the renderer merges them.
  const payload = (state.geometryPayloads ?? []).find((candidate) => candidate.asset_id === asset.id);
  const config = { ...(payload?.generation_config ?? {}), ...(asset.generation_config ?? {}) };
  const sectors = config.sector_indices ?? [];
  const layers = config.layer_indices ?? [];
  const values = config.values ?? [];
  const stations = [];
  for (let index = 0; index < sectors.length; index += 1) {
    if (!Number.isFinite(Number(sectors[index])) || !Number.isFinite(Number(layers[index]))) continue;
    stations.push({
      sectorIndex: Number(sectors[index]),
      layerIndex: Number(layers[index]),
      value: Number(values[index])
    });
  }
  return stations;
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}
