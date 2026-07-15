# Engineering Review Package And Viewer Workflow Design

**Date:** 2026-07-15
**Status:** Proposed for implementation
**Branch:** `codex/future-ready-workpackages`

## 1. Purpose

Tuba needs an engineer-facing analysis deliverable, not only an interactive
scene inspector. The deliverable must combine authoritative model inputs,
traceable Code_Aster result states, piping-code compliance results, tabular
reports, and the existing reviewable Three.js scene without making the viewer
the source of engineering truth.

This design introduces a function-first `tuba.reporting` boundary and turns the
existing viewer into a workflow-oriented consumer of the same review data. It
preserves the two established visualization paths:

- `tuba.plotting` for PyVista quick-look and export;
- `tuba.visualization` plus `viewer/` for reviewable web scenes.

Reporting is a data/export concern, not a third visualization path.

## 2. Current State

Commit `10d2bd8` added scene-derived functions for a line list, section
schedule, load-case summary, FE stress/utilization, reactions, displacements,
CSV output, and static HTML output. These functions are useful and tested, but
their input is `VisualizationScene`, which is a rendering contract and does not
retain every authoritative model, study, provenance, load, and compliance
field.

The browser viewer renders Code_Aster result overlays successfully, but its
layout exposes layers, overlays, results, hotspots, diagnostics, tree, issues,
search, objects, and raw properties at once. This is appropriate for debugging
a scene contract but does not guide a piping engineer through model review,
load cases, results, code checks, and diagnostics.

## 3. Decision Drivers

- `TubaModel` remains authoritative for geometry, sections, materials,
  supports, operations, and load cases.
- `AnalysisStudy` and `ResultState` remain authoritative for solver lineage and
  processed Code_Aster results.
- `ComplianceReport` remains authoritative for ASME sustained and expansion
  checks.
- FE Von Mises stress must never be labeled or interpreted as piping-code
  stress.
- A model-only package may report inputs and an explicit `not_solved` status,
  but it must not contain solver or compliance results.
- Existing scene/report APIs and existing viewer bundles must continue to work.
- Engineers and automation need stable Python rows and JSON/CSV output; the UI
  is one consumer of those contracts.
- The first slice must be printable and archivable without adding a heavyweight
  document-generation dependency.

## 4. Considered Approaches

### A. Continue deriving reports from `VisualizationScene`

This is the smallest change and retains the current implementation. It is
rejected as the long-term boundary because scenes intentionally flatten and
omit data that does not affect rendering. Adding every reporting field to the
scene would turn a renderer contract into a second model schema.

### B. Make the viewer the application and calculate reports in JavaScript

This could deliver a polished UI quickly. It is rejected because engineering
semantics would be duplicated in the browser, Python users would receive a
weaker API, and archived report output could drift from notebook/CSV output.

### C. Build an authoritative engineering-review package with multiple consumers

This is the selected approach. Python constructs one review package from the
model, studies, result states, and compliance reports. CSV, printable HTML, the
static report, and the viewer consume the same typed tables and provenance.
The scene remains responsible only for spatial review.

## 5. Architecture

```text
TubaModel + AnalysisStudy + ResultState + ComplianceReport
                             |
                  EngineeringReviewPackage
              +--------------+--------------+
              |              |              |
        Python tables    HTML / CSV     VisualizationScene
        and JSON         deliverable    and Three.js viewer
```

### 5.1 New package

Add `tuba/reporting/` with these responsibilities:

- `model.py`: typed `ReportColumn`, `ReportTable`, `ReviewDiagnostic`,
  `ReviewProvenance`, and `EngineeringReviewPackage` records;
- `builder.py`: validation and construction from authoritative inputs;
- `tables.py`: pure table builders;
- `export.py`: deterministic JSON, CSV, and printable HTML export;
- `__init__.py`: the small public API.

The reporting package may import `tuba.model`, `tuba.analysis`, and
`tuba.compliance`. It must not import browser code. Scene integration belongs
in a thin adapter under `tuba.visualization` so `tuba.reporting` does not depend
on visualization.

### 5.2 Public API

```python
from tuba.reporting import build_engineering_review, write_engineering_review

review = build_engineering_review(
    model,
    studies=[study],
    result_states=[result_state],
    compliance_reports=[compliance_report],
)

review.table("line_list")
review.table("load_cases")
review.table("fe_stress")
review.table("code_compliance")
review.to_dict()

output = write_engineering_review(
    review,
    "reports/HOT-100",
    scene=scene,
    title="HOT-100 engineering review",
)
```

`build_engineering_review` accepts empty iterables for studies, result states,
and compliance reports. Model input tables are then generated with
`analysis_status="not_solved"`. It does not run Code_Aster implicitly.

`write_engineering_review` writes a self-contained directory containing:

```text
index.html
review.json
report_manifest.json
reports/*.csv
scene.json                       # only when a scene is supplied
metadata/* and geometry/*        # existing scene-bundle layout
```

