import assert from "node:assert/strict";
import test from "node:test";

import { clampCutHandle, cutHandleStep, cutViewRanges, stepCutHandle, typedCutHandle } from "../src/cutView.js";

// Just enough DOM for the Display palette controls: elements, children, attributes and
// listeners. The handlers run for real; only the browser is missing.
class FakeElement {
  constructor(tag, document) {
    this.tagName = tag.toUpperCase();
    this.ownerDocument = document;
    this.children = [];
    this.dataset = {};
    this.attributes = {};
    this.listeners = {};
    this.parentNode = null;
    this.textContent = "";
    this.style = { setProperty(name, value) { this[name] = value; } };
  }
  append(...nodes) {
    for (const node of nodes) {
      if (typeof node === "object") {
        node.parentNode?.removeChild(node);
        node.parentNode = this;
      }
      this.children.push(node);
    }
  }
  // Like a browser, taking the focused element out fires its blur while it is
  // still attached, and removing a node that is no longer a child throws.
  blurIfFocused(node) {
    if (typeof node === "object" && this.ownerDocument.activeElement === node) {
      this.ownerDocument.activeElement = null;
      node.fire("blur");
    }
  }
  replaceChildren(...nodes) {
    for (const child of [...this.children]) this.blurIfFocused(child);
    for (const child of this.children) if (typeof child === "object") child.parentNode = null;
    this.children = [];
    this.append(...nodes);
  }
  removeChild(node) {
    this.blurIfFocused(node);
    if (!this.children.includes(node)) throw new Error("NotFoundError: the node to be removed is no longer a child of this node");
    this.children = this.children.filter((child) => child !== node);
    node.parentNode = null;
  }
  remove() { this.parentNode?.removeChild(this); }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  removeAttribute(name) { delete this.attributes[name]; }
  getAttribute(name) { return this.attributes[name] ?? null; }
  addEventListener(type, listener) { (this.listeners[type] ??= []).push(listener); }
  fire(type, init = {}) {
    const event = { defaultPrevented: false, preventDefault() { this.defaultPrevented = true; }, stopPropagation() {}, ...init };
    for (const listener of this.listeners[type] ?? []) listener(event);
    return event;
  }
  focus() { this.ownerDocument.activeElement = this; }
  select() {}
  get text() {
    return this.children.length ? this.children.map((child) => (typeof child === "string" ? child : child.text)).join("") : this.textContent;
  }
  *walk() {
    yield this;
    for (const child of this.children) if (typeof child === "object") yield* child.walk();
  }
}

function withDocument(run) {
  const document = { activeElement: null, createElement(tag) { return new FakeElement(tag, document); } };
  const previous = globalThis.document;
  globalThis.document = document;
  try {
    return run(document);
  } finally {
    globalThis.document = previous;
  }
}

// A 100 m model and the box "Around selection" fits to a support at X = 0.
function ranges(sectionBox, unitSystem = "si") {
  const commits = [];
  const previews = [];
  const grid = cutViewRanges(
    { bounds: [-50, -1, -1, 50, 1, 1], unitSystem, sectionBox },
    { onPreview: (box) => previews.push(structuredClone(box)), onCommit: (box) => commits.push(box) }
  );
  const all = [...grid.walk()];
  const slider = (label) => all.find((node) => node.type === "range" && node.getAttribute("aria-label") === label);
  const value = (key) => [...grid.walk()].find((node) => node.dataset.focusKey === key);
  return { grid, commits, previews, slider, value, all };
}

const SMALL_BOX = { mode: "selection", min: [-0.05, -0.05, -0.05], max: [0.05, 0.05, 0.05] };

test("an arrow key on a small cut moves its handle inward, never outward", () => {
  withDocument(() => {
    const { slider, commits } = ranges(SMALL_BOX);
    const right = slider("X min").fire("keydown", { key: "ArrowRight" });
    assert.equal(right.defaultPrevented, true, "the key is stepped here, not by the slider's grid");
    const tightened = commits.at(-1).min[0];
    // It used to commit -0.45: snapped to a 0.5 m grid, then held a step short.
    assert.ok(tightened > -0.05, `min ${tightened} must move right`);
    assert.ok(tightened <= 0.05);

    slider("X max").fire("keydown", { key: "ArrowLeft" });
    const lowered = commits.at(-1).max[0];
    assert.ok(lowered < 0.05 && lowered >= commits.at(-1).min[0], `max ${lowered} must move left, not past min`);
  });
});

