import assert from "node:assert/strict";
import test from "node:test";

import {
  getGeometryStateOptions,
  getHotspots,
  getLoadCaseOptions,
  getObjectScalarColor,
  getScalarLegend,
  getSolverResultOverlays,
  setActiveGeometryState,
  setActiveLoadCase,
  setActiveResultState,
  setResultThreshold,
  setResultVectorScale,
  setUtilizationThreshold,
  setVisualDeformationScale
} from "../src/resultReview.js";
import { createViewerState } from "../src/sceneLoader.js";

function resultState() {
  return createViewerState({
    scene: {
      schema_version: "visualization.scene.v1",
      scene_id: "scene:result-review",
      model_id: "model:result-review",
      objects: [
        { id: "object:pipe:cold", kind: "pipe", name: "Cold pipe", geometry_asset_id: "asset:cold" },
        { id: "object:pipe:hot", kind: "pipe", name: "Hot pipe", geometry_asset_id: "asset:hot" },
        { id: "object:clash", kind: "clash_marker", name: "Operating clash", geometry_asset_id: "asset:clash" }
      ],
      geometry_assets: [
        { id: "asset:cold", format: "tube", bounds: [0, 0, 0, 1, 0.1, 0.1], object_ids: ["object:pipe:cold"], generation_config: {} },
        { id: "asset:hot", format: "tube", bounds: [0, 1, 0, 1, 1.1, 0.1], object_ids: ["object:pipe:hot"], generation_config: {} },
        { id: "asset:clash", format: "marker", bounds: [0.5, 0.5, 0, 0.5, 0.5, 0], object_ids: ["object:clash"], generation_config: {} }
      ],
      overlays: [
        {
          id: "overlay:result_state:Hot",
          kind: "result_state",
          name: "Result state Hot",
          data: { id: "result_state:Hot", load_case: "Hot", solver_name: "code_aster" }
        },
        {
          id: "overlay:stress:Hot",
          kind: "solver_result",
          name: "Stress Hot",
          object_ids: ["object:pipe:cold", "object:pipe:hot"],
          data: {
            result_type: "stress",
            result_state_id: "result_state:Hot",
            load_case: "Hot",
            field: "max_von_mises",
            unit: "Pa",
            values: { "object:pipe:cold": 6000000, "object:pipe:hot": 57000000 },
            utilization_values: { "object:pipe:cold": 0.2, "object:pipe:hot": 0.95 },
            range: { min: 6000000, max: 57000000 },
            legend: {
              field: "max_von_mises",
              unit: "Pa",
              range: { min: 6000000, max: 57000000 },
              thresholds: { warning: 0.8, critical: 1.0 }
            },
            hotspots: [
              { object_id: "object:pipe:hot", value: 57000000, utilization: 0.95, unit: "Pa" },
              { object_id: "object:pipe:cold", value: 6000000, utilization: 0.2, unit: "Pa" }
            ]
          }
        },
        {
          id: "overlay:displacement:Hot",
          kind: "solver_result",
          data: { result_type: "displacement", result_state_id: "result_state:Hot", load_case: "Hot", vectors: [] }
        },
        {
          id: "overlay:reaction:Hot",
          kind: "solver_result",
          data: { result_type: "reaction", result_state_id: "result_state:Hot", load_case: "Hot", vectors: [] }
        }
      ],
      issues: [
        {
          id: "issue:clash",
          type: "clash",
          title: "Operating clash",
          severity: "error",
          status: "open",
          metadata: { cold_distance_m: 0.12, operating_distance_m: 0.04 }
        }
      ],
      views: [],
      diagnostics: []
    }
  });
}

test("result review derives load cases scalar legend and filtered hotspots", () => {
  const state = setUtilizationThreshold(setResultThreshold(resultState(), 50000000), 0.8);

  assert.deepEqual(getLoadCaseOptions(state).map((option) => option.id), ["Hot"]);
  assert.equal(getSolverResultOverlays(state, "displacement").length, 1);
  assert.equal(getScalarLegend(state).field, "max_von_mises");
  assert.deepEqual(getHotspots(state).map((hotspot) => hotspot.objectId), ["object:pipe:hot"]);
});

test("TUYAU hotspots preserve repeated-row identity", () => {
  const state = resultState();
  state.overlays.push({
    id: "overlay:tuyau:Hot",
    kind: "solver_result",
    data: {
      result_type: "tuyau_subpoints",
      result_state_id: "result_state:Hot",
      load_case: "Hot",
      values: { "object:tuyau": 84_000_000 },
      hotspots: [
        {
          object_id: "object:tuyau",
          element_id: "pipe_0",
          row_index: 9,
          subpoint_index: 4,
          value: 84_000_000,
          unit: "Pa"
        }
      ]
    }
  });

  assert.deepEqual(getHotspots(state)[0], {
    objectId: "object:tuyau",
    objectName: "object:tuyau",
    elementId: "pipe_0",
    rowIndex: 9,
    subpointIndex: 4,
    unit: "Pa",
    utilization: null,
    value: 84_000_000
  });
});

test("scalar color uses active solver result values", () => {
  const state = resultState();

  const coldColor = getObjectScalarColor(state, ["object:pipe:cold"]);
  const hotColor = getObjectScalarColor(state, ["object:pipe:hot"]);

  assert.ok(Number.isInteger(coldColor));
  assert.ok(Number.isInteger(hotColor));
  assert.notEqual(coldColor, hotColor);
});

