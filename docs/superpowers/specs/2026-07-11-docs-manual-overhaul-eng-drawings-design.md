# Docs manual-grade overhaul + real engineering cross-sections

- Date: 2026-07-11
- Status: design, approved (drawing style + scope locked); pending spec review
- Author: pairing session (Jan-Georg + Claude)
- Supersedes/extends: `2026-07-09-docs-visual-overhaul-design.md` (that pass replaced
  Mermaid/CSS sketches with real 3D renders; this pass raises content to manual grade
  and replaces the one figure that is a *render pretending to be a drawing*).

## Problem

The static docs site (`docs/site/`, 10 pages) already renders real 3D stills from the
Tuba pipeline. Two problems remain:

1. **The cross-section figure is stylized slop.** `assets/figures/sections.png`
   (`fig_sections` in `generate_figures.py`) is a floating isometric render of five
   extruded solids on a dark background. It has **no dimensions, no bore/wall callouts,
   no hatching, no orthographic section view** — it is a picture, not an engineering
   drawing. For the one concept that is inherently a 2D dimensioned detail, a 3D render
   teaches less than a real section drawing would.
2. **Content is uneven and incomplete for a professional manual.** The reference site
   (`tuba-v2.readthedocs.io/en/new_dev/`) is shallower than v4 overall, but its canonical
   spine is instructive: Installation → *How to Start* (one worked script decomposed
   line-by-line, then run + result analysis) → grouped Command reference → Developer
   (class docs, naming conventions, how to write a macro). Measured against a manual of
   that shape, v4 has concrete gaps on every page (audit below), the largest being
   `commands.html` (one-line entries, no signatures, ~18 shipped public APIs undocumented).

## Goal

- Replace `sections.png` with **true 2D dimensioned engineering section drawings**,
  generated from the real Tuba section objects so they cannot drift from the model.
- Raise all 10 pages to a consistent **manual grade**: real signatures/params, the
  currently-undocumented subsystems, a glossary, an architecture drawing, deeper
  install/tutorial/developer content — while keeping every claim honest to the code and
  preserving the export-vs-solved-result boundary.

## Locked decisions (user-approved)

1. **Drawing style: 2D dimensioned detail sheets.** White sheet, ISO 45° section hatch
   on cut material only, chain-dash centrelines, dimension lines with arrowheads +
   extension lines, `Ø`/`R` callouts, per-detail title + a title-block/legend. Crisp
   **SVG**. A style prototype (`scratchpad/proto_sections.py`) was rendered and approved.
2. **Scope: full manual-grade overhaul** of all 10 pages plus the drawings.
3. **Modeling layout: one combined section plate** (all five details + title block on a
   single sheet), with the engine also emitting individual detail SVGs for reuse.
4. **Reuse only.** No changes to `tuba/` runtime, `tuba/plotting`, `tuba/visualization`,
   or `viewer/` internals. The drawing generator only *reads* section objects.

## Ground truth the content must respect (cited)

### Section API and real dimensions (from `tuba/model.py`, `tuba/geometry/profiles.py`)

`profile_for_section(section)` (in `tuba/geometry/profiles.py`) returns the exact
dimensioned truth per kind — this is the single source the drawing generator reads:

| kind | `add_*` call (as used in `fig_sections`) | dims returned | drawing |
|---|---|---|---|
| pipe | `add_pipe_section("DN100", OD=0.1143, WT=0.00602, corrosion_allowance=0.001)` | `OD, WT, ID=OD-2·WT` | annulus, hatch wall, `Ø`OD, `Ø`ID bore, WT leader |
| bar | `add_bar_section("Bar", OD=0.18, WT=0.0)` | `OD, WT` (0 = solid) | filled disc, `Ø`OD |
| cable | `add_cable_section("Cable", radius=0.04, pretension=500.0)` | `radius, pretension` | filled disc, `R`, pretension note |
| rectangular | `add_rectangular_section("Box", height_y=0.24, height_z=0.14, thickness_y=0.012, thickness_z=0.012)` | `height_y, height_z, thickness_y, thickness_z` | RHS, hatch wall band, height_y (Y, horiz), height_z (Z, vert), wall t |
| ibeam | `add_ibeam_section("IBeam", "HE200B")` | `H, B, Tw, Tf` (+ `R` from catalog) | I with root fillets, H, B, Tw, Tf |

