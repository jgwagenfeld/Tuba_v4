---
name: isometry-to-tuba
description: Reconstruct or review piping isometric drawings in Tuba, reconcile supports and fittings with source evidence, verify through MCP, and open the model in Studio. Use for drawing-to-model work, not general viewer development.
---

# Isometry to Tuba

Deliver a source-traceable, procedural Tuba model and an honest completeness report. A request to model a drawing collection includes its supports and fittings unless the user explicitly narrows the scope. A geometry-only review may remain unsolved; it must identify incomplete engineering inputs.

## Establish the source and scope

- Read the target checkout's `AGENTS.md`, inspect its state, and preserve concurrent work. Use its supported environment and APIs; do not assume another checkout or a running Studio uses the same code.
- Inventory drawing numbers, sheets, revisions, units, coordinate axes, continuation references and accompanying BOMs/support schedules. Distinguish drawing sets from individual sheets. Record PDF/CSV conflicts and the selected evidence; ask for the authoritative revision where it changes the model.
- Inspect the rendered drawings as well as extracted text. Recover geometry from dimensions and shared connection references. A schematic isometry need not be to scale. Treat lengths recovered from projection as estimates with uncertainty; do not invent sheet offsets or snap away unexplained closure errors.
- Build what the sources establish while requesting missing information. Do not require approval for routine reversible work already authorized by the user.

## Author the project

Use readable `model.py` functions, engineering parameters, native pipe builders and existing construction units. Keep dimensional schedules separate when useful. Do not author an unrolled node/element dump or build a large network through individual MCP geometry calls.

Keep source drawing, revision, callout and connection IDs associated with model entities. Verify shared topology at branches and sheet boundaries: coincident coordinates alone do not prove connectivity. Report open tie-ins with their measured discrepancy and source references.

Maintain a project-local reconciliation table (JSON, CSV or Markdown) covering source supports and fittings. Reuse an existing project schedule rather than introducing a second source of truth. Each entry needs:

- Source sheet/revision and callout or node reference.
- Interpreted component, dimensions or restraint settings, and the evidence for them.
- Corresponding native element/support IDs; allow one source support to map to multiple restraints.
- Status: implemented, partial, unresolved, or excluded by explicit scope; include the reason and missing input.

An attribute or label is provenance, not implementation. Unsupported features and placeholders remain partial/unresolved even when they render convincingly.

## Translate supports

Reconcile callout locations with symbols and source node IDs. Nearest-text matching is a candidate association, not proof. Check repeated callouts and cross-sheet duplicates before adding restraints.

For each support, establish the constrained/free translations and rotations, local-to-global axis mapping, bilateral versus unilateral behavior, clearance/gap, friction, attachment and any stiffness, preload, cold setting or travel. Record which settings are explicit, inferred, or missing. Never silently replace missing values with API defaults.

- Distinguish guides, sliding rests, axial/lateral stops and anchors. Do not lock rotations or all translations merely because the drawing says "support" or "rigid".
- Preserve directional restraint semantics. Read the current `Support.restraint()` and solver/contact implementation before selecting `direction`, `blocked_dof`, `gap` or stiffness fields; a direction vector may be an axis mask rather than an arbitrary oblique constraint.
- Preserve units: for example, a spring rate in N/mm must be converted to N/m when required by the API. A spring rate alone does not establish preload or cold load.
- A constant hanger is not an anchor or an arbitrary spring. If its load/settings or a supported formulation are missing, retain an explicit unresolved record.
- Add actual native supports for fully established behavior. Keep incomplete settings visible in the reconciliation table and project review; do not present the model as ready to solve while required restraints remain unresolved.

Check coverage by identity and behavior, not by comparing raw totals. Every in-scope source support must be accounted for; implemented entries must reference existing supports at the correct nodes, with matching restraint states and numeric settings. Detect missing entries, duplicate associations and extra model restraints. Annotation-only coverage fails model completeness.

## Translate fittings

Check fitting-specific wall thicknesses, diameters, radii, lengths, branch/run orientation and connectivity against the BOM and symbols. Do not automatically inherit adjacent pipe properties.

Use supported native tee, reducer and other fitting definitions where the current library provides them. Verify procedural replay, serialization and the actual geometry/solver path; the existence of an API name is insufficient. A diameter change between uniform segments is not an explicit finite-length reducer. Unsupported bodies or stiffnesses must remain marked as placeholders; do not implement a new core formulation as an incidental import fix.

When a junction looks wrong, inspect that specific junction in Studio and trace its element IDs to the source. Distinguish disconnected topology, wrong dimensions, overlapping display tubes/end rings, and missing fitting bodies. Do not diagnose a renderer defect from a description or claim that tee metadata alone produces a joined solid.

## Verify and review

Use MCP as the inspection, verification and solving interface after Python authoring. Read [MCP and Studio procedure](references/mcp-and-studio.md) when connecting or checking a project. If tools are not exposed, attempt the repository's local stdio server with an available MCP client. Disclose a concrete blocker if that fails; do not relabel direct function calls as MCP use.

Combine MCP results with source reconciliation and focused project checks:

- Sheet/revision coverage, dimensional units, sections and fitting dimensions.
- Shared nodes, branches, continuation references and closure discrepancies.
- Actual support IDs, nodes, six restraint states and settings against the source table.
- Join-aware clashes and duplicate-node findings; inspect reported pairs and their originating routes/units. Do not dismiss all fitting overlaps as false positives or disable checks to obtain a pass.
- Execute/reload the authored script and check that its meaning and source are preserved.

Open Studio on the intended project and inspect the live scene, including a tee, diameter transition, representative support types and any known issue. Confirm the served project/source and keep the requested tab open. A successful server start or scene export is not visual verification.

If evaluation is requested, first resolve required geometry/support inputs, materials, temperatures, pressures and load cases. Run the real Code_Aster backend and display its processed artifacts. Missing runtime or engineering inputs block evaluation; exported decks and model checks are not solved results. A skill's import/review workflow does not itself authorize an unrequested solve.

## Handoff

Report the project path and Studio URL, covered sources, implemented versus unresolved supports/fittings, open geometry issues, checks actually performed, and whether MCP and Code_Aster actually ran. Label geometry-only work **UNSOLVED**. Do not call the collection complete because all sheets render or `model.validate()` passes.
