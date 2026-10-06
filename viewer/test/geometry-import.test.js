import assert from "node:assert/strict";
import test from "node:test";
import { geometryImportOptions, geometryPreviewState, pythonLiteral, uploadGeometry } from "../src/geometryImport.js";
import { getGeometryRelations, getPropertySections, selectObject, distance } from "../src/selection.js";
import { getSelectionSummary } from "../src/selectionSummary.js";

const values = { id: "part.1", unit: "mm", origin: [10, 20, 30], rotation: [0, 0, 90] };
const surface = { ok: true, component_id: "part.1", role: "reference", unit_scale_to_m: .001,
  placement: geometryImportOptions(values).placement,
  metadata: { mesh_vertices_local: [[0, 0, 0], [1000, 0, 0], [0, 2000, 0]], mesh_faces: [[0, 1, 2]] } };

test("explicit units and placement transform actual source vertices exactly once", () => {
  assert.throws(() => geometryImportOptions({ ...values, unit: "" }), /Choose/);
  assert.throws(() => geometryImportOptions({ ...values, unit: "custom", scale: 0 }), /positive/);
  assert.throws(() => geometryImportOptions({ ...values, origin: [0, "", 0] }), /finite/);
  assert.throws(() => geometryImportOptions({ ...values, id: "a".repeat(65) }), /1–64/);
  const state = geometryPreviewState(surface);
  const mesh = state.geometryAssets[0];
  assert.deepEqual(mesh.generation_config.faces, [[0, 1, 2]]);
  assert.deepEqual(mesh.bounds, [8, 20, 30, 10, 21, 30]);
  assert.ok(Math.abs(distance(...mesh.generation_config.vertices.slice(0, 2)) - 1) < 1e-12);
  assert.deepEqual(selectObject(state, "object:component:part.1").selectedObjectIds, ["object:component:part.1"]);
  assert.deepEqual(surface.metadata.mesh_vertices_local[1], [1000, 0, 0]);
});

test("surface preview refuses malformed or absent triangles instead of showing a bounds proxy", () => {
  for (const metadata of [{ local_bounds: [0, 0, 0, 1, 1, 1] },
    { ...surface.metadata, mesh_faces: [[0, 1, 3]] },
    { ...surface.metadata, mesh_vertices_local: [[NaN, 0, 0], [1, 0, 0], [0, 1, 0]] }]) {
    assert.throws(() => geometryPreviewState({ ...surface, metadata }), /actual surface/);
  }
  assert.throws(() => geometryPreviewState({ ...surface, placement: { rotation: [0, 0, 0, 0] } }), /quaternion/);
});

test("STEP uses normalized millimetres while STL keeps raw coordinate units", () => {
  for (const format of ["STEP", "stp"]) {
    for (const unit of ["m", "cm", "inch", ""]) assert.throws(() => geometryImportOptions({ ...values, format, unit }), /normalized to millimetres/);
    assert.equal(geometryImportOptions({ ...values, format, unit: "mm" }).unit_scale_to_m, .001);
    assert.equal(geometryImportOptions({ ...values, format, unit: "custom", scale: 1 }).unit_scale_to_m, 1);
  }
  assert.equal(geometryImportOptions({ ...values, format: "STL", unit: "m" }).unit_scale_to_m, 1);
  assert.equal(geometryImportOptions({ ...values, format: "STL", unit: "inch" }).unit_scale_to_m, .0254);
});

test("geometry upload sends raw source and explicit options only to the preview/store API", async () => {
  const file = { name: "Müller part.STP", size: 12 };
  const options = geometryImportOptions(values);
  for (const action of ["preview", "store"]) {
    const result = await uploadGeometry(action, file, options, { fetcher: async (url, init) => {
      assert.equal(url, `/api/geometry/${action}`);
      assert.equal(init.body, file);
      assert.equal(init.headers["Content-Type"], "application/octet-stream");
      assert.equal(decodeURIComponent(init.headers["X-Geometry-Name"]), file.name);
      assert.deepEqual(JSON.parse(init.headers["X-Geometry-Options"]), options);
      return { ok: true, json: async () => surface };
    } });
    assert.equal(result, surface);
  }
  await assert.rejects(uploadGeometry("preview", { name: "part.stl", size: 17 * 1024 * 1024 }, options), /16 MiB/);
  await assert.rejects(uploadGeometry("preview", file, options, { fetcher: async () => ({ ok: false, status: 503, json: async () => ({ error: "Gmsh is unavailable" }) }) }), /Gmsh is unavailable/);
});

