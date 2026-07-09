# Docs visual overhaul — deductive teaching with real renders

- Date: 2026-07-09
- Status: design, pending user approval
- Author: pairing session (Jan-Georg + Claude)

## Problem

The static docs site (`docs/site/`) teaches a 3D FEA piping tool using
JavaScript **Mermaid flowcharts** and **CSS-drawn "sketches"** — rotated `<span>`
"axes" (`.axis-sketch`), CSS rings/boxes for cross-sections (`.section-gallery`),
and CSS pseudo-diagrams (`.process-map`, `.artifact-lifecycle`, `.module-map`,
`.routing-sketch`). For a tool whose entire value is 3D geometry, coordinate
frames, and solver results, these teach almost nothing: they can't show how a
vector lives in 3D, how a local frame follows a pipe through a bend, or what a
section actually looks like extruded.

Meanwhile Tuba already renders **real, docs-grade 3D** headlessly. A candidate
spike (`scratchpad/render_candidates.py`, this session) produced three curated
stills from the real pipeline that decisively beat the CSS equivalents:

- **local frame along a route** — the red axial (local X) triad turning through an
  in-plane *and* an out-of-plane bend (replaces `.axis-sketch`);
- **section gallery** — all five section types as true extruded solids with
  visible bore and wall thickness (replaces `.section-gallery`);
- **placement frame** — labeled world triad + a rotated local placement frame with
  a pipe authored in local coords (new, deductive).

## Goal

Replace every Mermaid flowchart and CSS pseudo-graphic across all doc pages with
**real renders from the Tuba pipeline**, and restructure the explanations so the
3D mental model is built **deductively** (point → vector → frame → local system →
placement frame → moving builder frame → bend chord-vs-arc → section body → typed
model → solve/review). Keep genuinely useful structured content (reference tables,
step lists, prose).

## Locked decisions

1. **Scope: full visual overhaul** of all 10 pages in `docs/site/`.
2. **Medium: both, by role.** Curated annotated PNG **stills carry the teaching**
   (deliberate camera + labels, one per concept); a **live viewer embed on the pages
   where exploration earns its place** — at most one per page — (frames on Modeling,
   results on Tutorial/Examples, optionally route candidates on Autorouting). Text-only
   pages (commands, setup, developer) get stills only.
3. **Figure delivery: commit the PNGs** to `docs/site/assets/figures/`, with a
   committed generator as the regeneration source. GitHub Pages serves static
   images — no fragile headless-GL rendering in CI.
4. **Reuse only.** No changes to the rendering engine (`tuba/plotting`,
   `tuba/visualization`) or the viewer app (`viewer/`). We only *call* them.

## Ground-truth the content must respect (cited)

The deductive text must be correct to the code, not hand-wavy:

- A point is `Node.coords`, a NumPy `(3,)` float array in the model-global frame,
  meters; nodes dedup at `1e-6` (`tuba/model.py`).
- A `CoordinateSystem` is `origin` + an orthonormal, right-handed basis;
  `to_global_point(p) = origin + basis @ p`. Orthogonality and right-handedness are
  enforced at construction (`tuba/coordinates.py`).
- A `PlacementFrame` (IFC Axis2Placement3D): `axis` = local Z, `ref_direction` = local
  X hint; local X is Gram-Schmidt-projected off Z, local Y = Z × X; parents compose
  root-down (`tuba/placements.py`).
- The pipe builder is a **moving frame**: cursor `[0,0,0]`, forward `+X`, up `+Z`;
  `run` advances along forward, `bend` rotates forward about a plane-derived axis
  (`tuba/builder.py`).
- **Bend chord vs arc (the deductive "aha"):** `bend()` places the exit *node* at
  the tangent-intersection point (a straight FE chord between nodes) while the stored
  `BendGeometry` describes the *true circular arc*; they differ by the bend's rise
  (`tuba/builder.py`, `tuba/model.py` `make_bend_geometry`/`sample_bend_geometry`).

## Architecture

### 1. Figure generation pipeline (new)

