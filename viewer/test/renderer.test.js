import assert from "node:assert/strict";
import test from "node:test";
import { Box3, BoxGeometry, Color, DoubleSide, Group, Line, LineBasicMaterial, Mesh, MeshBasicMaterial, OrthographicCamera, PerspectiveCamera, Sprite, Vector3 } from "three";

import * as rendererModule from "../src/renderer.js";
import { colorForScalarValue, getScalarLegend } from "../src/resultReview.js";
import { SUPPORT_BUILD_COLORS, SUPPORT_GROUND_COLOR, SUPPORT_REVIEW_COLORS } from "../src/supportGlyphs.js";
import { applySectionBox } from "../src/controls.js";
import { createViewerState, setLayerVisibility } from "../src/sceneLoader.js";

test("mesh diagnostics preserve requested-size colours and exact x-ray bounds", () => {
  const asset = { id: "geometry:mesh_problem", format: "aabb", bounds: [0,0,0,.1,.1,.1], object_ids: ["object:mesh_problem"],
    generation_config: { source: "tuba.analysis_mesh.review", color: "#dc2626", opacity: .25 } };
  const state = { objects: [{ id: "object:mesh_problem", kind: "mesh_problem" }], geometryAssets: [asset], visibleObjectIds: ["object:mesh_problem"] };
  assert.equal(prepareAssetRenderConfig(asset, {}, state).color, "#dc2626");
  const graph = createThreeSceneGraph(state);
  const rendered = graph.objectsByObjectId.get("object:mesh_problem");
  assert.ok(rendered);
  rendered.traverse(part => { if (part.material) assert.equal(part.material.depthTest, false); });
  applySelectionHighlight(graph, ["object:mesh_problem"]);
  assert.equal(rendered.material.color.getHexString(), "dc2626", "selection keeps the requested colour");
  disposeThreeSceneGraph(graph);
});
// In Review (the default stage) support glyphs are achromatic: hue belongs to
// the results, where it says authored-input vs Code_Aster-result. The tests
// below assert that rule through this one constant rather than a literal per part.
const SUPPORT_NEUTRAL = Number.parseInt(SUPPORT_REVIEW_COLORS.restraint.slice(1), 16);

import {
  SUPPORTED_RENDER_FORMATS,
  applyVisualDeformationScale,
  applyHoverHighlight,
  applySelectionHighlight,
  applySupportStage,
  createThreeSceneGraph,
  disposeThreeSceneGraph,
  fitCameraToBounds,
  resizeCameraViewport,
  setCameraToStandardView,
  zoomCameraBy,
  STANDARD_VIEW_DIRECTIONS,
  pickRenderedObject,
  pickRenderedPoint,
  prepareAssetRenderConfig,
  sectionBoxClippingPlanes,
  applySectionBoxClipping,
  applyValueLabelVisibility,
  scaleValueLabels,
  updateSceneGraphBounds
} from "../src/renderer.js";

function fixtureState() {
  const geometryAssets = [
    {
      id: "geometry:pipe",
      format: "tube",
      bounds: [0, -0.05, -0.05, 2, 0.05, 0.05],
      object_ids: ["object:pipe"],
      generation_config: { points: [[0, 0, 0], [2, 0, 0]], radius_m: 0.05, source: "tuba.element" }
    },
    {
      id: "geometry:mesh-line",
      format: "polyline",
      bounds: [0, 0, 0, 2, 0, 0],
      object_ids: ["object:mesh-line"],
      generation_config: { points: [[0, 0.12, 0], [2, 0.12, 0]], source: "tuba.analysis_mesh.element" }
    },
    {
      id: "geometry:node",
      format: "point",
      bounds: [0, 0, 0, 0, 0, 0],
      object_ids: ["object:node"],
      generation_config: { point: [0, 0, 0], source: "tuba.analysis_mesh.node" }
    },
    {
      id: "geometry:reaction",
      format: "vector",
      bounds: [0, 0, 0, 0, 0, 1],
      object_ids: ["object:reaction"],
      generation_config: { start: [0, 0, 0], end: [0, 0, 1], source: "tuba.solver_results" }
    },
    {
      id: "geometry:box",
      format: "aabb",
      bounds: [1, -0.25, -0.2, 1.4, 0.25, 0.2],
      object_ids: ["object:box"],
      generation_config: { source: "tuba.obstacle" }
    },
    {
      id: "geometry:issue",
      format: "marker",
      bounds: [1.1, 0.05, 0, 1.1, 0.05, 0],
      object_ids: ["object:issue"],
      generation_config: { point: [1.1, 0.05, 0], issue_id: "issue:clash" }
    },
    {
      id: "geometry:mesh",
      format: "mesh",
      bounds: [2.2, 0, 0, 2.4, 0.2, 0.2],
      object_ids: ["object:mesh"],
      generation_config: {
        faces: [[0, 1, 2], [0, 1, 3]],
        source: "fixture.mesh",
        vertices: [[2.2, 0, 0], [2.4, 0, 0], [2.2, 0.2, 0], [2.2, 0, 0.2]]
      }
    }
  ];
  return {
    bounds: [0, -0.25, -0.2, 2.4, 0.25, 1],
    geometryAssets,
    geometryPayloads: [],
    visibleObjectIds: geometryAssets.flatMap((asset) => asset.object_ids)
  };
}

test("renderer declares all RV08 asset formats", () => {
  for (const format of ["tube", "polyline", "point", "vector", "marker", "aabb", "cylinder", "mesh", "tuyau_subpoint_glyphs", "label"]) {
    assert.ok(SUPPORTED_RENDER_FORMATS.has(format), `${format} is supported`);
  }
});

test("cylinder obstacles render as a horizontal bullet along their longest extent", () => {
  // The HP storage bullets in the hydrogen plant layout are cylinder obstacles;
  // without a renderer they came back as invalid assets and never drew.
  const state = fixtureState();
  state.geometryAssets.push({
    id: "geometry:bullet",
    format: "cylinder",
    bounds: [34, -5, 0, 46, -1.5, 3.5],
    object_ids: ["object:bullet"],
    generation_config: { source: "tuba.obstacle" }
  });

  const graph = createThreeSceneGraph({
    ...state,
    visibleObjectIds: [...state.visibleObjectIds, "object:bullet"]
  });

  assert.equal(graph.diagnostics.length, 0);
  const bullet = graph.objectsByObjectId.get("object:bullet");
  assert.ok(bullet, "the bullet renders");
  assert.equal(bullet.geometry.type, "CylinderGeometry");
  // 12 m along X, 3.5 m across: the X axis is the barrel, so the radius is 1.75.
  assert.ok(Math.abs(bullet.geometry.parameters.height - 12) < 1e-9);
  assert.ok(Math.abs(bullet.geometry.parameters.radiusTop - 1.75) < 1e-9);
  assert.deepEqual(bullet.position.toArray(), [40, -3.25, 1.75]);
});

test("scene graph renders visible geometry with stable scene object metadata", () => {
  const graph = createThreeSceneGraph(fixtureState());

  assert.equal(graph.diagnostics.length, 0);
  assert.equal(graph.renderedObjectCount, 7);
  assert.ok(graph.objectsByObjectId.get("object:pipe"));
  assert.equal(graph.objectsByObjectId.get("object:pipe").userData.primaryObjectId, "object:pipe");
  assert.equal(graph.objectsByObjectId.get("object:issue").userData.assetId, "geometry:issue");
});

// The grid is drawn from the model bounds rather than from a layer, so the
// Ground grid row toggles this flag instead of a layer's visibility. The lights
// share addReferenceHelpers with it and must not answer to it - without them
// nothing is visible at all.
test("the ground grid answers to its flag, and the lights do not", () => {
  const gridOf = (scene) => scene.children.filter((child) => child.type === "GridHelper");
  const lightsOf = (scene) =>
    scene.children.filter((child) => child.type === "HemisphereLight" || child.type === "DirectionalLight");

  const on = createThreeSceneGraph(fixtureState()).scene;
  assert.equal(gridOf(on).length, 1, "drawn by default");
  assert.equal(lightsOf(on).length, 2);

  const off = createThreeSceneGraph({ ...fixtureState(), referenceGridVisible: false }).scene;
  assert.equal(gridOf(off).filter((grid) => grid.visible).length, 0);
  assert.equal(lightsOf(off).length, 2, "the lights are not optional");
});

// The row flipped the flag, but the cached graph kept the grid it was built
// with. Rebuilding for it was correct but cost a full graph (a 56k-node skin)
// per click; the visibility pass flips the grid instead.
test("toggling the ground grid hides and shows it without rebuilding the graph", () => {
  const gridOf = (graph) => graph.scene.children.find((child) => child.type === "GridHelper");
  const cache = rendererModule.createSceneGraphCache(createThreeSceneGraph, disposeThreeSceneGraph);
  const state = fixtureState();
  const graph = cache.get(state);
  assert.equal(gridOf(graph).visible, true);
  const hidden = { ...state, referenceGridVisible: false };
  assert.equal(cache.get(hidden), graph, "no rebuild");
  rendererModule.updateSceneGraphVisibility(graph, hidden);
  assert.equal(gridOf(graph).visible, false);
  const shown = { ...state, referenceGridVisible: true };
  assert.equal(cache.get(shown), graph);
  rendererModule.updateSceneGraphVisibility(graph, shown);
  assert.equal(gridOf(graph).visible, true);
  cache.clear();
});

// Only the prescribed-displacement badge is drawn in display units, so only a
// scene with one rebuilds when the units change.
test("a unit switch rebuilds the graph only when a prescribed badge needs redrawing", () => {
  const cache = rendererModule.createSceneGraphCache(createThreeSceneGraph, disposeThreeSceneGraph);
  const plain = { ...fixtureState(), unitSystem: "si" };
  const graph = cache.get(plain);
  assert.equal(cache.get({ ...plain, unitSystem: "engineering" }), graph, "nothing drawn in units: no rebuild");
  const prescribed = {
    ...plain,
    geometryAssets: [...plain.geometryAssets, {
      id: "geometry:support:p", format: "point", bounds: [0, 0, 0, 0, 0, 0], object_ids: ["object:support:p"],
      generation_config: { point: [0, 0, 0], source: "tuba.support", imposed_displacement: [0, 0, 0.08] }
    }],
    visibleObjectIds: [...plain.visibleObjectIds, "object:support:p"]
  };
  const withBadge = cache.get(prescribed);
  assert.notEqual(cache.get({ ...prescribed, unitSystem: "engineering" }), withBadge, "the badge is redrawn in the new units");
  cache.clear();
});

test("source triangulation toggles only its imported surface and invalidates the cached graph", () => {
  const state = fixtureState();
  const source = state.geometryAssets.find(asset => asset.id === "geometry:mesh");
  state.geometryAssets.push({ ...source, id: "second", object_ids: ["second"] });
  state.visibleObjectIds.push("second");
  const cache = rendererModule.createSceneGraphCache(createThreeSceneGraph, disposeThreeSceneGraph);
  const initial = cache.get(state);
  assert.equal(initial.objectsByObjectId.get("object:mesh").children.some(child => child.isLineSegments), false);
  const withMesh = cache.get({ ...state, sourceMeshObjectIds: ["object:mesh"] });
  assert.ok(withMesh !== initial);
  assert.equal(withMesh.objectsByObjectId.get("object:mesh").children.some(child => child.isLineSegments), true);
  assert.equal(withMesh.objectsByObjectId.get("second").children.some(child => child.isLineSegments), false);
  assert.equal(source.generation_config.show_edges, undefined);
  const cleared = cache.get({ ...state, sourceMeshObjectIds: [] });
  assert.equal(cleared.objectsByObjectId.get("object:mesh").children.some(child => child.isLineSegments), false);
  cache.clear();
});

test("mesh vertex values render as a scalar-colored surface", () => {
  const state = fixtureState();
  const asset = state.geometryAssets.find((candidate) => candidate.id === "geometry:mesh");
  asset.generation_config.vertex_values = [10, 20, 30, 40];
  asset.generation_config.legend = { range: { min: 10, max: 40 }, color_map: "turbo" };

  const graph = createThreeSceneGraph(state);
  const mesh = graph.objectsByObjectId.get("object:mesh");

  assert.equal(mesh.material.vertexColors, true);
  assert.equal(mesh.geometry.getAttribute("color").count, 6);
  // Both faces retain the same scalar color at their duplicated corner.
  const colors = mesh.geometry.getAttribute("color");
  const sources = mesh.geometry.userData.sourceVertexIndices;
  assert.deepEqual(Array.from(colors.array.slice(0,3)),
    Array.from(colors.array.slice(sources.lastIndexOf(0)*3,sources.lastIndexOf(0)*3+3)));
});

test("analysis mesh at 100 percent opacity is actually opaque", () => {
  const state = fixtureState();
  const asset = state.geometryAssets.find((candidate) => candidate.id === "geometry:mesh");
  asset.generation_config.show_edges = true;
  state.objectLayerIds = { "object:mesh": ["analysis_mesh:volume_skin"] };
  state.layers = { "analysis_mesh:volume_skin": { category: "analysis_mesh" } };
  state.bodyOpacity = { analysis_mesh: 1 };

  const mesh = createThreeSceneGraph(state).objectsByObjectId.get("object:mesh");

  assert.equal(mesh.material.opacity, 1);
  assert.equal(mesh.material.transparent, false);
  assert.equal(mesh.material.depthWrite, true);
});

test("analysis surface mesh triangulates quadrilateral fills without drawing diagonals", () => {
  const state = fixtureState();
  const asset = state.geometryAssets.find((candidate) => candidate.id === "geometry:mesh");
  asset.generation_config.vertices = [
    [0, 0, 0],
    [1, 0, 0],
    [1, 1, 0],
    [0, 1, 0]
  ];
  asset.generation_config.faces = [[0, 1, 2, 3]];
  asset.generation_config.show_edges = true;
  asset.generation_config.surface_edge_indices = [[0, 1], [1, 2], [2, 3], [3, 0]];

  const mesh = createThreeSceneGraph(state).objectsByObjectId.get("object:mesh");
  const edges = mesh.children.find((child) => child.isLineSegments);

  assert.ok(edges);
  assert.deepEqual([...mesh.geometry.index.array], [0, 1, 2, 0, 2, 3]);
  assert.deepEqual([...edges.geometry.index.array], [0, 1, 1, 2, 2, 3, 3, 0]);
  assert.equal(mesh.material.side, DoubleSide);
  assert.equal(edges.material.color.getHex(), 0x1f2937);
});

test("a cut reveals the internal volume-element edges", () => {
  const state = fixtureState();
  const asset = state.geometryAssets.find((candidate) => candidate.id === "geometry:mesh");
  asset.generation_config.volume_vertices = [
    [0, 0, 0],
    [1, 0, 0],
    [0, 1, 0],
    [0, 0, 1]
  ];
  asset.generation_config.volume_edge_indices = [
    [0, 1],
    [0, 2],
    [0, 3],
    [1, 2],
    [1, 3],
    [2, 3]
  ];

  const mesh = createThreeSceneGraph(state).objectsByObjectId.get("object:mesh");
  const volumeEdges = mesh.children.find((child) => child.userData.volumeMeshEdges);

  assert.ok(volumeEdges);
  assert.equal(volumeEdges.visible, false);
  applySectionBoxClipping({ root: mesh }, { min: [0, 0, 0], max: [0.5, 0.5, 0.5] });
  assert.equal(volumeEdges.visible, true);
  applySectionBoxClipping({ root: mesh }, null);
  assert.equal(volumeEdges.visible, false);
});

