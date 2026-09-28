import assert from "node:assert/strict";
import test from "node:test";
import { runBrowserModel } from "../src/browserPreview.js";

test("preview reuses successful workers and discards cancelled, failed and timed-out runs", async t => {
  const workers = [];
  let timeout;
  class Worker {
    constructor() { workers.push(this); }
    postMessage(data) { this.code = data.code; }
    terminate() { this.terminated = true; }
    reply(data) { this.onmessage({ data }); }
  }
  const originals = { Worker: globalThis.Worker, document: globalThis.document };
  Object.assign(globalThis, { Worker, document: { baseURI: "https://example.test/viewer/" } });
  t.after(() => {
    for (const [key, value] of Object.entries(originals)) {
      if (value === undefined) delete globalThis[key];
      else globalThis[key] = value;
    }
  });
  t.mock.method(globalThis, "setTimeout", callback => { timeout = callback; return 1; });
  t.mock.method(globalThis, "clearTimeout", () => {});
  const progress = [];
  const first = runBrowserModel("first", status => progress.push(status));
  workers[0].reply({ status: "Building geometry…" });
  workers[0].reply({ ok: true, scene: { id: 1 } });
  assert.deepEqual(await first.promise, { id: 1 });
  assert.deepEqual(progress, ["Building geometry…"]);
  const second = runBrowserModel("second", () => {});
  first.cancel(); // A stale handle must not cancel the next run.
  assert.equal(workers.length, 1);
  assert.equal(workers[0].terminated, undefined);
  workers[0].reply({ ok: true, scene: { id: 2 } });
  assert.deepEqual(await second.promise, { id: 2 });

  const stopped = runBrowserModel("loop", () => {});
  const stoppedCheck = assert.rejects(stopped.promise, { name: "AbortError" });
  const replacement = runBrowserModel("replacement", () => {});
  await stoppedCheck;
  assert.equal(workers[0].terminated, true);
  assert.equal(workers.length, 2);
  workers[1].reply({ ok: false, error: "SyntaxError", line: 3 });
  await assert.rejects(replacement.promise, { message: "SyntaxError", line: 3 });
  assert.equal(workers[1].terminated, true);

  const timedOut = runBrowserModel("loop", () => {});
  timeout();
  await assert.rejects(timedOut.promise, /timed out/);
  assert.equal(workers[2].terminated, true);
  globalThis.Worker = class { constructor() { throw new Error("blocked"); } };
  await assert.rejects(runBrowserModel("blocked", () => {}).promise, /blocked/);
  globalThis.Worker = Worker;
  const recovered = runBrowserModel("recovered", () => {});
  assert.equal(workers.length, 4);
  recovered.cancel();
  await assert.rejects(recovered.promise, { name: "AbortError" });
});
