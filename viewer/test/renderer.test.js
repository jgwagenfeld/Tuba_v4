import assert from "node:assert/strict";
import test from "node:test";
import { PerspectiveCamera, Vector3 } from "three";

import * as rendererModule from "../src/renderer.js";

import {
  SUPPORTED_RENDER_FORMATS,
  applyHoverHighlight,
  applySelectionHighlight,
  buildRenderableScene,
  createThreeSceneGraph,
  fitCameraToBounds,
  pickRenderedObject,
  prepareAssetRenderConfig
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

test("pipe geometry remains visible end-on as a hollow section", () => {
  const state = fixtureState();
  state.geometryAssets[0].generation_config.inner_radius_m = 0.04;

  const graph = createThreeSceneGraph(state);
  const pipe = graph.objectsByObjectId.get("object:pipe");

  assert.equal(pipe.isGroup, true);
  assert.equal(pipe.children.filter((child) => child.geometry?.type === "RingGeometry").length, 2);
  assert.equal(pipe.children.filter((child) => child.geometry?.type === "TubeGeometry").length, 2);
});

test("support points use a non-occluding engineering glyph", () => {
  const graph = createThreeSceneGraph({
    bounds: [-0.1, -0.1, -0.1, 0.1, 0.1, 0.1],
    geometryAssets: [
      {
        id: "geometry:support",
        format: "point",
        bounds: [0, 0, 0, 0, 0, 0],
        object_ids: ["object:support"],
        generation_config: { point: [0, 0, 0], source: "tuba.support" }
      }
    ],
    geometryPayloads: [],
    visibleObjectIds: ["object:support"]
  });

  const support = graph.objectsByObjectId.get("object:support");
  assert.equal(support.geometry.type, "OctahedronGeometry");
  assert.equal(support.material.wireframe, true);
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