test("scene graph renders cold geometry as transparent gray reference for visual deformation", () => {
  const graph = createThreeSceneGraph({
    bounds: [0, -0.1, -0.1, 1, 0.1, 0.1],
    geometryAssets: [
      {
        id: "geometry:pipe",
        format: "tube",
        bounds: [0, -0.05, -0.05, 1, 0.05, 0.05],
        object_ids: ["object:pipe"],
        generation_config: { points: [[0, 0, 0], [1, 0, 0]], radius_m: 0.05, source: "tuba.element" }
      },
      {
        id: "geometry:visual_deformed",
        format: "polyline",
        bounds: [0, 0, 0, 1, 0.4, 0],
        object_ids: ["object:visual"],
        generation_config: {
          source: "tuba.deformed_centerline.visual",
          visual_scale: 40,
          base_points: [[0, 0, 0], [1, 0, 0]],
          points: [[0, 0, 0], [1, 0.4, 0]]
        }
      }
    ],
    geometryPayloads: [],
    visibleObjectIds: ["object:pipe", "object:visual"]
  });

  const material = graph.objectsByObjectId.get("object:pipe").material;
  assert.equal(material.color.getHex(), 0x9ca3af);
  assert.equal(material.opacity, 0.32);
  assert.equal(material.transparent, true);
});

test("geometry state selection renders only matching deformation assets and keeps untagged reference geometry", () => {
  const state = {
    bounds: [0, -0.1, -0.1, 1, 0.4, 0.1],
    geometryAssets: [
      {
        id: "geometry:reference",
        format: "tube",
        bounds: [0, -0.05, -0.05, 1, 0.05, 0.05],
        object_ids: ["object:reference"],
        generation_config: { points: [[0, 0, 0], [1, 0, 0]], radius_m: 0.05, source: "tuba.element" }
      },
      {
        id: "geometry:physical",
        format: "polyline",
        bounds: [0, 0, 0, 1, 0.1, 0],
        object_ids: ["object:physical"],
        generation_config: {
          geometry_state_id: "geometry_state:Operating:physical",
          points: [[0, 0, 0], [1, 0.1, 0]],
          source: "tuba.deformed_centerline.physical"
        }
      },
      {
        id: "geometry:visual",
        format: "polyline",
        bounds: [0, 0, 0, 1, 0.4, 0],
        object_ids: ["object:visual"],
        generation_config: {
          points: [[0, 0, 0], [1, 0.4, 0]],
          source: "tuba.deformed_centerline.visual",
          visual_scale: 40
        }
      }
    ],
    geometryPayloads: [{
      asset_id: "geometry:visual",
      generation_config: { geometry_state_id: "geometry_state:Operating:visual" }
    }],
    visibleObjectIds: ["object:reference", "object:physical", "object:visual"]
  };

  const physical = createThreeSceneGraph({ ...state, activeGeometryStateId: "geometry_state:Operating:physical" });
  assert.deepEqual([...physical.objectsByObjectId.keys()].sort(), ["object:physical", "object:reference"]);

  const visual = createThreeSceneGraph({ ...state, activeGeometryStateId: "geometry_state:Operating:visual" });
  assert.deepEqual([...visual.objectsByObjectId.keys()].sort(), ["object:reference", "object:visual"]);
  const reference = visual.objectsByObjectId.get("object:reference").material;
  assert.equal(reference.color.getHex(), 0x9ca3af);
  assert.equal(reference.opacity, 0.32);
});

test("pipe geometry remains visible end-on as a hollow section", () => {
  const state = fixtureState();
  state.geometryAssets[0].generation_config.inner_radius_m = 0.04;

  const graph = createThreeSceneGraph(state);
  const pipe = graph.objectsByObjectId.get("object:pipe");

  assert.equal(pipe.isGroup, true);
  assert.equal(pipe.children.filter((child) => child.geometry?.type === "RingGeometry").length, 2);
  assert.equal(pipe.children.filter((child) => child.geometry?.type === "TubeGeometry").length, 2);
});

test("support restraints use solid V2 DOF glyphs at a visible scale", () => {
  const supports = [
    { id: "anchor", support_type: "anchor" },
    { id: "guide-z", support_type: "guide", direction: [0, 0, 1] },
    { id: "rest-z", support_type: "rest" },
    { id: "joint", support_type: "custom", blocked_dof: [1, 1, 1, 0, 0, 0] },
    { id: "custom", support_type: "custom", blocked_dof: [1, 1, 0, 0, 0, 1] }
  ];
  const graph = createThreeSceneGraph({
    bounds: [0, -1, -1, 10, 1, 1],
    geometryAssets: supports.map((support, index) => ({
        id: `geometry:support:${support.id}`,
        format: "point",
        bounds: [index, 0, 0, index, 0, 0],
        object_ids: [`object:support:${support.id}`],
        generation_config: {
          point: [index, 0, 0],
          source: "tuba.support",
          ...support
        }
      })),
    geometryPayloads: [],
    visibleObjectIds: supports.map(({ id }) => `object:support:${id}`)
  });

  const glyphs = supports.map(({ id }) => graph.objectsByObjectId.get(`object:support:${id}`));
  // A directionless rest is NOM_CMP='DZ' in the solver, so its cones ride Z.
  const restCones = graph.objectsByObjectId
    .get("object:support:rest-z")
    .children.filter((part) => part.userData.supportPart === "restraint-cone");
  assert.deepEqual(restCones.map((cone) => cone.userData.supportAxis), [2, 2]);
  assert.deepEqual(glyphs.map((glyph) => glyph.userData.supportGlyph), ["dof", "dof", "dof", "dof", "dof"]);
  // Grounded fixtures carry a hatch plate; the DOF parts are unchanged.
  assert.deepEqual(glyphs.map((glyph) => glyph.userData.supportAttachment), ["ground", "ground", "ground", "ground", "ground"]);
  assert.deepEqual(
    glyphs.map((glyph) => glyph.children.map((child) => child.userData.supportPart).filter(Boolean).sort().join(",")),
    [
      "fixed-block,ground-hatch",
      "ground-hatch,restraint-cone,restraint-cone",
      "ground-hatch,restraint-cone,restraint-cone",
      "ground-hatch,restraint-cone,restraint-cone,restraint-cone,restraint-cone,restraint-cone,restraint-cone",
      "ground-hatch,restraint-cone,restraint-cone,restraint-cone,restraint-cone,restraint-rotation"
    ]
  );
  for (const glyph of glyphs) {
    const size = new Box3().setFromObject(glyph).getSize(new Vector3());
    assert.ok(Math.max(size.x, size.y, size.z) >= 0.1, `${glyph.userData.supportGlyph} remains visible`);
      for (const part of glyph.children) {
        assert.equal(part.material.wireframe, false);
        assert.equal(part.material.color.getHex(), SUPPORT_NEUTRAL);
      }
  }
});

test("rest support with friction generates contact shoe pad and friction badge", () => {
  const canvasFactory = () => ({
    width: 0,
    height: 0,
    getContext: () => ({
      fillRect() {},
      fillText() {},
      beginPath() {},
      roundRect() {},
      fill() {},
      stroke() {},
      measureText: (text) => ({ width: text.length * 16 })
    })
  });
  const graph = createThreeSceneGraph(
    {
      bounds: [0, -1, -1, 5, 1, 1],
      geometryAssets: [
        {
          id: "geometry:support:shoe-rest",
          format: "point",
          bounds: [2, 0, 3, 2, 0, 3],
          object_ids: ["object:support:shoe-rest"],
          generation_config: {
            point: [2, 0, 3],
            source: "tuba.support",
            support_type: "rest",
            friction_coefficient: 0.3,
            attached_to: "N_beam",
            contact_normal: [0, 0, 1]
          }
        }
      ],
      geometryPayloads: [],
      visibleObjectIds: ["object:support:shoe-rest"]
    },
    { canvasFactory }
  );

  const glyph = graph.objectsByObjectId.get("object:support:shoe-rest");
  assert.ok(glyph, "support glyph created");

  const pad = glyph.children.find((p) => p.userData.supportPart === "contact-shoe-pad");
  assert.ok(pad, "contact shoe pad mesh created");

  const badge = glyph.children.find((p) => p.userData.supportPart === "friction-badge");
  assert.ok(badge, "friction micro-badge sprite created");

  const guides = pad.children.find((c) => c.name === "sliding-plane-guides");
  assert.ok(guides, "sliding plane guides created on shoe pad");
});

// Sticking/sliding is a Code_Aster result, not one of the authored values Show
// values hides; hiding the μ badge used to take the state icon with it.
test("hiding values keeps a shoe's solved contact state on screen", () => {
  const texts = [];
  const canvasFactory = () => ({
    width: 0,
    height: 0,
    getContext: () => ({
      fillRect() {}, beginPath() {}, roundRect() {}, fill() {}, stroke() {},
      fillText(text) { texts.push(text); },
      measureText: (text) => ({ width: text.length * 16 })
    })
  });
  const contact = { support_id: "shoe", node_id: "N1", normal: [0, 0, 1], status: "sliding", normal_force: 1000,
    tangential_force: [300, 0, 0], gap: 0, relative_displacement: [0.002, 0, 0], slip: [0.002, 0, 0], friction_limit: 300, utilization: 1 };
  const graph = createThreeSceneGraph({
    bounds: [0, -1, -1, 5, 1, 1],
    resultStates: [{ kind: "result_state", id: "rs", data: { id: "rs", load_case: "Op", contact_results: { shoe: contact } } }],
    activeResultStateId: "rs",
    geometryAssets: [{
      id: "geometry:support:shoe", format: "point", bounds: [2, 0, 0, 2, 0, 0], object_ids: ["object:support:shoe"],
      generation_config: { point: [2, 0, 0], source: "tuba.support", support_id: "shoe", support_type: "rest", friction_coefficient: 0.3, contact_normal: [0, 0, 1] }
    }],
    geometryPayloads: [],
    visibleObjectIds: ["object:support:shoe"]
  }, { canvasFactory });
  const glyph = graph.objectsByObjectId.get("object:support:shoe");
  const badge = glyph.children.find((part) => part.userData.supportPart === "friction-badge");
  const state = glyph.children.find((part) => part.userData.supportPart === "friction-state");
  assert.ok(texts.includes("➜ μ = 0.30"));
  assert.ok(state?.isSprite && texts.includes("➜"), "an icon-only stand-in exists");

  applyValueLabelVisibility(graph, false);
  assert.equal(badge.visible, false, "the μ value goes");
  assert.equal(state.visible, true, "the solved state stays");
  applyValueLabelVisibility(graph, true);
  assert.equal(badge.visible, true);
  assert.equal(state.visible, false, "one badge at a time");
});

test("ground hatch hugs the glyph underside instead of floating below it", () => {
  const graph = createThreeSceneGraph({
    bounds: [0, -1, -1, 10, 1, 1],
    geometryAssets: [
      {
        id: "geometry:support:anchor",
        format: "point",
        bounds: [0, 0, 0, 0, 0, 0],
        object_ids: ["object:support:anchor"],
        generation_config: { point: [0, 0, 0], source: "tuba.support", support_type: "anchor" }
      },
      {
        id: "geometry:support:rest",
        format: "point",
        bounds: [2, 0, 0, 2, 0, 0],
        object_ids: ["object:support:rest"],
        generation_config: { point: [2, 0, 0], source: "tuba.support", support_type: "rest" }
      }
    ],
    geometryPayloads: [],
    visibleObjectIds: ["object:support:anchor", "object:support:rest"]
  });
  for (const id of ["object:support:anchor", "object:support:rest"]) {
    const glyph = graph.objectsByObjectId.get(id);
    const plate = glyph.children.find((part) => part.userData.supportPart === "ground-hatch");
    assert.ok(plate, `${id} carries a ground hatch`);
    // Lowest DOF part, measured without the plate itself.
    const holder = new Group();
    for (const part of glyph.children.filter((part) => part !== plate)) holder.add(part.clone());
    holder.position.copy(glyph.position);
    holder.updateMatrixWorld(true);
    const restMin = new Box3().setFromObject(holder).min.z - glyph.position.z;
    const plateTop = plate.position.z + plate.geometry.parameters.depth / 2;
    assert.ok(restMin - plateTop >= 0, "plate clears the glyph");
    assert.ok(restMin - plateTop < 0.5, `plate hugs the glyph (gap ${restMin - plateTop})`);
  }
});

test("an attached support skips the ground hatch and draws a dashed link", () => {
  const graph = createThreeSceneGraph({
    bounds: [0, -1, -1, 10, 1, 1],
    geometryAssets: [
      {
        id: "geometry:support:shoe",
        format: "point",
        bounds: [0, 0, 3, 0, 0, 3],
        object_ids: ["object:support:shoe"],
        generation_config: { point: [0, 0, 3], source: "tuba.support", support_type: "rest", attached_to: "N9" }
      },
      {
        id: "geometry:support_link:shoe",
        format: "polyline",
        bounds: [0, 0, 2.75, 0, 0, 3],
        object_ids: ["object:support_link:shoe"],
        generation_config: {
          source: "tuba.support_link",
          support_id: "shoe",
          node: "N1",
          attached_to: "N9",
          points: [[0, 0, 3], [0, 0, 2.75]],
          color: "#64748b"
        }
      }
    ],
    geometryPayloads: [],
    visibleObjectIds: ["object:support:shoe", "object:support_link:shoe"]
  });
  const glyph = graph.objectsByObjectId.get("object:support:shoe");
  assert.equal(glyph.userData.supportAttachment, "attached");
  assert.equal(
    glyph.children.some((part) => part.userData.supportPart === "ground-hatch"),
    false,
    "attached glyphs carry no ground hatch"
  );
  const link = graph.objectsByObjectId.get("object:support_link:shoe");
  assert.equal(link.userData.supportLink, "attachment");
  assert.equal(link.material.isLineDashedMaterial, true);
});

test("a support glyph clears the pipe radius the asset carries", () => {
  // Real bundles carry radius_m - the radius of the pipe the support clamps.
  // Read as a glyph size it drew the mark flush with the wall, invisible.
  const radius = 0.04445;
  const graph = createThreeSceneGraph({
    bounds: [0, -1, -1, 8, 1, 1],
    geometryAssets: [
      {
        id: "geometry:support:anchor",
        format: "point",
        bounds: [2, 0, 0, 2, 0, 0],
        object_ids: ["object:support:anchor"],
        generation_config: {
          point: [2, 0, 0],
          source: "tuba.support",
          support_type: "anchor",
          radius_m: radius
        }
      }
    ],
    geometryPayloads: [],
    visibleObjectIds: ["object:support:anchor"]
  });

  const glyph = graph.objectsByObjectId.get("object:support:anchor");
  const size = new Box3().setFromObject(glyph).getSize(new Vector3());
  assert.ok(
    Math.min(size.x, size.y, size.z) > radius * 2,
    `glyph ${size.x} must clear the ${radius * 2} pipe it marks`
  );
});

test("a support glyph follows its pipe, not the model span", () => {
  // A span-driven size gave an 80 mm pipe on a 40 m plant a 1.8 m restraint star.
  const graph = createThreeSceneGraph({
    bounds: [0, -1, -1, 40, 1, 1],
    geometryAssets: [{
      id: "geometry:support:joint",
      format: "point",
      bounds: [2, 0, 0, 2, 0, 0],
      object_ids: ["object:support:joint"],
      generation_config: { point: [2, 0, 0], source: "tuba.support", support_type: "custom", blocked_dof: [1, 1, 1, 0, 0, 0], radius_m: 0.04 }
    }],
    geometryPayloads: [],
    visibleObjectIds: ["object:support:joint"]
  });

  const size = new Box3().setFromObject(graph.objectsByObjectId.get("object:support:joint")).getSize(new Vector3());
  assert.ok(Math.max(size.x, size.y, size.z) <= 0.7, `glyph ${size.x} x ${size.z} dwarfs the 0.08 pipe`);
});

