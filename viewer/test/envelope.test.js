import assert from "node:assert/strict";
import test from "node:test";

import {
  ENVELOPE_FIELD_ID,
  buildEnvelope,
  envelopeAvailable,
  envelopeResultStates,
  envelopeSourceOverlays,
  isEnvelopeField
} from "../src/envelope.js";
import { scalarFor } from "../src/coloring.js";

function state({ steps = ["Hot", "Cold"], quantities = ["stress"] } = {}) {
  const resultStates = steps.map((id) => ({
    id: `overlay:result_state:${id}`,
    kind: "result_state",
    name: id,
    data: { id: `result_state:${id}`, load_case: "Hot" }
  }));
  // Each quantity in each step, with values chosen so the envelope has a
  // different winner per object - which is the case that makes "which step won"
  // worth reporting at all.
  const values = {
    "overlay:0:stress": { "object:a": 10, "object:b": 90 },
    "overlay:1:stress": { "object:a": 70, "object:b": 20 }
  };
  const overlays = steps.flatMap((step, stepIndex) =>
    quantities.map((quantity) => ({
      id: `overlay:${stepIndex}:${quantity}`,
      kind: "solver_result",
      data: {
        result_state_id: `result_state:${step}`,
        result_type: quantity,
        load_case: "Hot",
        field: quantity === "stress" ? "max_von_mises" : "reaction_force_magnitude",
        unit: quantity === "stress" ? "Pa" : "N",
        values: values[`overlay:${stepIndex}:${quantity}`] ?? {}
      }
    })));
  return { resultStates, overlays: [...resultStates, ...overlays], activeLoadCase: "Hot" };
}

const stressField = { field: "max_von_mises", unit: "Pa", result_type: "stress", load_case: "Hot" };

test("an envelope needs more than one result step to be an envelope", () => {
  assert.equal(envelopeAvailable(state()), true);
  assert.equal(envelopeAvailable(state({ steps: ["Hot"] })), false);
  assert.equal(envelopeAvailable({ resultStates: [], overlays: [] }), false);
  assert.deepEqual(envelopeResultStates(state()).map((step) => step.id), ["result_state:Hot", "result_state:Cold"]);
});

test("the envelope takes the worst value per object, not the last one", () => {
  const envelope = buildEnvelope(state(), stressField);
  // A: 10 then 70. B: 90 then 20. A last-wins would report 70 and 20.
  assert.deepEqual(envelope.values, { "object:a": 70, "object:b": 90 });
  assert.deepEqual(envelope.range, { min: 70, max: 90 });
  assert.equal(envelope.enveloped, true);
  assert.deepEqual(envelope.resultStateIds.sort(), ["result_state:Cold", "result_state:Hot"]);
});

test("the envelope records which result step governed each object", () => {
  // This is the difference between a maximum and an answer. A reviewer needs to
  // know which load step to go and look at, not just what the worst number was.
  const envelope = buildEnvelope(state(), stressField);
  assert.equal(envelope.winners["object:a"], "result_state:Cold");
  assert.equal(envelope.winners["object:b"], "result_state:Hot");
});

test("a tie is credited to the earlier result step", () => {
  // A tie in a staged run usually means the increment added nothing, and naming
  // the later step would credit it with a value it did not produce.
  const tied = state();
  tied.overlays.find((overlay) => overlay.id === "overlay:1:stress").data.values["object:a"] = 10;
  const envelope = buildEnvelope(tied, stressField);
  assert.equal(envelope.winners["object:a"], "result_state:Hot");
});

test("a displacement envelope never absorbs a stress overlay", () => {
  // Both are keyed by object id, so matching on the key alone would blend
  // pascals and newtons into one field.
  const mixed = state({ quantities: ["stress", "reaction_force"] });
  const sources = envelopeSourceOverlays(mixed, stressField);
  assert.equal(sources.length, 2);
  assert.ok(sources.every((overlay) => overlay.data.unit === "Pa"));
  const envelope = buildEnvelope(mixed, stressField);
  assert.ok(Object.values(envelope.values).every((value) => value > 0 && value < 1000));
});

