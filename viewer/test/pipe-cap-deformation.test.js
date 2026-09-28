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