test("a support acting through a rigid patch draws no larger than the patch", () => {
  // A lug support on a 10 m tower: no pipe on its node, so the span floor would
  // draw a star about 0.37 m across around a 0.15 m lug patch.
  const glyph = (extra) => {
    const graph = createThreeSceneGraph({
      bounds: [0, -5, 0, 1, 5, 10],
      geometryAssets: [{
        id: "geometry:support:lug", format: "point", bounds: [0, 0, 6, 0, 0, 6], object_ids: ["object:support:lug"],
        generation_config: { point: [0, 0, 6], source: "tuba.support", support_type: "custom", blocked_dof: [1, 0, 1, 0, 0, 0], ...extra }
      }],
      geometryPayloads: [],
      visibleObjectIds: ["object:support:lug"]
    });
    const size = new Box3().setFromObject(graph.objectsByObjectId.get("object:support:lug")).getSize(new Vector3());
    return Math.max(size.x, size.y, size.z);
  };
  assert.ok(glyph({}) > 0.3, "without a patch the span floor still keeps an unpiped support visible");
  assert.ok(glyph({ body_extent_m: 0.15 }) <= 0.16, `glyph ${glyph({ body_extent_m: 0.15 })} overruns its 0.15 m patch`);
});

test("support anchors stay on the constrained node without hiding the pipe", () => {
  const graph = createThreeSceneGraph({
    bounds: [-0.08, -0.05, -0.05, 0, 0.05, 0.05],
    geometryAssets: [{
      id: "geometry:support:anchor",
      format: "point",
      bounds: [-0.08, 0, 0, -0.08, 0, 0],
      object_ids: ["object:support:anchor"],
      generation_config: {
        point: [-0.08, 0, 0],
        source: "tuba.support",
        support_type: "anchor",
        radius_m: 0.05,
        display_direction: [-1, 0, 0]
      }
    }],
    geometryPayloads: [],
    visibleObjectIds: ["object:support:anchor"]
  });

  const glyph = graph.objectsByObjectId.get("object:support:anchor");
  const block = glyph.children.find((part) => part.userData.supportPart === "fixed-block");
  const blockBounds = new Box3().setFromObject(block);
  const blockSize = blockBounds.getSize(new Vector3());

  assert.ok(glyph.position.distanceTo(new Vector3(-0.08, 0, 0)) < 1e-12, `glyph is offset to ${glyph.position.toArray()}`);
  assert.ok(blockSize.x > 0.1, `fixed block width ${blockSize.x} must clear the 0.1 pipe`);
  assert.equal(block.material.depthTest, true);
  assert.equal(block.material.depthWrite, false);
  assert.equal(block.material.transparent, true);
  assert.equal(block.material.opacity, 0.85);
  assert.equal(glyph.children.some((part) => part.userData.supportPart === "leader"), false);
});

test("support springs and prescribed displacements retain V2 colors and axis semantics", () => {
  const graph = createThreeSceneGraph({
    bounds: [0, -1, -1, 2, 1, 1],
    geometryAssets: [
      {
        id: "geometry:support:spring",
        format: "point",
        bounds: [0, 0, 0, 0, 0, 0],
        object_ids: ["object:support:spring"],
        generation_config: {
          point: [0, 0, 0],
          source: "tuba.support",
          support_type: "spring",
          stiffness_matrix: [1000, 0, 3000, 0, 4000, 0]
        }
      },
      {
        id: "geometry:support:prescribed",
        format: "point",
        bounds: [1, 0, 0, 1, 0, 0],
        object_ids: ["object:support:prescribed"],
        generation_config: {
          point: [1, 0, 0],
          source: "tuba.support",
          support_type: "custom",
          blocked_dof: [1, 0, 0, 0, 0, 0],
          imposed_displacement: [0, 0.001, 0]
        }
      }
    ],
    geometryPayloads: [],
    visibleObjectIds: ["object:support:spring", "object:support:prescribed"]
  });

  const spring = graph.objectsByObjectId.get("object:support:spring");
  const springParts = spring.children.filter((part) => part.userData.supportPart?.startsWith("spring"));
  // One coil and its seat per sprung direction (X and Z here).
  assert.deepEqual(springParts.filter((part) => part.userData.supportPart === "spring-coil").map((part) => part.userData.supportAxis), [0, 2]);
  assert.equal(springParts.filter((part) => part.userData.supportPart === "spring-seat").length, 2);
  assert.equal(springParts.filter((part) => part.userData.supportPart === "spring-rotation").length, 1);
    assert.ok(springParts.every((part) => part.material.color.getHex() === SUPPORT_NEUTRAL && part.material.wireframe === false));

    const prescribed = graph.objectsByObjectId.get("object:support:prescribed");
    assert.equal(prescribed.children.filter((part) => part.userData.supportPart === "restraint-cone").length, 2);
    const displacement = prescribed.children.find((part) => part.userData.supportPart === "prescribed-displacement");
    assert.ok(displacement);
    assert.equal(displacement.material.color.getHex(), SUPPORT_NEUTRAL);
    // Hollow where a restraint is solid: a prescribed movement and a restraint
    // are both cones on one axis, and fill is what tells them apart.
    assert.equal(displacement.material.wireframe, true);
});

test("a prescribed movement on a fully held support reads clear of the anchor block, with its value", () => {
  const texts = [];
  const canvasFactory = () => ({
    width: 0,
    height: 0,
    getContext: () => ({
      measureText: (text) => ({ width: text.length * 20 }),
      beginPath() {}, roundRect() {}, fill() {}, stroke() {}, fillRect() {},
      fillText(text) { texts.push(text); }
    })
  });
  const state = (unitSystem) => ({
    bounds: [0, -1, -1, 2, 1, 1],
    unitSystem,
    geometryAssets: [{
      id: "geometry:support:tp",
      format: "point",
      bounds: [0, 0, 0, 0, 0, 0],
      object_ids: ["object:support:tp"],
      generation_config: {
        point: [0, 0, 0],
        source: "tuba.support",
        support_type: "custom",
        blocked_dof: [1, 1, 1, 1, 1, 1],
        imposed_displacement: [0, 0, 0.08]
      }
    }],
    geometryPayloads: [],
    visibleObjectIds: ["object:support:tp"]
  });

  const graph = createThreeSceneGraph(state("engineering"), { canvasFactory });
  const glyph = graph.objectsByObjectId.get("object:support:tp");
  glyph.updateMatrixWorld(true);
  const block = new Box3().setFromObject(glyph.children.find((part) => part.userData.supportPart === "fixed-block"));
  const arrow = new Box3().setFromObject(glyph.children.find((part) => part.userData.supportPart === "prescribed-displacement"));
  // The hollow cone used to start at the node, inside the block that holds the
  // other five DOFs. It now sits wholly past it, on the imposed direction.
  assert.ok(arrow.min.z > block.max.z, `arrow ${arrow.min.z} must clear the block ${block.max.z}`);
  assert.ok(glyph.children.some((part) => part.userData.supportPart === "prescribed-shaft"), "a shaft ties it to the node");

  const badge = glyph.children.find((part) => part.userData.loadPart === "load-badge");
  assert.ok(badge?.isSprite, "the movement carries a value badge");
  assert.ok(badge.position.z > arrow.max.z - glyph.position.z, "the badge sits past the arrow tip");
  assert.ok(texts.includes("ΔZ = 80 mm"));
  createThreeSceneGraph(state("si"), { canvasFactory });
  assert.ok(texts.includes("ΔZ = 0.08 m"), "the badge follows the display units");

  // Show values governs it like the force badges.
  applyValueLabelVisibility(graph, false);
  assert.equal(badge.visible, false);
  applyValueLabelVisibility(graph, true);
  assert.equal(badge.visible, true);

  // A screen-sized badge has no fixed world size: the ground plate and the
  // selection outline count it by its anchor alone.
  const support = { ...state("engineering"), objects: [{ id: "object:support:tp", kind: "support", entity_ref: "support:tp" }] };
  const labelled = createThreeSceneGraph(support, { canvasFactory });
  const bare = createThreeSceneGraph(support, { canvasFactory: () => null });
  const plateZ = (rendered) => rendered.objectsByObjectId.get("object:support:tp").children
    .find((part) => part.userData.supportPart === "ground-hatch").position.z;
  assert.equal(plateZ(labelled), plateZ(bare));
  // The selection outline is the outline pass, which traces meshes only, so a
  // badge sprite of whatever zoomed size never enlarges it - and there is no
  // box to measure it into.
  assert.equal(labelled.objectsByObjectId.get("object:support:tp").userData.outlineSurface, true);
  assert.equal(labelled.objectsByObjectId.get("object:support:tp").userData.highlightOutline, undefined);
});

// Imposed displacement carries three or six components (mixed_study.py), and the
// badge used to be gated on the translation length: a rotation-only support,
// or one moved by a micrometre, carried no mark at all.
test("a rotation-only or micrometre prescribed movement still gets its badge and mark", () => {
  const texts = [];
  const canvasFactory = () => ({
    width: 0,
    height: 0,
    getContext: () => ({
      measureText: (text) => ({ width: text.length * 20 }),
      beginPath() {}, roundRect() {}, fill() {}, stroke() {}, fillRect() {},
      fillText(text) { texts.push(text); }
    })
  });
  const glyphFor = (imposed) => {
    const graph = createThreeSceneGraph({
      bounds: [0, -1, -1, 2, 1, 1],
      unitSystem: "si",
      geometryAssets: [{
        id: "geometry:support:p",
        format: "point",
        bounds: [0, 0, 0, 0, 0, 0],
        object_ids: ["object:support:p"],
        generation_config: { point: [0, 0, 0], source: "tuba.support", support_type: "custom", blocked_dof: [1, 1, 1, 1, 1, 1], imposed_displacement: imposed }
      }],
      geometryPayloads: [],
      visibleObjectIds: ["object:support:p"]
    }, { canvasFactory });
    return graph.objectsByObjectId.get("object:support:p");
  };
  const part = (glyph, name) => glyph.children.find((child) => child.userData.supportPart === name || child.userData.loadPart === name);

  const rotation = glyphFor([0, 0, 0, 0, 0, 0.01]);
  assert.ok(part(rotation, "load-badge")?.isSprite, "a rotation-only support carries a badge");
  assert.ok(texts.includes("ΔRZ = 0.01 rad"));
  const turn = part(rotation, "prescribed-rotation");
  assert.ok(turn, "and a rotation arc");
  assert.equal(part(rotation, "prescribed-displacement"), undefined, "no translation cone for a pure rotation");
  // The arc turns about Z: its local +Y is the world Z axis.
  assert.ok(new Vector3(0, 1, 0).applyQuaternion(turn.quaternion).distanceTo(new Vector3(0, 0, 1)) < 1e-9);

  const tiny = glyphFor([0, 0, 5e-7]);
  assert.ok(part(tiny, "prescribed-displacement"), "half a micrometre is still a movement");
  assert.ok(part(tiny, "load-badge")?.isSprite);
  assert.equal(part(tiny, "prescribed-rotation"), undefined);

  assert.equal(part(glyphFor([0, 0, 0, 0, 0, 0]), "load-badge"), undefined, "nothing moves, nothing is drawn");
});

test("scene graph reports invalid assets without throwing", () => {
  const graph = createThreeSceneGraph({
    bounds: [0, 0, 0, 1, 1, 1],
    geometryAssets: [
      {
        id: "geometry:bad-tube",
        format: "tube",
        bounds: [0, 0, 0, 0, 0, 0],
        object_ids: ["object:bad-tube"],
        generation_config: { points: [[0, 0, 0]] }
      }
    ],
    geometryPayloads: [],
    visibleObjectIds: ["object:bad-tube"]
  });

  assert.equal(graph.renderedObjectCount, 0);
  assert.equal(graph.diagnostics[0].code, "renderer.invalid_asset");
  assert.match(graph.diagnostics[0].message, /at least two points/);
});

function tuyauSubpointState(overrides = {}) {
  return {
    bounds: [0, 0, 0, 1, 1, 1],
    geometryAssets: [
      {
        id: "geometry:tuyau",
        format: "tuyau_subpoint_glyphs",
        bounds: [0, 0, 0, 0, 0.04, 0.07],
        object_ids: ["object:tuyau"],
        generation_config: {
          starts: [[0, 0, 0.034], [0, 0.017, 0.029]],
          ends: [[0, 0, 0.05], [0, 0.025, 0.043]],
          values: [42000000, 84000000],
          range: { min: 42000000, max: 84000000 },
          radius_m: 0.006
        }
      }
    ],
    geometryPayloads: [],
    overlays: [
      {
        id: "overlay:tuyau",
        kind: "solver_result",
        data: {
          result_type: "tuyau_subpoints",
          values: { "object:tuyau": 84000000 },
          range: { min: 42000000, max: 84000000 },
          unit: "Pa"
        }
      }
    ],
    visibleObjectIds: ["object:tuyau"],
    ...overrides
  };
}

test("scene graph renders TUYAU sub-points as one instanced glyph batch", () => {
  const graph = createThreeSceneGraph(tuyauSubpointState({ subpointMode: "measured" }));

  assert.equal(graph.diagnostics.length, 0);
  assert.equal(graph.renderedObjectCount, 1);
  const mesh = graph.objectsByObjectId.get("object:tuyau");
  assert.equal(mesh.isInstancedMesh, true);
  assert.equal(mesh.count, 2);
  assert.equal(mesh.material.vertexColors, false);
  assert.equal(mesh.instanceColor.count, 2);
});

// The pipe a sub-point sits in is opaque and hides every wall layer but the
// outer one, so the mode meant to surface the worst stations has to ignore
// depth - otherwise the bore and mid-wall points it exists to show are the ones
// thrown away. Peak mode therefore draws fewer marks, through the pipe.
test("peak mode thins the sub-point batch to the top of the range and x-rays it", () => {
  const graph = createThreeSceneGraph(tuyauSubpointState({ subpointMode: "peak", subpointThreshold: 0.8 }));
  const mesh = graph.objectsByObjectId.get("object:tuyau");

  assert.equal(mesh.count, 1);
  assert.equal(mesh.userData.subpointDrawnCount, 1);
  assert.equal(mesh.material.depthTest, false);
  assert.equal(mesh.material.depthWrite, false);
  assert.ok(mesh.renderOrder > 0);

  // The mark that survived is the high one, coloured exactly as the un-thinned
  // batch colours it - thinning must not quietly restyle the survivors.
  const full = createThreeSceneGraph(tuyauSubpointState({ subpointMode: "measured" }));
  const unthinned = full.objectsByObjectId.get("object:tuyau");
  assert.equal(mesh.instanceColor.getX(0), unthinned.instanceColor.getX(1));
  assert.equal(mesh.instanceColor.getY(0), unthinned.instanceColor.getY(1));
  assert.equal(mesh.instanceColor.getZ(0), unthinned.instanceColor.getZ(1));
});

test("measured mode keeps every sub-point and depth-tests them into the pipe", () => {
  const graph = createThreeSceneGraph(tuyauSubpointState({ subpointMode: "measured" }));
  const mesh = graph.objectsByObjectId.get("object:tuyau");

  assert.equal(mesh.count, 2);
  assert.equal(mesh.material.depthTest, true);
  assert.equal(mesh.material.depthWrite, true);
  assert.equal(mesh.renderOrder, 0);
});

test("a lower sub-point threshold admits more of the field", () => {
  const strict = createThreeSceneGraph(tuyauSubpointState({ subpointMode: "peak", subpointThreshold: 0.9 }));
  const loose = createThreeSceneGraph(tuyauSubpointState({ subpointMode: "peak", subpointThreshold: 0.5 }));

  assert.equal(strict.objectsByObjectId.get("object:tuyau").count, 1);
  assert.equal(loose.objectsByObjectId.get("object:tuyau").count, 2);
});

test("a sub-point with no value is kept, never read as a low one", () => {
  const state = tuyauSubpointState({ subpointMode: "peak", subpointThreshold: 0.8 });
  state.geometryAssets[0].generation_config.values = [84000000, null];
  const graph = createThreeSceneGraph(state);

  assert.equal(graph.objectsByObjectId.get("object:tuyau").count, 2);
});

