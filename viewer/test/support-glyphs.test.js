// The support glyph's vocabulary, and the fact that the viewport key and the
// renderer share it.
//
// An imposed displacement is the case that matters here: it is an authored
// input that compiles to a penalty spring, it is drawn as its own mark, and
// before this it was named in neither the key nor the published scene.

import assert from "node:assert/strict";
import test from "node:test";
import { describeDofStates, SUPPORT_PART_COLORS, SUPPORT_PART_FILLS, SUPPORT_PART_LABELS, supportParts, visibleSupportParts } from "../src/supportGlyphs.js";

const FIXED = ["fixed", "fixed", "fixed", "fixed", "fixed", "fixed"];
const ALL_FREE = ["free", "free", "free", "free", "free", "free"];
const GUIDE_X = ["fixed", "free", "free", "free", "free", "free"];
const SHOE_Z = ["free", "free", "one-way", "free", "free", "free"];
const SPRING_Z = ["free", "free", "spring", "free", "free", "free"];

test("a restraint, a spring and a prescribed movement are three different marks", () => {
  assert.deepEqual(supportParts({ dof_states: FIXED }), ["restraint"]);
  assert.deepEqual(supportParts({ dof_states: SPRING_Z }), ["spring"]);
  assert.deepEqual(supportParts({ dof_states: SHOE_Z, imposed_displacement: [0, 0, 0.004] }),
    ["restraint", "prescribed"]);
  // A shoe is a one-way restraint, so it is named as a restraint even though it
  // is not bilateral - the key must not imply it holds all six.
  assert.deepEqual(supportParts({ dof_states: SHOE_Z }), ["restraint"]);
  assert.deepEqual(supportParts({ dof_states: ALL_FREE, stiffness_matrix: [0, 0, 1e6] }), ["spring"]);
});

test("a zero prescribed displacement is not a prescribed movement", () => {
  // Authoring [0,0,0] is a no-op, and drawing an orange cone for it would claim
  // a movement that was never asked for.
  assert.deepEqual(supportParts({ dof_states: ALL_FREE, imposed_displacement: [0, 0, 0] }), []);
  assert.deepEqual(supportParts({ dof_states: ALL_FREE, imposed_displacement: [0, 0, 0.004] }), ["prescribed"]);
});

test("the key lists only marks the scene is showing", () => {
  const support = (id, config) => ({
    id,
    kind: "support",
    geometry_asset_id: `asset:${id}`,
    metadata: { support_id: id }
  });
  const state = {
    objects: [support("a", {}), support("b", {}), support("c", {})],
    geometryAssets: [
      { id: "asset:a", generation_config: { dof_states: FIXED } },
      { id: "asset:b", generation_config: { dof_states: SPRING_Z } },
      { id: "asset:c", generation_config: { dof_states: ALL_FREE } }
    ]
  };
  // Everything on screen: restraint and spring, no prescribed movement.
  assert.deepEqual(visibleSupportParts(state, new Set(["a", "b", "c"])), ["restraint", "spring"]);
  // One support hidden: its mark leaves the key with it.
  assert.deepEqual(visibleSupportParts(state, new Set(["a", "c"])), ["restraint"]);
  // Nothing visible: the key says nothing, rather than advertising every hue.
  assert.deepEqual(visibleSupportParts(state, new Set()), []);
});

test("the key names every mark it can list, and each says it is an input", () => {
  assert.deepEqual(Object.keys(SUPPORT_PART_COLORS).sort(), Object.keys(SUPPORT_PART_LABELS).sort());
  for (const [part, label] of Object.entries(SUPPORT_PART_LABELS)) {
    assert.match(label, /— authored input/, `${part} must be marked as an authored input`);
    assert.match(SUPPORT_PART_COLORS[part], /^#[0-9a-f]{6}$/i, `${part} needs a hex colour the renderer can parse`);
  }
  // "Prescribed displacement" has to say it is a penalty, because a prescribed
  // value a penalty method cannot hold exactly is the thing most worth knowing.
  assert.match(SUPPORT_PART_LABELS.prescribed, /penalty/i);
});

test("support glyphs are achromatic, so hue is left to the vector convention", () => {
  // Blue and teal are authored inputs; red and orange are Code_Aster results.
  // The support glyphs used to borrow a blue and an orange from those two ends,
  // so a reader could not tell an authored support from a solved reaction by
  // looking at the mark. One neutral, and shape does the rest.
  const values = new Set(Object.values(SUPPORT_PART_COLORS));
  assert.equal(values.size, 1, "all three parts must share one colour");
  const [only] = [...values];
  const r = Number.parseInt(only.slice(1, 3), 16);
  const g = Number.parseInt(only.slice(3, 5), 16);
  const b = Number.parseInt(only.slice(5, 7), 16);
  assert.equal(r, g, "the neutral has no red bias");
  assert.equal(g, b, "the neutral has no blue bias");
  // Dark enough to read on the light ground the renderer paints (#f8fafc).
  const luminance = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
  assert.ok(luminance < 0.25, `neutral luminance ${luminance.toFixed(2)} is too light for the light ground`);

  // And it is not any hue the vector convention spends.
  for (const vectorColor of ["#2563eb", "#0f766e", "#dc2626", "#f97316", "#7c3aed", "#0284c7"]) {
    assert.notEqual(only.toLowerCase(), vectorColor, "support glyphs must not reuse a vector hue");
  }
});

test("shape, not fill alone, tells a prescribed movement from a restraint", () => {
  // Both are cones on one axis. Solid-vs-hollow is the second signal, and the
  // restraint's paired cones are the first.
  assert.equal(SUPPORT_PART_FILLS.prescribed, "hollow");
  assert.equal(SUPPORT_PART_FILLS.restraint, "solid");
  assert.equal(SUPPORT_PART_FILLS.spring, "solid");
  // The key has to say which is which, or a shape-only language is undecodable.
  assert.match(SUPPORT_PART_LABELS.prescribed, /hollow cone/);
  assert.match(SUPPORT_PART_LABELS.restraint, /solid cones/);
  assert.match(SUPPORT_PART_LABELS.spring, /rings/);
});

test("held degrees of freedom are spelled out for the inspector", () => {
  assert.equal(describeDofStates(FIXED), "X, Y, Z, RX, RY, RZ");
  assert.equal(describeDofStates(GUIDE_X), "X");
  assert.equal(describeDofStates(SHOE_Z), "Z");
  assert.equal(describeDofStates(ALL_FREE), "");
  assert.equal(describeDofStates(null), "");
});
