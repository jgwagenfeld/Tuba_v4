import assert from "node:assert/strict";
import test from "node:test";

import { buildObjectTree, rankObjectMatches, searchObjects } from "../src/controls.js";

function state() {
  return {
    objects: [
      {
        id: "object:element:pipe_0",
        kind: "pipe",
        name: "P-100",
        entity_ref: "element:pipe_0",
        metadata: {
          material: "Steel",
          route: "R-100",
          insulation: { id: "mw_50", material: "mineral_wool" },
          attributes: { service: "hot_oil", design_pressure_bar: 19 },
          // The coordinates that made a whole-object match useless.
          profile: { outer_diameter_m: 0.1143 }
        }
      },
      { id: "object:support:S1", kind: "support", name: "Anchor N0", entity_ref: "support:S1", metadata: {} },
      { id: "object:displacement_vector:N2", kind: "displacement_vector", name: "D N2", metadata: {} }
    ],
    objectLayerIds: {
      "object:element:pipe_0": ["pipe"],
      "object:support:S1": ["support"],
      "object:displacement_vector:N2": ["result:displacement"]
    },
    layers: {
      pipe: { id: "pipe", category: "design" },
      support: { id: "support", category: "design" },
      "result:displacement": { id: "result:displacement", category: "results" }
    }
  };
}

test("search matches fields a reader can actually see", () => {
  assert.deepEqual(searchObjects(state(), "P-100").map((o) => o.id), ["object:element:pipe_0"]);
  assert.deepEqual(searchObjects(state(), "anchor").map((o) => o.id), ["object:support:S1"]);
  assert.deepEqual(searchObjects(state(), "mineral").map((o) => o.id), ["object:element:pipe_0"]);
  assert.deepEqual(searchObjects(state(), "hot_oil").map((o) => o.id), ["object:element:pipe_0"]);
  assert.deepEqual(searchObjects(state(), "R-100").map((o) => o.id), ["object:element:pipe_0"]);
});

test("search does not match coordinates, and numbers are not searchable text", () => {
  // The old implementation ran over JSON.stringify(obj), so "0.1143" matched the
  // pipe on its outer diameter and "1" matched almost everything.
  assert.deepEqual(searchObjects(state(), "0.1143"), []);
  assert.deepEqual(searchObjects(state(), "19"), []);
  assert.deepEqual(searchObjects(state(), "outer_diameter_m"), []);
});

test("a name hit outranks a metadata hit", () => {
  const scene = state();
  scene.objects[1].metadata.material = "P-100 alloy";
  const ranked = rankObjectMatches(scene, "P-100");
  assert.deepEqual(ranked.map((match) => match.object.id), ["object:element:pipe_0", "object:support:S1"]);
  assert.equal(ranked[0].field, "name");
  assert.equal(ranked[1].field, "material");
});

test("every match reports where it landed, so a row can say why it is there", () => {
  const [match] = rankObjectMatches(state(), "mineral");
  assert.equal(match.field, "insulation");
  const nameMatch = rankObjectMatches(state(), "100")[0];
  assert.equal(nameMatch.field, "name");
  assert.equal(nameMatch.object.name.slice(nameMatch.start, nameMatch.end), "100");
});

test("an empty query browses rather than returning nothing", () => {
  // The finder must be usable before you type: it replaced a browsable tree.
  const matches = rankObjectMatches(state(), "");
  assert.equal(matches.length, 3);
  assert.equal(matches[0].field, null);
});

test("the body axis groups by what draws an object, with a home for the rest", () => {
  const tree = buildObjectTree(state(), { groupBy: "body" });
  const groups = Object.fromEntries(tree.children.map((child) => [child.label, child.objectIds]));
  assert.deepEqual(groups.geometry, ["object:element:pipe_0", "object:support:S1"]);
  // Vectors, clash markers and proposals belong to no composited body. They get
  // a named bucket rather than disappearing from the finder.
  assert.deepEqual(groups.other, ["object:displacement_vector:N2"]);
});

test("the tree's other grouping axes still work through the same call", () => {
  const byKind = buildObjectTree(state(), { groupBy: "kind" });
  assert.deepEqual(byKind.children.map((child) => child.label).sort(), [
    "displacement_vector",
    "pipe",
    "support"
  ]);
  assert.equal(buildObjectTree(state(), { groupBy: "route" }).children[0].label, "R-100");
  assert.equal(buildObjectTree(state(), { groupBy: "material" }).children[0].label, "Steel");
});
