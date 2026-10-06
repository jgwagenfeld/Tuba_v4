import * as THREE from "three";

// Duplicate lighting vertices only where faces form a hard edge. Unlike
// welding by rounded world coordinates, this preserves even very thin walls
// and keeps coincident, independently authored surfaces separate.
export function splitSurfaceCreases(geometry, baseVertices, creaseAngle = Math.PI / 4) {
  if (!geometry.index) {
    geometry.computeVertexNormals();
    return geometry;
  }
  const positions = geometry.getAttribute("position");
  const reference = Array.isArray(baseVertices) && baseVertices.length === positions.count
    ? new THREE.Float32BufferAttribute(baseVertices.flat(), 3) : positions;
  const indices = Array.from(geometry.index.array);
  const adjacent = Array.from({length:positions.count},()=>[]);
  const faceNormals = [];
  const a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3();
  for (let i=0;i<indices.length;i+=3) {
    a.fromBufferAttribute(reference,indices[i]);
    b.fromBufferAttribute(reference,indices[i+1]);
    c.fromBufferAttribute(reference,indices[i+2]);
    faceNormals.push(b.sub(a).cross(c.sub(a)).normalize().clone());
    for(let j=i;j<i+3;j++) adjacent[indices[j]].push(j);
  }
  const sourceIndices = Array.from({length:positions.count},(_,i)=>i);
  const cutoff = Math.cos(creaseAngle);
  adjacent.forEach((corners,sourceIndex)=>{
    const groups = [];
    for (const corner of corners) {
      const normal = faceNormals[Math.floor(corner/3)];
      let group = groups.find(candidate=>candidate.normal.dot(normal)>=cutoff);
      if (!group) {
        const index = groups.length ? sourceIndices.push(sourceIndex)-1 : sourceIndex;
        group = {normal,index};
        groups.push(group);
      }
      indices[corner] = group.index;
    }
  });
  // Preserve the original vertex prefix: scene surface_edge_indices still
  // address it. The map also carries scalar colors and section deformation to
  // each new lighting vertex without modifying any engineering topology.
  const result = new THREE.BufferGeometry();
  result.setAttribute("position",new THREE.Float32BufferAttribute(
    sourceIndices.flatMap(i=>[positions.getX(i),positions.getY(i),positions.getZ(i)]),3));
  result.setIndex(indices);
  result.userData.sourceVertexIndices = sourceIndices;
  result.computeVertexNormals();
  geometry.dispose();
  return result;
}

// The corner lines of a profiled member: edges where two faces meet at a crease
// and that run along the member. A square tube needs them to read as square -
// shaded or greyed, its flat faces alone look like a round pipe. Only edges
// along the axis: cap edges would draw a ring at every segment a deformed member
// is split into. The indices address the original vertices, which
// splitSurfaceCreases keeps as its prefix, so the lines can share the mesh's
// position attribute and follow its deformation.
export function memberCornerEdges(geometry, axis, creaseAngle = Math.PI / 4) {
  if (!geometry.index) return [];
  const positions = geometry.getAttribute("position");
  const indices = geometry.index.array;
  const normalsByEdge = new Map();
  const a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3();
  for (let i = 0; i < indices.length; i += 3) {
    a.fromBufferAttribute(positions, indices[i]);
    b.fromBufferAttribute(positions, indices[i + 1]);
    c.fromBufferAttribute(positions, indices[i + 2]);
    const normal = b.sub(a).cross(c.sub(a)).normalize().clone();
    for (const [p, q] of [[indices[i], indices[i + 1]], [indices[i + 1], indices[i + 2]], [indices[i + 2], indices[i]]]) {
      const key = p < q ? `${p},${q}` : `${q},${p}`;
      if (!normalsByEdge.has(key)) normalsByEdge.set(key, []);
      normalsByEdge.get(key).push(normal);
    }
  }
  const cutoff = Math.cos(creaseAngle);
  const along = axis.clone().normalize();
  const edges = [];
  for (const [key, normals] of normalsByEdge) {
    if (normals.length !== 2 || normals[0].dot(normals[1]) >= cutoff) continue;
    const [p, q] = key.split(",").map(Number);
    a.fromBufferAttribute(positions, p);
    b.fromBufferAttribute(positions, q);
    if (Math.abs(b.sub(a).normalize().dot(along)) < 0.9) continue;
    edges.push(p, q);
  }
  return edges;
}
