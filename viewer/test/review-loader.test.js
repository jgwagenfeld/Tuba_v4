import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { loadOptionalReview, normalizeReview } from "../src/reviewLoader.js";

const reviewFixture = JSON.parse(
  await readFile(new URL("./fixtures/code_aster_results/review.json", import.meta.url), "utf8")
);

test("loads review.json beside the scene bundle", async () => {
  let requestedUrl = null;
  const fetcher = async (url) => {
    requestedUrl = url;
    return new Response(JSON.stringify(reviewFixture), { status: 200 });
  };

  const result = await loadOptionalReview("/bundle", fetcher);

  assert.equal(requestedUrl, "/bundle/review.json");
  assert.equal(result.review.schema_version, "engineering_review.v1");
  assert.equal(result.legacy, false);
  assert.deepEqual(result.diagnostics, []);
});

test("normalizes trailing slashes in the review URL", async () => {
  let requestedUrl = null;

  await loadOptionalReview("/bundle///", async (url) => {
    requestedUrl = url;
    return new Response(JSON.stringify(reviewFixture), { status: 200 });
  });

  assert.equal(requestedUrl, "/bundle/review.json");
});

test("treats review.json 404 as a supported legacy bundle", async () => {
  const result = await loadOptionalReview(
    "/legacy",
    async () => new Response("", { status: 404 })
  );

  assert.deepEqual(result, { review: null, diagnostics: [], legacy: true });
});

test("reports network and non-404 failures without review tables", async (t) => {
  await t.test("network failure", async () => {
    const result = await loadOptionalReview("/bundle", async () => {
      throw new TypeError("network unavailable");
    });

    assert.equal(result.review, null);
    assert.equal(result.legacy, false);
    assert.equal(result.diagnostics[0].code, "viewer.review.load_failed");
    assert.equal(result.diagnostics[0].source, "review.json");
  });

  await t.test("HTTP failure", async () => {
    const result = await loadOptionalReview(
      "/bundle",
      async () => new Response("server error", { status: 503, statusText: "Unavailable" })
    );

    assert.equal(result.review, null);
    assert.equal(result.legacy, false);
    assert.equal(result.diagnostics[0].code, "viewer.review.load_failed");
    assert.match(result.diagnostics[0].message, /HTTP 503/);
  });
});

test("reports invalid review JSON without fabricating tables", async () => {
  const result = await loadOptionalReview(
    "/bundle",
    async () => new Response("{", { status: 200 })
  );

  assert.equal(result.review, null);
  assert.equal(result.legacy, false);
  assert.equal(result.diagnostics[0].code, "viewer.review.load_failed");
});

test("reports malformed review contracts without fabricating tables", async () => {
  const result = await loadOptionalReview(
    "/bundle",
    async () => new Response("{}", { status: 200 })
  );

  assert.equal(result.review, null);
  assert.equal(result.legacy, false);
  assert.equal(result.diagnostics[0].code, "viewer.review.invalid_contract");

  for (const malformed of [
    { ...reviewFixture, schema_version: "engineering_review.v2" },
    { ...reviewFixture, analysis_status: "" },
    { ...reviewFixture, tables: [] }
  ]) {
    assert.throws(() => normalizeReview(malformed), /engineering review/i);
  }
});

test("normalizes stable review table order and lookup while preserving row values as data", () => {
  const normalized = normalizeReview(reviewFixture);

  assert.deepEqual(normalized.tableOrder, [
    "project_summary",
    "line_list",
    "load_cases",
    "studies",
    "result_summary",
    "fe_stress"
  ]);
  assert.deepEqual(Object.keys(normalized.tables), normalized.tableOrder);
  assert.equal(normalized.tables.result_summary.id, "result_summary");
  assert.equal(
    normalized.tables.result_summary.rows[0].display_note,
    "<strong>plain data</strong>"
  );
  assert.deepEqual(normalized.tables.result_summary.rows[0].components, {
    dx: 0.001,
    dy: 0.002
  });
});
