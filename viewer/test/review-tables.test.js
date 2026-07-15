import assert from "node:assert/strict";
import test from "node:test";

import {
  tableIdsForWorkflow,
  tableViewModel,
  workflowViewModel
} from "../src/reviewTables.js";

const reviewFixture = {
  analysis_status: "solved",
  tables: {
    project_summary: {
      id: "project_summary",
      title: "Project summary",
      source: "model",
      columns: [{ id: "project_name", label: "Project" }],
      rows: [{ project_name: "Example" }]
    },
    result_summary: {
      id: "result_summary",
      title: "Governing results",
      source: "result_state",
      columns: [
        { id: "maximum_value", label: "Maximum value", unit: "Pa" },
        { id: "governing_entity_ref", label: "Governing entity" }
      ],
      rows: [
        { maximum_value: 125000000, governing_entity_ref: "element:pipe_17" },
        { maximum_value: 98000000, governing_entity_ref: "element:pipe_4" }
      ]
    },
    fe_stress: {
      id: "fe_stress",
      title: "FE stress",
      source: "result_state",
      columns: [
        { id: "result_basis", label: "Result basis" },
        { id: "max_von_mises_pa", label: "Maximum Von Mises", unit: "Pa" }
      ],
      rows: [
        {
          result_basis: "FE Von Mises (not piping-code stress)",
          max_von_mises_pa: 125000000
        }
      ]
    }
  }
};

test("review table maps workflow tabs to stable authoritative table ids", () => {
  assert.deepEqual(tableIdsForWorkflow("model"), ["nodes", "line_list", "section_schedule", "materials", "supports"]);
  assert.deepEqual(tableIdsForWorkflow("load-cases"), ["load_cases", "studies"]);
  assert.deepEqual(tableIdsForWorkflow("results"), ["result_summary", "displacements", "reactions", "element_forces", "fe_stress"]);
  assert.deepEqual(tableIdsForWorkflow("compliance"), ["code_compliance"]);
});

test("review table keeps the exact FE stress basis visible", () => {
  const model = tableViewModel(reviewFixture.tables.fe_stress);

  assert.match(JSON.stringify(model), /FE Von Mises \(not piping-code stress\)/);
});

test("workflow tables return an explicit unsolved state", () => {
  const modelOnlyReview = {
    analysis_status: "not_solved",
    tables: { project_summary: reviewFixture.tables.project_summary }
  };

  assert.equal(
    workflowViewModel(modelOnlyReview, "results").unavailableReason,
    "Analysis has not been solved."
  );
});

test("workflow tables distinguish a missing ComplianceReport", () => {
  const withoutCompliance = { analysis_status: "solved", tables: reviewFixture.tables };

  assert.equal(
    workflowViewModel(withoutCompliance, "compliance").unavailableReason,
    "Code compliance is unavailable because no ComplianceReport was supplied."
  );
});

test("review table formats JSON-native values as plain deterministic cell strings", () => {
  const model = tableViewModel({
    id: "formatting",
    title: "Formatting",
    source: "fixture",
    columns: [
      { id: "missing", label: "Missing" },
      { id: "enabled", label: "Enabled" },
      { id: "tags", label: "Tags" },
      { id: "metadata", label: "Metadata" },
      { id: "pressure", label: "Pressure", unit: "Pa" }
    ],
    rows: [{ missing: null, enabled: true, tags: ["hot", "operating"], metadata: { z: 2, a: 1 }, pressure: 2400000 }]
  });

  assert.deepEqual(model.columns.map((column) => column.label), ["Missing", "Enabled", "Tags", "Metadata", "Pressure [Pa]"]);
  assert.deepEqual(model.rows[0].cells.map((cell) => cell.text), [
    "—",
    "Yes",
    "hot, operating",
    "a: 1; z: 2",
    "2400000"
  ]);
  assert.ok(model.rows[0].cells.every((cell) => typeof cell.text === "string"));
});

test("review table identifies pass/fail, diagnostic severity, and governing references", () => {
  const model = tableViewModel({
    id: "diagnostics",
    title: "Diagnostics",
    source: "diagnostics",
    columns: [
      { id: "passed", label: "Passed" },
      { id: "severity", label: "Severity" },
      { id: "governing_entity_ref", label: "Governing entity" }
    ],
    rows: [{ passed: false, severity: "warning", governing_entity_ref: "element:pipe_17" }]
  });

  assert.deepEqual(model.rows[0].cells, [
    { columnId: "passed", text: "FAIL", tone: "fail" },
    { columnId: "severity", text: "WARNING", tone: "warning" },
    { columnId: "governing_entity_ref", text: "element:pipe_17", entityRef: "element:pipe_17" }
  ]);
  assert.equal(model.rows[0].entityRef, "element:pipe_17");
});

test("review table preserves authoritative row order and never produces raw HTML", () => {
  const dangerous = "<img src=x onerror=alert(1)>";
  const model = tableViewModel({
    id: "ordered",
    title: "Ordered rows",
    source: "fixture",
    columns: [
      { id: "id", label: "ID" },
      { id: "note", label: "Note" }
    ],
    rows: [
      { id: "second-by-name", note: dangerous },
      { id: "first-by-name", note: "safe" }
    ]
  });

  assert.deepEqual(model.rows.map((row) => row.cells[0].text), ["second-by-name", "first-by-name"]);
  assert.equal(model.rows[0].cells[1].text, dangerous);
  assert.doesNotMatch(JSON.stringify(model), /"html"\s*:/i);
});
