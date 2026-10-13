# Studio workflow and frontend review

Reviewed 2026-10-13 against `805ba78`, with parallel assessments of Build,
Solve and hydraulics, and Review, search history and gallery navigation.
The shared shell was inspected in a browser against a local Studio with retained
Code_Aster results. This is an interface review, not a new solver qualification
or a Pages publication check.

## Direction

Keep the engineering sequence clear: author a Python model, update its geometry,
solve with Code_Aster, then inspect the imported results. Preserve the existing
Build and Review workspaces, with Solve as an action between them. Keep solver
identity, field applicability, stale-result status and display units visible.
Move occasional tools and provenance out of the primary action row, and show
the next step beside a blocked action.

## Findings and changes

| Area | Friction found | Change |
| --- | --- | --- |
| Navigation | Profiles, imports, exports and technical metadata competed with the main workflow; keyboard help had no visible entry point. | Group occasional actions under **Tools & files**, label downloads **Files & export**, and add **Help** with workflow guidance and keyboard shortcuts. Technical details remain accessible at compact widths. |
| Stage loading | A live Build transition took about six seconds without an immediate response. | Announce **Opening Build…** or **Opening Review…**, disable repeat stage changes during loading, and publish the stage and URL only after a successful load. |
| Build | Local **Run** and browser **Update geometry** described the same authoring step differently. | Use **Update geometry** consistently; preserve Ctrl+Enter and browser Stop, and state local saving behavior. |
| Build | Line-count comparison left source-linked editing active after same-length source changes. | Compare complete normalized source with the executed source before offering source links or editable lengths. |
| Build | A saved Python failure appeared unsaved because the footer compared against the last successful execution. | Derive disk-save feedback from the accepted disk source; state when 3D still shows the last good run. |
| Solve | Disabled controls explained prerequisites only on hover. | Add visible, announced guidance for pending edits, source errors, missing studies, hydraulic prerequisites and active jobs. This does not claim runtime availability. |
| Solve inputs | Changing Case while viewing Solver .comm could leave the previous case's input on screen. | Refresh the selected input immediately and retain request guards against late responses. |
| Failures | Solver output could be discarded by a header repaint. | Retain the latest error in a separate **Last error output** disclosure inside Technical details. Disconnection messages explain how to reconnect. |
| Review | Result-finding dispositions were counted and described as issues. | Report recorded issues and result findings separately, including historical recorded subjects. |
| Review | Plotting a run could open a nested disclosure inside a closed drawer. | Open the enclosing review drawer before scrolling to the diagram. |
| Review | Legacy hotspot rows shared a focus key. | Include the selected object identity to preserve keyboard focus on the intended finding. |
| Process drawing | A schematic without instrumentation still offered **Open P&ID**. | Name the entry **Open schematic** and the dialog **Process schematic** when no P&ID is declared. |
| Search history | Comparing parameters could replace a chosen reference/finding view and lose an in-flight load's status. | Preserve the view and its status during comparison; reject late failure updates from superseded requests. |
| Accessibility | Shortcut help used an unstyled modal-like div, without native modal focus behavior. | Use a styled native dialog, Close and Escape, focus restoration, and inactive viewport shortcuts while a dialog is open. |

The simplification keeps the features available. Authored Python, project files,
solver admission rules and result artifacts are unchanged by these interface edits.

## Larger improvements to schedule separately

1. **Study setup inside the authoring workflow.** Model-only projects need a
   usable path to create or edit `study.py`, with load-case and solver-option
   validation. Help now explains the prerequisite; designing an editor or
   scaffolding flow needs its own source-preservation and validation work.
2. **Project picker error recovery.** Folder-browser failures currently update
   a status behind the active dialog in `tuba/studio_launcher.py`. Show the
   error inside that dialog and prevent selecting a previous folder after a
   failed navigation. This backend-served UI was reviewed but not changed here.
3. **Solver connection recovery.** Explain reload on disconnection now; a
   reconnect-and-reconcile flow should recover actual job state and preserve
   pending drafts without inventing progress or cancelling someone else's job.
4. **A lighter process sidebar.** Keep a compact drawing entry and selected
   component summary in the rail; use the existing full-size dialog for the
   detailed schematic and port values. Preserve linked 3D selection and
   declared inputs versus measured results.
5. **Gallery onboarding and search discoverability.** Source-level review does
   not establish freshness of gallery bundles or published screenshots. Run
   the repository's Pages verification workflow before changing or publishing
   those artifacts.
6. **Generated input latency.** The live Solver .comm view remained at
   **Generating…** beyond a 60-second browser deadline. Its API handler calls
   `export_study` into a temporary directory, using the same export selection
   as Solve. This is a separately observed limitation; the case-switching
   regressions pass, but completion of this native generated-input request
   was not verified. Investigate its runtime before adding caching or a job
   flow, and preserve source/case identity for any reused input.

## Verification boundaries

Behavioral regression tests cover case switching and late requests, exact source
mapping, accepted saves with failed execution, busy-state transitions, review
record counts, retained search views and status, preserved error output, and
opening the enclosing review drawer. Browser smoke checks use the existing
Code_Aster-backed review, block API writes, and compare the authored source hash.
The checked viewports are desktop, compact desktop and phone width.

- All **845 viewer tests passed** against the final implementation.
- Frontend-only Vite compilation passed. It retains the existing large
  application-chunk advisory; a full Python/runtime package was not rebuilt.
- Navigation and changed-surface accessibility passed at **1440 x 900**,
  **900 x 650** and **390 x 844**, with zero JavaScript errors and API writes.
  The live authored source hash remained unchanged.
- Generated-input completion is excluded from that successful navigation
  receipt and has separate retained failure evidence. A fresh Code_Aster run,
  full backend suite and Pages readiness were not checked.

Frontend compilation is separate from installing the viewer, building Pages,
running the backend suite, or executing a fresh Code_Aster solve. No deployment
or publication is implied. Task logs, screenshots, the design scan and the
browser receipt are retained outside source at
`D:\tuba-runs\Tuba_v4\frontend-polish-20261013`.