test("sub-point glyph faceting comes from the bundle, not a renderer literal", () => {
  const state = tuyauSubpointState({ subpointMode: "measured" });
  state.geometryAssets[0].generation_config.radial_segments = 12;
  const graph = createThreeSceneGraph(state);

  const geometry = graph.objectsByObjectId.get("object:tuyau").geometry;
  assert.equal(geometry.parameters.radialSegments, 12);
});

test("fitCameraToBounds targets scene center and computes a usable distance", () => {
  const camera = new PerspectiveCamera(45, 1, 0.1, 1000);
  const fit = fitCameraToBounds(camera, [0, -1, -0.5, 10, 1, 2]);

  assert.deepEqual(fit.target, [5, 0, 0.75]);
  assert.ok(fit.distance > 10);
  assert.ok(camera.far > camera.near);
});

test("live camera fitting applies each request once and retains OrbitControls changes", () => {
  assert.equal(typeof rendererModule.createCameraFitController, "function");
  const camera = new PerspectiveCamera(45, 1, 0.1, 1000);
  const controls = { target: new Vector3(), update() {} };
  const controller = rendererModule.createCameraFitController(camera, controls);
  const firstState = { camera: { fitRequest: { id: 1, bounds: [0, 0, 0, 2, 2, 2] } } };

  controller.apply(firstState, [-10, -10, -10, 10, 10, 10]);
  assert.deepEqual(camera.userData.fitBounds, [0, 0, 0, 2, 2, 2]);
  camera.position.set(9, 8, 7);
  controls.target.set(6, 5, 4);

  controller.apply(firstState, [-10, -10, -10, 10, 10, 10]);
  assert.deepEqual(camera.position.toArray(), [9, 8, 7]);
  assert.deepEqual(controls.target.toArray(), [6, 5, 4]);

  controller.apply(
    { camera: { fitRequest: { id: 2, bounds: [10, 0, 0, 12, 2, 2] } } },
    [-10, -10, -10, 10, 10, 10]
  );
  assert.deepEqual(camera.userData.fitBounds, [10, 0, 0, 12, 2, 2]);
  assert.deepEqual(controls.target.toArray(), [11, 1, 1]);
});

test("live camera fitting performs the initial whole-scene fit only once", () => {
  assert.equal(typeof rendererModule.createCameraFitController, "function");
  const camera = new PerspectiveCamera(45, 1, 0.1, 1000);
  const controls = { target: new Vector3(), update() {} };
  const controller = rendererModule.createCameraFitController(camera, controls);
  const state = { camera: {} };

  controller.apply(state, [0, 0, 0, 4, 2, 2]);
  assert.deepEqual(camera.userData.fitBounds, [0, 0, 0, 4, 2, 2]);
  camera.position.set(9, 8, 7);
  controls.target.set(6, 5, 4);

  controller.apply(state, [0, 0, 0, 8, 4, 4]);
  assert.deepEqual(camera.position.toArray(), [9, 8, 7]);
  assert.deepEqual(controls.target.toArray(), [6, 5, 4]);
});

test("scene graph cache reuses geometry for selection-only state changes", () => {
  const state = fixtureState();
  const selected = { ...state, selectedObjectIds: ["object:pipe"] };
  const builds = [];
  const cache = rendererModule.createSceneGraphCache?.((nextState) => {
    builds.push(nextState);
    return { state: nextState };
  });

  assert.ok(cache);
  assert.strictEqual(cache.get(state), cache.get(selected));
  assert.equal(builds.length, 1);
});

test("scene graph cache reuses geometry when visibility changes", () => {
  const state = fixtureState();
  const visible = { ...state, visibleObjectIds: ["object:pipe"] };
  const builds = [];
  const disposed = [];
  const cache = rendererModule.createSceneGraphCache?.(
    (nextState) => {
      const graph = { state: nextState };
      builds.push(graph);
      return graph;
    },
    (graph) => disposed.push(graph)
  );

  assert.ok(cache);
  assert.strictEqual(cache.get(state), cache.get(visible));
  assert.equal(builds.length, 1);
  assert.deepEqual(disposed, []);
});

test("scene graph cache rebuilds when visibility changes deformed-reference materials", () => {
  const state = fixtureState();
  state.geometryAssets.push({
    id: "geometry:visual-deformed",
    format: "tube",
    bounds: [0, -0.05, -0.05, 2, 0.05, 0.05],
    object_ids: ["object:visual-deformed"],
    generation_config: {
      source: "tuba.deformed_centerline",
      points: [[0, 0, 0], [2, 0, 0]],
      base_points: [[0, 0, 0], [2, 0, 0]],
      visual_scale: 40
    }
  });
  state.visibleObjectIds.push("object:visual-deformed");
  const hidden = {
    ...state,
    visibleObjectIds: state.visibleObjectIds.filter((objectId) => objectId !== "object:visual-deformed")
  };
  const builds = [];
  const disposed = [];
  const cache = rendererModule.createSceneGraphCache(
    (nextState) => {
      const graph = { state: nextState };
      builds.push(graph);
      return graph;
    },
    (graph) => disposed.push(graph)
  );

  assert.notStrictEqual(cache.get(state), cache.get(hidden));
  assert.equal(builds.length, 2);
  assert.deepEqual(disposed, [builds[0]]);
});

test("scene graph cache rebuilds rendered materials when the coloring field changes", () => {
  const state = {
    ...fixtureState(),
    overlays: [
      { id: "overlay:blue", kind: "solver_result", data: { values: { "object:pipe": 0 }, legend: { range: { min: 0, max: 10 } } } },
      { id: "overlay:red", kind: "solver_result", data: { values: { "object:pipe": 10 }, legend: { range: { min: 0, max: 10 } } } }
    ],
    resultFields: [
      { id: "field:blue", overlay_id: "overlay:blue", load_case: "Hot", components: ["magnitude"], range: [0, 10] },
      { id: "field:red", overlay_id: "overlay:red", load_case: "Hot", components: ["magnitude"], range: [0, 10] }
    ],
    coloring: { loadCase: "Hot", fieldId: "field:blue", component: "magnitude" }
  };
  const cache = rendererModule.createSceneGraphCache(createThreeSceneGraph);
  const blue = cache.get(state);
  const red = cache.get({ ...state, coloring: { ...state.coloring, fieldId: "field:red" } });

  assert.notStrictEqual(red, blue);
  assert.notEqual(
    blue.objectsByObjectId.get("object:pipe").material.color.getHex(),
    red.objectsByObjectId.get("object:pipe").material.color.getHex()
  );
});

test("a solved shape at x1 owns the colour: the design solid yields, and each field paints only what carries it", () => {
  const tube = (id, objectId, config) => ({ id, format: "tube", bounds: [0, -0.1, -0.1, 1, 0.1, 0.1], object_ids: [objectId],
    generation_config: { points: [[0, 0, 0], [1, 0, 0]], radius_m: 0.05, ...config } });
  const arrow = (id, objectId, config) => ({ id, format: "vector", bounds: [0, 0, 0, 1, 0, 0], object_ids: [objectId],
    generation_config: { source: "tuba.result_state", node_id: "N1", start: [0, 0, 0], end: [1, 0, 0], ...config } });
  const field = (type, values, components = ["magnitude"]) => ({
    overlay: { id: `overlay:${type}`, kind: "solver_result", data: { result_type: type, values, legend: { range: { min: 0, max: 10 } } } },
    field: { id: `field:${type}`, overlay_id: `overlay:${type}`, load_case: "Hot", components, range: [0, 10] }
  });
  const fields = [
    field("stress", { "object:element:P": 7 }),
    field("displacement", { N1: [0, 0, 1], N2: [0, 0, 4] }, ["DX", "DY", "DZ", "magnitude"]),
    field("reaction_force", { N1: [0, 0, 9] }, ["DX", "DY", "DZ", "magnitude"])
  ];
  const objects = [
    { id: "object:element:P", kind: "pipe", entity_ref: "element:P" },
    { id: "object:element:R", kind: "rack_member", entity_ref: "element:R" },
    { id: "object:warp:P_s0", kind: "deformed_analysis_mesh_element", entity_ref: "element:P" },
    { id: "object:warp:R_s0", kind: "deformed_analysis_mesh_element", entity_ref: "element:R" },
    { id: "object:reaction:N1", kind: "reaction_vector", metadata: { result_type: "reaction_force" } },
    { id: "object:displacement:N1", kind: "displacement_vector", metadata: { result_type: "displacement" } }
  ];
  const warp = { source: "tuba.deformed_analysis_mesh.profile", geometry_state_id: "shape:Hot:physical", visual_scale: 1 };
  const state = {
    ...fixtureState(),
    objects,
    geometryAssets: [
      tube("geometry:P", "object:element:P", { source: "tuba.element" }),
      tube("geometry:warp:P_s0", "object:warp:P_s0", { ...warp, element_id: "P_s0", node_ids: ["N1", "N2"] }),
      tube("geometry:warp:R_s0", "object:warp:R_s0", { ...warp, element_id: "R_s0", node_ids: ["N3"] }),
      arrow("geometry:reaction:N1", "object:reaction:N1", { result_type: "reaction_force", color: "#dc2626" }),
      arrow("geometry:displacement:N1", "object:displacement:N1", { result_type: "displacement", color: "#7c3aed" })
    ],
    geometryPayloads: [],
    visibleObjectIds: objects.map((object) => object.id),
    activeGeometryStateId: "shape:Hot:physical",
    overlays: fields.map((item) => item.overlay),
    resultFields: fields.map((item) => item.field),
    colorChannel: "results"
  };
  const colorOf = (graph, id) => { const object = graph.objectsByObjectId.get(id); return (object.material ?? object.children[0].material).color.getHex(); };
  const stateFor = (type) => ({ ...state, coloring: { loadCase: "Hot", fieldId: `field:${type}`, component: "magnitude" } });
  const showing = (type) => createThreeSceneGraph(stateFor(type));
  const tint = (type, value) => colorForScalarValue(value, getScalarLegend(stateFor(type)));

  const stress = showing("stress");
  const design = stress.objectsByObjectId.get("object:element:P").material;
  assert.equal(design.color.getHex(), 0x9ca3af, "the design solid is reference geometry once its solved shape is drawn");
  assert.equal(design.polygonOffset, true, "and yields the depth test where the two coincide");
  assert.equal(colorOf(stress, "object:warp:P_s0"), tint("stress", 7), "a mesh segment carries its element's cell value");
  assert.equal(colorOf(stress, "object:warp:R_s0"), 0x9ca3af, "a body the field does not reach is grey, not a hue off the legend");
  assert.equal(stress.objectsByObjectId.get("object:warp:R_s0").material.userData.noResultHatch, true,
    "and hatched, so it cannot pass for the scale's own grey middle");
  assert.equal(Boolean(stress.objectsByObjectId.get("object:warp:P_s0").material.userData.noResultHatch), false);

  const displacement = showing("displacement");
  assert.equal(colorOf(displacement, "object:warp:P_s0"), tint("displacement", 4), "a segment reads its own nodes");
  assert.equal(colorOf(displacement, "object:reaction:N1"), 0xdc2626, "a reaction arrow never wears the displacement of its node");

  const reaction = showing("reaction_force");
  assert.equal(colorOf(reaction, "object:reaction:N1"), tint("reaction_force", 9));
  assert.equal(colorOf(reaction, "object:warp:P_s0"), 0x9ca3af, "a reaction field paints its arrows, not the supported member");
  assert.equal(Boolean(reaction.objectsByObjectId.get("object:warp:P_s0").material.userData.noResultHatch), false,
    "a member under an arrow-only field is scenery, not a missing result");

  // A CAD body is scenery around its solid's own field surfaces, never a gap.
  const cad = createThreeSceneGraph({ ...stateFor("stress"),
    objects: [...objects, { id: "object:component:tee", kind: "imported_component" }],
    geometryAssets: [...state.geometryAssets, { id: "geometry:tee", format: "mesh", bounds: [0, 0, 0, 1, 1, 0], object_ids: ["object:component:tee"],
      generation_config: { source: "tuba.imported_component", vertices: [[0, 0, 0], [1, 0, 0], [0, 1, 0]], faces: [[0, 1, 2]] } }],
    visibleObjectIds: [...state.visibleObjectIds, "object:component:tee"] });
  assert.equal(Boolean(cad.objectsByObjectId.get("object:component:tee").material.userData.noResultHatch), false);
  assert.equal(colorOf(reaction, "object:displacement:N1"), 0x7c3aed);
});

test("scene graph recolors a node-result vector when the coloring component changes", () => {
  const state = {
    ...fixtureState(),
    geometryAssets: [
      {
        id: "geometry:displacement:N1",
        format: "vector",
        bounds: [0, 0, 0, 1, 0, 0],
        object_ids: ["object:displacement:N1"],
        generation_config: {
          source: "tuba.result_state",
          result_type: "displacement",
          node_id: "N1",
          start: [0, 0, 0],
          end: [1, 0, 0]
        }
      }
    ],
    geometryPayloads: [],
    visibleObjectIds: ["object:displacement:N1"],
    overlays: [
      {
        id: "overlay:displacement",
        kind: "solver_result",
        data: { values: { N1: [3, 4, 8], N2: [0, 10, 0] } }
      }
    ],
    resultFields: [
      {
        id: "field:displacement",
        overlay_id: "overlay:displacement",
        load_case: "Hot",
        components: ["DX", "DY", "DZ", "magnitude"]
      }
    ],
    coloring: { loadCase: "Hot", fieldId: "field:displacement", component: "magnitude" }
  };
  const magnitude = createThreeSceneGraph(state);
  const dz = createThreeSceneGraph({
    ...state,
    coloring: { ...state.coloring, component: "DZ" }
  });

  assert.notEqual(
    magnitude.objectsByObjectId.get("object:displacement:N1").children[0].material.color.getHex(),
    dz.objectsByObjectId.get("object:displacement:N1").children[0].material.color.getHex()
  );
});

test("visual deformation scale updates the cached geometry", () => {
  const state = {
    bounds: [0, 0, 0, 1, 0.04, 0],
    geometryAssets: [{
      id: "asset:visual",
      format: "polyline",
      object_ids: ["object:visual"],
      generation_config: {
        base_points: [[0, 0, 0], [1, 0, 0]],
        points: [[0, 0, 0], [1, 0.04, 0]],
        source: "tuba.deformed_centerline.visual",
        visual_scale: 40
      }
    }],
    geometryPayloads: [],
    visibleObjectIds: ["object:visual"],
    visualDeformationScale: 40
  };
  const graph = createThreeSceneGraph(state);
  const line = graph.objectsByObjectId.get("object:visual");
  const cache = rendererModule.createSceneGraphCache(createThreeSceneGraph);
  const halfGraph = createThreeSceneGraph({ ...state, visualDeformationScale: 20 });

  applyVisualDeformationScale(graph.root, { ...state, visualDeformationScale: 20 });

  assert.strictEqual(cache.get(state), cache.get({ ...state, visualDeformationScale: 20 }));
  assert.ok(Math.abs(halfGraph.bounds[4] - 0.02) < 1e-6);
  assert.ok(Math.abs(line.geometry.getAttribute("position").getY(1) - 0.02) < 1e-6);
});