test("inspector exposes actual geometry, analysis role, candidate interfaces and selected mechanics", () => {
  const object = { id: "part", kind: "imported_component", metadata: { role: "reference", geometry_representation: "source_surface",
    cad_asset: { source_path: "geometry/a.stl", source_format: "STL", content_digest: "sha256:abc", unit_scale_to_m: .001, metadata: { ...surface.metadata, inspection: { boundary_edges: 3, closed_surface: false } } },
    ports: [{ id: "cut", status: "detected", kind: "annular_face" }] } };
  const state = { objects: [object], geometryAssets: [{ id: "unused" }], overlays: [], issues: [] };
  const rows = getPropertySections(state, "part").find(section => section.id === "imported_geometry").rows;
  assert.equal(rows.role, "Reference geometry"); assert.equal(rows.triangles, 1); assert.equal(rows.closed_surface, false);
  assert.match(rows.ports, /cut: detected/);
  assert.match(rows.clearance_coverage, /shell\/STEP bodies and reference pairs excluded/);
  object.metadata.analysis_regions = [{ code_aster_modelisation: "3D" }];
  assert.equal(getPropertySections(state, "part").find(section => section.id === "imported_geometry").rows.role, "Analysis geometry: 3D");
  const beam = { id: "beam", kind: "mixed_coupling", metadata: { continuation_family: "frame", code_aster_option: "3D_POU" } };
  state.objects.push(beam);
  assert.equal(getPropertySections(state, "beam").find(section => section.id === "connections").rows.kind, "Beam to solid port");
  const support = { id: "link", kind: "support", metadata: { node: "N1", attached_to: "N2", attachment_mode: "dof_equality", blocked_dof: [1, 1, 0, 1, 1, 1] } };
  state.objects.push(support);
  assert.match(getPropertySections(state, "link").find(section => section.id === "node_attachment").rows.kinematics, /no offset lever terms/);
});

test("copying a geometric selector keeps string content and produces valid Python literals", () => {
  assert.equal(pythonLiteral({ position: [1, 2, 3], name: "true null", active: true, none: null }), '{"position": [1, 2, 3], "name": "true null", "active": True, "none": None}');
  assert.throws(() => pythonLiteral({ position: [Infinity, 0, 0] }), /cannot/);
});

test("imported STL inspection distinguishes reference triangles from structural meshing", () => {
  const object = { id: "stl", kind: "imported_component", metadata: { role: "reference", geometry_representation: "source_surface",
    cad_asset: { source_format: "STL", metadata: surface.metadata }, ports: [], couplings: [], analysis_regions: [] } };
  const state = { objects: [object], geometryAssets: [], overlays: [], issues: [] };
  const sections = getPropertySections(state, object.id);
  const meshing = sections.find(section => section.id === "meshing").rows;
  const integration = sections.find(section => section.id === "structural_integration").rows;
  assert.match(meshing["Display mesh"], /STL source triangles/);
  assert.match(meshing["Solver mesh"], /No structural FE mesh/);
  assert.equal(meshing["Source triangles"], 1);
  assert.match(integration.Stiffness, /No structural stiffness/);
  assert.equal(integration.Ports, "0 ports defined");
  assert.equal(integration.Connections, "0 structural couplings defined");
  assert.equal(getSelectionSummary(state, object.id).badge, "Reference");
  assert.match(getSelectionSummary(state, object.id).lede, /clearance.*no structural stiffness/i);
  assert.deepEqual(getSelectionSummary(state, object.id).sections.slice(0, 2).map(section => section.id), ["meshing", "structural_integration"]);
  assert.equal(getSelectionSummary(state, object.id).reference.source_format, "STL");
  assert.ok(!getSelectionSummary(state, object.id).sections.some(section => section.id === "imported_geometry"));
});

test("STEP inspection exposes authored FE material, order and sizes without treating tessellation as FE mesh", () => {
  const object = { id: "step", kind: "imported_component", metadata: { geometry_representation: "source_surface",
    cad_asset: { source_format: "STEP", metadata: { ...surface.metadata, mesh_size: "auto", interface_mesh_sizes: { inlet: .01 } } },
    analysis_regions: [{ id: "solid", role: "solid_3d", material: "P265GH", code_aster_modelisation: "3D", element_order: 2, mesh_group: "G_SOLID" }],
    ports: [{ id: "inlet", status: "confirmed" }, { id: "candidate", status: "detected" }],
    couplings: [{ id: "inlet_tie", code_aster_option: "3D_TUYAU" }] } };
  const state = { objects: [object], geometryAssets: [], overlays: [], issues: [] };
  const rows = getPropertySections(state, object.id).find(section => section.id === "meshing").rows;
  assert.match(rows["Display mesh"], /STEP display tessellation/);
  assert.match(rows["Solver mesh"], /separate.*source triangles/i);
  assert.equal(rows["solid material"], "P265GH");
  assert.equal(rows["solid modelisation"], "3D");
  assert.equal(rows["solid element order"], 2);
  assert.equal(rows["solid mesh group"], "G_SOLID");
  assert.equal(rows["Requested size (m)"], "auto");
  assert.deepEqual(rows["Interface sizes (m)"], { inlet: .01 });
  assert.equal(getSelectionSummary(state, object.id).badge, "Analysis geometry");
  assert.match(getSelectionSummary(state, object.id).lede, /1 structural coupling/);
  object.metadata.analysis_regions = [];
  assert.match(getSelectionSummary(state, object.id).lede, /no analysis region/i);
});

