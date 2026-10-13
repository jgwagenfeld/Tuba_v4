import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { runInNewContext } from "node:vm";

const app = await readFile(new URL("../src/app.js", import.meta.url), "utf8");
const transitions = app.slice(app.indexOf("async function setMode(stage)"), app.indexOf("function setScriptText(code)"));

function deferred() {
  let resolve, reject;
  const promise = new Promise((accept, fail) => { resolve = accept; reject = fail; });
  return { promise, resolve, reject };
}

function harness(load) {
  const buttons = [{ disabled: false }, { disabled: true }];
  const attributes = new Map();
  const status = [], errors = [], loads = [], actions = [], history = [];
  const runtime = {
    studio: { available: true, project: {}, hasReview: true },
    sourceView: { available: false, preview: null },
    currentBundleUrl: "review", reviewOpened: true, userChoseColor: false,
    currentBundle: { id: "review" }, currentState: { stage: "review", scene: "retained review" },
    dom: { modeSwitch: {
      getAttribute: name => attributes.get(name) ?? null,
      setAttribute: (name, value) => attributes.set(name, value),
      querySelectorAll: () => buttons
    } },
    URL,
    window: { location: { href: "http://127.0.0.1:5188/?bundle=review" }, history: {
      replaceState: (_state, _unused, url) => { history.push(url.href); runtime.window.location.href = url.href; }
    } },
    bundleKey: value => value,
    currentStage: () => runtime.currentState.stage,
    setStatus: message => status.push(message),
    setErrorStatus: (error, message) => { errors.push({ error, message }); status.push(message); },
    loadBundle: async (bundle, options) => {
      loads.push({ bundle, options });
      await load(bundle);
      runtime.currentBundle = { id: bundle };
      runtime.currentState = { ...runtime.currentState, scene: bundle };
      return true;
    },
    dispatch: action => { actions.push(action); if (action.type === "setStage") runtime.currentState = { ...runtime.currentState, stage: action.stage }; },
    render: () => status.push("Ready"),
    showBrowserBundle: () => {}
  };
  const functions = runInNewContext(`${transitions}\n({ setMode, showStudioBundle })`, runtime);
  return { ...functions, runtime, buttons, attributes, status, errors, loads, actions, history };
}

test("a deferred stage load gives feedback while preserving the displayed review and URL", async () => {
  const loading = deferred();
  const h = harness(() => loading.promise);
  const previousState = h.runtime.currentState;
  const previousBundle = h.runtime.currentBundle;
  const pending = h.setMode("build");
  assert.equal(h.attributes.get("aria-busy"), "true");
  assert.ok(h.buttons.every(button => button.disabled));
  assert.equal(h.status.at(-1), "Opening Build…");
  assert.equal(h.runtime.currentState, previousState);
  assert.equal(h.runtime.currentBundle, previousBundle);
  assert.equal(h.runtime.currentBundleUrl, "review");
  assert.deepEqual(h.history, []);
  loading.resolve();
  await pending;
  assert.equal(h.runtime.currentState.stage, "build");
  assert.equal(h.runtime.currentBundleUrl, "build");
  assert.equal(new URL(h.runtime.window.location.href).searchParams.get("bundle"), "build");
  assert.equal(h.actions.filter(action => action.type === "setStage").length, 1);
  assert.equal(h.attributes.get("aria-busy"), "false");
  assert.deepEqual(h.buttons.map(button => button.disabled), [false, true]);
});

test("a failed stage load reports the actual error, preserves stage and URL, and remains retryable", async () => {
  const failure = new Error("The build scene is unavailable");
  let fail = true;
  const h = harness(async () => { if (fail) throw failure; });
  const previousState = h.runtime.currentState;
  const previousBundle = h.runtime.currentBundle;
  await h.setMode("build");
  assert.equal(h.runtime.currentState, previousState);
  assert.equal(h.runtime.currentBundle, previousBundle);
  assert.equal(h.runtime.currentBundleUrl, "review");
  assert.deepEqual(h.history, []);
  assert.deepEqual(h.actions, []);
  assert.equal(h.errors.length, 1);
  assert.equal(h.errors[0].error, failure);
  assert.equal(h.attributes.get("aria-busy"), "false");
  assert.deepEqual(h.buttons.map(button => button.disabled), [false, true]);
  fail = false;
  await h.setMode("build");
  assert.equal(h.loads.length, 2, "retry must fetch the failed target instead of treating its URL as already loaded");
  assert.equal(h.runtime.currentState.stage, "build");
});

test("repeated stage requests cannot start overlapping loads", async () => {
  const loading = deferred();
  const h = harness(() => loading.promise);
  const first = h.setMode("build");
  const repeated = h.setMode("build");
  const reverse = h.setMode("review");
  assert.equal(h.loads.length, 1);
  assert.equal(h.actions.length, 0);
  loading.resolve();
  await Promise.all([first, repeated, reverse]);
  assert.equal(h.runtime.currentState.stage, "build");
  assert.equal(h.actions.filter(action => action.type === "setStage").length, 1);
});

test("the shared Studio loader returns success or failure and reuses an already loaded bundle", async () => {
  const h = harness(async () => {});
  assert.equal(await h.showStudioBundle("review"), true);
  assert.equal(h.loads.length, 0);
  assert.equal(await h.showStudioBundle("build"), true);
  assert.equal(h.loads.length, 1);
  assert.equal(h.runtime.currentState.stage, "review", "only the stage transition commits the stage");
  const failed = harness(async () => { throw new Error("Missing scene"); });
  assert.equal(await failed.showStudioBundle("build"), false);
  assert.equal(failed.runtime.currentBundleUrl, "review");
});
