// The coloring channel: which field tints the scene, and how.
//
// Kept deliberately separate from layer visibility. The display strip answers
// "what is drawn"; this answers "what does it mean". Following ParaView, one
// field yields one legend yields one colour map - the viewer never picks a
// field by guessing which overlay happens to carry numbers.

import {
  ENVELOPE_FIELD_ID,
  buildEnvelope,
  envelopeAvailable,
  envelopeResultStates,
  envelopeSourceOverlays,
  isEnvelopeField
} from "./envelope.js";

const AXES = ["loadCase", "fieldId", "component"];
const EMPTY_VALUES = Object.freeze({});
const scalarCache = new WeakMap();
const fieldCache = new WeakMap();

export function getResultFields(state) {
  return state.resultFields ?? [];
}

export function getFieldOptions(state, loadCase = getActiveLoadCase(state)) {
  const options = fieldsForActiveResult(state)
    .filter((field) => !loadCase || !field.load_case || field.load_case === loadCase)
    .map((field) => ({
      id: field.id,
      label: fieldLabel(field),
      support: field.support,
      components: field.components ?? ["magnitude"],
      field
    }));
  const envelope = envelopeOption(state, loadCase);
  return envelope ? [...options, envelope] : options;
}

// The envelope is one more field in the one selector ADR 0006 requires, not a
// second channel beside it. It appears only when the active load case published
// more than one result step, because a "maximum of one result" is a single
// result wearing an envelope's label.
function envelopeOption(state, loadCase) {
  if (!envelopeAvailable(state)) {
    return null;
  }
  const steps = envelopeResultStates(state).length;
  const sources = fieldsForActiveResult(state)
    .filter((field) => !loadCase || !field.load_case || field.load_case === loadCase)
    .map((field) => ({ field: field.id, label: fieldLabel(field), unit: field.unit }));
  // An envelope with no declared quantity to take the maximum of is not a field
  // anybody can read, so it is not offered. This is also what keeps a bundle
  // whose active result state cannot be resolved - the catalogue empty, the
  // load case still holding two steps - from offering an envelope over nothing.
  if (sources.length === 0) {
    return null;
  }
  const quantity = envelopeQuantity(state, { load_case: loadCase });
  return {
    id: ENVELOPE_FIELD_ID,
    label: `Envelope — worst of ${steps} result steps`,
    support: "envelope",
    components: ["magnitude"],
    envelope: true,
    field: {
      id: ENVELOPE_FIELD_ID,
      label: "Envelope",
      support: "envelope",
      components: ["magnitude"],
      load_case: loadCase ?? null,
      unit: quantity?.unit ?? "",
      // Set on the field as well as the legend: the compliance notice reads the
      // field, and a derived maximum that skipped the disclaimer because the
      // disclaimer was attached one layer over would be the worst kind of bug
      // this product has.
      compliance_role: "derived_envelope_not_a_solver_result"
    }
  };
}

export function getActiveLoadCase(state) {
  return state.coloring?.loadCase ?? getResultFields(state)[0]?.load_case ?? null;
}

export function getActiveField(state) {
  const fields = fieldsForActiveResult(state);
  const requested = getResultFields(state).find((field) => field.id === state.coloring?.fieldId);
  const envelope = envelopeOption(state, getActiveLoadCase(state));
  if (state.coloring?.fieldId === ENVELOPE_FIELD_ID) {
    // The envelope disappears when the load case narrows to a single result
    // step. Falling through to the catalogue rather than yielding null is what
    // keeps a load-case switch from blanking the whole colouring channel.
    return envelope?.field ?? fields.find((field) => field.load_case === getActiveLoadCase(state)) ?? fields[0] ?? null;
  }
  const byId = fields.find((field) => field.id === requested?.id);
  if (byId) return byId;
  if (requested) {
    const quantity = (field) => {
      const overlay = (state.overlays ?? []).find((item) => item.id === field.overlay_id);
      return JSON.stringify([overlay?.data?.field ?? overlay?.data?.result_type ?? field.label, field.support, field.unit]);
    };
    const matching = fields.find((field) => quantity(field) === quantity(requested));
    if (matching) return matching;
  }
  const loadCase = getActiveLoadCase(state);
  return fields.find((field) => field.load_case === loadCase) ?? fields[0] ?? null;
}