The HTML is printable with a dedicated print stylesheet, which permits browser
Print-to-PDF without adding a PDF runtime in this slice.

### 5.3 Compatibility

The current functions in `tuba.visualization.reports` remain importable. They
become compatibility adapters for scene-only callers and retain their current
return type. New code and documentation use `tuba.reporting`.

`write_static_report(scene, ...)` remains supported. Internally it may build a
scene-only legacy review, but it must label missing authoritative inputs and
must not claim code compliance. Existing scene bundles without `review.json`
continue to load in the viewer using the current scene-derived fallback.

## 6. Engineering Review Data Contract

### 6.1 Package metadata

`EngineeringReviewPackage` contains:

- schema version;
- package ID and creation timestamp;
- project/model name, model standard, and model revision;
- analysis status: `not_solved`, `partial`, `solved`, or `compliance_complete`;
- units and coordinate-system declaration;
- provenance records;
- ordered report tables;
- diagnostics;
- optional scene URI supplied by the exporter.

Serialization is deterministic: stable table order, stable row order, sorted
mapping keys, and no machine-specific absolute paths in public links. Original
artifact paths may appear only as provenance values.

### 6.2 Tables in the first slice

The package exposes these stable table IDs:

| Table | Source | Required content |
|---|---|---|
| `project_summary` | model/package | project, standard, revision, status, counts |
| `nodes` | model | node ID and X/Y/Z coordinates |
| `line_list` | model | element, type, end nodes, route/stations, length, section, material, bend data |
| `section_schedule` | model | section type and full defining dimensions/properties, count, length, mass |
| `materials` | model | E, nu, density, alpha, temperature-dependent allowables |
| `supports` | model | node, type, direction/blocked DOF, stiffness, mass, friction |
| `load_cases` | model | gravity, pressure, temperature, reference temperature, nodal loads, fields |
| `studies` | studies | study ID, load case, solver, model revision, mesh, input artifacts |
| `result_summary` | results/compliance | governing locations and maxima per load case with result basis |
| `displacements` | result states | six DOF, translation magnitude, load case, result-state ID |
| `reactions` | result states/model | six DOF, force magnitude, support identity, load case |
| `element_forces` | result states | end forces/moments for both element ends and load case |
| `fe_stress` | result states | end/max Von Mises with explicit `FE, not code stress` basis |
| `code_compliance` | compliance | sustained/expansion stress, allowables, ratios, pass/fail, SIF/flexibility trace values |
| `diagnostics` | all sources | severity, code, source, target, message |

Every solver-derived row includes `solver_name`, `study_id`,
`result_state_id`, and `load_case`. Summary rows include both the maximum value
and its governing node or element; a maximum without a location is invalid.

### 6.3 Stress semantics

The following labels are mandatory:

- Code_Aster `SIEQ_ELNO`/`VMIS` and `max_von_mises` values use the basis
  `FE Von Mises (not piping-code stress)`.
- A ratio of FE Von Mises to a material allowable is an FE screening ratio. It
  is not named `code utilization`, `ASME utilization`, or `compliance`.
- Only rows derived from `ComplianceReport` may use the terms sustained stress,
  expansion stress, code allowable, code utilization, or compliance.

The `ComplianceReport` contract gains explicit code name and edition fields so
the report never relies on an unstated default.

## 7. Validation And Failure Handling

`build_engineering_review` validates before producing solver-derived tables:

- all studies and result states match the current model revision;
- every result state references a supplied study;
- study/result load cases and mesh IDs agree;
- production result states identify Code_Aster as the solver;
- compliance load cases have a matching result state;
- referenced model nodes and elements exist.

Revision, study-link, mesh, or entity-reference mismatches raise
`EngineeringReviewError`. Missing optional artifact paths and parser warnings
become report diagnostics. A package with no result state is valid but is
explicitly `not_solved` and has no result/compliance tables.

Portable tests use deterministic `Code_Aster` fixtures. User-facing examples
must use imported real Code_Aster artifacts or stop before result/compliance
display, following the repository contract.

## 8. Viewer Workflow

### 8.1 Navigation

Replace the always-visible debug inventory with top-level workflow tabs:

1. **Summary** — analysis status, provenance, model counts, governing results,
   compliance verdict, warnings;
2. **Model** — nodes, line list, sections, materials, and supports;
3. **Load Cases** — definitions, nodal loads/fields, linked studies and solve
   status;
4. **Results** — result-state/load-case controls, summary tables, hotspots,
   displacements, reactions, element forces, and FE stress;
5. **Compliance** — code/edition, sustained and expansion checks, governing
   ratios, and a clear unavailable state when no compliance report exists;
6. **3D** — the existing Three.js viewport, layers, overlays, object search,
   selection, property inspection, issue focus, and deformation/vector scales;
