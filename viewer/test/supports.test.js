import assert from "node:assert/strict";
import test from "node:test";

import { DOF_AXES, supportBlockedDofs, supportDofStates } from "../src/supports.js";
import { getSelectionSummary } from "../src/selectionSummary.js";

const states = (config) => supportDofStates(config).join(",");

test("a directionless rest is one-way on Z, the DOF the solver constrains", () => {
  // aster_comm.py writes NOM_CMP='DZ' for a rest with no direction: Tuba is
  // Z-up and gravity is (0, 0, -1), so the shoe is underneath the pipe.
  assert.equal(states({ support_type: "rest" }), "free,free,one-way,free,free,free");
});

test("a rest takes one axis only, matching the single NOM_CMP of its contact zone", () => {
  // DEFI_CONTACT gets one component; aster_comm.py breaks after the first
  // nonzero. Claiming all three would show restraint that was never applied.
  assert.equal(states({ support_type: "rest", direction: [0, 1, 1] }), "free,one-way,free,free,free,free");
});

test("a guide blocks every nonzero component of its direction and no rotation", () => {
  assert.equal(states({ support_type: "guide", direction: [1, 1, 0] }), "fixed,fixed,free,free,free,free");
});

test("a guide with no direction falls back to all three translations", () => {
  assert.equal(states({ support_type: "guide" }), "fixed,fixed,fixed,free,free,free");
});

test("an anchor fixes all six, and 'fixed' is accepted as its older spelling", () => {
  assert.equal(states({ support_type: "anchor" }), "fixed,fixed,fixed,fixed,fixed,fixed");
  assert.equal(states({ support_type: "fixed" }), "fixed,fixed,fixed,fixed,fixed,fixed");
});

test("a spring restrains nothing rigidly - only the axes carrying stiffness", () => {
  assert.equal(
    states({ support_type: "spring", stiffness_matrix: [0, 0, 4.72e4, 0, 0, 0] }),
    "free,free,spring,free,free,free"
  );
  // Without a direction a scalar stiffness has no axis, so nothing is claimed.
  assert.equal(states({ support_type: "spring", stiffness: 4.72e4 }), "free,free,free,free,free,free");
  assert.equal(
    states({ support_type: "spring", stiffness: 4.72e4, direction: [0, 0, 1] }),
    "free,free,spring,free,free,free"
  );
});

test("an explicit blocked_dof overrides the type", () => {
  assert.equal(
    states({ support_type: "rest", blocked_dof: [1, 1, 0, 0, 0, 1] }),
    "fixed,fixed,free,free,free,fixed"
  );
});

test("the glyph treats one-way as held - it is a restraint, just a conditional one", () => {
  assert.deepEqual(supportBlockedDofs({ support_type: "rest" }), [false, false, true, false, false, false]);
  assert.deepEqual(supportBlockedDofs({ support_type: "spring", stiffness_matrix: [1, 0, 0, 0, 0, 0] }),
    [false, false, false, false, false, false]);
});

test("DOF_AXES is the solver's order, so an index means the same thing everywhere", () => {
  assert.deepEqual([...DOF_AXES], ["X", "Y", "Z", "RX", "RY", "RZ"]);
});

function stateWith(objects, geometryAssets = []) {
  return { objects, geometryAssets, overlays: [], issues: [], visibleObjectIds: objects.map((obj) => obj.id) };
}

function supportFixture(metadata, assetConfig = {}) {
  const objects = [{
    id: "object:support:s0",
    entity_ref: "support:s0",
    kind: "support",
    name: "s0",
    geometry_asset_id: "geometry:support:s0",
    metadata
  }];
  const assets = [{
    id: "geometry:support:s0",
    format: "point",
    bounds: [2, 0, 0, 2, 0, 0],
    object_ids: ["object:support:s0"],
    generation_config: { source: "tuba.support", point: [2, 0, 0], ...assetConfig }
  }];
  return stateWith(objects, assets);
}

test("the panel leads with what the support does, not with its id", () => {
  const summary = getSelectionSummary(supportFixture({ support_type: "anchor", node: "N0" }), "object:support:s0");
  assert.equal(summary.title, "Anchor");
  assert.equal(summary.lede, "Fixes all six degrees of freedom at node N0.");
  assert.equal(summary.meta, "s0 · node N0 · 2, 0, 0 m");
  assert.deepEqual(summary.dofs.map((dof) => dof.state), Array(6).fill("fixed"));
});

test("a rest says it lifts off, and carries its gap and friction into the sentence", () => {
  const state = supportFixture({ support_type: "rest", node: "N1", gap: 0.003, friction_coefficient: 0.3 });
  const summary = getSelectionSummary(state, "object:support:s0");
  assert.equal(summary.title, "Rest");
  assert.match(summary.lede, /compression only along Z and lifts off in tension/);
  assert.match(summary.lede, /3 mm gap/);
  assert.match(summary.lede, /0\.3/);
});

test("the ids fold into Reference, and the two derived spellings are dropped", () => {
  const summary = getSelectionSummary(supportFixture({ support_type: "anchor", node: "N0" }), "object:support:s0");
  assert.deepEqual(summary.reference, {
    entity_ref: "support:s0",
    geometry: "point",
    source: "tuba.support"
  });
  const titles = summary.sections.map((section) => section.title);
  for (const gone of ["Identity", "Geometry", "Provenance"]) {
    assert.equal(titles.includes(gone), false, `${gone} should have folded into Reference`);
  }
});

test("the reaction the solver reported reaches the panel in display units", () => {
  const state = supportFixture({ support_type: "anchor", node: "N0" });
  state.geometryAssets.push({
    id: "geometry:solver_result:reaction_force:result_state_Hot:N0",
    format: "vector",
    bounds: [0, 0, 0, 1, 0, 0],
    object_ids: [],
    generation_config: {
      source: "tuba.result_state",
      result_type: "reaction_force",
      node_id: "N0",
      load_case: "Hot",
      reaction_force_n: [3000, 0, 4000]
    }
  });
  const summary = getSelectionSummary(state, "object:support:s0");
  const reactions = summary.sections.find((section) => section.title.startsWith("Reactions"));
  assert.ok(reactions, "a support with a reaction gets a Reactions section");
  assert.equal(reactions.lines[0].value, "5 kN");
});

test("a support the scene says nothing extra about gets no empty sections", () => {
  const summary = getSelectionSummary(supportFixture({ support_type: "anchor", node: "N0" }), "object:support:s0");
  for (const section of summary.sections) {
    assert.ok(section.lines.length > 0, `${section.title} is empty and should have been omitted`);
  }
});
