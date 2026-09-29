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
  isEnvelopeField
} from "./envelope.js";

const AXES = ["loadCase", "fieldId", "component"];

export function getResultFields(state) {
  return state.resultFields ?? [];
}

export function getLoadCaseOptionsFromFields(state) {
  const seen = new Map();
  for (const field of getResultFields(state)) {
    if (field.load_case && !seen.has(field.load_case)) {
      seen.set(field.load_case, { id: field.load_case, label: field.load_case });
    }
  }
  return [...seen.values()];
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
      unit: sources[0]?.unit ?? "",
      // Set on the field as well as the legend: the compliance notice reads the
      // field, and a derived maximum that skipped the disclaimer because the
      // disclaimer was attached one layer over would be the worst kind of bug
      // this product has.
      compliance_role: "derived_envelope_not_a_solver_result",
      // Which declared quantities this maximum is taken over, so the legend can
      // say what was enveloped instead of leaving the reviewer to infer it.
      envelope_source: sources
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
    return envelope ?? fields.find((field) => field.load_case === getActiveLoadCase(state)) ?? fields[0] ?? null;
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
  return components.includes(requested) ? requested : components[0];
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
  return {
    ...withCoherentColoring({
      ...state,
      coloring: {
        ...(state.coloring ?? {}),
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

export function getColoringLegend(state) {
  const field = getActiveField(state);
  if (!field) return null;
  if (isEnvelopeField(field)) {
    const envelope = buildEnvelope(state, envelopeQuantity(state, field), getActiveComponent(state), scalarFor);
    if (!envelope.range) return null;
    return {
      fieldId: field.id,
      field: "Envelope",
      component: envelope.component,
      support: "envelope",
      unit: field.unit ?? "",
      loadCase: field.load_case ?? null,
      range: envelope.range,
      // Derived arithmetic over solved results, and the disclaimer has to say so
      // in the same breath as the number, exactly as the FE-stress field does.
      complianceRole: "derived_envelope_not_a_solver_result",
      envelope: { ...envelope, sources: field.envelope_source ?? [], resultStates: envelopeResultStates(state) },
      overlay: null
    };
  }
  const overlay = (state.overlays ?? []).find((candidate) => candidate.id === field.overlay_id);
  // A declared range describes the field's own scalar. For a multi-component
  // field the displayed scalar depends on the chosen component, so the range
  // has to come from the values as actually resolved.
  const declared = (field.components ?? ["magnitude"]).length === 1 ? field.range : null;
  const range = declared ?? rangeOf(Object.values(getColoringValues(state)));
  if (!range) return null;
  const component = getActiveComponent(state);
  return {
    fieldId: field.id,
    field: fieldLabel(field),
    component,
    support: field.support,
    unit: componentUnit(field, component),
    loadCase: field.load_case ?? null,
    range: { min: range[0], max: range[1] },
    complianceRole: field.compliance_role ?? null,
    overlay
  };
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

// The notice belongs wherever a compliance-flagged field is actually tinting
// the scene. The result panel is detached under the Review/Model/Issues tasks
// while the scene stays colour-mapped, so this is driven by the Results layer
// being visible rather than by which task is open.
export function shouldShowComplianceNotice(state, categories) {
  if (!getComplianceNotice(state)) return false;
  const results = (categories ?? []).find((category) => category.id === "results");
  return Boolean(results?.layerIds.some((id) => state.layers?.[id]?.visible !== false));
}

export function getColoringValues(state) {
  const field = getActiveField(state);
  if (!field) return {};
  if (isEnvelopeField(field)) {
    return buildEnvelope(state, envelopeQuantity(state, field), getActiveComponent(state), scalarFor).values;
  }
  const overlay = (state.overlays ?? []).find((candidate) => candidate.id === field.overlay_id);
  const values = overlay?.data?.values ?? {};
  const component = getActiveComponent(state);
  const resolved = {};
  for (const [key, value] of Object.entries(values)) {
    const scalar = scalarFor(value, component);
    if (Number.isFinite(scalar)) {
      resolved[key] = scalar;
    }
  }
  return resolved;
}

// Which result states produced each object's envelope value. The hotspot list
// reads this to name the governing step beside the number, which is the
// difference between a maximum and an answer.
export function getEnvelopeWinners(state) {
  const field = getActiveField(state);
  if (!isEnvelopeField(field)) {
    return null;
  }
  const envelope = buildEnvelope(state, envelopeQuantity(state, field), getActiveComponent(state), scalarFor);
  return { ...envelope, resultStates: envelopeResultStates(state) };
}

// The envelope option is synthetic and carries no overlay_id, so the declared
// quantity it envelopes is taken from the catalogue entry it was built over -
// the first field of the same load case, which is the one the reviewer was
// looking at a moment before they chose the envelope.
function envelopeQuantity(state, field) {
  const loadCase = field.load_case ?? getActiveLoadCase(state);
  const catalogue = fieldsForActiveResult(state)
    .filter((candidate) => !loadCase || !candidate.load_case || candidate.load_case === loadCase);
  return catalogue.find((candidate) => candidate.support === "cell")
    ?? catalogue.find((candidate) => candidate.support !== "node")
    ?? catalogue[0]
    ?? null;
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
    if (index !== undefined && index < value.length) return Number(value[index]);
    if (component === "magnitude" || !component) {
      return Math.hypot(...value.slice(0, Math.min(3, value.length)).map(Number));
    }
    return Number(value[0]);
  }
  return Number(value);
}

function rangeOf(values) {
  const numeric = values.filter((value) => Number.isFinite(value));
  return numeric.length > 0 ? [Math.min(...numeric), Math.max(...numeric)] : null;
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
    stress: "Stress"
  }[normalized] ?? String(raw).replaceAll("_", " ").replace(/^[a-z]/, (letter) => letter.toUpperCase());
  return `${readable}${support}`;
}

export { AXES as COLORING_AXES };
