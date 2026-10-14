import { contactRecords, contactObjectId, contactForceMaxima, CONTACT_COLORS } from "./contactReview.js";
import { prescribedDisplacementText, SUPPORT_GROUND_COLOR, supportPartColors } from "./supportGlyphs.js";
import { sceneStage } from "./workflowState.js";
import { getUnitSystem } from "./units.js";
import * as THREE from "three";
import { textTextureSize, tubeTessellation, validateSceneBudget } from "./sceneBudget.js";
import { relatedSelectionIds, selectionKey } from "./reviewSelection.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { ViewHelper } from "three/examples/jsm/helpers/ViewHelper.js";
import { EffectComposer } from "three/examples/jsm/postprocessing/EffectComposer.js";
import { RenderPass } from "three/examples/jsm/postprocessing/RenderPass.js";
import { OutlinePass } from "three/examples/jsm/postprocessing/OutlinePass.js";
import { OutputPass } from "three/examples/jsm/postprocessing/OutputPass.js";
import {
  colorForScalarValue,
  getActiveResultState,
  getActiveShapeScale,
  getObjectScalarColor,
  fieldBodyState,
  getResultVectorScale,
  getScalarLegend,
  getVisualDeformationDisplayScale
} from "./resultReview.js";
import { bodyOpacityForObjectIds, hasSubpointValue, subpointModeSpec, subpointPassesThreshold, subpointThreshold, subpointThresholdValue } from "./bodies.js";
import { isSupportConfig, supportBlockedDofs } from "./supports.js";
import { getModelObjectColor } from "./modelColoring.js";
import { getVisibleObjectIds } from "./sceneLoader.js";
import { memberCornerEdges, splitSurfaceCreases } from "./surfaceGeometry.js";
import { TransparencyRenderer } from "./transparencyRenderer.js";
import { clampBoundsToSpan } from "./selection.js";

export const SUPPORTED_RENDER_FORMATS = new Set([
  "aabb",
  "cuboid",
  "cylinder",
  "label",
  "line",
  "line_load_comb",
  "marker",
  "mesh",
  "point",
  "polyline",
  "tube",
  "tube_envelope",
  "tuyau_subpoint_glyphs",
  "vector"
]);

const REFERENCE_GEOMETRY_COLOR = 0x9ca3af;
const REFERENCE_GEOMETRY_OPACITY = 0.32;

// Draw order for the x-ray sub-point batch. Above the analysis mesh (500) and
// the result annotations below it, and well under the load preview (1000) and
// the labels (1100) so the field never sits on top of something the reviewer
// is reading.
const SUBPOINT_XRAY_RENDER_ORDER = 520;

export const STANDARD_VIEW_DIRECTIONS = {
  iso: [1, -1, 0.65],
  positiveX: [1, 0, 0],
  negativeX: [-1, 0, 0],
  positiveY: [0, 1, 0],
  negativeY: [0, -1, 0],
  positiveZ: [0, 0, 1],
  negativeZ: [0, 0, -1]
};

export const WEBGL2_UNAVAILABLE = "viewer.webgl2_unavailable";
const isInspectionDiagnosticSource = source => ["tuba.interface_mapping", "tuba.analysis_mesh.review"].includes(source);

export function createThreeSceneGraph(sceneState, options = {}) {
  validateSceneBudget(sceneState, []);
  // Built for the uncut model. Cut view culls whole objects through state, and
  // a graph built without them could not show them again while a handle is
  // dragged outward; updateSceneGraphVisibility hides them instead, and the
  // live preview flips them back (previewSectionBoxVisibility).
  const state = sceneState.sectionBox && Array.isArray(sceneState.objects)
    ? { ...sceneState, visibleObjectIds: uncutVisibleObjectIds(sceneState) }
    : sceneState;
  const payloadsByAssetId = new Map((state.geometryPayloads ?? []).map((payload) => [payload.asset_id, payload]));
  const visibleIds = new Set(state.visibleObjectIds ?? []);
  const renderAssets = (state.geometryAssets ?? []).filter((asset) =>
    isAssetVisible(asset, visibleIds) &&
    assetMatchesActiveGeometryState(asset, payloadsByAssetId.get(asset.id) ?? {}, state.activeGeometryStateId));
  validateSceneBudget(state, renderAssets);
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(options.backgroundColor ?? 0xf8fafc);

  const root = new THREE.Group();
  root.name = "TubaSceneRoot";
  scene.add(root);

  const declaredBounds = normalizeBounds(state.bounds) ?? mergeAssetBounds(state.geometryAssets ?? []);

  const renderState = {
    ...state,
    textureBudget: { pixels: 0 },
    canvasFactory: options.canvasFactory ?? (() => globalThis.document?.createElement("canvas")),
    deformedReference: visibleDeformedReference(state, payloadsByAssetId, visibleIds)
  };
  const objectsByObjectId = new Map();
  const diagnostics = [];
  let renderedObjectCount = 0;

  for (const asset of renderAssets) {
    const payload = payloadsByAssetId.get(asset.id) ?? {};
    const result = createRenderableForAsset(asset, payload, renderState);
    if (result.diagnostic) {
      diagnostics.push(result.diagnostic);
    }
    if (!result.object) {
      continue;
    }
    setRenderMetadata(result.object, asset, result.format);
    if (isInspectionDiagnosticSource(asset.generation_config?.source)) {
      result.object.traverse(part => {
        part.renderOrder = 700;
        for (const material of Array.isArray(part.material) ? part.material : part.material ? [part.material] : []) {
          material.depthTest = false;
          material.depthWrite = false;
          material.transparent = true;
        }
      });
    }
    root.add(result.object);
    renderedObjectCount += 1;
    for (const objectId of asset.object_ids ?? []) {
      objectsByObjectId.set(objectId, result.object);
    }
  }

  addContactMarkers(root, state);
  const keysById = new Map((state.objects ?? []).map(o => [o.id, selectionKey(o)]));
  const structuralIds = new Set((state.objects ?? []).filter(o => String(selectionKey(o)).startsWith("element:")).map(o => o.id));
  const meshIds = new Set((state.objects ?? []).filter(o => String(o.kind).includes("analysis_mesh")).map(o => o.id));
  const surfaceKeys = new Set((state.objects ?? []).filter(o => structuralIds.has(o.id) &&
    !meshIds.has(o.id) && objectsByObjectId.has(o.id)).map(selectionKey));
  const objectsBySelectionKey = new Map();
  const lineMarks = [];
  for (const object of root.children) {
    for (const id of object.userData.objectIds ?? []) {
      const key = keysById.get(id) ?? id;
      if (!objectsBySelectionKey.has(key)) objectsBySelectionKey.set(key, new Set());
      objectsBySelectionKey.get(key).add(object);
    }
    const isStructure = (object.userData.objectIds ?? []).some(id => structuralIds.has(id));
    // One surface outline, not a cage around every underlying FE segment.
    const outlineStructure = isStructure && (object.userData.objectIds ?? []).some(id =>
      !meshIds.has(id) || !surfaceKeys.has(keysById.get(id)));
    // Selection never repaints: colour carries the results, input vs result and
    // the support roles, so the highlight is drawn around an object instead. A
    // surface gets the silhouette outline. A mark made only of lines - an arrow,
    // a load comb, a polyline - gets a box, because the outline pass traces
    // meshes only.
    const lineMark = LINE_MARK_FORMATS.has(object.userData.format);
    object.userData.outlineSurface = isStructure ? outlineStructure : !lineMark;
    if (lineMark && !isStructure) lineMarks.push(object);
  }
  // Unless the mark shares its selection with an outlined surface - a contact
  // marker with its support, a component's axis arrows with the component -
  // whose outline already shows it: boxes there would cage the surface's parts.
  for (const object of lineMarks) {
    const covered = (object.userData.objectIds ?? []).some(id =>
      [...(objectsBySelectionKey.get(keysById.get(id) ?? id) ?? [])].some(other => other.userData.outlineSurface));
    if (covered) continue;
    const outline = new THREE.BoxHelper(object.userData.pickVolume ?? object, SELECT_HIGHLIGHT);
    outline.material.depthTest = false;
    outline.renderOrder = 40;
    outline.visible = false;
    outline.raycast = () => {};
    object.userData.highlightOutline = outline;
    scene.add(outline);
  }

  // Fit to what was actually drawn, not to what the assets declare. Deformed
  // geometry is baked at its authored visual scale (x50) and rescaled here at
  // draw time, so the declared bounds describe an envelope fifty times larger
  // than the shape on screen - and the camera framed that envelope instead.
  const measuredBounds = renderedSceneBounds(root);
  const bounds = measuredBounds.bounds ?? declaredBounds;
  const renderableObjects = [...root.children];
  const deformationPreview = createVisualDeformationPreview(root);
  if (deformationPreview) root.add(deformationPreview);
  const referenceGrid = addReferenceHelpers(scene, bounds, state.referenceGridVisible !== false);

  return {
    bounds,
    referenceGrid,
    depthBounds: measuredBounds.depthBounds ?? bounds,
    boundsState: { visibleObjectIds: state.visibleObjectIds, displayScale: getVisualDeformationDisplayScale(state), preview: false },
    deformationPreview,
    diagnostics,
    objectsByObjectId,
    keysById,
    objectsBySelectionKey,
    renderableObjects,
    renderedObjectCount,
    root,
    scene,
    supportStage: sceneStage(state)
  };
}

function renderedSceneBounds(root, preview = null) {
  const structural = new THREE.Box3();
  const all = new THREE.Box3();
  const part = new THREE.Box3();
  measuredWithoutLabels(root.children, () => {
    for (const object of root.children) {
      if (object.visible === false && object !== preview) continue;
      part.makeEmpty().expandByObject(object, true);
      all.union(part);
      if (object.userData?.format !== "vector") structural.union(part);
    }
  });
  const toBounds = (box) => {
    const values = [...box.min.toArray(), ...box.max.toArray()];
    return !box.isEmpty() && values.every(Number.isFinite) ? values : null;
  };
  const depthBounds = toBounds(all);
  return { bounds: toBounds(structural) ?? depthBounds, depthBounds };
}

export function updateSceneGraphBounds(graph, state) {
  const displayScale = getVisualDeformationDisplayScale(state);
  // The fast preview is painted into a 2D overlay, so its Three.js object stays
  // hidden. Its displayed coordinates still belong in framing and depth bounds.
  const preview = Boolean(graph.deformationPreviewActive);
  const previous = graph.boundsState;
  if (previous?.visibleObjectIds === state.visibleObjectIds && previous.displayScale === displayScale && previous.preview === preview) return;
  const measured = renderedSceneBounds(graph.root, preview ? graph.deformationPreview : null);
  graph.bounds = measured.bounds ?? graph.bounds;
  graph.depthBounds = measured.depthBounds ?? graph.bounds;
  graph.boundsState = { visibleObjectIds: state.visibleObjectIds, displayScale, preview };
}

const SCENE_GRAPH_STATE_KEYS = [
  "bounds",
  "geometryAssets",
  "geometryPayloads",
  "overlays",
  "objects",
  "resultFields",
  "resultStates",
  "activeLoadCase",
  "activeResultStateId",
  "activeGeometryStateId",
  "coloring",
  "legendRanges",
  "legendBands",
  "modelColorBy",
  "colorChannel",
  "resultVectorScales",
  "supportReactionPresentation",
  "searchIterationPresentation",
  "bodyOpacity",
  "sourceMeshObjectIds",
  "subpointMode",
  "subpointThreshold",
  "contactArrows",
  "contactNeutral"
  // Not referenceGridVisible: the grid is always built and the visibility pass
  // shows or hides it, so the toggle never rebuilds a large skin. Not
  // unitSystem either: only a prescribed-displacement badge is drawn in display
  // units, so only a scene that has one rebuilds for it (see below).
];

// The one thing in the graph drawn in display units: the "ΔZ = 80 mm" badge on a
// prescribed support. Checked only when the unit system actually changed.
function hasPrescribedBadges(state) {
  return (state?.geometryAssets ?? []).some((asset) =>
    asset.generation_config?.source === "tuba.support" &&
    (asset.generation_config.imposed_displacement ?? []).some((value) => Number(value) !== 0 && Number.isFinite(Number(value))));
}

// Reload preservation recreates small display settings and overlay wrappers.
// Compare those by value, while large geometry and result data retain their
// identity: a new solver payload must always build a new graph.
function sameGraphRecord(a, b, depth = 0) {
  if (a === b) return true;
  if (!a || !b || typeof a !== "object" || typeof b !== "object") return false;
  const keys = Object.keys(a);
  return keys.length === Object.keys(b).length && keys.every(key => Object.hasOwn(b, key) &&
    (a[key] === b[key] || depth > 0 && sameGraphRecord(a[key], b[key], depth - 1)));
}

const GRAPH_DISPLAY_RECORDS = new Set([
  "coloring", "legendRanges", "resultVectorScales", "bodyOpacity", "bounds", "sourceMeshObjectIds"
]);

function sameGraphInput(key, a, b) {
  if (a === b) return true;
  if (GRAPH_DISPLAY_RECORDS.has(key)) return sameGraphRecord(a, b, 1);
  return key === "overlays" && Array.isArray(a) && Array.isArray(b) && a.length === b.length &&
    a.every((overlay, index) => sameGraphRecord(overlay, b[index]));
}

export function createSceneGraphCache(buildGraph, disposeGraph = () => {}, capacity = 1) {
  const entries = [];
  return {
    get(state, canReuse = () => true) {
      const index = entries.findIndex(({ state: previous, graph }) =>
        SCENE_GRAPH_STATE_KEYS.every(key => sameGraphInput(key, previous?.[key], state?.[key])) &&
        (previous?.unitSystem === state?.unitSystem || !hasPrescribedBadges(state)) &&
        (previous?.visibleObjectIds === state?.visibleObjectIds ||
          deformedReferenceSignature(previous) === deformedReferenceSignature(state)) && canReuse(graph));
      if (index >= 0) {
        const [entry] = entries.splice(index, 1);
        entry.state = state;
        entries.push(entry);
        return entry.graph;
      }
      const graph = buildGraph(state);
      entries.push({ state, graph });
      while (entries.length > Math.max(1, capacity)) disposeGraph(entries.shift().graph);
      return graph;
    },
    clear() {
      for (const { graph } of entries) disposeGraph(graph);
      entries.length = 0;
    }
  };
}

function deformedReferenceSignature(state) {
  if (!state) {
    return "";
  }
  const payloadsByAssetId = new Map(
    (state.geometryPayloads ?? []).map((payload) => [payload.asset_id, payload])
  );
  const { visual, bodyKeys } = visibleDeformedReference(state, payloadsByAssetId, new Set(state.visibleObjectIds ?? []));
  return `${visual}|${[...bodyKeys].sort().join(",")}`;
}

export function getViewportInsets(canvas, panels = {}) {
  const viewport = canvas.getBoundingClientRect();
  if (!(viewport.width > 0 && viewport.height > 0)) return {};
  const scaleX = canvas.clientWidth / viewport.width;
  const scaleY = canvas.clientHeight / viewport.height;
  const insets = {};
  for (const side of ["left", "right", "top", "bottom"]) {
    const panel = panels[side];
    if (!panel || panel.hidden) continue;
    const rect = panel.getBoundingClientRect();
    if (Math.min(rect.right, viewport.right) <= Math.max(rect.left, viewport.left)
      || Math.min(rect.bottom, viewport.bottom) <= Math.max(rect.top, viewport.top)) continue;
    const overlap = {
      left: rect.right - viewport.left, right: viewport.right - rect.left,
      top: rect.bottom - viewport.top, bottom: viewport.bottom - rect.top
    }[side];
    const horizontal = side === "left" || side === "right";
    insets[side] = Math.min(horizontal ? viewport.width : viewport.height, overlap) * (horizontal ? scaleX : scaleY);
  }
  return insets;
}