7. **Diagnostics** — scene diagnostics, parser/report diagnostics, issues,
   artifact provenance, and review state.

The 3D renderer and scene state remain intact. The change is information
architecture, not a renderer rewrite.

### 8.2 Bundle loading

The viewer tries to load `review.json` after loading the existing scene bundle.
A 404 is a supported legacy condition and does not produce an error. When
review data is present, tabs render the authoritative tables. When absent, the
viewer exposes the 3D and Diagnostics workflows and may show clearly labeled
scene-derived summaries.

The full viewer defaults to **Summary** when `review.json` exists and **3D** for
legacy scene-only bundles. `embed=1` always defaults to **3D** and keeps the
compact embedded presentation.

### 8.3 Interaction between tables and 3D

Rows containing an object/entity reference provide a `Show in 3D` action. It
selects the object, switches to the 3D tab, fits the selection, and preserves
the active load case/result state. This is the main bridge between tabular
engineering review and spatial review.

## 9. Static HTML Deliverable

The HTML report presents the same workflow in a printable order:

1. title, project, revision, analysis status, code and provenance;
2. governing results and compliance verdict;
3. model/input tables;
4. load cases and studies;
5. result tables;
6. code-compliance tables;
7. diagnostics;
8. link to the scene manifest and interactive viewer when supplied.

Each non-empty table has a CSV link. Empty solver/compliance tables are not
silently omitted: the summary states why they are unavailable. The report does
not call itself approved, certified, or signed; approval/signature workflows
are outside this slice.

## 10. Testing Strategy

Implementation follows red-green-refactor.

### Python unit tests

- package construction from a model-only input;
- full model table coverage, including section wall thickness and supports;
- provenance and deterministic serialization;
- revision/study/mesh mismatch failures;
- no result tables without result states;
- FE stress basis is never code stress;
- compliance fields come only from `ComplianceReport`;
- governing values include locations;
- CSV/JSON/HTML output and legacy adapter compatibility.

### Viewer unit tests

- optional review loading and legacy 404 behavior;
- tab visibility and default tab rules;
- table rendering and unavailable states;
- `Show in 3D` selection handoff;
- existing result controls, layer visibility, issue review, and scene-diff state
  remain functional.

### Browser tests

- full review bundle opens on Summary and navigates through every tab;
- legacy bundle opens on 3D;
- embedded bundle opens compact 3D;
- a governing-result row focuses the correct object in 3D;
- a nonblank WebGL frame is rendered after navigation.

### Integration verification

- generate a fresh review package from the existing committed Code_Aster
  artifact workflow;
- inspect `review.json`, CSVs, printable HTML, and the browser viewer;
- run the existing Code_Aster real-smoke gate when the configured runtime is
  available; otherwise report that runtime boundary explicitly.

## 11. Non-Goals

- Running Code_Aster from the report writer.
- Creating synthetic or proxy solver values.
- Replacing PyVista or Three.js.
- Adding a third visualization path.
- Implementing electronic signatures, approvals, document control, or a report
  database.
- Adding a server-side PDF dependency; printable HTML is the first PDF path.
- Implementing every dynamic, fatigue, flange, nozzle, spring-hanger, or
  equipment-code report before Tuba has authoritative domain results for it.
- Recreating CAESAR II or AutoPIPE report-template editors.

## 12. Delivery Sequence

1. Add the reporting data model, builder validation, and model-input tables.
2. Add result, force, FE-stress, compliance, provenance, and diagnostic tables.
3. Add deterministic JSON/CSV/printable-HTML export.
4. Adapt existing visualization report/static-report APIs without breaking
   callers.
5. Publish `review.json` alongside scene bundles.
6. Restructure the viewer into workflow tabs and add table-to-3D navigation.
7. Regenerate the committed Code_Aster review artifact and update public docs.
8. Run focused, viewer, package, build, browser, and available Code_Aster gates.

## 13. Acceptance Criteria

- A caller can build authoritative model/input tables without creating a scene.
- A model-only package is visibly `not_solved` and contains no solver-derived
  or compliance values.
- A solved package records Code_Aster study/result provenance on every
  solver-derived table row.
- FE Von Mises values are visibly and structurally distinct from code stress.
- Sustained/expansion compliance values originate only from
  `ComplianceReport` and state code name/edition.
- The first-slice table set in section 6.2 is generated and downloadable as
  CSV where applicable.
- Printable HTML and `review.json` contain the same table values.
- Existing `tuba.visualization.reports` imports and scene-only bundles remain
  functional.
- The viewer presents Summary, Model, Load Cases, Results, Compliance, 3D, and
  Diagnostics workflows.
- A report row can focus its referenced object in the 3D viewer.
- `embed=1` retains a compact interactive 3D experience.
- Existing viewer tests pass, new reporting/viewer tests pass, the Vite build
  succeeds, browser E2E passes, and real Code_Aster verification is either
  successful or reported as an explicit environment blocker.
