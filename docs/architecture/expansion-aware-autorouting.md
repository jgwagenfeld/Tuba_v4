# Expansion Aware Autorouting

## Decision

Tuba treats hot-line routing as solver-reviewed candidate generation, not as
shortest-path search. The grid and network routers remain deterministic
candidate sources. Expansion-aware autorouting adds explicit routing spaces,
generated U-loop candidates, reserved loop envelopes, and
`SolverAcceptanceCriteria` metadata so engineers can compare route options
against available thermal and solver evidence. Additional loop families are
typed/planned extension points, not current generator output.

A passing solver check is not automatic signoff. Solver execution is optional,
and final route acceptance remains an engineering review decision based on the
generated report, exported studies, and project constraints.

## Required Inputs

- Endpoints with optional approach directions and minimum straight lengths.
- Pipe section, material, insulation, and clearance requirements.
- Routing grid bounds, resolution, obstacles, and context geometry.
- Routing space with allowed, preferred, forbidden, and reserved zones.
- Thermal route requirement with design temperature, reference temperature,
  effective line length, and expansion coefficient.
- `SolverAcceptanceCriteria` values. Today `SolverLoopScorer` enforces
  expansion stress ratio, sustained stress ratio, and maximum anchor reaction.
  Nozzle reaction, operating displacement, and operating-clearance fields are
  typed review/future fields until scorer support exists.
- Solver loop configuration that states whether candidates are exported only or
  run through Code_Aster for review.

## Review Outputs

- Candidate type and centerline points, including direct routes and generated
  U-loop candidates.
- Expansion-loop dimensions and reserved envelope.
- Corridor, keepout, and reserved-zone conflicts.
- Rank and cost terms used to compare candidates.
- Code_Aster study path for each reviewed candidate when export is enabled.
- ASME sustained and expansion ratios when solver results are available.
- Raw reaction and displacement vectors in candidate metadata/JSON when solver
  results are available. Markdown route reports do not yet render detailed
  reaction or displacement summaries.
- Failed enforced `SolverAcceptanceCriteria` checks and open engineering review
  items.

## Review Checklist

- Do endpoints, approach directions, and minimum straight lengths match
  equipment and nozzle constraints?
- Are preferred corridors, forbidden zones, and reserved zones current for the
  model revision?
- Does the selected route reserve enough loop envelope and operating clearance
  for nearby lines, supports, and maintenance access?
- If solver results are present, are stress ratios, reactions, and
  displacements within project limits? Only stress ratios and anchor reactions
  are scorer-enforced today.
- If solver execution was skipped, has an engineer reviewed exported Code_Aster
  studies or accepted the export-only evidence boundary?
- Are remaining assumptions captured in the route report before construction or
  downstream automation?

## Limitations

- First implementation uses linear envelope reservation; nonlinear contact
  behavior is not modeled.
- `ExpansionLoopGenerator` currently generates U-loop candidates only.
  Additional loop families remain future work.
- Solver execution remains optional; export-only studies support review but do
  not prove solver acceptance.
- Current `SolverAcceptanceCriteria` enforcement is limited to expansion ratio,
  sustained ratio, and anchor reaction. Other typed fields remain review inputs
  or future scorer gates.
- Nonlinear friction, support gaps, lift-off, spring supports, and restraint
  behavior require later support-model and solver upgrades.
- Final construction routing still requires engineer review.
