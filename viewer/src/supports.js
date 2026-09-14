// What a support actually constrains, in one place.
//
// Two things ask this question and they used to answer it separately: the 3D
// glyph in renderer.js, which needs to know which cones to draw, and the
// Selected Evidence panel, which needs to say so in words. They disagreed - the
// glyph had a directionless rest holding the pipe sideways along Y while the
// solver wrote NOM_CMP='DZ' - so the answer lives here now and both read it.
//
// The states are the four the solver can produce, per aster_comm.py:
//   fixed    a bilateral DDL_IMPO - the DOF cannot move at all
//   one-way  a LIAISON_UNIL zone: carries compression, lifts off in tension
//   spring   a discrete element with stiffness, no DDL_IMPO of its own
//   free     nothing written for this DOF
export const DOF_AXES = Object.freeze(["X", "Y", "Z", "RX", "RY", "RZ"]);

const FREE = "free";
const FIXED = "fixed";
const SPRING = "spring";
const ONE_WAY = "one-way";

const EPSILON = 1e-12;

function directionOf(config) {
  const raw = config?.direction;
  if (!Array.isArray(raw)) return null;
  const axes = [0, 1, 2].map((index) => Number(raw[index]));
  if (!axes.every((value) => Number.isFinite(value))) return null;
  return axes.some((value) => Math.abs(value) > EPSILON) ? axes : null;
}

function stiffnessAxes(config) {
  const matrix = Array.isArray(config?.stiffness_matrix) ? config.stiffness_matrix.map(Number) : [];
  if (matrix.length > 0) {
    return DOF_AXES.map((_axis, index) => Number.isFinite(matrix[index]) && Math.abs(matrix[index]) > 0);
  }
  // A scalar stiffness needs a direction to mean anything; without one the
  // solver has no axis to hang the discrete element on, so nothing is claimed.
  const scalar = Number(config?.stiffness);
  const direction = directionOf(config);
  if (!Number.isFinite(scalar) || Math.abs(scalar) <= 0 || !direction) {
    return DOF_AXES.map(() => false);
  }
  return [...direction.map((value) => Math.abs(value) > EPSILON), false, false, false];
}

// An explicit blocked_dof list is the author overriding the type, so it wins.
// Anything but these falsy spellings counts as blocked - the same test
// aster_comm.py applies when it turns the list into DDL_IMPO entries.
function isBlockedDof(value) {
  return ![false, 0, "0", "x", "X", null, undefined].includes(value);
}

/**
 * The six DOF states for one support, ordered X, Y, Z, RX, RY, RZ.
 *
 * `config` is the support's generation_config or its scene metadata - both
 * carry the same keys (support_type, direction, stiffness, blocked_dof, ...).
 */
export function supportDofStates(config = {}) {
  const type = String(config.support_type ?? config.type ?? "custom").toLowerCase();
  const supportType = type === "fixed" ? "anchor" : type;
  const springs = stiffnessAxes(config);
  const withSprings = (states) =>
    states.map((state, index) => (state === FREE && springs[index] ? SPRING : state));

  if (Array.isArray(config.blocked_dof)) {
    return withSprings(DOF_AXES.map((_axis, index) => (isBlockedDof(config.blocked_dof[index]) ? FIXED : FREE)));
  }
  if (supportType === "anchor") {
    return DOF_AXES.map(() => FIXED);
  }
  if (supportType === "spring") {
    // No DDL_IMPO at all: a spring's only restraint is the discrete element,
    // so an axis without stiffness is genuinely free.
    return withSprings(DOF_AXES.map(() => FREE));
  }

  const direction = directionOf(config);
  if (supportType === "rest") {
    // Unilateral, and DEFI_CONTACT takes one NOM_CMP - aster_comm.py breaks
    // after the first nonzero component. A rest with no direction is DZ:
    // Tuba is Z-up and gravity is (0, 0, -1), so the shoe is underneath.
    const axis = direction ? direction.findIndex((value) => Math.abs(value) > EPSILON) : 2;
    return withSprings(DOF_AXES.map((_name, index) => (index === axis ? ONE_WAY : FREE)));
  }
  if (direction) {
    // A guide blocks every nonzero component of its direction, and only
    // translations - AFFE_CHAR_MECA writes DX/DY/DZ, never a rotation.
    return withSprings([
      ...direction.map((value) => (Math.abs(value) > EPSILON ? FIXED : FREE)),
      FREE,
      FREE,
      FREE
    ]);
  }
  // A guide with no direction, and the fallback for an unrecognised type: all
  // three translations, matching the DX=DY=DZ=0 branch in aster_comm.py.
  return withSprings([FIXED, FIXED, FIXED, FREE, FREE, FREE]);
}

/**
 * The DOFs the glyph should draw a restraint on: fixed and one-way both mean
 * "the solver holds this axis", which is what a cone on the axis claims.
 */
export function supportBlockedDofs(config = {}) {
  return supportDofStates(config).map((state) => state === FIXED || state === ONE_WAY);
}

export function isSupportConfig(config) {
  return String(config?.source ?? "").toLowerCase() === "tuba.support";
}
