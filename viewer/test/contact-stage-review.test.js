// The contact review, rendered.
//
// The three things that made a staged friction run unreadable are all here: a
// fifty-one row step menu instead of the five stages of the load path, a table
// that described one instant at a time, and no sentence anywhere saying what the
// shoes actually did. These tests render the real panel and read its text.

import assert from "node:assert/strict";
import test from "node:test";
import { contactStageNav, renderContactReview } from "../src/contactReview.js";
import { getStageGroups } from "../src/resultReview.js";

// A minimal DOM: the panel is built with createElement, dataset, classList and
// append, and the tests need the text that came out the far end.
function shim() {
  const original = globalThis.document;
  const make = (tag) => {
    const classes = new Set();
    const element = {
      tagName: String(tag).toUpperCase(),
      children: [],
      dataset: {},
      attributes: {},
      textContent: "",
      prepend(...nodes) { this.children.unshift(...nodes); },
      append(...nodes) { this.children.push(...nodes); },
      setAttribute(name, value) { this.attributes[name] = String(value); },
      getAttribute(name) { return this.attributes[name] ?? null; },
      classList: {
        add: (...names) => names.forEach((name) => classes.add(name)),
        remove: (...names) => names.forEach((name) => classes.delete(name)),
        contains: (name) => classes.has(name),
        toggle: (name, on) => (on ? classes.add(name) : classes.delete(name))
      },
      get classes() { return [...classes]; }
    };
    // In a browser assigning className rewrites the class list, and the panel
    // code does both. Without this the shim would report elements as having no
    // class at all, and every lookup by class would silently miss.
    Object.defineProperty(element, "className", {
      get: () => [...classes].join(" "),
      set: (value) => {
        classes.clear();
        String(value).split(/\s+/).filter(Boolean).forEach((name) => classes.add(name));
      }
    });
    return element;
  };
  globalThis.document = { createElement: make, createElementNS: (_ns, tag) => make(tag) };
  return {
    restore: () => { globalThis.document = original; },
    text: (node) => {
      if (node == null) return "";
      if (typeof node === "string") return node;
      if (Array.isArray(node)) return node.map((child) => shimText(child)).join(" ");
      return [node.textContent ?? "", ...node.children.map((child) => shimText(child))].join(" ");
    }
  };
}
const shimText = (node) => {
  if (node == null) return "";
  if (typeof node === "string") return node;
  return [node.textContent ?? "", ...(node.children ?? []).map(shimText)].join(" ");
};
const find = (node, predicate) => {
  if (node == null) return null;
  if (predicate(node)) return node;
  for (const child of node.children ?? []) {
    const hit = find(child, predicate);
    if (hit) return hit;
  }
  return null;
};
const findAll = (node, predicate, hits = []) => {
  if (node == null) return hits;
  if (predicate(node)) hits.push(node);
  for (const child of node.children ?? []) findAll(child, predicate, hits);
  return hits;
};

// A solved cycle in the shape the Python derivation publishes: reference, then
// Cold / Hot / Cold / Lift / Cold, two increments per stage, two shoes. S1 sits
// on its cone from Hot through Lift and S2 lifts clear at Lift.
const PATH = ["Reference", "Cold", "Hot", "Cold", "Lift", "Cold"];
const INCREMENTS = 2;

function contact(supportId, { status = "sticking", normalForce = 10000, tangential = [0, 0, 0], mu = 0.3, gap = 0, slip = [0, 0, 0] } = {}) {
  const limit = mu * Math.max(0, normalForce);
  const magnitude = Math.hypot(...tangential);
  return {
    support_id: supportId,
    node_id: `n_${supportId}`,
    status,
    status_source: "solver",
    normal: [0, 0, 1],
    normal_force: normalForce,
    tangential_force: tangential,
    gap,
    relative_displacement: tangential,
    slip,
    friction_limit: limit,
    utilization: limit > 1e-9 && status !== "open" ? magnitude / limit : null
  };
}

// stage index -> the contact each shoe shows at that stage's final increment
const CYCLE = {
  0: { S1: contact("S1", { normalForce: 0, mu: 0 }), S2: contact("S2", { normalForce: 0, mu: 0 }) },
  1: { S1: contact("S1"), S2: contact("S2") },
  2: { S1: contact("S1", { status: "sliding", tangential: [-3000, 0, 0], slip: [0.0024, 0, 0] }), S2: contact("S2", { tangential: [-700, 0, 0] }) },
  3: { S1: contact("S1", { status: "sliding", tangential: [3100, 0, 0], slip: [0.0005, 0, 0] }), S2: contact("S2", { tangential: [80, 0, 0] }) },
  4: { S1: contact("S1", { status: "sliding", tangential: [-3150, 0, 0], slip: [0.0005, 0, 0] }), S2: contact("S2", { normalForce: 0, status: "open", gap: 0.00375, mu: 0 }) },
  5: { S1: contact("S1", { tangential: [-3150, 0, 0], slip: [0.0005, 0, 0] }), S2: contact("S2", { mu: 0 }) }
};

