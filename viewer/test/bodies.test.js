import assert from "node:assert/strict";
import test from "node:test";

import {
  OPACITY_STEPS,
  bodyIdForLayerId,
  bodyOpacity,
  bodyOpacityForObjectIds,
  createBodyOpacityState,
  cycleBodyOpacity,
  getBodies,
  getDiscretisationCheck,
  getMeshIdentity,
  getSectionProfile,
  getSubpointPeak,
  getSubpointStations,
  setBodyVisibility,
  withDefaultBodyOpacity
} from "../src/bodies.js";

const MESH_IDENTITY = {
  mesh_id: "analysis_mesh:Hot",
  solver: "Code_Aster",
  modelisations: [{ modelisation: "TUYAU_3M", element_count: 11, topological_dim: 1, result_support: "subpoint" }],
  topological_dim: 1,
  node_count: 23,
  element_count: 11,
  element_families: [{ family: "SEG3", element_count: 11 }],
  discretisation: {
    check: "bend_chord_deviation",
    unit: "m",
    bend_count: 2,
    min_elements_per_bend: 2,
    max_chord_deviation: 0.0041,
    tolerance_ratio: 0.01,
    within_tolerance: true,
    worst_bend: { source_element_id: "B1", element_count: 2 }
  }
};

const SECTION_PROFILE = {
  nsec: 16,
  ncou: 3,
  sectors: 33,
  layers: 7,
  subpoints_per_node: 231,
  display_generatrice: [0, 0, 1]
};

function sceneState(overrides = {}) {
  const layers = {
    pipe: { id: "pipe", category: "design", count: 2, visible: true, objectIds: ["o:pipe", "o:result_state"], source: "object" },
    support: { id: "support", category: "design", count: 1, visible: true, objectIds: ["o:support"], source: "object" },
    "analysis_mesh:elements": {
      id: "analysis_mesh:elements",
      category: "analysis_mesh",
      count: 11,
      visible: true,
      objectIds: ["o:mesh"],
      source: "object"
    },
    "analysis_mesh:identity:m1": {
      id: "analysis_mesh:identity:m1",
      category: "analysis_mesh",
      count: 0,
      visible: false,
      source: "scene",
      meshIdentity: MESH_IDENTITY
    },
    "solver_result:tuyau_subpoints": {
      id: "solver_result:tuyau_subpoints",
      category: "results",
      count: 1,
      visible: true,
      objectIds: ["o:subpoints"],
      source: "object"
    },
    "deformed:visual_centerline": {
      id: "deformed:visual_centerline",
      category: "results",
      count: 3,
      visible: false,
      objectIds: ["o:deformed"],
      source: "object"
    },
    "result:reaction": { id: "result:reaction", category: "results", count: 1, visible: true, objectIds: ["o:reaction"], source: "object" },
    "issues:clash": { id: "issues:clash", category: "annotations", count: 1, visible: true, objectIds: ["o:clash"], source: "object" }
  };
  return {
    layers,
    objects: [
      {
        id: "o:pipe",
        kind: "pipe",
        geometry_asset_id: "geometry:pipe",
        metadata: { profile: { outer_diameter_m: 0.1143, wall_thickness_m: 0.00602 } }
      },
      { id: "o:support", kind: "support", geometry_asset_id: "geometry:support", metadata: {} },
      // A metadata record with no geometry: drawn by nothing, so tallied by nothing.
      { id: "o:result_state", kind: "result_state", metadata: {} }
    ],
    objectLayerIds: {
      "o:pipe": ["pipe"],
      "o:support": ["support"],
      "o:result_state": ["pipe"],
      "o:mesh": ["analysis_mesh:elements"],
      "o:subpoints": ["solver_result:tuyau_subpoints"],
      "o:deformed": ["deformed:visual_centerline"],
      "o:reaction": ["result:reaction"]
    },
    // The scene entry keeps a pointer; the stations live in the payload file.
    geometryAssets: [
      {
        id: "geometry:subpoints",
        object_ids: ["o:subpoints"],
        uri: "geometry/subpoints.json",
        generation_config: { source: "tuba.tuyau_subpoint_field", payload_uri: "geometry/subpoints.json" }
      }
    ],
    geometryPayloads: [
      {
        asset_id: "geometry:subpoints",
        generation_config: { sector_indices: [2, 8], layer_indices: [0, 6], values: [4.2e7, 2.015e8] }
      }
    ],
    overlays: [
      {
        id: "overlay:solver_result:tuyau_subpoints:Hot",
        object_ids: ["o:subpoints"],
        data: {
          result_type: "tuyau_subpoints",
          section_profile: SECTION_PROFILE,
          rendered_count: 2,
          total_count: 5,
          peak: { value: 2.015e8, unit: "Pa", element_id: "E-104", angle_deg: 90, wall_position: "outer" }
        }
      },
      { id: "overlay:solver_result:displacement:Hot", data: { result_type: "displacement", values: { N14: 0.0426, N2: 0.01 } } }
    ],
    geometryStates: [
      { id: "overlay:geometry_state:visual", data: { id: "gs:visual", state_type: "deformed", visual_scale: 50 } }
    ],
    activeGeometryStateId: "gs:visual",
    visualDeformationScale: 50,
    ...overrides
  };
}

