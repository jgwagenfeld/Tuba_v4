import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import { runInNewContext } from "node:vm";
import { createStudioBundleCache } from "../src/studioBundleCache.js";

test("stage navigation reuses the two loaded scenes and their normalized state", async () => {
  const cache = createStudioBundleCache();
  let loads = 0;
  const load = async () => ({ bundle: { revision: ++loads }, state: {} });
  const review = await cache.load("review", load);
  const build = await cache.load("build", load);
  const selected = { selectedObjectIds: ["pipe:1"] };
  cache.remember("review", review.bundle, selected);
  assert.deepEqual(await cache.load("review", load, { reuse: true }), { ...review, state: selected });
  assert.equal(await cache.load("build", load, { reuse: true }), build);
  assert.equal(loads, 2);
});

test("explicit reloads and invalidation replace scenes instead of serving old results", async () => {
  const cache = createStudioBundleCache();
  let revision = 0;
  const load = async () => ({ bundle: { revision: ++revision }, state: {} });
  const old = await cache.load("review", load);
  assert.notEqual(await cache.load("review", load), old, "reload is fresh by default");
  cache.invalidate("review");
  cache.remember("review", old.bundle, { stale: true });
  const latest = await cache.load("review", load, { reuse: true });
  assert.equal(latest.bundle.revision, 3);
  assert.equal(latest.state.stale, undefined);
  cache.clear();
  assert.notEqual(await cache.load("review", load, { reuse: true }), latest);
});

test("an invalidated or superseded in-flight load cannot seed the next stage visit", async () => {
  const cache = createStudioBundleCache();
  let finish;
  const pending = cache.load("build", () => new Promise(resolve => { finish = resolve; }));
  cache.invalidate("build");
  const fresh = { bundle: { revision: "new" }, state: {} };
  await cache.load("build", async () => fresh);
  finish({ bundle: { revision: "old" }, state: {} });
  await pending;
  assert.equal(await cache.load("build", () => assert.fail("unnecessary reload"), { reuse: true }), fresh);
});

test("failed loads are retried and arbitrary gallery/search bundles are never retained", async () => {
  const cache = createStudioBundleCache();
  await assert.rejects(cache.load("build", async () => { throw new Error("offline"); }), /offline/);
  const fresh = { bundle: {}, state: {} };
  assert.equal(await cache.load("build", async () => fresh, { reuse: true }), fresh);
  let calls = 0;
  const load = async () => { calls++; return fresh; };
  await cache.load("gallery-review", load, { reuse: true });
  await cache.load("gallery-review", load, { reuse: true });
  assert.equal(calls, 2);
});

test("socket startup discards pre-connection scenes, and errors and close disable reuse", async () => {
  const app = await readFile(new URL("../src/app.js", import.meta.url), "utf8");
  const source = app.slice(app.indexOf("function connectLivePreview("), app.indexOf("async function handleLivePreviewEvent("));
  const studioBundles = createStudioBundleCache();
  let revision = 0;
  const load = async () => ({ bundle: { revision: ++revision }, state: {} });
  const beforeConnection = await studioBundles.load("review", load);
  const handlers = new Map();
  const runtime = {
    studio: { connected: false }, studioBundles, currentState: {}, setStatus() {},
    previewProtocols: () => [], handleLivePreviewEvent() {},
    WebSocket: class { addEventListener(type, callback) { handlers.set(type, callback); } }
  };
  runInNewContext(source, runtime);
  runtime.connectLivePreview("ws://127.0.0.1/preview/ws");
  handlers.get("open")();
  assert.equal(runtime.studio.connected, true);
  const connected = await studioBundles.load("review", load, { reuse: true });
  assert.notEqual(connected, beforeConnection, "updates during startup had no live notification listener");
  for (const event of ["error", "close"]) {
    runtime.studio.connected = true;
    handlers.get(event)();
    assert.equal(runtime.studio.connected, false);
    assert.notEqual(await studioBundles.load("review", load, { reuse: true }), connected);
  }
});
