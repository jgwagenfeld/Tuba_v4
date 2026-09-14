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

const reviewWithCompliance = {
  analysis_status: "compliance_complete",
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
    code_compliance: {
      id: "code_compliance",
      columns: [
        { id: "load_case", label: "Load case" },
        { id: "entity_ref", label: "Entity reference" },
        { id: "sustained_ratio", label: "Sustained code utilization" },
        { id: "sustained_pass", label: "Sustained pass" },
        { id: "expansion_ratio", label: "Expansion code utilization" },
        { id: "expansion_pass", label: "Expansion pass" }
      ],
      rows: [
        {
          load_case: "Operating",
          entity_ref: "element:pipe_b04",
          sustained_ratio: 0.82,
          sustained_pass: true,
          expansion_ratio: 0.61,
          expansion_pass: true
        },
        {
          load_case: "Operating",
          entity_ref: "element:pipe_a02",
          sustained_ratio: 0.55,
          sustained_pass: true,
          expansion_ratio: 0.72,
          expansion_pass: true
        }
      ]
    },
    diagnostics: {
      id: "diagnostics",
      columns: [{ id: "severity", label: "Severity" }],
      rows: [{ severity: "warning" }, { severity: "info" }, { severity: "warning" }]
    }
  }
};

const reviewWithoutCompliance = {
  ...reviewWithCompliance,
  tables: {
    project_summary: reviewWithCompliance.tables.project_summary,
    result_summary: reviewWithCompliance.tables.result_summary,
    diagnostics: reviewWithCompliance.tables.diagnostics
  }
};

test("cockpit status exposes authoritative governing evidence", () => {
  const status = cockpitStatusViewModel(reviewWithCompliance);
  assert.deepEqual(status, {
    analysisStatus: "compliance_complete",
    complianceStatus: "Pass",
    governingLoadCase: "Operating",
    warningCount: 2,
    governingRatio: "0.82",
    governingLocation: "element:pipe_b04"
  });
});

test("cockpit status keeps missing compliance neutral", () => {
  const status = cockpitStatusViewModel(reviewWithoutCompliance);
  assert.equal(status.complianceStatus, "Not available");
  assert.equal(status.governingLoadCase, "Not available");
  assert.equal(status.governingRatio, "Not available");
  assert.equal(status.governingLocation, "Not available");
});

test("cockpit status keeps partial compliance evidence neutral", () => {
  const review = {
    ...reviewWithCompliance,
    tables: {
      ...reviewWithCompliance.tables,
      code_compliance: {
        ...reviewWithCompliance.tables.code_compliance,
        rows: [{
          load_case: "Partial Operating",
          entity_ref: "element:pipe_partial",
          sustained_ratio: 0.74,
          expansion_ratio: 0.86
        }]
      }
    }
  };

  const status = cockpitStatusViewModel(review);
  assert.equal(status.complianceStatus, "Not available");
  assert.equal(status.governingLoadCase, "Not available");
  assert.equal(status.governingRatio, "Not available");
  assert.equal(status.governingLocation, "Not available");
});