- Real values: DN100 = OD 114.3 / WT 6.02 / ID 102.26 mm. Bar = Ø180. Cable = R40,
  pretension 500 N. RHS = 240×140, wall 12. HE200B = H200 · B200 · Tw9 · Tf15 · R18
  (root radius `R` from `SectionCatalog.default().get_ibeam_profile("HE200B").dimensions`).
- Section-plane convention: cut normal to the member axis; **local Y horizontal, local Z
  up** (matches matplotlib y-up; no flip). Pipe validation: `OD>0, WT>0, 2·WT<OD`.

### Public API surfaces implemented but NOT on `commands.html` (fill these)

`model.solve(solver="code_aster")` (`model.py:1095`); `tuba.compliance` —
`ASMEB313Evaluator`/`ComplianceReport` (`asme_b313.py:334`), `compute_sif_set`/`compute_sifs`/
`flexibility_factor` (`sif.py:220`); `tuba.optimization` — `GeneticSupportPlacer`/
`RuleBasedSupportPlacer`/`LLMSupportOptimizer` (`optimization/__init__.py:8`);
`quantity_takeoff` (`quantities.py:53`), `wind_loads` (`quantities.py:77`);
`analyze_load_paths` (`load_path.py:43`); `RuleEngine`/`ClashFreeRule`/`SupportSpacingRule`/
`rule_report_to_markdown` (`rules.py:56`); `ClashEngine`/`TrimeshClashEngine`/
`clash_report_to_markdown` (`tuba.clash`); `IfcExporter`/`IfcImporter`, `bom_to_csv`/
`bom_to_dict` (`external/__init__.py:3`); `add_bar_section`/`add_cable_section`
(`model.py:547`,`552`); `define_tee`/`define_load_case` (`model.py:1006`,`901`);
`assign_attribute`/`assign_insulation`/`add_insulation_spec` (`model.py:825`,`844`,`805`);
`place_fragment`/`add_placement_frame`/`assign_placement`/`to_global_point`
(`model.py:1056`–`1081`); `to_json`/`from_json`/`to_dict`/`from_dict` + `MODEL_SCHEMA_V4`,
`ModelPatch`/`ModelTransaction` (`model.py:1291`,`1445`); `FEAResults.get_displacement`/
`get_reaction`/`get_max_von_mises`/`plot_temperature`/`export_ply`/`export_gltf`
(`solver/base.py:80–148`); mixed-model `add_port`/`connect_pipe_to_port`/
`add_analysis_region`/`add_coupling`/`add_mesh_group` (`model.py:592–612`); viz extras
`build_scene_diff`/`apply_scene_diff`/`preview_python_script`/`write_static_report`/
`export_bcf_topics` (`visualization/__init__.py:28–34`). **Every documented signature
must be verified against the code before it is written — no invented parameters.**

### Per-page gap audit (drives the deepening)

- **tutorial.html** — add: run-it + expected console output; a result-reading walkthrough
  (max Von Mises / displacement, colour scale, pick max location) for the embedded viewer;
  SI units table; explain `allowable_stress` temperature-keying; `bend` vs `bend_to` note.
  Keep the strong line-by-line spine.
- **overview.html** — add: a real **data-flow architecture drawing** (model → validate →
  export → solve → parse → state → review); a **glossary**; name shipped subsystems
  (compliance, optimization, clash, BOM/quantities, IFC, rules, load-path); scope/non-goals.
- **workflow.html** — turn "Execution sequence" prose into an explicit
  export→run→parse→state→scene step/state list; fix "two paths" vs three; say what
  `model.validate()` checks; cover partial-solve / `None`-result branches; reconcile
  `model.solve(...)` one-call vs staged path with overview.
- **autorouting.html** — add: cost-model formula + `cost_breakdown` units; `RoutingSpace`/
  `RoutingZone` example; `PipeRouteResult`/`PipeRouteCandidate` field table; sample
  `route_report.md`. Keep the (already strong) troubleshooting + limitations.