test("visible TUYAU sub-point results own the scalar legend", () => {
  const state = resultState();
  state.overlays.push({
    id: "overlay:tuyau:Hot",
    kind: "solver_result",
    name: "TUYAU FE VMIS Hot",
    data: {
      result_type: "tuyau_subpoints",
      result_state_id: "result_state:Hot",
      load_case: "Hot",
      values: { "object:tuyau": 84000000 },
      legend: { field: "FE VMIS (not code stress)", unit: "Pa", range: { min: 42000000, max: 84000000 } }
    }
  });

  assert.equal(getScalarLegend(state).field, "FE VMIS (not code stress)");

  state.overlays.at(-1).visible = false;
  assert.equal(getScalarLegend(state).field, "max_von_mises");
});

test("visual deformation and vector display controls do not mutate clash issue metadata", () => {
  const state = resultState();
  const originalIssues = state.issues;

  const next = setVisualDeformationScale(
    setResultVectorScale(setResultVectorScale(setActiveLoadCase(state, "Hot"), "displacement", 12), "reaction", 0.25),
    80,
  );

  assert.equal(next.activeResultStateId, "result_state:Hot");
  assert.equal(next.resultVectorScales.displacement, 12);
  assert.equal(next.resultVectorScales.reaction, 0.25);
  assert.equal(next.visualDeformationScale, 80);
  assert.deepEqual(next.issues, originalIssues);
});

test("moving the deformation slider activates the visual state", () => {
  const state = {
    activeLoadCase: "Operating",
    activeGeometryStateId: "geometry_state:Operating:physical",
    visualDeformationScale: 1,
    geometryStates: [
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
    ]
  };

  const next = setVisualDeformationScale(state, 25);

  assert.equal(next.activeGeometryStateId, "geometry_state:Operating:visual_x40");
  assert.equal(next.visualDeformationScale, 25);
});

test("load case changes keep result and geometry states on the case while preserving deformation purpose", () => {
  const state = resultState();
  state.resultStates.push({
    id: "overlay:result_state:Cold",
    kind: "result_state",
    data: { id: "result_state:Cold", load_case: "Cold", solver_name: "code_aster" }
  });
  state.geometryStates = [
    { id: "overlay:geometry_state:Hot:physical", kind: "geometry_state", data: { id: "geometry_state:Hot:physical", load_case: "Hot", purpose: "engineering" } },
    { id: "overlay:geometry_state:Hot:visual", kind: "geometry_state", data: { id: "geometry_state:Hot:visual", load_case: "Hot", purpose: "visualization", visual_scale: 40 } },
    { id: "overlay:geometry_state:Cold:physical", kind: "geometry_state", data: { id: "geometry_state:Cold:physical", load_case: "Cold", purpose: "engineering" } },
    { id: "overlay:geometry_state:Cold:visual", kind: "geometry_state", data: { id: "geometry_state:Cold:visual", load_case: "Cold", purpose: "visualization", visual_scale: 25 } }
  ];

  const next = setActiveLoadCase(setActiveGeometryState(state, "geometry_state:Hot:visual"), "Cold");

  assert.equal(next.activeLoadCase, "Cold");
  assert.equal(next.activeResultStateId, "result_state:Cold");
  assert.equal(next.activeGeometryStateId, "geometry_state:Cold:visual");
  assert.deepEqual(getGeometryStateOptions(next).map((option) => option.id), [
    "geometry_state:Cold:physical",
    "geometry_state:Cold:visual"
  ]);
});

test("legacy result-state selection keeps result and geometry states on its load case", () => {
  const state = resultState();
  state.resultStates.push({
    id: "overlay:result_state:Cold",
    kind: "result_state",
    data: { id: "result_state:Cold", load_case: "Cold", solver_name: "code_aster" }
  });
  state.geometryStates = [
    { id: "overlay:geometry_state:Hot:visual", kind: "geometry_state", data: { id: "geometry_state:Hot:visual", load_case: "Hot", purpose: "visualization", visual_scale: 40 } },
    { id: "overlay:geometry_state:Cold:physical", kind: "geometry_state", data: { id: "geometry_state:Cold:physical", load_case: "Cold", purpose: "engineering" } },
    { id: "overlay:geometry_state:Cold:visual", kind: "geometry_state", data: { id: "geometry_state:Cold:visual", load_case: "Cold", purpose: "visualization", visual_scale: 25 } }
  ];

  const next = setActiveResultState(setActiveGeometryState(state, "geometry_state:Hot:visual"), "result_state:Cold");

  assert.equal(next.activeLoadCase, "Cold");
  assert.equal(next.activeResultStateId, "result_state:Cold");
  assert.equal(next.activeGeometryStateId, "geometry_state:Cold:visual");
});

test("load case selection uses the target case's first geometry state when the current purpose is missing", () => {
  const state = resultState();
  state.geometryStates = [
    { id: "overlay:geometry_state:Hot", kind: "geometry_state", data: { id: "geometry_state:Hot", load_case: "Hot" } },
    { id: "overlay:geometry_state:Cold:physical", kind: "geometry_state", data: { id: "geometry_state:Cold:physical", load_case: "Cold", purpose: "engineering" } },
    { id: "overlay:geometry_state:Cold", kind: "geometry_state", data: { id: "geometry_state:Cold", load_case: "Cold" } }
  ];

  const next = setActiveLoadCase(setActiveGeometryState(state, "geometry_state:Hot"), "Cold");

  assert.equal(next.activeGeometryStateId, "geometry_state:Cold:physical");
});
