import assert from "node:assert/strict";
import test from "node:test";

import {
  bundleIdsOf,
  normalizeCatalog,
  shouldShowGallery,
  titleFromId
} from "../src/gallery.js";

const PUBLISHED = [
  {
    id: "support-rack-review",
    title: "Pipe on a support rack",
    question: "What do the supports and the steel underneath actually carry?",
    summary: "A line resting on a framed rack.",
    evidence: "Results",
    thumbnail: "gallery/support-rack-review.png"
  },
  {
    id: "gmsh-tee-mesh-review",
    title: "Tee junction mesh",
    question: "What does the analysis actually discretise at a branch?",
    summary: "The conformal tetrahedral wall mesh.",
    evidence: "Mesh only - no results",
    thumbnail: "gallery/gmsh-tee-mesh-review.png"
  }
];

test("gallery accepts the published catalog untouched", () => {
  const entries = normalizeCatalog(PUBLISHED);

  assert.deepEqual(entries.map((entry) => entry.id), [
    "support-rack-review",
    "gmsh-tee-mesh-review"
  ]);
  assert.equal(entries[0].question, PUBLISHED[0].question);
  assert.equal(entries[1].evidence, "Mesh only - no results");
});

test("gallery accepts the bare id list the dev server discovers", () => {
  // vite.config.js serves ids only; a recipe bundle has no registry entry.
  const entries = normalizeCatalog(["my-recipe", "smoke-scene"]);

  assert.deepEqual(entries, [
    { id: "my-recipe", title: "My Recipe" },
    { id: "smoke-scene", title: "Smoke Scene" }
  ]);
});

test("gallery accepts the empty catalog emitted into the packaged shell", () => {
  assert.deepEqual(normalizeCatalog([]), []);
  assert.deepEqual(normalizeCatalog(null), []);
  assert.deepEqual(bundleIdsOf(undefined), []);
});

test("gallery keeps a registry title and never invents one", () => {
  assert.equal(titleFromId("elements-supports-review"), "Elements Supports Review");
  assert.equal(normalizeCatalog([{ id: "a-b", title: "Real Title" }])[0].title, "Real Title");
  assert.equal(normalizeCatalog([{ id: "a-b" }])[0].title, "A B");
});

test("gallery shows only when there is a real choice and none was made", () => {
  assert.equal(shouldShowGallery({ requestedBundle: null, embed: false, catalog: PUBLISHED }), true);
});

test("gallery yields to an explicitly requested review", () => {
  assert.equal(
    shouldShowGallery({ requestedBundle: "support-rack-review", embed: false, catalog: PUBLISHED }),
    false
  );
});

test("gallery yields to an embedded viewer so documentation embeds keep working", () => {
  assert.equal(shouldShowGallery({ requestedBundle: null, embed: true, catalog: PUBLISHED }), false);
});

test("gallery yields to a shared single-bundle folder", () => {
  // A standalone bundle needs no catalog and must open straight into its review.
  assert.equal(
    shouldShowGallery({ requestedBundle: null, embed: false, catalog: [PUBLISHED[0]] }),
    false
  );
  assert.equal(shouldShowGallery({ requestedBundle: null, embed: false, catalog: [] }), false);
});
