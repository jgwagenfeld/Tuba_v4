import assert from "node:assert/strict";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import * as sceneLoaderModule from "../src/sceneLoader.js";

import {
  createViewerState,
  loadSceneBundle,
  loadSceneBundleFromUrl,
  setLayerVisibility,
  categoryForLayerId,
  legacyCategoryForLayerId,
  categorizeLayers,
  applyTaskVisibilityPreset
} from "../src/sceneLoader.js";

test("startup falls back to the first available bundle when the preferred review is absent", () => {
  assert.equal(typeof sceneLoaderModule.resolveBundleId, "function");
  assert.equal(
    sceneLoaderModule.resolveBundleId(null, ["gmsh-tee-mesh-review", "smoke-scene"]),
    "gmsh-tee-mesh-review"
  );
});

test("startup retains an explicitly requested bundle", () => {
  assert.equal(sceneLoaderModule.resolveBundleId("custom-review", []), "custom-review");
  assert.equal(
    sceneLoaderModule.resolveBundleId("custom-review", ["gmsh-tee-mesh-review"]),
    "custom-review"
  );
});

async function createFixtureBundle() {
  const root = join(tmpdir(), `tuba-viewer-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  await mkdir(join(root, "metadata"), { recursive: true });
  await mkdir(join(root, "geometry"), { recursive: true });
  const scene = {
    schema_version: "visualization.scene.v1",
    scene_id: "scene_001",
    model_id: "model_001",
    units: { length: "m" },
    coordinate_system: { up_axis: "Z" },
    objects: [
      {
        id: "object:element:pipe_0",
        entity_ref: "element:pipe_0",
        kind: "pipe",
        name: "P-100",
        geometry_asset_id: "geometry:element:pipe_0",
        metadata: { section: "PipeSec" }
      }
    ],
    geometry_assets: [
      {
        id: "geometry:element:pipe_0",
        format: "tube",
        uri: "geometry/geometry_element_pipe_0.json",
        bounds: [0, -0.1, -0.1, 1, 0.1, 0.1],
        object_ids: ["object:element:pipe_0"],
        generation_config: { entity_ref: "element:pipe_0", points: [[0, 0, 0], [1, 0, 0]] }
      }
    ],
    materials: [],
    styles: [],
    overlays: [],
    issues: [],
    route_reviews: [],
    agent_proposals: [],
    views: [],
    scene_diffs: [],
    diagnostics: []
  };
  await writeFile(join(root, "scene.json"), JSON.stringify(scene), "utf8");
  await writeFile(join(root, "metadata", "objects.json"), JSON.stringify(scene.objects), "utf8");
  await writeFile(join(root, "metadata", "object_map.json"), JSON.stringify({ "object:element:pipe_0": { entity_ref: "element:pipe_0" } }), "utf8");
  await writeFile(join(root, "metadata", "overlays.json"), "[]", "utf8");
  await writeFile(join(root, "geometry", "geometry_assets.json"), JSON.stringify(scene.geometry_assets), "utf8");
  await writeFile(join(root, "geometry", "geometry_element_pipe_0.json"), JSON.stringify({
    asset_id: "geometry:element:pipe_0",
    object_ids: ["object:element:pipe_0"],
    generation_config: { entity_ref: "element:pipe_0" }
  }), "utf8");
  return root;
}

test("loads scene bundle files and geometry payloads", async () => {
  const bundle = await loadSceneBundle(await createFixtureBundle());

  assert.equal(bundle.scene.scene_id, "scene_001");
  assert.equal(bundle.objects.length, 1);
  assert.equal(bundle.geometryPayloads.length, 1);
  assert.equal(bundle.geometryPayloads[0].asset_id, "geometry:element:pipe_0");
});

test("creates viewer state with visible layers and scene bounds", async () => {
  const bundle = await loadSceneBundle(await createFixtureBundle());

  const state = createViewerState(bundle);

  assert.deepEqual(state.bounds, [0, -0.1, -0.1, 1, 0.1, 0.1]);
  assert.equal(state.objectMap, bundle.objectMap);
  assert.equal(state.layers.pipe.visible, true);
  assert.deepEqual(state.visibleObjectIds, ["object:element:pipe_0"]);
});

test("opens an unsolved mesh review with design and analysis mesh visible", () => {
  const scene = {
    scene_id: "scene:gmsh-mesh",
    model_id: "model:tee",
    publication_status: "mesh_only_unsolved",
    objects: [
      { id: "object:design", kind: "pipe", layer_ids: ["design:pipes"] },
      { id: "object:mesh", kind: "analysis_mesh_surface", layer_ids: ["analysis_mesh:volume_skin"] }
    ],
    geometry_assets: [],
    overlays: [],
    layers: [
      { id: "design:pipes", category: "design", default_visible: true },
      { id: "analysis_mesh:volume_skin", category: "analysis_mesh", default_visible: true }
    ],
    result_fields: [],
    diagnostics: []
  };

  const state = createViewerState({ scene, objectMap: {}, geometryPayloads: [] });

  assert.deepEqual(state.visibleObjectIds, ["object:design", "object:mesh"]);
  assert.deepEqual(state.resultFields, []);
});

test("opens solved scenes on the physical engineering state", () => {
  const geometryStates = [
    {
      id: "overlay:geometry:physical",
      kind: "geometry_state",
      data: {
        id: "geometry_state:Operating:physical",
        load_case: "Operating",
        purpose: "engineering",
        displacement_scale: 1
      }
    },
    {
      id: "overlay:geometry:visual",
      kind: "geometry_state",
      data: {
        id: "geometry_state:Operating:visual_x40",
        load_case: "Operating",
        purpose: "visualization",
        displacement_scale: 40
      }
    }
  ];
  const scene = {
    scene_id: "scene:solved",
    model_id: "model:solved",
    objects: [],
    geometry_assets: [],
    overlays: [
      {
        id: "overlay:result:Operating",
        kind: "result_state",
        data: { id: "result_state:Operating", load_case: "Operating" }
      },
      ...geometryStates
    ]
  };

  const state = createViewerState({ scene, objects: [], overlays: scene.overlays, geometryAssets: [], geometryPayloads: [] });

  assert.equal(state.activeGeometryStateId, "geometry_state:Operating:physical");
  assert.equal(state.visualDeformationScale, 1);
});

test("loads scene files before the optional review and exposes review state", async () => {
  const fixtureRoot = new URL("./fixtures/code_aster_results/", import.meta.url);
  const fixturePaths = [
    "scene.json",
    "metadata/objects.json",
    "metadata/object_map.json",
    "metadata/overlays.json",
    "geometry/geometry_assets.json",
    "review.json"
  ];
  const fixtureFiles = Object.fromEntries(
    await Promise.all(
      fixturePaths.map(async (path) => [path, await readFile(new URL(path, fixtureRoot), "utf8")])
    )
  );
  const requestedUrls = [];
  const fetcher = async (url) => {
    requestedUrls.push(url);
    const relativePath = url.replace(/^\/bundle\//, "");
    return relativePath in fixtureFiles
      ? new Response(fixtureFiles[relativePath], { status: 200 })
      : new Response("", { status: 404 });
  };

  const bundle = await loadSceneBundleFromUrl("/bundle", fetcher);
  const state = createViewerState(bundle);

  assert.equal(requestedUrls.at(-1), "/bundle/review.json");
  assert.equal(requestedUrls.includes("/bundle/metadata/objects.json"), false);
  assert.equal(requestedUrls.includes("/bundle/metadata/overlays.json"), false);
  assert.equal(requestedUrls.includes("/bundle/geometry/geometry_assets.json"), false);
  assert.equal(bundle.review.analysis_status, "solved");
  assert.deepEqual(bundle.reviewDiagnostics, []);
  assert.equal(bundle.legacyReview, false);
  assert.equal(state.review, bundle.review);
  assert.deepEqual(state.reviewDiagnostics, []);
  assert.equal(state.legacyReview, false);
  assert.equal(state.sceneId, "scene:code_aster_results");
  assert.equal(state.activeLoadCase, "Hot");
});

test("reports the requested URL when a scene JSON request receives HTML", async () => {
  const fetcher = async () =>
    new Response("<!doctype html><title>Wrong application</title>", {
      status: 200,
      headers: { "content-type": "text/html; charset=utf-8" }
    });

  await assert.rejects(
    loadSceneBundleFromUrl("http://127.0.0.1:5173/code-aster-review", fetcher),
    /Expected JSON from http:\/\/127\.0\.0\.1:5173\/code-aster-review\/scene\.json, but received text\/html.*different application or server/s
  );
});

test("starts URL geometry requests concurrently and preserves asset order", async () => {
  const assets = ["geometry:first", "geometry:second", "geometry:third"].map((id) => ({
    id,
    uri: `${id.replace(":", "_")}.json`
  }));
  const basePayloads = {
    "scene.json": { schema_version: "visualization.scene.v1", scene_id: "concurrent", geometry_assets: assets },
    "metadata/objects.json": [],
    "metadata/object_map.json": {},
    "metadata/overlays.json": [],
    "geometry/geometry_assets.json": assets,
    "review.json": { schema_version: "engineering_review.v1", analysis_status: "solved", tables: [] }
  };
  const geometryResolvers = new Map();
  const geometryRequests = [];
  const fetcher = async (url) => {
    const relativePath = url.replace(/^\/concurrent\//, "");
    if (relativePath in basePayloads) {
      return new Response(JSON.stringify(basePayloads[relativePath]), { status: 200 });
    }
    geometryRequests.push(relativePath);
    return new Promise((resolve) => geometryResolvers.set(relativePath, resolve));
  };

  const loading = loadSceneBundleFromUrl("/concurrent", fetcher);
  await new Promise((resolve) => setImmediate(resolve));

  assert.deepEqual(geometryRequests, ["geometry_first.json", "geometry_second.json", "geometry_third.json"]);
  for (const relativePath of [...geometryRequests].reverse()) {
    geometryResolvers.get(relativePath)(
      new Response(JSON.stringify({ asset_id: relativePath.replace("geometry_", "geometry:").replace(".json", "") }), {
        status: 200
      })
    );
  }
  const bundle = await loading;

  assert.deepEqual(bundle.geometryPayloads.map((payload) => payload.asset_id), [
    "geometry:first",
    "geometry:second",
    "geometry:third"
  ]);
});

test("updates layer visibility without mutating prior state", async () => {
  const bundle = await loadSceneBundle(await createFixtureBundle());
  const state = createViewerState(bundle);

  const next = setLayerVisibility(state, "pipe", false);

  assert.equal(state.layers.pipe.visible, true);
  assert.equal(next.layers.pipe.visible, false);
  assert.deepEqual(next.visibleObjectIds, []);
});

test("categoryForLayerId prefers the category the scene declares", () => {
  // The builders state the category outright; the id is not consulted.
  assert.equal(categoryForLayerId("anything:at:all", "design"), "design");
  assert.equal(categoryForLayerId("pipe", "annotations"), "annotations");
  // A category the viewer does not know falls back to the id rules.
  assert.equal(categoryForLayerId("analysis_mesh:nodes", "not_a_category"), "analysis_mesh");
});

test("categoryForLayerId falls back to legacy prefixes, remapped onto four categories", () => {
  assert.equal(categoryForLayerId("pipe"), "design");
  assert.equal(categoryForLayerId("imported_components"), "design");
  assert.equal(categoryForLayerId("physical_envelope:insulation"), "design");
  assert.equal(categoryForLayerId("overlay:physical_envelope"), "design");
  assert.equal(categoryForLayerId("analysis_mesh:nodes"), "analysis_mesh");
  assert.equal(categoryForLayerId("analysis_mesh:group:GN_N0"), "analysis_mesh");
  assert.equal(categoryForLayerId("result:reaction"), "results");
  assert.equal(categoryForLayerId("solver_result:tuyau_subpoints"), "results");
  assert.equal(categoryForLayerId("deformed:mesh"), "results");
  assert.equal(categoryForLayerId("overlay:solver_result"), "results");
  assert.equal(categoryForLayerId("overlay:clash"), "annotations");
  assert.equal(categoryForLayerId("weird:namespace"), "annotations");
});

test("legacyCategoryForLayerId still reports the pre-restructure taxonomy", () => {
  assert.equal(legacyCategoryForLayerId("physical_envelope:insulation"), "envelopes");
  assert.equal(legacyCategoryForLayerId("overlay:clash"), "overlays");
  assert.equal(legacyCategoryForLayerId("weird:namespace"), "other");
});

test("categorizeLayers folds envelopes into Design", () => {
  const layers = {
    "physical_envelope:insulation": { id: "physical_envelope:insulation", count: 3 },
    "overlay:physical_envelope": { id: "overlay:physical_envelope", count: 1, source: "overlay" }
  };
  const categories = categorizeLayers(layers);
  const design = categories.find((category) => category.id === "design");
  assert.ok(design, "design category is present");
  assert.ok(design.layerIds.includes("physical_envelope:insulation"));
  assert.ok(design.layerIds.includes("overlay:physical_envelope"));
});

test("metadata-only layers surface as category identity, not as a toggle", () => {
  const layers = {
    "analysis_mesh:nodes": { id: "analysis_mesh:nodes", category: "analysis_mesh", count: 12, source: "object" },
    "analysis_mesh:identity:m1": {
      id: "analysis_mesh:identity:m1",
      category: "analysis_mesh",
      count: 0,
      source: "scene",
      visible: false,
      meshIdentity: { modelisations: [{ modelisation: "TUYAU_3M", topological_dim: 1, result_support: "subpoint" }] }
    }
  };
  const mesh = categorizeLayers(layers).find((category) => category.id === "analysis_mesh");
  // It must not gate the master switch, or a never-visible metadata row would
  // hold the category permanently indeterminate.
  assert.deepEqual(mesh.layerIds, ["analysis_mesh:nodes"]);
  assert.deepEqual(mesh.leaves, [{ layerId: "analysis_mesh:nodes", label: "Nodes", count: 12 }]);
  assert.equal(mesh.meshIdentity.modelisations[0].modelisation, "TUYAU_3M");
});

test("categories without mesh identity report none", () => {
  const categories = categorizeLayers({ pipe: { id: "pipe", category: "design", count: 1, source: "object" } });
  assert.equal(categories[0].meshIdentity, null);
});

test("createViewerState reads declared layers and the field catalogue", () => {
  const scene = {
    scene_id: "s",
    model_id: "m",
    objects: [{ id: "o1", kind: "applied_load", layer_ids: ["design:loads"] }],
    overlays: [{ id: "overlay:solver_result:stress:Hot", kind: "solver_result", data: { values: { o1: 5 } } }],
    geometry_assets: [],
    layers: [
      { id: "design:loads", category: "design", label: "Loads" },
      { id: "overlay:solver_result", category: "results", label: "Solver result" }
    ],
    result_fields: [
      {
        id: "field:stress",
        label: "VMIS",
        load_case: "Hot",
        result_state_id: "rs",
        overlay_id: "overlay:solver_result:stress:Hot",
        support: "cell",
        components: ["magnitude"]
      }
    ]
  };
  const state = createViewerState({ scene, objects: scene.objects, overlays: scene.overlays, geometryAssets: [], geometryPayloads: [] });
  assert.equal(state.layers["design:loads"].category, "design");
  assert.equal(state.layers["overlay:solver_result"].category, "results");
  assert.equal(state.resultFields.length, 1);
  assert.equal(state.coloring.fieldId, "field:stress");
  assert.equal(state.coloring.loadCase, "Hot");
});

test("createViewerState on a legacy scene has no fields and empty coloring", () => {
  const scene = {
    scene_id: "s",
    model_id: "m",
    objects: [{ id: "o1", kind: "pipe" }],
    overlays: [],
    geometry_assets: []
  };
  const state = createViewerState({ scene, objects: scene.objects, overlays: [], geometryAssets: [], geometryPayloads: [] });
  assert.deepEqual(state.resultFields, []);
  assert.equal(state.coloring.fieldId, null);
  // Legacy ids still land in a real category rather than an "other" bin.
  assert.equal(categorizeLayers(state.layers)[0].id, "design");
});

test("categorizeLayers honours declared categories over id prefixes", () => {
  const layers = {
    "design:loads": { id: "design:loads", category: "design", count: 2 },
    pipe: { id: "pipe", category: "design", count: 4 },
    "overlay:load_case": { id: "overlay:load_case", category: "design", count: 1, source: "overlay" }
  };
  const categories = categorizeLayers(layers);
  assert.deepEqual(categories.map((category) => category.id), ["design"]);
  assert.deepEqual(categories[0].layerIds.sort(), ["design:loads", "overlay:load_case", "pipe"]);
});

test("categorizeLayers puts both vector gates under the Results category", () => {
  const layers = {
    "result:reaction": { id: "result:reaction", count: 7 },
    "overlay:solver_result": { id: "overlay:solver_result", count: 1, source: "overlay" }
  };
  const categories = categorizeLayers(layers);
  const results = categories.find((category) => category.id === "results");
  assert.ok(results, "results category is present");
  assert.ok(results.layerIds.includes("result:reaction"));
  assert.ok(results.layerIds.includes("overlay:solver_result"));
});

test("categorizeLayers orders categories and collapses mesh groups", () => {
  const layers = {
    pipe: { id: "pipe", label: "Pipe", visible: true, count: 105, source: "object" },
    "analysis_mesh:nodes": { id: "analysis_mesh:nodes", label: "Analysis Mesh Nodes", visible: true, count: 71, source: "object" },
    "analysis_mesh:group:GN_N0": { id: "analysis_mesh:group:GN_N0", label: "Analysis Mesh Group GN N0", visible: true, count: 1, source: "object" },
    "analysis_mesh:group:MAT_Steel": { id: "analysis_mesh:group:MAT_Steel", label: "Analysis Mesh Group MAT Steel", visible: true, count: 105, source: "object" },
    "overlay:clash": { id: "overlay:clash", label: "Overlay Clash", visible: true, count: 2, source: "overlay", overlayKind: "clash" }
  };

  const categories = categorizeLayers(layers);
  assert.deepEqual(categories.map((category) => category.id), ["design", "analysis_mesh", "annotations"]);

  const design = categories.find((category) => category.id === "design");
  assert.deepEqual(design.layerIds, ["pipe"]);
  assert.deepEqual(design.leaves, [{ layerId: "pipe", label: "Pipe", count: 105 }]);
  assert.deepEqual(design.groups, []);

  const mesh = categories.find((category) => category.id === "analysis_mesh");
  assert.deepEqual(mesh.layerIds, ["analysis_mesh:nodes", "analysis_mesh:group:GN_N0", "analysis_mesh:group:MAT_Steel"]);
  assert.deepEqual(mesh.leaves, [{ layerId: "analysis_mesh:nodes", label: "Nodes", count: 71 }]);
  assert.equal(mesh.groups.length, 1);
  assert.equal(mesh.groups[0].label, "Groups");
  assert.deepEqual(mesh.groups[0].leaves, [
    { layerId: "analysis_mesh:group:GN_N0", label: "GN N0", count: 1 },
    { layerId: "analysis_mesh:group:MAT_Steel", label: "MAT Steel", count: 105 }
  ]);
});

test("categorizeLayers gives the support layer its engineering label", () => {
  const categories = categorizeLayers({
    support: {
      id: "support",
      category: "design",
      label: "Support",
      visible: true,
      count: 4,
      source: "object",
      objectIds: []
    }
  });

  assert.deepEqual(categories[0].leaves, [
    { layerId: "support", label: "Supports / constraints", count: 4 }
  ]);
});

test("applyTaskVisibilityPreset toggles categories to match the task preset", () => {
  const layers = {
    pipe: { id: "pipe", label: "Pipe", visible: true, count: 3, source: "object", objectIds: [] },
    "analysis_mesh:nodes": { id: "analysis_mesh:nodes", label: "Nodes", visible: true, count: 5, source: "object", objectIds: [] },
    "overlay:clash": { id: "overlay:clash", label: "Overlay Clash", visible: true, count: 1, source: "overlay", overlayKind: "clash", overlayIds: [] }
  };
  const state = { objects: [], overlays: [], hiddenObjectIds: [], isolatedObjectIds: [], geometryAssets: [], layers };

  const modelState = applyTaskVisibilityPreset(state, "model");
  assert.equal(modelState.layers.pipe.visible, true);
  assert.equal(modelState.layers["analysis_mesh:nodes"].visible, false);
  assert.equal(modelState.layers["overlay:clash"].visible, false);

  const resultsState = applyTaskVisibilityPreset(modelState, "results");
  assert.equal(resultsState.layers["overlay:clash"].visible, true);
  assert.equal(resultsState.layers["analysis_mesh:nodes"].visible, false);

  assert.equal(applyTaskVisibilityPreset(state, "3d"), state);
});

test("task presets keep scene-declared analytical layers hidden", () => {
  const layers = {
    pipe: { id: "pipe", category: "design", visible: true, defaultVisible: true, count: 1, source: "object", objectIds: [] },
    "physical_envelope:clearance": {
      id: "physical_envelope:clearance",
      category: "design",
      visible: false,
      defaultVisible: false,
      count: 1,
      source: "object",
      objectIds: []
    }
  };
  const state = { objects: [], overlays: [], hiddenObjectIds: [], isolatedObjectIds: [], geometryAssets: [], layers };

  const resultsState = applyTaskVisibilityPreset(state, "results");

  assert.equal(resultsState.layers.pipe.visible, true);
  assert.equal(resultsState.layers["physical_envelope:clearance"].visible, false);
});

test("scene loader carries the authoring script uri into viewer state", async () => {
  const bundle = await loadSceneBundle(await createFixtureBundle());
  bundle.scene.source_uri = "source.py";

  assert.equal(createViewerState(bundle).sourceUri, "source.py");
});

test("scene loader reports no authoring script when the bundle omits one", async () => {
  const bundle = await loadSceneBundle(await createFixtureBundle());

  assert.equal(createViewerState(bundle).sourceUri, null);
});