export function createThreeCanvasRenderer(canvas, options = {}) {
  const context = canvas.getContext?.("webgl2", {
    antialias: true,
    preserveDrawingBuffer: true
  });
  if (!context) {
    const error = new Error("This browser could not start WebGL2.");
    error.code = WEBGL2_UNAVAILABLE;
    throw error;
  }
  const renderer = new THREE.WebGLRenderer({
    antialias: true,
    canvas,
    context,
    preserveDrawingBuffer: true
  });
  renderer.setClearColor(options.backgroundColor ?? 0xf8fafc, 1);
  renderer.setPixelRatio(Math.min(globalThis.devicePixelRatio ?? 1, 2));
  renderer.localClippingEnabled = true;
  const transparencyRenderer = new TransparencyRenderer(renderer);
  const deformationOverlay = createDeformationOverlay(canvas);

  const camera = createEngineeringCamera(1);

  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = false;

  // Orientation gizmo. ViewHelper draws itself into a corner viewport on top of the
  // scene, so the main pass must not auto-clear underneath it.
  renderer.autoClear = false;
  const viewHelper = new ViewHelper(camera, canvas);
  viewHelper.setLabels("X", "Y", "Z");

  let currentGraph = null;
  let currentState = null;
  let highlightComposer = null;
  let highlightRenderPass = null;
  const outlinePasses = [];
  let deformationInteractionActive = false;
  let redrawFrameId = null;
  const cameraDirection = new THREE.Vector3();
  // Rendering is on-demand, so nothing re-reads the canvas box between state
  // renders. Without this the drawing buffer keeps its old size after a window
  // or panel resize and the frame is stretched into the new box - geometry
  // reads as squashed and cut off.
  const syncCanvasSize = () => {
    const width = Math.max(1, Math.floor(canvas.clientWidth || canvas.width || 1));
    const height = Math.max(1, Math.floor(canvas.clientHeight || canvas.height || 1));
    const insets = options.viewportInsets?.() ?? {};
    const previousSize = camera.userData.viewportSize;
    const previousInsets = camera.userData.viewportInsets ?? {};
    const viewportChanged = previousSize?.width !== width || previousSize?.height !== height
      || ["left", "right", "top", "bottom"].some(side => (previousInsets[side] ?? 0) !== (insets[side] ?? 0));
    resizeCameraViewport(camera, width, height, insets);
    const size = renderer.getSize(new THREE.Vector2());
    if (size.x === width && size.y === height) {
      return viewportChanged;
    }
    renderer.setSize(width, height, false);
    highlightComposer?.setSize(width, height);
    return true;
  };
  const drawFrame = (graph) => {
    // This is shared by mouse/keyboard orbit, the gizmo, resize and state draws.
    // A fit may frame a tiny selection, but depth must still include the scene.
    updateCameraDepthRange(camera, graph.depthBounds ?? graph.bounds);
    // Every zoom, fit, view change and resize redraws through here.
    scaleValueLabels(graph, camera.userData.viewportSize);
    renderer.clear();
    const surfaces = graph.renderableObjects.filter(object => object.visible && object.userData.outlineSurface);
    const selected = surfaces.filter(object => object.userData.selected && !object.userData.hovered);
    const hovered = surfaces.filter(object => object.userData.hovered);
    if (selected.length || hovered.length) {
      if (!highlightComposer) {
        highlightComposer = new EffectComposer(renderer);
        highlightRenderPass = new RenderPass(graph.scene, camera);
        highlightRenderPass.render = (_renderer, _writeBuffer, readBuffer) => {
          transparencyRenderer.render(highlightRenderPass.scene, camera, readBuffer);
        };
        highlightComposer.addPass(highlightRenderPass);
        for (const color of [SELECT_HIGHLIGHT, HOVER_HIGHLIGHT]) {
          const pass = new OutlinePass(renderer.getSize(new THREE.Vector2()), graph.scene, camera);
          pass.visibleEdgeColor.setHex(color);
          pass.hiddenEdgeColor.setHex(color);
          // Additive edges disappear against the viewer's light background.
          pass.overlayMaterial.blending = THREE.NormalBlending;
          pass.overlayMaterial.premultipliedAlpha = true;
          // The outline is the whole selection cue now that nothing is
          // repainted; at strength 1 it was a pale glow beside a support.
          pass.edgeStrength = 2;
          outlinePasses.push(pass);
          highlightComposer.addPass(pass);
        }
        highlightComposer.addPass(new OutputPass());
      }
      highlightRenderPass.scene = graph.scene;
      outlinePasses.forEach((pass, index) => {
        pass.renderScene = graph.scene;
        pass.selectedObjects = index === 0 ? selected : hovered;
        pass.enabled = pass.selectedObjects.length > 0;
      });
      highlightComposer.render();
    } else {
      transparencyRenderer.render(graph.scene, camera);
    }
    viewHelper.render(renderer);
    options.onViewChange?.();
    if (deformationInteractionActive) drawDeformationOverlay(deformationOverlay, graph.deformationPreview, camera);
    canvas.dataset.cameraDirection = camera
      .getWorldDirection(cameraDirection)
      .toArray()
      .map((value) => value.toFixed(3))
      .join(",");
  };
  const redrawScene = () => {
    if (redrawFrameId !== null) return;
    redrawFrameId = requestAnimationFrame(() => {
      redrawFrameId = null;
      if (currentGraph) drawFrame(currentGraph);
    });
  };
  // ponytail: fixed 1/60s step instead of a real clock — the gizmo turn is a short
  // constant-rate slerp, so drift is invisible. Swap in THREE.Clock if it ever matters.
  const animateGizmo = () => {
    viewHelper.update(1 / 60);
    controls.update();
    if (currentGraph) drawFrame(currentGraph);
    if (viewHelper.animating) requestAnimationFrame(animateGizmo);
  };
  // Nothing is dropped while the camera moves. A detail LOD used to hide the
  // line/point formats here, which took supports, coupling lines and the whole
  // analysis mesh off screen on every drag - a beam model is those lines, so
  // orbiting emptied the viewport. Measured before removing it: the heaviest
  // bundle is 2224 draw calls / 139k triangles and the LOD spared 154 of them,
  // while the one scene it did thin (1.62M triangles) is a single InstancedMesh
  // costing one draw call. If orbit ever does judder, measure first and thin
  // the thing that is actually slow.
  //
  // That measurement now exists: `npm run perf -- <bundle>` drives this exact
  // loader and graph in a real browser and reports draw calls, draw calls per
  // object, triangles and frame and orbit times, per sub-point display mode.
  // Re-run it before touching anything here, and record the rate, not the total
  // - draw calls per object is what a larger model keeps paying, and it is the
  // number that says whether merging the pipe shells would be worth breaking
  // per-element picking and the deformation morph path to save them.
  controls.addEventListener("change", redrawScene);
  // Guarded: the node test environment has no ResizeObserver.
  const resizeObserver =
    typeof ResizeObserver === "undefined"
      ? null
      : new ResizeObserver(() => {
          if (!syncCanvasSize()) return;
          // setSize clears the drawing buffer. redrawScene defers to the next
          // animation frame, so the paint in between shows the cleared buffer -
          // a black flash on every step of a panel-edge drag. Draw in the same
          // callback, before that paint.
          if (currentGraph) drawFrame(currentGraph);
        });
  resizeObserver?.observe(canvas);
  for (const target of options.resizeTargets ?? []) resizeObserver?.observe(target);
  const graphCache = createSceneGraphCache(
    (state) => createThreeSceneGraph(state, options),
    disposeThreeSceneGraph,
    2
  );
  const cameraFitController = createCameraFitController(camera, controls);

  return {
    render(state) {
      syncCanvasSize();

      const graph = graphCache.get(state, candidate => hasAllVisibleAssets(candidate, state));
      applySupportStage(graph, sceneStage(state));
      applyVisualDeformationScale(graph.root, state, { previewOnly: deformationInteractionActive });
      updateSceneGraphVisibility(graph, state);
      if (deformationInteractionActive) setDeformationPreviewMode(graph, true);
      updateSceneGraphBounds(graph, state);
      applySectionBoxClipping(graph, state.sectionBox);
      applyValueLabelVisibility(graph, state.valueLabelsVisible !== false);
      applyFocusSelection(graph, state.focusSelection ? relatedSelectionIds(state, state.selectedObjectIds ?? []) : []);
      cameraFitController.apply(state, graph.bounds, graph.depthBounds, graph);
      controls.update();
      graph.camera = camera;
      applySelectionHighlight(graph, state.selectedObjectIds ?? []);
      drawFrame(graph);
      currentGraph = graph;
      currentState = state;

      canvas.dataset.renderer = "three";
      canvas.dataset.renderedObjects = String(graph.renderedObjectCount);
      canvas.dataset.renderDiagnostics = String(graph.diagnostics.length);
      return graph;
    },
    redraw() {
      redrawScene();
    },
    // Cut view while a handle is dragged: clipping, outline and whole-object
    // culling by visibility flags alone. The commit on release recomputes the
    // culling through state.
    previewSectionBox(sectionBox) {
      if (!currentGraph) return;
      if (currentState) previewSectionBoxVisibility(currentGraph, currentState, sectionBox);
      applySectionBoxClipping(currentGraph, sectionBox);
      redrawScene();
    },
    setDeformationInteraction(active) {
      if (deformationInteractionActive === active || !canSetDeformationPreview(currentGraph, active)) return false;
      deformationInteractionActive = active;
      if (currentGraph) setDeformationPreviewMode(currentGraph, active);
      if (deformationOverlay.canvas) deformationOverlay.canvas.hidden = !active;
      if (active) drawFrame(currentGraph);
      else deformationOverlay.context?.clearRect(0, 0, deformationOverlay.canvas.width, deformationOverlay.canvas.height);
      return true;
    },
    renderDeformation(state) {
      if (!deformationInteractionActive || !currentGraph?.deformationPreview) return false;
      applyVisualDeformationScale(currentGraph.root, state, { previewOnly: true });
      updateSceneGraphBounds(currentGraph, state);
      updateCameraDepthRange(camera, currentGraph.depthBounds);
      drawDeformationOverlay(deformationOverlay, currentGraph.deformationPreview, camera);
      return true;
    },
    handleGizmoClick(event) {
      viewHelper.center.copy(controls.target);
      if (!viewHelper.handleClick(event)) return false;
      requestAnimationFrame(animateGizmo);
      return true;
    },
    resetView() {
      if (!currentGraph) return;
      syncCanvasSize();
      fitCameraToBounds(camera, currentGraph.bounds, controls);
      drawFrame(currentGraph);
    },
    fitRecordedEnvelope(bounds) {
      syncCanvasSize();
      fitCameraToBounds(camera, bounds, controls);
      if (currentGraph) drawFrame(currentGraph);
    },
    projectPoint(point) {
      if (!Array.isArray(point) || point.length !== 3 || !point.every(Number.isFinite)) return null;
      const p = new THREE.Vector3(...point).project(camera);
      const rect = canvas.getBoundingClientRect();
      return { x: rect.left + (p.x + 1) * rect.width / 2, y: rect.top + (1 - p.y) * rect.height / 2, visible: Math.abs(p.x) <= 1 && Math.abs(p.y) <= 1 && Math.abs(p.z) <= 1 };
    },
    cameraSnapshot() {
      return { position: camera.position.toArray(), target: controls.target.toArray(), up: camera.up.toArray(),
        zoom: camera.zoom, left: camera.left, right: camera.right, top: camera.top, bottom: camera.bottom };
    },
    supportReactionGlyphs() {
      return (currentGraph?.root.children ?? []).filter(o => o.visible && o.userData.supportReaction)
        .map(object => {
          const record = { ...object.userData.supportReaction, meshes: [] };
          object.traverse(part => { if (part.isMesh && part.visible) record.meshes.push(part.name); });
          return record;
        });
    },
    resultBodyColours() {
      return (currentGraph?.root.children ?? []).filter(o => o.visible && o.userData.assetId?.startsWith('geometry:element:'))
        .map(object => {
          const materials = [];
          object.traverse(part => {
            if (!part.isMesh || !part.visible) return;
            for (const material of Array.isArray(part.material) ? part.material : [part.material]) {
              if (material?.color) materials.push({ color: `#${material.color.getHexString()}`, opacity: material.opacity });
            }
          });
          return { object_ids: object.userData.objectIds, materials };
        });
    },
    setStandardView(viewId) {
      if (!currentGraph) return;
      syncCanvasSize();
      setCameraToStandardView(camera, currentGraph.bounds, controls, viewId);
      drawFrame(currentGraph);
    },
    zoomBy(factor) {
      if (!zoomCameraBy(camera, factor)) return;
      if (currentGraph) drawFrame(currentGraph);
    },
    orbitBy(deltaAzimuth, deltaPolar) {
      if (!orbitCameraBy(camera, controls.target, deltaAzimuth, deltaPolar)) return;
      controls.update();
      if (currentGraph) drawFrame(currentGraph);
    }
  };
}

function createDeformationOverlay(canvas) {
  const overlay = canvas.ownerDocument?.createElement?.("canvas");
  const context = overlay?.getContext?.("2d");
  if (!overlay || !context || !canvas.parentElement) return { canvas: null, context: null };
  overlay.dataset.deformationPreview = "";
  overlay.hidden = true;
  canvas.insertAdjacentElement("afterend", overlay);
  return { canvas: overlay, context };
}

function drawDeformationOverlay(overlay, preview, camera) {
  if (!overlay?.canvas || !overlay.context || overlay.canvas.hidden || !preview) return;
  const sourceCanvas = overlay.canvas.previousElementSibling;
  if (!sourceCanvas) return;
  if (overlay.canvas.width !== sourceCanvas.width || overlay.canvas.height !== sourceCanvas.height) {
    overlay.canvas.width = sourceCanvas.width;
    overlay.canvas.height = sourceCanvas.height;
  }
  const { canvas, context } = overlay;
  const positions = preview.geometry.getAttribute("position");
  const point = new THREE.Vector3();
  context.clearRect(0, 0, canvas.width, canvas.height);
  context.beginPath();
  for (let index = 0; index + 1 < positions.count; index += 2) {
    point.fromBufferAttribute(positions, index).applyMatrix4(preview.matrixWorld).project(camera);
    context.moveTo((point.x + 1) * canvas.width / 2, (1 - point.y) * canvas.height / 2);
    point.fromBufferAttribute(positions, index + 1).applyMatrix4(preview.matrixWorld).project(camera);
    context.lineTo((point.x + 1) * canvas.width / 2, (1 - point.y) * canvas.height / 2);
  }
  context.strokeStyle = "#7c3aed";
  context.lineCap = "round";
  context.lineJoin = "round";
  context.lineWidth = Math.max(6, 6 * (globalThis.devicePixelRatio ?? 1));
  context.stroke();
}

export function disposeThreeSceneGraph(graph) {
  const geometries = new Set();
  const materials = new Set();
  const textures = new Set();
  graph?.scene?.traverse((object) => {
    if (object.geometry) {
      geometries.add(object.geometry);
    }
    for (const material of Array.isArray(object.material) ? object.material : object.material ? [object.material] : []) {
      materials.add(material);
      if (material.map) textures.add(material.map);
    }
  });
  for (const geometry of geometries) {
    geometry.dispose();
  }
  for (const material of materials) {
    material.dispose();
  }
  for (const texture of textures) {
    texture.dispose();
  }
}

function renderedFitBounds(request, graph) {
  if (!request?.objectIds?.length || !graph) return request?.bounds;
  const selected = new Set(request.objectIds);
  const children = graph.renderableObjects.filter(object => object.visible !== false
    && object.userData.objectIds?.some(id => selected.has(id)));
  const bounds = renderedSceneBounds({ children }).depthBounds;
  // Point/support assets can declare zero-size bounds; deformed assets can
  // declare a different display scale. Frame the visible representation.
  if (!bounds) return request.bounds;
  return clampBoundsToSpan(bounds, request.maxSpan) ?? bounds;
}

export function createCameraFitController(camera, controls = null) {
  let initialized = false;
  let appliedRequestId = null;

  return {
    apply(state, sceneBounds, depthBounds = sceneBounds, graph = null) {
      const request = state?.camera?.fitRequest;
      let fit = null;
      if (!initialized) {
        initialized = true;
        appliedRequestId = request?.id ?? null;
        fit = fitCameraToBounds(camera, renderedFitBounds(request, graph) ?? sceneBounds, controls);
      } else if (request && request.id !== appliedRequestId) {
        appliedRequestId = request.id;
        fit = fitCameraToBounds(camera, renderedFitBounds(request, graph), controls);
      }
      updateCameraDepthRange(camera, depthBounds);
      return fit;
    }
  };
}

// Orthographic framing is independent of camera distance. Keep every scene
// corner in front of the camera without changing its orientation, screen-space
// pan, zoom or orbit target. Tight planes also retain depth-buffer precision;
// making far arbitrarily huge cannot repair geometry behind the camera.
export function updateCameraDepthRange(camera, bounds) {
  const normalized = normalizeBounds(bounds);
  if (!camera.isOrthographicCamera || !normalized) return;
  const direction = camera.getWorldDirection(new THREE.Vector3());
  const corner = new THREE.Vector3();
  let closest = Infinity;
  let furthest = -Infinity;
  for (let index = 0; index < 8; index++) {
    corner.set(
      normalized[index & 1 ? 3 : 0],
      normalized[index & 2 ? 4 : 1],
      normalized[index & 4 ? 5 : 2]
    );
    const depth = corner.sub(camera.position).dot(direction);
    closest = Math.min(closest, depth);
    furthest = Math.max(furthest, depth);
  }
  const padding = Math.max((furthest - closest) * 0.05, 1e-4);
  if (closest < padding) {
    const shift = padding - closest;
    camera.position.addScaledVector(direction, -shift);
    closest += shift;
    furthest += shift;
    camera.updateMatrixWorld(true);
  }
  const near = Math.max(0, closest - padding);
  const far = Math.max(near + padding, furthest + padding);
  if (camera.near !== near || camera.far !== far) {
    camera.near = near;
    camera.far = far;
    camera.updateProjectionMatrix();
  }
}

// How far from a line, in screen pixels, a click still lands on it.
const PICK_LINE_TOLERANCE_PX = 6;

// Support glyphs and load arrows are small annotations that sit on or inside the
// structure they mark, so a pipe or beam surface is nearer the camera and raycast
// reports it first - clicking a support selected the pipe under it, and a click
// that was meant to move the selection looked like it did nothing. A glyph that
// the ray touches therefore wins over the structural geometry behind it.
const PICK_PRIORITY_ANNOTATION = 1;

export function pickRenderedObject(graph, point, viewport) {
  return pickRenderedPoint(graph, point, viewport)?.objectId ?? null;
}

export function pickRenderedPoint(graph, point, viewport) {
  const hits = pickRenderedPoints(graph, point, viewport);
  return hits.find(hit => hit.priority === PICK_PRIORITY_ANNOTATION && !hit.volumeHit)
    ?? hits.find(hit => hit.volumeHit) ?? hits[0] ?? null;
}

// Keep the full depth stack for Select Other; ordinary picking retains glyph priority.
export function pickRenderedPoints(graph, point, viewport) {
  if (!graph?.camera || !graph.renderableObjects?.length) {
    return [];
  }
  const raycaster = new THREE.Raycaster();
  const normalized = new THREE.Vector2((point.x / viewport.width) * 2 - 1, -(point.y / viewport.height) * 2 + 1);
  graph.camera.updateProjectionMatrix();
  graph.camera.updateMatrixWorld();
  graph.scene?.updateMatrixWorld(true);
  raycaster.setFromCamera(normalized, graph.camera);
  // Three.js hits a line anywhere within 1 world unit of the ray. On a metre-
  // scale model that is dozens of pixels, and hits are ordered by depth, so any
  // element line or mesh edge nearer the camera took the click from the support
  // or pipe actually under the cursor.
  raycaster.params.Line.threshold = PICK_LINE_TOLERANCE_PX * worldUnitsPerPixel(graph, viewport);
  raycaster.params.Points.threshold = 4 * worldUnitsPerPixel(graph, viewport);
  const raycastTargets = graph.renderableObjects.filter(
    (object) => object.visible !== false && object.userData?.pickable !== false && object.userData?.format !== "tuyau_subpoint_glyphs"
  );
  const intersections = raycaster.intersectObjects(raycastTargets, true);
  const hits = new Map();
  for (const intersection of intersections) {
    // Raycasting ignores clipping planes: without this a click picked geometry
    // the section box had already cut away.
    const clippingPlanes = (Array.isArray(intersection.object.material)
      ? intersection.object.material[intersection.face?.materialIndex ?? 0] : intersection.object.material)?.clippingPlanes ?? [];
    if (clippingPlanes.some((plane) => plane.distanceToPoint(intersection.point) < 0)) {
      continue;
    }
    const objectId = intersection.object.userData?.primaryObjectId || intersection.object.userData?.objectId;
    if (!objectId) {
      continue;
    }
    let visible = true;
    for (let part = intersection.object; part; part = part.parent) {
      if (part.visible === false || part.userData?.pickable === false) visible = false;
    }
    const key = graph.keysById?.get(objectId) ?? objectId;
    if (!visible) continue;
    const hit = { objectId, point: intersection.point.toArray(), distance: intersection.distance,
      priority: intersection.object.userData.pickPriority ?? 0, volumeHit: Boolean(intersection.object.userData.pickVolumeHit) };
    const previous = hits.get(key);
    if (!previous) hits.set(key, hit);
    else if (previous.volumeHit && !hit.volumeHit) hits.set(key, hit);
  }
  // A miss selects nothing. It used to fall back to the object whose bounds
  // centre projected nearest the click, which for a long pipe run is nowhere
  // near where it is drawn - a near-miss selected something across the model.
  return [...hits.values()].sort((a, b) => a.distance - b.distance);
}

