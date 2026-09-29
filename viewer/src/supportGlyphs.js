// The support glyph's visual vocabulary, in one place.
//
// The renderer paints three materials and the viewport key names them. When each
// side held its own copy, a colour change in one silently desynced the other and
// the key ended up naming a mark that was no longer on screen. The key also has
// to say "authored input" the way the applied-load rows do, because every other
// coloured arrow in the scene is a Code_Aster result and a reader cannot tell an
// input from a result by hovering.
//
// Two of these hues are shared with the vector convention - the spring blue is
// the applied-force blue and the prescribed orange is the reaction-moment orange.
// That collision predates this module and is left alone here because the
// screenshot baselines in the Pages build are keyed to those exact colours;
// the rows below are what make the marks resolvable, not a sixth hue.

export const SUPPORT_PART_COLORS = Object.freeze({
  restraint: "#daa520",
  spring: "#2563eb",
  prescribed: "#f97316"
});

export const SUPPORT_PART_LABELS = Object.freeze({
  restraint: "Restraint — authored input, degrees of freedom held",
  spring: "Support spring — authored input, stiffness to ground",
  prescribed: "Prescribed displacement — authored input, penalty stiffness"
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
