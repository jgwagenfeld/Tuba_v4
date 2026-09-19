import test from "node:test";
import assert from "node:assert/strict";
import {
  CATEGORICAL_PALETTE,
  MODEL_COLOR_MODES,
  getModelObjectPropertyValue,
  getModelColoring,
  getModelObjectColor
} from "../src/modelColoring.js";

test("getModelObjectPropertyValue extracts section, material, group and insulation", () => {
  const obj = {
    id: "obj1",
    kind: "pipe",
    metadata: {
      section: "PIPE_4_SCH40",
      material: "A106-B",
      groups: ["Header_1"],
      insulation: {
        material: "mineral_wool",
        thickness_m: 0.05
      }
    }
  };

  assert.equal(getModelObjectPropertyValue(obj, "section"), "PIPE_4_SCH40");
  assert.equal(getModelObjectPropertyValue(obj, "material"), "A106-B");
  assert.equal(getModelObjectPropertyValue(obj, "group"), "Header_1");
  assert.equal(getModelObjectPropertyValue(obj, "insulation"), "mineral_wool (50 mm)");
  assert.equal(getModelObjectPropertyValue(obj, "default"), null);
});

test("getModelColoring assigns deterministic palette colors to sorted unique values", () => {
  const state = {
    modelColorBy: "material",
    objects: [
      { id: "e1", kind: "pipe", metadata: { material: "Steel_A" } },
      { id: "e2", kind: "pipe", metadata: { material: "Steel_B" } },
      { id: "e3", kind: "pipe", metadata: { material: "Steel_A" } }
    ]
  };

  const coloring = getModelColoring(state, "material");
  assert.equal(coloring.mode, "material");
  assert.equal(coloring.items.length, 2);

  // Steel_A comes first alphabetically
  assert.equal(coloring.items[0].value, "Steel_A");
  assert.equal(coloring.items[0].count, 2);
  assert.equal(coloring.items[0].color, CATEGORICAL_PALETTE[0]);
  assert.deepEqual(coloring.items[0].objectIds, ["e1", "e3"]);

  // Steel_B comes second
  assert.equal(coloring.items[1].value, "Steel_B");
  assert.equal(coloring.items[1].count, 1);
  assert.equal(coloring.items[1].color, CATEGORICAL_PALETTE[1]);
  assert.deepEqual(coloring.items[1].objectIds, ["e2"]);
});

test("getModelObjectColor returns hex color when active and null when default", () => {
  const state = {
    activeTab: "model",
    modelColorBy: "section",
    objects: [
      { id: "p1", kind: "pipe", metadata: { section: "DN50" } },
      { id: "p2", kind: "pipe", metadata: { section: "DN100" } }
    ]
  };

  const colorP1 = getModelObjectColor(state, ["p1"]);
  const colorP2 = getModelObjectColor(state, ["p2"]);
  assert.notEqual(colorP1, null);
  assert.notEqual(colorP2, null);
  assert.notEqual(colorP1, colorP2);

  // When mode is default, returns null
  assert.equal(getModelObjectColor({ ...state, modelColorBy: "default" }, ["p1"]), null);

  // When the results task governs the scene, it yields the colouring channel.
  // The scene has to actually carry results for Results to be a task the rail
  // offers - otherwise it resolves back to Model, which is the point of the
  // guard rather than a quirk of this fixture.
  assert.equal(
    getModelObjectColor({ ...state, activeTab: "results", resultFields: [{ id: "field:stress" }] }, ["p1"]),
    null
  );
});

test("Build colours by the model whatever task the rail was left on", () => {
  // Build inspects what was built, so model colouring governs its scene. That
  // used to hold only by accident: entering Build forced activeTab to "model",
  // so `activeTab !== "model"` doubled as "results colouring is active". Once
  // Build stopped claiming a task, a reader who left the rail on Results and
  // switched to Build lost the model colouring with it.
  const state = {
    stage: "build",
    activeTab: "results",
    modelColorBy: "section",
    resultFields: [{ id: "field:stress" }],
    objects: [{ id: "p1", kind: "pipe", metadata: { section: "DN50" } }]
  };

  assert.notEqual(getModelObjectColor(state, ["p1"]), null);
  // And the review stage still yields the scene to the results channel.
  assert.equal(getModelObjectColor({ ...state, stage: "review" }, ["p1"]), null);
});

test("reduceViewerState handles setModelColorBy action", async () => {
  const { reduceViewerState } = await import("../src/viewerState.js");
  const initial = { modelColorBy: "default", objects: [] };
  const next = reduceViewerState(initial, { type: "setModelColorBy", colorBy: "material" });
  assert.equal(next.modelColorBy, "material");
});

test("prepareAssetRenderConfig tints assets with model property colors", async () => {
  const { prepareAssetRenderConfig } = await import("../src/renderer.js");
  const asset = {
    id: "geom:p1",
    format: "tube",
    object_ids: ["p1"],
    generation_config: { radius_m: 0.05 }
  };
  const state = {
    activeTab: "model",
    modelColorBy: "section",
    objects: [{ id: "p1", kind: "pipe", metadata: { section: "DN50" } }]
  };
  const config = prepareAssetRenderConfig(asset, {}, state);
  assert.notEqual(config.color, undefined);
  assert.equal(typeof config.color, "number");
});

