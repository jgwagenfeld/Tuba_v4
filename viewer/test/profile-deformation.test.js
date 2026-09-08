import assert from "node:assert/strict";
import test from "node:test";
import { scaledSectionPoints, createThreeSceneGraph, applyVisualDeformationScale } from "../src/renderer.js";

test("section deformation rotates rigid profiles and triads at every display scale", () => {
  const config = { base_vertices: [[0,1,0],[0,0,1],[2,1,0],[2,0,1]],
    section_origins: [[0,0,0],[2,0,0]],
    section_deformations: [[0,0,0,0,0,0],[0,0.1,0,Math.PI/4,0,0]] };
  assert.deepEqual(scaledSectionPoints(config, 0), config.base_vertices);
  for (const scale of [0.5,1,2,4]) {
    const points = scaledSectionPoints(config,scale);
    assert.ok(Math.abs(Math.hypot(points[2][1]-0.1*scale, points[2][2])-1)<1e-12);
    assert.ok(Math.abs(Math.hypot(...points[2].map((v,i)=>v-points[3][i]))-Math.SQRT2)<1e-12);
    assert.ok(Math.abs(points[2][2]-Math.sin(Math.PI/4*scale))<1e-12);
  }
  const frame = {...config, base_points:config.base_vertices.slice(2), base_vertices:undefined,
    section_origins:config.section_origins.slice(1), section_deformations:config.section_deformations.slice(1)};
  assert.deepEqual(scaledSectionPoints(frame,2),scaledSectionPoints(config,2).slice(2));
});

test("cached mesh and local frame follow solved section rotations, including preview updates", () => {
  const config = { base_vertices:[[0,1,0],[0,0,1],[0,-1,0]], vertices:[[0,1,0],[0,0,1],[0,-1,0]],
    faces:[[0,1,2]], section_origins:[[0,0,0]], section_deformations:[[0,0.1,0,Math.PI/4,0,0]],
    source:"tuba.deformed_analysis_mesh.profile", visual_scale:4 };
  const state = { bounds:[0,-1,-1,1,1,1], geometryAssets:[
    {id:"mesh",format:"mesh",object_ids:["profile"],generation_config:config},
    {id:"axes",format:"polyline",object_ids:["axis"],generation_config:{...config,vertices:undefined,
      base_vertices:undefined,base_points:[[0,0,0],[0,1,0]],points:[[0,0,0],[0,1,0]]}}],
    geometryPayloads:[],visibleObjectIds:["profile","axis"],visualDeformationScale:2 };
  const graph = createThreeSceneGraph(state);
  for (const [scale,previewOnly] of [[2,false],[1,true],[4,false]]) {
    applyVisualDeformationScale(graph.root,{...state,visualDeformationScale:scale},{previewOnly});
    const mesh = graph.objectsByObjectId.get("profile").geometry.getAttribute("position");
    const frame = graph.objectsByObjectId.get("axis").geometry.getAttribute("position");
    assert.ok(Math.abs(mesh.getZ(0)-Math.sin(Math.PI/4*scale))<1e-6);
    assert.ok(Math.abs(mesh.getY(0)-Math.cos(Math.PI/4*scale)-0.1*scale)<1e-6);
    assert.ok(Math.abs(frame.getZ(1)-mesh.getZ(0))<1e-6);
  }
});