// World size of one screen pixel. Exact for the app's orthographic camera; a
// perspective camera is measured at the depth of the scene centre.
function worldUnitsPerPixel(graph, viewport) {
  const camera = graph.camera;
  if (camera.isOrthographicCamera) {
    return (camera.top - camera.bottom) / camera.zoom / viewport.height;
  }
  const depth = camera.position.distanceTo(centerOfBounds(graph.bounds) ?? new THREE.Vector3());
  return (2 * depth * Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2)) / viewport.height;
}

export function updateSceneGraphVisibility(graph, state) {
  if (graph.referenceGrid) graph.referenceGrid.visible = state.referenceGridVisible !== false;
  const visibleIds = new Set(state.visibleObjectIds ?? []);
  let renderedObjectCount = 0;
  for (const object of graph.renderableObjects ?? []) {
    const objectIds = object.userData?.objectIds ?? [];
    object.visible = objectIds.length === 0 || objectIds.some((objectId) => visibleIds.has(objectId));
    if (object.visible) {
      renderedObjectCount += 1;
    }
  }
  graph.renderedObjectCount = renderedObjectCount;
  return graph;
}

function uncutVisibleObjectIds(state) {
  return getVisibleObjectIds({ ...state, sectionBox: null });
}

// The drag preview's half of Cut view culling: what the state would show with
// no box, narrowed to what the preview box reaches - the same asset-bounds test
// the committed box applies (sceneLoader objectIntersectsSectionBox). Objects
// the committed box culled are in the graph (it is built uncut), so widening
// the box brings them back without a rebuild. The uncut set is computed once
// per rendered state, not per pointer move.
export function previewSectionBoxVisibility(graph, state, sectionBox) {
  if (graph.previewBase?.state !== state) {
    graph.previewBase = { state, ids: new Set(Array.isArray(state.objects) ? uncutVisibleObjectIds(state) : state.visibleObjectIds ?? []) };
  }
  const ids = graph.previewBase.ids;
  for (const object of graph.renderableObjects ?? []) {
    const objectIds = object.userData?.objectIds ?? [];
    const shown = objectIds.length === 0 || objectIds.some((objectId) => ids.has(objectId));
    object.visible = shown && boundsReachBox(object.userData?.bounds, sectionBox);
  }
}

function boundsReachBox(bounds, sectionBox) {
  if (!sectionBox || !Array.isArray(bounds) || bounds.length !== 6) return true;
  const { min, max } = sectionBox;
  return bounds[3] >= min[0] && bounds[0] <= max[0] &&
    bounds[4] >= min[1] && bounds[1] <= max[1] &&
    bounds[5] >= min[2] && bounds[2] <= max[2];
}

export function sectionBoxClippingPlanes(sectionBox) {
  if (!sectionBox) {
    return [];
  }
  const { min, max } = sectionBox;
  return [
    new THREE.Plane(new THREE.Vector3(-1, 0, 0), max[0]),
    new THREE.Plane(new THREE.Vector3(1, 0, 0), -min[0]),
    new THREE.Plane(new THREE.Vector3(0, -1, 0), max[1]),
    new THREE.Plane(new THREE.Vector3(0, 1, 0), -min[1]),
    new THREE.Plane(new THREE.Vector3(0, 0, -1), max[2]),
    new THREE.Plane(new THREE.Vector3(0, 0, 1), -min[2])
  ];
}

// --muted from styles.css: a neutral that reads on the light canvas and does
// not compete with the selection amber or the result colours.
const CUT_OUTLINE_COLOR = 0x4c5b63;

export function applySectionBoxClipping(graph, sectionBox) {
  const clippingPlanes = sectionBox ? sectionBoxClippingPlanes(sectionBox) : null;
  updateCutOutline(graph, sectionBox);
  const anchor = new THREE.Vector3();
  const cutBox = sectionBox ? new THREE.Box3(new THREE.Vector3(...sectionBox.min), new THREE.Vector3(...sectionBox.max)) : null;
  graph.root?.traverse((object) => {
    // Labels and value badges are sprites: a plane slices one mid-word ("Tee
    // (HEXA"). They are never clipped; a label whose anchor is outside the box
    // goes as a whole instead. Material visibility, not object.visible, so it
    // composes with the layer and Show values toggles that own object.visible,
    // and so the live drag preview can bring a label back without a rebuild.
    if (object.isSprite) {
      object.material.clippingPlanes = null;
      object.material.visible = !cutBox || cutBox.containsPoint(object.getWorldPosition(anchor));
      return;
    }
    // Intentional, and only for a cut: a volume mesh draws its outer skin, and
    // the interior element edges stay hidden because through an intact skin they
    // are noise. Once the box cuts the skin open they are the mesh you are
    // looking into, so they show exactly while a cut is on.
    if (object.userData?.volumeMeshEdges) object.visible = Boolean(sectionBox);
    const materials = Array.isArray(object.material) ? object.material : object.material ? [object.material] : [];
    for (const material of materials) {
      material.clippingPlanes = clippingPlanes;
      material.needsUpdate = true;
    }
  });
}

// A thin box where the cut is, drawn over the model so it reads from any
// angle. It lives in the scene, not under root, so it is never clipped, picked,
// counted in the bounds or exported with the model.
function updateCutOutline(graph, sectionBox) {
  if (!sectionBox && !graph.cutOutline) return;
  if (!graph.cutOutline && graph.scene) {
    const outline = new THREE.Box3Helper(new THREE.Box3(), CUT_OUTLINE_COLOR);
    outline.name = "cut-view-outline";
    outline.material.depthTest = false;
    outline.material.transparent = true;
    outline.material.opacity = 0.8;
    outline.renderOrder = 1050;
    outline.raycast = () => {};
    graph.scene.add(outline);
    graph.cutOutline = outline;
  }
  if (!graph.cutOutline) return;
  graph.cutOutline.visible = Boolean(sectionBox);
  if (sectionBox) graph.cutOutline.box.set(new THREE.Vector3(...sectionBox.min), new THREE.Vector3(...sectionBox.max));
}

// Value labels are the F = / q = / μ = / Δ badges the load and support glyphs carry
// as child sprites. They are hidden in place, so turning them off costs no
// rebuild; the list is gathered once per graph.
export function applyValueLabelVisibility(graph, visible) {
  graph.valueLabels ??= collectValueLabels(graph.root);
  for (const sprite of graph.valueLabels) {
    // The contact-state icon is the badge's stand-in: shown exactly when the
    // values are hidden.
    sprite.visible = sprite.userData.supportPart === "friction-state" ? !visible : visible;
  }
}

// Value labels keep one on-screen height at any zoom. At a fixed world size they
// grew with every zoom step until they covered the detail being zoomed into.
// sizeAttenuation cannot do this: it only acts under a perspective camera.
const VALUE_LABEL_HEIGHT_PX = 20;

export function scaleValueLabels(graph, viewport) {
  graph.valueLabels ??= collectValueLabels(graph.root);
  const height = VALUE_LABEL_HEIGHT_PX * worldUnitsPerPixel(graph, viewport);
  for (const sprite of graph.valueLabels) sprite.scale.set(height * sprite.userData.aspect, height, 1);
}

// Value labels are screen-sized (scaleValueLabels), so their world size is the
// current zoom's - or a sprite's default 1 m before the first draw. Anything that
// measures a body in world units (a fit, a selection outline, a glyph's ground
// plate) counts a label by its anchor alone.
function measuredWithoutLabels(objects, measure) {
  const labels = objects.flatMap((object) => collectValueLabels(object));
  const scales = labels.map((label) => label.scale.clone());
  for (const label of labels) label.scale.setScalar(0);
  try {
    return measure();
  } finally {
    labels.forEach((label, index) => label.scale.copy(scales[index]));
  }
}

function collectValueLabels(root) {
  const labels = [];
  root?.traverse((object) => {
    const part = object.userData?.supportPart;
    if (object.userData?.loadPart === "load-badge" || part === "friction-badge" || part === "friction-state") labels.push(object);
  });
  return labels;
}

// Whether the deformation preview may flip to `active`. Entering needs a preview
// to draw, and is refused while a section rotation is on screen - that one needs
// its surface and local frames throughout the drag. Leaving is unconditional: a
// graph rebuilt between pointerdown and pointerup carries no preview, and making
// the exit depend on one stranded the flag set, so every later render re-hid the
// undeformed reference geometry for good.
export function canSetDeformationPreview(graph, active) {
  if (!active) return true;
  return (
    Boolean(graph?.deformationPreview) &&
    !(graph.renderableObjects ?? []).some((object) => object.userData?.sectionDeformation)
  );
}

export function setDeformationPreviewMode(graph, active) {
  graph.deformationPreviewActive = active;
  for (const object of graph.renderableObjects ?? []) {
    if (!object.userData?.undeformedReference && !objectHasVisualDeformation(object)) continue;
    if (active) {
      if (!Object.hasOwn(object.userData, "visibleBeforeDeformationPreview")) {
        object.userData.visibleBeforeDeformationPreview = object.visible;
      }
      object.visible = false;
    } else if (Object.hasOwn(object.userData, "visibleBeforeDeformationPreview")) {
      object.visible = object.userData.visibleBeforeDeformationPreview;
      delete object.userData.visibleBeforeDeformationPreview;
    }
  }
  return graph;
}

function objectHasVisualDeformation(object) {
  let found = false;
  object.traverse((part) => { found ||= Boolean(part.userData?.visualDeformationSourceScale); });
  return found;
}

function hasAllVisibleAssets(graph, state) {
  const cachedAssetIds = new Set((graph.renderableObjects ?? []).map((object) => object.userData?.assetId));
  const visibleIds = new Set(state.visibleObjectIds ?? []);
  const payloadsByAssetId = new Map((state.geometryPayloads ?? []).map((payload) => [payload.asset_id, payload]));
  return (state.geometryAssets ?? [])
    .filter((asset) => isAssetVisible(asset, visibleIds))
    .filter((asset) => assetMatchesActiveGeometryState(asset, payloadsByAssetId.get(asset.id) ?? {}, state.activeGeometryStateId))
    .every((asset) => cachedAssetIds.has(asset.id));
}

// The colours of the hover and selection outline or box. Nothing is painted in
// them: colour carries the results, input vs result and the support roles.
// Cyan, the selection-blue family CAD users expect, but lighter and greener than
// the member blue, and clear of the gold, orange and green supports and the
// cividis ramp. The old amber sat beside the gold restraint it outlined. Hover
// is the lighter tint: a preview, where selection is the strong line.
const HOVER_HIGHLIGHT = 0x67e8f9;
const SELECT_HIGHLIGHT = 0x06b6d4;
// Drawn as lines, so the outline pass, which traces meshes only, has nothing to
// trace: these get a box when selected.
const LINE_MARK_FORMATS = new Set(["vector", "line_load_comb", "polyline", "line"]);
// Profiled members drawn as extruded section meshes, as designed and as solved.
const MEMBER_SURFACE_SOURCES = new Set(["tuba.element", "tuba.deformed_analysis_mesh.profile"]);

export function applyHoverHighlight(graph, objectId) {
  if (graph.highlightedObjectId === (objectId ?? null)) {
    return graph;
  }
  for (const object of highlightObjects(graph, graph.highlightedObjectId)) setObjectHover(object, false);
  graph.highlightedObjectId = objectId ?? null;
  for (const object of highlightObjects(graph, objectId)) setObjectHover(object, true);
  return graph;
}

function highlightObjects(graph, id) {
  return graph.objectsBySelectionKey?.get(graph.keysById?.get(id) ?? id) ??
    [graph.objectsByObjectId?.get(id)].filter(Boolean);
}

function setObjectHover(object, hovered) {
  if (!object) return;
  object.traverse((child) => {
    setChildHighlight(child, hovered, child.userData.selected === true);
  });
  updateHighlightOutline(object);
}

function updateHighlightOutline(object) {
  const outline = object.userData.highlightOutline;
  if (!outline) return;
  outline.visible = object.visible && (object.userData.hovered || object.userData.selected);
  if (outline.visible) measuredWithoutLabels([object], () => outline.update());
  outline.material.color.setHex(object.userData.hovered ? HOVER_HIGHLIGHT : SELECT_HIGHLIGHT);
}

export function applySelectionHighlight(graph, objectIds = []) {
  const selectedIds = new Set(objectIds);
  graph.selectedObjectIds = [...selectedIds];
  const selectedObjects = new Set([...selectedIds].flatMap(id => [...highlightObjects(graph, id)]));
  for (const object of graph.renderableObjects ?? []) {
    const selected = selectedObjects.has(object) || (object.userData.objectIds ?? []).some(id => selectedIds.has(id));
    object.userData.selected = selected;
    object.traverse((child) => {
      setChildHighlight(child, child.userData.hovered === true, selected);
    });
    updateHighlightOutline(object);
  }
  return graph;
}

export function applyFocusSelection(graph, objectIds = []) {
  const focused = new Set(objectIds.flatMap(id => [...highlightObjects(graph, id)]).filter(object => object.visible !== false));
  for (const object of graph.renderableObjects ?? []) {
    const subject = focused.has(object);
    object.traverse(part => {
      for (const material of Array.isArray(part.material) ? part.material : part.material ? [part.material] : []) {
        const base = material.userData.focusBase ??= {
          opacity: material.opacity, transparent: material.transparent, depthWrite: material.depthWrite
        };
        const active = focused.size > 0;
        const opacity = active ? subject ? 1 : Math.min(base.opacity, 0.14) : base.opacity;
        const transparent = active && subject ? false : base.transparent || opacity < 1;
        if (material.transparent !== transparent) material.needsUpdate = true;
        material.opacity = opacity;
        material.transparent = transparent;
        material.depthWrite = active ? subject && material.depthTest : base.depthWrite;
      }
    });
  }
  return graph;
}

function setChildHighlight(child, hovered, selected) {
  child.userData.hovered = hovered;
  child.userData.selected = selected;
}

// Half-extents of the bounds as they actually project onto the screen for one
// view direction, plus the depth along it.
//
// The fit used to size the frustum from half the AABB diagonal - the bounding
// sphere. For an elongated pipe run that diagonal is far longer than anything
// visible from any single angle, so the model sat at a fraction of the frame
// with the rest of the viewport empty.
function projectedHalfExtents(bounds, direction, up) {
  const center = centerOfBounds(bounds);
  const forward = direction.clone().normalize();
  let screenUp = up.clone().normalize();
  if (Math.abs(forward.dot(screenUp)) > 0.999) {
    screenUp = new THREE.Vector3(0, 1, 0);
  }
  const right = new THREE.Vector3().crossVectors(screenUp, forward).normalize();
  screenUp = new THREE.Vector3().crossVectors(forward, right).normalize();

  const corner = new THREE.Vector3();
  let halfWidth = 0;
  let halfHeight = 0;
  let halfDepth = 0;
  for (let index = 0; index < 8; index += 1) {
    corner
      .set(
        index & 1 ? bounds[3] : bounds[0],
        index & 2 ? bounds[4] : bounds[1],
        index & 4 ? bounds[5] : bounds[2]
      )
      .sub(center);
    halfWidth = Math.max(halfWidth, Math.abs(corner.dot(right)));
    halfHeight = Math.max(halfHeight, Math.abs(corner.dot(screenUp)));
    halfDepth = Math.max(halfDepth, Math.abs(corner.dot(forward)));
  }
  return { halfWidth, halfHeight, halfDepth };
}

// Breathing room around the fitted extents, so the outermost surface is not
// flush against the frame edge.
const FIT_MARGIN = 1.1;

export function upVectorForView(viewId = "iso") {
  // Looking straight down or up the Z axis, world Z cannot also be screen up.
  return Math.abs(STANDARD_VIEW_DIRECTIONS[viewId]?.[2] ?? 0) === 1
    ? new THREE.Vector3(0, 1, 0)
    : new THREE.Vector3(0, 0, 1);
}

export function resizeCameraViewport(camera, width, height, insets = {}) {
  camera.userData.viewportSize = { width, height };
  camera.userData.viewportInsets = insets;
  camera.userData.viewportAspect = width / height;
  if (camera.isOrthographicCamera) {
    const inset = (side) => Math.max(0, Number(insets[side]) || 0);
    let halfHeight = camera.userData.fitHalfHeight ?? 1;
    const extents = camera.userData.fitExtents;
    if (extents) {
      const availableWidth = Math.max(1, width - inset("left") - inset("right"));
      const availableHeight = Math.max(1, height - inset("top") - inset("bottom"));
      halfHeight = Math.max(extents.halfHeight, extents.halfWidth * availableHeight / availableWidth) * FIT_MARGIN;
      halfHeight = Math.max(halfHeight, 1e-4) * height / availableHeight;
      camera.userData.fitHalfHeight = halfHeight;
    }
    camera.left = -halfHeight * width / height;
    camera.right = halfHeight * width / height;
    camera.top = halfHeight;
    camera.bottom = -halfHeight;
    // Native view offsets remain fixed in screen pixels when zoom changes.
    camera.setViewOffset(width, height, (inset("right") - inset("left")) / 2,
      (inset("bottom") - inset("top")) / 2, width, height);
  } else {
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  }
}