function fieldsForActiveResult(state) {
  const overlays = new Map((state.overlays ?? []).map((overlay) => [overlay.id, overlay]));
  const loadCase = state.activeLoadCase ?? state.coloring?.loadCase;
  return getResultFields(state).filter((field) => {
    const owner = overlays.get(field.overlay_id)?.data?.result_state_id ?? field.result_state_id;
    return (!loadCase || !field.load_case || field.load_case === loadCase) &&
      (!state.activeResultStateId || !owner || owner === state.activeResultStateId);
  });
}

export function getActiveComponent(state) {
  const field = getActiveField(state);
  const components = field?.components ?? ["magnitude"];
  const requested = state.coloring?.component;
  if (components.includes(requested)) return requested;
  // A DX/DY/DZ vector opens on how far, not on whichever axis the solver listed
  // first: DX alone hid a riser that moves almost entirely in Z. Section forces
  // keep their first, N - the resultant of N, VY and VZ would hide the sign that
  // tells tension from compression.
  return components[0] === "DX" && components.includes("magnitude") ? "magnitude" : components[0];
}

export function componentIsSelectable(state) {
  return (getActiveField(state)?.components ?? ["magnitude"]).length > 1;
}

export function setColoringLoadCase(state, loadCase) {
  // Retain the requested quantity; getActiveField resolves its counterpart
  // within the new case and result step before falling back to another field.
  const next = { ...(state.coloring ?? {}), loadCase: loadCase ?? null };
  return withCoherentColoring({ ...state, coloring: next });
}

export function setColoringField(state, fieldId) {
  const field = getResultFields(state).find((candidate) => candidate.id === fieldId);
  // Only a component the reader could have chosen is carried to the new field.
  // A scalar field's lone "magnitude" was never a choice, and carrying it turned
  // section forces into the resultant of N, VY and VZ instead of opening on N.
  const carried = componentIsSelectable(state) ? state.coloring?.component ?? null : null;
  return {
    ...withCoherentColoring({
      ...state,
      coloring: {
        ...(state.coloring ?? {}),
        component: carried,
        fieldId: fieldId ?? null,
        loadCase: field?.load_case ?? state.coloring?.loadCase ?? null
      }
    }),
    // Picking a field is choosing to colour by results, whatever lens is open.
    colorChannel: "results"
  };
}

export function setColoringComponent(state, component) {
  return {
    ...withCoherentColoring({
      ...state,
      coloring: { ...(state.coloring ?? {}), component: component ?? null }
    }),
    colorChannel: "results"
  };
}

// Snap the triple back onto something that exists. Called on every change and
// after a live reload, where the selected field may have vanished entirely.
export function withCoherentColoring(state) {
  const field = getActiveField(state);
  const coloring = {
    loadCase: field?.load_case ?? getActiveLoadCase(state) ?? null,
    fieldId: field?.id ?? null,
    // Keep the requested component when the resolved field offers it; only
    // fall back when it does not.
    component: state.coloring?.component ?? null
  };
  coloring.component = getActiveComponent({ ...state, coloring });
  return { ...state, coloring };
}

export function createColoringState(state) {
  return withCoherentColoring({ ...state, coloring: state.coloring ?? {} }).coloring;
}

// One resolved field for every reader: a derived envelope has values and source
// metadata without pretending to be a separate solver overlay. Payloads are
// immutable, and reload replaces the catalogue and overlays together.
export function getColoringField(state) {
  const dependencies = [state.resultFields, state.overlays, state.resultStates, state.activeLoadCase,
    state.activeResultStateId, state.coloring?.loadCase, state.coloring?.fieldId, state.coloring?.component];
  let cached = fieldCache.get(state);
  if (!cached || dependencies.some((value, index) => value !== cached.dependencies[index])) {
    cached = { dependencies, value: resolveColoringField(state) };
    fieldCache.set(state, cached);
  }
  return cached.value;
}

