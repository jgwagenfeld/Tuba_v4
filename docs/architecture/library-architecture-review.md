# Historical library cleanup review

This records the September 30, 2026 cleanup and its scoped verification.
It is not a current feature inventory or a release-readiness verdict. The
original review and follow-up remain in Git history at `ad04454`.

## Current scope and owners

- [Architecture](../content/architecture/index.md), [modeling](../content/modeling.md)
  and [public Python interface](../content/reference/public-api.md).
- [Workflow](../content/workflow.md): authored Python model -> Code_Aster solve ->
  processed result review. Exported inputs alone are incomplete.
- [Visualization](../content/architecture/visualization.md): PyVista quick-look/export
  and the shareable web-scene review.
- [Mixed STEP studies](step-mixed-code-aster.md): supported solves, reference checks
  and their qualification limits.
- [Autorouting](../content/autorouting.md) and
  [native friction qualification](../content/engineering/native-friction-qualification.md).
- [Retired piping standards checks](b31j-compliance-migration.md) and the
  [historical reliability plan](../superpowers/plans/2026-09-26-library-reliability-and-v2-parity.md).

## Historical findings and verification

The cleanup removed unused helpers and duplicate feature descriptions. Follow-up
fixes made routing reject incomplete acceptance evidence and preserved unavailable
plotting fields instead of reporting zero.

The review also recorded routing controls without enforcement, case-default
temperatures in the PyVista surface mapper, and volume eligibility checks after
output-directory creation. These are historical findings, not claims about the
current implementation.

Focused Python and viewer checks, package verification and two real WSL Code_Aster
smoke/reference tests passed. The full Python suite and full numerical
qualification were not rerun. Local evidence was retained under
`.build/cleanup/` and `.build/correctness/`; those paths are not shipped evidence.

Use the current owners above for supported behavior and the applicable
verification gates for any new engineering claim.
