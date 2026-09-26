# Shared Frontend and IFC Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development. Track steps below; the user has requested implementation with subagents in this session.

**Goal:** Improve the shared Studio/Gallery engineering workspace and connect real IFC exchange to it.

**Architecture:** Retain the vanilla JavaScript/Three.js viewer and Python Studio transport. Reuse scene mesh assets and IfcOpenShell; reference models remain separate from the engineering model. Conversion creates a new unsolved project and never overwrites authored source.

**Tech Stack:** Python, IfcOpenShell 0.8.4.post1, Three.js, Vite, Node test runner, pytest, Playwright.

**Spec:** `docs/superpowers/specs/2026-09-26-frontend-ifc.md`.

## Global Constraints

- Worktree: `D:/Gitprojects/Tuba_v4/.worktrees/frontend-ifc`; existing dirty changes copied as baseline. Preserve all of them.
- No commits, resets, stashes, cleaning, push, deployment, or external messages. Integrate only this task's changes after verifying the original checkout has not changed underneath us.
- Run Python with `$env:UV_NO_SYNC='1'; uv run ...`. Verify imports resolve to this worktree.
- Reuse installed dependencies. No third visualization surface, browser IFC dependency, invented solver results, or authored flat node dumps.
- Each implementer owns the listed files for its task and leaves a report in `.superpowers/sdd/2026-09-26-frontend-ifc/`.

## Review Focus

1. Derived objects without physical parents must remain searchable and selectable (Task 1).
2. Field switching and stage navigation must not reset user visibility or mislabel units (Task 1/3).
3. IFC units and nested rotations must produce correct metre geometry; missing engineering properties must block conversion (Task 2).
4. Malformed/oversized uploads, path traversal and cross-origin requests must not write outside project storage or mutate source (Task 2).
5. Missing IFC dependency, stale evidence and static hosting must produce honest capability states and preserve existing reviews (Task 2/3).

### Task 1: Shared engineering workspace

**Files:** `viewer/src/controls.js`, `selection.js`, `app.js`, `styles.css`, relevant result label helpers, `viewer/test/`; a small measurement helper if necessary.
**Interfaces:** Keep existing state/actions and object IDs. Extend `buildObjectTree(state, options)` with an explicit engineering grouping. Expose readable label functions shared by control/legend renderers. Measurement works from two selected geometric points with a metre distance converted through existing unit helpers.

- [x] Trace all callers of tree/selection/labels and add regression checks for a physical pipe plus deformed/mesh children, an orphan vector, search, and unchanged layer state.
- [x] Implement engineering grouping as default, expandable representations, readable names (`Displacement`, `Reaction force`, `Operating — actual deformation`), and retained detailed IDs.
- [x] Consolidate selection tools and implement explicit two-point measurement. Add the invariant `distance([0,0,0], [3,4,0]) === 5` and reject nonfinite/missing points.
- [x] Run `node --test test/controls.test.js test/find.test.js test/selection.test.js` plus new focused tests, then `npm test`.
- [x] Report changed files, commands/results and remaining limits for controller review. Do not build packaged viewer assets yet.

### Task 2: IFC backend and Studio transport

**Files:** `tuba/external/ifc*.py`, new `tuba/external/ifc_reference.py` if needed, `tuba/visualization/preview/server.py`, `transport.py`, corresponding focused tests.
**Interfaces:** Add an explicit `ifc` capability to `/api/project`. Provide same-origin Studio endpoints under `/api/ifc/`: reference preview/upload, attach/remove, export, and conversion download. Document exact request/response fields in the task report before Task 3. Reference geometry must use existing scene contracts and persist under a project-owned directory.

