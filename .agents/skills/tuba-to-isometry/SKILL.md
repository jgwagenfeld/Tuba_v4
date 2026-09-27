---
name: tuba-to-isometry
description: Prepare and verify dimensioned piping isometric drawings from a Tuba model, with support and fitting schedules, sheet continuations and traceability. Use for model-to-drawing export, not a generic isometric viewport screenshot.
---

# Tuba to isometry

The skill governs drawing content and verification. Deterministic code performs projection, layout, dimensioning, schedules and file export. Reuse an existing exporter after checking its capabilities; do not imply this skill installs one or establishes standards compliance.

## Define the deliverable

Read the checkout's `AGENTS.md` and identify the actual model, revision and project environment. Establish whether the user needs a review drawing, a stress-analysis isometry, or fabrication/installation documentation. Use a clearly marked review draft when the intended issue status is unknown. Ask only for choices that affect correctness or acceptance: governing project drawing specification, units, sheet format, line/sheet split and output formats.

Read [Standards and applicability](references/standards.md) when choosing drafting conventions or discussing compliance. Record the selected editions and project requirements. Do not label a drawing compliant based on a catalog abstract or its visual appearance.

Inspect the model through MCP when available, confirming current project/source before export. If a local connection is needed, `python -m tuba.mcp.server` is the repository entry point; inspect current tool schemas. `init_session` can create/update `study.py`, so use an owned project copy for a strictly read-only export. Disclose transport blockers and any direct Python inspection used instead.

## Check whether the model contains enough information

Export engineering components from the authored model, routes and source provenance. Do not treat every analysis-mesh segment as a stock pipe, fabrication spool or weld. FEM subdivisions and construction joints are different entities.

Check topology, dimensions, sections, materials, fitting definitions, supports and continuation references. Identify placeholder fittings, open ties, unresolved support settings and estimated dimensions before drawing. Native supports describe restraints; they do not necessarily define support steelwork or a manufacturer's hardware assembly.

For fabrication output, establish fitting takeouts, end preparations, weld allowances, flange/valve face-to-face dimensions, joint definitions and any shop/field split from supplied data. Never infer cut lengths by subtracting guessed allowances from centerline lengths. Do not invent weld numbers, part specifications, support hardware, revision approvals or a manufacturing release.

Carry unresolved information visibly into review drawings and the export report. Block a fabrication-ready claim when required fabrication data is absent. A geometry drawing can be produced without solving; any displayed stress, displacement, reaction or operating-state geometry must come from attributable real Code_Aster artifacts.

## Use or implement the exporter within scope

The repository review exporter is `python -m tuba.reporting.isometry PROJECT --output DIRECTORY`.
Read [its usage and limitations](../../../docs/isometry-export.md) before exporting.
It writes A3 SVG, printable HTML and CSV/JSON schedules; it does not generate native
PDF/DXF, fabrication cut lists or solved results. Python callers can use
`tuba.reporting.isometry.write_isometry(model, path, **options)`.

Look for the actual drawing/export entry point and its tests. A viewport camera named "isometric", a 3D scene export, or a report table is not evidence of a dimensioned piping-drawing exporter. If none exists, say so. When implementation is authorized, add the smallest deterministic exporter through existing Tuba geometry/reporting infrastructure; do not add a third interactive result viewer or a one-off model-specific core class.

Keep engineering data separate from page placement. Sheet spacing, schematic shortening and label movement must never change the model or dimension values. If a diagram is intentionally not to scale, label that explicitly. Make units, precision, orientation and sheet size explicit configuration rather than hidden constants.

Generate supported output formats from one drawing representation, with stable entity IDs linking drawing objects back to native model entities. Prefer vector output for technical linework. Do not claim DXF, PDF or other formats until actual generation and reopening have been verified.

## Drawing content and checks

- Show an unambiguous coordinate/orientation reference, line identifiers, endpoints/nozzles, elevations and any relevant slopes or non-orthogonal offsets. Show flow direction only when known.
- Dimension true engineering geometry, not projected screen distance. Distinguish center-to-center, face-to-face, developed length and cut length. Preserve elbow radius/angle and reducer length/end sections; a diameter-change symbol cannot supply missing model semantics.
- Label tees, reducers, valves and other fittings consistently with model/source records. Do not silently replace unsupported components with straight pipe.
- Show each in-scope support with a source/model ID, understandable symbol/legend, directions and known settings or a reference to its support schedule. Separate unresolved drawing annotations from actual model restraints.
- Build BOMs from component identity and specification, not raw element counts. Keep fitting quantities, straight stock, centerline lengths and estimated quantities distinct. Do not double-count components or supports at sheet boundaries.
- Split sheets at meaningful boundaries; match continuation IDs, dimensions and coordinates on both sides. Preserve branch connectivity even where projected lines cross without joining.
- Include drawing number, revision, sheet number, units, issue status and model provenance in the title block or associated manifest. Populate approval fields only from actual approval records.

Verify numeric values and IDs against the model before rendering, then reopen the actual exported files. Inspect every sheet for cropped text, overlapping labels, ambiguous junctions, unreadable dimensions, missing symbols, broken continuations and schedule mismatches. Include slopes, branches, diameter changes, different support types and at least one sheet boundary where present.

When implementing export code, leave focused runnable checks for true versus projected dimensions, unit conversion, connectivity, component/support coverage and consistent sheet boundaries. Verify output determinism for unchanged model/configuration, allowing explicitly recorded timestamps. Do not use only image snapshots or tests that mirror the projection implementation.

## Handoff

Provide the exported files, model/source revision, exporter/configuration used, checks performed, selected drafting conventions and unresolved inputs. Distinguish a verified review draft from fabrication-ready documentation and standards compliance. Do not claim an exported drawing or an implemented exporter when only this skill or a plan was created.
