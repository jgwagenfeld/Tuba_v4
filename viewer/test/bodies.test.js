import assert from "node:assert/strict";
import test from "node:test";

import {
  OPACITY_STEPS,
  ambiguousSubpointNodeKeys,
  SUBPOINT_NODE_ANY,
  UNLABELLED_NODE,
  bodyIdForLayerId,
  VECTOR_SCALE_STEPS,
  bodyOpacity,
  bodyOpacityForObjectIds,
  createBodyOpacityState,
  cycleBodyOpacity,
  cycleSubpointMode,
  cycleSubpointNodeId,
  cycleSubpointThreshold,
  cycleVectorScale,
  getBodies,
  getOverlays,
  getDiscretisationCheck,
  getMeshIdentity,
  getSectionProfile,
  getSelectableSubpointNodes,
  getSubpointDrawnCount,
  getSubpointNodes,
  getSubpointPeak,
  getSubpointSelectionPeak,
  getSubpointStations,
  getSubpointStationsForSelection,
  hasSubpointValue,
  setBodyVisibility,
  setOverlayVisibility,
  setSubpointMode,
  setSubpointNodeId,
  subpointMode,
  subpointNodeKey,
  subpointNodeLabel,
  subpointNodeBase,
  subpointNodeId,
  subpointPassesThreshold,
  subpointValueCutoff,
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
  generatrice: { vector: [1, 1, 1], source: "code_aster_gene_tuyau", solved: true }
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
  // Measured mode is the one that shows the bundle's own count, so the point of
  // the line is the bundle's truncation and not the display cut.
  const bodies = getBodies(sceneState({ subpointMode: "measured" }));
  assert.equal(bodies[2].metrics[0], "33 sectors × 7 layers · NSEC 16 · NCOU 3");
  assert.equal(bodies[2].metrics[1], "2 of 5 points drawn");
});

