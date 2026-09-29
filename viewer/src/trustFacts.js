// The two facts a reviewer should never have to go looking for.
//
// 1. Does the reaction set balance the load set? The incumbents in this category
//    cannot answer this at all - Femap offers a free-body tool, PrePoMax has to
//    be worked around with a nodal history output request and `Totals = Only` -
//    and the complaint it answers is the one on Eng-Tips: "I can take just about
//    any piping system and code it so that it passes or fails." A number showing
//    the reactions against the loads is evidence, not a verdict, and it is drawn
//    only from terms the bundle actually carries.
//
// 2. What population is the colour ramp's maximum taken over? Averaging is the
//    most consequential display setting in structural FEA and almost never a
//    first-class control: ANSYS buries it in a dropdown as Nodal Difference /
//    Nodal Fraction, and Nastran's own documentation notes that Simcenter and
//    Femap compute a "nodal average" in different orders, so the same model
//    yields different numbers in the two tools. The cell stress field is a
//    maximum over the two element ends; a sub-point field is a measured value
//    with the wall between points interpolated. Saying which, at strip weight,
//    is cheaper than the alternative - a screenshot with no basis on it.
//
// Neither of these is a code check. Neither claims pass or fail.

const ZERO = Object.freeze([0, 0, 0]);

// Component order is [X, Y, Z] throughout the scene, and this is the same
// cross product contactReview.js uses for the friction tangents. Matching it
// rather than deriving an order from the scene's coordinate_system keeps the
// moment arm in the same frame as the glyphs the reviewer is looking at.
const cross = (a, b) => [
  a[1] * b[2] - a[2] * b[1],
  a[2] * b[0] - a[0] * b[2],
  a[0] * b[1] - a[1] * b[0]
];

// Residual at or below this share of the summed term magnitudes reads as
// balanced. Chosen to sit above solver round-off and below anything a real
// mis-assembly produces; it labels a number, it does not enforce a code limit.
const BALANCE_TOLERANCE = 0.01;

export function isBalanced(ratio, tolerance = BALANCE_TOLERANCE) {
  return Number.isFinite(ratio) && ratio <= tolerance;
}

export function getReactionConsistency(state, overlays) {
  const reactionForce = overlays?.reactionForce ?? null;
  const reactionMoment = overlays?.reactionMoment ?? null;
  if (!reactionForce && !reactionMoment) {
    return null;
  }
  const loadCase = overlays?.loadCaseDefinition ?? null;
  const applied = authoredLoads(state, overlays?.loadCase ?? null);

  // Reactions act at their own nodes, so the moment balance is only closed by
  // carrying the applied forces to the same origin. Summing applied nodal
  // moments alone would be the kind of number that looks like a residual and is
  // not one.
  const appliedForce = addAll(applied.forces.map((entry) => entry.components));
  const appliedMomentAboutOrigin = addAll([
    ...applied.moments.map((entry) => entry.components),
    ...applied.forces.map((entry) => cross(entry.position ?? ZERO, entry.components))
  ]);
  const summedReactionForce = addAll(reactionForce ? Object.values(reactionForce) : []);
  const summedReactionMoment = addAll(reactionMoment ? Object.values(reactionMoment) : []);

  // Both residuals are sums, not differences: at a held node the support
  // reaction and the applied load cancel, so the quantity that should be zero
  // is their sum. Summing the moment residual instead would report 100 N-m for
  // a perfectly balanced 50 N-m couple.
  const residualForce = add(summedReactionForce, appliedForce);
  const residualMoment = add(summedReactionMoment, appliedMomentAboutOrigin);

  // The denominator is the total the residual is measured against. Using the
  // summed magnitudes rather than the resultant keeps a balanced-but-large load
  // set from scoring better than a small unbalanced one.
  const forceDenominator =
    magnitudeSum(Object.values(reactionForce ?? {})) + magnitudeSum(applied.forces.map((entry) => entry.components));
  const momentDenominator =
    magnitudeSum(Object.values(reactionMoment ?? {})) +
    magnitudeSum([
      ...applied.moments.map((entry) => entry.components),
      ...applied.forces.map((entry) => cross(entry.position ?? ZERO, entry.components))
    ]);

  const omitted = omittedSolverTerms(loadCase);
  return {
    loadCase: overlays?.loadCase ?? null,
    complete: omitted.length === 0,
    omitted,
    included: [
      `${countValues(reactionForce ?? reactionMoment)} support reaction${countValues(reactionForce ?? reactionMoment) === 1 ? "" : "s"}`,
      ...(applied.total > 0 ? [`${applied.total} authored nodal load${applied.total === 1 ? "" : "s"}`] : [])
    ],
    reactionForce: summedReactionForce,
    reactionMoment: summedReactionMoment,
    appliedForce,
    appliedMomentAboutOrigin,
    residualForce,
    residualMoment,
    forceResidual: norm(residualForce),
    momentResidual: norm(residualMoment),
    forceResidualRatio: ratio(norm(residualForce), forceDenominator),
    momentResidualRatio: ratio(norm(residualMoment), momentDenominator),
    tolerance: BALANCE_TOLERANCE
  };
}

