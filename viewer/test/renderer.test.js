import assert from "node:assert/strict";
import test from "node:test";
import { Box3, BoxGeometry, DoubleSide, Group, Line, LineBasicMaterial, Mesh, MeshBasicMaterial, OrthographicCamera, PerspectiveCamera, Vector3 } from "three";

import * as rendererModule from "../src/renderer.js";
import { colorForScalarValue } from "../src/resultReview.js";

import {
  SUPPORTED_RENDER_FORMATS,
  applyVisualDeformationScale,
  applyHoverHighlight,
  applySelectionHighlight,
  buildRenderableScene,
  createThreeSceneGraph,
  fitCameraToBounds,
  setCameraToStandardView,
  zoomCameraBy,
  STANDARD_VIEW_DIRECTIONS,
  pickRenderedObject,
  prepareAssetRenderConfig,
  sectionBoxClippingPlanes,
  applySectionBoxClipping
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
  for (const format of ["tube", "polyline", "point", "vector", "marker", "aabb", "mesh", "tuyau_subpoint_glyphs"]) {
    assert.ok(SUPPORTED_RENDER_FORMATS.has(format), `${format} is supported`);
  }
});

test("scene graph renders visible geometry with stable scene object metadata", () => {
  const graph = createThreeSceneGraph(fixtureState());

  assert.equal(graph.diagnostics.length, 0);
  assert.equal(graph.renderedObjectCount, 7);
  assert.ok(graph.objectsByObjectId.get("object:pipe"));
  assert.equal(graph.objectsByObjectId.get("object:pipe").userData.primaryObjectId, "object:pipe");
  assert.equal(graph.objectsByObjectId.get("object:issue").userData.assetId, "geometry:issue");
});