test("visual deformation scale updates a cached profile mesh with its source element result color", () => {
  const state = {
    bounds: [0, 0, 0, 1, 0.4, 1],
    geometryAssets: [
      {
        id: "asset:reference",
        format: "tube",
        object_ids: ["object:reference"],
        generation_config: { points: [[0, 0, 0], [1, 0, 0]], radius_m: 0.05, source: "tuba.element" }
      },
      {
        id: "asset:visual-profile",
        format: "mesh",
        object_ids: ["object:visual-profile"],
        generation_config: {
          base_vertices: [[0, 0, 0], [1, 0, 0], [0, 0, 1]],
          element_id: "pipe_1",
          vertices: [[0, 0, 0], [1, 0.4, 0], [0, 0, 1]],
          faces: [[0, 1, 2]],
          source: "tuba.deformed_analysis_mesh.profile",
          visual_scale: 40
        }
      }
    ],
    geometryPayloads: [],
    overlays: [{
      kind: "solver_result",
      visible: true,
      data: { values: { "object:element:pipe_1": 100 }, legend: { range: { min: 0, max: 100 } } }
    }],
    resultFields: [],
    visibleObjectIds: ["object:reference", "object:visual-profile"],
    visualDeformationScale: 40
  };
  const graph = createThreeSceneGraph(state);
  const mesh = graph.objectsByObjectId.get("object:visual-profile");
  const reference = graph.objectsByObjectId.get("object:reference");

  applyVisualDeformationScale(graph.root, { ...state, visualDeformationScale: 20 });

  assert.equal(mesh.morphTargetInfluences[0], 0.5);
  assert.equal(mesh.material.color.getHex(), colorForScalarValue(100, { range: { min: 0, max: 100 } }));
  rendererModule.setDeformationPreviewMode(graph, true);
  assert.equal(mesh.visible, false);
  assert.equal(reference.visible, false);
  rendererModule.setDeformationPreviewMode(graph, true);
  rendererModule.setDeformationPreviewMode(graph, false);
  assert.equal(mesh.visible, true);
  assert.equal(reference.visible, true);
});

test("moment vectors render a signed axis and right-hand-rule rotation at the result node", () => {
  const graph = createThreeSceneGraph({
    ...fixtureState(),
    geometryAssets: [
      {
        id: "geometry:reaction-moment:N1",
        format: "vector",
        bounds: [0, 0, 0, 1, 0, 0],
        object_ids: ["object:reaction-moment:N1"],
        generation_config: {
          source: "tuba.result_state",
          result_type: "reaction_moment",
          start: [2, 3, 4],
          end: [3, 3, 4]
        }
      }
    ],
    geometryPayloads: [],
    visibleObjectIds: ["object:reaction-moment:N1"]
  });

  const moment = graph.objectsByObjectId.get("object:reaction-moment:N1");
  assert.deepEqual(moment.position.toArray(), [2, 3, 4]);
  assert.deepEqual(moment.children.map((child) => child.name), [
    "moment-axis",
    "moment-rotation-arc",
    "moment-rotation-head"
  ]);
  assert.equal(moment.children[0].type, "ArrowHelper");
  assert.equal(moment.children[1].geometry.type, "TubeGeometry");
  assert.equal(moment.children[2].geometry.type, "ConeGeometry");

  const [, arc, head] = moment.children;
  const headDirection = new Vector3(0, 1, 0).applyQuaternion(head.quaternion);
  const headBase = head.position.clone().addScaledVector(headDirection, -head.geometry.parameters.height / 2);
  const arcEnd = arc.geometry.parameters.path.getPoint(1);
  assert.ok(headBase.distanceTo(arcEnd) < 1e-12, "The arc must meet the arrowhead base, not protrude through its tip");
  assert.ok(new Vector3().crossVectors(arcEnd, headDirection).normalize().distanceTo(new Vector3(0, 1, 0)) < 1e-12);

  const worldAxis = new Vector3(0, 1, 0).applyQuaternion(moment.quaternion);
  assert.ok(worldAxis.distanceTo(new Vector3(1, 0, 0)) < 1e-12);
});

test("scene graph visibility updates hide cached renderables without rebuilding", () => {
  const state = fixtureState();
  const graph = createThreeSceneGraph(state);

  rendererModule.updateSceneGraphVisibility?.(graph, {
    ...state,
    visibleObjectIds: ["object:pipe"]
  });

  assert.equal(graph.objectsByObjectId.get("object:pipe").visible, true);
  assert.equal(graph.objectsByObjectId.get("object:mesh-line").visible, false);
  assert.equal(graph.renderedObjectCount, 1);
});

test("standard camera views preserve the fitted target and clear the geometry", () => {
  const camera = new OrthographicCamera(-1, 1, 1, -1, 0.1, 1000);
  camera.userData.viewportAspect = 1;
  const controls = { target: new Vector3(), update() {} };

  // An 8 x 4 x 4 box: long in X, so its diagonal is much larger than anything
  // visible when looking down X.
  setCameraToStandardView(camera, [0, -2, -1, 8, 2, 3], controls, "positiveX");

  assert.deepEqual(controls.target.toArray(), [4, 0, 1]);
  assert.ok(camera.position.x > controls.target.x);
  assert.ok(camera.far > camera.near);
  // Far enough that no geometry sits behind the camera plane.
  assert.ok(camera.position.distanceTo(controls.target) > 4);
});

test("the graph is bounded by what it drew, not by what the assets declare", () => {
  // Deformed geometry is baked at its authored visual scale and rescaled at draw
  // time, so the declared bounds describe an envelope far larger than the shape
  // on screen. Framing that envelope left the model at a fraction of the frame.
  const graph = createThreeSceneGraph({
    bounds: [-50, -50, -50, 50, 50, 50],
    geometryAssets: [
      {
        id: "asset:pipe",
        format: "tube",
        object_ids: ["object:pipe"],
        bounds: [-50, -50, -50, 50, 50, 50],
        generation_config: { points: [[0, 0, 0], [1, 0, 0]], radius_m: 0.05 }
      }
    ],
    geometryPayloads: [],
    visibleObjectIds: ["object:pipe"],
    objects: [{ id: "object:pipe", kind: "pipe" }]
  });

  assert.equal(graph.renderedObjectCount, 1);
  const span = graph.bounds[3] - graph.bounds[0];
  assert.ok(span > 0.9 && span < 1.5, `drawn span was ${span}, not the declared 100`);
});

test("display vectors do not shrink structural geometry during camera fit", () => {
  const graph = createThreeSceneGraph({
    bounds: [0, -0.05, -0.05, 1, 0.05, 100],
    geometryAssets: [
      {
        id: "asset:pipe",
        format: "tube",
        object_ids: ["object:pipe"],
        generation_config: { points: [[0, 0, 0], [1, 0, 0]], radius_m: 0.05 }
      },
      {
        id: "asset:reaction",
        format: "vector",
        object_ids: ["object:reaction"],
        generation_config: { start: [0, 0, 0], end: [0, 0, 100], source: "tuba.solver_results" }
      }
    ],
    geometryPayloads: [],
    visibleObjectIds: ["object:pipe", "object:reaction"],
    objects: [
      { id: "object:pipe", kind: "pipe" },
      { id: "object:reaction", kind: "reaction_vector" }
    ]
  });

  assert.equal(graph.renderedObjectCount, 2);
  assert.ok(graph.bounds[5] - graph.bounds[2] < 1, `vector expanded fit bounds to ${graph.bounds}`);
});

test("the frustum fits what the view can see, not the bounding sphere", () => {
  const camera = new OrthographicCamera(-1, 1, 1, -1, 0.1, 1000);
  camera.userData.viewportAspect = 1;
  const controls = { target: new Vector3(), update() {} };

  // Looking down +X, the silhouette is the 4 x 4 YZ face: half-extents of 2.
  // Sizing from half the AABB diagonal (4.899) instead put the box at a third
  // of the frame with the rest of the viewport empty.
  setCameraToStandardView(camera, [0, -2, -1, 8, 2, 3], controls, "positiveX");
  assert.ok(camera.top > 2 && camera.top < 2.5, `top was ${camera.top}`);
  assert.ok(camera.right > 2 && camera.right < 2.5, `right was ${camera.right}`);

  // Looking down +Z the silhouette is the 8 x 4 XY face, so the same bounds
  // must produce a wider frustum. One fit for every axis cannot do this.
  setCameraToStandardView(camera, [0, -2, -1, 8, 2, 3], controls, "positiveZ");
  assert.ok(camera.top > 4, `+Z top was ${camera.top}`);
});

test("a wide viewport is fitted on its binding axis", () => {
  const wide = new OrthographicCamera(-1, 1, 1, -1, 0.1, 1000);
  wide.userData.viewportAspect = 3;
  const tall = new OrthographicCamera(-1, 1, 1, -1, 0.1, 1000);
  tall.userData.viewportAspect = 0.5;
  const controls = () => ({ target: new Vector3(), update() {} });

  // Silhouette down +X is 4 wide by 4 high. A 3:1 viewport is limited by
  // height; a 1:2 viewport is limited by width and must grow taller to hold it.
  setCameraToStandardView(wide, [0, -2, -1, 8, 2, 3], controls(), "positiveX");
  setCameraToStandardView(tall, [0, -2, -1, 8, 2, 3], controls(), "positiveX");
  assert.ok(tall.top > wide.top, `tall ${tall.top} should exceed wide ${wide.top}`);
  assert.ok(Math.abs(wide.right / wide.top - 3) < 1e-9);
});

test("camera fit keeps scene bounds clear of an open left controls dock", () => {
  const camera = new OrthographicCamera(-1, 1, 1, -1, 0.1, 1000);
  camera.userData.viewportAspect = 1440 / 852;
  camera.userData.viewportSize = { width: 1440, height: 852 };
  camera.userData.viewportInsets = { left: 296 };
  const bounds = [0, -2, -1, 8, 2, 3];

  fitCameraToBounds(camera, bounds);
  camera.updateMatrixWorld(true);
  const screenXs = [];
  for (const x of [bounds[0], bounds[3]]) for (const y of [bounds[1], bounds[4]]) for (const z of [bounds[2], bounds[5]]) {
    const projected = new Vector3(x, y, z).project(camera);
    screenXs.push((projected.x + 1) * 1440 / 2);
  }

  assert.ok(Math.min(...screenXs) > 296, `left edge ${Math.min(...screenXs)} was behind the controls dock`);
});

test("dock centering survives orthographic zoom and resize without resetting pan", () => {
  const camera = new OrthographicCamera(-1, 1, 1, -1, 0.1, 1000);
  const bounds = [0, -2, -1, 8, 2, 3];
  resizeCameraViewport(camera, 1440, 852, { left: 296 });
  const fit = fitCameraToBounds(camera, bounds);
  const target = new Vector3(...fit.target);
  const projectedX = (point, width) => {
    camera.updateMatrixWorld(true);
    return (point.clone().project(camera).x + 1) * width / 2;
  };
  assert.ok(Math.abs(projectedX(target, 1440) - 868) < 1e-6);
  zoomCameraBy(camera, 2);
  assert.ok(Math.abs(projectedX(target, 1440) - 868) < 1e-6);
  resizeCameraViewport(camera, 1200, 720, { left: 296 });
  assert.ok(Math.abs(projectedX(target, 1200) - 748) < 1e-6);
  assert.equal(camera.zoom, 2);
  camera.position.x += 0.2;
  const pannedPosition = camera.position.clone();
  resizeCameraViewport(camera, 1000, 720, { left: 296 });
  assert.deepEqual(camera.position, pannedPosition);
  resizeCameraViewport(camera, 1000, 720);
  const reset = fitCameraToBounds(camera, bounds);
  assert.ok(Math.abs(projectedX(new Vector3(...reset.target), 1000) - 500) < 1e-6);
});

test("standard Z camera views use stable up vectors", () => {
  const camera = new OrthographicCamera(-1, 1, 1, -1, 0.1, 1000);
  camera.userData.viewportAspect = 1;
  const controls = { target: new Vector3(), update() {} };

  setCameraToStandardView(camera, [-1, -1, -1, 1, 1, 1], controls, "positiveZ");
  assert.deepEqual(camera.up.toArray(), [0, 1, 0]);
  setCameraToStandardView(camera, [-1, -1, -1, 1, 1, 1], controls, "negativeZ");
  assert.deepEqual(camera.up.toArray(), [0, 1, 0]);
  assert.deepEqual(STANDARD_VIEW_DIRECTIONS.negativeZ, [0, 0, -1]);
});

test("camera reset restores the canonical Z-up engineering orientation after a Z view", () => {
  const camera = new OrthographicCamera(-1, 1, 1, -1, 0.1, 1000);
  camera.userData.viewportAspect = 1;
  const controls = { target: new Vector3(), update() {} };

  setCameraToStandardView(camera, [-1, -1, -1, 1, 1, 1], controls, "positiveZ");
  fitCameraToBounds(camera, [-1, -1, -1, 1, 1, 1], controls);

  assert.deepEqual(camera.up.toArray(), [0, 0, 1]);
  assert.deepEqual(camera.getWorldDirection(new Vector3()).toArray().map((value) => Number(value.toFixed(3))), [-0.642, 0.642, -0.418]);
});

test("orthographic zoom clamps and updates the projection matrix", () => {
  const camera = new OrthographicCamera(-2, 2, 2, -2, 0.1, 1000);
  camera.zoom = 19;
  camera.updateProjectionMatrix();
  const before = camera.projectionMatrix.elements.slice();

  zoomCameraBy(camera, 2);

  assert.equal(camera.zoom, 20);
  assert.notDeepEqual(camera.projectionMatrix.elements, before);
  zoomCameraBy(camera, 0.001);
  assert.equal(camera.zoom, 0.05);
});

test("section box clipping planes retain interior fragments and reject exterior fragments", () => {
  const planes = sectionBoxClippingPlanes({
    min: [-1, -2, -3],
    max: [4, 5, 6]
  });

  assert.equal(planes.length, 6);
  assert.ok(planes.every((plane) => plane.distanceToPoint(new Vector3(0, 0, 0)) >= 0));
  for (const point of [
    new Vector3(7, 0, 0),
    new Vector3(-2, 0, 0),
    new Vector3(0, 6, 0),
    new Vector3(0, -3, 0),
    new Vector3(0, 0, 7),
    new Vector3(0, 0, -4)
  ]) {
    assert.ok(planes.some((plane) => plane.distanceToPoint(point) < 0));
  }
});

test("section box clipping applies and removes planes on root mesh and line materials", () => {
  const root = new Group();
  const mesh = new Mesh(new BoxGeometry(1, 1, 1), [new MeshBasicMaterial(), new MeshBasicMaterial()]);
  const line = new Line();
  line.material = [new LineBasicMaterial(), new LineBasicMaterial()];
  root.add(mesh, line);
  const graph = { root };

  applySectionBoxClipping(graph, { min: [-1, -1, -1], max: [1, 1, 1] });

  for (const material of [...mesh.material, ...line.material]) {
    assert.equal(material.clippingPlanes.length, 6);
  }

  applySectionBoxClipping(graph, undefined);

  for (const material of [...mesh.material, ...line.material]) {
    assert.equal(material.clippingPlanes, null);
  }
});

test("cut view never slices a label: one outside the box goes whole, one inside stays whole", () => {
  const root = new Group();
  const inside = new Sprite();
  inside.position.set(0, 0, 0);
  const outside = new Sprite();
  outside.position.set(3, 0, 0);
  const glyph = new Group();
  glyph.position.set(0.8, 0, 0);
  const badge = new Sprite();
  badge.position.set(0.5, 0, 0); // world x = 1.3, past the box
  glyph.add(badge);
  root.add(inside, outside, glyph);
  const graph = { root };

  applySectionBoxClipping(graph, { min: [-1, -1, -1], max: [1, 1, 1] });
  for (const sprite of [inside, outside, badge]) assert.equal(sprite.material.clippingPlanes, null);
  assert.equal(inside.material.visible, true);
  assert.equal(outside.material.visible, false);
  assert.equal(badge.material.visible, false, "anchored on the badge itself, not its glyph");
  // Material, not object, visibility: the layer and Show values toggles own
  // object.visible and must not be overwritten.
  assert.equal(outside.visible, true);

  // A drag that widens the box brings the label back with no rebuild.
  applySectionBoxClipping(graph, { min: [-1, -1, -1], max: [4, 1, 1] });
  assert.equal(outside.material.visible, true);
  applySectionBoxClipping(graph, null);
  assert.ok([inside, outside, badge].every((sprite) => sprite.material.visible));
});