function fixture() {
  const resultStates = [];
  for (const [index, label] of PATH.entries()) {
    for (let step = 0; step < INCREMENTS; step += 1) {
      const pseudoTime = index + step / INCREMENTS;
      const final = step === INCREMENTS - 1;
      resultStates.push({
        kind: "result_state",
        id: `state-${index}-${step}`,
        data: {
          id: `state-${index}-${step}`,
          load_case: "Cycle",
          metadata: { run_id: "run-1", pseudo_time: pseudoTime, stage_index: index, stage_label: label },
          contact_results: final
            ? CYCLE[index]
            // A mid-stage increment is still a solved increment; the shoe simply
            // has not got there yet.
            : { S1: contact("S1"), S2: contact("S2") }
        }
      });
    }
  }
  const stages = PATH.map((label, index) => ({
    index,
    label,
    pseudo_time: index,
    load_case: "Cycle",
    result_state_id: `state-${index}-${INCREMENTS - 1}`,
    result_state_ids: Array.from({ length: INCREMENTS }, (_, step) => `state-${index}-${step}`),
    increment_count: INCREMENTS
  }));
  const run = {
    run_id: "run-1",
    load_case: "Cycle",
    stage_count: stages.length,
    shoe_count: 2,
    stages,
    shoes: ["S1", "S2"].map((supportId) => ({
          support_id: supportId,
          frictionless: supportId === "S2" && CYCLE[5][supportId].friction_limit === 0,
          note: "",
          ever_slid: stages.some((stage) => CYCLE[stage.index][supportId].status === "sliding"),
          ever_open: stages.some((stage) => CYCLE[stage.index][supportId].status === "open"),
          peak_normal_force_n: 10000,
          peak_tangential_force_n: 3150,
          peak_utilization: 1,
          peak_slip_m: 0.0024,
          max_gap_m: 0.00375,
          final_status: CYCLE[5][supportId].status,
          stages: stages.map((stage) => {
            const record = CYCLE[stage.index][supportId];
            return {
              index: stage.index,
              label: stage.label,
              pseudo_time: stage.pseudo_time,
              result_state_id: stage.result_state_id,
              status: record.status,
              statuses: [record.status],
              transitioned: false,
              normal_force_n: record.normal_force,
              tangential_force_n: Math.hypot(...record.tangential_force),
              friction_limit_n: record.friction_limit,
              utilization: record.utilization,
              gap_m: record.gap,
              slip_m: Math.hypot(...record.slip),
              peak_normal_force_n: record.normal_force,
              peak_tangential_force_n: Math.hypot(...record.tangential_force),
              peak_slip_m: Math.hypot(...record.slip),
              peak_gap_m: record.gap,
              peak_utilization: record.utilization
            };
          })
        })),
        findings: [
          { id: "contact_finding:000", kind: "slip", severity: "attention", support_ids: ["S1"],
            stage_index: 2, stage_indices: [2, 3, 4], stage_label: "Hot", final_stage_label: "Lift",
            spans_stages: true, pseudo_time: 2, result_state_id: "state-2-1",
            values: { tangential_force_n: 3150, friction_limit_n: 3000, utilization: 1, slip_m: 0.0024, normal_force_n: 10000 },
            note: "The tangential force reached the Coulomb cone, so the shoe slid instead of sticking." },
          { id: "contact_finding:001", kind: "lift_off", severity: "attention", support_ids: ["S2"],
            stage_index: 4, stage_indices: [4], stage_label: "Lift", final_stage_label: "Lift",
            spans_stages: false, pseudo_time: 4, result_state_id: "state-4-1",
            values: { gap_m: 0.00375, normal_force_n: 0, friction_limit_n: 0 },
            note: "The shoe left the surface, so its friction capacity fell to zero while it is clear." },
          { id: "contact_finding:002", kind: "reseat", severity: "info", support_ids: ["S2"],
            stage_index: 5, stage_indices: [5], stage_label: "Cold", final_stage_label: "Cold",
            spans_stages: false, pseudo_time: 5, result_state_id: "state-5-1",
            values: { normal_force_n: 10000, friction_limit_n: 0, gap_m: 0 },
            note: "The shoe came back down onto the surface and carries load again." }
        ],
        attention_count: 2
  };
  return {
    reviewFocus: "contact",
    resultStates,
    overlays: resultStates,
    activeResultStateId: "state-2-1",
    activeLoadCase: "Cycle",
    unitSystem: "engineering",
    visualDeformationScale: 20,
    geometryStates: [],
    geometryPayloads: [],
    selectedObjectIds: [],
    objects: [
      { id: "shoe-S1", entity_ref: "support:S1" },
      { id: "shoe-S2", entity_ref: "support:S2" }
    ],
    // `primary` is what the scene loader resolves for a reader; the rest of the
    // block is the published shape.
    contactFindings: { schema: "tuba.contact_findings.v1", primary_run_id: "run-1", primary: run, runs: [run] }
  };
}

