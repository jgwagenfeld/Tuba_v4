import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { buildObjectTree, rankObjectMatches } from "../src/controls.js";
import { distance, selectObject } from "../src/selection.js";
import { relatedSelectionIds } from "../src/reviewSelection.js";
import { fieldLabel } from "../src/coloring.js";
import { geometryStateLabel } from "../src/resultReview.js";

const pipe = { id: "object:element:p", entity_ref: "element:p", kind: "pipe", name: "P-100" };
const mesh = { id: "object:mesh:p", entity_ref: "element:p", kind: "analysis_mesh_element", name: "P-100 mesh" };
const deformed = { id: "object:deformed:p", entity_ref: "element:p", kind: "deformed_centerline", name: "P-100 deformed" };
const vector = { id: "object:vector:n", entity_ref: "node:n", kind: "reaction_vector", name: "Reaction N" };

test("engineering tree nests representations, preserves orphan analysis and layer state", () => {
  const load = { id: "object:load:p", entity_ref: "element:p", kind: "applied_load", name: "Load on P-100" };
  const state = { objects: [pipe, load, mesh, deformed, vector], layers: { geometry: { visible: false } } };
  const tree = buildObjectTree(state);
  assert.deepEqual(tree.children[0].objectIds, [pipe.id, mesh.id, deformed.id]);
  assert.deepEqual(tree.children[0].children.map((child) => child.id), [mesh.id, deformed.id]);
  assert.deepEqual(tree.children[1].objectIds, [load.id]);
  assert.deepEqual(tree.children[2].objectIds, [vector.id]);
  assert.equal(tree.children[2].label, "Unmapped analysis");
  assert.equal(state.layers.geometry.visible, false);
  assert.deepEqual(rankObjectMatches(state, "mesh").map(({ object }) => object.id), [mesh.id]);
  assert.deepEqual(relatedSelectionIds(selectObject(state, deformed.id), [pipe.id]), [pipe.id, mesh.id, deformed.id]);
});

test("fixture pipe owns its solved representations even beside a load on the same entity", () => {
  const objects = JSON.parse(readFileSync(new URL("./fixtures/geometry_mesh_deformed/metadata/objects.json", import.meta.url), "utf8"));
  objects.push({ id: "object:load:pipe_str_0", kind: "applied_load", entity_ref: "element:pipe_str_0" });
  const tree = buildObjectTree({ objects });
  const pipe = tree.children.find((group) => group.id === "engineering:object:element:pipe_str_0");
  assert.ok(pipe.objectIds.some((id) => id.startsWith("object:analysis_mesh:") && id.includes("pipe_str_0")));
  assert.ok(pipe.objectIds.some((id) => id.startsWith("object:deformed_centerline:") && id.includes("pipe_str_0")));
  assert.ok(!pipe.objectIds.includes("object:load:pipe_str_0"));
});

test("field and geometry state labels keep readable engineering names", () => {
  assert.equal(fieldLabel({ id: "displacement" }), "Displacement");
  assert.equal(fieldLabel({ label: "displacement_magnitude" }), "Displacement");
  assert.equal(fieldLabel({ id: "reaction_force" }), "Reaction force");
  assert.equal(fieldLabel({ label: "reaction_force_magnitude" }), "Reaction force");
  assert.equal(geometryStateLabel({ data: {
    id: "geometry_state:Operating:physical", load_case: "Operating", state_type: "operating",
    purpose: "engineering", displacement_scale: 1
  } }), "Operating — actual deformation");
  assert.equal(geometryStateLabel({ data: {
    id: "geometry_state:Operating:visual_x50", load_case: "Operating", state_type: "deformed",
    purpose: "visualization", displacement_scale: 50
  } }), "Operating — exaggerated deformation (50×)");
});

test("rail tools wrap and bundle replacement clears measured points", () => {
  const styles = readFileSync(new URL("../src/styles.css", import.meta.url), "utf8");
  const app = readFileSync(new URL("../src/app.js", import.meta.url), "utf8");
  assert.match(styles, /\.rail-utility\s*\{[^}]*flex-wrap:\s*wrap/s);
  assert.match(app, /async function loadBundle\([\s\S]*?currentState = startupConfig\.embed[\s\S]*?measurementPoints = \[\];\s*measuring = false;/);
  assert.match(app, /function dispatch\(action\)[\s\S]*?"setActiveGeometryState"[\s\S]*?"setVisualDeformationScale"[\s\S]*?measurementPoints = \[\];/);
  assert.match(app, /function dispatch\(action\)[\s\S]*?"setActiveLoadCase"[\s\S]*?measurementPoints = \[\];/);
});

test("two picked points measure metres and reject absent or nonfinite geometry", () => {
  assert.equal(distance([0, 0, 0], [3, 4, 0]), 5);
  assert.throws(() => distance(null, [0, 0, 0]), TypeError);
  assert.throws(() => distance([0, NaN, 0], [0, 0, 0]), TypeError);
});