function resolveColoringField(state) {
  const field = getActiveField(state);
  if (!field) return null;
  const component = getActiveComponent(state);
  if (isEnvelopeField(field)) {
    const quantity = envelopeQuantity(state, field);
    const sources = envelopeSourceOverlays(state, quantity);
    const unit = componentUnit(quantity ?? field, component);
    const envelope = { ...buildEnvelope(state, quantity, component, scalarFor),
      sources: quantity ? [{ field: quantity.id, label: fieldLabel(quantity), unit }] : [],
      resultStates: envelopeResultStates(state) };
    const legend = envelope.range ? {
      fieldId: field.id,
      field: "Envelope",
      component: envelope.component,
      support: "envelope",
      unit,
      loadCase: field.load_case ?? null,
      range: envelope.range,
      // Derived arithmetic over solved results, and the disclaimer has to say so
      // in the same breath as the number, exactly as the FE-stress field does.
      complianceRole: "derived_envelope_not_a_solver_result",
      envelope,
      overlay: null
    } : null;
    return { field, component, values: envelope.values, legend, overlay: null, envelope,
      resultType: sources[0]?.data?.result_type ?? quantity?.result_type ?? null,
      vectors: sources.flatMap(source => source.data?.vectors ?? []) };
  }
  const overlay = (state.overlays ?? []).find((candidate) => candidate.id === field.overlay_id);
  // A declared range describes the field's own scalar. For a multi-component
  // field the displayed scalar depends on the chosen component, so the range
  // has to come from the values as actually resolved.
  const declared = (field.components ?? ["magnitude"]).length === 1 ? field.range : null;
  const scalars = resolvedScalars(overlay?.data?.values, component);
  const range = declared ?? scalars.range;
  const legend = range ? {
    fieldId: field.id,
    field: fieldLabel(field),
    component,
    support: field.support,
    unit: componentUnit(field, component),
    loadCase: field.load_case ?? null,
    range: { min: range[0], max: range[1] },
    complianceRole: field.compliance_role ?? null,
    overlay
  } : null;
  return { field, component, values: scalars.values, legend, overlay, envelope: null,
    resultType: overlay?.data?.result_type ?? field.result_type ?? null, vectors: overlay?.data?.vectors };
}

export function getColoringLegend(state) {
  return getColoringField(state)?.legend ?? null;
}

function componentUnit(field, component) {
  if (["MT", "MFY", "MFZ", "MX", "MY", "MZ"].includes(component)) return "N·m";
  if (["N", "VY", "VZ", "FX", "FY", "FZ"].includes(component)) return "N";
  if (["DRX", "DRY", "DRZ"].includes(component)) return "rad";
  return field.unit ?? "";
}

// Rendered next to the legend, never as a tooltip and never suppressed by a
// visibility preset: an FE stress screenshot mislabelled as code stress is a
// compliance problem, not a UI nicety.
export function getComplianceNotice(state) {
  const field = getActiveField(state);
  const role = field?.compliance_role ?? (field?.label?.toLowerCase() === "fe vmis (not code stress)"
    ? "visualization_only_not_asme_code_stress" : null);
  if (!role) return null;
  if (role === "hydraulic_result_not_structural_acceptance") {
    return "OpenModelica steady fluid result; structural acceptance is evaluated separately";
  }
  if (role === "visualization_only_not_asme_code_stress") {
    return "FE stress - not ASME code stress";
  }
  if (role === "derived_envelope_not_a_solver_result") {
    return "Envelope - the worst of the result steps, not a separate solve";
  }
  if (role === "user_reference_ratio_not_a_code_check") {
    // The denominator is the user's own typed schedule, and that is the whole
    // claim. Naming the code this is not keeps the notice honest in both
    // directions: it neither implies an evaluation nor hides that the reviewer
    // supplied the number.
    return "Ratio to a user-entered allowable - not a code check";
  }
  return role.replace(/_/g, " ");
}

