import { getActiveResultState, getResultStateOptions, formatPseudoTime } from "./resultReview.js";
import { resolveEntityObjectId } from "./reviewSelection.js";
import { displayUnit, formatQuantity, getUnitSystem, toDisplay } from "./units.js";

export const CONTACT_SYMBOLS = { open: "○", sticking: "■", sliding: "➜", indeterminate: "?" };
export const CONTACT_COLORS = { open: 0x64748b, sticking: 0x2563eb, sliding: 0x0f766e, indeterminate: 0x92400e };
export const magnitude = (v) => Array.isArray(v) && v.length === 3 && v.every(Number.isFinite) ? Math.hypot(...v) : NaN;
const dot = (a, b) => a.reduce((sum, value, i) => sum + value * b[i], 0);
const cross = (a, b) => [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]];

export function contactStatusLabel(contact) {
  return contact.status === "indeterminate" && contact.normal_force > 1 && contact.friction_limit === 0
    ? "closed (frictionless)" : contact.status;
}

export function contactRecords(state) {
  const records = getActiveResultState(state)?.overlay.data?.contact_results ?? {};
  return Object.fromEntries(Object.entries(records).filter(([, c]) => c && CONTACT_SYMBOLS[c.status] &&
    typeof c.support_id === "string" && [c.normal, c.tangential_force, c.relative_displacement, c.slip].every((v) => Number.isFinite(magnitude(v))) &&
    magnitude(c.normal) > 0 && [c.normal_force, c.friction_limit, c.gap].every(Number.isFinite) &&
    (c.utilization === null || Number.isFinite(c.utilization))));
}

export function contactObjectId(state, supportId) {
  return resolveEntityObjectId(state, `support:${supportId}`) ??
    (state.objects ?? []).find((o) => o.metadata?.support_id === supportId || o.id === supportId)?.id ?? null;
}

export function contactStates(state) {
  const active = getActiveResultState(state)?.overlay.data ?? {};
  const run = active.metadata?.run_id ?? active.metadata?.analysis_id ?? active.load_case;
  return getResultStateOptions(state).filter(({ overlay }) => {
    const data = overlay.data ?? {};
    return (data.metadata?.run_id ?? data.metadata?.analysis_id ?? data.load_case) === run;
  });
}

// Fixed deterministic support frame: t1 is projected global X (Y near parallel), t2 = n x t1.
export function contactTangents(normal) {
  const length = magnitude(normal);
  if (!(length > 0)) return null;
  const n = normal.map((v) => v / length);
  const reference = Math.abs(n[0]) < 0.9 ? [1, 0, 0] : [0, 1, 0];
  const projection = dot(reference, n);
  const t1 = reference.map((v, i) => v - projection * n[i]);
  const norm = magnitude(t1);
  return [t1.map((v) => v / norm), cross(n, t1).map((v) => v / norm)];
}

export function contactHistory(state, supportId, axis = "t1") {
  const states = contactStates(state);
  const first = states.find((s) => s.overlay.data?.contact_results?.[supportId]);
  const frame = contactTangents(first?.overlay.data?.contact_results?.[supportId]?.normal);
  return states.map((option, index) => {
    const data = option.overlay.data;
    const contact = data?.contact_results?.[supportId];
    const tangent = frame?.[axis === "t2" ? 1 : 0];
    const available = contact && tangent && Number.isFinite(magnitude(contact.relative_displacement)) &&
      Number.isFinite(magnitude(contact.tangential_force)) && Number.isFinite(contact.friction_limit) && Number.isFinite(contact.normal_force);
    return { id: option.id, index, label: data?.metadata?.stage_label ?? option.label,
      pseudoTime: data?.metadata?.pseudo_time, contact, available: Boolean(available),
      travel: available ? dot(contact.relative_displacement, tangent) : null,
      force: available ? dot(contact.tangential_force, tangent) : null };
  });
}

export function contactForceMaxima(state) {
  const records = (state.resultStates ?? []).flatMap((s) => Object.values(s.data?.contact_results ?? {}));
  return { normal: Math.max(0, ...records.map((c) => c.normal_force).filter(Number.isFinite)),
    tangential: Math.max(0, ...records.map((c) => magnitude(c.tangential_force)).filter(Number.isFinite)) };
}

