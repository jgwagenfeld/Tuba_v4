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
    id: "insulation",
    label: "Insulation",
    description: "Assigned insulation: included in weight, wind diameter and clearance checks.",
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

// Overlays are the marks drawn on the model rather than bodies with extent, so
// a scale factor is meaningful for them and an opacity is not - the same line
// supportsOpacity already draws through BODY_SPECS. They are listed here
// because every one of them used to be reachable only as a checkbox in the
// layer tree, inside the rail-foot popover, filed under whichever category its
// layer id happened to start with.
//
// Supports carry no layer_ids of their own; layerIdsForObject falls back to the
// object kind, which is why "support" is both the fallback id and the id the
// bundle declares.
const OVERLAY_SPECS = Object.freeze([
  {
    id: "support",
    label: "Supports & BCs",
    description: "Restraints and boundary conditions as the solver received them.",
    layerIds: ["support"]
  },
  {
    id: "support_link",
    label: "Support attachments",
    description: "Which structure each attached support acts against. Ground supports carry a hatch instead.",
    layerIds: ["support_link"]
  },
  {
    id: "applied_force",
    label: "Applied forces",
    description: "Nodal forces applied to the model.",
    layerIds: ["design:loads:forces"]
  },
  {
    id: "applied_moment",
    label: "Applied moments",
    description: "Nodal moments applied to the model.",
    layerIds: ["design:loads:moments"]
  },
  {
    id: "applied_line_load",
    label: "Applied line loads",
    description: "Distributed line loads applied along elements.",
    layerIds: ["design:loads:line_loads"]
  },
  {
    id: "reaction_force",
    label: "Reaction forces",
    description: "Reaction forces at the restrained degrees of freedom.",
    layerIds: ["result:reaction_force"],
    vectorType: "reaction"
  },
  {
    id: "reaction_moment",
    label: "Reaction moments",
    description: "Reaction moments, right-hand rule.",
    layerIds: ["result:reaction_moment"],
    vectorType: "moment"
  },
  {
    id: "displacement",
    label: "Displacements",
    description: "Nodal displacement vectors.",
    layerIds: ["result:displacement"],
    vectorType: "displacement"
  },
  // The one mark the scene does not carry a layer for: the renderer draws the
  // grid from the model bounds, so there is nothing to gate it with. It is
  // still a thing on screen the reviewer wants off, so it gets a row and a
  // state flag of its own.
  //
  // Named for the grid alone. The design called this row "Global axes & grid",
  // but renderer.js draws no axes helper - deliberately, the corner view gizmo
  // is the orientation indicator - and a row must not promise a mark that is
  // never drawn.
  {
    id: "ground_grid",
    label: "Ground grid",
    description: "The reference plane under the model. Orientation is on the corner gizmo.",
    stateKey: "referenceGridVisible"
  }
]);

export const OVERLAY_ORDER = Object.freeze(OVERLAY_SPECS.map((spec) => spec.id));

// The steps the scale chip cycles. Inside the 0-5 range the vector sliders
// already used, so a chip and a slider can never disagree about what is legal.
export const VECTOR_SCALE_STEPS = Object.freeze([0.5, 1, 2, 5]);

export function vectorScale(state, vectorType) {
  const stored = Number(state.resultVectorScales?.[vectorType]);
  return Number.isFinite(stored) ? stored : 1;
}

// Mirrors getBodies: an overlay the scene does not populate is omitted rather
// than shown empty.
export function getOverlays(state) {
  const overlays = [];
  for (const spec of OVERLAY_SPECS) {
    // Viewer chrome rather than scene content: always offered, because the
    // renderer always draws it. It has no layer to count, so it carries no
    // badge.
    if (spec.stateKey) {
      overlays.push({
        ...spec,
        layerIds: [],
        count: null,
        visible: state[spec.stateKey] !== false,
        partiallyVisible: false,
        scale: null
      });
      continue;
    }
    const gates = spec.layerIds
      .map((layerId) => state.layers?.[layerId])
      .filter((layer) => layer && layer.count > 0);
    if (gates.length === 0) continue;
    const visibles = gates.map((layer) => layer.visible !== false);
    overlays.push({
      ...spec,
      layerIds: gates.map((layer) => layer.id),
      count: gates.reduce((total, layer) => total + layer.count, 0),
      visible: visibles.every(Boolean),
      partiallyVisible: !visibles.every(Boolean) && visibles.some(Boolean),
      scale: spec.vectorType ? vectorScale(state, spec.vectorType) : null
    });
  }
  return overlays;
}