test("cut view draws an outline of its box that is never clipped, picked or counted", () => {
  const graph = createThreeSceneGraph(fixtureState());
  const bounds = [...graph.bounds];
  const renderables = graph.renderableObjects.length;
  applySectionBoxClipping(graph, undefined);
  assert.equal(graph.cutOutline, undefined, "no outline while the cut is off");

  applySectionBoxClipping(graph, { min: [0.5, -1, -1], max: [1.5, 1, 1] });
  const outline = graph.cutOutline;
  assert.ok(outline);
  assert.equal(outline.visible, true);
  assert.equal(outline.parent, graph.scene, "in the scene, outside the clipped root");
  assert.deepEqual(outline.box.min.toArray(), [0.5, -1, -1]);
  assert.deepEqual(outline.box.max.toArray(), [1.5, 1, 1]);
  assert.equal(outline.material.depthTest, false);
  assert.equal(outline.material.clippingPlanes, null);
  assert.equal(graph.renderableObjects.length, renderables);
  assert.deepEqual(graph.bounds, bounds);

  applySectionBoxClipping(graph, null);
  assert.equal(outline.visible, false);
});

// Commit a narrow cut that excludes a pipe, then drag a handle outward: the pipe
// stayed hidden until release, and a graph rebuilt under the cut did not even
// contain it. The graph is built uncut and the preview flips visibility.
test("dragging a committed cut outward brings back what it culled, with no rebuild", () => {
  const pipe = (id, x) => ({ id: `object:${id}`, kind: "pipe", name: id, geometry_asset_id: `asset:${id}`, layer_ids: [`layer:${id}`] });
  const asset = (id, x) => ({
    id: `asset:${id}`, format: "tube", bounds: [x, -0.05, -0.05, x + 1, 0.05, 0.05], object_ids: [`object:${id}`],
    generation_config: { points: [[x, 0, 0], [x + 1, 0, 0]], radius_m: 0.05 }
  });
  const loaded = createViewerState({ scene: {
    scene_id: "scene:cut",
    objects: [pipe("near", 0), pipe("far", 5), pipe("hidden", 5)],
    geometry_assets: [asset("near", 0), asset("far", 5), asset("hidden", 5)],
    overlays: []
  } });
  const narrow = { mode: "custom", min: [-0.5, -1, -1], max: [1.5, 1, 1] };
  const state = applySectionBox(setLayerVisibility(loaded, "layer:hidden", false), narrow);
  assert.deepEqual(state.visibleObjectIds, ["object:near"]);

  const cache = rendererModule.createSceneGraphCache(createThreeSceneGraph, disposeThreeSceneGraph);
  const graph = cache.get(state);
  rendererModule.updateSceneGraphVisibility(graph, state);
  const far = graph.objectsByObjectId.get("object:far");
  assert.ok(far, "built although the committed box culls it");
  assert.equal(far.visible, false);

  rendererModule.previewSectionBoxVisibility(graph, state, { min: [-0.5, -1, -1], max: [5.5, 1, 1] });
  assert.equal(far.visible, true, "the widened preview reaches it");
  assert.notEqual(graph.objectsByObjectId.get("object:hidden")?.visible, true, "a hidden layer stays hidden");
  rendererModule.previewSectionBoxVisibility(graph, state, narrow);
  assert.equal(far.visible, false);

  // Released wide: the commit needs no rebuild either.
  const wide = applySectionBox(state, { mode: "custom", min: [-0.5, -1, -1], max: [5.5, 1, 1] });
  assert.equal(cache.get(wide), graph);
  cache.clear();
});

test("section box clipping keeps a crossing pipe in the coarse scene graph", () => {
  const state = fixtureState();
  state.sectionBox = { min: [0.5, -1, -1], max: [1.5, 1, 1] };
  const graph = createThreeSceneGraph(state);

  assert.ok(graph.objectsByObjectId.get("object:pipe"));
  applySectionBoxClipping(graph, state.sectionBox);
  const planes = graph.objectsByObjectId.get("object:pipe").material.clippingPlanes;
  assert.equal(planes.length, 6);
  assert.ok(planes.every((plane) => plane.distanceToPoint(new Vector3(1, 0, 0)) >= 0));
  for (const point of [new Vector3(0, 0, 0), new Vector3(2, 0, 0)]) {
    assert.ok(planes.some((plane) => plane.distanceToPoint(point) < 0));
  }
});

test("leaving deformation preview is allowed even when the graph lost its preview", () => {
  const { canSetDeformationPreview } = rendererModule;
  const withPreview = { deformationPreview: {}, renderableObjects: [] };

  assert.equal(canSetDeformationPreview(withPreview, true), true);
  assert.equal(canSetDeformationPreview({ renderableObjects: [] }, true), false, "nothing to preview");
  assert.equal(
    canSetDeformationPreview({ deformationPreview: {}, renderableObjects: [{ userData: { sectionDeformation: {} } }] }, true),
    false,
    "a section rotation needs its frames left alone"
  );

  // A graph rebuilt between pointerdown and pointerup carries no preview. The
  // exit must not depend on one, or the flag stays set and every later render
  // re-hides the undeformed reference geometry.
  for (const graph of [withPreview, { renderableObjects: [] }, null, undefined]) {
    assert.equal(canSetDeformationPreview(graph, false), true);
  }
});

test("pickRenderedObject uses Three.js raycasting metadata", () => {
  const graph = createThreeSceneGraph({
    bounds: [-1, -1, -1, 1, 1, 1],
    geometryAssets: [
      {
        id: "geometry:marker",
        format: "marker",
        bounds: [0, 0, 0, 0, 0, 0],
        object_ids: ["object:marker"],
        generation_config: { point: [0, 0, 0], radius_m: 0.2 }
      }
    ],
    geometryPayloads: [],
    visibleObjectIds: ["object:marker"]
  });
  const camera = new PerspectiveCamera(45, 1, 0.1, 100);
  camera.up.set(0, 0, 1);
  camera.position.set(0, -4, 0);
  camera.lookAt(0, 0, 0);
  camera.updateMatrixWorld();
  graph.camera = camera;

  // One pixel off centre: the ray down the axis hits the sphere's pole vertex
  // exactly, which three.js reports as a miss.
  assert.equal(pickRenderedObject(graph, { x: 51, y: 51 }, { width: 100, height: 100 }), "object:marker");
  const hit = pickRenderedPoint(graph, { x: 51, y: 51 }, { width: 100, height: 100 });
  assert.equal(hit.objectId, "object:marker");
  assert.equal(hit.point.length, 3);
  assert.ok(hit.point.every(Number.isFinite));
});

test("pickRenderedObject skips dense TUYAU glyph instances", () => {
  const state = fixtureState();
  state.geometryAssets.push({
    id: "geometry:dense-tuyau",
    format: "tuyau_subpoint_glyphs",
    bounds: [-1, -1, -1, 1, 1, 1],
    object_ids: ["object:dense-tuyau"],
    generation_config: {
      starts: [[0, 0, 0]],
      ends: [[0, 0, 0.1]],
      values: [1]
    }
  });
  state.visibleObjectIds.push("object:dense-tuyau");
  const graph = createThreeSceneGraph(state);
  const denseGlyphs = graph.objectsByObjectId.get("object:dense-tuyau");
  denseGlyphs.raycast = () => {
    throw new Error("dense glyph raycast should not run");
  };
  const camera = new PerspectiveCamera(45, 1, 0.1, 100);
  camera.position.set(0, -4, 0);
  camera.lookAt(0, 0, 0);
  camera.updateMatrixWorld();
  graph.camera = camera;

  assert.doesNotThrow(() => pickRenderedObject(graph, { x: 50, y: 50 }, { width: 100, height: 100 }));
});

test("pickRenderedObject selects nothing when the cursor misses", () => {
  const graph = createThreeSceneGraph({
    bounds: [-1, -1, -1, 1, 1, 1],
    geometryAssets: [
      {
        id: "geometry:marker",
        format: "marker",
        bounds: [0, 0, 0, 0, 0, 0],
        object_ids: ["object:marker"],
        generation_config: { point: [0, 0, 0], radius_m: 0.1 }
      }
    ],
    geometryPayloads: [],
    visibleObjectIds: ["object:marker"]
  });
  const camera = new PerspectiveCamera(45, 1, 0.1, 100);
  camera.position.set(0, -4, 0);
  camera.lookAt(0, 0, 0);
  camera.updateMatrixWorld();
  graph.camera = camera;

  assert.equal(pickRenderedObject(graph, { x: 0, y: 0 }, { width: 100, height: 100 }), null);
});

// The app's camera: orthographic, 10 m of height over 500 px, so 1 px = 0.02 m.
// Screen x runs along world +X and screen y down world -Z. The marker is aimed
// at 2 px off centre, clear of the sphere's pole vertex (a raycast miss).
const PICK_VIEWPORT = { width: 500, height: 500 };
const AT_MARKER = { x: 252, y: 252 };
function pickGraph(assets) {
  const graph = createThreeSceneGraph({
    bounds: [-5, -5, -5, 5, 5, 5],
    geometryAssets: assets,
    geometryPayloads: [],
    visibleObjectIds: assets.flatMap((asset) => asset.object_ids)
  });
  const camera = new OrthographicCamera(-5, 5, 5, -5, 0.1, 100);
  camera.up.set(0, 0, 1);
  camera.position.set(0, -10, 0);
  camera.lookAt(0, 0, 0);
  camera.updateMatrixWorld();
  graph.camera = camera;
  return graph;
}
const PICK_MARKER = {
  id: "geometry:marker",
  format: "marker",
  bounds: [0, 0, 0, 0, 0, 0],
  object_ids: ["object:marker"],
  generation_config: { point: [0, 0, 0], radius_m: 0.2 }
};

test("sizing samples and FE nodes stay screen-sized and pick locally while targets retain geometry", () => {
  const samples = [.0006, .078].map((radius, index) => ({
    id: `geometry:mesh_size:mesh:${index}`, format: "point", bounds: [-radius,-radius,-radius,radius,radius,radius],
    object_ids: [`object:mesh_size:mesh:${index}`],
    generation_config: { source: "tuba.analysis_mesh.review", point: [index,0,0], radius_m: radius, color: index ? "#2563eb" : "#e65a28" }
  }));
  const target = { ...PICK_MARKER, id: "geometry:mesh_target:mesh:sphere", object_ids: ["object:mesh_target"],
    generation_config: { source: "tuba.analysis_mesh.review", point: [2,0,0], radius_m: .2 } };
  const node = { ...PICK_MARKER, id: "geometry:analysis_mesh:mesh:node:N1", object_ids: ["object:node"],
    generation_config: { source: "tuba.analysis_mesh.node", point: [3,0,0], radius_m: .0075 } };
  const graph = pickGraph([...samples, target, node]);
  for (const sample of samples) {
    const marker = graph.objectsByObjectId.get(sample.object_ids[0]);
    assert.equal(marker.isPoints, true);
    assert.equal(marker.material.size, 9);
    assert.equal(marker.material.customProgramCacheKey(), "tuba-point-ball");
    assert.equal(marker.material.sizeAttenuation, false);
    assert.equal(marker.material.color.getHexString(), sample.generation_config.color.slice(1));
  }
  assert.equal(graph.objectsByObjectId.get("object:mesh_target").geometry.parameters.radius, .2);
  const feNode = graph.objectsByObjectId.get("object:node");
  assert.equal(feNode.isPoints, true);
  assert.equal(feNode.material.size, 4);
  assert.equal(feNode.material.customProgramCacheKey(), "tuba-point-dot");
  assert.equal(feNode.material.sizeAttenuation, false);
  for (const zoom of [.25, 1, 4]) {
    graph.camera.zoom = zoom;
    assert.equal(pickRenderedObject(graph, {x:253,y:250}, PICK_VIEWPORT), samples[0].object_ids[0]);
    assert.equal(pickRenderedObject(graph, {x:240,y:250}, PICK_VIEWPORT), null);
  }
  disposeThreeSceneGraph(graph);
});

test("pickRenderedObject does not let a line off the cursor steal the pick", () => {
  const graph = pickGraph([
    PICK_MARKER,
    // 25 px above the marker on screen, and nearer the camera.
    {
      id: "geometry:line",
      format: "polyline",
      bounds: [-5, -0.5, 0.5, 5, -0.5, 0.5],
      object_ids: ["object:line"],
      generation_config: { points: [[-5, -0.5, 0.5], [5, -0.5, 0.5]] }
    }
  ]);

  assert.equal(pickRenderedObject(graph, AT_MARKER, PICK_VIEWPORT), "object:marker");
  // A one-pixel line still has to be hittable without pixel-perfect aim.
  assert.equal(pickRenderedObject(graph, { x: 250, y: 228 }, PICK_VIEWPORT), "object:line");
});

test("pickRenderedObject ignores geometry the section box has cut away", () => {
  const graph = pickGraph([PICK_MARKER]);

  applySectionBoxClipping(graph, { min: [-1, -1, -1], max: [1, 1, 1] });
  assert.equal(pickRenderedObject(graph, AT_MARKER, PICK_VIEWPORT), "object:marker");
  applySectionBoxClipping(graph, { min: [1, 1, 1], max: [2, 2, 2] });
  assert.equal(pickRenderedObject(graph, AT_MARKER, PICK_VIEWPORT), null);
});

test("pickRenderedObject resolves parts nested below an asset's direct children", () => {
  // A moment is Group > ArrowHelper > Line: the axis line is a grandchild.
  const graph = pickGraph([
    {
      id: "geometry:moment",
      format: "vector",
      bounds: [0, 0, 0, 0, 0, 2],
      object_ids: ["object:moment"],
      generation_config: { start: [0, 0, 0], end: [0, 0, 2], vector_kind: "moment" }
    }
  ]);

  assert.equal(pickRenderedObject(graph, { x: 250, y: 225 }, PICK_VIEWPORT), "object:moment");
});

// A support sits on the pipe it marks and its block is drawn inside the pipe
// wall, so the nearer pipe surface took the click. A click meant to move the
// selection landed on the pipe that was already selected and looked like it did
// nothing.
test("pickRenderedObject prefers a support glyph over the pipe it sits inside", () => {
  const graph = pickGraph([
    {
      id: "geometry:pipe",
      format: "tube",
      bounds: [-5, -0.1, -0.1, 5, 0.1, 0.1],
      object_ids: ["object:pipe"],
      generation_config: { points: [[-5, 0, 0], [5, 0, 0]], radius_m: 0.1, source: "tuba.element" }
    },
    {
      id: "geometry:support",
      format: "point",
      bounds: [0, 0, 0, 0, 0, 0],
      object_ids: ["object:support"],
      generation_config: { point: [0, 0, 0], source: "tuba.support", support_type: "anchor" }
    }
  ]);

  assert.equal(pickRenderedObject(graph, AT_MARKER, PICK_VIEWPORT), "object:support");
});

test("pickRenderedObject prefers a load arrow over the pipe beneath it", () => {
  const graph = pickGraph([
    {
      id: "geometry:pipe",
      format: "tube",
      bounds: [-5, -0.1, -0.1, 5, 0.1, 0.1],
      object_ids: ["object:pipe"],
      generation_config: { points: [[-5, 0, 0], [5, 0, 0]], radius_m: 0.1, source: "tuba.element" }
    },
    {
      id: "geometry:load",
      format: "vector",
      bounds: [0, 0, 0, 0, 0, 2],
      object_ids: ["object:load"],
      generation_config: { start: [0, 0, 0], end: [0, 0, 2], source: "tuba.solver_results", vector_kind: "force" }
    }
  ]);

  assert.equal(pickRenderedObject(graph, AT_MARKER, PICK_VIEWPORT), "object:load");
});

test("applyHoverHighlight records hover target and marks matching materials", () => {
  const graph = createThreeSceneGraph(fixtureState());

  applyHoverHighlight(graph, "object:pipe");

  assert.equal(graph.highlightedObjectId, "object:pipe");
  assert.equal(graph.objectsByObjectId.get("object:pipe").userData.hovered, true);
});