test("layer ids claim the body that draws them", () => {
  assert.equal(bodyIdForLayerId("pipe", "design"), "geometry");
  assert.equal(bodyIdForLayerId("cold_geometry"), "geometry");
  assert.equal(bodyIdForLayerId("analysis_mesh:elements", "analysis_mesh"), "analysis_mesh");
  assert.equal(bodyIdForLayerId("solver_result:tuyau_subpoints", "results"), "subpoints");
  assert.equal(bodyIdForLayerId("deformed:visual_centerline", "results"), "deformed");
});

test("results that are not one of the composited bodies claim none", () => {
  // Vectors and annotations are drawn, but they belong to the layer tree rather
  // than the bodies panel.
  assert.equal(bodyIdForLayerId("result:reaction", "results"), null);
  assert.equal(bodyIdForLayerId("issues:clash", "annotations"), null);
  assert.equal(bodyIdForLayerId("overlay:clash", "annotations"), null);
});

test("getBodies reports the four bodies in composite order with their layers", () => {
  const bodies = getBodies(sceneState());
  assert.deepEqual(
    bodies.map((body) => body.id),
    ["geometry", "analysis_mesh", "subpoints", "deformed"]
  );
  assert.deepEqual(bodies[0].layerIds.sort(), ["pipe", "support"]);
  assert.equal(bodies[3].visible, false);
});

test("a body the scene does not populate is omitted, not shown empty", () => {
  const state = sceneState({
    layers: { pipe: { id: "pipe", category: "design", count: 1, visible: true, objectIds: ["o:pipe"], source: "object" } }
  });
  assert.deepEqual(
    getBodies(state).map((body) => body.id),
    ["geometry"]
  );
});

test("the mesh identity badge describes the mesh without making it look drawn", () => {
  const state = sceneState({
    layers: {
      "analysis_mesh:identity:m1": {
        id: "analysis_mesh:identity:m1",
        category: "analysis_mesh",
        count: 0,
        visible: false,
        source: "scene",
        meshIdentity: MESH_IDENTITY
      }
    }
  });
  assert.deepEqual(getBodies(state), []);
  assert.equal(getMeshIdentity(state).node_count, 23);
});

test("badges come from the scene, not from the body name", () => {
  const bodies = getBodies(sceneState());
  assert.deepEqual(bodies[1].badge, { text: "1D", tone: "accent" });
  assert.deepEqual(bodies[2].badge, { text: "2.5D", tone: "accent" });
  assert.equal(bodies[3].badge.text, "DEFORMED");
});

test("mesh metrics name the element family the connectivity actually has", () => {
  const bodies = getBodies(sceneState());
  assert.deepEqual(bodies[1].metrics, ["11 SEG3 · 23 nodes · TUYAU_3M"]);
});

test("geometry metrics report the tally and the section it was authored with", () => {
  const [geometry] = getBodies(sceneState());
  // o:result_state sits in the same layer but carries no geometry, so it is not
  // tallied as authored content.
  assert.equal(geometry.metrics[0], "1 pipe · 1 support");
  // A tenth of a millimetre matters here: 114.3 is DN100, 114 is nothing.
  assert.equal(geometry.metrics[1], "OD 114.3 · WT 6.02 mm");
});

test("a truncated sub-point field says so rather than reading as full coverage", () => {
  const bodies = getBodies(sceneState());
  assert.equal(bodies[2].metrics[0], "33 sectors × 7 layers · NSEC 16 · NCOU 3");
  assert.equal(bodies[2].metrics[1], "2 of 5 points drawn");
});

test("deformed metrics report the peak and flag the display scale", () => {
  const bodies = getBodies(sceneState());
  assert.equal(bodies[3].metrics[0], "max |D| 42.6 mm at N14");
  assert.equal(bodies[3].metrics[1], "drawn at ×50 (display only)");
});

test("the deformed body reports the scale it is drawn at, not the bundle's", () => {
  // The deform slider overrides the state's own visual_scale; a body claiming
  // x50 while the bar reads x1 is a mismatch a screenshot carries away.
  const bodies = getBodies({ ...sceneState(), visualDeformationScale: 1 });
  assert.equal(bodies[3].metrics.length, 1);
  assert.equal(bodies[3].metrics[0], "max |D| 42.6 mm at N14");
});

