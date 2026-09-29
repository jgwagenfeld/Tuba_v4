// The support glyph's visual vocabulary, in one place.
//
// The renderer paints support marks and the viewport key names them. When each
// side held its own copy, a colour change in one silently desynced the other and
// the key ended up naming a mark that was no longer on screen.
//
// Support glyphs are achromatic, and that is the point rather than a concession.
// Every hue in the scene belongs to the vector convention, where it carries one
// bit that matters: blue and teal are authored inputs, red and orange are
// Code_Aster results. The support glyphs were borrowing from both ends of that -
// a spring ring in the applied-force blue, a prescribed cone in the
// reaction-moment orange - so a reader could not tell an authored support from a
// solved reaction by looking at the mark, only by opening a panel.
//
// So hue now means exactly one thing and the three support marks differ by shape
// alone: solid paired cones for a restraint, rings for a spring, a single hollow
// cone for a prescribed movement. The key is where a shape is decoded, which is
// the honest arrangement for a shape-only language.
//
// A true neutral, not the cool slate #1f2937: "no colour" has to mean r == g == b,
// and a tinted grey is still a hue a reader can be misled by. Dark enough to read
// against the light ground the renderer paints.
export const SUPPORT_PART_COLORS = Object.freeze({
  restraint: "#262626",
  spring: "#262626",
  prescribed: "#262626"
});

export const SUPPORT_PART_LABELS = Object.freeze({
  restraint: "Restraint — authored input, solid cones on the held degrees of freedom",
  spring: "Support spring — authored input, rings at the support",
  prescribed: "Prescribed displacement — authored input, hollow cone, penalty stiffness"
});

// How each part is filled, which is the half of "shape" the primitive geometry
// cannot express. A prescribed movement is hollow where a restraint is solid, so
// the two are told apart even at the size a restraint glyph is drawn.
export const SUPPORT_PART_FILLS = Object.freeze({
  restraint: "solid",
  spring: "solid",
  prescribed: "hollow"
});

export const SUPPORT_PARTS = Object.freeze(["restraint", "spring", "prescribed"]);

const DOF_STATES = ["X", "Y", "Z", "RX", "RY", "RZ"];

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

/** The six restraint states, spelled out, for the inspector. */
export function describeDofStates(states) {
  const held = (Array.isArray(states) ? states : []).map(String)
    .map((state, index) => (state === "fixed" || state === "one-way" ? DOF_STATES[index] : null))
    .filter(Boolean);
  return held.length ? held.join(", ") : "";
}
