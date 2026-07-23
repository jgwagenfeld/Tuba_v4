// The coloring channel: which field tints the scene, and how.
//
// Kept deliberately separate from layer visibility. The display strip answers
// "what is drawn"; this answers "what does it mean". Following ParaView, one
// field yields one legend yields one colour map - the viewer never picks a
// field by guessing which overlay happens to carry numbers.

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
  return getResultFields(state)
    .filter((field) => !loadCase || !field.load_case || field.load_case === loadCase)
    .map((field) => ({
      id: field.id,
      label: fieldLabel(field),
      support: field.support,
      components: field.components ?? ["magnitude"],
      field
    }));
}

export function getActiveLoadCase(state) {
  return state.coloring?.loadCase ?? getResultFields(state)[0]?.load_case ?? null;
}

export function getActiveField(state) {
  const fields = getResultFields(state);
  const byId = fields.find((field) => field.id === state.coloring?.fieldId);
  if (byId) return byId;
  const loadCase = getActiveLoadCase(state);
  return fields.find((field) => field.load_case === loadCase) ?? fields[0] ?? null;
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
  // Changing case re-points the field: the same field id belongs to one case,
  // so keeping it would silently show the previous case's numbers.
  const next = { ...(state.coloring ?? {}), loadCase: loadCase ?? null };
  const candidate = getResultFields(state).find((field) => field.load_case === loadCase);
  next.fieldId = candidate?.id ?? null;
  return withCoherentColoring({ ...state, coloring: next });
}

export function setColoringField(state, fieldId) {
  const field = getResultFields(state).find((candidate) => candidate.id === fieldId);
  return withCoherentColoring({
    ...state,
    coloring: {
      ...(state.coloring ?? {}),
      fieldId: fieldId ?? null,
      loadCase: field?.load_case ?? state.coloring?.loadCase ?? null
    }
  });
}

export function setColoringComponent(state, component) {
  return withCoherentColoring({
    ...state,
    coloring: { ...(state.coloring ?? {}), component: component ?? null }
  });
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
  const overlay = (state.overlays ?? []).find((candidate) => candidate.id === field.overlay_id);
  // A declared range describes the field's own scalar. For a multi-component
  // field the displayed scalar depends on the chosen component, so the range
  // has to come from the values as actually resolved.
  const declared = (field.components ?? ["magnitude"]).length === 1 ? field.range : null;
  const range = declared ?? rangeOf(Object.values(getColoringValues(state)));
  if (!range) return null;
  return {
    fieldId: field.id,
    field: fieldLabel(field),
    component: getActiveComponent(state),
    support: field.support,
    unit: field.unit ?? "",
    loadCase: field.load_case ?? null,
    range: { min: range[0], max: range[1] },
    complianceRole: field.compliance_role ?? null,
    overlay
  };
}

// Rendered next to the legend, never as a tooltip and never suppressed by a
// visibility preset: an FE stress screenshot mislabelled as code stress is a
// compliance problem, not a UI nicety.
export function getComplianceNotice(state) {
  const role = getActiveField(state)?.compliance_role;
  if (!role) return null;
  if (role === "visualization_only_not_asme_code_stress") {
    return "FE stress - not ASME code stress";
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

export function scalarFor(value, component) {
  if (Array.isArray(value)) {
    const index = { DX: 0, DY: 1, DZ: 2 }[component];
    if (index !== undefined) return Number(value[index]);
    return Math.hypot(...value.slice(0, 3).map(Number));
  }
  return Number(value);
}

function rangeOf(values) {
  const numeric = values.filter((value) => Number.isFinite(value));
  return numeric.length > 0 ? [Math.min(...numeric), Math.max(...numeric)] : null;
}

function fieldLabel(field) {
  const support = field.support && field.support !== "node" ? ` (${field.support})` : "";
  return `${field.label || field.id}${support}`;
}

export { AXES as COLORING_AXES };
