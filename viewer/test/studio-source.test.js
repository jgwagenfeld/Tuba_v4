import assert from "node:assert/strict";
import test from "node:test";
import { editorSource, saveStudioSource } from "../src/studioSource.js";

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
