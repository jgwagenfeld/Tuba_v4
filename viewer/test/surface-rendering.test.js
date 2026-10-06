import assert from "node:assert/strict";
import test from "node:test";
import { Vector3 } from "three";
import { applyFocusSelection, applyVisualDeformationScale, createThreeSceneGraph } from "../src/renderer.js";

// Shared corner vertices, as emitted by straight_section_surface_mesh. Keeping
// them shared for lighting makes a square member read as a rounded extrusion.
const vertices = [[0,-1,-1],[0,1,-1],[0,1,1],[0,-1,1],
  [3,-1,-1],[3,1,-1],[3,1,1],[3,-1,1]];
const faces = [[0,1,5],[0,5,4],[1,2,6],[1,6,5],[2,3,7],[2,7,6],
  [3,0,4],[3,4,7],[0,3,2],[0,2,1],[4,5,6],[4,6,7]];

function graphFor(format, config = {}) {
  return createThreeSceneGraph({ referenceGridVisible: false,
    geometryAssets: [{ id:"shape", format, object_ids:["shape"],
      bounds:[0,-1,-1,3,1,1], generation_config:config }],
    geometryPayloads:[], visibleObjectIds:["shape"] });
}

function assertPlanarLighting(mesh) {
  const p = mesh.geometry.getAttribute("position");
  const n = mesh.geometry.getAttribute("normal");
  const indices = mesh.geometry.index.array;
  for (let i = 0; i < indices.length; i += 3) {
    const a = new Vector3().fromBufferAttribute(p, indices[i]);
    const b = new Vector3().fromBufferAttribute(p, indices[i+1]);
    const c = new Vector3().fromBufferAttribute(p, indices[i+2]);
    const faceNormal = b.sub(a).cross(c.sub(a)).normalize();
    for (const index of indices.slice(i,i+3)) {
      assert.ok(faceNormal.dot(new Vector3().fromBufferAttribute(n,index)) > 0.99999,
        "lighting normal must stay on its planar face at a square corner");
    }
  }
}

test("ordinary pipe and obstacle surfaces are opaque unless explicitly faded", () => {
  for (const [format, config] of [["tube", {points:[[0,0,0],[3,0,0]],radius_m:0.3}],
    ["aabb", {}], ["cylinder", {}]]) {
    const mesh = graphFor(format, config).objectsByObjectId.get("shape");
    assert.equal(mesh.material.opacity, 1, `${format} must not fade by default`);
    assert.equal(mesh.material.transparent, false);
    assert.equal(mesh.material.depthWrite, true);
  }
});

test("rectangular profiles light as flat faces with sharp corners and caps", () => {
  assertPlanarLighting(graphFor("mesh", {vertices,faces,source:"tuba.element"})
    .objectsByObjectId.get("shape"));
});

test("100 percent opacity occludes even when a surface carries a transparency hint", () => {
  const mesh=graphFor("tube_envelope",{points:[[0,0,0],[3,0,0]],radius_m:1,opacity:1,transparent:true})
    .objectsByObjectId.get("shape");
  assert.equal(mesh.material.transparent,false);
  assert.equal(mesh.material.depthWrite,true);
});

test("focusing a faded surface makes it opaque and restores its fade afterwards", () => {
  const graph=graphFor("mesh",{vertices,faces,opacity:.4});
  const material=graph.objectsByObjectId.get("shape").material;
  applyFocusSelection(graph,["shape"]);
  assert.equal(material.opacity,1);
  assert.equal(material.transparent,false);
  assert.equal(material.depthWrite,true);
  applyFocusSelection(graph,[]);
  assert.equal(material.opacity,.4);
  assert.equal(material.transparent,true);
  assert.equal(material.depthWrite,false);
});

test("sharp profile normals survive solved section rotations and scalar colors", () => {
  const config = {vertices,faces,base_vertices:vertices,
    source:"tuba.deformed_analysis_mesh.profile",visual_scale:4,
    section_origins:[[0,0,0],[3,0,0]],
    section_deformations:[[0,0,0,Math.PI/8,0,0],[0,0,0,Math.PI/8,0,0]],
    vertex_values:[1,2,3,4,5,6,7,8], legend:{range:{min:1,max:8},color_map:"viridis"}};
  const graph = graphFor("mesh",config);
  const mesh = graph.objectsByObjectId.get("shape");
  for (const scale of [0,1,2,4]) {
    applyVisualDeformationScale(graph.root,{visualDeformationScale:scale});
    assertPlanarLighting(mesh);
    const p = mesh.geometry.getAttribute("position");
    for (let i = 0; i < p.count; i++) {
      assert.ok(Math.abs(Math.hypot(p.getY(i),p.getZ(i))-Math.SQRT2)<1e-6,
        "splitting a shading vertex must preserve its solved section position");
    }
    assert.equal(mesh.geometry.getAttribute("color").count,p.count);
  }
});

test("pipe walls keep smooth normals while their annular caps stay flat", () => {
  const mesh = graphFor("tube",{points:[[0,0,0],[3,0,0]],radius_m:1,inner_radius_m:0.8})
    .objectsByObjectId.get("shape");
  const wallNormals = mesh.children[0].geometry.getAttribute("normal");
  assert.ok(Array.from(wallNormals.array).some(value=>Math.abs(value)>0.1 && Math.abs(value)<0.9));
  for (const cap of mesh.children.slice(2)) {
    const n = cap.geometry.getAttribute("normal");
    for(let i=0;i<n.count;i++) assert.ok(Math.abs(n.getX(i))>0.99999);
  }
});