export function fitCameraToBounds(camera, bounds, controls = null, viewId = "iso") {
  const normalized = normalizeBounds(bounds) ?? [-1, -1, -1, 1, 1, 1];
  const center = centerOfBounds(normalized);
  const size = sizeOfBounds(normalized);
  const radius = Math.max(size.length() * 0.5, 0.5);
  // Fitted per view: setCameraToStandardView reuses this frustum when it swings
  // the camera to an axis, so sizing it for the isometric view alone would clip
  // the others.
  const direction = new THREE.Vector3(
    ...(STANDARD_VIEW_DIRECTIONS[viewId] ?? STANDARD_VIEW_DIRECTIONS.iso)
  ).normalize();
  const up = upVectorForView(viewId);
  const extents = projectedHalfExtents(normalized, direction, up);
  let distance;

  if (camera.isOrthographicCamera) {
    const aspect = positiveNumber(camera.userData.viewportAspect) ?? 1;
    const viewport = camera.userData.viewportSize;
    const insets = camera.userData.viewportInsets ?? {};
    // Retain the fitted silhouette so a narrower canvas (an open inspector or
    // script pane) can change the binding axis without resetting user zoom/pan.
    camera.userData.fitExtents = extents;
    camera.zoom = 1;
    if (viewport) {
      resizeCameraViewport(camera, viewport.width, viewport.height, insets);
    } else {
      const halfHeight = Math.max(Math.max(extents.halfHeight, extents.halfWidth / aspect) * FIT_MARGIN, 1e-4);
      camera.userData.fitHalfHeight = halfHeight;
      camera.left = -halfHeight * aspect;
      camera.right = halfHeight * aspect;
      camera.top = halfHeight;
      camera.bottom = -halfHeight;
    }
    // Orthographic projection does not change with distance, so this only has to
    // clear the geometry and leave near/far room around it.
    distance = Math.max(extents.halfDepth * 2 + radius, 1);
  } else {
    const fov = THREE.MathUtils.degToRad(camera.fov || 45);
    const aspect = positiveNumber(camera.aspect) ?? 1;
    const forHeight = (extents.halfHeight * FIT_MARGIN) / Math.tan(fov / 2);
    const forWidth = (extents.halfWidth * FIT_MARGIN) / (Math.tan(fov / 2) * aspect);
    distance = Math.max(forHeight, forWidth) + extents.halfDepth;
    distance = Math.max(distance, 1e-3);
  }

  camera.near = Math.max(distance / 1000, 0.001);
  camera.far = distance * 1000;
  camera.up.copy(up);
  camera.position.copy(center).addScaledVector(direction, distance);
  camera.lookAt(center);
  camera.updateProjectionMatrix();
  camera.userData.fitBounds = normalized;

  if (controls) {
    controls.target.copy(center);
    controls.update();
  }

  return {
    distance,
    radius,
    target: center.toArray()
  };
}

export function setCameraToStandardView(camera, bounds, controls = null, viewId = "iso") {
  // Fit for the view being switched to, not for the isometric one: each axis
  // sees a different silhouette, and reusing one frustum for all of them either
  // clips the widest or wastes the frame on the narrowest.
  const fit = fitCameraToBounds(camera, bounds, controls, viewId);
  const target = new THREE.Vector3(...fit.target);
  const direction = new THREE.Vector3(...(STANDARD_VIEW_DIRECTIONS[viewId] ?? STANDARD_VIEW_DIRECTIONS.iso)).normalize();
  camera.up.copy(upVectorForView(viewId));
  camera.position.copy(target).addScaledVector(direction, fit.distance);
  camera.lookAt(target);
  camera.updateProjectionMatrix();
  if (controls) {
    controls.target.copy(target);
    controls.update();
  }
}

/**
 * Swing the camera around its target by two angles, in radians.
 *
 * Written against spherical coordinates rather than OrbitControls internals so
 * the keyboard path and the mouse path cannot drift apart. The polar angle is
 * clamped short of the poles: at exactly 0 or PI the up vector and the view
 * direction are parallel and the view flips.
 */
export function orbitCameraBy(camera, target, deltaAzimuth, deltaPolar) {
  if (!Number.isFinite(deltaAzimuth) || !Number.isFinite(deltaPolar)) return false;
  const offset = camera.position.clone().sub(target);
  const spherical = new THREE.Spherical().setFromVector3(
    new THREE.Vector3(offset.x, offset.z, -offset.y)
  );
  spherical.theta += deltaAzimuth;
  spherical.phi = THREE.MathUtils.clamp(spherical.phi + deltaPolar, 0.02, Math.PI - 0.02);
  const rotated = new THREE.Vector3().setFromSpherical(spherical);
  camera.position.copy(target).add(new THREE.Vector3(rotated.x, -rotated.z, rotated.y));
  camera.up.set(0, 0, 1);
  camera.lookAt(target);
  camera.updateProjectionMatrix();
  return true;
}

export function zoomCameraBy(camera, factor) {
  if (!camera.isOrthographicCamera || !Number.isFinite(factor) || factor <= 0) return false;
  camera.zoom = THREE.MathUtils.clamp(camera.zoom * factor, 0.05, 20);
  camera.updateProjectionMatrix();
  return true;
}

function createRenderableForAsset(asset, payload, state) {
  const format = String(asset.format ?? "").toLowerCase();
  if (!SUPPORTED_RENDER_FORMATS.has(format)) {
    return invalidAsset(asset, `Unsupported geometry format '${asset.format}'.`);
  }

  const preparedConfig = prepareAssetRenderConfig(asset, payload, state);
  const morph = preparedConfig.section_deformations ? null : visualDeformationMorphConfigs(asset, payload, preparedConfig);
  const config = morph?.sourceConfig ?? preparedConfig;
  try {
    const result = createPreparedRenderable(asset, payload, state, format, config);
    if (result.object) result.object.userData.undeformedReference = isUndeformedReferenceConfig(asset, preparedConfig, state);
    if (result.object && preparedConfig.section_deformations && isVisualDeformedConfig(asset, preparedConfig)) {
      result.object.userData.sectionDeformation = preparedConfig;
      applyVisualDeformationScale(result.object, state);
    } else if (result.object && morph) {
      const base = createPreparedRenderable(asset, payload, state, format, morph.baseConfig);
      if (base.object && attachVisualDeformationMorph(result.object, base.object, morph.sourceScale)) {
        if (isSolvedShapeSurface(format, preparedConfig)) result.object.traverse((child) => { child.userData.followsActiveShape = true; });
        applyVisualDeformationScale(result.object, state);
      }
    }
    return result;
  } catch (error) {
    return invalidAsset(asset, error.message);
  }
}

function createPreparedRenderable(asset, payload, state, format, config) {
  if (format === "tube" || format === "tube_envelope") {
    return createTube(asset, config, format);
  }
  if (format === "polyline" || format === "line") {
    return createPolyline(asset, config, format);
  }
  if (format === "label") {
    return createLabel(asset, config, format, state);
  }
  if (format === "point" || format === "marker") {
    return createPoint(asset, config, format, state);
  }
  if (format === "tuyau_subpoint_glyphs") {
    return createTuyauSubpointGlyphs(asset, config, format, state);
  }
  if (format === "vector") {
    return createVector(asset, config, format, state);
  }
  if (format === "line_load_comb") {
    return createLineLoadComb(asset, config, format, state);
  }
  if (format === "cuboid" || format === "aabb") {
    return createBox(asset, config, format);
  }
  if (format === "cylinder") {
    return createCylinder(asset, config, format);
  }
  if (format === "mesh") {
    return createMesh(asset, config, payload, format, state);
  }
  return invalidAsset(asset, `No renderer for geometry format '${asset.format}'.`);
}

function visualDeformationMorphConfigs(asset, payload, preparedConfig) {
  const format = String(asset.format ?? "").toLowerCase();
  if (format !== "polyline" && format !== "line" && format !== "tube" && format !== "tube_envelope" && format !== "mesh") {
    return null;
  }
  const source = {
    ...(payload.generation_config ?? {}),
    ...(asset.generation_config ?? {})
  };
  const solvedSurface = isSolvedShapeSurface(format, source);
  if (!isVisualDeformedConfig(asset, source) && !solvedSurface) {
    return null;
  }
  const sourceScale = positiveNumber(source.visual_scale ?? source.deformation_scale ?? source.displacement_scale) ?? (solvedSurface ? 1 : null);
  const sourceKey = format === "mesh" ? "vertices" : "points";
  const baseKey = format === "mesh" ? "base_vertices" : "base_points";
  const sourcePoints = numericPoints(source[sourceKey]);
  const basePoints = numericPoints(source[baseKey] ?? (format === "mesh" ? undefined : source.cold_points));
  if (!sourceScale || sourcePoints.length < 2 || basePoints.length !== sourcePoints.length) {
    return null;
  }
  return {
    sourceScale,
    sourceConfig: { ...preparedConfig, [sourceKey]: sourcePoints, visual_scale_display_only: sourceScale },
    baseConfig: { ...preparedConfig, [sourceKey]: basePoints, visual_scale_display_only: 0 }
  };
}

// A result surface with per-vertex values drawn on the solved shape, with the
// undeformed shape beside it: a solid's stress or displacement skin, a shell's.
function isSolvedShapeSurface(format, config) {
  return format === "mesh" && Array.isArray(config.vertex_values) && Array.isArray(config.base_vertices);
}

function attachVisualDeformationMorph(sourceRoot, baseRoot, sourceScale) {
  const sourceObjects = [];
  const baseObjects = [];
  sourceRoot.traverse((object) => {
    if (object.geometry?.getAttribute("position")) sourceObjects.push(object);
  });
  baseRoot.traverse((object) => {
    if (object.geometry?.getAttribute("position")) baseObjects.push(object);
  });
  let attached = false;
  for (let index = 0; index < Math.min(sourceObjects.length, baseObjects.length); index += 1) {
    const object = sourceObjects[index];
    const base = baseObjects[index];
    const position = object.geometry.getAttribute("position");
    const basePosition = base.geometry.getAttribute("position");
    if (position.count !== basePosition.count) continue;
    object.userData.visualDeformationSourceScale = sourceScale;
    if (object.isLine) {
      object.userData.visualDeformationPositions = {
        base: basePosition.array.slice(),
        source: position.array.slice()
      };
      attached = true;
      continue;
    }
    object.geometry.morphAttributes.position = [basePosition];
    const normal = object.geometry.getAttribute("normal");
    const baseNormal = base.geometry.getAttribute("normal");
    if (normal && baseNormal?.count === normal.count) {
      object.geometry.morphAttributes.normal = [baseNormal];
    }
    object.updateMorphTargets?.();
    attached = true;
  }
  return attached;
}

function createVisualDeformationPreview(root) {
  const vertices = [];
  for (const object of root.children) {
    const positions = object.userData?.visualDeformationPositions;
    if (!positions) continue;
    for (let point = 0; point < positions.base.length / 3 - 1; point += 1) {
      for (const index of [point, point + 1]) {
        vertices.push({
          base: positions.base.slice(index * 3, index * 3 + 3),
          source: positions.source.slice(index * 3, index * 3 + 3),
          sourceScale: object.userData.visualDeformationSourceScale
        });
      }
    }
  }
  if (vertices.length === 0) return null;
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(vertices.flatMap(({ source }) => [...source]), 3));
  const preview = new THREE.LineSegments(
    geometry,
    new THREE.LineBasicMaterial({ color: 0x7c3aed, depthTest: false, transparent: true })
  );
  preview.name = "VisualDeformationPreview";
  preview.renderOrder = 1000;
  preview.visible = false;
  preview.userData.visualDeformationPreview = vertices;
  return preview;
}

export function applyVisualDeformationScale(root, state, options = {}) {
  const sliderScale = getVisualDeformationDisplayScale(state);
  const shapeScale = getActiveShapeScale(state);
  root?.traverse((object) => {
    const displayScale = object.userData?.followsActiveShape ? shapeScale : sliderScale;
    const preview = object.userData?.visualDeformationPreview;
    if (preview) {
      const attribute = object.geometry.getAttribute("position");
      for (let index = 0; index < preview.length; index += 1) {
        const { base, source, sourceScale } = preview[index];
        const factor = displayScale / sourceScale;
        attribute.setXYZ(
          index,
          base[0] + (source[0] - base[0]) * factor,
          base[1] + (source[1] - base[1]) * factor,
          base[2] + (source[2] - base[2]) * factor
        );
      }
      attribute.needsUpdate = true;
      return;
    }
    const section = object.userData?.sectionDeformation;
    if (section) {
      const points = scaledSectionPoints(section, displayScale);
      const attribute = object.geometry.getAttribute("position");
      const sourceIndices = object.geometry.userData.sourceVertexIndices;
      for (let index = 0; index < attribute.count; index++) {
        attribute.setXYZ(index, ...points[sourceIndices?.[index] ?? index]);
      }
      attribute.needsUpdate = true;
      if (object.isMesh) object.geometry.computeVertexNormals();
      object.geometry.computeBoundingBox();
      object.geometry.computeBoundingSphere();
      return;
    }
    if (options.previewOnly) return;
    const sourceScale = positiveNumber(object.userData?.visualDeformationSourceScale);
    if (!sourceScale) return;
    const positions = object.userData.visualDeformationPositions;
    if (positions) {
      const attribute = object.geometry.getAttribute("position");
      const factor = displayScale / sourceScale;
      for (let index = 0; index < attribute.array.length; index += 1) {
        attribute.array[index] = positions.base[index] + (positions.source[index] - positions.base[index]) * factor;
      }
      attribute.needsUpdate = true;
      object.geometry.computeBoundingBox();
      object.geometry.computeBoundingSphere();
    } else if (object.morphTargetInfluences) {
      object.morphTargetInfluences[0] = 1 - displayScale / sourceScale;
    }
  });
}

function createTube(asset, config, format) {
  const { tubularSegments, radialSegments } = tubeTessellation(config);
  const points = readPoints(config.points);
  if (points.length < 2) {
    return invalidAsset(asset, "Tube assets require at least two points.");
  }
  const radius = positiveNumber(config.radius_m) ?? radiusFromBounds(asset.bounds, 0.035);
  const curve = new THREE.CatmullRomCurve3(points);
  // A solved tube is morphed against its undeformed one vertex for vertex, so
  // both are built on the undeformed path's frames and their rings only move
  // with the centreline. On frames of its own, a bent solved path turns its
  // rings away from the straight base's, and scaling the deformation up scaled
  // that turn too: an 80 mm pipe swelled to a tube metres across at x10.
  const basePoints = readPoints(config.base_points);
  const frameCurve = basePoints.length === points.length ? new THREE.CatmullRomCurve3(basePoints) : curve;
  if (frameCurve !== curve) curve.computeFrenetFrames = (segments, closed) => frameCurve.computeFrenetFrames(segments, closed);
  // Faceting comes from the bundle, which owns the section and states the budget
  // it swept to. The fallback matches that budget so a tube with no config - a
  // deformed envelope, a hand-built fixture - is not drawn at a different
  // resolution than a real one.
  const outer = new THREE.Mesh(
    new THREE.TubeGeometry(curve, tubularSegments, radius, radialSegments, false),
    materialForAsset(asset, config, { transparent: format === "tube_envelope" && config.envelope_type !== "insulation" })
  );
  const innerRadius = positiveNumber(config.inner_radius_m);
  if (!innerRadius || innerRadius >= radius) {
    outer.name = asset.id;
    return { format, object: outer };
  }

  const pipe = new THREE.Group();
  const innerMaterial = materialForAsset(asset, config);
  innerMaterial.side = THREE.BackSide;
  pipe.add(outer, new THREE.Mesh(new THREE.TubeGeometry(curve, tubularSegments, innerRadius, radialSegments, false), innerMaterial));

  const capMaterial = materialForAsset(asset, config);
  capMaterial.side = THREE.DoubleSide;
  const normal = new THREE.Vector3(0, 0, 1);
  for (const position of [0, 1]) {
    // Morph targets interpolate vertices, so caps must share the tube's coordinates.
    const capGeometry = new THREE.RingGeometry(innerRadius, radius, radialSegments * 2);
    capGeometry.applyQuaternion(new THREE.Quaternion().setFromUnitVectors(normal, frameCurve.getTangent(position).normalize()));
    capGeometry.translate(...curve.getPoint(position).toArray());
    pipe.add(new THREE.Mesh(capGeometry, capMaterial));
  }
  pipe.name = asset.id;
  return { format, object: pipe };
}

function createPolyline(asset, config, format) {
  const points = readPoints(config.points);
  if (points.length < 2) {
    return invalidAsset(asset, "Polyline assets require at least two points.");
  }
  const geometry = new THREE.BufferGeometry().setFromPoints(points);
  const opacity = opacityForConfig(config, 1);
  const isSupportLink = String(config.source ?? "").toLowerCase() === "tuba.support_link";
  if (isSupportLink) {
    // P->A attachment link: dashed so it never reads as structure, even
    // though it spans the same space. Dash in world units, scaled to the
    // link itself so a 0.25 m shoe link and a 4 m hanger link dash alike.
    const length = points[0].distanceTo(points[1]);
    const material = new THREE.LineDashedMaterial({
      color: colorForAsset(asset, config),
      dashSize: Math.max(length * 0.08, 1e-3),
      gapSize: Math.max(length * 0.05, 1e-3),
      depthWrite: false,
      opacity,
      transparent: true
    });
    const line = new THREE.Line(geometry, material);
    line.computeLineDistances();
    line.name = asset.id;
    line.userData.supportLink = "attachment";
    return { format, object: line };
  }
  const isAnalysisMesh = String(config.source ?? "").includes("analysis_mesh") || String(asset.id ?? "").includes("analysis_mesh");
  const line = new THREE.Line(
    geometry,
    new THREE.LineBasicMaterial({
      color: colorForAsset(asset, config),
      depthTest: !isAnalysisMesh,
      depthWrite: !isAnalysisMesh && opacity >= 1 && !config.transparent,
      linewidth: isAnalysisMesh ? 3 : 2,
      opacity,
      transparent: Boolean(config.transparent || opacity < 1 || isAnalysisMesh)
    })
  );
  if (isAnalysisMesh) {
    line.renderOrder = 500;
  }
  line.name = asset.id;
  return { format, object: line };
}

function createPoint(asset, config, format, state) {
  const point = readPoint(config.point ?? config.location ?? config.clash?.location) ?? centerOfBounds(asset.bounds);
  if (!point) {
    return invalidAsset(asset, "Point assets require a point or valid bounds.");
  }
  const isSupport = isSupportConfig(config);
  if (isSupport) {
    return createSupportGlyph(asset, config, format, point, state);
  }
  // FE nodes and requested-size samples are drawn at a fixed pixel size, as Gmsh
  // draws mesh nodes (Mesh.NodeSize 4 px, NodeType 0: solid colour dots, on top
  // of the lines). A node sized in metres vanished on a tower and the 1D
  // elements merged into plain lines. Refinement targets keep their extents.
  const isSizingSample = config.source === "tuba.analysis_mesh.review" && asset.id.startsWith("geometry:mesh_size:");
  if (isSizingSample || config.source === "tuba.analysis_mesh.node") {
    const geometry = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3()]);
    const material = new THREE.PointsMaterial({
      color: colorForAsset(asset, config), size: isSizingSample ? SIZING_SAMPLE_PX : FE_NODE_PX,
      sizeAttenuation: false, depthTest: isSizingSample
    });
    shadeAsBall(material, isSizingSample);
    const marker = new THREE.Points(geometry, material);
    marker.position.copy(point);
    marker.name = asset.id;
    if (!isSizingSample) marker.renderOrder = 501;
    return { format, object: marker };
  }
  const isAnalysisMesh = String(config.source ?? "").includes("analysis_mesh") || String(asset.id ?? "").includes("analysis_mesh");
  const radius = positiveNumber(config.radius_m) ?? radiusFromBounds(asset.bounds, format === "marker" ? 0.06 : isAnalysisMesh ? 0.025 : 0.035);
  const geometry = new THREE.SphereGeometry(radius, 16, 12);
  geometry.computeBoundingSphere();
  const material = materialForAsset(asset, config);
  if (isAnalysisMesh) {
    material.depthTest = false;
  }
  const mesh = new THREE.Mesh(geometry, material);
  if (isAnalysisMesh) {
    mesh.renderOrder = 501;
  }
  mesh.position.copy(point);
  mesh.name = asset.id;
  return { format, object: mesh };
}

