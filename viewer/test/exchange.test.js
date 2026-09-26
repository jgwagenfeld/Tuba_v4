import assert from "node:assert/strict";
import test from "node:test";
import { fetchIfcCapability, fetchIfcExport, publishedDownloads } from "../src/exchange.js";
import { getPropertySections } from "../src/selection.js";

test("only declared, shape-valid download links reach the Gallery", () => {
  const entry = { id: "pipe", downloads: {
    project: "downloads/pipe.zip", ifc: "downloads/pipe.ifc", other: "downloads/missing.txt"
  } };
  assert.deepEqual(publishedDownloads(entry), [["project", "downloads/pipe.zip"], ["ifc", "downloads/pipe.ifc"]]);
  assert.deepEqual(publishedDownloads({ id: "mesh" }), []);
});

test("IFC reference identity and property sets appear in selection details", () => {
  const object = { id: "ifc:abc:guid", kind: "ifc_reference", source: { ifc_guid: "guid", reference_id: "abc" },
    metadata: { ifc_class: "IfcPipeSegment", properties: { Pset_Test: { Service: "Hydrogen" } } } };
  const section = getPropertySections({ objects: [object], geometryAssets: [], overlays: [], issues: [] }, object.id)
    .find(item => item.id === "ifc");
  assert.deepEqual(section.rows, { guid: "guid", class: "IfcPipeSegment", reference: "abc",
    "Pset_Test.Service": "Hydrogen" });
});

test("Exchange refreshes capability and keeps rejected export errors in its request path", async () => {
  const capability = { export_available: false, export_reason: "Imported CAD cannot be included" };
  assert.deepEqual(await fetchIfcCapability(async (url, options) => {
    assert.equal(url, "/api/project");
    assert.equal(options.cache, "no-store");
    return { ok: true, json: async () => ({ ok: true, ifc: capability }) };
  }), capability);
  await assert.rejects(fetchIfcExport(async (url) => {
    assert.equal(url, "/api/ifc/export");
    return { ok: false, status: 422, json: async () => ({ error: "Export incomplete" }) };
  }), /Export incomplete/);
  const exported = await fetchIfcExport(async () => ({
    ok: true, blob: async () => new Blob(["IFC"]),
    headers: new Headers({ "content-disposition": 'attachment; filename="plant.ifc"' })
  }));
  assert.equal(exported.filename, "plant.ifc");
  assert.equal(await exported.blob.text(), "IFC");
});