test("a bounds envelope never reports proxy corners and triangles as source mesh counts", () => {
  const object = { id: "proxy", kind: "imported_component", geometry_asset_id: "proxy-mesh", metadata: {
    geometry_representation: "bounds_envelope", cad_asset: { source_format: "STEP", metadata: {} } } };
  const state = { objects: [object], geometryAssets: [{ id: "proxy-mesh", format: "mesh", generation_config: {
    vertices: Array.from({ length: 8 }, () => [0, 0, 0]), faces: Array.from({ length: 12 }, () => [0, 1, 2]) } }], overlays: [], issues: [] };
  const rows = getPropertySections(state, object.id).find(section => section.id === "meshing").rows;
  assert.match(rows["Display mesh"], /source surface unavailable/);
  assert.ok(!Object.hasOwn(rows, "Source vertices"));
  assert.ok(!Object.hasOwn(rows, "Source triangles"));
});

test("geometry relations navigate authored ownership and load path using entity resolution only", () => {
  const component = { id: "part-custom", kind: "imported_component", entity_ref: "component:part", metadata: { ports: [{ id: "cut", owner: "component:part", status: "confirmed" }], couplings: [{ id: "tie", target: "port:cut" }] } };
  const port = { id: "cut-custom", kind: "imported_port", entity_ref: "port:cut", metadata: { id: "cut", owner: "component:part", status: "confirmed" } };
  const coupling = { id: "tie-custom", kind: "mixed_coupling", entity_ref: "coupling:tie", metadata: { id: "tie", source: "element:pipe", source_node: "node:REF", target: "port:cut",
    attachments: [{ id: "V3", node: "REF", attached_to: "FRAME" }] } };
  const source = { id: "pipe-custom", kind: "pipe", entity_ref: "element:pipe" };
  const reference = { id: "ref-custom", kind: "analysis_mesh_node", metadata: { source_ref: "node:REF" } };
  const support = { id: "support-custom", kind: "support", entity_ref: "support:V3" };
  const attachedNode = { id: "frame-custom", kind: "analysis_mesh_node", entity_ref: "node:FRAME" };
  const nearby = { id: "nearby", kind: "pipe", entity_ref: "element:nearby", metadata: { nodes: ["OTHER", "FRAME"] } };
  const state = { objects: [component, port, coupling, source, reference, support, attachedNode, nearby], geometryAssets: [], objectMap: { "ref-custom": "node:REF" } };
  const ids = id => getGeometryRelations(state, id).map(link => link.id);
  assert.deepEqual(new Set(ids(component.id)), new Set([port.id, coupling.id, source.id, reference.id, support.id, attachedNode.id]));
  assert.deepEqual(new Set(ids(port.id)), new Set([component.id, coupling.id, source.id, reference.id, support.id, attachedNode.id]));
  assert.deepEqual(new Set(ids(coupling.id)), new Set([component.id, port.id, source.id, reference.id, support.id, attachedNode.id]));
  assert.ok(getGeometryRelations(state, port.id).every(link => typeof link.label === "string" && link.label.length));
  assert.deepEqual(ids(nearby.id), []);
  component.metadata.ports = []; component.metadata.couplings = [];
  assert.ok(ids(component.id).includes(port.id), "Standalone port/coupling ownership supports older bundles");
  assert.deepEqual(ids("missing"), []);
});

test("geometry relations ignore malformed reference values while retaining valid links", () => {
  const component = { id: "part", kind: "imported_component", entity_ref: "component:part", metadata: {} };
  const port = { id: "port", kind: "imported_port", entity_ref: "port:cut", metadata: { id: "cut", owner: "component:part" } };
  const member = { id: "member", kind: "pipe", entity_ref: "element:member" };
  const malformed = { id: "malformed", kind: "mixed_coupling", entity_ref: "coupling:malformed", metadata: {
    id: "malformed", source: { kind: "element", id: "member" }, source_node: 42, target: { kind: "port", id: "cut" } } };
  const partial = { id: "partial", kind: "mixed_coupling", entity_ref: "coupling:partial", metadata: {
    id: "partial", source: "element:member", source_node: {}, target: "port:cut" } };
  const badOwner = { id: "bad-owner", kind: "imported_port", entity_ref: "port:bad", metadata: { id: "bad", owner: {} } };
  const state = { objects: [component, port, member, malformed, partial, badOwner], geometryAssets: [] };
  const ids = id => getGeometryRelations(state, id).map(link => link.id);
  assert.deepEqual(new Set(ids(component.id)), new Set([port.id, member.id, partial.id]));
  assert.deepEqual(ids(malformed.id), []);
  assert.deepEqual(ids(badOwner.id), []);
  assert.ok(ids(partial.id).includes(member.id));
});
