import test from "node:test";
import assert from "node:assert/strict";
import { createStudioMeshClient } from "../src/studioMesh.js";

const response = (value, status = 200) => ({ ok: status < 400, status, json: async () => value });

test("convergence uses the acknowledged revision and Python-configured endpoint", async () => {
  const calls=[];
  const client=createStudioMeshClient({fetcher:async(path,options)=>{calls.push([path,options]);return response({state:"idle",loaded_source_revision:9});}});
  await client.refresh();
  await client.converge();
  assert.equal(calls[1][0],"/api/mesh/convergence");
  assert.deepEqual(JSON.parse(calls[1][1].body),{force:true,expected_source_revision:9});
  client.close();
});

test("an older refresh cannot overwrite a newly accepted native job", async () => {
  let finishRefresh;
  const changes = [];
  const client = createStudioMeshClient({ onChange: state => changes.push(state),
    fetcher: async (_path, options) => options?.method === "POST"
      ? response({ id:"new", state:"running", busy:true, loaded_source_revision:4 }, 202)
      : new Promise(resolve => { finishRefresh = resolve; }) });
  const old = client.refresh();
  await client.generate(false);
  finishRefresh(response({ state:"idle", busy:false, loaded_source_revision:3 }));
  await old;
  client.close();
  assert.equal(client.snapshot().job.id, "new");
  assert.equal(changes.length, 1);
});

test("revision conflict remains actionable and is never automatically retried", async () => {
  const calls = [];
  const client = createStudioMeshClient({ fetcher: async (path, options) => {
    calls.push([path, options]);
    return options?.method === "POST"
      ? response({ error:"Source revision changed; refresh before generating." }, 409)
      : response({ id:null, state:"idle", busy:false, loaded_source_revision:5 });
  }});
  await client.refresh();
  await client.generate(false);
  assert.deepEqual(JSON.parse(calls[1][1].body), { force:false, expected_source_revision:5 });
  assert.match(client.snapshot().error, /Source revision changed/);
  assert.equal(calls.length, 2);
  client.close();
});
