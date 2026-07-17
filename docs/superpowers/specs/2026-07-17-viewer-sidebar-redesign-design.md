# Viewer sidebar redesign: task presets + structured layer tree

Date: 2026-07-17
Status: approved (Approach A)

## Problem

The left sidebar of the viewer cockpit has three structural problems:

1. **Generated layer wall.** Every Code_Aster mesh group becomes its own
   top-level checkbox (~20 in the demo bundle). Layer ids are already
   hierarchical (`analysis_mesh:group:GN_N0`), but `buildLayerRegistry`
   (viewer/src/sceneLoader.js) flattens them and `labelForLayer` produces
   noisy labels ("Analysis Mesh Group GN N0"). Parent layers and leaves sit
   at the same visual level, and the all-layers-must-be-visible AND rule
   makes toggle interactions opaque.
2. **Dead nav weight.** Six nav items under three headings. "Display" is a
   lone item under a heading also named "DISPLAY". The "Load Cases" tab
   opens an empty panel (no home in `renderTaskPanel`); the load-case
   selector actually lives in the Results controls.
3. **No separation of concerns.** Navigation, task tools, and scene-display
   settings share one scrolling column.

## Design

### Navigation

Four tasks, no group headings: **Review, Model, Results, Issues**.
Remove the `load-cases` and `3d` ("Display") workflow tabs from the cockpit
rail. Embed mode keeps its current minimal behavior (3D-only); the internal
`3d` tab id remains for embed but is not shown as a rail task. Compliance
stays evidence-dock-only, as today.

### Task-driven visibility presets

Activating a task applies a visibility preset over layer *categories*
(via the existing `setLayerVisibility`):

| Task    | Visible categories                                    |
|---------|-------------------------------------------------------|
| Review  | Geometry, Results, Overlays                            |
| Model   | Geometry                                               |
| Results | Geometry, Results, Overlays (deformed shape, vectors)  |
| Issues  | Geometry, Overlays (markers)                           |

Analysis-mesh and envelope layers default off everywhere; users opt in via
the Display strip. Manual toggles after a task switch stick until the next
task switch (task switch re-applies its preset).

### Layer hierarchy (derived, no bundle change)

Derived at load time in the viewer from existing colon-namespaced ids:

- First segment maps to a category: `analysis_mesh:*` → Analysis mesh,
  `result:*` / `solver_result:*` / `deformed:*` → Results,
  `overlay:*` → Overlays, `physical_envelope:*` → Envelopes,
  `imported_components` and friends → Imported,
  object-kind fallback layers (e.g. `pipe`) → Geometry.
- `analysis_mesh:group:<name>` leaves nest under a "Groups" node inside
  Analysis mesh; leaf label is the last segment only ("GN N0", "MAT Steel"),
  counts kept.

No Python/builder changes; the scene bundle format is untouched.

### Display strip

A slim section pinned at the bottom of the sidebar, visible in every task:

- **Category switches** (~5): Geometry, Analysis mesh, Results, Overlays,
  Envelopes. Tri-state checkboxes (checked / unchecked / indeterminate from
  children). Toggling a category sets all its layers.
- **All layers** — one collapsed `<details>` containing the hierarchical
  tree for fine control (mesh groups under "Groups", cleaned labels).
- **Saved Views** — moves here from the old Display task panel.
- Overlays merge into this model (they are already layers with an
  `overlay:` prefix); the separate Overlays checkbox list is removed.

### Touched files

`viewer/src/workflowState.js` (tab list), `viewer/src/app.js` (nav render,
display strip, preset application), `viewer/src/sceneLoader.js` (category
grouping helper), `viewer/index.html` (display strip markup location),
`viewer/src/styles.css`, and the affected tests under `viewer/test/`.

### Error handling

Unknown layer-id namespaces fall into a catch-all "Other" category rather
than being dropped. Presets only touch categories that exist in the loaded
bundle.

### Testing

Extend existing node tests: layer categorization (id → category/label),
preset application on task switch, tri-state category toggle behavior,
nav renders four tasks and no empty panels. E2E smoke keeps passing.