function createLabel(asset, config, format, state) {
  const text = typeof config.text === "string" ? config.text : "";
  const point = readPoint(config.position);
  const height = positiveNumber(config.height);
  if (!text || !point || !height) return invalidAsset(asset, "Label assets require text, position, and a positive height.");
  const canvas = state.canvasFactory?.();
  const context = canvas?.getContext?.("2d");
  if (!context) return invalidAsset(asset, "Label rendering requires a 2D canvas context.");
  const fontSize = 64;
  const padding = 18;
  context.font = `600 ${fontSize}px sans-serif`;
  const dimensions = textTextureSize(text, context.measureText(text).width + padding * 2,
    fontSize + padding * 2, state.textureBudget);
  canvas.width = dimensions.width;
  canvas.height = dimensions.height;
  context.font = `600 ${fontSize}px sans-serif`;
  context.fillStyle = "rgba(15, 23, 42, 0.86)";
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.fillStyle = "#ffffff";
  context.textAlign = "center";
  context.textBaseline = "middle";
  context.fillText(text, canvas.width / 2, canvas.height / 2);
  const texture = new THREE.CanvasTexture(canvas);
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: texture, depthTest: false, transparent: true }));
  sprite.position.copy(point);
  sprite.scale.set(height * canvas.width / canvas.height, height, 1);
  sprite.renderOrder = 1100;
  sprite.name = asset.id;
  sprite.userData.pickable = false;
  return { format, object: sprite };
}

function createFrictionBadgeSprite(text, position, state, status = null, overLimit = false) {
  const canvasFactory = state?.canvasFactory ?? (() => globalThis.document?.createElement?.("canvas"));
  const canvas = canvasFactory();
  if (!canvas) return null;
  const context = canvas.getContext?.("2d");
  if (!context) return null;

  const fontSize = 44;
  const padX = 22;
  const padY = 12;
  context.font = `600 ${fontSize}px "IBM Plex Mono", monospace, sans-serif`;
  const textWidth = context.measureText ? context.measureText(text).width : 110;
  const dimensions = textTextureSize(text, textWidth + padX * 2, fontSize + padY * 2, state.textureBudget);
  canvas.width = dimensions.width;
  canvas.height = dimensions.height;

  context.font = `600 ${fontSize}px "IBM Plex Mono", monospace, sans-serif`;

  let borderColor = "rgba(245, 158, 11, 0.8)";
  let textColor = "#fef3c7";
  let bgColor = "rgba(15, 23, 42, 0.88)";

  if (overLimit) {
    borderColor = "rgba(220, 38, 38, 0.9)";
    textColor = "#fecaca";
  } else if (status === "sticking") {
    borderColor = "rgba(59, 130, 246, 0.85)";
    textColor = "#dbeafe";
  } else if (status === "sliding") {
    borderColor = "rgba(20, 184, 166, 0.85)";
    textColor = "#ccfbf1";
  } else if (status === "open") {
    borderColor = "rgba(148, 163, 184, 0.7)";
    textColor = "#cbd5e1";
  }

  context.fillStyle = bgColor;
  const radius = 10;
  if (typeof context.roundRect === "function") {
    context.beginPath();
    context.roundRect(0, 0, canvas.width, canvas.height, radius);
    context.fill();
    context.strokeStyle = borderColor;
    context.lineWidth = 3;
    context.stroke();
  } else {
    context.fillRect(0, 0, canvas.width, canvas.height);
  }

  context.fillStyle = textColor;
  context.textAlign = "center";
  context.textBaseline = "middle";
  context.fillText(text, canvas.width / 2, canvas.height / 2 + 1);

  const texture = new THREE.CanvasTexture(canvas);
  const material = new THREE.SpriteMaterial({
    map: texture,
    depthTest: false,
    depthWrite: false,
    transparent: true
  });
  const sprite = new THREE.Sprite(material);
  sprite.position.copy(position);
  // Sized on screen at draw time (scaleValueLabels).
  sprite.userData.aspect = canvas.width / canvas.height;
  sprite.renderOrder = 1100;
  sprite.userData.supportPart = "friction-badge";
  return sprite;
}

function createLoadBadgeSprite(text, position, state, kind = "force") {
  const canvasFactory = state?.canvasFactory ?? (() => globalThis.document?.createElement?.("canvas"));
  const canvas = canvasFactory();
  if (!canvas) return null;
  const context = canvas.getContext?.("2d");
  if (!context) return null;

  const fontSize = 44;
  const padX = 22;
  const padY = 12;
  context.font = `600 ${fontSize}px "IBM Plex Mono", monospace, sans-serif`;
  const textWidth = context.measureText ? context.measureText(text).width : 110;
  const dimensions = textTextureSize(text, textWidth + padX * 2, fontSize + padY * 2, state.textureBudget);
  canvas.width = dimensions.width;
  canvas.height = dimensions.height;

  context.font = `600 ${fontSize}px "IBM Plex Mono", monospace, sans-serif`;

  let borderColor = "rgba(59, 130, 246, 0.85)";
  let textColor = "#dbeafe";
  const bgColor = "rgba(15, 23, 42, 0.90)";

  if (kind === "moment") {
    borderColor = "rgba(20, 184, 166, 0.85)";
    textColor = "#ccfbf1";
  } else if (kind === "line_load") {
    borderColor = "rgba(2, 132, 199, 0.85)";
    textColor = "#e0f2fe";
  } else if (kind === "prescribed") {
    // Achromatic: the badge reads the same in Build and Review, where hue is
    // spent on input vs result and a support speaks in shape.
    borderColor = "rgba(212, 212, 212, 0.85)";
    textColor = "#f5f5f5";
  }

  context.fillStyle = bgColor;
  const radius = 10;
  if (typeof context.roundRect === "function") {
    context.beginPath();
    context.roundRect(0, 0, canvas.width, canvas.height, radius);
    context.fill();
    context.strokeStyle = borderColor;
    context.lineWidth = 3;
    context.stroke();
  } else {
    context.fillRect(0, 0, canvas.width, canvas.height);
  }

  context.fillStyle = textColor;
  context.textAlign = "center";
  context.textBaseline = "middle";
  context.fillText(text, canvas.width / 2, canvas.height / 2 + 1);

  const texture = new THREE.CanvasTexture(canvas);
  const material = new THREE.SpriteMaterial({
    map: texture,
    depthTest: false,
    depthWrite: false,
    transparent: true
  });
  const sprite = new THREE.Sprite(material);
  sprite.position.copy(position);
  // Sized on screen at draw time (scaleValueLabels).
  sprite.userData.aspect = canvas.width / canvas.height;
  sprite.renderOrder = 1100;
  sprite.name = `${kind}-badge`;
  sprite.userData.loadPart = "load-badge";
  sprite.userData.pickable = false;
  return sprite;
}

function formatMagnitudeWithPrefix(prefix, val, baseUnit) {
  let displayVal = val;
  let unit = baseUnit;
  if (val >= 1000) {
    displayVal = val / 1000;
    unit = baseUnit === "N" ? "kN" : baseUnit === "N·m" ? "kN·m" : "kN/m";
  }
  let str;
  if (Math.abs(displayVal - Math.round(displayVal)) < 1e-4) {
    str = String(Math.round(displayVal));
  } else {
    str = displayVal.toFixed(displayVal < 10 ? 1 : 1);
    if (str.endsWith(".0")) str = str.slice(0, -2);
  }
  return `${prefix} = ${str} ${unit}`;
}

function formatLoadBadgeText(kind, config) {
  if (config.badge_text) return String(config.badge_text);
  if (kind === "force") {
    if (config.vector_kind !== "force" && config.quantity !== "force" && !config.source?.includes("applied_loads")) {
      return null;
    }
    const components = Array.isArray(config.components) ? config.components.map(Number) : null;
    let mag = Number(config.magnitude);
    if (!Number.isFinite(mag) && components) {
      mag = Math.hypot(...components);
    }
    if (!Number.isFinite(mag) || mag <= 0) return null;
    return formatMagnitudeWithPrefix("F", mag, "N");
  }
  if (kind === "moment") {
    if (config.vector_kind !== "moment" && config.quantity !== "moment" && !String(config.result_type ?? "").endsWith("_moment")) {
      return null;
    }
    const components = Array.isArray(config.components) ? config.components.map(Number) : null;
    let mag = Number(config.magnitude);
    if (!Number.isFinite(mag) && components) {
      mag = Math.hypot(...components);
    }
    if (!Number.isFinite(mag) || mag <= 0) return null;
    return formatMagnitudeWithPrefix("M", mag, "N·m");
  }
  if (kind === "line_load") {
    const val = Number(config.value_npm ?? config.value);
    if (!Number.isFinite(val) || Math.abs(val) <= 0) return null;
    return formatMagnitudeWithPrefix("q", Math.abs(val), "N/m");
  }
  return null;
}

function createSupportGlyph(asset, config, format, point, state) {
  const requestedType = String(config.support_type ?? "custom").toLowerCase();
  const supportType = requestedType === "fixed" ? "anchor" : requestedType;
  const sceneSize = sizeOfBounds(state?.bounds ?? asset.bounds);
  const span = Math.max(sceneSize.x, sceneSize.y, sceneSize.z);
  // radius_m on a support asset is the radius of the pipe the support clamps
  // (builders/_objects.py writes max(attached_radii)), not a glyph size. Taking
  // it as the size drew every restraint flush with the pipe wall, where a 50%
  // opaque mark is invisible. The pipe sets the size now - the glyph must clear
  // the pipe it marks - and the span is only a small floor for unpiped nodes and
  // hairline members. At 1.8% of the span (capped 0.3 m) the span term won
  // everywhere: an 80 mm pipe on a 10 m tower got a restraint star 1.1 m across.
  const fitted = Math.max(
    (positiveNumber(config.radius_m) ?? 0) * 1.5,
    THREE.MathUtils.clamp(span * 0.006, 0.03, 0.1)
  );
  // A support that acts through a rigid patch on a small solid draws no larger
  // than that patch (body_extent_m): the glyph reaches about 3 * size each way.
  const bodyExtent = positiveNumber(config.body_extent_m);
  const size = bodyExtent ? Math.min(fitted, bodyExtent / 6) : fitted;
  // One definition of the support glyph's vocabulary, shared with the viewport
  // key: a colour changed here and not there used to leave the key naming a mark
  // that was no longer on screen. Coloured by role in Build, one neutral in
  // Review, where hue belongs to the results (supportGlyphs.js).
  const colors = supportPartColors(sceneStage(state ?? {}));
  const restraintMaterial = supportMaterial(colors.restraint, { part: "restraint" });
  const springMaterial = supportMaterial(colors.spring, { part: "spring" });
  const displacementMaterial = supportMaterial(colors.prescribed, {
    part: "prescribed",
    // Hollow, where a restraint is solid. A prescribed movement and a restraint
    // are both cones on the same axis, so fill is the half of shape that the
    // primitive geometry cannot express - and the key names it.
    wireframe: true,
    opacity: 0.9
  });
  const glyph = new THREE.Group();
  glyph.name = asset.id;
  glyph.position.copy(point);
  glyph.renderOrder = 20;
  glyph.userData.supportGlyph = "dof";
  glyph.userData.pickPriority = PICK_PRIORITY_ANNOTATION;
  glyph.userData.supportType = supportType;
  // Second channel: what the restraint acts against. Geometry, not color -
  // in Build, color already says which role a part plays.
  glyph.userData.supportAttachment = config.attached_to ? "attached" : "ground";

  const mesh = (geometry, role, material, position = null) => {
    const child = new THREE.Mesh(geometry, material);
    if (position) child.position.copy(position);
    child.userData.supportPart = role;
    glyph.add(child);
    return child;
  };

  const axes = [new THREE.Vector3(1, 0, 0), new THREE.Vector3(0, 1, 0), new THREE.Vector3(0, 0, 1)];
  const blocked = supportBlockedDofs(config);
  if (blocked.every(Boolean)) {
    mesh(new THREE.BoxGeometry(size * 2, size * 2, size * 2), "fixed-block", restraintMaterial);
  } else {
    for (let index = 0; index < 3; index += 1) {
      if (!blocked[index]) continue;
      for (const side of [-1, 1]) {
        const axis = axes[index];
        const cone = mesh(
          new THREE.ConeGeometry(size, size * 2, 24),
          "restraint-cone",
          restraintMaterial,
          axis.clone().multiplyScalar(side * size * 2)
        );
        cone.quaternion.setFromUnitVectors(
          new THREE.Vector3(0, 1, 0),
          axis.clone().multiplyScalar(-side)
        );
        cone.userData.supportAxis = index;
        cone.userData.supportSide = side;
      }
    }
    for (let index = 3; index < 6; index += 1) {
      if (!blocked[index]) continue;
      const rotation = mesh(
        new THREE.TorusGeometry(size * 0.85, size * 0.18, 8, 24),
        "restraint-rotation",
        restraintMaterial
      );
      rotation.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), axes[index - 3]);
      rotation.userData.supportAxis = index;
    }
  }

  const stiffness = Array.isArray(config.stiffness_matrix) ? config.stiffness_matrix.map(Number) : [];
  for (let index = 0; index < 3; index += 1) {
    if (!Number.isFinite(stiffness[index]) || Math.abs(stiffness[index]) <= 0) continue;
    addSupportSpringCoil(mesh, axes[index], size, springMaterial, index);
  }
  if (stiffness.length === 0 && Number.isFinite(Number(config.stiffness)) && Math.abs(Number(config.stiffness)) > 0) {
    const direction = readPoint(config.direction);
    if (direction?.lengthSq() > 1e-12) {
      addSupportSpringCoil(mesh, direction.normalize(), size, springMaterial, "direction");
    }
  }
  for (let index = 3; index < 6; index += 1) {
    if (!Number.isFinite(stiffness[index]) || Math.abs(stiffness[index]) <= 0) continue;
    const rotation = mesh(
      new THREE.TorusGeometry(size * 1.25, size * 0.22, 8, 24),
      "spring-rotation",
      springMaterial
    );
    rotation.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), axes[index - 3]);
    rotation.userData.supportAxis = index;
  }

  // Three or six components (DX..DRZ). Any non-zero one is a prescribed
  // movement, however small: a 0.5 µm settlement or a rotation-only support
  // used to get no mark at all, because only the translation length was read.
  const imposedValues = (Array.isArray(config.imposed_displacement) ? config.imposed_displacement : [])
    .slice(0, 6).map((value) => (Number.isFinite(Number(value)) ? Number(value) : 0));
  const translation = new THREE.Vector3(...[0, 1, 2].map((index) => imposedValues[index] ?? 0));
  const rotationVector = new THREE.Vector3(...[3, 4, 5].map((index) => imposedValues[index] ?? 0));
  const moves = (vector) => vector.x !== 0 || vector.y !== 0 || vector.z !== 0;
  // Scaled before normalising, so a value whose square underflows still has a
  // direction.
  const unit = (vector) => vector.divideScalar(Math.max(Math.abs(vector.x), Math.abs(vector.y), Math.abs(vector.z))).normalize();
  // Clear of the restraint and spring marks: drawn from the node, the hollow
  // cone sat inside the anchor block (or the cones on its own axis) of a
  // support that also holds every DOF, which is the common prescribed case.
  // Restraint cones reach 3 * size and spring rings 3.5 * size, so the mark
  // starts just past them and a stroked shaft ties it back to the node.
  const start = glyph.children.length > 0 ? size * 3.8 : 0;
  const shaftTo = (direction) => {
    if (start <= 0) return;
    const shaft = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), direction.clone().multiplyScalar(start)]),
      new THREE.LineBasicMaterial({ color: displacementMaterial.color, transparent: true, opacity: 0.9, userData: { supportPart: "prescribed" } })
    );
    shaft.userData.supportPart = "prescribed-shaft";
    glyph.add(shaft);
  };
  let badgeDirection = null;
  if (moves(translation)) {
    const direction = unit(translation);
    badgeDirection = direction;
    const displacement = mesh(
      new THREE.ConeGeometry(size, size * 3, 24),
      "prescribed-displacement",
      displacementMaterial,
      direction.clone().multiplyScalar(start + size * 1.5)
    );
    displacement.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction);
    shaftTo(direction);
  }
  if (moves(rotationVector)) {
    // The moment vectors' right-hand-rule arc, about the rotation axis, hollow
    // like the cone. Its own mark, so a rotation-only support is not bare.
    const axis = unit(rotationVector);
    badgeDirection ??= axis;
    const turn = new THREE.Group();
    turn.add(...rotationArc(size * 1.2, size * 0.08, size * 0.3, size * 0.7, displacementMaterial));
    turn.position.copy(axis.clone().multiplyScalar(start + size * 1.5));
    turn.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), axis);
    turn.userData.supportPart = "prescribed-rotation";
    glyph.add(turn);
    if (!moves(translation)) shaftTo(axis);
  }
  if (badgeDirection) {
    // "ΔZ = 80 mm · ΔRZ = 0.01 rad": every non-zero component.
    const badgeText = prescribedDisplacementText(config, getUnitSystem(state));
    const badge = badgeText
      ? createLoadBadgeSprite(badgeText, badgeDirection.clone().multiplyScalar(start + size * 4.4), state, "prescribed")
      : null;
    if (badge) glyph.add(badge);
  }

  const mu = Number(config.friction_coefficient);
  const hasFriction = Number.isFinite(mu) && mu > 0;
  const isRest = supportType === "rest";

  if (isRest && (hasFriction || config.attached_to || config.normal_stiffness != null)) {
    const rawNormal = readPoint(config.contact_normal ?? config.direction) ?? new THREE.Vector3(0, 0, 1);
    const normal = rawNormal.lengthSq() > 1e-12 ? rawNormal.clone().normalize() : new THREE.Vector3(0, 0, 1);
    const normalAxis = Math.abs(normal.z) >= 0.8 ? 2 : (Math.abs(normal.y) >= 0.8 ? 1 : 0);

    let contactStatus = null;
    let contactOverLimit = false;
    if (state) {
      const records = contactRecords(state);
      const key = config.support_id ?? config.id ?? asset.id?.split(":").pop();
      const contactRecord = records[key];
      if (contactRecord) {
        contactStatus = contactRecord.status;
        contactOverLimit = Number(contactRecord.utilization) > 1.001;
      }
    }

    const padWidth = size * 2.2;
    const padLength = size * 2.6;
    const padThickness = size * 0.16;

    const pipeRadius = positiveNumber(config.radius_m) ?? (size * 0.7);
    const padPos = normal.clone().multiplyScalar(-pipeRadius - padThickness / 2);
    const padRot = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 0, 1), normal);

    // Utilization past the friction limit outranks the status colour: the shoe
    // is over its Coulomb envelope whatever the state word says.
    let padColor = hasFriction ? 0xd97706 : 0xdaa520;
    if (contactOverLimit) padColor = 0xdc2626;
    else if (contactStatus === "sticking") padColor = 0x2563eb;
    else if (contactStatus === "sliding") padColor = 0x0f766e;
    else if (contactStatus === "open") padColor = 0x64748b;

    const padMaterial = new THREE.MeshStandardMaterial({
      color: padColor,
      roughness: 0.35,
      metalness: 0.25,
      depthTest: true,
      transparent: contactStatus === "open",
      opacity: contactStatus === "open" ? 0.45 : 0.95
    });

    const padMesh = mesh(
      new THREE.BoxGeometry(padWidth, padLength, padThickness),
      "contact-shoe-pad",
      padMaterial,
      padPos
    );
    padMesh.quaternion.copy(padRot);
    padMesh.userData.supportAxis = normalAxis;

    const edgeColor = contactOverLimit ? 0xfca5a5 :
                      contactStatus === "sticking" ? 0x93c5fd :
                      contactStatus === "sliding" ? 0x5eead4 :
                      contactStatus === "open" ? 0x94a3b8 :
                      (hasFriction ? 0xfef3c7 : 0xffffff);
    const padEdges = new THREE.LineSegments(
      new THREE.EdgesGeometry(new THREE.BoxGeometry(padWidth, padLength, padThickness)),
      new THREE.LineBasicMaterial({ color: edgeColor, transparent: true, opacity: 0.85 })
    );
    padMesh.add(padEdges);

    const halfW = padWidth * 0.36;
    const halfL = padLength * 0.36;
    const guideTop = padThickness / 2 + 0.001;
    const guideGeo = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(-halfW, 0, guideTop), new THREE.Vector3(halfW, 0, guideTop),
      new THREE.Vector3(0, -halfL, guideTop), new THREE.Vector3(0, halfL, guideTop)
    ]);
    const guideLines = new THREE.LineSegments(
      guideGeo,
      new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.85 })
    );
    guideLines.name = "sliding-plane-guides";
    padMesh.add(guideLines);

    if (hasFriction) {
      let badgeText = `μ = ${mu.toFixed(2)}`;
      const icon = contactStatus ? (contactStatus === "sticking" ? "■" : (contactStatus === "sliding" ? "➜" : "○")) : null;
      if (icon) badgeText = `${icon} ${badgeText}`;
      const refTangent = Math.abs(normal.x) < 0.9 ? new THREE.Vector3(1, 0, 0) : new THREE.Vector3(0, 1, 0);
      const tangent = new THREE.Vector3().crossVectors(normal, refTangent).normalize();
      const badgePos = padPos.clone().add(tangent.multiplyScalar(padWidth * 0.85));
      const badgeSprite = createFrictionBadgeSprite(badgeText, badgePos, state, contactStatus, contactOverLimit);
      if (badgeSprite) {
        glyph.add(badgeSprite);
      }
      // The sticking/sliding/open icon is a Code_Aster result, not an authored
      // value, so Show values must not take it off screen with the μ. One
      // sprite cannot drop half its text, so the icon alone stands in for the
      // badge while values are hidden (applyValueLabelVisibility).
      const stateSprite = icon ? createFrictionBadgeSprite(icon, badgePos, state, contactStatus, contactOverLimit) : null;
      if (stateSprite) {
        stateSprite.userData.supportPart = "friction-state";
        stateSprite.visible = false;
        glyph.add(stateSprite);
      }
    }
  }

  if (!config.attached_to) {
    // Grounded: a hatch plate hugging the glyph's underside in -Z (Tuba is
    // Z-up). Measured off the parts, not a fixed offset, so an anchor cube
    // and a rest's cones both get a plate that reads as attached to them.
    // Attached supports skip it - their dashed P->A link says where they go.
    glyph.updateMatrixWorld(true);
    const drawn = measuredWithoutLabels([glyph], () => new THREE.Box3().setFromObject(glyph));
    const under = Number.isFinite(drawn.min.z) ? drawn.min.z - glyph.position.z : -size;
    const thickness = size * 0.18;
    const plate = mesh(
      new THREE.BoxGeometry(size * 2.4, size * 2.4, thickness),
      "ground-hatch",
      supportMaterial(SUPPORT_GROUND_COLOR),
      new THREE.Vector3(0, 0, under - size * 0.12 - thickness / 2)
    );
    plate.userData.supportAxis = 2;
  }
  return { format, object: glyph };
}

