import { getActiveResultState, getActiveStageIndex, getResultStateOptions, getStageGroups, formatPseudoTime } from "./resultReview.js";
import { resolveEntityObjectId } from "./reviewSelection.js";
import { displayUnit, formatQuantity, getUnitSystem, toDisplay } from "./units.js";

export const CONTACT_SYMBOLS = { open: "○", sticking: "■", sliding: "➜", indeterminate: "?" };
export const CONTACT_COLORS = { open: 0x64748b, sticking: 0x2563eb, sliding: 0x0f766e, indeterminate: 0x92400e };
export const magnitude = (v) => Array.isArray(v) && v.length === 3 && v.every(Number.isFinite) ? Math.hypot(...v) : NaN;
const dot = (a, b) => a.reduce((sum, value, i) => sum + value * b[i], 0);
const cross = (a, b) => [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]];

// The stage of a shoe's history, in the order a reviewer meets them.
const FINDING_TITLES = {
  slip: "slid on its friction cone",
  lift_off: "lifted clear",
  reseat: "reseated",
  force_reversal: "reversed its tangential force",
  over_limit: "reported friction beyond its cone",
  unloaded: "carried no normal force"
};
// Tie-break for two findings in the same stage, so a run of them reads in the
// order the shoes did it rather than in object order.
const STAGE_TIEBREAK = ["lift_off", "over_limit", "slip", "unloaded", "force_reversal", "reseat"];

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

// The load path, in words. The solver wrote every instant; the derivation in
// Python wrote down what changed between them; this turns that into the one
// paragraph a reviewer would otherwise have to reconstruct from the table.
//
// Quantities are formatted here rather than in the bundle because this is the
// only place that knows the reader's unit system.
function findingSentence(finding, system) {
  const qty = (value, unit) => formatQuantity(value, unit, system) || "unavailable";
  const title = FINDING_TITLES[finding.kind] ?? finding.kind.replaceAll("_", " ");
  const supports = finding.support_ids?.join(", ") ?? "the shoe";
  const where = finding.spans_stages
    ? `from ${finding.stage_label} through ${finding.final_stage_label}`
    : `at ${finding.stage_label}`;
  const values = finding.values ?? {};
  const detail = [];
  if (Number.isFinite(values.tangential_force_n)) {
    detail.push(`${qty(values.tangential_force_n, "N")} tangential against a ${qty(values.friction_limit_n, "N")} cone`);
  }
  if (Number.isFinite(values.slip_m) && values.slip_m > 0) {
    detail.push(`${qty(values.slip_m, "m")} slip`);
  }
  if (Number.isFinite(values.gap_m) && values.gap_m > 0) {
    detail.push(`clear by ${qty(values.gap_m, "m")}`);
  }
  if (Number.isFinite(values.normal_force_n)) {
    detail.push(`${qty(values.normal_force_n, "N")} normal`);
  }
  return `${supports} ${title} ${where}${detail.length ? ` — ${detail.join(", ")}` : ""}.`;
}