test("applyHoverHighlight only revisits the previous and next objects", () => {
  const graph = createThreeSceneGraph(fixtureState());
  applyHoverHighlight(graph, "object:pipe");
  graph.objectsByObjectId.get("object:box").traverse = () => {
    throw new Error("unrelated objects must not be traversed");
  };

  assert.doesNotThrow(() => applyHoverHighlight(graph, "object:issue"));
  assert.equal(graph.objectsByObjectId.get("object:pipe").userData.hovered, false);
  assert.equal(graph.objectsByObjectId.get("object:issue").userData.hovered, true);
});

test("clearing hover preserves an existing selection highlight", () => {
  const graph = createThreeSceneGraph(fixtureState());
  applySelectionHighlight(graph, ["object:pipe"]);

  applyHoverHighlight(graph, "object:pipe");
  applyHoverHighlight(graph, "object:issue");

  const pipe = graph.objectsByObjectId.get("object:pipe");
  assert.equal(pipe.userData.selected, true);
  assert.equal(pipe.userData.hovered, false);
  // The outline pass draws the highlight; the pipe itself is never repainted.
  assert.equal(pipe.material.emissive.getHex(), 0);
});

test("a support glyph is outlined, never repainted, when hovered or selected", () => {
  const graph = createThreeSceneGraph({
    bounds: [0, -1, -1, 2, 1, 1],
    geometryAssets: [
      {
        id: "geometry:support:anchor",
        format: "point",
        bounds: [0, 0, 0, 0, 0, 0],
        object_ids: ["object:support:anchor"],
        generation_config: { point: [0, 0, 0], source: "tuba.support", support_type: "anchor" }
      }
    ],
    geometryPayloads: [],
    visibleObjectIds: ["object:support:anchor"]
  });
  const glyph = graph.objectsByObjectId.get("object:support:anchor");
  const block = glyph.children.find((part) => part.userData.supportPart === "fixed-block");
  assert.equal(glyph.userData.outlineSurface, true, "a support has a surface to outline");
  assert.equal(glyph.userData.highlightOutline, undefined, "and gets no box");

  applyHoverHighlight(graph, "object:support:anchor");
  applySelectionHighlight(graph, ["object:support:anchor"]);
  assert.equal(block.userData.hovered, true);
  assert.equal(block.userData.selected, true);
  assert.equal(block.material.color.getHex(), SUPPORT_NEUTRAL, "colour carries the support role, not the selection");

  applyHoverHighlight(graph, null);
  applySelectionHighlight(graph, []);
  assert.equal(block.material.color.getHex(), SUPPORT_NEUTRAL);
});

test("a load arrow is boxed, never repainted, when selected", () => {
  // The outline pass traces meshes only, and an arrow is mostly a line.
  const graph = createThreeSceneGraph({
    bounds: [0, -1, -1, 0, 1, 1],
    geometryAssets: [
      {
        id: "geometry:load",
        format: "vector",
        bounds: [0, 0, 0, 0, 0, 1],
        object_ids: ["object:load"],
        generation_config: { start: [0, 0, 0], end: [0, 0, 1], source: "applied_loads", vector_kind: "force", magnitude: 100 }
      }
    ],
    geometryPayloads: [],
    visibleObjectIds: ["object:load"]
  });
  const arrow = graph.objectsByObjectId.get("object:load");
  assert.equal(arrow.userData.outlineSurface, false);

  applySelectionHighlight(graph, ["object:load"]);
  assert.equal(arrow.userData.highlightOutline.visible, true);
  assert.equal(arrow.cone.material.color.getHex(), 0xc026d3, "the authored colour stays");
  assert.equal(arrow.line.material.color.getHex(), 0xc026d3);

  applySelectionHighlight(graph, []);
  assert.equal(arrow.userData.highlightOutline.visible, false);
});

test("support glyphs take role colours in Build and follow a stage move without a rebuild", () => {
  const supports = [
    { id: "joint", support_type: "custom", blocked_dof: [1, 1, 1, 0, 0, 0] },
    { id: "spring", support_type: "custom", stiffness_matrix: [0, 0, 1e5, 0, 0, 0] },
    { id: "moved", support_type: "anchor", imposed_displacement: [0, 0, 0.08, 0, 0, 0] }
  ];
  const graph = createThreeSceneGraph({
    stage: "build",
    bounds: [0, -1, -1, 4, 1, 1],
    geometryAssets: supports.map((support, index) => ({
      id: `geometry:support:${support.id}`,
      format: "point",
      bounds: [index, 0, 0, index, 0, 0],
      object_ids: [`object:support:${support.id}`],
      generation_config: { point: [index, 0, 0], source: "tuba.support", ...support }
    })),
    geometryPayloads: [],
    visibleObjectIds: supports.map(({ id }) => `object:support:${id}`)
  });
  const colourOf = (id, role) => graph.objectsByObjectId.get(`object:support:${id}`)
    .children.find((part) => part.userData.supportPart === role).material.color.getHexString();
  const build = (part) => SUPPORT_BUILD_COLORS[part].slice(1);
  assert.equal(colourOf("joint", "restraint-cone"), build("restraint"));
  assert.equal(colourOf("spring", "spring-coil"), build("spring"));
  assert.equal(colourOf("moved", "prescribed-displacement"), build("prescribed"));
  assert.equal(colourOf("moved", "prescribed-shaft"), build("prescribed"));

  // A studio with nothing solved shows the build bundle in both stages, so a
  // stage move reaches the glyphs without a new graph.
  applySupportStage(graph, "review");
  const neutral = SUPPORT_REVIEW_COLORS.restraint.slice(1);
  for (const [id, role] of [["joint", "restraint-cone"], ["spring", "spring-coil"], ["moved", "prescribed-displacement"], ["moved", "prescribed-shaft"]]) {
    assert.equal(colourOf(id, role), neutral, `${id} ${role} is neutral in Review`);
  }
  applySupportStage(graph, "build");
  assert.equal(colourOf("joint", "restraint-cone"), build("restraint"));
  // The ground is not a role: a gold plate under a spring would claim a
  // restraint the spring does not have.
  assert.equal(colourOf("spring", "ground-hatch"), SUPPORT_GROUND_COLOR.slice(1));
});

test("a line mark that shares its selection with an outlined surface gets no box", () => {
  // A contact marker with its support, a component's axis arrows with the
  // component: the surface's outline already shows them.
  const graph = createThreeSceneGraph({
    bounds: [0, -1, -1, 2, 1, 1],
    objects: [{ id: "object:support:s", kind: "support" }, { id: "object:load", kind: "applied_load" }],
    geometryAssets: [
      { id: "geometry:support:s", format: "point", bounds: [0, 0, 0, 0, 0, 0], object_ids: ["object:support:s"],
        generation_config: { point: [0, 0, 0], source: "tuba.support", support_type: "anchor" } },
      { id: "geometry:support:s:arrow", format: "vector", bounds: [0, 0, 0, 0, 0, 1], object_ids: ["object:support:s"],
        generation_config: { start: [0, 0, 0], end: [0, 0, 1], vector_kind: "force" } },
      { id: "geometry:load", format: "vector", bounds: [1, 0, 0, 1, 0, 1], object_ids: ["object:load"],
        generation_config: { start: [1, 0, 0], end: [1, 0, 1], vector_kind: "force" } }
    ],
    geometryPayloads: [],
    visibleObjectIds: ["object:support:s", "object:load"]
  });
  const shared = graph.root.children.find((object) => object.userData.assetId === "geometry:support:s:arrow");
  assert.equal(shared.userData.highlightOutline, undefined, "the support's outline covers its arrow");
  assert.ok(graph.objectsByObjectId.get("object:load").userData.highlightOutline, "a load selected on its own is boxed");
});

test("applySelectionHighlight marks focused clash review objects", () => {
  const graph = createThreeSceneGraph(fixtureState());

  applySelectionHighlight(graph, ["object:pipe", "object:issue"]);

  assert.deepEqual(graph.selectedObjectIds, ["object:pipe", "object:issue"]);
  assert.equal(graph.objectsByObjectId.get("object:pipe").userData.selected, true);
  assert.equal(graph.objectsByObjectId.get("object:issue").userData.selected, true);
  assert.equal(graph.objectsByObjectId.get("object:box").userData.selected, false);
});

test("prepareAssetRenderConfig colors active stress objects by scalar value", () => {
  const state = {
    activeLoadCase: "Hot",
    activeResultStateId: "result_state:Hot",
    overlays: [
      {
        id: "overlay:stress",
        kind: "solver_result",
        data: {
          result_type: "stress",
          result_state_id: "result_state:Hot",
          load_case: "Hot",
          values: { "object:cool": 6000000, "object:hot": 57000000 },
          range: { min: 6000000, max: 57000000 },
          unit: "Pa"
        }
      }
    ]
  };

  const cool = prepareAssetRenderConfig({ id: "asset:cool", format: "tube", object_ids: ["object:cool"] }, {}, state);
  const hot = prepareAssetRenderConfig({ id: "asset:hot", format: "tube", object_ids: ["object:hot"] }, {}, state);

  assert.ok(Number.isInteger(cool.color));
  assert.ok(Number.isInteger(hot.color));
  assert.notEqual(cool.color, hot.color);
});

test("prepareAssetRenderConfig applies vector and visual deformation display scales", () => {
  const state = {
    resultVectorScales: { displacement: 10, reaction: 0.5 },
    visualDeformationScale: 80
  };

  const displacement = prepareAssetRenderConfig(
    {
      id: "asset:displacement",
      format: "vector",
      object_ids: ["object:displacement"],
      generation_config: { result_type: "displacement", start: [0, 0, 0], end: [0, 0, 0.01] }
    },
    {},
    state
  );
  const visual = prepareAssetRenderConfig(
    {
      id: "asset:visual_deformed",
      format: "polyline",
      object_ids: ["object:visual"],
      generation_config: {
        source: "tuba.deformed_centerline.visual",
        visual_scale: 40,
        base_points: [[0, 0, 0], [1, 0, 0]],
        points: [[0, 0, 0], [1, 0.04, 0]]
      }
    },
    {},
    state
  );
  const missingBase = prepareAssetRenderConfig(
    {
      id: "asset:visual_deformed_missing_base",
      format: "polyline",
      object_ids: ["object:visual-missing-base"],
      generation_config: {
        source: "tuba.deformed_centerline.visual",
        visual_scale: 40,
        points: [[0, 0, 0], [1, 0.04, 0]]
      }
    },
    {},
    state
  );

  assert.deepEqual(displacement.end, [0, 0, 0.1]);
  assert.deepEqual(visual.points[1], [1, 0.08, 0]);
  assert.equal(visual.visual_scale_display_only, 80);
  assert.deepEqual(missingBase.points[1], [1, 0.04, 0]);
  assert.equal(missingBase.visual_scale_display_only, 40);
});

test("label renders as a camera-facing sprite and stays out of picking", () => {
  const state = fixtureState();
  state.geometryAssets.push({ id: "geometry:label:low", format: "label", bounds: [1, 1, 1, 1, 1, 1], object_ids: ["label:low"], generation_config: { text: "Low friction", position: [1, 1, 1], height: 0.2 } });
  state.visibleObjectIds.push("label:low");
  const canvasFactory = () => ({ width: 0, height: 0, getContext: () => ({ fillRect() {}, fillText() {}, measureText: (text) => ({ width: text.length * 32 }) }) });
  const graph = createThreeSceneGraph(state, { canvasFactory });
  const label = graph.objectsByObjectId.get("label:low");
  assert.equal(label.isSprite, true);
  assert.deepEqual(label.position.toArray(), [1, 1, 1]);
  assert.equal(label.scale.y, 0.2);
  assert.equal(label.userData.pickable, false);
});

test("label fails visibly when no canvas is available", () => {
  const state = fixtureState();
  state.geometryAssets = [{ id: "geometry:label", format: "label", object_ids: ["label"], generation_config: { text: "Label", position: [0, 0, 0], height: 1 } }];
  state.visibleObjectIds = ["label"];
  const graph = createThreeSceneGraph(state, { canvasFactory: () => null });
  assert.equal(graph.renderedObjectCount, 0);
  assert.match(graph.diagnostics[0].message, /2D canvas context/);
});

test("scene graph disposal releases each label texture once", () => {
  const state = fixtureState();
  const labelAsset = { id: "geometry:label", format: "label", object_ids: ["label"], generation_config: { text: "Label", position: [0, 0, 0], height: 1 } };
  state.geometryAssets = [labelAsset, { ...labelAsset, id: "geometry:label-copy", object_ids: ["label-copy"] }];
  state.visibleObjectIds = ["label", "label-copy"];
  const canvasFactory = () => ({ width: 0, height: 0, getContext: () => ({ fillRect() {}, fillText() {}, measureText: () => ({ width: 100 }) }) });
  const graph = createThreeSceneGraph(state, { canvasFactory });
  const texture = graph.objectsByObjectId.get("label").material.map;
  graph.objectsByObjectId.get("label-copy").material.map = texture;
  let disposals = 0;
  texture.dispose = () => { disposals += 1; };

  disposeThreeSceneGraph(graph);

  assert.equal(disposals, 1);
});

test("moment glyphs use their own scale independently of reaction forces", () => {
  const state = { resultVectorScales: { reaction: 0.5, moment: 2 } };
  for (const [type, length] of [["reaction_force", 0.5], ["reaction_moment", 2]]) {
    const config = prepareAssetRenderConfig({ id: type, format: "vector", generation_config: {
      result_type: type, start: [0, 0, 0], end: [1, 0, 0]
    } }, {}, state);
    assert.deepEqual(config.end, [length, 0, 0]);
  }
});

test("line_load_comb assets create an arrow group and crest rail tagged with object IDs", () => {
  const state = fixtureState();
  const combAsset = {
    id: "geometry:line-load",
    format: "line_load_comb",
    bounds: [0, 0, 0, 2, 0, 0.5],
    object_ids: ["object:line-load"],
    generation_config: {
      source: "tuba.applied_loads",
      color: "#0284c7",
      vector_kind: "line_load",
      arrow_starts: [[0, 0, 0.5], [1, 0, 0.5], [2, 0, 0.5]],
      arrow_ends: [[0, 0, 0], [1, 0, 0], [2, 0, 0]],
      crest_points: [[0, 0, 0.5], [1, 0, 0.5], [2, 0, 0.5]],
      value_npm: 300,
      direction: [0, 0, -1]
    }
  };
  state.geometryAssets.push(combAsset);
  state.objects = [{ id: "object:line-load", kind: "applied_load", geometry_asset_id: combAsset.id, layer_ids: ["design:loads"] }];
  state.visibleObjectIds = ["object:line-load"];

  const graph = createThreeSceneGraph(state);
  const rendered = graph.objectsByObjectId.get("object:line-load");
  assert.ok(rendered);
  assert.equal(rendered.isGroup, true);
  const arrows = rendered.children.filter((c) => c.name === "line-load-arrow");
  const crest = rendered.children.find((c) => c.name === "line-load-crest");
  assert.equal(arrows.length, 3);
  assert.ok(crest);
  assert.equal(crest.isLine, true);
  assert.equal(rendered.userData.primaryObjectId, "object:line-load");
  const volume = rendered.userData.pickVolume;
  assert.equal(volume.material.visible, false, "the pick volume does not obscure the model");
  assert.ok(volume.geometry.parameters.height >= 0.125, "the planar comb has depth along Y");
  graph.camera = new OrthographicCamera(-2, 2, 2, -2, 0.1, 100);
  graph.camera.up.set(0, 0, 1);
  graph.camera.position.set(0, -10, 0);
  graph.camera.lookAt(0, 0, 0);
  graph.camera.updateMatrixWorld();
  const pickAt = point => {
    const projected = point.clone().project(graph.camera);
    return pickRenderedObject(graph, { x: (projected.x + 1) * 250, y: (1 - projected.y) * 250 }, PICK_VIEWPORT);
  };
  assert.equal(pickAt(new Vector3(0.5, 0, 0.25)), "object:line-load", "space between arrows selects the load");
  applyHoverHighlight(graph, "object:line-load");
  assert.equal(rendered.userData.highlightOutline.visible, true);
  applyHoverHighlight(graph, null);
  assert.equal(rendered.userData.highlightOutline.visible, false);
  applySelectionHighlight(graph, ["object:line-load"]);
  assert.equal(rendered.userData.highlightOutline.visible, true);
  graph.camera.position.set(10, 0, 0);
  graph.camera.lookAt(0, 0, 0);
  graph.camera.updateMatrixWorld();
  assert.equal(pickAt(new Vector3(0.5, 0.055, 0.25)), "object:line-load", "depth remains selectable edge-on");
  assert.equal(pickAt(new Vector3(0.5, 0.3, 0.25)), null, "outside the volume still misses");
  graph.camera.position.set(0, -10, 0);
  graph.camera.lookAt(0, 0, 0);
  graph.camera.updateMatrixWorld();
  const support = new Mesh(new BoxGeometry(0.05, 0.05, 0.05), new MeshBasicMaterial());
  support.position.set(0.5, 0, 0.25);
  support.userData = { primaryObjectId: "support", pickPriority: 1 };
  graph.root.add(support);
  graph.renderableObjects.push(support);
  assert.equal(pickAt(new Vector3(0.5, 0, 0.25)), "support", "a real support wins over the load volume");
  applySectionBoxClipping(graph, { min: [1.5, -1, -1], max: [3, 1, 1] });
  assert.equal(pickAt(new Vector3(0.5, 0, 0.25)), null, "clipped load volumes cannot be selected");
});

