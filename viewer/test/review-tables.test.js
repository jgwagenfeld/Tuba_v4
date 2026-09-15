import assert from "node:assert/strict";
import test from "node:test";

import { cockpitStatusViewModel } from "../src/reviewTables.js";

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

const reviewWithWarnings = {
  analysis_status: "solved",
  tables: {
    project_summary: {
      id: "project_summary",
      columns: [{ id: "project_name", label: "Project" }],
      rows: [{ project_name: "Example" }]
    },
    result_summary: {
      id: "result_summary",
      columns: [{ id: "result_type", label: "Result type" }],
      rows: [{ result_type: "translation_magnitude" }]
    },
    diagnostics: {
      id: "diagnostics",
      columns: [{ id: "severity", label: "Severity" }],
      rows: [{ severity: "warning" }, { severity: "info" }, { severity: "warning" }]
    }
  }
};

test("cockpit status reports the analysis status and counts warnings", () => {
  assert.deepEqual(cockpitStatusViewModel(reviewWithWarnings), {
    analysisStatus: "solved",
    warningCount: 2
  });
});

