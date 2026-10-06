// The support glyph's vocabulary, and the fact that the viewport key and the
// renderer share it.
//
// An imposed displacement is the case that matters here: it is an authored
// input (not a result), it is drawn as its own mark, and
// before this it was named in neither the key nor the published scene.

import assert from "node:assert/strict";
import test from "node:test";
import { prescribedDisplacementText, SUPPORT_BUILD_COLORS, SUPPORT_PART_LABELS, SUPPORT_REVIEW_COLORS, supportPartColors, supportParts, visibleSupportParts } from "../src/supportGlyphs.js";

const FIXED = ["fixed", "fixed", "fixed", "fixed", "fixed", "fixed"];
const ALL_FREE = ["free", "free", "free", "free", "free", "free"];
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
  for (const palette of [SUPPORT_BUILD_COLORS, SUPPORT_REVIEW_COLORS]) {
    assert.deepEqual(Object.keys(palette).sort(), Object.keys(SUPPORT_PART_LABELS).sort());
  }
  for (const [part, label] of Object.entries(SUPPORT_PART_LABELS)) {
    assert.match(label, /— authored input/, `${part} must be marked as an authored input`);
    for (const palette of [SUPPORT_BUILD_COLORS, SUPPORT_REVIEW_COLORS]) {
      assert.match(palette[part], /^#[0-9a-f]{6}$/i, `${part} needs a hex colour the renderer can parse`);
    }
  }
  // No backend compiles a prescribed movement as a penalty spring: the volume
  // and mixed studies impose it exactly (DDL_IMPO), the line compiler refuses it.
  assert.doesNotMatch(SUPPORT_PART_LABELS.prescribed, /penalty/i);
});

test("in Build each support role has its own colour, as in other piping programs", () => {
  // Build has no results, so the reaction colours cannot be confused with it.
  assert.deepEqual(supportPartColors("build"), SUPPORT_BUILD_COLORS);
  assert.equal(SUPPORT_BUILD_COLORS.restraint, "#daa520", "restraints are gold");
  assert.equal(SUPPORT_BUILD_COLORS.spring, "#16a34a", "springs are green, clear of the blue members");
  assert.equal(SUPPORT_BUILD_COLORS.prescribed, "#f97316", "prescribed movements are orange");
});

test("in Review support glyphs are achromatic, so hue is left to the results", () => {
  // Blue and teal are authored inputs; red and orange are Code_Aster results.
  // The Build colours borrow a blue and an orange from those two ends, so in
  // Review a reader could not tell an authored support from a solved reaction
  // by looking at the mark. One neutral, and shape does the rest. The embedded
  // canvas shows published reviews and takes the same palette.
  assert.deepEqual(supportPartColors("review"), SUPPORT_REVIEW_COLORS);
  assert.deepEqual(supportPartColors("embed"), SUPPORT_REVIEW_COLORS);
  const values = new Set(Object.values(SUPPORT_REVIEW_COLORS));
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

test("the support key names each glyph's shape", () => {
  // The key has to say which is which, or a shape-only language is undecodable.
  assert.match(SUPPORT_PART_LABELS.prescribed, /hollow cone/);
  assert.match(SUPPORT_PART_LABELS.restraint, /solid cones/);
  assert.match(SUPPORT_PART_LABELS.spring, /coil/);
});

test("the prescribed badge names the moving components, in display units", () => {
  const config = { imposed_displacement: [0, 0, 0.08] };
  assert.equal(prescribedDisplacementText(config), "ΔZ = 80 mm");
  assert.equal(prescribedDisplacementText(config, "si"), "ΔZ = 0.08 m");
  // Rotations stay in rad, the unit DRX..DRZ are coloured in.
  assert.equal(prescribedDisplacementText({ imposed_displacement: [-0.005, 0, 0, 0, 0, 0.01] }), "ΔX = -5 mm · ΔRZ = 0.01 rad");
  // Nothing moves, nothing to say: a badge of zeros would be noise.
  assert.equal(prescribedDisplacementText({ imposed_displacement: [0, 0, 0] }), null);
  assert.equal(prescribedDisplacementText({}), null);
});