// What the active colour field's number actually is. Ordered most-specific
// first: a builder that states its own derivation has said something no rule
// below could recover, and the volume-stress builder already does.
export function getAveragingBasis(state, legend) {
  const field = legend?.fieldId
    ? (state.resultFields ?? []).find((candidate) => candidate.id === legend.fieldId)
    : null;
  const overlay = legend?.overlay ?? null;
  const data = overlay?.data ?? {};
  const stated = firstString(data.derivation, data.averaging);
  if (stated) {
    return stated;
  }
  const support = field?.support ?? supportFromFieldId(legend?.fieldId);
  if (support === "subpoint") {
    return firstString(
      data.stress_basis,
      `measured at each Code_Aster section point (${data.component ?? "VMIS"} from ${data.field ?? "SIEQ_ELNO"}); the wall between points is interpolated`
    );
  }
  if (isElementMaxVonMises(data.field, legend?.field)) {
    return "element maximum of the two element-end values";
  }
  if (support === "node") {
    return "nodal value read from the solver result table";
  }
  if (support === "cell") {
    return "one value per element, as reported by the solver";
  }
  return null;
}

function isElementMaxVonMises(dataField, legendField) {
  const candidate = String(dataField ?? "").toLowerCase();
  return candidate === "max_von_mises" || String(legendField ?? "").toLowerCase().startsWith("fe vmis");
}

function supportFromFieldId(fieldId) {
  if (typeof fieldId !== "string") {
    return null;
  }
  if (fieldId.includes("tuyau_subpoints") || fieldId.includes("subpoint")) {
    return "subpoint";
  }
  if (fieldId.includes("displacement") || fieldId.includes("reaction")) {
    return "node";
  }
  return "cell";
}

// Authored nodal forces and moments, as scene objects. Line loads, pressure and
// self-weight are deliberately not here: their resultants are assembled inside
// Code_Aster and do not reach the bundle, so including a subset and calling it a
// balance would be the exact silent-omission failure this is meant to prevent.
function authoredLoads(state, loadCase) {
  const forces = [];
  const moments = [];
  for (const object of state.objects ?? []) {
    if (object.kind !== "applied_load") {
      continue;
    }
    const metadata = object.metadata ?? {};
    if (loadCase && metadata.load_case && metadata.load_case !== loadCase) {
      continue;
    }
    const components = vector3(metadata.components);
    if (!components) {
      continue;
    }
    const entry = { components, position: nodePosition(state, metadata.node_id) };
    if (metadata.vector_kind === "moment") {
      moments.push(entry);
    } else {
      forces.push(entry);
    }
  }
  return { forces, moments, total: forces.length + moments.length };
}

// Node coordinates for the moment arm. The reaction vectors carry the same
// nodes' positions, and they are the frame the reactions were resolved in, so
// they are preferred; the applied load's own asset start is the fallback.
function nodePosition(state, nodeId) {
  if (!nodeId) {
    return null;
  }
  for (const overlay of state.overlays ?? []) {
    for (const entry of overlay.data?.vectors ?? []) {
      if (entry.node_id === nodeId && Array.isArray(entry.start)) {
        const point = vector3(entry.start);
        if (point) {
          return point;
        }
      }
    }
  }
  return null;
}

// Named, not silent. A reviewer who sees "self-weight excluded" can reason about
// the number; a reviewer who sees a small residual with no explanation cannot.
function omittedSolverTerms(loadCase) {
  if (!loadCase) {
    return ["load definition not in this bundle"];
  }
  const omitted = [];
  if (loadCase.gravity) {
    omitted.push("self-weight (assembled inside Code_Aster)");
  }
  if (Number(loadCase.internal_pressure_pa) > 0) {
    omitted.push("internal pressure (assembled inside Code_Aster)");
  }
  if ((loadCase.pressure_fields ?? []).length > 0) {
    omitted.push("pressure fields (assembled inside Code_Aster)");
  }
  if (Number(loadCase.line_load_count) > 0) {
    omitted.push("line loads (assembled inside Code_Aster)");
  }
  if ((loadCase.field_count ?? 0) > 0) {
    omitted.push("authored load fields (assembled inside Code_Aster)");
  }
  return omitted;
}

function addAll(vectors) {
  return vectors.reduce((total, vector) => add(total, vector), [...ZERO]);
}

function add(left, right) {
  return [left[0] + right[0], left[1] + right[1], left[2] + right[2]];
}

function vector3(value) {
  if (!Array.isArray(value) || value.length < 3) {
    return null;
  }
  const point = value.slice(0, 3).map(Number);
  return point.every((component) => Number.isFinite(component)) ? point : null;
}

function countValues(record) {
  return Object.keys(record ?? {}).length;
}

function magnitudeSum(vectors) {
  return vectors.reduce((total, vector) => total + norm(vector), 0);
}

function norm(vector) {
  return Math.hypot(vector[0], vector[1], vector[2]);
}

function ratio(residual, denominator) {
  return denominator > 0 ? residual / denominator : null;
}

function firstString(...candidates) {
  for (const candidate of candidates) {
    if (typeof candidate === "string" && candidate.trim()) {
      return candidate.trim();
    }
  }
  return null;
}
