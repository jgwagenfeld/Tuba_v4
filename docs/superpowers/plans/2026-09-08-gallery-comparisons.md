# Gallery comparisons

User-approved specification: one Code_Aster model with two disconnected identical pipe systems differing only in shoe friction; one gallery example with three identical I-section cantilevers rolled 0/45/90 degrees and global/local force cases; world-anchored camera-facing scene labels. Verify real solver output and served browser, then merge to local main without pushing.

## Global constraints

- Preserve both original dirty checkouts. Implementation uses an isolated snapshot.
- Code_Aster results only; one existing web scene path; reuse profile deformation and result selection.
- Friction copies have physical offsets, separate nodes and supports, identical loading in one nonlinear evolution.
- Profile axes distinguish original basis from section orientation under solved displacement and rotation. Shared deformation and field scales.
- Labels survive bundle export and use native Three.js sprites, with a visibility control and accessible text.

## Tasks

1. Add reusable scene labels and rendering; validate payloads and visibility with focused tests. Owner: labels.
2. Replace the two friction entries with one combined model/example; run the real solver, preserve attestation, update gallery/docs/tests. Owner: friction.
3. Add local-axis profile example and solved reference checks; original/deformed local frames and two load cases. Owner: profiles.
4. Register profile gallery, build both portable bundles and thumbnails, verify served interaction and source provenance, review, and merge locally. Owner: root.

## Validation

Run existing Python and viewer baselines, focused new checks, real Code_Aster examples, viewer build, Pages bundle validation, browser gallery/labels/deformation/load-case interaction. Record commands and outcomes in the task ledger. Existing native-friction qualification is inherited evidence and will be checked against the final code.

## Implemented and verified

- One friction comparison model, one native Code_Aster evolution, 51 converged states and four shoe histories. Canonical artifacts contain the real WSL Code_Aster 18.0.12 attestation. The copies differ only by translation and friction coefficient.
- One three-cantilever profile model, two attested load cases, 0/45/90-degree section rolls. Solved displacement and rotation drive deformed I-sections and their local frames at a shared display scale. Analytical beam checks match both cases.
- Reusable world-space labels, accessible layer control, Results-owned deformed groups, and camera fitting that accounts for the open controls dock through zoom and resize. Complete manifest geometry avoids duplicate payload requests.
- Eight official Pages bundles built and validated; strict Zensical docs build passed; complete assembled Pages tree validated. Both new thumbnails were captured from actual rendered scenes.
- Final viewer checks: 304 unit tests passed; six Playwright gallery/profile/contact checks passed across the final runs. Native contact integration: 10 tests passed with real Code_Aster. Gallery/docs/refresh checks: 66 passed. Beam load-case and contact provenance mutation checks passed; independent reviews resolved all reported P1/P2 findings.
- The monolithic pytest attempt was interrupted during a slow clean-snapshot/package rebuild. The split rerun subsequently passed that clean-snapshot rebuild. Remaining Python checks and focused publication checks are recorded in the execution ledger; no claim of a completed monolithic full-suite run.
- Local integration only. Original dirty worktrees have concurrent unrelated edits and are preserved.