test("handles stop on each other however many steps are pressed", () => {
  withDocument(() => {
    const { slider, commits } = ranges(SMALL_BOX);
    for (let press = 0; press < 200; press += 1) slider("X min").fire("keydown", { key: "PageUp" });
    const box = commits.at(-1);
    assert.ok(box.min[0] <= box.max[0], "never crossed");
    // Every committed min moved right or stayed: no step went the wrong way.
    const mins = commits.map((committed) => committed.min[0]);
    assert.ok(mins.every((value, index) => index === 0 || value >= mins[index - 1]));
  });
});

test("a drag past the other handle stops on it", () => {
  withDocument(() => {
    const { slider, previews } = ranges(SMALL_BOX);
    const min = slider("X min");
    min.value = "30";
    min.fire("input");
    assert.equal(previews.at(-1).min[0], 0.05);
    assert.equal(Number(min.value), 0.05);
  });
});

test("the step is fine enough to adjust the box it is on", () => {
  assert.equal(cutHandleStep(100, 100), 0.5, "a whole-model box keeps 1/200 of the axis");
  assert.ok(cutHandleStep(100, 0.1) <= 0.01, "a 10 cm box steps in a tenth of itself");
  assert.equal(cutHandleStep(100, 0), 0.5, "touching handles can still move apart");
  // The pure step never runs against the key, even from outside the range.
  const box = { min: [-0.05], max: [0.05] };
  assert.equal(stepCutHandle(box, 0, "min", 1, { lo: -50, hi: 50, step: 0.5 }), 0.05);
  assert.equal(stepCutHandle(box, 0, "max", -1, { lo: -50, hi: 50, step: 0.5 }), -0.05);
  assert.equal(clampCutHandle(box, 0, "max", -10, -50, 50), -0.05);
});

test("each readout end is a field: Enter commits in display units, clamped; Escape cancels", () => {
  withDocument((document) => {
    const { value, commits, all } = ranges(SMALL_BOX, "engineering");
    // An en dash between the ends, not an ellipsis that reads as "_".
    const readout = all.find((node) => node.className === "cut-axis-readout");
    assert.equal(readout.text, "-50 – 50 mm");

    const minValue = value("cut-view:X:min:value");
    minValue.fire("click");
    const field = value("cut-view:X:min:value:edit");
    assert.ok(field, "clicking the value opens a field");
    assert.equal(field.value, "-50");
    assert.equal(document.activeElement, field);

    field.value = "-20";
    field.fire("keydown", { key: "Enter" });
    assert.deepEqual(commits.at(-1).min, [-0.02, -0.05, -0.05], "20 mm, stored in metres");
    assert.equal(document.activeElement, minValue, "focus returns to the readout");

    minValue.fire("click");
    field.value = "900";
    field.fire("keydown", { key: "Enter" });
    assert.equal(commits.at(-1).min[0], 0.05, "clamped against the max handle");

    const count = commits.length;
    minValue.fire("click");
    field.value = "not a number";
    field.fire("keydown", { key: "Enter" });
    assert.equal(commits.length, count, "refused, not committed");
    assert.equal(field.getAttribute("aria-invalid"), "true");
    field.value = "-1";
    const escape = field.fire("keydown", { key: "Escape" });
    assert.equal(escape.defaultPrevented, true);
    assert.equal(commits.length, count, "Escape cancels");
    assert.equal(field.parentNode, null, "and closes the field");
  });
});

test("a typed value is read in the active unit system", () => {
  const box = { min: [0, 0, 0], max: [10, 10, 10] };
  assert.equal(typedCutHandle(box, 2, "max", "5.5", "si"), 5.5);
  assert.equal(typedCutHandle(box, 2, "max", "5500", "engineering"), 5.5);
  assert.equal(typedCutHandle(box, 2, "max", "5,5", "si"), 5.5, "a decimal comma is a decimal point");
  assert.equal(typedCutHandle(box, 2, "max", "", "si"), null);
});