const noop = () => {};
test("the load path is navigable as stages, not as a list of every increment", () => {
  const state = fixture();
  const groups = getStageGroups(state);
  assert.equal(groups.length, PATH.length);
  assert.deepEqual(groups.map((group) => group.label), PATH);
  // Each stage points at the increment it ended on, which is what a reviewer
  // means by "Hot" - not at the first increment after the load changed.
  assert.equal(groups[2].resultStateId, "state-2-1");
  assert.equal(groups[2].firstResultStateId, "state-2-0");
  assert.equal(groups[2].incrementCount, INCREMENTS);
  assert.deepEqual(groups[2].findings.map((finding) => finding.kind), ["slip"]);
  assert.deepEqual(groups[1].findings, []);
});

test("the stage navigator marks the current stage and the stages worth looking at", () => {
  const dom = shim();
  try {
    const state = fixture();
    const built = contactStageNav(state, noop, noop);
    const buttons = built.nav.children;
    assert.equal(buttons.length, PATH.length);
    assert.deepEqual(buttons.map((button) => button.textContent), PATH);
    // The scene is open on the end of Hot, so Hot is the active chip.
    assert.equal(find(built.nav, (node) => node.dataset.focusKey === "contact-stage:2").getAttribute("aria-pressed"), "true");
    assert.equal(buttons.filter((button) => button.getAttribute("aria-pressed") === "true").length, 1);
    // Hot and Lift contain an attention finding; Cold and Reference do not.
    assert.equal(buttons[2].dataset.hasFinding, "true");
    assert.equal(buttons[4].dataset.hasFinding, "true");
    assert.equal(buttons[1].dataset.hasFinding, "false");
  } finally {
    dom.restore();
  }
});

test("a stage chip moves the scene to that stage's converged increment", () => {
  const dom = shim();
  try {
    const state = fixture();
    const actions = [];
    const built = contactStageNav(state, (action) => actions.push(action), noop);
    built.nav.children[4].onclick();
    assert.deepEqual(actions, [{ type: "setActiveResultState", resultStateId: "state-4-1" }]);
  } finally {
    dom.restore();
  }
});

test("the increment scrubber steps inside a stage and reads its position", () => {
  const dom = shim();
  try {
    const state = fixture();
    const actions = [];
    const built = contactStageNav(state, (action) => actions.push(action), noop);
    const slider = find(built.steps, (node) => node.type === "range");
    assert.equal(slider.min, "0");
    assert.equal(slider.max, String(INCREMENTS - 1));
    assert.equal(slider.value, "1", "the scene is on the last increment of Hot");
    const readout = find(built.steps, (node) => node.textContent?.includes("/"));
    assert.match(readout.textContent, new RegExp(`${INCREMENTS} / ${INCREMENTS}`));
    slider.value = "0";
    slider.oninput();
    assert.deepEqual(actions, [{ type: "setActiveResultState", resultStateId: "state-2-0" }]);
  } finally {
    dom.restore();
  }
});

test("the panel says what the shoes did, before it shows the numbers", () => {
  const dom = shim();
  try {
    const state = fixture();
    const panel = renderContactReview(state, noop, noop, "table");
    const lines = findAll(panel, (node) => node.classList?.contains("contact-finding"));
    assert.equal(lines.length, 3);
    // Attention first, because that is what a reviewer has to sign off.
    assert.equal(lines[0].dataset.kind, "slip");
    assert.equal(lines[0].classList.contains("contact-finding-attention"), true);
    assert.equal(lines[1].dataset.kind, "lift_off");
    assert.equal(lines[2].dataset.kind, "reseat");
    assert.equal(lines[2].classList.contains("contact-finding-attention"), false);

    // Quantities are formatted in the reader's units, not the bundle's.
    assert.match(dom.text(lines[0]), /S1 slid on its friction cone from Hot through Lift/);
    assert.match(dom.text(lines[0]), /3\.15 kN tangential against a 3 kN cone/);
    assert.match(dom.text(lines[0]), /2\.4 mm slip/);
    assert.match(dom.text(lines[1]), /S2 lifted clear at Lift/);
    assert.match(dom.text(lines[1]), /clear by 3\.75 mm/);
    assert.match(dom.text(lines[2]), /S2 reseated at Cold/);
  } finally {
    dom.restore();
  }
});

