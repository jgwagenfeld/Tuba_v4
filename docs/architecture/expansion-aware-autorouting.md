# Expansion-aware autorouting

Scope reviewed 2026-09-30 against commit `2d1a028`. See the
[current autorouting manual](../content/autorouting.md) for runnable usage and
the [library review](library-architecture-review.md) for outstanding issues.

## Current behavior

`GridRouter` generates deterministic geometric candidates.
`ExpansionLoopGenerator` adds U-loop candidates and reserved loop envelopes;
`ExpansionAwareRouter` ranks those alternatives. Network routing and routing
spaces have been retired. Other declared loop families are not generator output.

`SolverLoopScorer` can export selected candidates or run Code_Aster and attach
imported reaction/displacement metadata. Export-only candidates are incomplete
engineering evaluations. A production stress, displacement or operating-state
clearance claim requires a completed Code_Aster run and imported evidence.

## Inputs and actual enforcement

| Input | Current behavior |
| --- | --- |
| Endpoints, approach directions, minimum straight lengths | Geometric routing inputs |
| Section, material, grid bounds/resolution, obstacles and clearance | Geometric routing and cost inputs |
| U-loop dimensions and reserved envelope | Candidate generation and review facts |
| Thermal requirement record | Presence enables loop generation; temperature, expansion coefficient and preferences do not size a qualified loop |
| Expansion/sustained ratios | Checked only when a user-supplied evaluator provides them; Tuba has no built-in piping-standard evaluator |
| Maximum anchor reaction | Scorer compares the maximum stored reaction magnitude; it does not classify every reaction by support type |
| Nozzle reaction, operating displacement, operating clearance | Declared acceptance fields without scorer enforcement |
| Slope, waypoints, preferred/forbidden zones and some cost weights | Declared records without implemented routing enforcement |

The acceptance label currently has known defects: a false evaluator verdict and
non-finite values can pass. Until those are fixed, it cannot replace inspection
of the actual evaluator output and solver records. See
`tuba/routing/solver_loop.py:_attach_solver_acceptance`.

## Review outputs

- Candidate centerlines, U-loop dimensions and reserved envelopes.
- Candidate ranking and implemented cost terms.
- Code_Aster study paths when export is enabled.
- Imported reaction and displacement vectors when Code_Aster is run.
- User-evaluator ratios, enforced-check diagnostics and open review items.

Markdown route reports do not yet render detailed reaction/displacement
summaries. Nozzle/displacement/hot-clearance checks must not be inferred from a
candidate's aggregate acceptance label.

## Engineering limits

- The generator produces U-loops only and does not select dimensions from a
  qualified thermal-stress optimization.
- Cold obstacle checks and envelope reservation do not establish operating-state
  clearance. Use the existing Code_Aster-backed operating-geometry/clash path.
- Native friction and lift-off are implemented elsewhere in Tuba, with their
  [qualified load limits](../content/engineering/native-friction-qualification.md).
  Their existence does not qualify arbitrary routed hot-line combinations.
- Built-in ASME checks are [retired](b31j-compliance-migration.md); applicable
  standards and project acceptance remain the engineer's responsibility.
- Every selected route still requires review of endpoints, equipment constraints,
  support/load assumptions, imported results and construction clearances.
