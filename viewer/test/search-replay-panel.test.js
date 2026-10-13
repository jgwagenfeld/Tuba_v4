import assert from "node:assert/strict";
import test from "node:test";
import { initSearchReplay } from "../src/searchReplayPanel.js";

function dom() {
  const original = globalThis.document;
  const make = (tag) => ({
    tagName: tag.toUpperCase(), children: [], dataset: {}, attributes: {}, listeners: {}, textContent: "",
    append(...nodes) { this.children.push(...nodes); },
    prepend(...nodes) { this.children.unshift(...nodes); },
    replaceChildren(...nodes) { this.children = nodes; },
    setAttribute(name, value) { this.attributes[name] = String(value); },
    getAttribute(name) { return this.attributes[name] ?? null; },
    addEventListener(name, handler) { this.listeners[name] = handler; },
    contains(target) { return this === target || this.children.some(node => node.contains?.(target)); },
    querySelector(selector) { return find(this, node => selector === "[data-search-view-status]" && "searchViewStatus" in node.dataset); }
  });
  globalThis.document = { createElement: make, activeElement: null };
  return { container: make("div"), restore: () => { globalThis.document = original; } };
}

function find(node, predicate) {
  if (predicate(node)) return node;
  for (const child of node.children) {
    const found = find(child, predicate);
    if (found) return found;
  }
  return null;
}

function manifest() {
  const event = (sequence, kind, candidate_id, payload = {}) => ({ sequence, kind, candidate_id, payload });
  return {
    run: { settings: { operations: ["Hot"] }, check_specs: [] },
    candidates: ["C1", "C2"].map(id => ({
      id, outcome: id === "C1" ? "selected" : "awaiting_evaluation", parent_ids: [], parameters: { width: id === "C1" ? 1 : 2 },
      preview: { availability: "available", bundle: `previews/${id}` },
      attempt_reviews: [{ availability: "available", evaluation_id: "E1", bundle: `reviews/${id}/E1` }]
    })),
    events: [event(1, "candidate.proposed", "C1"), event(2, "candidate.built", "C1"),
      event(3, "evaluation.completed", "C1", { id: "E1", attempt_id: "A1", checks: [{ constraint_id: "stress", operation: "Hot", verdict: "fail" }], completed_operations: ["Hot"] }),
      event(4, "candidate.proposed", "C2"), event(5, "candidate.built", "C2")]
  };
}

const settled = () => new Promise(resolve => setImmediate(resolve));
function compare(container) {
  const control = find(container, node => "searchCompare" in node.dataset);
  control.value = "C2";
  control.listeners.change();
}

test("parameter comparison keeps the selected reference geometry and its result warning", async () => {
  const ui = dom();
  try {
    const shown = [];
    initSearchReplay(ui.container, { manifest: manifest(), baseUrl: "http://localhost/run/search_replay.json", showView: async url => shown.push(url), highlight() {} });
    await settled();
    find(ui.container, node => "searchReference" in node.dataset).listeners.click();
    await settled();
    assert.match(shown.at(-1), /previews\/C1$/);
    const before = shown.length;
    compare(ui.container);
    await settled();
    assert.equal(shown.length, before, "comparing parameters must not switch the viewport to solver results");
    assert.equal(ui.container.querySelector("[data-search-view-status]").textContent, "Reference geometry — no solver result");
    assert.ok(find(ui.container, node => node.tagName === "TR" && node.className === "search-changed"));
  } finally { ui.restore(); }
});

test("parameter comparison keeps the recorded finding highlighted", async () => {
  const ui = dom();
  try {
    const shown = [], highlights = [];
    initSearchReplay(ui.container, { manifest: manifest(), baseUrl: "http://localhost/run/search_replay.json", showView: async url => shown.push(url), highlight: check => highlights.push(check.constraint_id) });
    await settled();
    find(ui.container, node => node.dataset.searchFinding === "stress").listeners.click();
    await settled();
    const before = shown.length;
    compare(ui.container);
    await settled();
    assert.equal(shown.length, before);
    assert.deepEqual(highlights, ["stress"]);
    assert.equal(ui.container.querySelector("[data-search-view-status]").textContent, "Showing the recorded finding");
  } finally { ui.restore(); }
});

test("a pending reference load completes in the current comparison panel", async () => {
  const ui = dom();
  try {
    const shown = [];
    let finish;
    initSearchReplay(ui.container, { manifest: manifest(), baseUrl: "http://localhost/run/search_replay.json", showView: async url => {
      shown.push(url);
      if (url?.includes("previews/")) await new Promise(resolve => { finish = resolve; });
    }, highlight() {} });
    await settled();
    find(ui.container, node => "searchReference" in node.dataset).listeners.click();
    compare(ui.container);
    assert.equal(ui.container.querySelector("[data-search-view-status]").textContent, "Loading recorded view…");
    finish();
    await settled();
    assert.equal(shown.length, 2, "comparison does not invalidate or replace the pending view request");
    assert.equal(ui.container.querySelector("[data-search-view-status]").textContent, "Reference geometry — no solver result");
  } finally { ui.restore(); }
});

test("an older failed view cannot replace the newer candidate's status", async () => {
  const ui = dom();
  try {
    let finishCleanup;
    const replay = initSearchReplay(ui.container, { manifest: manifest(), baseUrl: "http://localhost/run/search_replay.json", showView: async url => {
      if (url?.includes("reviews/C1")) throw new Error("missing recorded view");
      if (url === null) await new Promise(resolve => { finishCleanup = resolve; });
    }, highlight() {} });
    await settled();
    assert.ok(finishCleanup);
    await replay.seek(5, "C2", null, null, true);
    finishCleanup();
    await settled();
    assert.equal(ui.container.querySelector("[data-search-view-status]").textContent, "Reference geometry — no solver result");
  } finally { ui.restore(); }
});
