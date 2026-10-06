import { DEFAULT_UNIT_SYSTEM, formatQuantity } from "./units.js";

// The support glyph's visual vocabulary, in one place.
//
// The renderer paints support marks and the viewport key names them. When each
// side held its own copy, a colour change in one silently desynced the other and
// the key ended up naming a mark that was no longer on screen.
//
// The colours depend on the stage. Build is authoring and has no results, so
// each support role gets its own colour, the way other piping and FE programs
// mark restraints: gold restraint, green spring, orange prescribed movement.
// Green, not blue: members draw in blue in Build, and a blue coil vanished into
// the pipe it sat on.
//
// Review is achromatic. There, every hue belongs to the results and the vector
// convention: blue and teal are authored inputs, red and orange are Code_Aster
// results. The prescribed orange is the reaction-moment orange and gold sits on
// the warm end of the stress ramp, so in Review a coloured support could not be
// told from a solved reaction by looking at it. One neutral there, and shape
// does the work: solid paired cones for a restraint, a coil for a spring, a
// single hollow cone for a prescribed movement.
//
// A true neutral, not the cool slate #1f2937: "no colour" has to mean r == g == b,
// and a tinted grey is still a hue a reader can be misled by. Dark enough to read
// against the light ground the renderer paints.
export const SUPPORT_BUILD_COLORS = Object.freeze({
  restraint: "#daa520",
  spring: "#16a34a",
  prescribed: "#f97316"
});

export const SUPPORT_REVIEW_COLORS = Object.freeze({
  restraint: "#262626",
  spring: "#262626",
  prescribed: "#262626"
});

// The ground plate under a grounded support is not a role, so it is neutral in
// every stage: in Build a gold plate under a spring would claim a restraint the
// support does not have, and one the key never names.
export const SUPPORT_GROUND_COLOR = "#262626";

// The embedded canvas shows published reviews, so it takes Review's palette.
export function supportPartColors(stage) {
  return stage === "build" ? SUPPORT_BUILD_COLORS : SUPPORT_REVIEW_COLORS;
}

export const SUPPORT_PART_LABELS = Object.freeze({
  restraint: "Restraint — authored input, solid cones on the held degrees of freedom",
  spring: "Support spring — authored input, a coil along the sprung direction",
  prescribed: "Prescribed displacement — authored input, hollow cone pointing the way it moves"
});

export const SUPPORT_PARTS = Object.freeze(["restraint", "spring", "prescribed"]);

const DOF_STATES = ["X", "Y", "Z", "RX", "RY", "RZ"];

/**
 * The value badge a prescribed support carries: "ΔZ = 80 mm".
 *
 * Non-zero components only, so the badge names the movement and not five
 * zeros. Translations follow the active display units; rotations stay in rad,
 * the unit the result colouring states for DRX..DRZ. Null when nothing moves.
 */
export function prescribedDisplacementText(config, systemId = DEFAULT_UNIT_SYSTEM) {
  const imposed = Array.isArray(config?.imposed_displacement) ? config.imposed_displacement.map(Number) : [];
  const parts = imposed.slice(0, 6).flatMap((value, index) =>
    Number.isFinite(value) && value !== 0
      ? [`Δ${DOF_STATES[index]} = ${formatQuantity(value, index < 3 ? "m" : "rad", systemId)}`]
      : []
  );
  return parts.length ? parts.join(" · ") : null;
}

/**
 * Which support-glyph parts a support will actually be drawn with.
 *
 * Derived from the same fields the glyph is built from, so the key cannot name
 * a part the renderer chose not to draw. Springs are checked twice on purpose:
 * the renderer reads `stiffness_matrix` for its rings directly, so a bundle
 * carrying a stiffness but no `dof_states` would still get rings drawn - and a
 * key that trusted `dof_states` alone would list nothing for them.
 *
 * `dof_states` is the solver's own restraint record, not the authored direction,
 * so a guide that only holds one axis does not claim to hold six.
 */
export function supportParts(config) {
  const parts = [];
  const states = Array.isArray(config?.dof_states) ? config.dof_states.map(String) : [];
  if (states.some((state) => state === "fixed" || state === "one-way")) parts.push("restraint");
  const matrix = (Array.isArray(config?.stiffness_matrix) ? config.stiffness_matrix : []).map(Number);
  const scalarStiffness = Number(config?.stiffness);
  const hasStiffness = matrix.some((value) => Number.isFinite(value) && Math.abs(value) > 0)
    || (matrix.length === 0 && Number.isFinite(scalarStiffness) && Math.abs(scalarStiffness) > 0)
    || (Array.isArray(config?.spring_stiffness) && config.spring_stiffness.some((value) => Number(value) !== 0));
  if (states.some((state) => state === "spring") || hasStiffness) parts.push("spring");
  const imposed = Array.isArray(config?.imposed_displacement) ? config.imposed_displacement : null;
  if (imposed?.some((value) => Math.abs(Number(value)) > 0)) parts.push("prescribed");
  return parts;
}

/** Every support part visible in a scene, in key order, without duplicates. */
export function visibleSupportParts(state, visibleIds) {
  const present = new Set();
  for (const object of state.objects ?? []) {
    if (object.kind !== "support" || !visibleIds.has(object.id)) continue;
    const config = state.geometryAssets.find((asset) => asset.id === object.geometry_asset_id)?.generation_config;
    for (const part of supportParts(config)) present.add(part);
  }
  return SUPPORT_PARTS.filter((part) => present.has(part));
}