- **commands.html** *(largest)* — full **signatures/params/units/defaults/returns**; add the
  undocumented subsystems above; enumeration tables (support `type=`, section kinds,
  operation-field quantities, order strategies); a `FEAResults` accessor table; optional
  v2→v4 command cross-map.
- **examples.html** — expected output per example; reconcile the example table with the run
  block (verify script names exist); difficulty/prereq ordering (export-only vs needs
  Code_Aster); link each row to its manual section.
- **setup.html** — prerequisites (Python version, OS matrix, RAM/disk); **how to obtain/build
  `run_aster`** (the `~/bin/run_aster` wrapper) not just reference it; git clone/bootstrap
  step; `[notebook-viz]` extra + optional deps → features; full `TUBA_CODE_ASTER_*` /
  `exec_method` env-var table; passing-doctor sample output.
- **developer.html** — **class/dataclass reference** (Material, PipeSection, Node, Element,
  BendGeometry, Operation, FEAResults, ResultState, PipeRouteCandidate — fields, invariants);
  naming conventions (id schemes, `study_*` files); **how to extend** (new builder method,
  new section type, new `BaseSolver` backend at `solver/base.py:158`); serialization/patch
  contract; add compliance + optimization to the module map.

## Architecture

### 1. Section-drawing generator (new)

`docs/site/assets/generate_section_drawings.py` — committed, matplotlib (already installed
in `.venv`; **no OpenGL**, so CI-safe unlike the PyVista figures). Structure mirrors the
approved prototype:

- **Draughting primitives** (module-level helpers): `_arrow` (double-arrow `<|-|>` dim
  line), `dim_h`/`dim_v` (dimension with extension lines), `leader`, `centrelines`
  (chain-dash), `hatch` (45° lines clipped to a material `Patch` via `set_clip_path`).
- **Palette from site tokens:** object `#1b2026` (≈`--ink`), dimensions/centrelines
  `#2f6374` (`--steel`), hatch `#9aa3ad` (≈`--muted`), inner edges `#5b636d`, sheet white.
  Line weights: object 2.3, inner 1.6, dim 1.05, ext/centreline 0.85, hatch 0.7.
- **Five detail renderers** (`draw_pipe/bar/cable/rect/ibeam`) each taking the dims dict from
  `profile_for_section`; I-beam outline built with 4 true root-fillet arcs (validated).
  Diameter sign rendered as `Ø` (U+00D8; DejaVu-safe — avoid `⌀`/`⟂` which tofu).
- **Searchable text:** set `plt.rcParams["svg.fonttype"] = "none"` so dimension text is
  emitted as real `<text>` (not outlined paths) — smaller files, selectable text, and
  makes the data-driven drawings test possible.
- **Composition:** `main()` builds the real sections (same values as `fig_sections`),
  reads dims, renders (a) the **combined plate** → `assets/figures/sections.svg` (2×3 grid:
  five details + title-block/legend), and (b) **individual detail SVGs** →
  `assets/figures/section_pipe.svg` etc. for reuse on other pages. Prints a manifest.
- **`sections.png` retirement:** the modeling page and the docs test move from
  `sections.png` to `sections.svg`. Delete the now-unused `fig_sections` from
  `generate_figures.py` and drop `sections.png`. (All other `generate_figures.py` figures
  stay.)
- **6th drawing — bend geometry detail:** a 2D dimensioned bend detail (bend radius `R`,
  angle, tangent-intersection point, and the chord-vs-arc rise) → `assets/figures/bend_detail.svg`,
  complementing the existing 3D `bend_chord_arc.png` on Modeling. Built in the same module.

### 2. Architecture data-flow drawing (new, for overview)

A clean 2D flow drawing (same matplotlib draughting module, boxes + arrows, no fake
"sketch" CSS) → `assets/figures/dataflow.svg`: `Model → validate → export study →
Code_Aster → parse artifacts → ResultState → review (PyVista / web bundle)`. Emitted by a
`draw_dataflow()` in the same generator.

