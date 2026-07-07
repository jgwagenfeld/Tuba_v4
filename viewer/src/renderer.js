import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import {
  colorForScalarValue,
  getObjectScalarColor,
  getResultVectorScale,
  getScalarLegend,
  getVisualDeformationDisplayScale
} from "./resultReview.js";

export const SUPPORTED_RENDER_FORMATS = new Set([
  "aabb",
  "cuboid",
  "line",
  "marker",
  "mesh",
  "point",
  "polyline",
  "tube",
  "tube_envelope",
  "tuyau_subpoint_glyphs",
  "vector"
]);

export function createThreeSceneGraph(state, options = {}) {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(options.backgroundColor ?? 0xf8fafc);

  const root = new THREE.Group();
  root.name = "TubaSceneRoot";
  scene.add(root);

  const bounds = normalizeBounds(state.bounds) ?? mergeAssetBounds(state.geometryAssets ?? []);
  addReferenceHelpers(scene, bounds);

  const payloadsByAssetId = new Map((state.geometryPayloads ?? []).map((payload) => [payload.asset_id, payload]));
  const visibleIds = new Set(state.visibleObjectIds ?? []);
  const objectsByObjectId = new Map();
  const diagnostics = [];
  let renderedObjectCount = 0;

  for (const asset of state.geometryAssets ?? []) {
    if (!isAssetVisible(asset, visibleIds)) {
      continue;
    }
    const payload = payloadsByAssetId.get(asset.id) ?? {};
    const result = createRenderableForAsset(asset, payload, state);
    if (result.diagnostic) {
      diagnostics.push(result.diagnostic);
    }
    if (!result.object) {
      continue;
    }
    setRenderMetadata(result.object, asset, result.format);
    root.add(result.object);
    renderedObjectCount += 1;
    for (const objectId of asset.object_ids ?? []) {
      objectsByObjectId.set(objectId, result.object);
    }
  }

  return {
    bounds,
    diagnostics,
    objectsByObjectId,
    renderableObjects: [...root.children],
    renderedObjectCount,
    root,
    scene
  };
}

export function buildRenderableScene(state, options = {}) {
  const graph = createThreeSceneGraph(state, options);
  const camera = new THREE.PerspectiveCamera(45, (options.width ?? 1280) / Math.max(options.height ?? 800, 1), 0.01, 10000);
  camera.up.set(0, 0, 1);
  const fit = fitCameraToBounds(camera, graph.bounds);
  return {
    ...graph,
    camera,
    controlsTarget: new THREE.Vector3(...fit.target)
  };
}

export function createThreeCanvasRenderer(canvas, options = {}) {
  const renderer = new THREE.WebGLRenderer({
    antialias: true,
    canvas,
    preserveDrawingBuffer: true
  });
  renderer.setClearColor(options.backgroundColor ?? 0xf8fafc, 1);
  renderer.setPixelRatio(Math.min(globalThis.devicePixelRatio ?? 1, 2));

  const camera = new THREE.PerspectiveCamera(45, 1, 0.01, 10000);
  camera.up.set(0, 0, 1);

  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  let currentGraph = null;

  return {
    render(state) {
      const width = Math.max(1, Math.floor(canvas.clientWidth || canvas.width || 1));
      const height = Math.max(1, Math.floor(canvas.clientHeight || canvas.height || 1));
      renderer.setSize(width, height, false);
      camera.aspect = width / height;

      const graph = createThreeSceneGraph(state, options);
      fitCameraToBounds(camera, graph.bounds, controls);
      controls.update();
      graph.camera = camera;
      applySelectionHighlight(graph, state.selectedObjectIds ?? []);
      renderer.render(graph.scene, camera);
      currentGraph = graph;

      canvas.dataset.renderer = "three";
      canvas.dataset.renderedObjects = String(graph.renderedObjectCount);
      canvas.dataset.renderDiagnostics = String(graph.diagnostics.length);
      return graph;
    },
    redraw() {
      if (!currentGraph) {
        return;
      }
      controls.update();
      renderer.render(currentGraph.scene, camera);
    },
    dispose() {
      controls.dispose();
      renderer.dispose();
    }
  };
}

export function createThreeViewport(canvas, options = {}) {
  const canvasRenderer = createThreeCanvasRenderer(canvas, options);
  return {
    setState(state) {
      const graph = canvasRenderer.render(state);
      return {
        ...graph,
        renderableObjects: [...new Set(graph.objectsByObjectId.values())]
      };
    },
    render() {
      canvasRenderer.redraw();
    },
    dispose() {
      canvasRenderer.dispose();
    }
  };
}