test("applied loads render badges for force, moment, and line loads", () => {
  const state = fixtureState();
  const canvasCalls = [];
  const canvasFactory = () => ({
    width: 0,
    height: 0,
    getContext: () => ({
      font: "",
      fillStyle: "",
      strokeStyle: "",
      lineWidth: 0,
      textAlign: "",
      textBaseline: "",
      fillRect() {},
      beginPath() {},
      roundRect() {},
      fill() {},
      stroke() {},
      measureText: (text) => ({ width: text.length * 20 }),
      fillText(text) {
        canvasCalls.push(text);
      }
    })
  });

  const forceAsset = {
    id: "geometry:force",
    format: "vector",
    bounds: [0, 0, 0, 0, 0, 1],
    object_ids: ["object:force"],
    generation_config: {
      source: "tuba.applied_loads",
      vector_kind: "force",
      start: [0, 0, 1],
      end: [0, 0, 0],
      components: [0, 0, -3500],
      unit: "N"
    }
  };
  const momentAsset = {
    id: "geometry:moment",
    format: "vector",
    bounds: [0, 0, 0, 0, 1, 0],
    object_ids: ["object:moment"],
    generation_config: {
      source: "tuba.applied_loads",
      vector_kind: "moment",
      start: [0, 0, 0],
      end: [0, 1, 0],
      components: [0, 500, 0],
      unit: "N*m"
    }
  };
  const combAsset = {
    id: "geometry:line-load",
    format: "line_load_comb",
    bounds: [0, 0, 0, 2, 0, 0.5],
    object_ids: ["object:line-load"],
    generation_config: {
      source: "tuba.applied_loads",
      vector_kind: "line_load",
      arrow_starts: [[0, 0, 0.5], [1, 0, 0.5]],
      arrow_ends: [[0, 0, 0], [1, 0, 0]],
      crest_points: [[0, 0, 0.5], [1, 0, 0.5]],
      value_npm: 350,
      show_badge: true
    }
  };

  state.geometryAssets.push(forceAsset, momentAsset, combAsset);
  state.objects = [
    { id: "object:force", kind: "applied_load", geometry_asset_id: forceAsset.id, layer_ids: ["design:loads"] },
    { id: "object:moment", kind: "applied_load", geometry_asset_id: momentAsset.id, layer_ids: ["design:loads:moments"] },
    { id: "object:line-load", kind: "applied_load", geometry_asset_id: combAsset.id, layer_ids: ["design:loads"] }
  ];
  state.visibleObjectIds = ["object:force", "object:moment", "object:line-load"];

  const graph = createThreeSceneGraph(state, { canvasFactory });
  const renderedForce = graph.objectsByObjectId.get("object:force");
  const renderedMoment = graph.objectsByObjectId.get("object:moment");
  const renderedComb = graph.objectsByObjectId.get("object:line-load");

  assert.ok(renderedForce);
  assert.ok(renderedMoment);
  assert.ok(renderedComb);

  const forceBadge = renderedForce.children.find((c) => c.userData?.loadPart === "load-badge");
  const momentBadge = renderedMoment.children.find((c) => c.userData?.loadPart === "load-badge");
  const combBadge = renderedComb.children.find((c) => c.userData?.loadPart === "load-badge");

  assert.ok(forceBadge);
  assert.equal(forceBadge.isSprite, true);
  assert.equal(forceBadge.userData.pickable, false);

  assert.ok(momentBadge);
  assert.equal(momentBadge.isSprite, true);

  assert.ok(combBadge);
  assert.equal(combBadge.isSprite, true);

  assert.ok(canvasCalls.includes("F = 3.5 kN"));
  assert.ok(canvasCalls.includes("M = 500 N·m"));
  assert.ok(canvasCalls.includes("q = 350 N/m"));
});

test("Show values hides the load and friction badges in place, without a rebuild", () => {
  const root = new Group();
  const arrow = new Group();
  const force = new Sprite();
  force.userData.loadPart = "load-badge";
  const friction = new Sprite();
  friction.userData.supportPart = "friction-badge";
  const shaft = new Mesh(new BoxGeometry(1, 1, 1), new MeshBasicMaterial());
  arrow.add(force, shaft);
  root.add(arrow, friction);
  const graph = { root };

  applyValueLabelVisibility(graph, false);
  assert.equal(force.visible, false);
  assert.equal(friction.visible, false);
  assert.equal(shaft.visible, true, "only the value labels go, not the glyph");
  applyValueLabelVisibility(graph, true);
  assert.equal(force.visible, true);
  assert.equal(friction.visible, true);
});


test("a field's own surface is coloured per vertex on the field's legend, untinted", () => {
  // A mixed run's one von Mises field spans a solid (per vertex) and a pipe
  // (per element), on one range of 0..100.
  const state = {
    ...fixtureState(),
    objects: [{ id: "object:solid", kind: "volume_stress_field" }],
    geometryAssets: [{
      id: "geometry:solid", format: "mesh", bounds: [0, 0, 0, 1, 1, 0], object_ids: ["object:solid"],
      generation_config: { source: "tuba.result_state.volume_stress", vertices: [[0, 0, 0], [1, 0, 0], [0, 1, 0]], faces: [[0, 1, 2]],
        vertex_values: [10, 20, 30], legend: { range: { min: 10, max: 30 } } }
    }],
    geometryPayloads: [],
    visibleObjectIds: ["object:solid"],
    overlays: [{ id: "overlay:stress", kind: "solver_result", object_ids: ["object:solid", "object:element:P"],
      data: { result_type: "stress", values: { "object:solid": 30, "object:element:P": 100 }, legend: { range: { min: 0, max: 100 } } } }],
    resultFields: [{ id: "field:stress", overlay_id: "overlay:stress", load_case: "Hot", components: ["magnitude"], range: [0, 100] }],
    coloring: { loadCase: "Hot", fieldId: "field:stress", component: "magnitude" },
    colorChannel: "results"
  };
  const mesh = createThreeSceneGraph(state).objectsByObjectId.get("object:solid");
  assert.equal(mesh.material.color.getHex(), 0xffffff, "vertex colours are not multiplied by the peak tint");
  const first = mesh.geometry.getAttribute("color");
  const expected = new Color(colorForScalarValue(10, getScalarLegend(state)));
  assert.ok(Math.abs(first.getX(0) - expected.r) < 1e-6 && Math.abs(first.getZ(0) - expected.b) < 1e-6,
    "10 is read on the field's 0..100 scale, not the surface's own 10..30");
});

// A badge sized in world units grew with every zoom step until it hid the small
// tee being zoomed into. It now keeps 20 CSS px whatever the zoom.
test("value badges keep one on-screen height at any zoom, and fits ignore it", () => {
  const state = fixtureState();
  state.geometryAssets.push({ id: "geometry:force", format: "vector", bounds: [0, 0, 0, 0, 0, 1], object_ids: ["object:force"],
    generation_config: { source: "tuba.applied_loads", vector_kind: "force", start: [0, 0, 1], end: [0, 0, 0], components: [0, 0, -3500], unit: "N" } });
  state.objects = [{ id: "object:force", kind: "applied_load", geometry_asset_id: "geometry:force", layer_ids: ["design:loads"] }];
  state.visibleObjectIds = ["object:force"];
  const canvases = [];
  const canvasFactory = () => {
    const canvas = { width: 0, height: 0, getContext: () => ({ measureText: (text) => ({ width: text.length * 20 }), fillRect() {}, fillText() {} }) };
    canvases.push(canvas);
    return canvas;
  };
  const graph = createThreeSceneGraph(state, { canvasFactory });
  const badge = graph.objectsByObjectId.get("object:force").children.find((part) => part.userData.loadPart === "load-badge");
  const viewport = { width: 800, height: 600 };
  const camera = new OrthographicCamera();
  resizeCameraViewport(camera, viewport.width, viewport.height);
  fitCameraToBounds(camera, graph.bounds);
  graph.camera = camera;
  const pixelsTall = () => {
    scaleValueLabels(graph, viewport);
    camera.updateMatrixWorld();
    const anchor = badge.getWorldPosition(new Vector3());
    const top = anchor.clone().add(new Vector3(0, badge.scale.y, 0).applyQuaternion(camera.quaternion));
    return (top.project(camera).y - anchor.project(camera).y) * viewport.height / 2;
  };

  assert.ok(Math.abs(pixelsTall() - 20) < 1e-9);
  zoomCameraBy(camera, 8);
  assert.ok(Math.abs(pixelsTall() - 20) < 1e-9, "zoomed in, the badge is no taller on screen");
  assert.ok(Math.abs(badge.scale.x / badge.scale.y - canvases[0].width / canvases[0].height) < 1e-9, "the text is not stretched");

  // Zoomed out the badge is metres wide in world units; a fit must not frame it.
  const fitted = graph.depthBounds;
  zoomCameraBy(camera, 0.05 / 8);
  pixelsTall();
  const scale = badge.scale.clone();
  updateSceneGraphBounds(graph, { ...state, visibleObjectIds: [...state.visibleObjectIds] });
  assert.deepEqual(graph.depthBounds, fitted);
  assert.ok(badge.scale.equals(scale), "measuring leaves the badge its size");
});


test("a solid's result surface follows the shape the members are drawn at", () => {
  // Solved 0.01 m up; the exaggerated state is drawn x10 by the slider.
  const geometryStates = [
    { id: "overlay:shape:physical", kind: "geometry_state", data: { id: "shape:physical", purpose: "engineering" } },
    { id: "overlay:shape:visual", kind: "geometry_state", data: { id: "shape:visual", purpose: "visualization", visual_scale: 10 } }
  ];
  const state = (activeGeometryStateId) => ({
    ...fixtureState(),
    objects: [{ id: "object:solid", kind: "volume_displacement_field" }],
    geometryAssets: [{
      id: "geometry:solid", format: "mesh", bounds: [0, 0, 0, 1, 1, 0.01], object_ids: ["object:solid"],
      generation_config: { source: "tuba.result_state.volume_displacement", deformation_scale: 1,
        vertices: [[0, 0, 0.01], [1, 0, 0.01], [0, 1, 0.01]], base_vertices: [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
        faces: [[0, 1, 2]], vertex_values: [0.01, 0.01, 0.01] }
    }],
    geometryPayloads: [],
    visibleObjectIds: ["object:solid"],
    geometryStates,
    activeGeometryStateId,
    visualDeformationScale: 10
  });
  // Meshes morph on the GPU between the solved and the base shape: an influence
  // of 1 - scale, so -9 draws x10 and 0 draws the solved shape as it is.
  const influence = (graph) => graph.objectsByObjectId.get("object:solid").morphTargetInfluences[0];
  assert.equal(influence(createThreeSceneGraph(state("shape:visual"))), -9, "x10 with the exaggerated members");
  assert.equal(influence(createThreeSceneGraph(state("shape:physical"))), 0, "true scale with the actual deformation, whatever the slider reads");
});

// A section loop extruded along X, laid out like section_mesh.py: the start loop,
// then the end loop, sides as quads, caps as fans.
function prismAsset(id, loop, length = 2) {
  const n = loop.length;
  const vertices = [...loop.map(([y, z]) => [0, y, z]), ...loop.map(([y, z]) => [length, y, z])];
  const faces = [];
  for (let i = 0; i < n; i += 1) faces.push([i, (i + 1) % n, n + (i + 1) % n, n + i]);
  for (let i = 1; i < n - 1; i += 1) faces.push([0, i + 1, i], [n, n + i, n + i + 1]);
  return {
    id: `geometry:${id}`,
    format: "mesh",
    bounds: [0, -0.1, -0.1, length, 0.1, 0.1],
    object_ids: [`object:${id}`],
    generation_config: { source: "tuba.element", points: [[0, 0, 0], [length, 0, 0]], vertices, faces }
  };
}

test("a profiled member draws its corner lines, and a round one does not", () => {
  const square = [[-0.03, -0.03], [0.03, -0.03], [0.03, 0.03], [-0.03, 0.03]];
  const round = Array.from({ length: 16 }, (_, i) => [0.03 * Math.cos(i * Math.PI / 8), 0.03 * Math.sin(i * Math.PI / 8)]);
  const graph = createThreeSceneGraph({
    bounds: [0, -1, -1, 2, 1, 1],
    geometryAssets: [prismAsset("rhs", square), prismAsset("chs", round)],
    geometryPayloads: [],
    visibleObjectIds: ["object:rhs", "object:chs"]
  });
  const corners = (id) => graph.objectsByObjectId.get(id).children.find((part) => part.userData.memberCorners);

  const rhs = graph.objectsByObjectId.get("object:rhs");
  const lines = corners("object:rhs");
  // Four corners along the member, and no rings at its ends.
  assert.equal(lines.geometry.index.count, 8);
  // Sharing the mesh's positions is what keeps them on a deformed member.
  assert.equal(lines.geometry.getAttribute("position"), rhs.geometry.getAttribute("position"));
  // Deformation rewrites those positions, so the lines' own bounding sphere goes
  // stale; culling by it dropped corners still on screen.
  assert.equal(lines.frustumCulled, false);
  assert.equal(corners("object:chs"), undefined, "a 16-gon has no corner sharp enough to draw");
});

test("an FE mesh is coloured per member like Gmsh, not with the default member tint", () => {
  const ref = "element:L1";
  const asset = (id, source, format, extra) => ({ id: `geometry:${id}`, format, object_ids: [`object:${id}`],
    generation_config: { source, source_ref: ref, ...extra } });
  const node = asset("n", "tuba.analysis_mesh.node", "point", { point: [0,0,0] });
  const element = asset("e", "tuba.analysis_mesh.element", "polyline", { points: [[0,0,0],[1,0,0]] });
  const state = { colorChannel: "model", modelColorBy: "default", objects: [
    { id: "object:L1", kind: "rack_member", entity_ref: ref },
    { id: "object:n", kind: "analysis_mesh_node", entity_ref: ref },
    { id: "object:e", kind: "analysis_mesh_element", entity_ref: ref }] };
  assert.equal(prepareAssetRenderConfig(element, {}, state).color, undefined);
  const graph = pickGraph([node, element]);
  const nodeColor = graph.objectsByObjectId.get("object:n").material.color.getHex();
  assert.equal(graph.objectsByObjectId.get("object:e").material.color.getHex(), nodeColor);
  assert.notEqual(nodeColor, 0x059669);
  disposeThreeSceneGraph(graph);
});
