import assert from "node:assert/strict";
import test from "node:test";

import { getAveragingBasis, getReactionConsistency, isBalanced } from "../src/trustFacts.js";

// Two nodes, one at the origin and one 2 m out in X, so a 100 N force at the
// far node carries a 200 N-m moment about the origin. Getting that arm right is
// the difference between a moment balance and a number that merely looks like
// one.
function solvedState({
  reactions = { N1: [0, 0, -100], N2: [0, 0, 0] },
  reactionMoments = { N1: [0, 0, 0], N2: [0, 0, 0] },
  applied = [],
  loadCase = { load_case: "Hot", gravity: false, internal_pressure_pa: 0, field_count: 0 },
  nodePositions = { N1: [0, 0, 0], N2: [2, 0, 0] }
} = {}) {
  return {
    objects: applied.map((entry, index) => ({
      id: `object:applied:${index}`,
      kind: "applied_load",
      name: `Applied ${entry.vector_kind}`,
      metadata: {
        load_case: loadCase.load_case,
        node_id: entry.node_id,
        vector_kind: entry.vector_kind,
        components: entry.components
      }
    })),
    overlays: [
      {
        id: "overlay:reaction_force:Hot",
        data: { result_type: "reaction_force", values: reactions, vectors: [] }
      },
      {
        id: "overlay:reaction_moment:Hot",
        data: { result_type: "reaction_moment", values: reactionMoments, vectors: [] }
      },
      {
        id: "overlay:reaction_positions:Hot",
        data: { result_type: "reaction_force", values: {}, vectors: Object.entries(nodePositions).map(([node_id, start]) => ({ node_id, start })) }
      }
    ],
    loadCase
  };
}

function consistency(overrides) {
  const state = solvedState(overrides);
  return getReactionConsistency(state, {
    reactionForce: state.overlays[0].data.values,
    reactionMoment: state.overlays[1].data.values,
    loadCase: state.loadCase.load_case,
    loadCaseDefinition: state.loadCase
  });
}

test("reactions that cancel the applied loads balance", () => {
  const balance = consistency({
    reactions: { N1: [0, 0, -100] },
    applied: [{ node_id: "N1", vector_kind: "force", components: [0, 0, 100] }]
  });
  assert.deepEqual(balance.reactionForce, [0, 0, -100]);
  assert.deepEqual(balance.appliedForce, [0, 0, 100]);
  assert.equal(balance.forceResidual, 0);
  assert.equal(balance.forceResidualRatio, 0);
  assert.equal(balance.complete, true);
  assert.equal(isBalanced(balance.forceResidualRatio, balance.tolerance), true);
});

test("an unbalanced reaction set is reported as a residual, not as a verdict", () => {
  const balance = consistency({
    reactions: { N1: [0, 0, -80] },
    applied: [{ node_id: "N1", vector_kind: "force", components: [0, 0, 100] }]
  });
  assert.equal(balance.forceResidual, 20);
  assert.equal(balance.forceResidualRatio, 20 / 180);
  assert.equal(isBalanced(balance.forceResidualRatio, balance.tolerance), false);
  // No pass/fail vocabulary. This is a consistency check on the solve; saying
  // "fail" here would be a code claim, and there is no code in this number.
  assert.equal(balance.verdict ?? null, null);
});

test("the moment balance carries the applied forces to the same origin", () => {
  // 100 N at x=2 m needs 200 N-m of reaction moment to hold it, and the applied
  // side has to be evaluated about the origin too. Summing the nodal moments
  // alone would leave 200 N-m on the table and call it a residual.
  const balance = consistency({
    reactions: { N1: [0, 0, -100] },
    reactionMoments: { N1: [0, 0, 0] },
    applied: [{ node_id: "N2", vector_kind: "force", components: [0, 0, 100] }]
  });
  assert.deepEqual(balance.appliedMomentAboutOrigin, [0, -200, 0]);
  // The reaction set has no moment, so this does not close - and it should not.
  assert.equal(Math.round(balance.momentResidual), 200);
  assert.equal(isBalanced(balance.momentResidualRatio, balance.tolerance), false);
});

test("an applied nodal moment balances against a reaction moment directly", () => {
  const balance = consistency({
    reactions: { N1: [0, 0, 0] },
    reactionMoments: { N1: [0, 0, -50] },
    applied: [{ node_id: "N1", vector_kind: "moment", components: [0, 0, 50] }]
  });
  assert.equal(balance.momentResidual, 0);
  assert.equal(isBalanced(balance.momentResidualRatio, balance.tolerance), true);
});

