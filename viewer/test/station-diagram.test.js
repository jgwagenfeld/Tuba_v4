import assert from "node:assert/strict";
import test from "node:test";

import {
  DIAGRAM_COMPONENTS,
  DIAGRAM_MIN_ELEMENTS,
  buildDiagram,
  diagramComponentsFor,
  diagramSvg,
  findRuns,
  internalForceOverlay,
  isMemberObject,
  runForElement,
  stationAxis
} from "../src/stationDiagram.js";

// Three straight members in a chain, 2 m each, with the six end-force vectors
// Code_Aster's EFGE_ELNO writes: N, VY, VZ, MT, MFY, MFZ.
function chain({ elements = 3, bend = false } = {}) {
  const objects = [];
  const geometryAssets = [];
  for (let index = 0; index < elements; index += 1) {
    const start = [index * 2, 0, 0];
    const end = [(index + 1) * 2, 0, 0];
    // A bend carries sixteen segments, so its n2 end is sixteen stations on.
    const points = bend && index === 1
      ? Array.from({ length: 17 }, (_unused, step) => [2 + step / 8, Math.sin(step / 8) * 0.1, 0])
      : [start, end];
    objects.push({
      id: `object:pipe:${index}`,
      kind: "pipe",
      name: `Member ${index}`,
      geometry_asset_id: `asset:pipe:${index}`,
      metadata: { element_type: "pipe_str", section: "s1", material: "m1", nodes: [`N${index}`, `N${index + 1}`] }
    });
    geometryAssets.push({
      id: `asset:pipe:${index}`,
      format: "tube",
      bounds: [start[0], 0, 0, end[0], 0, 0],
      object_ids: [`object:pipe:${index}`],
      generation_config: { source: "tuba.element", points, radius_m: 0.05 }
    });
  }
  const elementResults = {};
  for (const [index] of objects.entries()) {
    const base = 1000 * (index + 1);
    elementResults[`object:pipe:${index}`] = {
      forces_n1: [base, 0, 0, 0, 50, -20],
      forces_n2: [base, 0, 0, 0, 50, -20],
      max_von_mises: base
    };
  }
  return {
    objects,
    geometryAssets,
    activeResultStateId: "result_state:Hot",
    activeLoadCase: "Hot",
    overlays: [{
      id: "overlay:solver_result:internal_forces:Hot",
      kind: "solver_result",
      data: {
        result_type: "internal_forces",
        result_state_id: "result_state:Hot",
        load_case: "Hot",
        element_results: elementResults
      }
    }]
  };
}

test("a run is a chain of two or more members joined node to node", () => {
  const state = chain({ elements: 3 });
  const runs = findRuns(state);
  assert.equal(runs.length, 1);
  assert.deepEqual(runs[0].elementIds, ["object:pipe:0", "object:pipe:1", "object:pipe:2"]);
  assert.equal(DIAGRAM_MIN_ELEMENTS, 2);
});

test("a single member is not a run, because it cannot show a peak", () => {
  // One pair of ordinates is not a diagram. Offering it would be a plot whose
  // whole purpose - where along the run - it cannot address.
  assert.deepEqual(findRuns(chain({ elements: 1 })), []);
  assert.equal(runForElement(chain({ elements: 1 }), "object:pipe:0"), null);
});

test("two disconnected chains are two runs", () => {
  const state = chain({ elements: 2 });
  const second = chain({ elements: 2 });
  for (const [index, object] of second.objects.entries()) {
    object.id = `object:other:${index}`;
    object.metadata.nodes = [`X${index}`, `X${index + 1}`];
    const asset = second.geometryAssets[index];
    asset.id = `asset:other:${index}`;
    asset.object_ids = [object.id];
    second.overlays[0].data.element_results[object.id] = { forces_n1: [1, 0, 0, 0, 0, 0], forces_n2: [1, 0, 0, 0, 0, 0] };
  }
  const combined = {
    ...state,
    objects: [...state.objects, ...second.objects],
    geometryAssets: [...state.geometryAssets, ...second.geometryAssets],
    overlays: [{ ...state.overlays[0], data: { ...state.overlays[0].data, element_results: { ...state.overlays[0].data.element_results, ...second.overlays[0].data.element_results } } }]
  };
  const runs = findRuns(combined);
  assert.equal(runs.length, 2);
  assert.ok(runs.every((run) => run.elementIds.length === 2));
});