test("mesh vertex values render as a scalar-colored surface", () => {
  const state = fixtureState();
  const asset = state.geometryAssets.find((candidate) => candidate.id === "geometry:mesh");
  asset.generation_config.vertex_values = [10, 20, 30, 40];
  asset.generation_config.legend = { range: { min: 10, max: 40 }, color_map: "turbo" };

  const graph = createThreeSceneGraph(state);
  const mesh = graph.objectsByObjectId.get("object:mesh");

  assert.equal(mesh.material.vertexColors, true);
  assert.equal(mesh.geometry.getAttribute("color").count, 4);
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

test("section box reveals the internal volume-element edges", () => {
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
    { id: "rest-y", support_type: "rest" },
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
  assert.deepEqual(glyphs.map((glyph) => glyph.userData.supportGlyph), ["dof", "dof", "dof", "dof", "dof"]);
  assert.deepEqual(
    glyphs.map((glyph) => glyph.children.map((child) => child.userData.supportPart).filter(Boolean).sort().join(",")),
    [
      "fixed-block",
      "restraint-cone,restraint-cone",
      "restraint-cone,restraint-cone",
      "restraint-cone,restraint-cone,restraint-cone,restraint-cone,restraint-cone,restraint-cone",
      "restraint-cone,restraint-cone,restraint-cone,restraint-cone,restraint-rotation"
    ]
  );
  for (const glyph of glyphs) {
    const size = new Box3().setFromObject(glyph).getSize(new Vector3());
    assert.ok(Math.max(size.x, size.y, size.z) >= 0.15, `${glyph.userData.supportGlyph} remains visible`);
    for (const part of glyph.children) {
      assert.equal(part.material.wireframe, false);
      assert.equal(part.material.color.getHex(), 0xdaa520);
    }
  }
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
  assert.ok(Math.abs(blockSize.x - 0.1) < 1e-8, `fixed block width was ${blockSize.x}`);
  assert.equal(block.material.depthTest, true);
  assert.equal(block.material.depthWrite, false);
  assert.equal(block.material.transparent, true);
  assert.equal(block.material.opacity, 0.5);
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
  assert.equal(springParts.filter((part) => part.userData.supportPart === "spring-ring").length, 8);
  assert.equal(springParts.filter((part) => part.userData.supportPart === "spring-rotation").length, 1);
  assert.ok(springParts.every((part) => part.material.color.getHex() === 0x2563eb && part.material.wireframe === false));

  const prescribed = graph.objectsByObjectId.get("object:support:prescribed");
  assert.equal(prescribed.children.filter((part) => part.userData.supportPart === "restraint-cone").length, 2);
  const displacement = prescribed.children.find((part) => part.userData.supportPart === "prescribed-displacement");
  assert.ok(displacement);
  assert.equal(displacement.material.color.getHex(), 0xf97316);
  assert.equal(displacement.material.wireframe, false);
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

test("scene graph renders TUYAU sub-points as one instanced glyph batch", () => {
  const graph = createThreeSceneGraph({
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
    visibleObjectIds: ["object:tuyau"]
  });

  assert.equal(graph.diagnostics.length, 0);
  assert.equal(graph.renderedObjectCount, 1);
  const mesh = graph.objectsByObjectId.get("object:tuyau");
  assert.equal(mesh.isInstancedMesh, true);
  assert.equal(mesh.count, 2);
  assert.equal(mesh.material.vertexColors, false);
  assert.equal(mesh.instanceColor.count, 2);
});

test("fitCameraToBounds targets scene center and computes a usable distance", () => {
  const camera = new PerspectiveCamera(45, 1, 0.1, 1000);
  const fit = fitCameraToBounds(camera, [0, -1, -0.5, 10, 1, 2]);

  assert.deepEqual(fit.target, [5, 0, 0.75]);
  assert.ok(fit.distance > 10);
  assert.ok(camera.far > camera.near);
});

test("viewer defaults to an orthographic engineering camera", () => {
  const renderable = buildRenderableScene(fixtureState(), { width: 976, height: 525 });

  assert.equal(renderable.camera.isOrthographicCamera, true);
  assert.ok(renderable.camera.right > renderable.camera.left);
  assert.ok(renderable.camera.top > renderable.camera.bottom);
});

test("renderer sends requested selection bounds through the existing camera-fit pipeline", () => {
  const selectionBounds = [0, -0.05, -0.05, 2, 0.05, 0.05];
  const renderable = buildRenderableScene({
    ...fixtureState(),
    camera: { mode: "orbit", target: [1, 0, 0], distance: 2, fitRequest: { id: 1, bounds: selectionBounds } }
  });

  assert.deepEqual(renderable.camera.userData.fitBounds, selectionBounds);
  assert.deepEqual(renderable.controlsTarget.toArray(), [1, 0, 0]);
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

test("interaction mode temporarily hides detail geometry and restores visibility", () => {
  const graph = createThreeSceneGraph(fixtureState());

  rendererModule.setSceneGraphInteractionMode?.(graph, true);

  assert.equal(typeof rendererModule.setSceneGraphInteractionMode, "function");
  assert.equal(graph.objectsByObjectId.get("object:pipe").visible, true);
  assert.equal(graph.objectsByObjectId.get("object:box").visible, true);
  assert.equal(graph.objectsByObjectId.get("object:mesh-line").visible, false);
  assert.equal(graph.objectsByObjectId.get("object:node").visible, false);
  assert.equal(graph.objectsByObjectId.get("object:reaction").visible, false);

  rendererModule.setSceneGraphInteractionMode(graph, false);

  assert.equal(graph.objectsByObjectId.get("object:mesh-line").visible, true);
  assert.equal(graph.objectsByObjectId.get("object:node").visible, true);
  assert.equal(graph.objectsByObjectId.get("object:reaction").visible, true);
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

  assert.equal(pickRenderedObject(graph, { x: 50, y: 50 }, { width: 100, height: 100 }), "object:marker");
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

test("pickRenderedObject can skip projected fallback for hover misses", () => {
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

  assert.equal(
    pickRenderedObject(graph, { x: 0, y: 0 }, { width: 100, height: 100 }, { projectedFallback: false }),
    null
  );
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

  assert.equal(graph.objectsByObjectId.get("object:pipe").material.emissive.getHex(), 0xf59e0b);
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