export function getColoringValues(state) {
  return getColoringField(state)?.values ?? EMPTY_VALUES;
}

// Which result states produced each object's envelope value. The hotspot list
// reads this to name the governing step beside the number, which is the
// difference between a maximum and an answer.
export function getEnvelopeWinners(state) {
  return getColoringField(state)?.envelope ?? null;
}

// Scene payloads are immutable: reload replaces their value maps. Resolve each
// component once, retaining its range beside it rather than rescanning it for
// every object's tint. Weak keys release old results after a reload.
function resolvedScalars(raw = EMPTY_VALUES, component) {
  raw = raw ?? EMPTY_VALUES;
  let components = scalarCache.get(raw);
  if (!components) {
    components = new Map();
    scalarCache.set(raw, components);
  }
  if (!components.has(component)) {
    const values = {};
    let min = Infinity, max = -Infinity;
    for (const [key, value] of Object.entries(raw)) {
      const scalar = scalarFor(value, component);
      if (!Number.isFinite(scalar)) continue;
      values[key] = scalar;
      min = Math.min(min, scalar);
      max = Math.max(max, scalar);
    }
    components.set(component, { values, range: min === Infinity ? null : [min, max] });
  }
  return components.get(component);
}

// The envelope option is synthetic and carries no overlay_id, so the declared
// quantity it envelopes is taken from the same-case catalogue: prefer the
// declared element field, then another non-nodal field, then the first field.
function envelopeQuantity(state, field) {
  const loadCase = field.load_case ?? getActiveLoadCase(state);
  const catalogue = fieldsForActiveResult(state)
    .filter((candidate) => !loadCase || !candidate.load_case || candidate.load_case === loadCase);
  const quantity = catalogue.find((candidate) => candidate.support === "cell")
    ?? catalogue.find((candidate) => candidate.support !== "node")
    ?? catalogue[0]
    ?? null;
  if (!quantity) return null;
  const source = (state.overlays ?? []).find(overlay => overlay.id === quantity.overlay_id)?.data;
  // Catalogue labels are display text ("Section Forces (EFGE_ELNO)"), not
  // solver quantity identifiers. Match other steps through the owning overlay.
  return { ...quantity, field: source?.field ?? source?.result_type ?? quantity.field ?? quantity.label,
    result_type: source?.result_type ?? quantity.result_type };
}

const COMPONENT_INDEX = {
  DX: 0, DY: 1, DZ: 2,
  FX: 0, FY: 1, FZ: 2,
  MX: 0, MY: 1, MZ: 2,
  DRX: 3, DRY: 4, DRZ: 5,
  N: 0, VY: 1, VZ: 2, MT: 3, MFY: 4, MFZ: 5
};

export function scalarFor(value, component) {
  if (Array.isArray(value)) {
    const index = COMPONENT_INDEX[component];
    if (index !== undefined) return numericScalar(value[index]);
    if (component === "magnitude" || !component) {
      return value.length ? Math.hypot(...value.slice(0, 3).map(numericScalar)) : NaN;
    }
    return numericScalar(value[0]);
  }
  return numericScalar(value);
}

function numericScalar(value) {
  return typeof value === "number" || (typeof value === "string" && value.trim()) ? Number(value) : NaN;
}

export function fieldLabel(field) {
  const supportName = { cell: "elements", subpoint: "wall points" }[field.support] ?? field.support;
  const support = supportName && supportName !== "node" ? ` (${supportName})` : "";
  const raw = field.label || field.id;
  const normalized = String(raw).toLowerCase().replace(/_magnitude$/, "");
  const readable = {
    displacement: "Displacement",
    reaction_force: "Reaction force",
    reaction_moment: "Reaction moment",
    "fe vmis": "Von Mises stress",
    "fe vmis (not code stress)": "Von Mises stress",
    stress: "Stress",
    "section forces (efge_elno)": "Section forces"
  }[normalized] ?? String(raw).replaceAll("_", " ").replace(/^[a-z]/, (letter) => letter.toUpperCase());
  return `${readable}${support}`;
}

export { AXES as COLORING_AXES };