// 85% opaque: at 50% the dark neutral came out a washed-out grey that read as
// disabled. Pipe-sized glyphs hide little of the pipe, so they can be solid.
function supportMaterial(color, { part = null, transparent = true, opacity = 0.85, wireframe = false } = {}) {
  return new THREE.MeshBasicMaterial({
    color,
    depthTest: true,
    depthWrite: false,
    opacity,
    transparent,
    wireframe,
    // applySupportStage recolours by this when the stage moves without a rebuild.
    userData: part ? { supportPart: part } : {}
  });
}

// A stage move with no bundle change - a studio with nothing solved shows the
// build bundle in both stages - keeps the graph, so the support colours follow
// the stage here instead of through a rebuild.
export function applySupportStage(graph, stage) {
  if (graph.supportStage === stage) return;
  graph.supportStage = stage;
  const colors = supportPartColors(stage);
  graph.root.traverse((part) => {
    const role = part.material?.userData?.supportPart;
    if (role) part.material.color.set(colors[role]);
  });
}

// The textbook spring-support symbol: a coil from the node out along the
// spring's axis, standing on a seat. Four stacked rings read as nothing in
// particular. It runs to the negative side - down for a vertical spring, onto
// the ground plate - and ends inside the 3.8 * size the prescribed mark keeps
// clear.
function addSupportSpringCoil(mesh, axis, size, material, supportAxis) {
  const turns = 4;
  const radius = size * 0.55;
  const from = size * 0.9;
  const to = size * 3.1;
  const steps = turns * 16;
  const points = [new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, -from, 0)];
  for (let step = 0; step <= steps; step += 1) {
    const angle = (step / steps) * turns * Math.PI * 2;
    points.push(new THREE.Vector3(radius * Math.cos(angle), -(from + (to - from) * step / steps), radius * Math.sin(angle)));
  }
  points.push(new THREE.Vector3(0, -to, 0));
  const toAxis = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), axis);
  const coil = mesh(
    new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points), steps * 2, size * 0.09, 6, false).applyQuaternion(toAxis),
    "spring-coil",
    material
  );
  coil.userData.supportAxis = supportAxis;
  const seat = mesh(
    new THREE.CylinderGeometry(radius * 1.35, radius * 1.35, size * 0.14, 20).translate(0, -to - size * 0.07, 0).applyQuaternion(toAxis),
    "spring-seat",
    material
  );
  seat.userData.supportAxis = supportAxis;
}

function createTuyauSubpointGlyphs(asset, config, format, state) {
  const starts = readPoints(config.starts ?? config.start_points);
  const ends = readPoints(config.ends ?? config.end_points);
  const count = Math.min(starts.length, ends.length);
  if (count < 1) {
    return invalidAsset(asset, "TUYAU sub-point glyph assets require start and end point arrays.");
  }
  const xray = config.xray === true;
  const threshold = config.value_threshold ?? null;
  const radius = positiveNumber(config.radius_m) ?? 0.006;
  // Thinned marks read at a glance and have nothing behind them to be confused
  // with, so the mode that surfaces the worst stations draws them a little
  // heavier than a full field has to.
  const markRadius = radius * (xray ? 1.6 : 1);
  const radialSegments = Math.max(4, Math.min(16, Math.floor(Number(config.radial_segments) || 8)));
  const geometry = new THREE.CylinderGeometry(markRadius, markRadius, 1, radialSegments, 1, false);
  const material = new THREE.MeshBasicMaterial({
    color: 0xffffff,
    opacity: opacityForConfig(config, 0.94),
    transparent: true,
    // An x-ray batch ignores depth on purpose: the pipe in front of a bore or
    // mid-wall station is exactly what would otherwise hide it. It is the one
    // thing drawn over the analysis mesh and under the load preview.
    depthTest: !xray,
    depthWrite: !xray
  });
  const mesh = new THREE.InstancedMesh(geometry, material, count);
  const matrix = new THREE.Matrix4();
  const midpoint = new THREE.Vector3();
  const direction = new THREE.Vector3();
  const scale = new THREE.Vector3(1, 1, 1);
  const quaternion = new THREE.Quaternion();
  const yAxis = new THREE.Vector3(0, 1, 0);
  // Kept raw: an absent value has to stay absent all the way to the pass test and
  // the colour lookup, or `Number(null)` quietly reports it as zero stress.
  const values = Array.isArray(config.values) ? config.values : [];
  const legend = subpointLegend(config, values.map(Number), state);
  let written = 0;

  for (let index = 0; index < count; index += 1) {
    if (!subpointPassesThreshold(values[index], threshold)) {
      continue;
    }
    direction.copy(ends[index]).sub(starts[index]);
    const length = direction.length();
    if (length <= 1e-12) {
      continue;
    }
    midpoint.copy(starts[index]).add(ends[index]).multiplyScalar(0.5);
    quaternion.setFromUnitVectors(yAxis, direction.normalize());
    scale.set(1, length, 1);
    matrix.compose(midpoint, quaternion, scale);
    mesh.setMatrixAt(written, matrix);
    mesh.setColorAt(written, new THREE.Color(colorForSubpointValue(values[index], legend, asset, config)));
    written += 1;
  }

  mesh.count = written;
  mesh.renderOrder = xray ? SUBPOINT_XRAY_RENDER_ORDER : 0;
  // The count the body metrics quote is read back off the built mesh, so a
  // thinned field can never claim more points than it drew.
  mesh.userData.subpointDrawnCount = written;
  mesh.instanceMatrix.needsUpdate = true;
  if (mesh.instanceColor) {
    mesh.instanceColor.needsUpdate = true;
  }
  mesh.name = asset.id;
  return { format, object: mesh };
}

// A right-hand-rule arc about local +Y with its arrowhead: the moment vectors'
// rotation mark, also drawn for a prescribed rotation.
function rotationArc(radius, tubeRadius, headRadius, headLength, material) {
  const arcStart = -Math.PI / 4;
  const arcSweep = Math.PI * 1.5;
  const points = Array.from({ length: 33 }, (_, index) => {
    const angle = arcStart + arcSweep * index / 32;
    return new THREE.Vector3(radius * Math.cos(angle), 0, -radius * Math.sin(angle));
  });
  const arc = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points), 32, tubeRadius, 10, false), material);
  const endAngle = arcStart + arcSweep;
  const tangent = new THREE.Vector3(-Math.sin(endAngle), 0, -Math.cos(endAngle)).normalize();
  const head = new THREE.Mesh(new THREE.ConeGeometry(headRadius, headLength, 16), material.clone());
  head.position.copy(points.at(-1)).addScaledVector(tangent, headLength / 2);
  head.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), tangent);
  return [arc, head];
}

function createVector(asset, config, format, state) {
  // Below the displayed 0.01 SI-unit precision, keep the recorded number in
  // the labels/table and avoid an artificial finite-length zero-result arrow.
  if (config.reaction_display && config.display_zero) return { format, object: null };
  const start = readPoint(config.start);
  const end = readPoint(config.end);
  if (!start || !end) {
    return invalidAsset(asset, "Vector assets require start and end points.");
  }
  const direction = end.clone().sub(start);
  const length = direction.length();
  if (length <= 1e-12) {
    return invalidAsset(asset, "Vector assets require non-zero length.");
  }
  const unitDirection = direction.normalize();
  const color = colorForAsset(asset, config);
  const headLength = Math.min(length * 0.25, 0.18);
  const headWidth = Math.min(length * 0.12, 0.08);
  if (config.vector_kind === "moment" || String(config.result_type ?? "").endsWith("_moment")) {
    const localAxis = new THREE.Vector3(0, 1, 0);
    const moment = new THREE.Group();
    moment.position.copy(start);
    moment.quaternion.setFromUnitVectors(localAxis, unitDirection);
    moment.userData.pickPriority = PICK_PRIORITY_ANNOTATION;

    const axis = new THREE.ArrowHelper(localAxis, new THREE.Vector3(), length, color, headLength, headWidth);
    axis.name = "moment-axis";

    const arcRadius = length * (config.reaction_display ? 0.38 : 0.22);
    const [arc, arcHead] = rotationArc(arcRadius, length * 0.012, length * 0.045, length * 0.12, new THREE.MeshBasicMaterial({ color }));
    arc.name = "moment-rotation-arc";
    arcHead.name = "moment-rotation-head";

    moment.add(axis, arc, arcHead);

    const badgeText = formatLoadBadgeText("moment", config);
    if (badgeText && !config.reaction_display) {
      const badgeLocalPos = new THREE.Vector3(arcRadius + 0.08, length * 0.5, 0);
      const badgeSprite = createLoadBadgeSprite(badgeText, badgeLocalPos, state, "moment");
      if (badgeSprite) {
        moment.add(badgeSprite);
      }
    }

    moment.name = asset.id;
    if (config.reaction_display) makeReadableReaction(moment, config, 'moment');
    return { format, object: moment };
  }
  if (config.reaction_display) {
    const group = new THREE.Group(); group.position.copy(start);
    group.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), unitDirection);
    const tipLength = length * 0.25;
    const shaft = new THREE.Mesh(new THREE.CylinderGeometry(length * 0.018, length * 0.018,
      length - tipLength, 10), new THREE.MeshBasicMaterial({ color }));
    shaft.name = 'reaction-force-shaft'; shaft.position.y = (length - tipLength) / 2;
    const head = new THREE.Mesh(new THREE.ConeGeometry(length * 0.09, tipLength, 16),
      new THREE.MeshBasicMaterial({ color }));
    head.name = 'reaction-force-head'; head.position.y = length - tipLength / 2;
    group.add(shaft, head); group.name = asset.id;
    makeReadableReaction(group, config, 'force');
    return { format, object: group };
  }
  const arrow = new THREE.ArrowHelper(
    unitDirection,
    start,
    length,
    color,
    headLength,
    headWidth
  );
  arrow.userData.pickPriority = PICK_PRIORITY_ANNOTATION;

  const badgeText = formatLoadBadgeText("force", config);
  if (badgeText) {
    const up = Math.abs(unitDirection.z) < 0.9 ? new THREE.Vector3(0, 0, 1) : new THREE.Vector3(0, 1, 0);
    const side = new THREE.Vector3().crossVectors(unitDirection, up).normalize();
    const offsetDist = Math.max(headWidth * 1.6, 0.08);
    const badgeWorldPos = start.clone()
      .addScaledVector(unitDirection, length * 0.5)
      .addScaledVector(side, offsetDist);
    const badgeLocalPos = badgeWorldPos.clone().sub(start);
    const badgeSprite = createLoadBadgeSprite(badgeText, badgeLocalPos, state, "force");
    if (badgeSprite) {
      arrow.add(badgeSprite);
    }
  }

  arrow.name = asset.id;
  return { format, object: arrow };
}

function makeReadableReaction(group, config, kind) {
  group.userData.supportReaction = { kind, node_id: config.node_id,
    components: [...(kind === 'force' ? config.reaction_force_n : config.reaction_moment_nm)],
    unit: kind === 'force' ? 'N' : 'N m' };
  group.traverse(part => {
    part.renderOrder = 800;
    for (const material of Array.isArray(part.material) ? part.material : part.material ? [part.material] : []) {
      material.depthTest = false; material.depthWrite = false;
    }
  });
}

function createLineLoadComb(asset, config, format, state) {
  const starts = readPoints(config.arrow_starts);
  const ends = readPoints(config.arrow_ends);
  if (!starts.length || starts.length !== ends.length) {
    return invalidAsset(asset, "Line load comb assets require matching arrow_starts and arrow_ends points.");
  }
  const color = colorForAsset(asset, config);
  const combGroup = new THREE.Group();
  combGroup.userData.pickPriority = PICK_PRIORITY_ANNOTATION;

  for (let index = 0; index < starts.length; index += 1) {
    const start = starts[index];
    const end = ends[index];
    const direction = end.clone().sub(start);
    const length = direction.length();
    if (length <= 1e-12) continue;

    const unitDirection = direction.normalize();
    const headLength = Math.min(length * 0.28, 0.18);
    const headWidth = Math.min(length * 0.14, 0.09);
    const arrow = new THREE.ArrowHelper(
      unitDirection,
      start,
      length,
      color,
      headLength,
      headWidth
    );
    arrow.name = "line-load-arrow";
    combGroup.add(arrow);
  }

  const crestPoints = readPoints(config.crest_points ?? config.arrow_starts);
  if (crestPoints.length >= 2) {
    const crestGeometry = new THREE.BufferGeometry().setFromPoints(crestPoints);
    const crestMaterial = new THREE.LineBasicMaterial({ color });
    const crestLine = new THREE.Line(crestGeometry, crestMaterial);
    crestLine.name = "line-load-crest";
    combGroup.add(crestLine);
  }

  // Give the planar comb a real pick volume. Its depth follows the glyph size,
  // so the same target works for small pipework and large racks.
  const pickBounds = new THREE.Box3().setFromObject(combGroup);
  if (!pickBounds.isEmpty()) {
    const depth = starts.reduce((maximum, start, i) => Math.max(maximum, start.distanceTo(ends[i])), 0) * 0.25;
    const size = pickBounds.getSize(new THREE.Vector3()).max(new THREE.Vector3(depth, depth, depth));
    const volume = new THREE.Mesh(
      new THREE.BoxGeometry(size.x, size.y, size.z),
      new THREE.MeshBasicMaterial({ visible: false, side: THREE.DoubleSide })
    );
    volume.name = "line-load-pick-volume";
    volume.position.copy(pickBounds.getCenter(new THREE.Vector3()));
    volume.userData.pickVolumeHit = true;
    combGroup.add(volume);
    combGroup.userData.pickVolume = volume;
  }

  const showBadge = config.show_badge !== false;
  const badgeText = formatLoadBadgeText("line_load", config);
  if (showBadge && badgeText && crestPoints.length >= 1 && starts.length >= 1) {
    const midIdx = Math.floor(crestPoints.length / 2);
    const crestMid = crestPoints[midIdx].clone();
    const arrowDiff = ends[0].clone().sub(starts[0]);
    const arrowLen = arrowDiff.length();
    const arrowDir = arrowLen > 1e-6 ? arrowDiff.normalize() : new THREE.Vector3(0, 0, -1);
    const badgePos = crestMid.addScaledVector(arrowDir, -Math.max(arrowLen * 0.3, 0.09));
    const badgeSprite = createLoadBadgeSprite(badgeText, badgePos, state, "line_load");
    if (badgeSprite) {
      combGroup.add(badgeSprite);
    }
  }

  combGroup.name = asset.id;
  return { format, object: combGroup };
}