- [x] Trace current IFC exporter/importer, project scene publication, origin/body-size checks and evidence lifecycle.
- [x] Add a real IFC fixture test with millimetres and nested placement rotation. Assert imported coordinates in metres and exact expected bounds. Test GUID/property-set preservation and unsupported-object reporting.
- [x] Implement validated reference extraction with IfcOpenShell tessellation; preview first, persist only on attach; merge references into Build/Review scenes without changing the solver model. Preserve original source bytes.
- [x] Implement geometry IFC export; allow result properties only through existing verified fresh evidence access, otherwise explicitly limit to geometry export.
- [x] Implement selected supported straight-pipe conversion with mandatory explicit engineering properties. Return a new project ZIP containing original IFC and short procedural `model.py`; no mutation to the current project. Reject fitting/unsupported selections and unknown GUIDs. Test a roundtrip by running the produced script and checking positions/sections/materials.
- [x] Test malformed bodies, oversized files, traversal, foreign origins, dependency failure, persistence after restart, removal, and authored-file preservation with `uv run pytest -q` on the added/affected test modules.
- [x] Report endpoints, test evidence, files, and explicit conversion ceiling for independent review.

### Task 3: Exchange UI, Gallery artifacts and parity

**Files:** `viewer/index.html`, `viewer/src/app.js`, `styles.css`, new small exchange module if necessary; `scripts/build_pages.py`, `scripts/official_gallery.py` or existing bundle producer seam; `viewer/vite.config.js`; related tests and user documentation.
**Interfaces:** Consume Task 2 endpoint contract and Task 1 shared controls. Published downloads are declared by the bundle/catalog; no broken links for absent artifacts.

- [x] Add one native accessible exchange dialog: preview IFC, attach/remove reference, inspect warnings, map selected supported pipes to explicit material/section values and download new project, export current model. Static mode shows actual published downloads and a clear Studio requirement for uploads.
- [x] Add IFC properties to the existing inspector and keep references out of engineering result colouring.
- [x] Generate portable example project ZIPs (authored source, study and referenced local assets; no massive solver artifacts) and geometry-only IFC downloads during Gallery build where supported. Preserve existing optional-dependency semantics and catalog validation.
- [x] Add build identity (source revision/content fingerprint) accessible from both Studio and Gallery. Add parity coverage for shared controls, source read-only behavior, downloads and geometry-only states.
- [x] Run affected Node/Python tests, viewer build and browser checks on a real Studio and a generated static bundle using attested Code_Aster evidence. Inspect final rendered scene and the download/import flows.
- [x] Update concise docs explaining supported IFC conversion, reference-only semantics, optional installation and evidence limitations.

### Completion

- [x] Independent task and final review; address actionable defects and rerun covering tests.
- [x] Record verification and limitations here. Apply only changes relative to the preserved dirty baseline to the original checkout, after checking for concurrent edits.
- [x] Provide plan link, implementation summary, test scope, and any remaining explicit ceilings. Do not deploy.

## Verification and bounded scope

- Frontend: 373 Node tests passed; packaged Vite build passed.
- Publication: initial 105 Python tests passed. Follow-up: all 22 publication tests pass, and the full Pages build completed with 12 validated reviews, 12 project ZIPs, nine supported IFC exports and 12 captured thumbnails. Both Pages catalog/download smoke scenarios pass. Deployment was not run.
- Backend: 41 IFC/Studio/visualization tests passed after the exporter fixes. The final strict large-coordinate Axis/Body fix passed its two focused tests.
- Engineering evidence: a fresh support-rack solve completed with Code_Aster 18.0.12 via WSL. Existing RMED `NOE` import warning occurred; native CSV artifacts supplied the processed review. This task does not alter result import.
- Browser: Studio and generated Gallery shared controls, readable deformation states, IFC inspector GUID/property sets, published download links, Studio IFC download and reference removal were checked. The downloaded IFC was parsed and checked for absence of invented reaction properties.
- HTTP integration: actual millimetre IFC preview/attach, persistence in Build and Review, conversion ZIP script execution, reference removal and authored-script preservation were verified. The opt-in Chromium smoke now exercises actual file selection, preview, attach, conversion download, IFC export and removal. It executes the browser-downloaded project and checks selected geometry, engineering assignments, absence of solver state, and unchanged authored source.
- IFC limits: optional IfcOpenShell, 16 MiB raw file ceiling; geometry-only native export rejects unsupported geometry. Arbitrary uploads require Studio. Engineering conversion accepts selected straight pipes with matching two-point Axis and swept-disk Body, explicit engineering assignments, and produces a new unsolved project. Loads/supports still require authoring and Code_Aster evaluation.
- Existing WIP was carried into the isolated worktree, with original checkout hashes retained for conflict-checked integration. No commits, push or deployment.