test("an object standing in for something else is not a station member", () => {
  const state = chain({ elements: 2 });
  assert.equal(isMemberObject(state, state.objects[0]), true);
  // A tee wall's display geometry is an idealised joined surface, not a member
  // between two nodes, and plotting it would put a fabricated ordinate on a real
  // station axis.
  assert.equal(isMemberObject(state, { kind: "tee", metadata: { nodes: ["A", "B"], display_geometry: "Joined tee wall" } }), false);
  assert.equal(isMemberObject(state, { kind: "support", metadata: { nodes: ["A", "B"] } }), false);
  assert.equal(isMemberObject(state, { kind: "pipe", metadata: { nodes: ["A"] } }), false);
  assert.equal(isMemberObject(state, { kind: "pipe", metadata: {} }), false);
  assert.equal(isMemberObject(state, null), false);
});

test("stations accumulate along the run and advance within every member", () => {
  const axis = stationAxis(chain({ elements: 3 }), findRuns(chain({ elements: 3 }))[0]);
  assert.equal(axis.stations.length, 6);
  assert.equal(axis.stations[0], 0);
  assert.equal(axis.totalLength, 6);
  // Non-decreasing overall, because a shared node is one station that appears
  // twice - once as the n2 end of one member and once as the n1 end of the next.
  // That is the joint, and it is exactly what a structural diagram draws.
  for (let index = 1; index < axis.stations.length; index += 1) {
    assert.ok(axis.stations[index] >= axis.stations[index - 1], `station ${index} must not go backwards`);
  }
  // Strictly advancing within a member, which is the part that carries the shape.
  for (const elementId of Object.keys(axis.elementStartStations)) {
    assert.ok(
      axis.stations[axis.elementEndStations[elementId]] > axis.stations[axis.elementStartStations[elementId]],
      `${elementId} must occupy a span of the axis`
    );
  }
  assert.deepEqual(axis.stations, [0, 2, 2, 4, 4, 6]);
});

test("a bend contributes its arc, not the chord between its nodes", () => {
  // The sampled centreline is the authority. A 90-degree bend on a 0.3 m radius
  // is 0.47 m of pipe, not 0.42 m, and using the chord would understate every
  // station downstream of the first bend.
  const state = chain({ elements: 3, bend: true });
  const axis = stationAxis(state, findRuns(state)[0]);
  const straight = stationAxis(chain({ elements: 3 }), findRuns(chain({ elements: 3 }))[0]);
  assert.ok(axis.totalLength > straight.totalLength, `${axis.totalLength} should exceed ${straight.totalLength}`);
  // Seventeen points for the bend, so its n2 end is sixteen stations on, not one.
  assert.equal(axis.elementEndStations["object:pipe:1"] - axis.elementStartStations["object:pipe:1"], 16);
  assert.equal(axis.elementEndStations["object:pipe:0"] - axis.elementStartStations["object:pipe:0"], 1);
});

test("the diagram takes one ordinate per element end, in the six-component order", () => {
  const state = chain({ elements: 2 });
  const diagram = buildDiagram(state, findRuns(state)[0], "MFY");
  assert.equal(diagram.points.length, 4);
  assert.deepEqual(diagram.points.map((point) => point.value), [50, 50, 50, 50]);
  // Component 4 of [N, VY, VZ, MT, MFY, MFZ] is MFY, and component 5 is MFZ -
  // picking the wrong index would silently plot the wrong quantity.
  const bending = buildDiagram(state, findRuns(state)[0], "MFZ");
  assert.deepEqual(bending.points.map((point) => point.value), [-20, -20, -20, -20]);
  const axial = buildDiagram(state, findRuns(state)[0], "N");
  assert.deepEqual(axial.points.map((point) => point.value), [1000, 1000, 2000, 2000]);
  assert.equal(diagram.unit, "N·m");
  assert.equal(axial.unit, "N");
});