test("the default sub-point body reports its own cut, not the bundle's", () => {
  // Opened without a mode, the field is thinned - so the metric that used to
  // quote the bundle's rendered count now has to quote what the screen shows.
  const bodies = getBodies(sceneState());
  assert.equal(bodies[2].metrics[1], "top 80% · 1 of 5 points drawn");
  assert.equal(bodies[2].metrics[2], "drawn through the wall");
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

test("toggling analysis mesh automatically dims geometry and restores it", () => {
  let state = { ...sceneState(), bodyOpacity: { geometry: 1.0, analysis_mesh: 1 } };
  state = setBodyVisibility(state, "analysis_mesh", true);
  assert.equal(bodyOpacity(state, "geometry"), 0.35);

  state = setBodyVisibility(state, "analysis_mesh", false);
  assert.equal(bodyOpacity(state, "geometry"), 1.0);
});

test("analysis_mesh:helpers is excluded from the analysis_mesh body", () => {
  assert.equal(bodyIdForLayerId("analysis_mesh:helpers"), null);
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

test("deformed peak displacement follows the active solved increment", () => {
  const state = sceneState();
  state.activeResultStateId = "hot";
  state.overlays = ["reference", "hot"].map((id, index) => ({ kind: "solver_result", data: {
    result_type: "displacement", result_state_id: id, values: { N1: [0.003*index,0,0] }
  } }));
  const deformed = getBodies(state).find((body) => body.id === "deformed");
  assert.ok(deformed.metrics.some((text) => text.includes("3 mm")), JSON.stringify(deformed.metrics));
  assert.ok(deformed.metrics.every((text) => !text.includes("0 mm")));
});

// The Overlays band. Every row here was previously reachable only as a leaf of
// the layer tree inside the rail-foot popover.
function overlayState(overrides = {}) {
  return {
    layers: {
      support: { id: "support", category: "design", count: 6, visible: true, objectIds: [], source: "object" },
      "design:loads:forces": { id: "design:loads:forces", category: "design", count: 4, visible: true, objectIds: [], source: "object" },
      "design:loads:moments": { id: "design:loads:moments", category: "design", count: 2, visible: true, objectIds: [], source: "object" },
      "design:loads:line_loads": { id: "design:loads:line_loads", category: "design", count: 3, visible: true, objectIds: [], source: "object" },
      "result:reaction_force": {
        id: "result:reaction_force",
        category: "results",
        count: 6,
        visible: true,
        objectIds: [],
        source: "object"
      },
      "result:reaction_moment": {
        id: "result:reaction_moment",
        category: "results",
        count: 6,
        visible: false,
        objectIds: [],
        source: "object"
      },
      // Declared but populated by nothing: an absent overlay, not an empty one.
      "result:displacement": {
        id: "result:displacement",
        category: "results",
        count: 0,
        visible: true,
        source: "scene"
      }
    },
    // setLayerVisibility reprojects both of these; a loaded state always
    // carries them.
    objects: [],
    overlays: [],
    resultVectorScales: { displacement: 1, reaction: 2, moment: 1 },
    ...overrides
  };
}

test("getOverlays lists the marks the scene actually draws, in spec order", () => {
  const overlays = getOverlays(overlayState());
  assert.deepEqual(
    overlays.map((overlay) => overlay.id),
    ["support", "applied_force", "applied_moment", "applied_line_load", "reaction_force", "reaction_moment", "ground_grid"]
  );
  // Displacement is declared but gates nothing, so it is omitted rather than
  // rendered as a row that toggles an empty layer.
  assert.equal(overlays.some((overlay) => overlay.id === "displacement"), false);
});

test("getOverlays reports count, visibility and the scale its vectors are drawn at", () => {
  const overlays = getOverlays(overlayState());
  const reaction = overlays.find((overlay) => overlay.id === "reaction_force");
  assert.equal(reaction.count, 6);
  assert.equal(reaction.visible, true);
  assert.equal(reaction.scale, 2);

  const moment = overlays.find((overlay) => overlay.id === "reaction_moment");
  assert.equal(moment.visible, false);
  assert.equal(moment.scale, 1);

  // Supports are not a vector family, so they carry no scale.
  assert.equal(overlays.find((overlay) => overlay.id === "support").scale, null);
});

test("setOverlayVisibility drives the layers behind the row", () => {
  const state = overlayState();
  const hidden = setOverlayVisibility(state, "reaction_force", false);
  assert.equal(hidden.layers["result:reaction_force"].visible, false);
  assert.equal(hidden.layers["result:reaction_moment"].visible, false, "unrelated layers stay put");
  assert.equal(getOverlays(hidden).find((overlay) => overlay.id === "reaction_force").visible, false);

  // An overlay the scene does not draw cannot be toggled into existence.
  assert.equal(setOverlayVisibility(state, "displacement", false), state);
});

// The renderer draws the grid from the model bounds, so no layer gates it and
// the row cannot be layer-driven like the others. It is still a mark on screen
// the reviewer wants off.
test("the ground grid is offered whatever the scene carries, and answers to its own flag", () => {
  const bare = { layers: {}, objects: [], overlays: [], resultVectorScales: {} };
  const grid = getOverlays(bare).find((overlay) => overlay.id === "ground_grid");
  assert.ok(grid, "offered even by a scene with no layers at all");
  assert.equal(grid.visible, true, "drawn until it is turned off");
  // No layer behind it means nothing to count, and a badge reading 0 would be a
  // lie rather than a blank.
  assert.equal(grid.count, null);
  assert.equal(grid.scale, null);

  const off = setOverlayVisibility(bare, "ground_grid", false);
  assert.equal(off.referenceGridVisible, false);
  assert.equal(getOverlays(off).find((overlay) => overlay.id === "ground_grid").visible, false);
  assert.deepEqual(off.layers, {}, "toggling chrome touches no layer");
});

test("attachment links appear as their own row only when the scene draws them", () => {
  assert.equal(getOverlays(overlayState()).some((overlay) => overlay.id === "support_link"), false);
  const state = overlayState();
  state.layers.support_link = { id: "support_link", category: "design", count: 2, visible: true, objectIds: [], source: "object" };
  const link = getOverlays(state).find((overlay) => overlay.id === "support_link");
  assert.ok(link, "offered when the scene carries attachment links");
  assert.equal(link.count, 2);
  assert.equal(link.scale, null);
  const hidden = setOverlayVisibility(state, "support_link", false);
  assert.equal(hidden.layers.support_link.visible, false);
  assert.equal(hidden.layers.support.visible, true, "toggling links leaves glyphs put");
});

test("cycleVectorScale walks the steps and wraps", () => {
  assert.deepEqual(VECTOR_SCALE_STEPS.map((step) => cycleVectorScale(step)), [1, 2, 5, 0.5]);
  // A scale set by the slider that is not one of the steps starts the cycle
  // over rather than sticking.
  assert.equal(cycleVectorScale(1.75), VECTOR_SCALE_STEPS[0]);
});

// --- how the sub-point field is drawn ---------------------------------------

test("the sub-point field opens in peak mode, and the mode cycles both ways", () => {
  const state = sceneState();
  assert.equal(subpointMode(state), "peak");

  const measured = cycleSubpointMode(state);
  assert.equal(subpointMode(measured), "measured");
  assert.equal(subpointMode(cycleSubpointMode(measured)), "peak", "wraps back to the first mode");
  assert.equal(subpointMode(setSubpointMode(state, "nonsense")), "peak", "an unknown mode is refused");
  assert.equal(setSubpointMode(state, "peak"), state, "setting the mode already on changes nothing");
});

test("measured mode thins nothing, so it has no cutoff and quotes the scene's own count", () => {
  const state = sceneState({ subpointMode: "measured" });
  assert.equal(subpointValueCutoff(state), null);
  assert.equal(getSubpointDrawnCount(state), null);
  const body = getBodies(state).find((candidate) => candidate.id === "subpoints");
  // The bundle reported 2 rendered of 5 total; that is what measured mode shows.
  assert.ok(body.metrics.some((metric) => metric.includes("2 of 5 points drawn")));
  assert.ok(!body.metrics.some((metric) => metric.includes("drawn through the wall")));
});

test("peak mode quotes the cut it drew, and says the marks are through the wall", () => {
  // The fixture's two values are 4.2e7 and 2.015e8 against a 2.015e8 range top.
  const state = sceneState({ subpointMode: "peak", subpointThreshold: 0.8 });
  assert.equal(subpointValueCutoff(state), 2.015e8 * 0.8);
  assert.equal(getSubpointDrawnCount(state), 1);

  const metrics = getBodies(state).find((candidate) => candidate.id === "subpoints").metrics;
  assert.ok(metrics.some((metric) => metric.includes("top 80%")));
  assert.ok(metrics.some((metric) => metric.includes("1 of 5 points drawn")));
  assert.ok(metrics.some((metric) => metric === "drawn through the wall"));
});

test("a looser peak cut admits more of the same field", () => {
  const drawn = (threshold) => getSubpointDrawnCount(sceneState({ subpointMode: "peak", subpointThreshold: threshold }));
  assert.equal(drawn(0.9), 1);
  assert.equal(drawn(0.5), 1, "4.2e7 is still under half of 2.015e8");
  assert.equal(drawn(0.1), 2);
});

test("the peak threshold cycles up the steps and wraps", () => {
  let state = sceneState({ subpointThreshold: 0.5 });
  state = cycleSubpointThreshold(state);
  assert.equal(state.subpointThreshold, 0.65);
  state = cycleSubpointThreshold(state);
  assert.equal(state.subpointThreshold, 0.8);
  assert.equal(cycleSubpointThreshold({ subpointThreshold: 0.95 }).subpointThreshold, 0.5, "wraps");
  // A cut typed in from outside the steps climbs to the next one above it rather
  // than jumping somewhere arbitrary.
  assert.equal(cycleSubpointThreshold({ subpointThreshold: 0.7 }).subpointThreshold, 0.8);
});

test("a sub-point with no value is never read as a low one", () => {
  assert.equal(hasSubpointValue(0), true, "zero is a value");
  assert.equal(hasSubpointValue(null), false);
  assert.equal(hasSubpointValue(undefined), false);
  assert.equal(hasSubpointValue(""), false);
  assert.equal(hasSubpointValue("n/a"), false);

  // Number(null) is 0, so an absent value read naively is the coldest mark on
  // the ramp and the first a threshold throws away. It is missing, not low.
  assert.equal(subpointPassesThreshold(null, 1e8), true);
  assert.equal(subpointPassesThreshold(undefined, 1e8), true);
  assert.equal(subpointPassesThreshold(4.2e7, 1e8), false);
  assert.equal(subpointPassesThreshold(1.2e8, 1e8), true);
  assert.equal(subpointPassesThreshold(4.2e7, null), true, "no cutoff draws everything");
});

test("the drawn count reads the payload file, where a real bundle keeps its values", () => {
  // The scene entry carries only a pointer, exactly as `write_scene_bundle`
  // writes it, so counting off the manifest alone would find nothing.
  const state = sceneState({ subpointMode: "peak", subpointThreshold: 0.1 });
  assert.equal(state.geometryAssets[0].generation_config.values, undefined);
  assert.equal(getSubpointDrawnCount(state), 2);
});

test("an unknown peak cut draws everything rather than nothing", () => {
  // No legend and no range anywhere: there is no cutoff to apply, so nothing is
  // hidden behind a threshold the scene never stated.
  const state = sceneState({ subpointMode: "peak", subpointThreshold: 0.8 });
  delete state.overlays[0].data.section_profile;
  state.geometryPayloads[0].generation_config = { sector_indices: [2], layer_indices: [0], values: [4.2e7] };
  const bare = { ...state, overlays: state.overlays.filter((overlay) => overlay.data?.result_type !== "tuyau_subpoints") };
  assert.equal(subpointValueCutoff(bare), null);
});

// --- choosing which node's section the wall panel shows --------------------

// Two nodes, two elements, four stations. N1 sits on the outer wall and is cold;
// N2 sits on the bore and is hot. The envelope, N1 and N2 are three different
// pictures, which is the whole reason the choice exists.
function nodeFieldState(overrides = {}) {
  const state = sceneState();
  state.geometryAssets[0].generation_config = {
    source: "tuba.tuyau_subpoint_field",
    payload_uri: "geometry/subpoints.json"
  };
  state.geometryPayloads[0].generation_config = {
    sector_indices: [0, 4, 0, 4],
    layer_indices: [6, 6, 0, 0],
    node_ids: ["N1", "N1", "N2", "N2"],
    element_ids: ["E-1", "E-1", "E-2", "E-2"],
    values: [10e6, 30e6, 250e6, 12e6]
  };
  state.overlays[0].data.rendered_count = 4;
  state.overlays[0].data.total_count = 4;
  return { ...state, ...overrides };
}

test("the wall panel opens on the envelope, which is what it showed before the choice", () => {
  assert.equal(subpointNodeId(nodeFieldState()), SUBPOINT_NODE_ANY);
  const stations = getSubpointStationsForSelection(nodeFieldState());
  assert.equal(stations.length, 4, "every station, from every node");
});

test("pinning the panel to a node narrows the grid to that node's section", () => {
  const state = setSubpointNodeId(nodeFieldState(), "E-2::N2");
  const stations = getSubpointStationsForSelection(state);
  assert.equal(stations.length, 2);
  assert.deepEqual(
    stations.map((station) => `${station.sectorIndex}:${station.layerIndex}`),
    ["0:0", "4:0"],
    "both of N2's stations are on the bore"
  );
  // N2 is hot on the bore and N1 is cold on the OD, so the envelope's worst
  // station and N2's worst station are the same number by coincidence of this
  // fixture - what differs is everything else the two grids show.
  assert.equal(getSubpointSelectionPeak(state).value, 250e6);
  // N1's peak is 30 MPa, and pinning to N1 must not still claim 250.
  assert.equal(getSubpointSelectionPeak(setSubpointNodeId(nodeFieldState(), "E-1::N1")).value, 30e6);
});


test("the headline peak follows the selection rather than the study", () => {
  // The un-pinned peak is the study's worst station, from the overlay.
  assert.equal(getSubpointPeak(nodeFieldState()).value, 2.015e8);
  assert.equal(getSubpointSelectionPeak(nodeFieldState()).value, 250e6);
  // A pinned panel describes one node, so a headline that stayed at the study
  // peak would be a number beside a section it did not come from.
  assert.equal(getSubpointSelectionPeak(setSubpointNodeId(nodeFieldState(), "E-1::N1")).value, 30e6);
});

test("the node list is ranked by each section's own peak, worst first", () => {
  const nodes = getSubpointNodes(nodeFieldState());
  assert.deepEqual(nodes.map((node) => node.key), ["E-2::N2", "E-1::N1"]);
  assert.equal(nodes[0].max, 250e6);
  assert.equal(nodes[0].count, 2);
  assert.equal(nodes[1].max, 30e6);
});

// A junction is one node shared by every element meeting there, so a node label
// is not a key. On the shipped review 34 of 71 labels carry 462 rows rather than
// 231 - "N1" is both pipe_bend_0's and pipe_str_0's - and grouping on the node
// alone silently merged two elements into one "section".
test("a node shared by two elements is two sections, not one", () => {
  const state = nodeFieldState();
  state.geometryPayloads[0].generation_config = {
    // N1 on both E-1 and E-2, each with its own 231 stations at its own stress.
    sector_indices: [0, 0, 0, 0],
    layer_indices: [0, 0, 0, 0],
    node_ids: ["N1", "N1", "N1", "N1"],
    element_ids: ["E-1", "E-1", "E-2", "E-2"],
    values: [10e6, 20e6, 300e6, 400e6]
  };
  const nodes = getSubpointNodes(state);
  assert.equal(nodes.length, 2, "one section per element, not one per node label");
  assert.deepEqual(nodes.map((node) => node.key), ["E-2::N1", "E-1::N1"]);
  // Pinned to the bend, the panel must not report the straight's 400 MPa.
  assert.equal(getSubpointSelectionPeak(setSubpointNodeId(state, "E-1::N1")).value, 20e6);
  assert.equal(getSubpointSelectionPeak(setSubpointNodeId(state, "E-2::N1")).value, 400e6);
  // And a bare node label matches nothing, rather than quietly matching both.
  assert.equal(getSubpointStationsForSelection(setSubpointNodeId(state, "N1")).length, 0);
});

// A bend is meshed into segments that share their end nodes, and stress is
// recovered per element, so one junction carries one stress per segment. On the
// shipped review pipe_bend_0_n1 is reported at the same coordinates by
// pipe_bend_0_s0 and pipe_bend_0_s1, with different values. Those are not
// duplicate rows and not a labelling fault - but keyed on the authored element
// and the node they merge into one section, reporting the per-station maximum of
// both as a single picture.
test("one junction on two segments is two sections, not one", () => {
  const state = nodeFieldState();
  state.geometryPayloads[0].generation_config = {
    sector_indices: [0, 0, 0, 0],
    layer_indices: [0, 0, 0, 0],
    node_ids: ["n1", "n1", "n1", "n1"],
    // The authored element is the same for both; only the segment differs.
    element_ids: ["bend", "bend", "bend", "bend"],
    analysis_element_ids: ["bend_s0", "bend_s0", "bend_s1", "bend_s1"],
    values: [100e6, 200e6, 300e6, 400e6]
  };
  const nodes = getSubpointNodes(state);
  assert.deepEqual(nodes.map((node) => node.key), ["bend_s1::n1", "bend_s0::n1"]);
  assert.equal(getSubpointSelectionPeak(setSubpointNodeId(state, "bend_s0::n1")).value, 200e6);
  assert.equal(getSubpointSelectionPeak(setSubpointNodeId(state, "bend_s1::n1")).value, 400e6);
  // Both are named, and the segment is what tells them apart - the authored
  // element and node are the same for the two.
  const bases = subpointNodeBase(state);
  const ambiguous = ambiguousSubpointNodeKeys(state);
  assert.deepEqual([...ambiguous], ["bend::n1"]);
  assert.equal(subpointNodeLabel("bend_s0::n1", { bases, ambiguous }), "n1 · bend · s0");
  assert.equal(subpointNodeLabel("bend_s1::n1", { bases, ambiguous }), "n1 · bend · s1");
});

test("a segment is not named when the junction is not shared", () => {
  // The segment is a mesh artefact. Where only one segment reports a junction,
  // showing "s0" would be noise in a list of 105.
  const state = nodeFieldState();
  state.geometryPayloads[0].generation_config = {
    sector_indices: [0, 4],
    layer_indices: [0, 0],
    node_ids: ["n1", "n2"],
    element_ids: ["bend", "bend"],
    analysis_element_ids: ["bend_s0", "bend_s0"],
    values: [10e6, 20e6]
  };
  const bases = subpointNodeBase(state);
  const ambiguous = ambiguousSubpointNodeKeys(state);
  assert.equal(ambiguous.size, 0);
  assert.equal(subpointNodeLabel("bend_s0::n1", { bases, ambiguous }), "n1 · bend");
});

test("a section key is labelled with its node and its element", () => {
  assert.equal(subpointNodeLabel("E-2::N2"), "N2 · E-2");
  assert.equal(subpointNodeLabel(subpointNodeKey("E-2", null)), "E-2 · (no node)");
  assert.equal(subpointNodeLabel(subpointNodeKey(undefined, "N3")), "N3");
});


test("rows that lost their node group under one bucket rather than vanishing", () => {
  // A row that came back without a node is how a label-mapping gap shows up.
  // Dropping it would quietly shrink the very field the panel reports a count of.
  const state = nodeFieldState();
  state.geometryPayloads[0].generation_config.node_ids = ["N1", "N1", null, null];
  const nodes = getSubpointNodes(state);
  assert.deepEqual(nodes.map((node) => node.key), ["E-2::(no node)", "E-1::N1"], "worst first");
  assert.equal(nodes[0].max, 250e6);
  // And the unlabelled group is inspectable, so its section is reachable.
  const pinned = getSubpointStationsForSelection(setSubpointNodeId(state, subpointNodeKey("E-2", null)));
  assert.equal(pinned.length, 2);
});


test("a bundle written before the rows carried a node still draws a grid", () => {
  // The scene fixture without node_ids is exactly this case: the rosette falls
  // back to the envelope rather than going blank, so an old review still reads.
  // Every row lands in the unlabelled bucket - reported, because that is the
  // truth about the rows - but nothing is selectable, because "worst anywhere"
  // and "(no node)" would be the same picture under two names.
  const nodes = getSubpointNodes(sceneState());
  assert.equal(nodes.length, 1);
  assert.equal(nodes[0].key, subpointNodeKey(undefined, undefined), "no element and no node label");
  assert.equal(getSelectableSubpointNodes(sceneState()).length, 0, "so no selector is offered");
  assert.equal(getSubpointStationsForSelection(sceneState()).length, 2);
  // Pinning something the bundle cannot answer leaves the envelope rather than
  // showing an empty section.
  assert.equal(getSubpointStationsForSelection(setSubpointNodeId(sceneState(), "E-9::N9")).length, 2);
});

test("cycling the section walks the envelope, then worst-first, and round", () => {
  let state = nodeFieldState();
  state = cycleSubpointNodeId(state);
  assert.equal(subpointNodeId(state), "E-2::N2", "the worst section comes first after the envelope");
  state = cycleSubpointNodeId(state);
  assert.equal(subpointNodeId(state), "E-1::N1");
  assert.equal(subpointNodeId(cycleSubpointNodeId(state)), SUBPOINT_NODE_ANY, "wraps");
  // Nothing selectable, so nothing to cycle through.
  const legacy = sceneState();
  assert.equal(cycleSubpointNodeId(legacy), legacy);
});

test("setting the section already shown changes nothing", () => {
  const state = nodeFieldState();
  assert.equal(setSubpointNodeId(state, SUBPOINT_NODE_ANY), state);
  const pinned = setSubpointNodeId(state, "E-2::N2");
  assert.equal(setSubpointNodeId(pinned, "E-2::N2"), pinned);
});

test("the body row says which section the panel is showing", () => {
  const metrics = (state) => getBodies(state).find((body) => body.id === "subpoints").metrics;
  assert.ok(metrics(nodeFieldState({ subpointMode: "measured" })).includes("wall panel: worst station across the run"));
  assert.ok(metrics(nodeFieldState({ subpointMode: "measured", subpointNodeId: "E-2::N2" })).includes("wall panel: N2 · E-2"));
  assert.ok(
    metrics(nodeFieldState({ subpointMode: "measured", subpointNodeId: "E-9::N9" })).includes("wall panel: N9 · E-9 has no sub-points"),
    "pinned to a section with no rows, it must not claim to be the run-wide worst"
  );
});