### 3. Page structure + CSS

- Add a `.figure--sheet` modifier (light sheet framing) so white SVG drawings sit cleanly
  where the existing `.figure` frame is dark `#111827`. SVGs also carry their own sheet, so
  they degrade gracefully.
- Reuse existing `.reference-table`, `.code-grid`, `.note`, `.error-stack`, `.viewer-panel`
  patterns for new content. New: a `.glossary` definition list and a `.api-entry` block for
  signature/param/return reference on `commands.html` (semantic, table- or dl-based; no new
  JS).
- Keep all existing viewer embeds and 3D figures; keep the left-sidebar nav.

### 4. Tests

- **Update** `tests/test_static_site_docs.py`:
  - `test_pages_use_real_figures_not_sketches`: modeling requires `sections.svg` (not
    `sections.png`); assert `sections.png` is gone; keep the forbidden-sketch/embeds asserts.
  - `test_site_contains_current_workflow_and_reference_pages` /
    `test_modeling_docs_explain_core_beginner_concepts`: extend required phrases to pin the
    new manual-grade sections (glossary term, a real signature marker, the run/expected-output
    heading, etc.) so regressions are caught.
- **Add** `tests/test_section_drawings.py`: import `generate_section_drawings`, run
  `main()` into a tmp dir, assert each SVG is non-empty, is well-formed XML, contains
  `<svg`, and embeds the real dimension strings (`Ø114.3`, `200`, `HE200B`, `Ø180`,
  `240`, `R40`) — proving the drawing is data-driven, not a static asset.
- Keep green: `test_current_api_docs.py`, `test_examples.py`, `test_operating_state_example.py`.
- **Playwright sweep** (as in prior passes): all 10 pages, desktop + mobile — figures/embeds
  load, nav works, **no horizontal overflow**, new SVGs render.

## Decomposition (implementation increments)

Each increment is independently shippable and gets its own writing-plans plan.

1. **Drawings + Modeling** — `generate_section_drawings.py` (five details + plate +
   individual SVGs + bend detail), `sections.png`→`sections.svg` swap in `modeling.html`,
   retire `fig_sections`, CSS `.figure--sheet`, updated docs test, new drawings test.
   *Done when:* the plate renders from real dims headlessly with no GL/solver; modeling shows
   it; tests pass; Playwright clean.
2. **Commands reference completeness** — full signatures + the undocumented subsystems +
   enumeration/`FEAResults` tables; every signature verified against code.
3. **Tutorial / Workflow / Overview** — run-it/expected-output, result-reading, units,
   validate-checks, glossary, `dataflow.svg` architecture drawing, subsystem naming.
4. **Setup / Examples / Developer** — install depth (`run_aster`, prereqs, env table),
   example expected-output/reconciliation, class reference + naming + extension how-to.

Implementation drives the deepening with **grounded parallel writers** (each reads the real
code for its page/subsystem; independent verification pass rejects any invented API). The
drawing engine is authored + visually verified directly, not fanned out.

## Non-goals / risks

- Non-goal: touching `tuba/` runtime, plotting, visualization, or viewer internals; adding
  new runtime dependencies (matplotlib is already present).
- Risk: an invented/incorrect signature. Mitigation: every documented API is code-verified;
  a review pass greps each documented symbol against the source.
- Risk: SVG-in-`.figure` contrast (white sheet on dark frame). Mitigation: `.figure--sheet`
  + self-contained sheet in the SVG.
- Risk: scope creep across 8 content pages. Mitigation: increments; each ships and is tested
  before the next.

## Done when

- `sections.png` is gone; `modeling.html` shows a real dimensioned **section plate** rendered
  by `generate_section_drawings.py` from the live Tuba section objects; a bend detail and an
  overview data-flow drawing exist.
- Every page meets its audit targets; `commands.html` documents the previously-undocumented
  public surfaces with verified signatures; a glossary and architecture drawing exist.
- No invented APIs; export-vs-solved boundary intact; no Mermaid/CSS-sketch regressions.
- Updated docs test + new drawings test pass; Playwright sweep clean.