function createBox(asset, config, format) {
  const bounds = normalizeBounds(config.bounds ?? config.obstacle?.bounds ?? asset.bounds);
  if (!bounds) {
    return invalidAsset(asset, "Box assets require valid bounds.");
  }
  const size = sizeOfBounds(bounds);
  const geometry = new THREE.BoxGeometry(Math.max(size.x, 1e-6), Math.max(size.y, 1e-6), Math.max(size.z, 1e-6));
  const mesh = new THREE.Mesh(geometry, materialForAsset(asset, config));
  mesh.position.copy(centerOfBounds(bounds));
  mesh.name = asset.id;

  const edges = new THREE.LineSegments(
    new THREE.EdgesGeometry(geometry),
    new THREE.LineBasicMaterial({ color: darkenColor(colorForAsset(asset, config)) })
  );
  mesh.add(edges);
  return { format, object: mesh };
}

function createCylinder(asset, config, format) {
  const bounds = normalizeBounds(config.bounds ?? config.obstacle?.bounds ?? asset.bounds);
  if (!bounds) {
    return invalidAsset(asset, "Cylinder assets require valid bounds.");
  }
  const size = sizeOfBounds(bounds);
  const extents = [size.x, size.y, size.z];
  const axis = extents.indexOf(Math.max(...extents));
  const radius = Math.min(...extents.filter((_, index) => index !== axis)) / 2;
  if (!(radius > 1e-6)) {
    return invalidAsset(asset, "Cylinder assets require a positive radius.");
  }
  const geometry = new THREE.CylinderGeometry(radius, radius, Math.max(extents[axis], 1e-6), 32, 1, false);
  const mesh = new THREE.Mesh(geometry, materialForAsset(asset, config));
  mesh.position.copy(centerOfBounds(bounds));
  if (axis === 0) {
    mesh.rotation.z = Math.PI / 2;
  } else if (axis === 2) {
    mesh.rotation.x = Math.PI / 2;
  }
  mesh.name = asset.id;

  const edges = new THREE.LineSegments(
    new THREE.EdgesGeometry(geometry, 30),
    new THREE.LineBasicMaterial({ color: darkenColor(colorForAsset(asset, config)) })
  );
  mesh.add(edges);
  return { format, object: mesh };
}

function createMesh(asset, config, payload, format, state) {
  const vertices = config.vertices ?? payload.vertices ?? config.mesh?.vertices;
  const faces = config.triangles ?? config.faces ?? config.indices ?? payload.faces ?? payload.indices ?? config.mesh?.faces;
  if (!Array.isArray(vertices) || vertices.length < 3) {
    return invalidAsset(asset, "Mesh assets require vertices.");
  }
  const flatVertices = vertices.flat();
  if (!flatVertices.every(Number.isFinite)) {
    return invalidAsset(asset, "Mesh vertices must be finite numbers.");
  }
  let geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(flatVertices, 3));
  if (Array.isArray(faces) && faces.length > 0) {
    geometry.setIndex(
      faces.flatMap((face) =>
        Array.isArray(face) && face.length === 4
          ? [face[0], face[1], face[2], face[0], face[2], face[3]]
          : face
      )
    );
  }
  const memberPoints = MEMBER_SURFACE_SOURCES.has(config.source) ? readPoints(config.points) : [];
  const cornerEdges = memberPoints.length >= 2
    ? memberCornerEdges(geometry, memberPoints.at(-1).clone().sub(memberPoints[0]))
    : [];
  geometry = splitSurfaceCreases(geometry, config.base_vertices);
  const meshConfig = { opacity: 1, ...config };
  const material = materialForAsset(asset, meshConfig);
  material.side = THREE.DoubleSide;
  const vertexValues = Array.isArray(config.vertex_values) ? config.vertex_values.map(Number) : [];
  if (vertexValues.length === vertices.length && vertexValues.every(Number.isFinite)) {
    const legend = subpointLegend(config, vertexValues, state, asset);
    const sourceIndices = geometry.userData.sourceVertexIndices ?? vertices.map((_, index) => index);
    const colors = sourceIndices.flatMap((index) => {
      const value = vertexValues[index];
      const color = new THREE.Color(colorForSubpointValue(value, legend, asset, config));
      return [color.r, color.g, color.b];
    });
    geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
    material.vertexColors = true;
    // Three multiplies vertex colours by the material colour. Left at the
    // field's peak tint (yellow), it erased blue and drew every low-stress node
    // of a solid near-black; reference grey and opacity still apply.
    if (!config.reference_geometry) material.color.set(0xffffff);
  }
  const mesh = new THREE.Mesh(geometry, material);
  if (config.show_edges || (asset.object_ids ?? []).some(id => state.sourceMeshObjectIds?.includes(id))) {
    material.polygonOffset = true;
    material.polygonOffsetFactor = Math.max(material.polygonOffsetFactor, 1);
    material.polygonOffsetUnits = Math.max(material.polygonOffsetUnits, 1);
    const opacity = opacityForConfig(meshConfig, 1);
    const surfaceEdges = config.surface_edge_indices;
    let edgeGeometry;
    if (Array.isArray(surfaceEdges) && surfaceEdges.length > 0) {
      edgeGeometry = new THREE.BufferGeometry();
      edgeGeometry.setAttribute("position", geometry.getAttribute("position"));
      edgeGeometry.setIndex(surfaceEdges.flat());
    } else {
      edgeGeometry = new THREE.WireframeGeometry(geometry);
    }
    const edges = new THREE.LineSegments(edgeGeometry, meshEdgeMaterial(asset, meshConfig, opacity));
    // Shares the mesh's positions, which deformation rewrites; its own bounding
    // sphere stays where it was first drawn and would cull the lines.
    if (edgeGeometry.getAttribute("position") === geometry.getAttribute("position")) edges.frustumCulled = false;
    mesh.add(edges);
  }
  if (cornerEdges.length > 0) {
    material.polygonOffset = true;
    material.polygonOffsetFactor = Math.max(material.polygonOffsetFactor, 1);
    material.polygonOffsetUnits = Math.max(material.polygonOffsetUnits, 1);
    const edgeGeometry = new THREE.BufferGeometry();
    edgeGeometry.setAttribute("position", geometry.getAttribute("position"));
    edgeGeometry.setIndex(cornerEdges);
    // Twice the member's opacity: a greyed member (32%) is exactly where a
    // square tube reads as a pipe, so its corners must still show, and dimming
    // a body still dims them.
    const corners = new THREE.LineSegments(edgeGeometry, meshEdgeMaterial(asset, meshConfig, Math.min(1, material.opacity * 2)));
    corners.userData.memberCorners = true;
    // Shares the mesh's positions, which deformation rewrites; its own bounding
    // sphere stays where it was first drawn and would cull the lines.
    corners.frustumCulled = false;
    mesh.add(corners);
  }
  const volumeVertices = config.volume_vertices;
  const volumeEdgeIndices = config.volume_edge_indices;
  if (Array.isArray(volumeVertices) && volumeVertices.length > 0 && Array.isArray(volumeEdgeIndices) && volumeEdgeIndices.length > 0) {
    const edgeGeometry = new THREE.BufferGeometry();
    edgeGeometry.setAttribute("position", new THREE.Float32BufferAttribute(volumeVertices.flat(), 3));
    edgeGeometry.setIndex(volumeEdgeIndices.flat());
    const volumeEdges = new THREE.LineSegments(edgeGeometry, meshEdgeMaterial(asset, meshConfig));
    volumeEdges.userData.volumeMeshEdges = true;
    volumeEdges.visible = false;
    mesh.add(volumeEdges);
  }
  mesh.name = asset.id;
  return { format, object: mesh };
}

function meshEdgeMaterial(asset, config, opacity = opacityForConfig(config, 1)) {
  return new THREE.LineBasicMaterial({
    color: 0x1f2937,
    depthWrite: false,
    opacity,
    transparent: opacity < 1
  });
}

function addReferenceHelpers(scene, bounds, gridVisible = true) {
  const size = sizeOfBounds(bounds);
  const span = Math.max(size.x, size.y, size.z, 1);
  const center = centerOfBounds(bounds);

  scene.add(new THREE.HemisphereLight(0xffffff, 0x8b94a3, 2.1));
  const directional = new THREE.DirectionalLight(0xffffff, 2.4);
  directional.position.set(center.x + span, center.y - span, center.z + span);
  scene.add(directional);

  // Sized to the model, not half again as large. At 1.5x the grid filled the
  // frame that the camera had fitted to the geometry, so the subject read as
  // small even when it was framed correctly.
  // Toggled from the Ground grid row in the Overlays band. The lights above
  // are not optional - they are how anything is visible at all - so only the
  // grid answers to it. Always built; updateSceneGraphVisibility flips it.
  const grid = new THREE.GridHelper(span * 1.05, 10, 0xb8c2d0, 0xe1e7ef);
  grid.name = "reference-grid";
  grid.rotation.x = Math.PI / 2;
  grid.position.set(center.x, center.y, bounds[2] - span * 0.03);
  grid.visible = gridVisible;
  scene.add(grid);

  // No axes helper. It drew a second orientation indicator floating at the
  // centre of the bounds - in mid-air, since the bounds centre is rarely on the
  // geometry - and the interactive view gizmo in the corner already says which
  // way X, Y and Z point.
  return grid;
}

function setRenderMetadata(object, asset, format) {
  const metadata = {
    assetId: asset.id,
    bounds: asset.bounds ?? null,
    format,
    // Every level carries the glyph's pick priority, not just its root: the ray
    // hits the cone or arrow child, never the group.
    pickPriority: object.userData?.pickPriority ?? 0,
    objectId: asset.object_ids?.[0] ?? null,
    objectIds: [...(asset.object_ids ?? [])],
    primaryObjectId: asset.object_ids?.[0] ?? null
  };
  // Every level, not just direct children: a moment glyph's axis line sits two
  // levels down (Group > ArrowHelper > Line) and was unpickable.
  object.traverse((part) => {
    part.userData = { ...part.userData, ...metadata };
  });
}

function isAssetVisible(asset, visibleIds) {
  const ids = asset.object_ids ?? [];
  return ids.length === 0 || ids.some((id) => visibleIds.has(id));
}

function assetMatchesActiveGeometryState(asset, payload, activeGeometryStateId) {
  const geometryStateId = {
    ...(payload?.generation_config ?? {}),
    ...(asset?.generation_config ?? {})
  }.geometry_state_id ?? null;
  return geometryStateId === null || geometryStateId === activeGeometryStateId;
}

// Which design solids are drawn as reference geometry. An exaggerated shape
// moves away from every member, so it turns all of them into reference. A warped
// solid at the solved scale sits on top of the one design solid it came from -
// both opaque, both coloured, fighting for the same pixels in stripes - so it
// turns that one into reference and no other: a header whose only warped solid
// is its tee must not grey out every pipe and frame member around it. A deformed
// centreline turns nothing into reference: it is a line inside the pipe, and
// ghosting the pipe for it would leave nothing coloured to read.
function visibleDeformedReference(state, payloadsByAssetId = new Map(), visibleIds = new Set(state.visibleObjectIds ?? [])) {
  const objectsById = new Map((state.objects ?? []).map((object) => [object.id, object]));
  let visual = false;
  const bodyKeys = new Set();
  for (const asset of state.geometryAssets ?? []) {
    if (!isAssetVisible(asset, visibleIds)) continue;
    const payload = payloadsByAssetId.get(asset.id) ?? {};
    if (!assetMatchesActiveGeometryState(asset, payload, state.activeGeometryStateId)) continue;
    const config = { ...(payload.generation_config ?? {}), ...(asset.generation_config ?? {}) };
    if (isVisualDeformedConfig(asset, config)) {
      visual = true;
    } else if (isPhysicalDeformedBodyConfig(asset, config)) {
      for (const id of asset.object_ids ?? []) bodyKeys.add(selectionKey(objectsById.get(id) ?? { id }));
    }
  }
  return { visual, bodyKeys, objectsById };
}

function isPhysicalDeformedBodyConfig(asset, config) {
  const format = String(asset.format ?? "").toLowerCase();
  return String(config.source ?? "").toLowerCase().includes("deformed") && format !== "polyline";
}

function isUndeformedReferenceConfig(asset, config, state) {
  if (String(config.source ?? "").toLowerCase() !== "tuba.element") return false;
  const { visual, bodyKeys, objectsById } = state.deformedReference ?? visibleDeformedReference(state);
  if (visual) return true;
  return (asset.object_ids ?? []).some((id) => bodyKeys.has(selectionKey(objectsById.get(id) ?? { id })));
}

export function prepareAssetRenderConfig(asset, payload = {}, state = {}) {
  const config = {
    ...(payload.generation_config ?? {}),
    ...(asset.generation_config ?? {})
  };
  if (isInspectionDiagnosticSource(config.source)) return config;
  if (String(asset.format ?? "").toLowerCase() !== "tuyau_subpoint_glyphs") {
    const scalarValueIds = [config.node_id, ...(config.node_ids ?? []), config.element_id && `object:element:${config.element_id}`].filter(Boolean).map(String);
    const scalarColor = getObjectScalarColor(state, asset.object_ids ?? [], scalarValueIds);
    const bodyState = scalarColor === null ? fieldBodyState(state, asset.object_ids ?? [], scalarValueIds) : null;
    if (scalarColor !== null) {
      config.color = scalarColor;
    } else if (bodyState) {
      config.color = REFERENCE_GEOMETRY_COLOR;
      config.opacity = REFERENCE_GEOMETRY_OPACITY;
      config.transparent = true;
      config.reference_geometry = true;
      config.no_result = bodyState === "no_result";
    } else if (!(GMSH_COLORED_SOURCES.has(config.source) && (state.modelColorBy ?? "default") === "default")) {
      // The default member tint (grey beams, route-coloured pipes) would paint
      // over the mesh's own per-entity colours; a chosen colour-by still applies.
      const modelColor = getModelObjectColor(state, asset.object_ids ?? []);
      if (modelColor !== null) {
        config.color = parseColor(modelColor) ?? modelColor;
      }
    }
  }
  if (isUndeformedReferenceConfig(asset, config, state)) {
    config.color = REFERENCE_GEOMETRY_COLOR;
    config.opacity = REFERENCE_GEOMETRY_OPACITY;
    config.transparent = true;
    config.reference_geometry = true;
    // The undeformed shape of a body whose solved shape is drawn: a reference,
    // not a member missing its result.
    config.no_result = false;
  }
  // Per-body opacity is a ceiling, not a multiplier: dimming Geometry must not
  // compound with the ghosting an undeformed reference already carries and
  // drive it to invisible.
  const bodyLimit = bodyOpacityForObjectIds(state, asset.object_ids ?? []);
  if (bodyLimit !== null && bodyLimit < 1) {
    const declared = Number(config.opacity);
    config.opacity = Number.isFinite(declared) ? Math.min(declared, bodyLimit) : bodyLimit;
    config.transparent = true;
  }
  if ((state.supportReactionPresentation || state.searchIterationPresentation) && sceneStage(state) !== 'build' && String(config.source).includes('obstacle')) {
    config.opacity = 0.12; config.transparent = true;
  }
  if (String(asset.format ?? "").toLowerCase() === "vector") {
    return scaleVectorConfig(asset, readableReactionConfig(config, state), state);
  }
  if (String(asset.format ?? "").toLowerCase() === "tuyau_subpoint_glyphs") {
    return subpointDisplayConfig(asset, config, state);
  }
  return scaleVisualDeformationConfig(asset, config, state);
}

function readableReactionConfig(config, state) {
  const kind = config.result_type;
  if (!state.supportReactionPresentation || sceneStage(state) === 'build' || !['reaction_force', 'reaction_moment'].includes(kind) ||
      config.load_case !== state.activeLoadCase || config.result_state_id !== state.activeResultStateId) return config;
  const vector = kind === 'reaction_force' ? config.reaction_force_n : config.reaction_moment_nm;
  if (!Array.isArray(vector) || vector.length !== 3 || !vector.every(Number.isFinite) || !numericPoint(config.start)) return config;
  const values = (state.overlays ?? []).find(o => o.data?.result_type === kind && o.data.load_case === state.activeLoadCase &&
    o.data.result_state_id === state.activeResultStateId)?.data.values ?? {};
  const magnitudes = Object.values(values).filter(v => Array.isArray(v) && v.length === 3 && v.every(Number.isFinite)).map(v => Math.hypot(...v));
  const magnitude = Math.hypot(...vector), maximum = Math.max(magnitude, ...magnitudes);
  const b = state.bounds;
  const span = Array.isArray(b) && b.length === 6 ? Math.max(1, ...[0, 1, 2].map(i => b[i + 3] - b[i])) : 8;
  // Independent display scales for forces and moments. Minimum visible size
  // is a presentation aid; all labels continue to report the native values.
  const length = span * Math.max(0.08, maximum > 0 ? 0.16 * magnitude / maximum : 0);
  return { ...config, reaction_display: true, display_zero: magnitude < 0.005,
    reference_geometry: false, no_result: false, opacity: 1, transparent: false,
    color: kind === 'reaction_force' ? '#2563eb' : '#f97316',
    end: config.start.map((value, i) => value + (magnitude > 0 ? vector[i] / magnitude * length : 0)) };
}