export function renderContactReview(state, dispatch, rerender) {
  if (!(state.resultStates ?? []).some((s) => Object.keys(s.data?.contact_results ?? {}).length)) return null;
  const panel = document.createElement("section");
  panel.className = "contact-review";
  panel.setAttribute("aria-label", "Contact review");
  const add = (tag, text, parent = panel) => { const el = document.createElement(tag); el.textContent = text; parent.append(el); return el; };
  const update = (action) => { dispatch(action); rerender(); };
  add("h2", "Contact review — forces on the pipe");
  const states = contactStates(state);
  const activeIndex = states.findIndex((s) => s.id === state.activeResultStateId);
  const navigation = add("div", ""); navigation.className = "contact-step-nav";
  for (const [label, offset] of [["Previous converged step", -1], ["Next converged step", 1]]) {
    const button = add("button", offset < 0 ? "← Previous" : "Next →", navigation);
    button.type = "button"; button.dataset.focusKey = `contact-step:${offset}`; button.setAttribute("aria-label", label);
    button.disabled = !states[activeIndex + offset];
    button.onclick = () => update({ type: "setActiveResultState", resultStateId: states[activeIndex + offset].id });
  }
  const active = getActiveResultState(state)?.overlay.data;
  add("p", `${active?.metadata?.stage_label ?? "Stage unavailable"} · Step ${activeIndex + 1}/${states.length} · Pseudo-time ${formatPseudoTime(active?.metadata?.pseudo_time)}`);
  add("p", `Deformation shown ×${state.visualDeformationScale ?? 1}. Gap, slip and travel below are true values. Support markers remain at their real locations.`);
  for (const [key, label] of [["normal", "Normal-force arrows"], ["tangential", "Tangential-force arrows"]]) {
    const wrapper = add("label", label);
    const input = document.createElement("input"); input.type = "checkbox";
    input.dataset.focusKey = `contact-arrow:${key}`; input.checked = state.contactArrows?.[key] !== false;
    input.onchange = () => update({ type: "setContactArrows", quantity: key, visible: input.checked });
    wrapper.prepend(input);
  }
  const neutralLabel = add("label", "Neutral pipe coloring (contact review)");
  const neutral = document.createElement("input"); neutral.type = "checkbox"; neutral.checked = state.contactNeutral !== false;
  neutral.dataset.focusKey = "contact-neutral";
  neutral.onchange = () => update({ type: "setContactNeutral", neutral: neutral.checked }); neutralLabel.prepend(neutral);
  const contacts = Object.values(contactRecords(state));
  if (!contacts.length) { add("p", "Contact results unavailable for this state."); return panel; }
  const selected = contacts.find((c) => (state.selectedObjectIds ?? []).includes(contactObjectId(state, c.support_id))) ?? contacts[0];
  const system = getUnitSystem(state);
  const quantity = (value, unit) => formatQuantity(value, unit, system) || "unavailable";
  const scroller = add("div", ""); scroller.className = "contact-table-scroll";
  scroller.tabIndex = 0; scroller.setAttribute("role", "region");
  scroller.setAttribute("aria-label", "Contact results, scrolls sideways");
  const table = add("table", "", scroller);
  const header = add("tr", "", add("thead", "", table));
  for (const label of ["Support", "State", "N", "|Ft|", "μN", "Usage", "Gap", "|Slip|"]) add("th", label, header).scope = "col";
  const body = add("tbody", "", table);
  for (const c of contacts) {
    const row = add("tr", "", body); row.dataset.selected = String(c === selected);
    const cell = add("td", "", row); const button = add("button", c.support_id, cell); button.type = "button";
    button.dataset.focusKey = `contact-support:${c.support_id}`;
    const objectId = contactObjectId(state, c.support_id); button.disabled = !objectId;
    button.onclick = () => update({ type: "selectObject", objectId });
    for (const value of [`${CONTACT_SYMBOLS[c.status] ?? "?"} ${contactStatusLabel(c)} (${c.status_source})`, quantity(c.normal_force, "N"),
      quantity(magnitude(c.tangential_force), "N"), quantity(c.friction_limit, "N"),
      c.utilization == null ? "n/a" : `${(100*c.utilization).toFixed(1)}%`, quantity(c.gap, "m"), quantity(magnitude(c.slip), "m")]) add("td", value, row);
    if (c.utilization > 1.001) row.classList.add("contact-limit-exceeded");
  }
  const provenance = add("details", "");
  add("summary", "Contact provenance", provenance);
  for (const key of ["run_id", "analysis_id", "source", "runtime_version", "code_aster_version", "formulation", "convergence_status", "contact_status_tolerances", "contact_variable_mapping", "native_contact_status", "contact_status_basis"]) {
    const value = active?.metadata?.[key];
    if (value != null) add("p", `${key}: ${typeof value === "object" ? JSON.stringify(value) : value}`, provenance);
  }
  add("h3", `Selected shoe ${selected.support_id}`);
  add("p", `Relative displacement: ${selected.relative_displacement.map((v) => quantity(v, "m")).join(", ")} (global X, Y, Z).`);
  const axisLabel = add("label", "History axis ");
  const axis = add("select", "", axisLabel);
  for (const [value, label] of [["t1", "Tangential t1"], ["t2", "Tangential t2"], ["normal", "Normal load vs step"]]) {
    const option = add("option", label, axis); option.value = value;
  }
  axis.dataset.focusKey = "contact-history-axis";
  axis.value = state.contactHistoryAxis ?? "t1";
  axis.onchange = () => update({ type: "setContactHistoryAxis", axis: axis.value });
  panel.append(contactChart(state, selected.support_id));
  add("p", "t1 = projected global X (Y if near parallel to the normal); t2 = normal × t1. Signed travel is relative displacement, not accumulated slip. The projected force plot is not the full vector friction cone. Dashed lines: ±μN.");
  return panel;
}

