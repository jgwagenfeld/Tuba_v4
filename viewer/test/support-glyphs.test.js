// The support glyph's vocabulary, and the fact that the viewport key and the
// renderer share it.
//
// An imposed displacement is the case that matters here: it is an authored
// input that compiles to a penalty spring, it is drawn as its own mark, and
// before this it was named in neither the key nor the published scene.

import assert from "node:assert/strict";
import test from "node:test";
import { describeDofStates, SUPPORT_PART_COLORS, SUPPORT_PART_LABELS, supportParts, visibleSupportParts } from "../src/supportGlyphs.js";

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

test("held degrees of freedom are spelled out for the inspector", () => {
  assert.equal(describeDofStates(FIXED), "X, Y, Z, RX, RY, RZ");
  assert.equal(describeDofStates(GUIDE_X), "X");
  assert.equal(describeDofStates(SHOE_Z), "Z");
  assert.equal(describeDofStates(ALL_FREE), "");
  assert.equal(describeDofStates(null), "");
});
