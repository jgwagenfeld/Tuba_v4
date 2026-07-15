import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { getReviewEntityAction, resolveEntityObjectId, showReviewEntityIn3d } from "../src/reviewSelection.js";

function reviewState() {
  const review = { schema_version: "engineering_review.v1", analysis_status: "solved" };
  const overlays = [{ id: "overlay:stress", visible: true }];
  return {
    activeTab: "results",
    activeLoadCase: "Hot",
    activeResultStateId: "result_state:Hot",
    activeGeometryStateId: "geometry_state:Hot:physical",
    activeOverlayIds: ["overlay:stress"],
    visibleOverlayIds: ["overlay:stress"],
    displacementVectorScale: 2,
    reactionVectorScale: 3,
    resultThreshold: 10,
    utilizationThreshold: 0.9,
    visualDeformationScale: 50,
    hiddenObjectIds: ["object:hidden"],
    isolatedObjectIds: [],
    visibleObjectIds: ["object:pipe", "object:deformed", "object:displacement", "object:mapped", "object:support-marker"],
    issueReviewState: { "issue:review": { status: "reviewing", comment: "Keep" } },
    embed: false,
    review,
    overlays,
    camera: { mode: "orbit", target: [99, 99, 99], distance: 99 },
    selectedObjectIds: [],
    objects: [
      {
        id: "object:pipe",
        entity_ref: "element:pipe_0",
        kind: "pipe",
        geometry_asset_id: "asset:pipe"
      },
      {
        id: "object:deformed",
        entity_ref: "element:pipe_0",
        kind: "deformed_centerline",
        geometry_asset_id: "asset:deformed"
      },
      {
        id: "object:displacement",
        entity_ref: "node:N2",
        kind: "displacement_vector",
        geometry_asset_id: "asset:displacement"
      },
      {
        id: "object:mapped",
        kind: "result_marker",
        geometry_asset_id: "asset:mapped"
      },
      {
        id: "object:support-marker",
        kind: "support_marker",
        geometry_asset_id: "asset:support-marker",
        metadata: { entity_ref: "support:S0" }
      },
      { id: "object:hidden", entity_ref: "element:hidden", kind: "pipe", geometry_asset_id: "asset:hidden" }
    ],
    objectMap: {
      "element:pipe_0": "object:pipe",
      "element:mapped": "object:mapped",
      "object:support-marker": { entity_ref: "support:S0" }
    },
    geometryAssets: [
      { id: "asset:pipe", bounds: [0, -0.1, -0.1, 2, 0.1, 0.1], object_ids: ["object:pipe"] },
      { id: "asset:deformed", bounds: [0, -0.2, -0.2, 2, 0.2, 0.2], object_ids: ["object:deformed"] },
      { id: "asset:displacement", bounds: [2, 0, 0, 3, 0, 0], object_ids: ["object:displacement"] },
      { id: "asset:mapped", bounds: [4, 0, 0, 4, 0, 0], object_ids: ["object:mapped"] },
      { id: "asset:support-marker", bounds: [5, 0, 0, 5, 0, 0], object_ids: ["object:support-marker"] },
      { id: "asset:hidden", bounds: [6, 0, 0, 7, 0, 0], object_ids: ["object:hidden"] }
    ]
  };
}

test("resolves direct scene object ids and canonical entity refs", () => {
  const state = reviewState();

  assert.equal(resolveEntityObjectId(state, "object:deformed"), "object:deformed");
  assert.equal(resolveEntityObjectId(state, "element:pipe_0"), "object:pipe");
});

test("resolves object-map fallbacks and metadata entity refs", () => {
  const state = reviewState();

  assert.equal(resolveEntityObjectId(state, "element:mapped"), "object:mapped");
  assert.equal(resolveEntityObjectId(state, "support:S0"), "object:support-marker");
});

test("resolves nodes represented only by result vectors", () => {
  assert.equal(resolveEntityObjectId(reviewState(), "node:N2"), "object:displacement");
});

test("returns null for unresolved report entity refs", () => {
  assert.equal(resolveEntityObjectId(reviewState(), "element:missing"), null);
  assert.equal(resolveEntityObjectId(reviewState(), ""), null);
  assert.equal(resolveEntityObjectId(reviewState(), null), null);
});

test("describes accessible actions only for resolvable report rows", () => {
  const state = reviewState();

  assert.deepEqual(getReviewEntityAction(state, "element:pipe_0"), {
    entityRef: "element:pipe_0",
    objectId: "object:pipe",
    accessibleName: "Show element:pipe_0 in 3D"
  });
  assert.equal(getReviewEntityAction(state, "element:missing"), null);
});

test("show in 3d selects, fits, and preserves the full review context", () => {
  const state = reviewState();

  const next = showReviewEntityIn3d(state, "element:pipe_0");

  assert.equal(next.activeTab, "3d");
  assert.deepEqual(next.selectedObjectIds, ["object:pipe"]);
  assert.notDeepEqual(next.camera, state.camera);
  assert.deepEqual(next.camera.target, [1, 0, 0]);
  for (const key of [
    "activeLoadCase",
    "activeResultStateId",
    "activeGeometryStateId",
    "activeOverlayIds",
    "visibleOverlayIds",
    "displacementVectorScale",
    "reactionVectorScale",
    "resultThreshold",
    "utilizationThreshold",
    "visualDeformationScale",
    "hiddenObjectIds",
    "isolatedObjectIds",
    "visibleObjectIds",
    "issueReviewState",
    "embed",
    "review",
    "overlays"
  ]) {
    assert.equal(next[key], state[key], `${key} must be preserved`);
  }
});

test("show in 3d returns the identical state for unresolved refs", () => {
  const state = reviewState();

  assert.equal(showReviewEntityIn3d(state, "element:missing"), state);
});

test("browser review rows wire resolvable actions through the selection bridge", async () => {
  const app = await readFile(new URL("../src/app.js", import.meta.url), "utf8");

  assert.match(app, /from ["']\.\/reviewSelection\.js["']/);
  assert.match(app, /getReviewEntityAction\(currentState, row\.entityRef\)/);
  assert.match(app, /showReviewEntityIn3d\(currentState, entityRef\)/);
  assert.match(app, /setAttribute\(["']aria-label["'], action\.accessibleName\)/);
  assert.match(app, /No 3D object is available for/);
});