function contactChart(state, supportId) {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg"); svg.setAttribute("viewBox", "0 0 420 230");
  svg.setAttribute("role", "img"); svg.setAttribute("aria-label", `${supportId} solved contact history with current step and Coulomb envelope`);
  const axis = state.contactHistoryAxis ?? "t1";
  const history = contactHistory(state, supportId, axis);
  const points = history.filter((p) => p.available);
  const system = getUnitSystem(state);
  const xValue = (p) => axis === "normal" ? p.index : toDisplay(p.travel, "m", system);
  const yValue = (p) => toDisplay(axis === "normal" ? p.contact.normal_force : p.force, "N", system);
  const limit = (p) => toDisplay(p.contact.friction_limit, "N", system);
  const xmin = Math.min(0, ...points.map(xValue)), xmax = Math.max(0, ...points.map(xValue));
  const ymax = Math.max(1e-9, ...points.map((p) => Math.max(Math.abs(yValue(p)), axis === "normal" ? 0 : limit(p))));
  const x = (v) => 54 + (v - xmin) / (xmax - xmin || 1) * 345;
  const y = (v) => 108 - v / ymax * 80;
  const element = (tag, attrs, text) => { const el = document.createElementNS(ns, tag); for (const [k,v] of Object.entries(attrs)) el.setAttribute(k, v); if (text) el.textContent = text; svg.append(el); return el; };
  element("path", { d: "M54 20V190H400 M54 108H400", stroke: "#64748b", fill: "none" });
  for (const [readY, color, dash] of [[yValue, "#0f766e", ""], ...(axis === "normal" ? [] : [[limit, "#64748b", "5 4"], [(p) => -limit(p), "#64748b", "5 4"]])]) {
    let pen = false;
    const path = history.map((p) => { if (!p.available) { pen = false; return ""; } const command = `${pen ? "L" : "M"}${x(xValue(p))},${y(readY(p))}`; pen = true; return command; }).join(" ");
    element("path", { d: path, stroke: color, "stroke-width": 2, "stroke-dasharray": dash, fill: "none" });
  }
  for (const p of points) {
    const point = element("circle", { cx: x(xValue(p)), cy: y(yValue(p)), r: 2, fill: "#0f766e" });
    const title = document.createElementNS(ns, "title"); title.textContent = `${p.label} / pseudo-time ${formatPseudoTime(p.pseudoTime)}`; point.append(title);
  }
  const current = points.find((p) => p.id === state.activeResultStateId);
  if (current) element("circle", { cx: x(xValue(current)), cy: y(yValue(current)), r: 5, fill: "#1e293b" });
  element("text", { x: 54, y: 14, "font-size": 11 }, `${axis === "normal" ? "N" : `Ft ${axis}`} [${displayUnit("N", system)}], ±${Number(ymax.toPrecision(4))}`);
  element("text", { x: 54, y: 209, "font-size": 11 }, `${axis === "normal" ? "Converged step" : `Signed ${axis} travel [${displayUnit("m", system)}]`}: ${Number(xmin.toPrecision(4))} … ${Number(xmax.toPrecision(4))}`);
  element("text", { x: 54, y: 225, "font-size": 10 }, current ? `${current.label} · pseudo-time ${formatPseudoTime(current.pseudoTime)}` : "Current contact data unavailable");
  return svg;
}
