import assert from "node:assert/strict";
import test from "node:test";
import { BoxGeometry, Mesh, MeshBasicMaterial, OrthographicCamera, Vector3 } from "three";
import * as rendererModule from "../src/renderer.js";
import { fitSelection } from "../src/selection.js";
import {
  createCameraFitController,
  fitCameraToBounds,
  orbitCameraBy,
  resizeCameraViewport
} from "../src/renderer.js";

const towerBounds = [-1.04, -5.44, -0.03, 1.04, 5.04, 6.97];
const teeBounds = [-0.09, -0.2, 6.6, 0.09, 0, 6.89];

function corners(bounds) {
  return Array.from({ length: 8 }, (_, index) => new Vector3(
    bounds[index & 1 ? 3 : 0],
    bounds[index & 2 ? 4 : 1],
    bounds[index & 4 ? 5 : 2]
  ));
}

function assertDepthContains(camera, bounds) {
  camera.updateMatrixWorld(true);
  for (const point of corners(bounds)) {
    const depth = point.clone().project(camera).z;
    assert.ok(depth > -1 && depth < 1,
      `${point.toArray()} is cut by the camera at projected depth ${depth}`);
  }
}

function cameraFixture() {
  const camera = new OrthographicCamera(-1, 1, 1, -1, 0.01, 10000);
  resizeCameraViewport(camera, 562, 586);
  const controls = { target: new Vector3(), update() {} };
  return { camera, controls, controller: createCameraFitController(camera, controls) };
}

test("fitting a small connection keeps the surrounding tower within camera depth", () => {
  const { camera, controls, controller } = cameraFixture();
  const state = { camera: { fitRequest: { id: 1, bounds: teeBounds } } };
  controller.apply(state, towerBounds);
  assert.ok(controls.target.distanceTo(new Vector3(0, -0.1, 6.745)) < 1e-12);
  const fittedHeight = (camera.top - camera.bottom) / camera.zoom;
  assert.ok(fittedHeight < 1, "the selected tee should still fill the view");
  assertDepthContains(camera, towerBounds);

  for (let step = 0; step < 48; step++) {
    orbitCameraBy(camera, controls.target, Math.PI / 12, step % 2 ? -0.09 : 0.09);
    controller.apply(state, towerBounds);
    assertDepthContains(camera, towerBounds);
    assert.equal((camera.top - camera.bottom) / camera.zoom, fittedHeight);
    assert.ok(controls.target.distanceTo(new Vector3(0, -0.1, 6.745)) < 1e-12);
  }
});

test("new geometry updates camera depth without resetting a focused view", () => {
  const { camera, controls, controller } = cameraFixture();
  const state = { camera: { fitRequest: { id: 1, bounds: teeBounds } } };
  controller.apply(state, teeBounds);
  camera.zoom = 3;
  camera.updateProjectionMatrix();
  camera.updateMatrixWorld(true);
  const targetBefore = controls.target.clone();
  const projectedBefore = targetBefore.clone().project(camera);
  const directionBefore = camera.getWorldDirection(new Vector3());

  controller.apply(state, towerBounds);

  assertDepthContains(camera, towerBounds);
  const projectedAfter = targetBefore.clone().project(camera);
  assert.ok(Math.abs(projectedAfter.x - projectedBefore.x) < 1e-9);
  assert.ok(Math.abs(projectedAfter.y - projectedBefore.y) < 1e-9);
  assert.ok(camera.getWorldDirection(new Vector3()).distanceTo(directionBefore) < 1e-12);
  assert.deepEqual(controls.target, targetBefore);
  assert.equal(camera.zoom, 3);
  assert.deepEqual(camera.userData.fitBounds, teeBounds);
});

test("opening the inspector keeps fitted geometry inside the smaller canvas", () => {
  const { camera } = cameraFixture();
  const bounds = [-5, -0.3, -0.3, 5, 0.3, 0.3];
  resizeCameraViewport(camera, 1280, 600);
  fitCameraToBounds(camera, bounds, null, "positiveZ");
  const position = camera.position.clone();
  resizeCameraViewport(camera, 560, 600);
  camera.updateMatrixWorld(true);
  for (const point of corners(bounds)) {
    const projected = point.project(camera);
    assert.ok(Math.abs(projected.x) < 1 && Math.abs(projected.y) < 1,
      `fitted geometry was cropped at ${projected.toArray()}`);
  }
  assert.deepEqual(camera.position, position);
});

test("an overlay inspector is excluded from the fitted viewport under CSS scaling", () => {
  const { camera } = cameraFixture();
  // Client dimensions are in CSS units; measured screen rectangles include
  // host zoom. The inspector overlays the right 320 of a 724 CSS-pixel canvas.
  const canvas = { clientWidth: 724, clientHeight: 600,
    getBoundingClientRect: () => ({ left: 240, right: 819.2, top: 40, bottom: 520, width: 579.2, height: 480 }) };
  const inspector = { hidden: false,
    getBoundingClientRect: () => ({ left: 563.2, right: 819.2, top: 40, bottom: 520, width: 256, height: 480 }) };
  const insets = rendererModule.getViewportInsets?.(canvas, { right: inspector }) ?? {};
  resizeCameraViewport(camera, 724, 600, insets);
  const bounds = [-5, -0.3, -0.3, 5, 0.3, 0.3];
  fitCameraToBounds(camera, bounds, null, "positiveZ");
  camera.updateMatrixWorld(true);
  for (const point of corners(bounds)) {
    const x = (point.project(camera).x + 1) * 724 / 2;
    assert.ok(x > 0 && x < 404, `geometry sits under the inspector at CSS X=${x}`);
  }
  inspector.hidden = true;
  const unobscured = rendererModule.getViewportInsets(canvas, { right: inspector });
  assert.deepEqual(unobscured, {});
  inspector.hidden = false;
  inspector.getBoundingClientRect = () => ({ left: 819.2, right: 1075.2, top: 40, bottom: 520, width: 256, height: 480 });
  assert.deepEqual(rendererModule.getViewportInsets(canvas, { right: inspector }), {},
    "a dock beside the canvas already reserves its own space");
});

