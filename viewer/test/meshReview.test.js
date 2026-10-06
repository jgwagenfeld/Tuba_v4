import test from "node:test";
import assert from "node:assert/strict";
import { meshReviewViewModel, meshToggleViewModel, measurementLabel, renderMeshReview } from "../src/meshReview.js";
import { selectionKey, relatedSelectionIds } from "../src/reviewSelection.js";

const review = {
  schema: "tuba.mesh-review.v1",
  policy: { global_size_m: .02, refinements: [{ id: "outlet", target: "element:P1", size_m: .004, influence_distance_m: 0, transition_distance_m: .02 }] },
  statistics: { node_count: 12, cell_count: 3, by_family: { HEXA20: 3 } },
  quality: { metrics: [{ metric: "minSJ", applicable_family: "HEXA20", minimum: .08, diagnostic_threshold: .1 }], invalid_count: 0, poor_count: 1, problem_locations: [{ cell_id: "VM1", source_ref: "element:P1", bounds_m: [0,0,0,.1,.1,.1] }] },
  size_preview: { units: "m", sample_count: 3, sampling: "bounded samples" }
};
const scene = { layers: [{ extra: { mesh_identity: { mesh_id: "mesh", mesh_review: review } } }] };

test("sizing legend distinguishes samples from nodes and handles a single requested size", () => {
  for (const sizes of [[.005,.65], [.02,.02]]) {
    const created = [];
    const document = { createElement() {
      const node = { dataset:{}, children:[], append(...children) { this.children.push(...children); } };
      created.push(node);
      return node;
    } };
    const root = { ownerDocument:document, dataset:{}, replaceChildren(){}, append(){},
      querySelector(selector) { return created.find(node => node.className === selector.slice(1)); } };
    renderMeshReview(root, { layers:[{mesh_identity:{mesh_review:{schema:review.schema,
      size_preview:{samples:sizes.map(size_m => ({size_m})),sample_count:2}}}}] });
    const legend = root.querySelector(".mesh-size-legend");
    assert.equal(legend.dataset.uniform, String(sizes[0] === sizes[1]));
    assert.equal(legend.children[0].textContent, "Requested element size");
    assert.deepEqual(legend.children[1].children.map(node => node.textContent), sizes[0] === sizes[1]
      ? ["0.02 m"] : ["Finer · 0.005 m", "Coarser · 0.65 m"]);
    assert.match(legend.children[2].textContent, /sizing samples, not FE nodes/);
  }
});

test("comparison metadata cannot hide effective sizing preview", () => {
  const authored = { ...review, statistics:undefined, quality:undefined,
    policy:{global_size_m:.1, invocation_max_element_size_m:.005},
    size_preview:{sample_count:17,samples:[{size_m:.005}]} };
  const vm = meshReviewViewModel({layers:[
    {mesh_identity:{mesh_review:{schema:review.schema,policy:{global_size_m:.1},comparison:{levels:[]}}}},
    {mesh_identity:{mesh_review:authored}}]});
  assert.equal(vm.invocationSize,"0.005 m");
  assert.equal(vm.previewCount,17);
  assert.deepEqual(vm.previewRange,[.005,.005]);
});

test("unsupported runtime disables convergence and blocked cleanup is retryable", () => {
  const native={available:true,sourceCurrent:true,job:{state:"cancelled",id:"named",busy:true,
    cleanup_pending:true,convergence_config:{scales:[1,.5]},
    convergence_capability:{supported:false,reason:"Configure Linux Python bridge"}}};
  const vm=meshReviewViewModel(scene,native);
  assert.equal(vm.canConverge,false);
  assert.equal(vm.canGenerate,false);
  assert.equal(vm.canCancel,true);
  assert.equal(vm.cleanupPending,true);
  assert.equal(vm.capabilityReason,"Configure Linux Python bridge");
});

test("compact measurement labels retain distinct stress supports", () => {
  assert.equal(measurementLabel({quantity:"displacement"}), "Displacement · FE nodes");
  assert.equal(measurementLabel({quantity:"von_mises",support:"TUYAU through-wall/circumferential subpoints"}), "Von Mises · TUYAU subpoints");
  assert.equal(measurementLabel({quantity:"von_mises",support:"adjacent-element averaged surface nodes"}), "Von Mises · solid surface nodes");
  assert.equal(measurementLabel({quantity:"von_mises",support:"shell through-thickness subpoint maxima"}), "Von Mises · shell thickness");
});