- `docs/site/assets/generate_figures.py` — committed script, **one function per
  figure**. Each builds a small curated model (or loads a committed study) and writes
  a PNG to `docs/site/assets/figures/`. Uses only `tuba.plotting`
  (`build_model_scene(off_screen=True)`, `add_local_axes_to_plotter`,
  `_add_supports_to_plotter`, `build_route_plotter(off_screen=True)`,
  `export_screenshot`). Shared helpers (dark `#111827` background, fixed resolution,
  consistent triad scale, `reset_camera` + zoom framing) kept in the same file unless
  it grows past ~1 file's worth.
- **Result figures need no solver:** load committed studies from
  `notebooks/code_aster_results/` via
  `tuba.analysis.code_aster_notebook.load_or_run_code_aster_results(..., run_solver=False)`.
- `main()` renders all figures and prints a manifest. Re-run locally when figures
  change; commit the regenerated PNGs.

### 2. Interactive viewer embeds (wire up existing)

- Embed pattern already exists: `viewer/?bundle=<name>&embed=1` in an `<iframe>`
  (already present in `examples.html`). Reuse the `.viewer-panel` CSS slot.
- Bundles (already in `viewer/public/`, so `vite build` copies them into
  `dist/` → `_site/viewer/`):
  - `imported_component_mixed_demo` → Modeling (global gizmo + live local-axis triad
    at a real placement) — teaches frames live.
  - `code-aster-review` → Tutorial + Examples (deformed + stress result review).
  - Autorouting: use route-candidate **stills** primarily; add a live route bundle
    only if a small one can be exported cheaply (`build_visualization_scene` +
    `write_scene_bundle`), else keep the "Open in viewer" link.
- **CI/delivery fix:** `.github/workflows/tuba-pages.yml` already builds `viewer/`
  and copies `dist` → `_site/viewer`. Verify the needed bundle dirs land under
  `_site/viewer/<bundle>/` and that `examples.html`'s iframe target resolves
  (currently `docs/site/viewer/` is empty locally — it exists only post-build).
  Document a local `vite build` step so the user's `127.0.0.1` preview shows embeds.

### 3. Page structure + CSS

- **Remove:** all `class="mermaid"` blocks, the `diagrams.js` include and file, the
  Mermaid CSS, and the CSS pseudo-graphic classes: `.axis-sketch`/`.axis*`,
  `.section-gallery`/`.section-visual`/`.pipe-ring`/`.bar-solid`/`.cable-dot`/
  `.rect-box`/`.ibeam-shape`, `.routing-sketch` and its children, and the
  picture-like `.process-map`/`.artifact-lifecycle`/`.module-map` uses.
- **Add:** a `.figure` / `figcaption` / `.figure-grid` pattern (dark figure frame
  inside the light page, matching `.viewer-panel`), and keep reusing `.viewer-panel`
  for embeds.
- **Keep:** reference tables, step lists, prose, notes/warnings. Where a flow was a
  Mermaid chart, replace it with either a **real render sequence** (model → deformed →
  reviewed) or a clean textual step list — not a fake flowchart.

## Deductive spine (Modeling / "how it works")

Each rung = one real figure + tight prose grounded in the cited ground-truth:

1. A point is three numbers in the world frame.
2. A direction is a vector; a frame is three orthonormal vectors (element local triad).
3. A local coordinate system = origin + right-handed basis; `to_global = origin + R·p`.
4. A placement frame = axis (local Z) + ref_direction (local X); Y = Z × X; parents compose.
5. The pipe builder is a *moving* frame: run advances, bend rotates it (route figure).
6. A bend: FE nodes sit at the tangent chord; `BendGeometry` stores the true arc.
7. Sections give the 1D centerline a 3D body (section gallery).
8. The model is a typed graph → validate → export → solve → import → review (money-shot).

## Figure inventory (finalized in the plan)