test("solver-assembled loads are named as excluded, never silently dropped", () => {
  // Self-weight and pressure are assembled inside Code_Aster and never reach the
  // bundle, so a "balanced" badge here would be balanced over one term out of
  // three. That is the silent-omission failure this exists to prevent, so the
  // omissions travel with the number.
  const balance = consistency({
    reactions: { N1: [0, 0, -100] },
    applied: [{ node_id: "N1", vector_kind: "force", components: [0, 0, 100] }],
    loadCase: { load_case: "Hot", gravity: true, internal_pressure_pa: 4e6, field_count: 1 }
  });
  assert.equal(balance.complete, false);
  assert.equal(balance.forceResidual, 0);
  assert.ok(balance.omitted.some((term) => term.includes("self-weight")));
  assert.ok(balance.omitted.some((term) => term.includes("internal pressure")));
  assert.ok(balance.omitted.some((term) => term.includes("load fields")));
  // The residual is still zero - it is just not a claim about the whole model.
  assert.ok(balance.included.join(" "));
});

test("line loads are excluded too", () => {
  const balance = consistency({
    loadCase: { load_case: "Hot", gravity: false, internal_pressure_pa: 0, line_load_count: 2 }
  });
  assert.ok(balance.omitted.some((term) => term.includes("line loads")));
});

test("a bundle with no reactions yields nothing rather than an empty verdict", () => {
  assert.equal(getReactionConsistency({}, { reactionForce: null, reactionMoment: null }), null);
  // And a load definition that is not in the bundle says so instead of
  // implying the loads were all authored.
  const state = solvedState({ reactions: { N1: [0, 0, -100] } });
  const balance = getReactionConsistency(state, { reactionForce: state.overlays[0].data.values, loadCase: "Hot" });
  assert.equal(balance.complete, false);
  assert.ok(balance.omitted.some((term) => term.includes("load definition")));
});

test("applied loads from another load case are not summed into this one", () => {
  const state = solvedState({
    reactions: { N1: [0, 0, -100] },
    loadCase: { load_case: "Hot", gravity: false, internal_pressure_pa: 0 }
  });
  state.objects.push({
    id: "object:applied:cold",
    kind: "applied_load",
    metadata: { load_case: "Cold", node_id: "N1", vector_kind: "force", components: [0, 0, 9999] }
  });
  const balance = getReactionConsistency(state, {
    reactionForce: state.overlays[0].data.values,
    loadCase: "Hot",
    loadCaseDefinition: state.loadCase
  });
  assert.deepEqual(balance.appliedForce, [0, 0, 0]);
});

test("a non-applied-load object is never counted as a load", () => {
  const state = solvedState({ reactions: { N1: [0, 0, -100] } });
  state.objects.push({
    id: "object:reaction_vector",
    kind: "reaction_vector",
    metadata: { load_case: "Hot", node_id: "N1", vector_kind: "force", components: [0, 0, 500] }
  });
  const balance = getReactionConsistency(state, {
    reactionForce: state.overlays[0].data.values,
    loadCase: "Hot",
    loadCaseDefinition: state.loadCase
  });
  assert.deepEqual(balance.appliedForce, [0, 0, 0]);
});

test("the cell stress field states that it is an element-end maximum", () => {
  const basis = getAveragingBasis({}, { overlay: { data: { field: "max_von_mises" } }, field: "FE VMIS (not code stress)" });
  assert.equal(basis, "element maximum of the two element-end values");
});

test("a sub-point field states what was measured and what was interpolated", () => {
  const basis = getAveragingBasis({}, {
    overlay: { data: { field: "SIEQ_ELNO", component: "VMIS", stress_basis: "Code_Aster SIEQ_ELNO VMIS TUYAU sub-point" } },
    fieldId: "field:solver_result:tuyau_subpoints:Hot"
  });
  assert.equal(basis, "Code_Aster SIEQ_ELNO VMIS TUYAU sub-point");
  // Without a stated basis, the fallback still says the wall is interpolated,
  // which is the half a reviewer cannot infer from a smooth surface.
  const fallback = getAveragingBasis({}, { overlay: { data: { field: "SIEQ_ELNO" } }, fieldId: "field:solver_result:tuyau_subpoints:Hot" });
  assert.match(fallback, /measured at each Code_Aster section point/);
  assert.match(fallback, /interpolated/);
});

test("a builder's own derivation statement wins over any rule", () => {
  const basis = getAveragingBasis({}, {
    overlay: { data: { field: "max_von_mises", derivation: "arithmetic mean of SIEQ_ELNO element-node rows at each surface node" } }
  });
  assert.equal(basis, "arithmetic mean of SIEQ_ELNO element-node rows at each surface node");
});

test("a nodal field says it is a nodal value", () => {
  const basis = getAveragingBasis({}, { fieldId: "field:solver_result:displacement:Hot" });
  assert.equal(basis, "nodal value read from the solver result table");
});

test("a field with nothing to say returns null rather than a filler sentence", () => {
  assert.equal(getAveragingBasis({}, { overlay: { data: {} }, fieldId: "field:solver_result:internal_forces:Hot" }), "one value per element, as reported by the solver");
  assert.equal(getAveragingBasis({}, {}), null);
});