test("convergence is Python configured and completion is separate from tolerance", () => {
  const comparison = { status:"completed", distinct_successful_meshes:2, all_available_changes_within_tolerance:false,
    levels:[{scale:1,status:"succeeded",mesh:{node_count:3,cell_count:1},measurements:[]}], accuracy_notice:"Not a certificate" };
  const native = { available:true, sourceCurrent:true, job:{state:"succeeded",mode:"convergence",current:true,convergence_config:{scales:[1,.5]},comparison} };
  const vm = meshReviewViewModel(scene,native);
  assert.equal(vm.canConverge,true);
  assert.equal(vm.comparison.all_available_changes_within_tolerance,false);
  assert.match(vm.notice,/Completed Code_Aster/);
  assert.equal(meshReviewViewModel(scene,{...native,sourceCurrent:false}).canConverge,false);
  assert.equal(meshReviewViewModel(scene,{...native,job:{...native.job,state:"stale",current:false}}).comparison,null);
  const staticScene = {layers:[{mesh_identity:{mesh_review:{...review,comparison}}}]};
  assert.equal(meshReviewViewModel(staticScene).comparison,comparison);
  assert.equal(meshReviewViewModel(staticScene).canConverge,false);
});

test("authored sizes, measured counts and unavailable quantities are explicit", () => {
  const vm = meshReviewViewModel(scene);
  assert.equal(vm.globalSize, "0.02 m");
  assert.equal(vm.refinements[0].size, "0.004 m");
  assert.equal(vm.statistics, "12 nodes · 3 cells · 3 HEXA20");
  assert.match(vm.notice, /unsolved/i);
  assert.match(vm.qualityNotice, /accuracy|compliance/i);
  assert.deepEqual(vm.metrics[0].values, ["0.08", "Unavailable", "Unavailable", "Unavailable"]);
  assert.equal(vm.metrics[0].label, "Scaled Jacobian (minSJ)");
  assert.equal(vm.metrics[0].threshold, "0.1");
  assert.equal(meshReviewViewModel({ layers:[{ mesh_identity:{ mesh_review:review, display_representation:"triangulated_surface" } }] }).surfaceNotice,
    "Surface display uses triangles; cell counts describe the actual analysis element families.");
  assert.equal(meshReviewViewModel({ layers: [] }).visible, false);
});

test("job stages and native controls reflect actual source/worker state", () => {
  assert.equal(meshReviewViewModel(scene, { available: true, sourceCurrent: true, job: { state: "running", stage: "generating", id: "one", elapsed_seconds: 1.2 } }).canCancel, true);
  assert.equal(meshReviewViewModel(scene, { available: true, sourceCurrent: true, job: { state: "running" } }).canGenerate, false);
  assert.equal(meshReviewViewModel(scene, { available: true, sourceCurrent: false }).canGenerate, false);
  assert.equal(meshReviewViewModel(scene).nativeActions, false);
  const stale = meshReviewViewModel(scene, { available: true, sourceCurrent: true, job: { state: "stale", current: false } });
  assert.match(stale.status, /outdated/i);
  assert.equal(stale.statistics, "Unavailable until generation");
  assert.equal(meshReviewViewModel(scene, { available: true, sourceCurrent: true, solving: true }).canGenerate, false);
});

test("poor-cell marker retains exact identity and source provenance", () => {
  const marker = { id: "object:mesh_problem:mesh:VM1", kind: "mesh_problem", metadata: { source_ref: "element:P1" } };
  const pipe = { id: "object:element:P1", kind: "pipe", entity_ref: "element:P1" };
  assert.equal(selectionKey(marker), marker.id);
  assert.deepEqual(relatedSelectionIds({ objects: [pipe, marker] }, [marker.id]), [marker.id]);
});

test("the Build Mesh button makes the mesh when there is none and toggles it once there is", () => {
  const studio = { available: true, sourceCurrent: true, solving: false };
  const body = { id: "analysis_mesh", visible: false };
  assert.equal(meshToggleViewModel(null, { ...studio, job: { state: "idle" } }).action, "generate");
  assert.equal(meshToggleViewModel(null, { ...studio, job: { state: "idle" } }).label, "Mesh · generate");
  const running = meshToggleViewModel(null, { ...studio, job: { state: "running", mode: "mesh", elapsed_seconds: 11.6, busy: true } });
  assert.deepEqual([running.label, running.disabled], ["Meshing · 12 s", true]);
  assert.equal(meshToggleViewModel(body, { ...studio, job: { state: "succeeded", mesh_current: true } }).action, "toggle");
  assert.equal(meshToggleViewModel(null, { ...studio, job: { state: "succeeded", mesh_current: true } }).label, "Mesh · loading");
  assert.equal(meshToggleViewModel(null, { ...studio, job: { state: "stale" } }).label, "Mesh · outdated");
  assert.equal(meshToggleViewModel(null, { ...studio, solving: true, job: { state: "idle" } }).label, "Mesh · waiting for solve");
  assert.equal(meshToggleViewModel(null, { ...studio, sourceCurrent: false, job: { state: "idle" } }).label, "Mesh · run Python first");
  // A current mesh stays viewable while a solve runs.
  assert.equal(meshToggleViewModel(body, { ...studio, solving: true, job: { mesh_current: true } }).action, "toggle");
  // A published bundle ships its mesh: plain toggle, or no button at all.
  assert.equal(meshToggleViewModel(body, { available: false }).action, "toggle");
  assert.equal(meshToggleViewModel(null, { available: false }).hidden, true);
});
