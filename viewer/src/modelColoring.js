// Categorical color palette for model properties (Section, Material, Group, Insulation).
// Accessible, high-contrast, visually distinct shades.
export const CATEGORICAL_PALETTE = Object.freeze([
  "#2563eb", // Blue
  "#059669", // Emerald
  "#d97706", // Amber
  "#7c3aed", // Purple
  "#0891b2", // Cyan
  "#e11d48", // Rose
  "#4f46e5", // Indigo
  "#0d9488", // Teal
  "#ea580c", // Orange
  "#64748b"  // Slate
]);

export const MODEL_COLOR_MODES = Object.freeze([
  { id: "default", label: "Default (Role)" },
  { id: "section", label: "Section" },
  { id: "material", label: "Material" },
  { id: "group", label: "Group" },
  { id: "insulation", label: "Insulation" }
]);

export function getModelObjectPropertyValue(obj, mode) {
  if (!obj || !mode || mode === "default") return null;
  if (mode === "section") {
    return obj.metadata?.section || obj.metadata?.profile?.kind || null;
  }
  if (mode === "material") {
    return obj.metadata?.material || null;
  }
  if (mode === "group") {
    return obj.group_ids?.[0] || obj.metadata?.groups?.[0] || obj.metadata?.group || null;
  }
  if (mode === "insulation") {
    const spec = obj.metadata?.insulation;
    if (!spec) return "Uninsulated / Bare";
    if (spec.material) {
      const thk = Number(spec.thickness_m);
      return Number.isFinite(thk) && thk > 0
        ? `${spec.material} (${Math.round(thk * 1000)} mm)`
        : spec.material;
    }
    return spec.id || "Insulated";
  }
  return obj[mode] || obj.metadata?.[mode] || null;
}

export function isModelColorable(obj) {
  const kind = String(obj?.kind || "");
  return kind === "pipe" || kind === "element" || kind === "rack_member";
}

export function getModelColoring(state, mode = state?.modelColorBy || "default") {
  if (!mode || mode === "default") {
    return { mode: "default", items: [], colorByValue: new Map(), colorByObjectId: new Map() };
  }
  const objects = (state?.objects || []).filter(isModelColorable);
  const counts = new Map();
  const objectIdsByValue = new Map();

  for (const obj of objects) {
    const val = getModelObjectPropertyValue(obj, mode) || "Unassigned";
    counts.set(val, (counts.get(val) || 0) + 1);
    if (!objectIdsByValue.has(val)) {
      objectIdsByValue.set(val, []);
    }
    objectIdsByValue.get(val).push(obj.id);
  }

  // Sort values deterministically
  const sortedValues = [...counts.keys()].sort((a, b) => a.localeCompare(b));
  const items = [];
  const colorByValue = new Map();
  const colorByObjectId = new Map();

  sortedValues.forEach((val, index) => {
    const color = CATEGORICAL_PALETTE[index % CATEGORICAL_PALETTE.length];
    colorByValue.set(val, color);
    const objectIds = objectIdsByValue.get(val) || [];
    items.push({
      value: val,
      label: val,
      color,
      count: counts.get(val) || 0,
      objectIds
    });
    for (const id of objectIds) {
      colorByObjectId.set(id, color);
    }
  });

  return {
    mode,
    items,
    colorByValue,
    colorByObjectId
  };
}

export function getModelObjectColor(state, objectIds = []) {
  const mode = state?.modelColorBy;
  if (!mode || mode === "default") return null;
  // If not in model task and results coloring is active, return null
  if (state?.activeTab && state.activeTab !== "model") return null;

  const ids = Array.isArray(objectIds) ? objectIds : [objectIds];
  const coloring = getModelColoring(state, mode);

  for (const id of ids) {
    if (coloring.colorByObjectId.has(id)) {
      return coloring.colorByObjectId.get(id);
    }
  }

  for (const id of ids) {
    const obj = (state?.objects || []).find((o) => o.id === id);
    if (obj) {
      const val = getModelObjectPropertyValue(obj, mode) || "Unassigned";
      if (coloring.colorByValue.has(val)) {
        return coloring.colorByValue.get(val);
      }
    }
  }
  return null;
}
