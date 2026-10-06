import assert from "node:assert/strict";
import test from "node:test";
import { Vector3 } from "three";
import { applyVisualDeformationScale, createThreeSceneGraph, disposeThreeSceneGraph } from "../src/renderer.js";

test("hollow pipe end caps follow the surface when deformation is rescaled", () => {
  const asset = {
    id: "geometry:deformed:visual:pipe",
    format: "tube",
    object_ids: ["object:pipe"],
    generation_config: {
      source: "tuba.deformed_analysis_mesh.profile",
      base_points: [[2, 1, 0], [3, 1, 0]],
      points: [[2, 1.4, 0.2], [3, 1.8, 0.6]],
      radius_m: 0.05715,
      inner_radius_m: 0.05113,
      visual_scale: 40
    }
  };
  const state = { geometryAssets: [asset], visibleObjectIds: asset.object_ids, visualDeformationScale: 40 };
  const graph = createThreeSceneGraph(state);
  const reference = createThreeSceneGraph({
    ...state,
    geometryAssets: [{ ...asset, id: "geometry:reference", generation_config: {
      ...asset.generation_config, source: "tuba.element", visual_scale: 1,
      points: asset.generation_config.base_points
    } }]
  });
  const pipe = graph.objectsByObjectId.get("object:pipe");
  const basePipe = reference.objectsByObjectId.get("object:pipe");
  const worldVertices = mesh => {
    mesh.updateWorldMatrix(true, false);
    return Array.from({ length: mesh.geometry.getAttribute("position").count }, (_, i) =>
      mesh.localToWorld(mesh.getVertexPosition(i, new Vector3())));
  };
  const sourceCaps = pipe.children.slice(2).map(worldVertices);
  const baseCaps = basePipe.children.slice(2).map(worldVertices);
  assert.equal(sourceCaps.length, 2);
  for (const scale of [1, 20, 0, 80, 40]) {
    applyVisualDeformationScale(graph.root, { ...state, visualDeformationScale: scale });
    pipe.children.slice(2).forEach((cap, end) => {
      worldVertices(cap).forEach((actual, i) => {
        const expected = baseCaps[end][i].clone().lerp(sourceCaps[end][i], scale / 40);
        assert.ok(actual.distanceTo(expected) < 1e-6, `cap ${end}, vertex ${i}, scale ${scale} stays attached`);
      });
    });
  }
  disposeThreeSceneGraph(graph);
  disposeThreeSceneGraph(reference);
});

test("a bent solved pipe keeps its radius at every display scale", () => {
  const radius = 0.04;
  const asset = {
    id: "geometry:deformed:visual:span",
    format: "tube",
    object_ids: ["object:span"],
    generation_config: {
      source: "tuba.deformed_analysis_mesh.profile",
      base_points: [[0, 0, 0], [1, 0, 0], [2, 0, 0], [3, 0, 0]],
      points: [[0, 0, 0.002], [1, 0.004, 0.012], [2, 0.004, 0.014], [3, 0, 0.003]],
      radius_m: radius,
      radial_segments: 12,
      visual_scale: 1
    }
  };
  const state = { geometryAssets: [asset], visibleObjectIds: asset.object_ids, visualDeformationScale: 1 };
  const graph = createThreeSceneGraph(state);
  const tube = graph.objectsByObjectId.get("object:span");
  const ring = 13;
  for (const scale of [1, 10, 100]) {
    applyVisualDeformationScale(graph.root, { ...state, visualDeformationScale: scale });
    const vertices = Array.from({ length: tube.geometry.getAttribute("position").count }, (_, i) =>
      tube.getVertexPosition(i, new Vector3()));
    for (let first = 0; first < vertices.length; first += ring) {
      // The seam vertex repeats the first, so the centre is the mean of the other twelve.
      const members = vertices.slice(first, first + ring - 1);
      const centre = members.reduce((sum, vertex) => sum.add(vertex), new Vector3()).divideScalar(members.length);
      for (const vertex of members) {
        assert.ok(Math.abs(vertex.distanceTo(centre) - radius) < 1e-4, `ring at ${first / ring}, scale ${scale}: ${vertex.distanceTo(centre)}`);
      }
    }
  }
  disposeThreeSceneGraph(graph);
});