// How much of the sub-point field reaches the screen, decided from the viewer's
// display mode rather than baked into the bundle: the scene carries every
// measured point, and which of them is a drawing choice. `xray` matters because
// the pipe the points sit in is opaque and hides every wall layer but the outer
// one - so in the mode meant to surface the worst stations, depth testing is
// what would throw them away.
function subpointDisplayConfig(asset, config, state) {
  const xray = subpointModeSpec(state).xray;
  const legend = subpointLegend(config, Array.isArray(config.values) ? config.values.map(Number) : [], state);
  return {
    ...config,
    xray,
    value_threshold: xray ? subpointThresholdValue(subpointThreshold(state), legend?.range?.max) : null
  };
}

function materialForAsset(asset, config, options = {}) {
  const opacity = opacityForConfig(config, options.transparent ? 0.48 : 1);
  const transparent = opacity < 1;
  const material = new THREE.MeshStandardMaterial({
    color: colorForAsset(asset, config),
    depthWrite: !transparent,
    metalness: 0.05,
    opacity,
    roughness: 0.68,
    transparent,
    // Reference geometry yields the depth test to anything coincident with it,
    // so where the deformed body has barely moved the coloured surface wins
    // cleanly and the grey shows only where the shape has moved away.
    ...(config.reference_geometry ? { polygonOffset: true, polygonOffsetFactor: 2, polygonOffsetUnits: 4 } : {})
  });
  if (config.no_result) hatchNoResult(material);
  return material;
}

// Diagonal stripes in screen space over a body the active field has no value
// for. Every colour the scale can produce is a flat shade, so a pattern cannot
// be read as one - the scale's grey middle and a grey "nothing here" could.
// Screen space needs no UVs, so tubes, profiles and imported meshes all get it.
const NO_RESULT_HATCH = Object.freeze({ period: 9, width: 2, color: [0.39, 0.45, 0.55], alpha: 0.7 });

function hatchNoResult(material) {
  const { period, width, color, alpha } = NO_RESULT_HATCH;
  material.userData.noResultHatch = true;
  material.onBeforeCompile = (shader) => {
    shader.fragmentShader = shader.fragmentShader.replace(
      "#include <dithering_fragment>",
      `#include <dithering_fragment>
      float tubaHatch = step(mod(gl_FragCoord.x - gl_FragCoord.y, ${period.toFixed(1)}), ${width.toFixed(1)});
      gl_FragColor = mix(gl_FragColor, vec4(${color.map((c) => c.toFixed(2)).join(", ")}, ${alpha.toFixed(2)}), tubaHatch);`
    );
  };
  material.customProgramCacheKey = () => "tuba-no-result-hatch";
}

// A point sprite drawn as a lit ball: square sprites read as noise in a dense cloud.
const SIZING_SAMPLE_PX = 9;
const FE_NODE_PX = 4;

// Round point sprites; lit ones read as balls, unlit ones are Gmsh's flat dots.
function shadeAsBall(material, lit = true) {
  material.onBeforeCompile = (shader) => {
    shader.fragmentShader = shader.fragmentShader.replace(
      "outgoingLight = diffuseColor.rgb;",
      `vec2 tubaBall = gl_PointCoord * 2.0 - 1.0;
      float tubaR2 = dot(tubaBall, tubaBall);
      if (tubaR2 > 1.0) discard;
      outgoingLight = diffuseColor.rgb;` + (lit ? `
      vec3 tubaNormal = vec3(tubaBall.x, -tubaBall.y, sqrt(1.0 - tubaR2));
      float tubaLight = 0.5 + 0.5 * max(dot(tubaNormal, normalize(vec3(-0.4, 0.5, 0.8))), 0.0);
      outgoingLight *= tubaLight * mix(1.0, 0.7, smoothstep(0.75, 1.0, tubaR2));` : "")
    );
  };
  material.customProgramCacheKey = () => lit ? "tuba-point-ball" : "tuba-point-dot";
}

// Gmsh's Mesh.ColorCarousel=1: every geometric entity (here a member or a
// model node) gets one of Mesh.Color.Zero..Nineteen, its elements and nodes alike.
const GMSH_CAROUSEL = [0xff7800, 0x00ff84, 0xffa000, 0x00ffc0, 0xffc800, 0x00d8ff, 0xfff000, 0x00b0ff, 0xe4ff00, 0x0074ff,
  0xbcff00, 0x004cff, 0x94ff00, 0x1800ff, 0x6cff00, 0x5400ff, 0x44ff00, 0x6800ff, 0x00ff34, 0xb800ff];

const GMSH_COLORED_SOURCES = new Set(["tuba.analysis_mesh.node", "tuba.analysis_mesh.element"]);

function carouselColor(sourceRef) {
  let hash = 0;
  for (const char of sourceRef) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return GMSH_CAROUSEL[hash % GMSH_CAROUSEL.length];
}

function colorForAsset(asset, config) {
  const explicitColor = parseColor(config.color);
  if (explicitColor !== null) {
    return explicitColor;
  }
  const markerish = config.issue_id || config.clash || asset.id?.includes(":clash:");
  if (markerish) {
    return 0xdc2626;
  }
  const source = String(config.source ?? "");
  if (source === "tuba.support") {
    return 0xf59e0b;
  }
  if (asset.format === "vector") {
    // Off the cividis ramp on purpose. An arrow is not a value: amber sat in
    // the ramp's warm end, so a glyph read as "high", and it collided with both
    // the support colour and the selection highlight.
    return 0xc026d3;
  }
  if (GMSH_COLORED_SOURCES.has(source) && config.source_ref) {
    return carouselColor(String(config.source_ref));
  }
  if (source.includes("analysis_mesh")) {
    return 0x059669;
  }
  if (source.includes("deformed")) {
    return 0x7c3aed;
  }
  if (source.includes("obstacle") || asset.id?.includes(":obstacle:")) {
    return 0x64748b;
  }
  if (asset.format === "aabb" || asset.format === "cuboid") {
    return 0x94a3b8;
  }
  if (asset.format === "line_load_comb") {
    return 0x0284c7;
  }
  return 0x2563eb;
}

function subpointLegend(config, values, state, asset = null) {
  const stateLegend = getScalarLegend(state);
  const fallbackRange = config.range ?? config.legend?.range ?? rangeForValues(values);
  // The field colouring the scene owns this surface: read it on that field's
  // legend - the one on screen, with any range the reviewer typed - not on the
  // surface's private copy, or a solid and the pipes beside it sit on two scales.
  const owned = (asset?.object_ids ?? []).some((id) => stateLegend?.overlay?.object_ids?.includes(id));
  if (stateLegend?.overlay?.data?.result_type === "tuyau_subpoints" || owned) {
    return stateLegend;
  }
  return {
    field: config.legend?.field ?? "VMIS",
    unit: config.legend?.unit ?? "Pa",
    range: fallbackRange,
    colorMap: config.legend?.color_map ?? "cividis",
    thresholds: config.legend?.thresholds ?? {}
  };
}

function colorForSubpointValue(value, legend, asset, config) {
  // A station the solver returned no value for is not a cold one. It falls back
  // to the asset's own colour instead of the bottom of the ramp, so an
  // unconverged run reads as "no number here" rather than as zero stress.
  if (!hasSubpointValue(value)) {
    return colorForAsset(asset, config);
  }
  const scalarColor = colorForScalarValue(Number(value), legend);
  return scalarColor ?? colorForAsset(asset, config);
}

function rangeForValues(values) {
  let min = Infinity, max = -Infinity;
  for (const value of values) {
    if (!Number.isFinite(value)) continue;
    min = Math.min(min, value);
    max = Math.max(max, value);
  }
  return min === Infinity ? { min: 0, max: 1 } : { min, max };
}

function scaleVectorConfig(asset, config, state) {
  const start = numericPoint(config.start);
  const end = numericPoint(config.end);
  if (!start || !end) {
    return config;
  }
  const vectorType = vectorTypeForConfig(asset, config);
  const scale = getResultVectorScale(state, vectorType);
  if (scale === 1) {
    return config;
  }
  return {
    ...config,
    end: start.map((value, index) => value + (end[index] - value) * scale)
  };
}

export function scaledSectionPoints(config, scale) {
  const base = config.base_vertices ?? config.base_points;
  const count = base.length / config.section_origins.length;
  return base.map((point, index) => {
    const station = Math.floor(index / count);
    const origin = new THREE.Vector3(...config.section_origins[station]);
    const dof = config.section_deformations[station];
    const rotation = new THREE.Vector3(...dof.slice(3)).multiplyScalar(scale);
    const angle = rotation.length();
    const offset = new THREE.Vector3(...point).sub(origin);
    if (angle > 1e-15) offset.applyAxisAngle(rotation.divideScalar(angle), angle);
    return offset.add(origin).add(new THREE.Vector3(...dof.slice(0, 3)).multiplyScalar(scale)).toArray();
  });
}

function scaleVisualDeformationConfig(asset, config, state) {
  if (!isVisualDeformedConfig(asset, config)) {
    return config;
  }
  const points = numericPoints(config.points);
  if (points.length < 2) {
    return config;
  }
  const sourceScale = positiveNumber(config.visual_scale ?? config.deformation_scale ?? config.displacement_scale);
  const displayScale = getVisualDeformationDisplayScale(state);
  if (!sourceScale || Math.abs(displayScale - sourceScale) <= 1e-12) {
    return { ...config, visual_scale_display_only: displayScale };
  }
  const basePoints = numericPoints(config.base_points ?? config.cold_points);
  if (basePoints.length !== points.length) {
    return { ...config, visual_scale_display_only: sourceScale };
  }
  const scaled = points.map((point, index) => {
    const base = basePoints[index];
    return point.map((value, axis) => base[axis] + (value - base[axis]) * (displayScale / sourceScale));
  });
  return {
    ...config,
    points: scaled,
    visual_scale_display_only: displayScale
  };
}

function vectorTypeForConfig(asset, config) {
  const source = `${asset.id ?? ""} ${config.source ?? ""} ${config.result_type ?? ""} ${config.resultType ?? ""}`.toLowerCase();
  // Moments scale against other moments, never against forces: they are a
  // different physical quantity, and sharing one slider meant a model whose
  // moments are numerically large drew arcs that swallowed the geometry.
  if (config.vector_kind === "moment" || source.includes("moment")) {
    return "moment";
  }
  if (source.includes("reaction") || source.includes("forc_noda")) {
    return "reaction";
  }
  if (source.includes("displacement") || source.includes("depl")) {
    return "displacement";
  }
  return "vector";
}

function isVisualDeformedConfig(asset, config) {
  const layerIds = asset.layer_ids ?? config.layer_ids ?? [];
  const source = `${asset.id ?? ""} ${config.source ?? ""} ${config.purpose ?? ""} ${config.geometry_state_id ?? ""}`.toLowerCase();
  return (
    layerIds.some((layerId) => String(layerId).includes("deformed:visual")) ||
    source.includes("visual") ||
    (source.includes("deformed") && positiveNumber(config.visual_scale ?? config.deformation_scale ?? config.displacement_scale) > 1)
  );
}

function numericPoints(points) {
  return Array.isArray(points) ? points.map(numericPoint).filter(Boolean) : [];
}

function numericPoint(point) {
  if (!Array.isArray(point) || point.length < 3) {
    return null;
  }
  const values = point.slice(0, 3).map(Number);
  return values.every(Number.isFinite) ? values : null;
}

function opacityForConfig(config, fallback) {
  const value = Number(config.opacity);
  if (!Number.isFinite(value)) {
    return fallback;
  }
  return Math.max(0, Math.min(1, value));
}

function parseColor(value) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value !== "string") {
    return null;
  }
  const normalized = value.trim().replace(/^#/, "");
  if (!/^[0-9a-f]{6}$/i.test(normalized)) {
    return null;
  }
  return Number.parseInt(normalized, 16);
}

function darkenColor(color) {
  const value = new THREE.Color(color);
  value.multiplyScalar(0.65);
  return value;
}

function readPoints(points) {
  if (!Array.isArray(points)) {
    return [];
  }
  return points.map(readPoint).filter(Boolean);
}

function readPoint(point) {
  if (!Array.isArray(point) || point.length < 3) {
    return null;
  }
  const values = point.slice(0, 3).map(Number);
  if (!values.every(Number.isFinite)) {
    return null;
  }
  return new THREE.Vector3(values[0], values[1], values[2]);
}

function normalizeBounds(bounds) {
  if (!Array.isArray(bounds) || bounds.length !== 6) {
    return null;
  }
  const values = bounds.map(Number);
  if (!values.every(Number.isFinite)) {
    return null;
  }
  return [
    Math.min(values[0], values[3]),
    Math.min(values[1], values[4]),
    Math.min(values[2], values[5]),
    Math.max(values[0], values[3]),
    Math.max(values[1], values[4]),
    Math.max(values[2], values[5])
  ];
}

function mergeAssetBounds(assets) {
  const bounds = assets.map((asset) => normalizeBounds(asset.bounds)).filter(Boolean);
  if (bounds.length === 0) {
    return [-1, -1, -1, 1, 1, 1];
  }
  return bounds.reduce(
    (merged, current) => [
      Math.min(merged[0], current[0]),
      Math.min(merged[1], current[1]),
      Math.min(merged[2], current[2]),
      Math.max(merged[3], current[3]),
      Math.max(merged[4], current[4]),
      Math.max(merged[5], current[5])
    ],
    bounds[0]
  );
}

function centerOfBounds(bounds) {
  const normalized = normalizeBounds(bounds);
  if (!normalized) {
    return null;
  }
  return new THREE.Vector3(
    (normalized[0] + normalized[3]) / 2,
    (normalized[1] + normalized[4]) / 2,
    (normalized[2] + normalized[5]) / 2
  );
}

function sizeOfBounds(bounds) {
  const normalized = normalizeBounds(bounds) ?? [-1, -1, -1, 1, 1, 1];
  return new THREE.Vector3(
    Math.max(normalized[3] - normalized[0], 1e-6),
    Math.max(normalized[4] - normalized[1], 1e-6),
    Math.max(normalized[5] - normalized[2], 1e-6)
  );
}

function radiusFromBounds(bounds, fallback) {
  const size = sizeOfBounds(bounds);
  const radius = Math.min(size.x, size.y, size.z) / 2;
  return radius > 1e-6 ? radius : fallback;
}

function positiveNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) && number > 0 ? number : null;
}

function createEngineeringCamera(aspect) {
  const safeAspect = positiveNumber(aspect) ?? 1;
  const camera = new THREE.OrthographicCamera(-safeAspect, safeAspect, 1, -1, 0.01, 10000);
  camera.up.set(0, 0, 1);
  camera.userData.viewportAspect = safeAspect;
  return camera;
}

function invalidAsset(asset, message) {
  return {
    diagnostic: {
      assetId: asset.id,
      code: "renderer.invalid_asset",
      message,
      severity: "error"
    },
    format: asset.format,
    object: null
  };
}

function addContactMarkers(root, state) {
  // Contact marks are solver output, so they answer to the result layers the
  // Build preset drops. Their supporting object is design (a visible shoe), so
  // without this gate a Build view kept drawing solved contact arrows over a
  // scene whose result layers were all off.
  const resultOverlayId = getActiveResultState(state)?.overlay?.id;
  if (resultOverlayId && Array.isArray(state.visibleOverlayIds) && !state.visibleOverlayIds.includes(resultOverlayId)) {
    return;
  }
  const maxima = contactForceMaxima(state);
  const span = sizeOfBounds(state.bounds);
  const size = Math.max(span.x, span.y, span.z, 1) * 0.025;
  for (const contact of Object.values(contactRecords(state))) {
    const objectId = contactObjectId(state, contact.support_id);
    if (!(state.visibleObjectIds ?? []).includes(objectId)) continue;
    const object = (state.objects ?? []).find((o) => o.id === objectId);
    const asset = (state.geometryAssets ?? []).find((a) => a.id === object?.geometry_asset_id);
    if (!asset) continue;
    const payload = (state.geometryPayloads ?? []).find((p) => p.asset_id === asset.id);
    const config = { ...asset.generation_config, ...payload?.generation_config };
    const location = readPoint(config.point ?? config.location) ?? centerOfBounds(asset.bounds);
    if (!location) continue;
    const group = new THREE.Group(); group.position.copy(location);
    group.userData = { objectIds: [objectId], format: "vector", contactStatus: contact.status, pickPriority: PICK_PRIORITY_ANNOTATION };
    const color = contact.utilization > 1.001 ? 0xdc2626 : CONTACT_COLORS[contact.status] ?? CONTACT_COLORS.indeterminate;
    const material = new THREE.MeshBasicMaterial({ color, depthTest: false });
    // Sticking is the resting state, and the shoe already says so twice: its pad
    // is painted blue and the mu badge carries the filled-square symbol. A cube
    // for the norm was the largest mark on the model. Only the states that need
    // saying - lift-off, slide, an indeterminate solve - get a glyph.
    let marker = null;
    if (contact.status === "open") marker = new THREE.Mesh(new THREE.TorusGeometry(size * 0.45, size * 0.08, 8, 24), material);
    else if (contact.status === "sliding") marker = new THREE.ArrowHelper(new THREE.Vector3(...contact.tangential_force).normalize(), new THREE.Vector3(), size, color, size * 0.5, size * 0.35);
    else if (contact.status !== "sticking") {
      marker = new THREE.Group();
      marker.add(new THREE.Mesh(new THREE.TorusGeometry(size * 0.3, size * 0.07, 8, 16, Math.PI * 1.5), material));
      const point = new THREE.Mesh(new THREE.SphereGeometry(size * 0.08, 8, 8), material); point.position.y = -size * 0.45; marker.add(point);
    }
    if (marker) group.add(marker);
    for (const [quantity, vector, color] of [["normal", contact.normal.map((v) => v * contact.normal_force), 0x2563eb], ["tangential", contact.tangential_force, 0x0f766e]]) {
      const direction = new THREE.Vector3(...vector); const force = direction.length();
      if (state.contactArrows?.[quantity] === false || !(force > 0) || !(maxima[quantity] > 0)) continue;
      const arrow = new THREE.ArrowHelper(direction.normalize(), new THREE.Vector3(), size * 8 * force / maxima[quantity], color);
      arrow.userData.contactForce = quantity; group.add(arrow);
    }
    group.traverse((child) => { child.userData.objectIds = [objectId]; child.userData.primaryObjectId = objectId; child.userData.pickPriority = PICK_PRIORITY_ANNOTATION; child.renderOrder = 30; });
    root.add(group);
  }
}