test("scene depth follows the displayed deformation rather than cached asset bounds", () => {
  const state = {
    referenceGridVisible: false,
    visualDeformationScale: 1,
    objects: [{ id: "member", kind: "beam" }],
    geometryAssets: [{
      id: "member", format: "mesh", object_ids: ["member"], bounds: [0, 0, 0, 1, 1, 30],
      generation_config: {
        vertices: [[0, 0, 0], [1, 0, 30], [0, 1, 0]],
        base_vertices: [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
        faces: [[0, 1, 2]], source: "tuba.deformed_analysis_mesh.profile", visual_scale: 10
      }
    }],
    visibleObjectIds: ["member"], geometryPayloads: []
  };
  const graph = rendererModule.createThreeSceneGraph(state);
  assert.ok(Math.abs(graph.bounds[5] - 3) < 1e-5);
  const changed = { ...state, visualDeformationScale: 100 };
  rendererModule.applyVisualDeformationScale(graph.root, changed);
  rendererModule.updateSceneGraphBounds?.(graph, changed);
  assert.ok(Math.abs(graph.bounds[5] - 300) < 1e-5,
    `displayed tip reaches Z=300, but the camera still sees bounds ${graph.bounds}`);
  const { camera, controller } = cameraFixture();
  controller.apply({ camera: { fitRequest: { id: 1, bounds: [0, 0, 0, 1, 1, 1] } } },
    graph.bounds, graph.depthBounds);
  assertDepthContains(camera, [0, 0, 0, 1, 1, 300]);
});

test("reset-view bounds retain the animated structure when static markers remain visible", () => {
  const state = {
    referenceGridVisible: false, visualDeformationScale: 1, geometryPayloads: [],
    objects: [{ id: "member", kind: "beam" }], visibleObjectIds: ["member"],
    geometryAssets: [{ id: "member", format: "polyline", object_ids: ["member"],
      generation_config: { points: [[0, 0, 0], [1, 0, 30]], base_points: [[0, 0, 0], [1, 0, 0]],
        source: "tuba.deformed_analysis_mesh.element", visual_scale: 10 } }]
  };
  const graph = rendererModule.createThreeSceneGraph(state);
  assert.ok(graph.deformationPreview, "this case must exercise the fast preview path");
  graph.root.add(new Mesh(new BoxGeometry(0.1, 0.1, 0.1), new MeshBasicMaterial()));
  rendererModule.setDeformationPreviewMode(graph, true);
  const changed = { ...state, visualDeformationScale: 100 };
  rendererModule.applyVisualDeformationScale(graph.root, changed, { previewOnly: true });
  rendererModule.updateSceneGraphBounds(graph, changed);
  assert.ok(Math.abs(graph.bounds[5] - 300) < 1e-5,
    "the visible deformation preview must remain part of structural framing");
});

test("large vectors are retained in scene depth while structural framing excludes them", () => {
  const graph = rendererModule.createThreeSceneGraph({
    referenceGridVisible: false, geometryPayloads: [],
    objects: [{ id: "member", kind: "beam" }, { id: "arrow", kind: "vector" }],
    visibleObjectIds: ["member", "arrow"],
    geometryAssets: [
      { id: "member", format: "tube", object_ids: ["member"],
        generation_config: { points: [[0, 0, 0], [1, 0, 0]], radius_m: 0.05 } },
      { id: "arrow", format: "vector", object_ids: ["arrow"],
        generation_config: { start: [0, 0, 0], end: [0, 0, 1000] } }
    ]
  });
  assert.ok(graph.bounds[5] < 1, "an annotation must not make the structure tiny");
  const { camera, controller } = cameraFixture();
  controller.apply({ camera: {} }, graph.bounds, graph.depthBounds);
  assertDepthContains(camera, [0, 0, 0, 1, 0, 1000]);
});

test("selection fitting frames the rendered support rather than its zero-size asset bounds", () => {
  const state = {
    referenceGridVisible: false, geometryPayloads: [], selectedObjectIds: ["anchor"],
    objects: [{ id: "anchor", kind: "support", entity_ref: "support:anchor" }],
    visibleObjectIds: ["anchor"],
    geometryAssets: [{ id: "anchor", format: "point", object_ids: ["anchor"], bounds: [0, 0, 0, 0, 0, 0],
      generation_config: { point: [0, 0, 0], radius_m: 0.05, source: "tuba.support", support_type: "anchor", dof_states: Array(6).fill("fixed") } }]
  };
  const graph = rendererModule.createThreeSceneGraph(state);
  const { camera, controller } = cameraFixture();
  controller.apply(fitSelection(state), graph.bounds, graph.depthBounds, graph);
  camera.updateMatrixWorld(true);
  for (const point of corners(graph.bounds)) {
    const projected = point.project(camera);
    assert.ok(Math.abs(projected.x) < 1 && Math.abs(projected.y) < 1,
      `the rendered support was over-zoomed at ${projected.toArray()}`);
  }
});
