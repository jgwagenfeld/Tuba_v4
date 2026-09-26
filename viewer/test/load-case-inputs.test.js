import assert from "node:assert/strict";
import test from "node:test";
import { assignmentObjectIds, assignmentScope, elementInputSection, loadCaseDefinitions } from "../src/loadCaseInputs.js";
import { createViewerState } from "../src/sceneLoader.js";
import { getLoadCaseOptions } from "../src/resultReview.js";
import { preserveViewerStateForReload, reduceViewerState } from "../src/viewerState.js";

test("unsolved cases select their own inputs and arrows without losing the selected pipe", () => {
  const field = { quantity: "pressure", scope: "group", group: "Return", value: 4e5, affected_element_ids: ["E2"] };
  const objects = [
    { id: "pipe1", kind: "pipe", entity_ref: "element:E1" },
    { id: "pipe2", kind: "pipe", entity_ref: "element:E2" },
    { id: "hot-force", kind: "applied_load", metadata: { load_case: "Hot" } },
    { id: "cold-force", kind: "applied_load", metadata: { load_case: "Cold" } }
  ];
  let state = createViewerState({ scene: { scene_id: "inputs", objects, overlays: [
    { id: "hot", kind: "load_case", data: { load_case: "Hot", temperature_c: 20, internal_pressure_pa: 15e5, fields: [field] } },
    { id: "cold", kind: "load_case", data: { load_case: "Cold", temperature_c: 20, internal_pressure_pa: 15e5, fields: [] } }
  ] } });
  assert.equal(state.activeLoadCase, "Hot");
  assert.deepEqual(getLoadCaseOptions(state).map((entry) => entry.id), ["Hot", "Cold"]);
  assert.equal(loadCaseDefinitions(state)[0].fields[0], field);
  assert.equal(assignmentScope(field), "Return");
  assert.deepEqual(assignmentObjectIds(state, field), ["pipe2"]);
  assert.match(elementInputSection(state, objects[1]).lines[1].label, /pressure · Return/);
  assert.match(elementInputSection(state, objects[0]).lines[1].label, /pressure · case default/);
  state = reduceViewerState(state, { type: "selectObjects", objectIds: ["pipe2"] });
  state = reduceViewerState(state, { type: "setActiveLoadCase", loadCase: "Cold" });
  assert.equal(state.activeLoadCase, "Cold");
  assert.deepEqual(state.selectedObjectIds, ["pipe2"]);
  assert.ok(state.visibleObjectIds.includes("cold-force"));
  assert.ok(!state.visibleObjectIds.includes("hot-force"));
  const solved = createViewerState({ scene: { scene_id: "review", objects, overlays: [
    ...state.overlays,
    { id: "hot-result", kind: "result_state", data: { id: "hot-state", load_case: "Hot" } },
    { id: "cold-result", kind: "result_state", data: { id: "cold-state", load_case: "Cold" } }
  ] } });
  const reviewed = preserveViewerStateForReload(state, solved);
  assert.equal(reviewed.activeLoadCase, "Cold");
  assert.equal(reviewed.activeResultStateId, "cold-state");
  assert.deepEqual(reviewed.selectedObjectIds, ["pipe2"]);
  assert.equal(assignmentScope({ scope: "route", route_id: "P1", station_start: 0, station_end: 3 }), "P1 (0–3 m)");
});