test("the table reads a shoe's whole cycle across one row", () => {
  const dom = shim();
  try {
    const state = fixture();
    const panel = renderContactReview(state, noop, noop, "table");
    const table = find(panel, (node) => node.classList?.contains("contact-strip"));
    assert.ok(table, "a staged review renders the per-stage strip");

    const headers = find(table, (node) => node.tagName === "TR").children;
    assert.deepEqual(headers.slice(-PATH.length).map((cell) => cell.textContent), PATH);

    const rows = findAll(find(table, (node) => node.tagName === "TBODY"), (node) => node.tagName === "TR");
    assert.equal(rows.length, 2);
    // Each row is one shoe's whole cycle, read left to right across the stages.
    // S1 slides from Hot through Lift; S2 never slides and leaves the surface at
    // Lift instead. Neither needs the reader to scrub to see that.
    const expectations = [
      { id: "S1", statuses: ["sticking", "sticking", "sliding", "sliding", "sliding", "sticking"] },
      { id: "S2", statuses: ["sticking", "sticking", "sticking", "sticking", "open", "sticking"] }
    ];
    rows.forEach((row, index) => {
      const cells = row.children.filter((cell) => cell.classList?.contains("contact-strip-cell"));
      assert.equal(cells.length, PATH.length, expectations[index].id);
      assert.equal(dom.text(row.children[0]).trim(), expectations[index].id);
      assert.deepEqual(cells.map((cell) => cell.dataset.status), expectations[index].statuses);
      // Only the stage the scene is open on is highlighted, and every symbol
      // the reader relies on must be a known contact state.
      const active = cells.filter((cell) => cell.classList.contains("is-active"));
      assert.equal(active.length, 1);
      assert.equal(active[0].dataset.stageIndex, "2");
      for (const cell of cells) assert.notEqual(cell.dataset.status, "unknown");
    });
    // The lift-off is the one cell that must not look calm, and its tooltip has
    // to carry the number, because the cell itself is one glyph.
    const s2Cells = rows[1].children.filter((cell) => cell.classList?.contains("contact-strip-cell"));
    assert.equal(s2Cells[4].dataset.status, "open");
    assert.match(s2Cells[4].title, /clear 3\.75 mm/);
    assert.match(s2Cells[2].title, /S2 at Hot · sticking · peak N 10 kN · peak \|Ft\| 0\.7 kN · 23\.3% of cone/);
  } finally {
    dom.restore();
  }
});

test("a review with no findings says the run was inert rather than showing an empty list", () => {
  const dom = shim();
  try {
    const state = fixture();
    state.contactFindings.runs[0].findings = [];
    state.contactFindings.runs[0].attention_count = 0;
    const panel = renderContactReview(state, noop, noop, "table");
    const lines = findAll(panel, (node) => node.classList?.contains("contact-finding"));
    assert.equal(lines.length, 1);
    assert.match(dom.text(lines[0]), /No shoe moved across the 6 published stages/);
  } finally {
    dom.restore();
  }
});

test("a frictionless shoe is explained, because indeterminate reads as a failure", () => {
  const dom = shim();
  try {
    const state = fixture();
    state.contactFindings.runs[0].shoes.find((s) => s.support_id === "S2").note =
      "Friction coefficient is zero, so this shoe has no Coulomb cone: it carries " +
      "compression only and has no stick/slip classification.";
    const panel = renderContactReview(state, noop, noop, "table");
    const lines = findAll(panel, (node) => node.classList?.contains("contact-finding"));
    const note = lines.find((line) => line.dataset?.kind === "frictionless");
    assert.ok(note, "the derivation's explanation has to reach the reader");
    assert.match(dom.text(note), /S2: Friction coefficient is zero/);
    // An explanation is not an alarm.
    assert.equal(note.classList.contains("contact-finding-attention"), false);
    assert.equal(note.classList.contains("contact-finding-frictionless"), true);
  } finally {
    dom.restore();
  }
});

