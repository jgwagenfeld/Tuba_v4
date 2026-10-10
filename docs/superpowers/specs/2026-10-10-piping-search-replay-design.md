# Interactive piping search replay

This implements roadmap M2: an engineer can explain every retained candidate
outcome in the existing viewer, navigate attempts and parents, compare authored
parameters and geometry, and inspect native findings without an agent or solve.
The user's instruction to continue the approved roadmap authorizes this work.

## Boundaries

- Python support remains `>=3.11,<3.15`.
- Use `tuba/visualization/` and `viewer/`; no new renderer or frontend dependency.
- Authored procedural source and the retained search archive are read-only.
- Engineering results come only from inventory-verified, publication-validated
  native Code_Aster artifacts. A missing artifact disables that result view.
- Every candidate and sealed attempt remains in the replay, including cold
  rejection, interrupted/failed/incomplete attempts, duplicate and deferred rows.
- Films, new search strategies and piping-standard approval remain later work.
- Commit locally; never push. Reuse the existing isolated worktree, dependencies
  and shared caches; generated packages/builds/logs remain outside tracked source.

## Export contract

`write_search_replay(run_dir, output_dir) -> Path` creates a new output folder
containing `search_replay.json` (`tuba.search.viewer.v1`), the M1 history export,
one native geometry preview per built candidate, and native review bundles for
each sealed evaluation attempt. It never calls a solver or executes authorship.
The existing candidate-review writer owns real-result validation and staging.
No new repository snapshots or dependency payloads are copied. Failed bundle
generation is recorded as unavailable and does not erase the history. Existing
output is refused. Output size and drive free space are reported.

Each candidate has `preview` and `attempt_reviews` entries containing a safe
bundle-relative directory, availability, message and evaluation/attempt IDs.
The manifest retains all original events and check/decision records. It also
retains consistent scalar ranges keyed by field ID and unit for comparable
magnitude fields. Native copied evidence links are bundle-relative; unavailable
or non-exported evidence stays explicitly identified as archived evidence.

## Viewer behavior

The existing local launcher accepts a replay directory and opens the viewer with
`?search=/bundle/search_replay.json`. A replay with no viewable scene still opens
its records with an empty viewport. Resource-bounded JSON loading and relative,
same-origin URLs reject traversal, encoded traversal and active URL schemes.

A Search section contains an event slider, step buttons, UTC search event time,
candidate list/order, best feasible candidates so far, branch/parent links,
attempt selection, reference-candidate parameter comparison, recorded decisions,
checks and artifact diagnostics. Solver result-state/increment is shown separately
from search event time. Candidates not yet proposed and evaluations/decisions
after the cursor are absent. Until an evaluation is sealed only its reference
geometry preview is eligible. Selected/feasible labels come from recorded
decisions at that point, never from the final snapshot.

Parents are recorded relationships; the previous grid candidate is never invented
as a parent. A missing parent is shown without a navigation link. A reference
selector can compare independent roots. Switching parent/reference geometry uses
the same viewport and camera. Units, display deformation scale and common
magnitude-field ranges stay consistent across candidates. Non-comparable field
components retain the native legend and say their range is local. Engineering
clash measurements always use the recorded physical scale-1 basis.

Check callouts identify required/advisory role, verdict, constraint ID, operation,
result-state, targets, measurement/comparator/limit/unit, reason and evidence.
Selecting a check switches to its exact operation/result state and highlights
only candidate-local entities. Cold findings switch to reference geometry.
Earlier attempts cannot inherit a later selected outcome. Missing geometry or
results clears the old viewport; asynchronous switches cannot show a previous
candidate under the newly selected candidate's heading. Replay is review-only.

## Qualification

Unit tests cover event causality, attempt scope, duplicate parent IDs/cycles,
missing/damaged artifacts, URL confinement, result-state highlights, comparisons
and rapid switching. Portable tests use the existing native deterministic fixtures
and name that scope. Browser validation uses the retained real Code_Aster hot-line
archive (12 candidates, 16 completed operation calls); no additional physics solve
is required for this read-only presentation milestone. Capture screenshots and
actual browser assertions outside tracked source. Run the affected viewer tests,
export/CLI/launcher tests and a source build to an external output folder.