export function pickRenderedObject(graph, point, viewport) {
  if (!graph?.camera || !graph.renderableObjects?.length) {
    return null;
  }
  const raycaster = new THREE.Raycaster();
  const normalized = new THREE.Vector2((point.x / viewport.width) * 2 - 1, -(point.y / viewport.height) * 2 + 1);
  graph.camera.updateProjectionMatrix();
  graph.camera.updateMatrixWorld();
  graph.scene?.updateMatrixWorld(true);
  raycaster.setFromCamera(normalized, graph.camera);
  const intersections = raycaster.intersectObjects(graph.renderableObjects, true);
  for (const intersection of intersections) {
    const objectId = intersection.object.userData?.primaryObjectId || intersection.object.userData?.objectId;
    if (objectId) {
      return objectId;
    }
  }
  return pickNearestProjectedObject(graph, point, viewport);
}

export function applyHoverHighlight(graph, objectId) {
  graph.highlightedObjectId = objectId ?? null;
  for (const object of graph.renderableObjects ?? []) {
    const hovered = Boolean(objectId && (object.userData.objectIds ?? []).includes(objectId));
    object.userData.hovered = hovered;
    object.traverse((child) => {
      child.userData.hovered = hovered;
      const materials = Array.isArray(child.material) ? child.material : child.material ? [child.material] : [];
      for (const material of materials) {
        if (material.emissive) {
          material.emissive.setHex(hovered ? 0x1d4ed8 : 0x000000);
        }
      }
    });
  }
  return graph;
}

export function applySelectionHighlight(graph, objectIds = []) {
  const selectedIds = new Set(objectIds);
  graph.selectedObjectIds = [...selectedIds];
  for (const object of graph.renderableObjects ?? []) {
    const selected = (object.userData.objectIds ?? []).some((objectId) => selectedIds.has(objectId));
    object.userData.selected = selected;
    object.traverse((child) => {
      child.userData.selected = selected;
      const materials = Array.isArray(child.material) ? child.material : child.material ? [child.material] : [];
      for (const material of materials) {
        if (material.emissive) {
          material.emissive.setHex(selected ? 0xf59e0b : 0x000000);
        }
      }
    });
  }
  return graph;
}

