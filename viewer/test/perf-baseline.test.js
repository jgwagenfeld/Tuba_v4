import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

import { SUBPOINT_MODES } from "../src/bodies.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const HARNESS = resolve(HERE, "..", "scripts", "perf-baseline.mjs");
const source = readFileSync(HARNESS, "utf8");

// The harness exists because `renderer.js` refused to thin anything on a guess:
// it carries a note ending "if orbit ever does judder, measure first and thin
// the thing that is actually slow." These keep the measurement honest about the
// code it measures, so the note can keep deferring to it.

test("the renderer points at the harness that was meant to replace its guess", () => {
  const renderer = readFileSync(resolve(HERE, "..", "src", "renderer.js"), "utf8");
  assert.match(renderer, /npm run perf/);
  assert.match(renderer, /draw calls per object/);
});

test("the harness measures every display mode the viewer actually has", () => {
  // If a mode is added to SUBPOINT_MODES and not to the harness, the baseline
  // silently stops covering it - and the mode nobody measured is the one that
  // turns out to be the expensive one.
  for (const mode of SUBPOINT_MODES) {
    assert.ok(
      source.includes(`"${mode.id}"`),
      `the harness does not measure the "${mode.id}" sub-point display mode`
    );
  }
});

test("the harness declares a ceiling for every cost it reports", () => {
  // A budget entry nothing checks is a number that looks like a limit and is
  // not one.
  for (const key of ["frame_ms", "orbit_ms", "draw_calls", "triangles", "graph_build_ms", "load_ms"]) {
    assert.match(source, new RegExp(`\\b${key}:`), `BUDGET has no ${key}`);
    assert.ok(
      source.includes(`BUDGET.${key}`),
      `BUDGET.${key} is declared but never compared against a measurement`
    );
  }
});

test("the harness loads the bundle through the studio's own loader", () => {
  // A harness that assembles its own scene measures itself, not the product.
  assert.match(source, /loadSceneBundleFromUrl/);
  assert.match(source, /createViewerState/);
  assert.match(source, /createThreeSceneGraph/);
});

test("the harness discards the first frame before timing", () => {
  // Shader compilation lands on the first render of a scene. Left in the sample
  // it shows up as a slow frame in a baseline that is supposed to describe the
  // steady state a reviewer drags through.
  assert.match(source, /gl\.render\(scene, camera\);\s*\n\s*const still_frame/);
});
