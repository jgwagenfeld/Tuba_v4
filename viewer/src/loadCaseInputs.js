import { formatQuantity, getUnitSystem } from "./units.js";

const UNITS = { temperature: "°C", pressure: "Pa", wind: "Pa", line_load: "N/m" };

export function loadCaseDefinitions(state) {
  return (state.overlays ?? []).filter((overlay) => overlay.kind === "load_case").map((overlay) => overlay.data);
}

export function assignmentScope(field) {
  if (field.group) return field.group;
  if (field.route_id) {
    const range = field.station_start != null || field.station_end != null
      ? ` (${field.station_start ?? "start"}–${field.station_end ?? "end"} m)` : "";
    return field.route_id + range;
  }
  if (field.scope === "nodes") return (field.node_ids ?? []).join(", ");
  if (field.scope === "elements") return (field.element_ids ?? []).join(", ");
  return "All pipes";
}

export function assignmentObjectIds(state, field) {
  const elements = new Set(field.affected_element_ids ?? field.element_ids ?? []);
  return (state.objects ?? []).filter((object) =>
    ["pipe", "element", "rack_member"].includes(object.kind) &&
    typeof object.entity_ref === "string" && object.entity_ref.startsWith("element:") && elements.has(object.entity_ref.slice(8))
  ).map((object) => object.id);
}

export function elementInputSection(state, object) {
  if (typeof object?.entity_ref !== "string" || !object.entity_ref.startsWith("element:")) return null;
  const active = loadCaseDefinitions(state).find((entry) => entry.load_case === state.activeLoadCase);
  if (!active?.fields) return null;
  const id = object.entity_ref.slice(8);
  const fields = active.fields.filter((field) => (field.affected_element_ids ?? field.element_ids ?? []).includes(id));
  const system = getUnitSystem(state);
  const lines = [];
  for (const quantity of ["temperature", "pressure"]) {
    const local = fields.filter((field) => field.quantity === quantity);
    if (!local.length) {
      lines.push({ label: `${quantity} · case default`, value: formatQuantity(quantity === "pressure" ? active.internal_pressure_pa : active.temperature_c, UNITS[quantity], system), sourceLine: active.source_line });
    }
    for (const field of local) {
      lines.push({ label: `${quantity} · ${assignmentScope(field)}`, value: `${formatQuantity(field.value, UNITS[quantity], system)}${field.profile === "linear" ? " (profile endpoint)" : ""}`, sourceLine: field.source_call_line ?? field.source_line });
    }
  }
  lines.push({ kind: "note", label: "Authored assignments; node temperatures interpolate along connected elements." });
  return { title: `Inputs · ${active.load_case}`, lines };
}

export function renderLoadCaseInputs(host, state, { select, sourceLink, compare = false } = {}) {
  host.replaceChildren();
  const definitions = loadCaseDefinitions(state);
  const active = definitions.find((entry) => entry.load_case === state.activeLoadCase);
  if (!active) {
    host.textContent = "This bundle has no input assignments for the selected case.";
    return;
  }
  const system = getUnitSystem(state);
  const format = (value, quantity) => formatQuantity(value, UNITS[quantity], system);
  const defaults = document.createElement("p");
  defaults.className = "case-defaults";
  defaults.textContent = `Defaults: ${format(active.temperature_c, "temperature")} · ${format(active.internal_pressure_pa, "pressure")} · reference ${format(active.ref_temperature_c, "temperature")} · self-weight ${active.gravity ? "on" : "off"}`;
  const link = sourceLink?.(active.source_line);
  if (link) defaults.append(" ", link);
  host.append(defaults);
  if (definitions.some((entry) => (compare || entry === active) && entry.field_count > 0 && !Array.isArray(entry.fields))) {
    const note = document.createElement("p");
    note.textContent = "This bundle records local fields without their assignments. Rebuild the review to inspect them; the defaults are not the values everywhere.";
    host.append(note);
    return;
  }

  const fields = active.fields ?? [];
  const table = document.createElement("table");
  table.className = "case-input-table";
  table.setAttribute("aria-label", compare ? "Assignments across load cases" : `${active.load_case} input assignments`);
  const head = table.createTHead().insertRow();
  for (const label of ["Assignment", ...(compare ? definitions.map((entry) => entry.load_case) : ["Value"])]) {
    const cell = document.createElement("th");
    cell.scope = "col";
    cell.textContent = label;
    head.append(cell);
  }
  const body = table.createTBody();
  if (compare) {
    for (const [label, property, quantity] of [["Default temperature", "temperature_c", "temperature"], ["Default pressure", "internal_pressure_pa", "pressure"], ["Reference temperature", "ref_temperature_c", "temperature"]]) {
      const row = body.insertRow();
      row.insertCell().textContent = label;
      for (const definition of definitions) row.insertCell().textContent = format(definition[property], quantity);
    }
    const row = body.insertRow();
    row.insertCell().textContent = "Self-weight";
    for (const definition of definitions) row.insertCell().textContent = definition.gravity ? "On" : "Off";
  }
  // Compare authored assignments, not invented combinations or scalar stress differences.
  const key = (field) => JSON.stringify([field.quantity, field.scope, field.profile, assignmentScope(field), field.direction]);
  const rows = compare ? [...new Map(definitions.flatMap((entry) => (entry.fields ?? []).map((field) => [key(field), field]))).values()] : fields;
  for (const [index, field] of rows.entries()) {
    const row = body.insertRow();
    const target = row.insertCell();
    const button = document.createElement("button");
    button.type = "button";
    button.className = "case-assignment";
    button.dataset.focusKey = `${host.dataset.caseInputs}:assignment:${index}`;
    button.textContent = `${field.quantity} · ${assignmentScope(field)}`;
    button.title = "Select affected elements in 3D";
    const ids = assignmentObjectIds(state, field);
    button.disabled = !ids.length;
    button.setAttribute("aria-pressed", String(ids.length > 0 && ids.every((id) => (state.selectedObjectIds ?? []).includes(id))));
    button.addEventListener("click", () => select?.(ids));
    target.append(button);
    if (!compare) {
      const link = sourceLink?.(field.source_call_line ?? field.source_line);
      if (link) target.append(" ", link);
    }
    for (const definition of compare ? definitions : [active]) {
      const value = compare ? (definition.fields ?? []).find((candidate) => key(candidate) === key(field)) : field;
      const cell = row.insertCell();
      cell.textContent = value ? format(value.value, value.quantity) : "—";
      if (value?.scope === "nodes") cell.append(" at node");
      else if (value?.profile === "linear") cell.append(" · linear endpoint");
      if (value?.direction) cell.append(` · direction [${value.direction.join(", ")}]`);
    }
  }
  if (rows.length || compare) host.append(table);
  const note = document.createElement("p");
  note.className = "case-input-note";
  note.textContent = compare
    ? "— means no matching assignment; inspect that case's defaults and other assignments."
    : fields.length ? "Authored inputs. Select an assignment to highlight its scope; line links open model.py. Unassigned regions use the defaults. Node temperatures interpolate along connected elements." : "Uniform inputs: every region uses the case defaults.";
  host.append(note);
}