export function fitCameraToBounds(camera, bounds, controls = null) {
  const normalized = normalizeBounds(bounds) ?? [-1, -1, -1, 1, 1, 1];
  const center = centerOfBounds(normalized);
  const size = sizeOfBounds(normalized);
  const radius = Math.max(size.length() * 0.5, 0.5);
  const fov = THREE.MathUtils.degToRad(camera.fov || 45);
  const distance = Math.max(radius / Math.sin(fov / 2), radius * 2.5);
  const direction = new THREE.Vector3(1, -1, 0.65).normalize();

  camera.near = Math.max(distance / 1000, 0.001);
  camera.far = distance * 1000;
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

function createRenderableForAsset(asset, payload, state) {
  const format = String(asset.format ?? "").toLowerCase();
  if (!SUPPORTED_RENDER_FORMATS.has(format)) {
    return invalidAsset(asset, `Unsupported geometry format '${asset.format}'.`);
  }

  const config = prepareAssetRenderConfig(asset, payload, state);
  try {
    if (format === "tube" || format === "tube_envelope") {
      return createTube(asset, config, format);
    }
    if (format === "polyline" || format === "line") {
      return createPolyline(asset, config, format);
    }
    if (format === "point" || format === "marker") {
      return createPoint(asset, config, format);
    }
    if (format === "tuyau_subpoint_glyphs") {
      return createTuyauSubpointGlyphs(asset, config, format, state);
    }
    if (format === "vector") {
      return createVector(asset, config, format, state);
    }
    if (format === "cuboid" || format === "aabb") {
      return createBox(asset, config, format);
    }
    if (format === "mesh") {
      return createMesh(asset, config, payload, format);
    }
  } catch (error) {
    return invalidAsset(asset, error.message);
  }
  return invalidAsset(asset, `No renderer for geometry format '${asset.format}'.`);
}

function createTube(asset, config, format) {
  const points = readPoints(config.points);
  if (points.length < 2) {
    return invalidAsset(asset, "Tube assets require at least two points.");
  }
  const radius = positiveNumber(config.radius_m) ?? radiusFromBounds(asset.bounds, 0.035);
  const curve = new THREE.CatmullRomCurve3(points);
  const geometry = new THREE.TubeGeometry(curve, Math.max(8, points.length * 12), radius, 14, false);
  const mesh = new THREE.Mesh(geometry, materialForAsset(asset, config, { transparent: format === "tube_envelope" }));
  mesh.name = asset.id;
  return { format, object: mesh };
}

function createPolyline(asset, config, format) {
  const points = readPoints(config.points);
  if (points.length < 2) {
    return invalidAsset(asset, "Polyline assets require at least two points.");
  }
  const geometry = new THREE.BufferGeometry().setFromPoints(points);
  const line = new THREE.Line(geometry, new THREE.LineBasicMaterial({ color: colorForAsset(asset, config), linewidth: 2 }));
  line.name = asset.id;
  return { format, object: line };
}

function createPoint(asset, config, format) {
  const point = readPoint(config.point ?? config.location ?? config.clash?.location) ?? centerOfBounds(asset.bounds);
  if (!point) {
    return invalidAsset(asset, "Point assets require a point or valid bounds.");
  }
  const radius = positiveNumber(config.radius_m) ?? radiusFromBounds(asset.bounds, format === "marker" ? 0.06 : 0.035);
  const geometry = new THREE.SphereGeometry(radius, 16, 12);
  geometry.computeBoundingSphere();
  const mesh = new THREE.Mesh(geometry, materialForAsset(asset, config));
  mesh.position.copy(point);
  mesh.name = asset.id;
  return { format, object: mesh };
}

function createTuyauSubpointGlyphs(asset, config, format, state) {
  const starts = readPoints(config.starts ?? config.start_points);
  const ends = readPoints(config.ends ?? config.end_points);
  const count = Math.min(starts.length, ends.length);
  if (count < 1) {
    return invalidAsset(asset, "TUYAU sub-point glyph assets require start and end point arrays.");
  }
  const radius = positiveNumber(config.radius_m) ?? 0.006;
  const radialSegments = Math.max(4, Math.min(16, Math.floor(Number(config.radial_segments) || 8)));
  const geometry = new THREE.CylinderGeometry(radius, radius, 1, radialSegments, 1, false);
  const material = new THREE.MeshBasicMaterial({
    color: 0xffffff,
    opacity: 0.94,
    transparent: true,
    vertexColors: true
  });
  const mesh = new THREE.InstancedMesh(geometry, material, count);
  const matrix = new THREE.Matrix4();
  const midpoint = new THREE.Vector3();
  const direction = new THREE.Vector3();
  const scale = new THREE.Vector3(1, 1, 1);
  const quaternion = new THREE.Quaternion();
  const yAxis = new THREE.Vector3(0, 1, 0);
  const values = Array.isArray(config.values) ? config.values.map(Number) : [];
  const legend = subpointLegend(config, values, state);
  let written = 0;

  for (let index = 0; index < count; index += 1) {
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
  mesh.instanceMatrix.needsUpdate = true;
  if (mesh.instanceColor) {
    mesh.instanceColor.needsUpdate = true;
  }
  mesh.name = asset.id;
  return { format, object: mesh };
}

function createVector(asset, config, format, state) {
  const start = readPoint(config.start);
  let end = readPoint(config.end);
  if (!start || !end) {
    return invalidAsset(asset, "Vector assets require start and end points.");
  }
  const direction = end.clone().sub(start);
  const length = direction.length();
  if (length <= 1e-12) {
    return invalidAsset(asset, "Vector assets require non-zero length.");
  }
  const arrow = new THREE.ArrowHelper(
    direction.normalize(),
    start,
    length,
    colorForAsset(asset, config),
    Math.min(length * 0.25, 0.18),
    Math.min(length * 0.12, 0.08)
  );
  arrow.name = asset.id;
  return { format, object: arrow };
}

function createBox(asset, config, format) {
  const bounds = normalizeBounds(config.bounds ?? config.obstacle?.bounds ?? asset.bounds);
  if (!bounds) {
    return invalidAsset(asset, "Box assets require valid bounds.");
  }
  const size = sizeOfBounds(bounds);
  const geometry = new THREE.BoxGeometry(Math.max(size.x, 1e-6), Math.max(size.y, 1e-6), Math.max(size.z, 1e-6));
  const mesh = new THREE.Mesh(geometry, materialForAsset(asset, config, { transparent: true }));
  mesh.position.copy(centerOfBounds(bounds));
  mesh.name = asset.id;

  const edges = new THREE.LineSegments(
    new THREE.EdgesGeometry(geometry),
    new THREE.LineBasicMaterial({ color: darkenColor(colorForAsset(asset, config)) })
  );
  mesh.add(edges);
  return { format, object: mesh };
}

function createMesh(asset, config, payload, format) {
  const vertices = config.vertices ?? payload.vertices ?? config.mesh?.vertices;
  const faces = config.triangles ?? config.faces ?? config.indices ?? payload.faces ?? payload.indices ?? config.mesh?.faces;
  if (!Array.isArray(vertices) || vertices.length < 3) {
    return invalidAsset(asset, "Mesh assets require vertices.");
  }
  const flatVertices = vertices.flat();
  if (!flatVertices.every(Number.isFinite)) {
    return invalidAsset(asset, "Mesh vertices must be finite numbers.");
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(flatVertices, 3));
  if (Array.isArray(faces) && faces.length > 0) {
    geometry.setIndex(faces.flat());
  }
  geometry.computeVertexNormals();
  const mesh = new THREE.Mesh(geometry, materialForAsset(asset, config, { transparent: true }));
  mesh.name = asset.id;
  return { format, object: mesh };
}

function addReferenceHelpers(scene, bounds) {
  const size = sizeOfBounds(bounds);
  const span = Math.max(size.x, size.y, size.z, 1);
  const center = centerOfBounds(bounds);

  scene.add(new THREE.HemisphereLight(0xffffff, 0x8b94a3, 2.1));
  const directional = new THREE.DirectionalLight(0xffffff, 2.4);
  directional.position.set(center.x + span, center.y - span, center.z + span);
  scene.add(directional);

  const grid = new THREE.GridHelper(span * 1.5, 12, 0xb8c2d0, 0xe1e7ef);
  grid.rotation.x = Math.PI / 2;
  grid.position.set(center.x, center.y, bounds[2] - span * 0.03);
  scene.add(grid);

  const axes = new THREE.AxesHelper(span * 0.35);
  axes.position.copy(center);
  scene.add(axes);
}

function setRenderMetadata(object, asset, format) {
  const metadata = {
    assetId: asset.id,
    bounds: asset.bounds ?? null,
    format,
    objectId: asset.object_ids?.[0] ?? null,
    objectIds: [...(asset.object_ids ?? [])],
    primaryObjectId: asset.object_ids?.[0] ?? null
  };
  object.userData = { ...object.userData, ...metadata };
  for (const child of object.children ?? []) {
    child.userData = { ...child.userData, ...metadata };
  }
}

function isAssetVisible(asset, visibleIds) {
  const ids = asset.object_ids ?? [];
  return ids.length === 0 || ids.some((id) => visibleIds.has(id));
}

export function prepareAssetRenderConfig(asset, payload = {}, state = {}) {
  const config = {
    ...(payload.generation_config ?? {}),
    ...(asset.generation_config ?? {})
  };
  if (String(asset.format ?? "").toLowerCase() !== "tuyau_subpoint_glyphs") {
    const scalarColor = getObjectScalarColor(state, asset.object_ids ?? []);
    if (scalarColor !== null) {
      config.color = scalarColor;
    }
  }
  if (String(asset.format ?? "").toLowerCase() === "vector") {
    return scaleVectorConfig(asset, config, state);
  }
  return scaleVisualDeformationConfig(asset, config, state);
}

function materialForAsset(asset, config, options = {}) {
  const transparent = options.transparent ?? false;
  return new THREE.MeshStandardMaterial({
    color: colorForAsset(asset, config),
    metalness: 0.05,
    opacity: transparent ? 0.48 : 0.92,
    roughness: 0.68,
    transparent
  });
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
  if (asset.format === "vector") {
    return 0xd97706;
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
  return 0x2563eb;
}

function subpointLegend(config, values, state) {
  const stateLegend = getScalarLegend(state);
  const fallbackRange = config.range ?? config.legend?.range ?? rangeForValues(values);
  if (stateLegend?.overlay?.data?.result_type === "tuyau_subpoints") {
    return stateLegend;
  }
  return {
    field: config.legend?.field ?? "VMIS",
    unit: config.legend?.unit ?? "Pa",
    range: fallbackRange,
    colorMap: config.legend?.color_map ?? "turbo",
    thresholds: config.legend?.thresholds ?? {}
  };
}

function colorForSubpointValue(value, legend, asset, config) {
  const scalarColor = colorForScalarValue(Number(value), legend);
  return scalarColor ?? colorForAsset(asset, config);
}

function rangeForValues(values) {
  const numeric = values.filter(Number.isFinite);
  if (numeric.length === 0) {
    return { min: 0, max: 1 };
  }
  return { min: Math.min(...numeric), max: Math.max(...numeric) };
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
  const scaled = points.map((point, index) => {
    const base = basePoints[index] ?? points[0];
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

function pickNearestProjectedObject(graph, point, viewport) {
  let best = null;
  for (const object of graph.renderableObjects ?? []) {
    const objectId = object.userData?.primaryObjectId || object.userData?.objectId;
    if (!objectId) {
      continue;
    }
    const center = new THREE.Vector3();
    new THREE.Box3().setFromObject(object).getCenter(center);
    const projected = center.project(graph.camera);
    if (!Number.isFinite(projected.x) || !Number.isFinite(projected.y) || projected.z < -1 || projected.z > 1) {
      continue;
    }
    const screenX = ((projected.x + 1) / 2) * viewport.width;
    const screenY = ((-projected.y + 1) / 2) * viewport.height;
    const distance = Math.hypot(screenX - point.x, screenY - point.y);
    if (!best || distance < best.distance) {
      best = { objectId, distance };
    }
  }
  return best?.objectId ?? null;
}