test("the value extent always spans zero, because every component is signed", () => {
  const state = chain({ elements: 2 });
  const diagram = buildDiagram(state, findRuns(state)[0], "MFZ");
  assert.equal(diagram.extent.value.min, -20);
  assert.equal(diagram.extent.value.max, 0);
  // A diagram that cannot tell a reversal from a rise needs the zero line.
  assert.ok(diagram.extent.value.min <= 0);
});

test("a member missing its far end yields no diagram and offers no component", () => {
  const state = chain({ elements: 2 });
  for (const elementId of Object.keys(state.overlays[0].data.element_results)) {
    state.overlays[0].data.element_results[elementId] = { forces_n1: [1, 2, 3, 4, 5, 6] };
  }
  const run = findRuns(state)[0];
  // Half a diagram that stops where the far end runs out would read as the load
  // vanishing, which is worse than offering nothing.
  assert.equal(buildDiagram(state, run, "MT"), null);
  assert.deepEqual(diagramComponentsFor(state, run), []);
});

test("members with no end forces are counted, not silently dropped", () => {
  const state = chain({ elements: 3 });
  delete state.overlays[0].data.element_results["object:pipe:1"];
  const diagram = buildDiagram(state, findRuns(state)[0], "N");
  assert.equal(diagram.missing, 1);
  // The two members that do have values still plot, and the gap is a real gap
  // in the diagram rather than an interpolation across unknown ground.
  assert.equal(diagram.points.length, 4);
});

test("an unknown component, or a run with no geometry, yields nothing", () => {
  const state = chain({ elements: 2 });
  const run = findRuns(state)[0];
  assert.equal(buildDiagram(state, run, "SIGMA_VON_MISES"), null);
  assert.equal(buildDiagram(state, null, "N"), null);
  const noGeometry = { ...state, geometryAssets: [] };
  assert.equal(buildDiagram(noGeometry, run, "N"), null);
});

test("the internal-force overlay follows the active result and load case", () => {
  const state = chain({ elements: 2 });
  assert.equal(internalForceOverlay(state), state.overlays[0]);
  assert.equal(internalForceOverlay({ ...state, activeResultStateId: "other" }), null);
  assert.equal(internalForceOverlay({ ...state, activeLoadCase: "Cold" }), null);
  assert.equal(internalForceOverlay({ ...state, overlays: [] }), null);
});

test("the diagram is an SVG with a zero line, a station axis and per-ordinate detail", () => {
  const state = chain({ elements: 3 });
  const diagram = buildDiagram(state, findRuns(state)[0], "MFY");
  const svg = diagramSvg(diagram);
  assert.match(svg, /<svg[^>]*class="station-diagram"/);
  assert.match(svg, /role="img"/);
  assert.match(svg, /aria-label="[^"]*MFY[^"]*"/);
  assert.match(svg, /class="diagram-zero"/);
  assert.match(svg, /class="diagram-path"/);
  assert.equal((svg.match(/class="diagram-ordinate"/g) ?? []).length, 6);
  // Each ordinate carries its own element, end, station and value, so the shape
  // of the diagram is readable without hovering.
  assert.match(svg, /object:pipe:0 n1 at 0 m: 50 N·m/);
  assert.match(svg, /Station along run \(m\)/);
  assert.equal(diagramSvg(null), "");
});

test("the SVG escapes the values it puts in an accessible name", () => {
  const state = chain({ elements: 2 });
  state.objects[0].name = 'Member <script>alert("x")</script>';
  state.objects[1].name = "Other";
  const diagram = buildDiagram(state, findRuns(state)[0], "N");
  const svg = diagramSvg(diagram);
  assert.ok(!svg.includes("<script>"));
  assert.match(svg, /&lt;script&gt;/);
});

test("every declared component is offered once end forces exist", () => {
  const state = chain({ elements: 2 });
  const components = diagramComponentsFor(state, findRuns(state)[0]);
  assert.deepEqual(components.map((component) => component.id), DIAGRAM_COMPONENTS.map((component) => component.id));
  assert.deepEqual(components.map((component) => component.unit), ["N", "N", "N", "N·m", "N·m", "N·m"]);
});
