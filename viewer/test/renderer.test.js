import assert from "node:assert/strict";
import test from "node:test";
import { PerspectiveCamera } from "three";

import {
  SUPPORTED_RENDER_FORMATS,
  applyHoverHighlight,
  applySelectionHighlight,
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
  for (const format of ["tube", "polyline", "point", "vector", "marker", "aabb", "mesh"]) {
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

test("fitCameraToBounds targets scene center and computes a usable distance", () => {
  const camera = new PerspectiveCamera(45, 1, 0.1, 1000);
  const fit = fitCameraToBounds(camera, [0, -1, -0.5, 10, 1, 2]);

  assert.deepEqual(fit.target, [5, 0, 0.75]);
  assert.ok(fit.distance > 10);
  assert.ok(camera.far > camera.near);
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

test("applyHoverHighlight records hover target and marks matching materials", () => {
  const graph = createThreeSceneGraph(fixtureState());

  applyHoverHighlight(graph, "object:pipe");

  assert.equal(graph.highlightedObjectId, "object:pipe");
  assert.equal(graph.objectsByObjectId.get("object:pipe").userData.hovered, true);
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

  assert.deepEqual(displacement.end, [0, 0, 0.1]);
  assert.deepEqual(visual.points[1], [1, 0.08, 0]);
  assert.equal(visual.visual_scale_display_only, 80);
});