test("toggling a body fans out to every layer that draws it", () => {
  let state = sceneState();
  state = setBodyVisibility(state, "geometry", false);
  assert.equal(state.layers.pipe.visible, false);
  assert.equal(state.layers.support.visible, false);
  assert.equal(state.layers["analysis_mesh:elements"].visible, true);
  assert.equal(getBodies(state)[0].visible, false);
});

test("a partly hidden body reads as indeterminate rather than on or off", () => {
  let state = sceneState();
  state = { ...state, layers: { ...state.layers, pipe: { ...state.layers.pipe, visible: false } } };
  const [geometry] = getBodies(state);
  assert.equal(geometry.visible, false);
  assert.equal(geometry.partiallyVisible, true);
});

test("opacity cycles through the declared steps and wraps", () => {
  let state = withDefaultBodyOpacity(sceneState());
  state = { ...state, bodyOpacity: { ...state.bodyOpacity, subpoints: 1 } };
  for (const expected of [...OPACITY_STEPS.slice(1), OPACITY_STEPS[0]]) {
    state = cycleBodyOpacity(state, "subpoints");
    assert.equal(bodyOpacity(state, "subpoints"), expected);
  }
});

test("geometry starts dimmed only when there is something underneath to see", () => {
  assert.equal(createBodyOpacityState(sceneState()).geometry, 0.6);
  const designOnly = sceneState({
    layers: { pipe: { id: "pipe", category: "design", count: 4, visible: true, objectIds: ["o:pipe"], source: "object" } }
  });
  assert.equal(createBodyOpacityState(designOnly).geometry, 1);
});

test("withDefaultBodyOpacity seeds once and never overwrites a choice", () => {
  const chosen = { ...sceneState(), bodyOpacity: { geometry: 0.3 } };
  assert.equal(withDefaultBodyOpacity(chosen).bodyOpacity.geometry, 0.3);
});

test("the renderer resolves an asset to the opacity of the body that owns it", () => {
  const state = { ...sceneState(), bodyOpacity: { geometry: 0.6, analysis_mesh: 1, subpoints: 0.3 } };
  assert.equal(bodyOpacityForObjectIds(state, ["o:pipe"]), 0.6);
  assert.equal(bodyOpacityForObjectIds(state, ["o:subpoints"]), 0.3);
  // Deformed carries no opacity of its own, and neither do vectors.
  assert.equal(bodyOpacityForObjectIds(state, ["o:deformed"]), null);
  assert.equal(bodyOpacityForObjectIds(state, ["o:reaction"]), null);
  assert.equal(bodyOpacityForObjectIds(state, []), null);
});

test("the section grid and the bend check come from the scene", () => {
  const state = sceneState();
  assert.equal(getSectionProfile(state).subpoints_per_node, 231);
  assert.equal(getDiscretisationCheck(state).max_chord_deviation, 0.0041);
  assert.equal(getSubpointPeak(state).location, "E-104 · 90° · outer");
  assert.deepEqual(getSubpointStations(state), [
    { sectorIndex: 2, layerIndex: 0, value: 4.2e7 },
    { sectorIndex: 8, layerIndex: 6, value: 2.015e8 }
  ]);
});

test("a bundle without the check reports none rather than a vacuous pass", () => {
  const { discretisation, ...withoutCheck } = MESH_IDENTITY;
  const state = sceneState({
    layers: {
      "analysis_mesh:elements": {
        id: "analysis_mesh:elements",
        category: "analysis_mesh",
        count: 11,
        visible: true,
        objectIds: ["o:mesh"],
        source: "object",
        meshIdentity: withoutCheck
      }
    },
    overlays: [],
    geometryPayloads: []
  });
  assert.equal(getDiscretisationCheck(state), null);
  assert.equal(getSectionProfile(state), null);
  assert.equal(getSubpointPeak(state), null);
  assert.deepEqual(getSubpointStations(state), []);
});

test("a legacy bundle with no declared categories still resolves its bodies", () => {
  const state = {
    layers: {
      cold_geometry: { id: "cold_geometry", count: 2, visible: true, objectIds: [], source: "object" },
      "deformed:visual_centerline": { id: "deformed:visual_centerline", count: 1, visible: true, objectIds: [], source: "object" }
    },
    objects: [],
    objectLayerIds: {},
    overlays: [],
    geometryAssets: []
  };
  assert.deepEqual(
    getBodies(state).map((body) => body.id),
    ["geometry", "deformed"]
  );
});