| id | figure | entrypoint | primary page |
|----|--------|-----------|--------------|
| F1 | element local triad | `build_model_scene` + `add_local_axes_to_plotter` | Modeling |
| F2 | local vs world placement frame | `PlacementFrame.to_coordinate_system` + arrows/labels | Modeling |
| F3 | builder frame through 2 bends | candidate A | Modeling |
| F4 | bend chord vs true arc | element mesh + `sample_bend_geometry` overlay | Modeling |
| F5 | five sections extruded | candidate B | Modeling |
| F6 | support glyph types | `_add_supports_to_plotter` (anchor/guide/rest/spring) | Modeling |
| F7 | tutorial model (geometry only) | `build_model_scene` | Tutorial |
| F8 | deformed + Von Mises money-shot | `build_model_scene(results, deform_scale)` from committed study | Tutorial/Overview/index hero |
| F9 | pre-route scene | `build_route_plotter(off_screen=True)` | Autorouting |
| F10 | route candidates + envelopes | `build_route_plotter(..., result=...)` | Autorouting |

Additional per-page stills (workflow sequence, developer module render, commands/setup
imagery) enumerated during planning; the pattern is identical.

## Per-page plan (summary)

- **index.html** — hero real render (F8); drop any flow-strip pseudo-graphic.
- **tutorial.html** — remove Mermaid + `.process-map` + `.artifact-lifecycle`; add F7
  (model), F8 (result), and a `code-aster-review` embed; keep the code + tables.
- **modeling.html** — the deductive spine (F1–F6) + an `imported_component_mixed_demo`
  embed; keep the reference tables and error-boundary/validation tables.
- **overview.html** — replace `System map` Mermaid/`module-map` with a real system
  render + concise text.
- **workflow.html** — replace `Execution sequence` Mermaid with a model→deformed→
  reviewed render sequence or a step list.
- **autorouting.html** — replace Mermaid + `.routing-sketch` with F9/F10 (real route
  scenes); optional live route bundle.
- **developer.html** — replace `Module dependency picture` Mermaid with a real render
  or a plain textual map; keep ownership tables.
- **commands.html / setup.html** — mostly text; remove any pseudo-graphics, add one
  real render where it helps.
- **examples.html** — fix/keep the `code-aster-review` embed; add supporting stills.

## Testing & verification

- **Rewrite** `tests/test_static_site_docs.py::test_core_docs_include_visual_diagrams`
  (currently asserts Mermaid/`diagrams.js`/`section-gallery`/`axis-sketch`/
  `routing-sketch`/`artifact-lifecycle` are **present**). Invert it: assert each page
  references real `assets/figures/*.png` and/or a `viewer/?bundle=…` embed, asserts
  **absence** of `class="mermaid"`, `diagrams.js`, and the removed sketch classes, and
  that every referenced figure file exists on disk.
- **Add** `tests/test_docs_figures.py`: import `generate_figures`, run each figure
  function `off_screen`, assert a non-empty PNG is produced (mirrors
  `tests/test_plotting_scenes.py`, which renders `off_screen=True` without a skip
  guard — the test env has a GL context).
- Keep green: `tests/test_current_api_docs.py`, `tests/test_examples.py`,
  `tests/test_operating_state_example.py`, and the rest of `test_static_site_docs.py`.
- **Playwright browser sweep** (as in the prior modeling.html pass): all 10 pages,
  desktop + mobile, assert figures/embeds load, sidebar/nav work, and **no horizontal
  overflow**.

## Non-goals / risks

- Non-goal: touching `tuba/plotting`, `tuba/visualization`, or `viewer/` internals.
- Risk: figure regeneration needs a local GL context (works here; committed PNGs mean
  CI never renders). Document the local regen command.
- Risk: repo weight — ~10–14 PNGs at ~1600×1000 add a few MB; acceptable, optional
  `pngcrush`/downscale in the generator.
- Risk: the bend chord-vs-arc figure (F4) is the one custom-drawn still (overlay the
  sampled arc on the FE chord); medium effort, high teaching payoff.

## Done when

- No page contains a Mermaid block, `diagrams.js`, or a CSS pseudo-graphic sketch.
- The Modeling page teaches the deductive spine with real figures; every page's
  removed flowchart/sketch is replaced by a real render or a live embed.
- `generate_figures.py` reproduces every committed figure headlessly with no solver.
- Embeds resolve after `vite build` + Pages copy; `examples.html` iframe points at a
  real bundle.
- Rewritten docs test + new figure test pass; Playwright sweep is clean.