// The Display rows' descriptions lived only in `title`, which a screen reader
// does not reliably announce. Each checkbox now points at a hidden description
// as well as at its status line.
test("each Display row's checkbox is described by its description and its status", async () => {
  const { readFile } = await import("node:fs/promises");
  const app = await readFile(new URL("../src/app.js", import.meta.url), "utf8");
  const slice = (from, to) => app.slice(app.indexOf(from), app.indexOf(to));
  const source = [
    slice("function bodyRow(", "// A cycle chip names its control"),
    slice("function overlayRow(", "// The scale a vector family")
  ].join("\n");
  withDocument((document) => {
    const { bodyRow, overlayRow } = new Function(
      "document", "dispatch", "render", "expandedBodies", "opacityChip", "subpointModeChip", "subpointThresholdChip", "scaleChip",
      `${source}; return { bodyRow, overlayRow };`
    )(document, () => {}, () => {}, new Set(), () => null, () => null, () => null, () => null);
    const describedBy = (row) => {
      const nodes = [...row.walk()];
      const input = nodes.find((node) => node.type === "checkbox");
      return input.getAttribute("aria-describedby").split(" ").map((id) => nodes.find((node) => node.id === id)?.text);
    };

    const body = bodyRow({ id: "deformed", label: "Deformed mesh", description: "A transform of the mesh.", visible: true,
      partiallyVisible: false, supportsOpacity: false, status: "×50 · display only", metrics: [] });
    assert.deepEqual(describedBy(body), ["A transform of the mesh.", "×50 · display only"]);
    const quiet = bodyRow({ id: "geometry", label: "Geometry", description: "What the engineer authored.", visible: true,
      partiallyVisible: false, supportsOpacity: false, status: null, metrics: [] });
    assert.deepEqual(describedBy(quiet), ["What the engineer authored."]);
    const overlay = overlayRow({ id: "imposed_displacement", label: "Imposed displacements", description: "Supports that move their node.", visible: true,
      partiallyVisible: false, count: 1, vectorType: null });
    assert.deepEqual(describedBy(overlay), ["Supports that move their node."]);
    const hidden = [...overlay.walk()].find((node) => node.id === "overlay-description-imposed_displacement");
    assert.equal(hidden.className, "visually-hidden");
  });
});

// Show values sat three clicks deep. V reaches it from anywhere, through the
// checkbox itself, so the box, the saved view and the badges cannot disagree.
test("V toggles Show values through its checkbox, but not while typing or with Ctrl", async () => {
  const { readFile } = await import("node:fs/promises");
  const app = await readFile(new URL("../src/app.js", import.meta.url), "utf8");
  const slice = (from, to) => app.slice(app.indexOf(from), app.indexOf(to));
  const source = [
    slice('dom.valueLabelsToggle.addEventListener("change"', "dom.bodyLegendToggle.addEventListener"),
    slice("const SHORTCUTS = [", "// [ and ] walk the issue list")
  ].join("\n");
  withDocument((document) => {
    const window = new FakeElement("window", document);
    let dialogOpen = false;
    document.querySelector = (selector) => selector === "dialog[open]" && dialogOpen ? {} : null;
    const toggle = new FakeElement("input", document);
    toggle.checked = true;
    // As in a browser: a click flips the box and fires change.
    toggle.click = () => { toggle.checked = !toggle.checked; toggle.fire("change"); };
    const dom = { profileLibrary: { open: false }, valueLabelsToggle: toggle, overlaysBlock: { hidden: false } };
    const actions = [];
    new Function("window", "dom", "HTMLElement", "dispatch", "render", source)(
      window, dom, FakeElement, (action) => actions.push(action), () => {});
    const press = (target, init = {}) => window.fire("keydown", { key: "v", target, ...init });
    const canvas = new FakeElement("canvas", document);

    assert.equal(press(canvas).defaultPrevented, true);
    assert.deepEqual(actions, [{ type: "setValueLabelsVisible", visible: false }]);
    press(canvas);
    assert.deepEqual(actions.at(-1), { type: "setValueLabelsVisible", visible: true });
    press(new FakeElement("input", document));
    press(canvas, { ctrlKey: true });
    assert.equal(actions.length, 2, "a v typed into a field, or a paste, is not a toggle");
    assert.equal(toggle.checked, true);
    dialogOpen = true;
    press(canvas);
    assert.equal(actions.length, 2, "a modal dialog keeps viewport shortcuts inactive");
  });
});
