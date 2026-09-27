---
name: tuba-pages-verification
description: Use when Tuba's gallery differs from Studio, published examples appear stale, or the user requests gallery/Pages readiness verification.
---

# Tuba Pages verification

## Inputs

- Intended checkout and candidate revision or explicit uncommitted changes.
- Target surface: local assembled gallery or published Pages URL.
- Existing build/test environment and available workflow evidence.
- The user's authorization scope for repairs and publication.

## Procedure

1. Identify the target.
   Record the candidate and the directory or deployment actually being served.
   For a local server, verify its listener and site root. For Pages, distinguish
   the requested revision from the last successful deployment.

2. Read the current publication contract.
   Use `.github/workflows/tuba-pages.yml`, `scripts/build_pages.py`, and the
   current viewer test commands. Do not copy dependency versions, example
   counts, or snapshot recipes from an old conversation.

3. Verify the assembled artifact.
   Build into an owned output directory using the existing workflow.
   Inspect its catalog, thumbnails, packaged viewer assets, and a representative
   scene. Result-bearing examples must reference genuine Code_Aster evidence.

4. Exercise the reported behavior.
   Serve that artifact and open the affected gallery card. Check the specific
   missing or stale content, result availability, and relevant interaction.
   Run the affected catalog/gallery/browser checks.
   For publication readiness, include the workflow's platform-dependent checks.

5. Classify failures before changing anything.
   Distinguish wrong served artifact, stale generated assets, invalid solver
   evidence, stale test expectations, renderer differences, and product defects.
   Repair only within the authorized scope. Do not refresh snapshots merely
   because a comparison failed.

6. Verify publication when publication was requested and authorized.
   Confirm build and deploy success for the intended revision, then inspect
   the live target. A successful push alone does not complete this step.

## Verification and completion

Report separately:
- candidate revision and tested artifact;
- local artifact/browser checks;
- deployment revision and live checks, if applicable;
- remaining failures or unverified boundaries.

A local-readiness task finishes with local evidence. A publication task
finishes only with deployment and live-target evidence.

## Stopping conditions

If the required runtime, solver evidence, or deployment evidence is unavailable,
report the exact blocked boundary. Do not substitute another checkout's result.
Do not publish, replace a shared server, or modify another session's work
without authorization covering that action.

## Examples

Trigger: "We pushed main, but the gallery still shows the old supports."

Do not trigger: "Rename a private Python helper with no gallery, generated
artifact, or publication impact."
