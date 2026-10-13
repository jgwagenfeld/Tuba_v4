import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { runInNewContext } from "node:vm";
import { editorSource, saveStudioSource } from "../src/studioSource.js";

const app = await readFile(new URL("../src/app.js", import.meta.url), "utf8");
const editorFunctions = [
  app.slice(app.indexOf("function scriptLinesMoved()"), app.indexOf("function stopBrowserPreview()")),
  app.slice(app.indexOf("function renderCodeFoot()"), app.indexOf("function renderScriptSelection()"))
].join("\n");
const runScriptFunction = app.slice(app.indexOf("async function runScript()"), app.indexOf("function showSourceConflict()"));

function editorHarness(studio, code, sourceView = { preview: null }) {
  const dom = {
    codeText: { value: code, selectionStart: 0 },
    codeFoot: { children: [], replaceChildren(...children) { this.children = children; } }
  };
  const functions = runInNewContext(`${editorFunctions}\n({ scriptLinesMoved, renderCodeFoot })`, {
    studio, sourceView, dom, editorSource,
    isBuildMode: () => true,
    lineCount: value => value.split("\n").length,
    lineAtOffset: () => 1,
    document: { createElement: () => ({ dataset: {}, textContent: "" }) }
  });
  return { ...functions, dom, footText: () => dom.codeFoot.children.map(child => child.textContent).join(" ") };
}

test("clean Windows source compares with the textarea's normalized line endings", () => {
  assert.equal(editorSource("# Müller\r\nmodel = build()\r\n"), "# Müller\nmodel = build()\n");
  assert.equal(editorSource("# Müller\rmodel = build()\r"), "# Müller\nmodel = build()\n");
});

test("saving sends the source revision, and conflicts keep the draft and its original revision", async () => {
  const state = { sourceRevision: "old", diskCode: "saved", draft: "my changes" };
  const result = await saveStudioSource(state, state.draft, { fetcher: async (url, options) => {
    assert.equal(url, "/api/script");
    assert.deepEqual(JSON.parse(options.body), { code: "my changes", expected_revision: "old" });
    return { status: 409, json: async () => ({ ok: false, conflict: true, source_revision: "external" }) };
  } });
  assert.equal(result.conflict, true);
  assert.deepEqual(state, { sourceRevision: "old", diskCode: "saved", draft: "my changes", saveConflict: true });
});

test("accepted source updates its revision even when Python reports a script error", async () => {
  for (const status of [200, 400]) {
    const state = { sourceRevision: "old", diskCode: "saved", draft: "next" };
    await saveStudioSource(state, state.draft, { fetcher: async () => ({ status,
      json: async () => ({ ok: status === 200, source_revision: "next" }) }) });
    assert.equal(state.sourceRevision, "next");
    assert.equal(state.diskCode, "next");
    assert.equal(state.draft, "next");
    assert.equal(state.saveConflict, false);
  }
});

test("same-length source edits and reorders disable mappings until the executed source is restored", () => {
  const executed = "first.run(2)\nsecond.run(3)\n";
  const harness = editorHarness({ available: true, ranCode: executed }, executed.replaceAll("\n", "\r\n"));
  assert.equal(harness.scriptLinesMoved(), false, "Windows line endings do not invalidate matching source");
  harness.dom.codeText.value = "first.run(9)\nsecond.run(3)\n";
  assert.equal(harness.scriptLinesMoved(), true, "changing a value makes the geometry's source mapping stale");
  harness.dom.codeText.value = "second.run(3)\nfirst.run(2)\n";
  assert.equal(harness.scriptLinesMoved(), true, "reordering statements cannot retain the previous source links");
  harness.dom.codeText.value = executed;
  assert.equal(harness.scriptLinesMoved(), false);
});

test("browser preview mappings follow the preview's executed source rather than the published example", () => {
  const published = "pipe.run(2)\n";
  const preview = { code: "pipe.run(5)\n" };
  const harness = editorHarness({ available: false, ranCode: published }, preview.code, { preview });
  assert.equal(harness.scriptLinesMoved(), false);
  harness.dom.codeText.value = published;
  assert.equal(harness.scriptLinesMoved(), true);
});

test("a saved Python failure is saved on disk while the viewport keeps the last successful geometry", async () => {
  const executed = "pipe.run(2)\n";
  const invalid = "pipe.run(\n";
  const state = { available: true, codeTab: null, ranCode: executed, diskCode: executed,
    sourceRevision: "old", project: { load_cases: ["Hot"] } };
  const harness = editorHarness(state, invalid);
  harness.renderCodeFoot();
  assert.match(harness.footText(), /Edited|Unsaved/);
  await saveStudioSource(state, invalid, { fetcher: async () => ({ status: 400,
    json: async () => ({ ok: false, error: "SyntaxError", source_revision: "saved-invalid" }) }) });
  harness.renderCodeFoot();
  assert.match(harness.footText(), /Saved/);
  assert.match(harness.footText(), /3D shows the last good run/);
  assert.doesNotMatch(harness.footText(), /Unsaved|Edited/);
  assert.equal(harness.scriptLinesMoved(), true);
  harness.dom.codeText.value = executed;
  harness.renderCodeFoot();
  assert.match(harness.footText(), /Unsaved/, "restoring executed geometry source still needs saving over the invalid disk source");
  state.diskCode = executed;
  harness.renderCodeFoot();
  assert.match(harness.footText(), /Saved to model.py/);
  assert.doesNotMatch(harness.footText(), /last good run/);
});

test("geometry updates immediately refresh busy controls and restore them after success or a Python failure", async () => {
  for (const ok of [true, false]) {
    const studio = { available: true, running: false };
    const dom = { codeText: { value: "pipe.run(2)\n" }, codeRun: { disabled: false },
      codeState: {}, codeProblem: { hidden: false } };
    const controls = [];
    let finishSave;
    const saving = new Promise(resolve => { finishSave = resolve; });
    const { runScript } = runInNewContext(`${runScriptFunction}\n({ runScript })`, {
      studio, dom, sourceView: { available: false }, currentBundleUrl: "build", refreshExchange: null,
      saveStudioSource: () => saving,
      renderCodeTabs: () => controls.push(["geometry", studio.running]),
      renderSolveControls: () => controls.push(["solve", studio.running]),
      renderCodeFoot: () => {}, render: () => {}, showScriptError: () => {}, showSourceConflict: () => {},
      refreshStudioProject: async () => {}, loadBundle: async () => {}, sourceIdentity: async () => "source",
      showIdentity: () => {}, setStatus: () => {}
    });
    const pending = runScript();
    assert.equal(studio.running, true);
    assert.equal(dom.codeRun.disabled, true);
    assert.deepEqual(controls, [["geometry", true], ["solve", true]], "all job controls update before waiting for the save");
    finishSave({ ok, elements: 1, error: ok ? undefined : "SyntaxError" });
    await pending;
    assert.equal(studio.running, false);
    assert.equal(dom.codeRun.disabled, false);
    assert.deepEqual(controls.slice(-2), [["geometry", false], ["solve", false]], "busy labels and Solve gating clear in finally");
  }
});
