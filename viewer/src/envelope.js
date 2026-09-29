// The envelope: the worst of a set of result steps, per object.
//
// Every tool in the piping category has one and this viewer had none. AutoPIPE
// reviews "the stress ratio of an envelope of the code combinations"; CAEPIPE
// computes the maximum across all cases at each node and reports which case
// produced it; PrePoMax, SCIA and SOFiSTiK all carry an envelope result type.
// A reviewer with five load cases and a dropdown wants the worst of them, and
// stepping through the dropdown by hand and remembering the answer is the one
// thing the dropdown cannot do for them.
//
// Two properties make it worth having rather than being a filter:
//
//   - It records *which* result step won. A maximum with no provenance is a
//     number the reviewer has to go and re-derive; a maximum that names its load
//     case is an answer.
//   - It is derived, not solved, and says so. An envelope is arithmetic over
//     results the solver produced. It is never a solver result, and a field that
//     claims to be one would be the kind of mislabel this product does not ship.
//
// It lives in its own module because resultReview.js imports coloring.js and so
// coloring.js cannot import resultReview.js back. Both import this.

export const ENVELOPE_FIELD_ID = "field:envelope";

// Result states the envelope spans for one load case. Deliberately every state
// the case published, not a selection: a reviewer who can choose which steps to
// envelope will eventually choose the one they already liked.
export function envelopeResultStates(state) {
  const states = (state.resultStates ?? []).filter((overlay) => {
    const loadCase = overlay.data?.load_case;
    return !state.activeLoadCase || !loadCase || loadCase === state.activeLoadCase;
  });
  return states.map((overlay) => ({
    id: overlay.data?.id ?? overlay.id,
    label: overlay.name ?? overlay.data?.load_case ?? overlay.id
  }));
}

export function envelopeAvailable(state) {
  return envelopeResultStates(state).length > 1;
}

// The overlays an envelope is built from: the same declared quantity, in every
// result step of the active load case. Matching on the quantity *and* the unit
// is what stops a displacement envelope from silently absorbing a stress
// overlay because both are keyed by object id.
export function envelopeSourceOverlays(state, field, component = "magnitude") {
  if (!field) {
    return [];
  }
  const declared = field.field ?? field.label ?? null;
  const unit = field.unit ?? null;
  const resultType = field.result_type ?? null;
  return (state.overlays ?? []).filter((overlay) => {
    if (overlay.kind !== "solver_result") return false;
    const data = overlay.data ?? {};
    if (state.activeLoadCase && data.load_case && data.load_case !== state.activeLoadCase) return false;
    if (data.result_type && resultType && data.result_type !== resultType) return false;
    const quantity = data.field ?? data.result_type ?? overlay.name ?? overlay.id;
    if (declared && quantity !== declared) return false;
    if (unit && data.unit && data.unit !== unit) return false;
    return hasValues(data.values);
  });
}

// { values, winners, range, resultStateIds, component }
//
// `winners` is the part that makes this a review answer rather than a chart: it
// maps each object to the result state that produced its envelope value, so the
// hotspot list can say "Operating, stage 3" beside the number.
export function buildEnvelope(state, field, component = "magnitude", readScalar = null) {
  const sources = envelopeSourceOverlays(state, field);
  const values = {};
  const winners = {};
  const contributing = new Set();
  for (const overlay of sources) {
    const data = overlay.data ?? {};
    const stateId = data.result_state_id ?? null;
    for (const [objectId, raw] of Object.entries(data.values ?? {})) {
      const value = Array.isArray(raw) ? raw[0] : raw;
      const scalar = readScalar ? readScalar(raw, component)
        : typeof value === "number" || (typeof value === "string" && value.trim()) ? Number(value) : NaN;
      if (!Number.isFinite(scalar)) {
        continue;
      }
      contributing.add(stateId);
      // Strictly greater, so the earliest result step keeps a tie. A tie is not
      // a coincidence in a staged run - it usually means the increment added
      // nothing - and naming the later step would credit it with the value.
      if (!Number.isFinite(values[objectId]) || scalar > values[objectId]) {
        values[objectId] = scalar;
        winners[objectId] = stateId;
      }
    }
  }
  const numbers = Object.values(values).filter(Number.isFinite);
  return {
    values,
    winners,
    range: numbers.length > 0 ? { min: Math.min(...numbers), max: Math.max(...numbers) } : null,
    resultStateIds: [...contributing].filter(Boolean),
    component,
    // Measured in result steps that actually contributed, not in overlays
    // matched: two overlays can belong to one step, and a load case can publish
    // two steps while only one of them carries this quantity. Either way the
    // honest answer is that no maximum was taken across steps, and a "maximum
    // of one" is a single result wearing an envelope's label.
    enveloped: contributing.size > 1
  };
}

export function isEnvelopeField(field) {
  return field?.id === ENVELOPE_FIELD_ID;
}

function hasValues(values) {
  return values && typeof values === "object" && Object.keys(values).length > 0;
}
