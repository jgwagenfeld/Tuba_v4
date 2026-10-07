import test from "node:test";
import assert from "node:assert/strict";
import { authenticatedFetch, initializeLocalAuth, previewProtocols } from "../src/localAuth.js";
import { boundedBytes } from "../src/reportView.js";

test("capability headers stay on the exact origin and cannot follow redirects", async () => {
  const calls = [];
  const fetcher = (url, options) => { calls.push({ url, options }); return Promise.resolve({ ok: true }); };
  const fetch = authenticatedFetch(fetcher, "http://localhost:8765", "a".repeat(43));
  await fetch("/api/script", { headers: { "Content-Type": "application/json" } });
  assert.equal(calls[0].options.headers.get("authorization"), "Bearer " + "a".repeat(43));
  assert.equal(calls[0].options.headers.get("content-type"), "application/json");
  assert.equal(calls[0].options.redirect, "error");
  await fetch("http://localhost:8766/api/script");
  await fetch("https://example.com/runtime.js");
  assert.equal(calls[1].options.headers, undefined);
  assert.equal(calls[2].options.headers, undefined);
});

test("fragment handoff is removed and persisted only in origin-scoped session storage", () => {
  const values = new Map();
  let replaced;
  const token = "b".repeat(43);
  const browser = {
    location: { hash: "#tuba_token=" + token, pathname: "/", search: "?bundle=build", origin: "http://localhost:8765" },
    history: { replaceState: (_, __, url) => { replaced = url; } },
    sessionStorage: { setItem: (key, value) => values.set(key, value), getItem: key => values.get(key) },
    fetch: () => Promise.resolve({ ok: true })
  };
  initializeLocalAuth(browser);
  assert.equal(replaced, "/?bundle=build");
  assert.equal(values.get("tuba:access"), token);
  assert.deepEqual(previewProtocols("ws://localhost:8765/preview/ws"), ["tuba-preview", "tuba-auth." + token]);
  assert.deepEqual(previewProtocols("ws://localhost:8766/preview/ws"), []);
});

test("report download limits apply to advertised and streamed bytes before rendering", async () => {
  assert.deepEqual(await boundedBytes(new Response("abc"), 3), new Uint8Array([97, 98, 99]));
  await assert.rejects(boundedBytes(new Response("abc", { headers: { "content-length": "99" } }), 3), /size limit/);
  await assert.rejects(boundedBytes(new Response("abcd"), 3), /size limit/);
  await assert.rejects(boundedBytes(new Response("denied", { status: 403 }), 10), /refused/);
});