test("an envelope of one step says so rather than wearing the label", () => {
  const envelope = buildEnvelope(state({ steps: ["Hot"], quantities: ["stress"] }), stressField);
  assert.deepEqual(envelope.values, { "object:a": 10, "object:b": 90 });
  // One contributing step is a result, not a maximum over results.
  assert.equal(envelope.enveloped, false);
  const none = buildEnvelope({ ...state(), overlays: [] }, stressField);
  assert.equal(none.enveloped, false);
  assert.equal(none.range, null);
  assert.deepEqual(none.values, {});
});

test("two published steps that only one of which carries the quantity is not an envelope", () => {
  // The load case published two steps, but the second has no stress overlay. A
  // "worst of two result steps" that silently considered one is the kind of
  // claim this product does not make.
  const partial = state();
  partial.overlays = partial.overlays.filter((overlay) => overlay.id !== "overlay:1:stress");
  const envelope = buildEnvelope(partial, stressField);
  assert.equal(envelope.enveloped, false);
  assert.deepEqual(envelope.resultStateIds, ["result_state:Hot"]);
  assert.deepEqual(envelope.values, { "object:a": 10, "object:b": 90 });
});

test("non-finite values never enter an envelope", () => {
  const broken = state();
  broken.overlays.find((overlay) => overlay.id === "overlay:1:stress").data.values["object:a"] = NaN;
  const envelope = buildEnvelope(broken, stressField);
  // The step that could not be read leaves the earlier value standing rather
  // than dragging the maximum to zero or to Infinity.
  assert.equal(envelope.values["object:a"], 10);
  assert.equal(envelope.winners["object:a"], "result_state:Hot");
});

test("missing values and unavailable vector components cannot become solved zeros", () => {
  for (const value of [null, undefined, "", " ", false, [], [null, 0, 0]]) {
    assert.ok(Number.isNaN(scalarFor(value, "magnitude")), String(value));
  }
  assert.ok(Number.isNaN(scalarFor([1, 2, 3], "DRX")));
  const broken = state();
  for (const overlay of broken.overlays.filter(overlay => overlay.data.values)) {
    overlay.data.values["object:a"] = null;
  }
  assert.equal(buildEnvelope(broken, stressField).values["object:a"], undefined);
  assert.equal(buildEnvelope(broken, stressField, "magnitude", scalarFor).values["object:a"], undefined);
});

test("a vector component is enveloped as the component, not the magnitude", () => {
  const vectorState = state({ quantities: ["displacement"] });
  for (const overlay of vectorState.overlays) {
    if (overlay.data.result_type === "displacement") {
      overlay.data.field = "displacement_magnitude";
      overlay.data.unit = "m";
      overlay.data.values = { "object:a": [0, 0, 3], "object:b": [0, 0, 1] };
    }
  }
  const envelope = buildEnvelope(
    vectorState,
    { field: "displacement_magnitude", unit: "m", result_type: "displacement" },
    "magnitude",
    scalarFor
  );
  assert.deepEqual(envelope.values, { "object:a": 3, "object:b": 1 });
});

test("an envelope only spans the active load case", () => {
  const twoCases = state();
  twoCases.overlays.push({
    id: "overlay:other",
    kind: "solver_result",
    data: { result_state_id: "result_state:Other", result_type: "stress", load_case: "Other", field: "max_von_mises", unit: "Pa", values: { "object:a": 9999 } }
  });
  twoCases.resultStates.push({
    id: "overlay:result_state:Other",
    kind: "result_state",
    data: { id: "result_state:Other", load_case: "Other" }
  });
  const envelope = buildEnvelope(twoCases, stressField);
  // Enveloping across load cases would be a different quantity - a combination
  // - and mixing them is the mistake the load-case algebra exists to prevent.
  assert.equal(envelope.values["object:a"], 70);
});

test("the envelope field is recognisable as itself", () => {
  assert.equal(isEnvelopeField({ id: ENVELOPE_FIELD_ID }), true);
  assert.equal(isEnvelopeField({ id: "field:stress" }), false);
  assert.equal(isEnvelopeField(null), false);
});

test("a null field yields an empty envelope rather than throwing", () => {
  const envelope = buildEnvelope(state(), null);
  assert.deepEqual(envelope.values, {});
  assert.equal(envelope.range, null);
});