test("an all-frictionless run does not claim that zero shoes stayed stuck", () => {
  const dom = shim();
  try {
    const state = fixture();
    const run = state.contactFindings.runs[0];
    run.findings = [];
    run.shoe_count = 2;
    for (const shoe of run.shoes) { shoe.frictionless = true; shoe.note = "no cone"; }
    const panel = renderContactReview(state, noop, noop, "table");
    const text = dom.text(panel);
    assert.doesNotMatch(text, /0 shoes/);
    assert.match(text, /No shoe has a friction coefficient/);
  } finally {
    dom.restore();
  }
});

test("a stage column reports what happened in the stage, not only where it ended", () => {
  const dom = shim();
  try {
    const state = fixture();
    // S1 slid through most of the Hot stage and re-stuck on its last increment.
    const hot = state.contactFindings.runs[0].shoes
      .find((s) => s.support_id === "S1").stages.find((s) => s.index === 2);
    hot.status = "sticking";
    hot.governing_status = "sliding";
    hot.statuses = ["sliding", "sticking"];
    hot.transitioned = true;
    const panel = renderContactReview(state, noop, noop, "table");
    const table = find(panel, (node) => node.classList?.contains("contact-strip"));
    const row = findAll(find(table, (node) => node.tagName === "TBODY"), (node) => node.tagName === "TR")[0];
    const cells = row.children.filter((cell) => cell.classList?.contains("contact-strip-cell"));
    const hotCell = cells.find((cell) => cell.dataset.stageIndex === "2");
    assert.equal(hotCell.dataset.status, "sliding", "the reader must not see a shoe that never moved");
    assert.equal(hotCell.dataset.transitioned, "true");
    assert.match(hotCell.title, /sliding then sticking/);
    assert.match(hotCell.title, /ended on sticking/);
  } finally {
    dom.restore();
  }
});

test("every shoe is drawn on one plot, so two shoes can be compared at a glance", () => {
  const dom = shim();
  try {
    const state = fixture();
    const panel = renderContactReview(state, noop, noop, "table");
    const plot = find(panel, (node) => node.tagName === "SVG");
    assert.ok(plot, "the panel carries the all-shoes plot the per-shoe chart cannot replace");
    // One solid force line and two dashed cone lines per shoe.
    const paths = findAll(plot, (node) => node.tagName === "PATH" && node.getAttribute("stroke") !== "#64748b");
    assert.equal(paths.length, 6, "two shoes x (force + 2 cone bounds)");
    assert.equal(paths.filter((p) => p.getAttribute("stroke-dasharray") === null).length, 2,
      "the force line carries no dash attribute at all, so solid and dashed differ in the DOM");
    // Distinct hue per shoe, or the comparison is not readable.
    const solids = paths.filter((p) => !p.getAttribute("stroke-dasharray"));
    assert.equal(new Set(solids.map((p) => p.getAttribute("stroke"))).size, 2);
    // A legend that names each shoe and says how hard it worked, and says "no
    // cone" rather than a fraction of nothing for a mu = 0 shoe.
    const text = dom.text(plot);
    assert.match(text, /S1 —/);
    assert.match(text, /S2 —/);
    assert.match(text, /100% of cone/);
    assert.doesNotMatch(text, /0 of cone used/);
    // The increment on screen is marked on every shoe's line.
    assert.equal(findAll(plot, (node) => node.tagName === "CIRCLE" && node.getAttribute("r") === "4.5").length, 2);
  } finally {
    dom.restore();
  }
});

test("a single-shoe run is left to the inspector's richer per-shoe chart", () => {
  const dom = shim();
  try {
    const state = fixture();
    state.contactFindings.runs[0].shoes = state.contactFindings.runs[0].shoes.slice(0, 1);
    const panel = renderContactReview(state, noop, noop, "table");
    assert.equal(find(panel, (node) => node.tagName === "SVG"), null);
  } finally {
    dom.restore();
  }
});

test("a scene with no findings block still renders the numbers", () => {
  const dom = shim();
  try {
    const state = fixture();
    state.contactFindings = null;
    const panel = renderContactReview(state, noop, noop, "table");
    assert.equal(findAll(panel, (node) => node.classList?.contains("contact-finding")).length, 0);
    // The stage strip needs the published summaries, so it degrades to the
    // single-instant table rather than to empty cells.
    assert.equal(find(panel, (node) => node.classList?.contains("contact-strip")), null);
    assert.ok(find(panel, (node) => node.tagName === "TABLE"));
  } finally {
    dom.restore();
  }
});