export function setOverlayVisibility(state, overlayId, visible) {
  const overlay = getOverlays(state).find((candidate) => candidate.id === overlayId);
  if (!overlay) return state;
  if (overlay.stateKey) return { ...state, [overlay.stateKey]: visible };
  return setLayersVisible(state, overlay.layerIds, visible);
}

export function cycleVectorScale(scale) {
  const index = VECTOR_SCALE_STEPS.findIndex((step) => Math.abs(step - scale) < 1e-9);
  return VECTOR_SCALE_STEPS[(index + 1) % VECTOR_SCALE_STEPS.length];
}

function setLayersVisible(state, layerIds, visible) {
  let next = state;
  for (const layerId of layerIds) {
    next = setLayerVisibility(next, layerId, visible);
  }
  return next;
}

// Sub-points and deformed are picked out by name before the category rule runs,
// because both are "results" and the category alone cannot separate them.
export function bodyIdForLayerId(layerId, declaredCategory = null) {
  const id = String(layerId);
  if (id === "physical_envelope:insulation") return "insulation";
  if (id.startsWith("physical_envelope:") || id === "overlay:physical_envelope") return null;
  if (id.includes("tuyau_subpoint")) return "subpoints";
  if (id.startsWith("deformed:")) return "deformed";
  if (id === "analysis_mesh:helpers") return null;
  const category = categoryForLayerId(id, declaredCategory);
  if (category === "design") return "geometry";
  if (category === "analysis_mesh") return "analysis_mesh";
  // Vectors, clashes, proposals and the rest are drawn, but they are not one of
  // the composited bodies. The marks a reviewer actually reaches for are in
  // OVERLAY_SPECS above; everything else stays reachable in the full layer tree.
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
  let nextState = setLayersVisible(state, body.layerIds, visible);
  if (bodyId === "analysis_mesh") {
    const currentGeoOpacity = bodyOpacity(nextState, "geometry");
    if (visible && Math.abs(currentGeoOpacity - 1.0) < 1e-4) {
      nextState = setBodyOpacity(nextState, "geometry", 0.35);
    } else if (!visible && Math.abs(currentGeoOpacity - 0.35) < 1e-4) {
      nextState = setBodyOpacity(nextState, "geometry", 1.0);
    }
  }
  return nextState;
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
  const meshVisible = Object.values(state.layers ?? {}).some(
    (layer) => layer.category === "analysis_mesh" && layer.count > 0 && layer.visible !== false
  );
  const subpointsVisible = Object.values(state.layers ?? {}).some(
    (layer) => layer.id?.includes("tuyau_subpoint") && layer.count > 0 && layer.visible !== false
  );
  const seesThrough = meshVisible || subpointsVisible;
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
  return (state.overlays ?? []).find((overlay) => overlay.data?.result_type === "tuyau_subpoints" &&
    (!state.activeResultStateId || !overlay.data?.result_state_id || overlay.data.result_state_id === state.activeResultStateId)) ?? null;
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
  if (bodyId === "insulation") return { text: "physical", tone: "neutral" };
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
  if (bodyId === "insulation") {
    return [...new Set((state.objects ?? []).flatMap((obj) => {
      const spec = obj.metadata?.insulation;
      return spec ? [`${spec.material} · ${formatQuantity(spec.thickness_m, "m", getUnitSystem(state))}`] : [];
    }))];
  }
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

// --- how the sub-point field is drawn ---------------------------------------
//
// A TUYAU element is 1D: its stress is recovered at 33 circumferential
// stations across 7 layers through the wall, not on a surface. Drawing all 231
// of those per node as ticks inside an opaque pipe is the honest picture and a
// useless one - the pipe hides every layer but the outer one, and the rest
// accumulate into an even grey band that ranks nothing.
//
// So there are two ways to draw it, and the scene carries every point either
// way. Which points reach the screen is a display decision, made here, and it is
// always reported in the body metrics - a field that silently drops points reads
// as complete coverage.
//
//   measured  every point, depth-tested, at its wall position. Complete, and
//             honest about the occlusion.
//   peak      only points in the top of the colour range, drawn through the pipe
//             (x-ray). Fewer marks, so the ones that survive are readable, and
//             legible through the wall - which is the whole point, because the
//             worst stations are often in the bore.

export const SUBPOINT_MODES = Object.freeze([
  { id: "peak", label: "Peak", xray: true, description: "Top of the range, drawn through the wall." },
  { id: "measured", label: "Measured", xray: false, description: "Every sub-point, at the wall, complete." }
]);

// What fraction of the colour range has to be exceeded before a point is drawn in
// peak mode. These are the cuts a reviewer actually asks for, not a continuous
// slider: each one is a sentence ("the worst fifth").
export const SUBPOINT_THRESHOLD_STEPS = Object.freeze([0.5, 0.65, 0.8, 0.9, 0.95]);
export const DEFAULT_SUBPOINT_THRESHOLD = 0.8;
export const DEFAULT_SUBPOINT_MODE = "peak";

export function subpointMode(state) {
  const id = String(state.subpointMode ?? DEFAULT_SUBPOINT_MODE);
  return SUBPOINT_MODES.some((mode) => mode.id === id) ? id : DEFAULT_SUBPOINT_MODE;
}

export function subpointModeSpec(state) {
  return SUBPOINT_MODES.find((mode) => mode.id === subpointMode(state)) ?? SUBPOINT_MODES[0];
}

export function subpointThreshold(state) {
  const stored = Number(state.subpointThreshold);
  if (!Number.isFinite(stored)) return DEFAULT_SUBPOINT_THRESHOLD;
  return Math.min(Math.max(stored, 0), 1);
}

export function setSubpointMode(state, modeId) {
  const id = String(modeId);
  if (!SUBPOINT_MODES.some((mode) => mode.id === id)) return state;
  if (id === subpointMode(state)) return state;
  return { ...state, subpointMode: id };
}

export function cycleSubpointMode(state) {
  const index = SUBPOINT_MODES.findIndex((mode) => mode.id === subpointMode(state));
  return setSubpointMode(state, SUBPOINT_MODES[(index + 1) % SUBPOINT_MODES.length].id);
}

export function cycleSubpointThreshold(state) {
  const current = subpointThreshold(state);
  const index = SUBPOINT_THRESHOLD_STEPS.findIndex((step) => Math.abs(step - current) < 1e-9);
  // Start from the nearest step above the current value when the stored one is
  // not on a step, so the first click moves up rather than jumping somewhere.
  const next = index >= 0
    ? SUBPOINT_THRESHOLD_STEPS[(index + 1) % SUBPOINT_THRESHOLD_STEPS.length]
    : SUBPOINT_THRESHOLD_STEPS.find((step) => step > current + 1e-9) ?? SUBPOINT_THRESHOLD_STEPS[0];
  return { ...state, subpointThreshold: next };
}

// The one definition of "does this point get drawn", shared with the renderer so
// the count the metrics report is the count that reaches the screen.
export function subpointPassesThreshold(value, threshold) {
  if (threshold === null || !Number.isFinite(threshold)) return true;
  // A point with no value is not a low point. It is missing, and it is kept:
  // dropping it would quietly thin the field in exactly the runs that failed to
  // converge. Note the explicit null check - `Number(null)` is 0, so an absent
  // value read naively becomes the coldest mark on the ramp and the one a
  // threshold throws away first.
  if (value === null || value === undefined || value === "") return true;
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return true;
  return numeric >= threshold;
}

// Whether a sub-point carries a value at all, for the same reason: it is not a
// zero, and it must not be painted as one.
export function hasSubpointValue(value) {
  if (value === null || value === undefined || value === "") return false;
  return Number.isFinite(Number(value));
}

export function subpointThresholdValue(fraction, rangeMax) {
  if (!Number.isFinite(fraction) || !Number.isFinite(rangeMax)) return null;
  return Number(rangeMax) * Math.min(Math.max(fraction, 0), 1);
}

// The top of the range the field is coloured against, resolved the way
// `subpointLegend` resolves it in the renderer - the overlay's legend, then the
// asset's own range, then the values themselves. Resolving it differently on
// this side would let the body quote a count the screen does not show.
function subpointRangeMax(state) {
  const legendMax = Number(getSubpointLegend(state)?.range?.max);
  if (Number.isFinite(legendMax)) return legendMax;
  const config = subpointFieldConfig(state);
  const configMax = Number(config?.range?.max ?? config?.legend?.range?.max);
  if (Number.isFinite(configMax)) return configMax;
  const values = (config?.values ?? []).filter(hasSubpointValue).map(Number);
  return values.length > 0 ? Math.max(...values) : null;
}

export function subpointValueCutoff(state) {
  if (subpointModeSpec(state).xray !== true) return null;
  return subpointThresholdValue(subpointThreshold(state), subpointRangeMax(state));
}

// The sub-point field's bulk config, merged the way the renderer merges it: a
// sub-point asset's arrays live in their own payload file and the scene entry
// keeps only a pointer, so reading the manifest alone finds no values at all.
function subpointFieldConfig(state) {
  const overlay = getSubpointOverlay(state);
  const asset = (state.geometryAssets ?? []).find((candidate) =>
    (candidate.object_ids ?? []).some((id) => (overlay?.object_ids ?? []).includes(id))
  ) ?? (state.geometryAssets ?? []).find((candidate) => candidate.format === "tuyau_subpoint_glyphs");
  if (!asset) return null;
  const payload = (state.geometryPayloads ?? []).find((candidate) => candidate.asset_id === asset.id);
  return { ...(payload?.generation_config ?? {}), ...(asset.generation_config ?? {}) };
}

// How many of the scene's sub-points this mode actually draws, so the body can
// say "N of M" instead of the bundle's own rendered_count, which counts the
// points the scene carries and not the ones on screen.
export function getSubpointDrawnCount(state) {
  const cutoff = subpointValueCutoff(state);
  if (cutoff === null) return null;
  const values = subpointFieldConfig(state)?.values;
  if (!Array.isArray(values)) return null;
  return values.reduce((count, value) => count + (subpointPassesThreshold(value, cutoff) ? 1 : 0), 0);
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
  const total = Number(data.total_count);
  const cutoff = subpointValueCutoff(state);
  const drawn = cutoff === null ? Number(data.rendered_count) : getSubpointDrawnCount(state);
  const mode = subpointModeSpec(state);
  if (Number.isFinite(drawn)) {
    // Say so when fewer points reach the screen than the scene read: a silently
    // thinned field reads as complete coverage.
    const prefix = cutoff === null ? "" : `top ${Math.round(subpointThreshold(state) * 100)}% · `;
    metrics.push(
      Number.isFinite(total) && total > drawn
        ? `${prefix}${drawn} of ${total} points drawn`
        : `${prefix}${drawn} points`
    );
  }
  if (mode.xray) {
    metrics.push("drawn through the wall");
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
  const overlay = (state.overlays ?? []).find((candidate) => candidate.data?.result_type === "displacement" &&
    (!state.activeResultStateId || !candidate.data?.result_state_id || candidate.data.result_state_id === state.activeResultStateId));
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
