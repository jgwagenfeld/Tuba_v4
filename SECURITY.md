# Security boundaries

Tuba is a local Python authoring and Code_Aster engineering workflow. Opening a
project, its study or a construction unit executes trusted Python with the
current OS user's authority. Inspecting a project package does not execute it.
Browser geometry preview is unsolved; engineering results require Code_Aster.

## Local Studio

Studio and the launcher use a random capability for each launch. The owner gets
it through the launch URL fragment; APIs, project files and WebSockets require
it. Browser credentials are scoped to the exact origin, including the port.
Session discovery stores credentials separately in an owner-private directory.
Host, origin, revision and Fetch Metadata checks remain additional guards.
Development access requires an explicitly configured origin.
Developer clients must supply the capability themselves; foreign WebSocket URLs
do not automatically receive browser credentials.

These controls separate browser origins and OS users. They do not sandbox a
process already running as the same OS user. Keep Studio bound to loopback.

## Evidence and sharing

Imported engineering evidence must match the current model, operation,
SOLVER_OPTIONS and VOLUME_EXPORT, in addition to passing artifact hashes and
execution checks. Current study checks run before imported results publish.
Hashes alone do not prove that an independently supplied solver actually ran.

Source package export is project-contained by default. The developer API's
`external_sources` allowlist names each approved source and archive destination;
the planned manifest marks those external sources. Static dependency inspection
cannot discover every computed path or dynamic import.

Received report HTML is constrained by the local server. Web publication
regenerates reports and CSVs from validated review JSON and rejects additional
active browser files. CSV string cells and headers are spreadsheet-safe; actual
numeric values stay numeric. Browser scenes, archive metadata and native imports
have resource budgets. Native parser failures remain outside the Studio process.

## GitHub configuration required before publication

Repository files cannot create or guarantee administrator-enforced protections.
The publication preflight must succeed before privileged execution:

- Protect `main`, require reviewed pull requests and required qualification
  checks, and restrict bypasses and workflow-file changes.
- Configure `code-aster`, `release` and `github-pages` environments with required
  reviewers, prevent self-review, and allow only the `main` branch. Disable
  administrator bypass where supported. Give runner access only to trusted jobs.
- Restore the Code_Aster runner only in an isolated environment. It must not run
  arbitrary contributor refs or share credentials with untrusted workloads.
  Restrict runner admission to the approved `main` workflows where the GitHub
  plan supports it, or enforce admission outside the repository. A writer can
  otherwise add another workflow that omits these environment gates.
- Official Pages deploys the site generated and tested by the exact-revision
  Code_Aster qualification run, with an artifact digest inventory. Build tokens
  stay read-only; publication authority belongs to the protected deploy job.

On 2026-10-07, the read-only configuration check found `main` unprotected,
`github-pages` without required reviewers, and the registered Code_Aster runner
offline. No external repository settings were changed by this hardening work.

## Verification

Static scans do not replace runtime checks. Security fixes should reject the
adversarial input and preserve the legitimate workflow. Evidence changes need
real Code_Aster validation; browser isolation needs browser validation. Keep the
revision, checks and unresolved external requirements with each release.

The 2026-10-07 candidate passed focused Python regressions, 712 viewer tests,
real WSL Code_Aster execution and current-input rejection checks, and Chromium
Studio, report, IFC exchange and local-only Python-runtime checks. Native worker
limits were exercised on Windows; Linux limits still need runtime validation.
Hosted workflow execution and deployment were not performed.