export function contactNarrative(state) {
  const run = state.contactFindings?.primary ?? null;
  if (!run) return null;
  const system = getUnitSystem(state);
  // Ordered by the load path, not by how alarming each finding is. The whole
  // point of publishing the sequence is that it reads as one: a shoe that slid
  // from Hot through Lift and then lifted clear at Lift is a single story, and
  // ranking the findings by kind would scatter it into unrelated alarms.
  // Attention is carried by the mark on each line instead.
  const findings = [...(run.findings ?? [])].sort(
    (left, right) =>
      left.stage_index - right.stage_index ||
      STAGE_TIEBREAK.indexOf(left.kind) - STAGE_TIEBREAK.indexOf(right.kind) ||
      (left.support_ids ?? []).join().localeCompare((right.support_ids ?? []).join())
  );
  const frictionless = (run.shoes ?? []).filter((shoe) => shoe.frictionless);
  const carried = (run.shoes ?? []).filter((shoe) => !shoe.frictionless);
  const lines = [];
  if (findings.length) {
    for (const finding of findings) {
      const item = document.createElement("li");
      item.className = `contact-finding contact-finding-${finding.severity}`;
      item.dataset.stageIndex = String(finding.stage_index);
      item.dataset.kind = finding.kind;
      item.dataset.severity = finding.severity;
      item.dataset.focusKey = `contact-finding:${finding.id}`;
      item.textContent = findingSentence(finding, system);
      lines.push(item);
    }
  } else if (carried.length === 0) {
    // Every shoe here is mu = 0, so "nothing moved" and "nothing could" are the
    // same statement. Saying "0 shoes stayed stuck" would read as a defect.
    const item = document.createElement("li");
    item.className = "contact-finding";
    item.textContent =
      `No shoe has a friction coefficient, so none of the ${(run.shoe_count ?? 0)} shoes in this run ` +
      `carries a Coulomb cone. There is no friction to review here - it is a comparison, not a demonstration.`;
    lines.push(item);
  } else {
    const item = document.createElement("li");
    item.className = "contact-finding";
    item.textContent =
      `No shoe moved across the ${run.stage_count} published stages: every one of the ` +
      `${carried.length} shoes with a friction coefficient stayed seated and stuck.`;
    lines.push(item);
  }
  // A mu = 0 shoe reads "indeterminate", which looks like a solver failure and is
  // not one. The derivation already carries the explanation; publish it, because
  // the row label alone does not say why there is no cone.
  for (const shoe of frictionless) {
    if (!shoe.note) continue;
    const item = document.createElement("li");
    item.className = "contact-finding contact-finding-frictionless";
    item.dataset.kind = "frictionless";
    item.dataset.supportId = shoe.support_id;
    item.dataset.focusKey = `contact-frictionless:${shoe.support_id}`;
    item.textContent = `${shoe.support_id}: ${shoe.note}`;
    lines.push(item);
  }
  return { findings, lines, frictionless };
}

// The stage navigator. The step this control replaces was a fifty-one row
// dropdown of "Cold / 0.3", "Hot / 2" labels; this is the five stages a cycle
// actually has, each jumping to the converged state that stage ended on.
export function contactStageNav(state, dispatch, rerender) {
  const groups = getStageGroups(state);
  if (groups.length < 2) return null;
  const activeIndex = getActiveStageIndex(state);
  const nav = document.createElement("div");
  nav.className = "contact-step-nav";
  nav.setAttribute("role", "group");
  nav.setAttribute("aria-label", "Load path stages");
  const update = (resultStateId) => {
    dispatch({ type: "setActiveResultState", resultStateId });
    rerender();
  };
  for (const group of groups) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = group.label;
    button.dataset.focusKey = `contact-stage:${group.index}`;
    button.dataset.stageIndex = String(group.index);
    button.setAttribute("aria-pressed", String(group.index === activeIndex));
    button.title = `${group.label} — ${group.incrementCount} converged increments`;
    const attention = group.findings.filter((finding) => finding.severity === "attention");
    button.dataset.hasFinding = String(attention.length > 0);
    button.classList.toggle("is-active", group.index === activeIndex);
    button.onclick = () => update(group.resultStateId);
    nav.append(button);
  }
  const steps = railRow("Increment", stepScrubber(state, groups, update));
  return { nav, steps };
}

function stepScrubber(state, groups, update) {
  const wrapper = document.createElement("div");
  wrapper.className = "contact-increment";
  const activeIndex = getActiveStageIndex(state);
  const group = groups.find((candidate) => candidate.index === activeIndex) ?? groups[0];
  const activeId = getActiveResultState(state)?.id;
  const position = Math.max(0, group.resultStateIds.indexOf(activeId));
  const input = document.createElement("input");
  input.type = "range";
  input.min = "0";
  input.max = String(Math.max(0, group.resultStateIds.length - 1));
  input.value = String(position);
  input.disabled = group.resultStateIds.length < 2;
  input.dataset.focusKey = "contact-increment";
  input.setAttribute("aria-label", `Converged increment within ${group.label}`);
  input.oninput = () => {
    const target = group.resultStateIds[Number(input.value)];
    if (target && target !== state.activeResultStateId) update(target);
  };
  const readout = document.createElement("span");
  readout.className = "contact-increment-readout";
  readout.textContent = `${position + 1} / ${group.resultStateIds.length}`;
  wrapper.append(input, readout);
  return wrapper;
}

