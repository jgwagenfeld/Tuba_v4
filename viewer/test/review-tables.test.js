import assert from "node:assert/strict";
import test from "node:test";

import { cockpitStatusViewModel, solverProvenanceLabel } from "../src/reviewTables.js";

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

// The provenance records are written one per artifact, so the solver is named
// three times over and the runtime version only once, on the result state.
test("solver provenance names the solver, its runtime and the case count", () => {
  const label = solverProvenanceLabel({
    provenance: [
      { kind: "study", solver_name: "Code_Aster", load_case: "Operating" },
      { kind: "analysis_mesh", solver_name: "Code_Aster", load_case: "Operating" },
      {
        kind: "result_state",
        solver_name: "Code_Aster",
        load_case: "Operating",
        metadata: { runtime_version: "18.0.12" }
      },
      { kind: "result_state", solver_name: "Code_Aster", load_case: "Hot" }
    ]
  });

  assert.equal(label, "Code_Aster 18.0.12 · 2 cases");
});

test("solver provenance stays singular for one case and drops an absent runtime", () => {
  assert.equal(
    solverProvenanceLabel({ provenance: [{ solver_name: "Code_Aster", load_case: "Operating" }] }),
    "Code_Aster · 1 case"
  );
});

// Nothing here may invent a solver: a scene with no review, or a review whose
// records name none, gets no line rather than a plausible one.
test("solver provenance says nothing when no record names a solver", () => {
  assert.equal(solverProvenanceLabel(null), "");
  assert.equal(solverProvenanceLabel({}), "");
  assert.equal(solverProvenanceLabel({ provenance: [{ kind: "study", load_case: "Operating" }] }), "");
});