Integration: 33 task paths copied to the original checkout after all baseline hashes matched. Existing unrelated result WIP verified byte-for-byte. No concurrent edits overwritten.
Post-integration: imports resolve to the original checkout; all 8 IFC reference tests passed there. Final Studio automatic Review and static Gallery both showed FE VMIS, actual deformation, and Viewer 2191c6594504.


## Publication and browser follow-up

- Pages CI installs the IFC extra so supported downloads are actually published. A catalog smoke check fetches every declared ZIP/IFC and verifies its signature.
- Beam/contact validation accepts the same attested optional internal-force family as other engineering reviews; required families and provenance checks remain strict.
- Built artifacts are served with Vite preview in tests and thumbnail capture. Development serving is unchanged. This removes dev transforms and watchers from artifact checks.
- Runtime-status locators distinguish the measurement live region; labels reflect the shared engineering terminology. The 43 MB contact history uses the existing 45-second gallery readiness budget; its three-regime test has a measured 180-second total budget while retaining full failure traces. The volume-tee readiness budget is 30 seconds. Engineering assertions are unchanged.
- Windows: all 13 Pages browser tests pass, including accessibility, contact state/forces, WebGL fallback, volume tee, profiles and responsive layout. The three visual baselines were inspected at 1440, 1024 and 800 px widths and the accessibility/visual test passed again without update mode; only separately validated content-hash labels are masked.
- Independent continuation and final code reviews found no actionable issues.
- Post-integration IFC smoke passed from the original checkout using real Chromium and IfcOpenShell, including execution of the downloaded conversion project.
- Follow-up integration: 21 task paths copied after conflict checks; original IFC smoke and preview-config test pass. No commits, push or deployment.
- Linux: the latest complete Pages run passed 12 of 13 cases with full tracing; the profile case exceeded its former 60-second overall budget after reaching the final interactions. With a test-local 90-second budget, the targeted profile rerun passed in 57.5 seconds with full tracing. All 13 cases are therefore covered by passing runs, rather than one all-green Linux suite invocation. The contact and tee budget adjustments passed in the complete run. All three Linux visual baselines were inspected and pass.
- Linux validation used Chromium in local WSL with the complete built artifact staged on ext4 and isolated dependencies. It was not a hosted GitHub Actions or deployment run. The owned test server stopped after completion.
- Final scoped review approved the profile timeout adjustment; all assertions and tracing are retained. All 21 follow-up paths match between worktree and original checkout, and the five tracked pre-existing frontend/result WIP paths remain unchanged from the continuation baseline.
## Local commit preparation

- User authorized a local commit without pushing. The saved dirty baseline was used to exclude the existing result-overlay Python edits and section-force component labels/scalar handling in the frontend. Existing working files are preserved.
- Packaged viewer assets were rebuilt from the isolated commit source, rather than committing a bundle containing uncommitted frontend work. The working checkout retains its existing bundle alongside that commit asset.
- The Gallery smoke validates the optional section-force field when present and retains all required field checks, allowing the committed feature to stand independently of the earlier result-overlay work.
- Commit-specific validation: all 373 frontend tests, the Vite build, 30 IFC/publication Python tests, real Chromium IFC exchange including converted project execution, and Gallery download smoke passed. Independent commit-scope review found no actionable issue. The broader Windows/Linux suite results above were obtained with the preserved working-tree baseline included.
- The commit-specific viewer also passed the accessibility/responsive visual test at all three recorded widths without changing snapshots.