function railRow(label, control) {
  const row = document.createElement("div");
  row.className = "contact-nav-row";
  const caption = document.createElement("span");
  caption.className = "contact-nav-label";
  caption.textContent = label;
  row.append(caption, control);
  return row;
}

export function renderContactReview(state, dispatch, rerender, part = "table", objectId = null) {
  if (!(state.resultStates ?? []).some((s) => Object.keys(s.data?.contact_results ?? {}).length)) return null;
  const panel = document.createElement("section");
  panel.className = "contact-review";
  panel.setAttribute("aria-label", "Contact review");
  const add = (tag, text, parent = panel) => { const el = document.createElement(tag); el.textContent = text; parent.append(el); return el; };
  const update = (action) => { dispatch(action); rerender(); };
  const active = getActiveResultState(state)?.overlay.data;
  if (part === "display") {
    for (const [key, label] of [["normal", "Normal-force arrows"], ["tangential", "Tangential-force arrows"]]) {
      const wrapper = add("label", label);
      const input = document.createElement("input"); input.type = "checkbox";
      input.dataset.focusKey = `contact-arrow:${key}`; input.checked = state.contactArrows?.[key] !== false;
      input.onchange = () => update({ type: "setContactArrows", quantity: key, visible: input.checked });
      wrapper.prepend(input);
    }
    const neutralLabel = add("label", "Neutral pipe colouring (contact review)");
    const neutral = document.createElement("input"); neutral.type = "checkbox"; neutral.checked = state.contactNeutral !== false;
    neutral.dataset.focusKey = "contact-neutral";
    neutral.onchange = () => update({ type: "setContactNeutral", neutral: neutral.checked }); neutralLabel.prepend(neutral);
    return panel;
  }
  const contacts = Object.values(contactRecords(state));
  const selected = contacts.find(c => contactObjectId(state, c.support_id) === objectId);
  const system = getUnitSystem(state);
  const quantity = (value, unit) => formatQuantity(value, unit, system) || "unavailable";
  if (part === "selection") {
    if (!selected) return null;
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
  add("h2", "Contact forces on the pipe");
  add("p", `Gap, slip and travel are true values. Deformation shown \u00d7${state.visualDeformationScale ?? 1}.`);
  const narrative = contactNarrative(state);
  if (narrative) {
    const list = add("ol", "", panel);
    list.className = "contact-findings";
    list.append(...narrative.lines);
  }
  if (!contacts.length) { add("p", "Contact results unavailable for this state."); return panel; }
  const groups = getStageGroups(state);
  const shoes = state.contactFindings?.primary?.shoes ?? [];
  // The cone threshold is published by the derivation rather than repeated here:
  // it has to sit above a solved slide's float noise and below the native
  // reader's own acceptance tolerance, and a third copy of that number is how
  // the finding ends up unreachable.
  const overLimit = state.contactFindings?.over_limit_utilization ?? 1.0001;
  // The strip needs the published per-stage summaries. Without them every stage
  // cell would be an unknown, which reads as "nothing happened" rather than
  // "this bundle has no story", so it degrades to the single-instant table.
  const staged = groups.length > 1 && shoes.length > 0;
  const scroller = add("div", "", panel);
  if (staged) scroller.className = "contact-table-scroll contact-strip-wrap";
  scroller.tabIndex = 0; scroller.setAttribute("role", "region");
  scroller.setAttribute("aria-label", staged
    ? "Contact results, with one column per load path stage, scrolls sideways"
    : "Contact results, scrolls sideways");
  const table = add("table", "", scroller);
  if (staged) table.className = "contact-strip";
  const header = add("tr", "", add("thead", "", table));
  for (const label of ["Support", "State", "N", "|Ft|", "μN", "Usage", "Gap", "|Slip|"]) add("th", label, header).scope = "col";
  // One column per stage, so a shoe's whole cycle reads across the row without
  // scrubbing. The numbers that follow stay on the active increment, because
  // they are the instant the 3D view is showing.
  for (const group of groups) {
    const cell = add("th", group.label, header);
    cell.scope = "col";
    cell.className = "contact-strip-head";
    cell.title = `${group.label} — ${group.incrementCount} converged increments`;
  }
  const body = add("tbody", "", table);
  const activeStage = getActiveStageIndex(state);
  for (const c of contacts) {
    const row = add("tr", "", body); row.dataset.selected = String((state.selectedObjectIds ?? []).includes(contactObjectId(state, c.support_id)));
    const cell = add("td", "", row); const button = add("button", c.support_id, cell); button.type = "button";
    button.dataset.focusKey = `contact-support:${c.support_id}`;
    const objectId = contactObjectId(state, c.support_id); button.disabled = !objectId;
    button.onclick = event => update({ type: "selectObject", objectId, additive: event.shiftKey });
    for (const value of [`${CONTACT_SYMBOLS[c.status] ?? "?"} ${contactStatusLabel(c)} (${c.status_source})`, quantity(c.normal_force, "N"),
      quantity(magnitude(c.tangential_force), "N"), quantity(c.friction_limit, "N"),
      c.utilization == null ? "n/a" : `${(100*c.utilization).toFixed(1)}%`, quantity(c.gap, "m"), quantity(magnitude(c.slip), "m")]) add("td", value, row);
    const shoe = shoes.find((entry) => entry.support_id === c.support_id) ?? null;
    for (const group of groups) {
      const summary = shoe?.stages?.find((entry) => entry.index === group.index) ?? null;
      const cell = add("td", "", row);
      cell.className = "contact-strip-cell";
      cell.dataset.stageIndex = String(group.index);
      // What happened anywhere in the stage, not what it ended on: a shoe that
      // slid for nine of ten increments and re-stuck must not read as stuck.
      const shown = summary?.governing_status ?? summary?.status;
      cell.dataset.status = shown ?? "unknown";
      if (group.index === activeStage) cell.classList.add("is-active");
      if (summary?.transitioned) cell.dataset.transitioned = "true";
      const symbol = CONTACT_SYMBOLS[shown] ?? "·";
      cell.textContent = symbol;
      const utilization = summary?.peak_utilization;
      cell.title = stageCellTitle(c.support_id, group, summary, system, quantity);
      if (utilization != null && utilization > overLimit) cell.classList.add("is-over-limit");
    }
    if (c.utilization > overLimit) row.classList.add("contact-limit-exceeded");
  }
  const provenance = add("details", "");
  add("summary", "Contact provenance", provenance);
  for (const key of ["run_id", "analysis_id", "source", "runtime_version", "code_aster_version", "formulation", "convergence_status", "contact_status_tolerances", "contact_variable_mapping", "native_contact_status", "contact_status_basis"]) {
    const value = active?.metadata?.[key];
    if (value != null) add("p", `${key}: ${typeof value === "object" ? JSON.stringify(value) : value}`, provenance);
  }
  return panel;
}

function stageCellTitle(supportId, group, summary, system, quantity) {
  if (!summary) return `${supportId}: no contact result in ${group.label}`;
  const parts = [`${supportId} at ${group.label}`];
  const seen = summary.statuses ?? [summary.status];
  // Say the whole sequence when the stage held more than one state: naming only
  // the governing one would hide that the shoe came back.
  parts.push(seen.length > 1 ? seen.join(" then ") : summary.status);
  if (summary.transitioned && summary.status !== summary.governing_status) {
    parts.push(`ended on ${summary.status}`);
  }
  if (summary.peak_normal_force_n > 0) parts.push(`peak N ${quantity(summary.peak_normal_force_n, "N")}`);
  if (summary.peak_tangential_force_n > 0) {
    parts.push(`peak |Ft| ${quantity(summary.peak_tangential_force_n, "N")}`);
  }
  if (summary.peak_utilization != null) {
    parts.push(`${(100 * summary.peak_utilization).toFixed(1)}% of cone`);
  }
  if (summary.peak_gap_m > 0) parts.push(`clear ${quantity(summary.peak_gap_m, "m")}`);
  if (summary.peak_slip_m > 0) parts.push(`slip ${quantity(summary.peak_slip_m, "m")}`);
  return parts.join(" · ");
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
