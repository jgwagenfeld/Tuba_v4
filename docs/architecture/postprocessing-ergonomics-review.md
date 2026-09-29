# Postprocessing Ergonomics — Review and Benchmark

**Date:** 2026-09-29
**Scope:** the results-review UX of both display paths — `tuba/plotting/` (PyVista) and
`tuba/visualization/` + `viewer/` (Three.js web scene) — benchmarked against commercial
piping stress software and structural FEA post-processors.
**Status:** review only. No code changed. Every proposal below is a proposal.

---

## 1. Method

Three sources, kept separate so the reader can weight them:

| Source | What it gives |
|---|---|
| Repository survey | current affordances, file:line, on both paths |
| Commercial piping benchmark | CAESAR II, AutoPIPE, CAEPIPE, PASS/START-PROF, Codeware, Triflex, AVEVA/E3D, PSI |
| Structural FEA benchmark | ANSYS, Abaqus, COMSOL, Inventor/SolidWorks, Femap, Patran, SCIA, MIDAS, CSI/STAAD, SOFiSTiK, LS-DYNA, and the open-source stack (Code_Aster + SALOME/ParaViS, PrePoMax/CalculiX, Elmer, FEniCS, ParaView) |

The two benchmark sets were gathered independently. Where they agree, the finding is about
engineering practice. Where they disagree, the finding is about product posture — and
those disagreements are the most useful part of this document.

---

## 2. Where Tuba stands today

Not a list of features — a list of *postures*, because posture determines which gaps are
real bugs and which are correct refusals.

**Tuba is a Layer-1 tool that has refused Layer 3 on principle, and has quietly built
part of Layer 2.** See §3 for the layer model.

### 2.1 The web-scene path is far more capable than a first glance suggests

Not documented as a capability list anywhere, so worth stating: the viewer already has
true 6-plane clipping (`app.js:1931`), a hotspot list with rank and utilisation
(`resultReview.js:276`), a stress threshold filter (`app.js:1264`) *and* a separate
utilisation threshold filter (`app.js:1205`), saved views (`controls.js:258`), a click
probe that reports value + rank (`selectionSummary.js:245`), a 13-table report bundle with
`governing_entity_ref` / `governing_location` (`reporting/tables.py:712`), a mesh
discretisation badge in the status strip, unit-system switching, and — most unusually —
a **contact review surface** with stage navigation, an increment scrubber, a per-shoe
friction chart against the Coulomb envelope, and a generated findings narrative
(`contactReview.js`, `analysis/contact_findings.py`).

That contact surface is, feature-for-feature, ahead of every commercial tool in the
piping benchmark. AutoPIPE's friction is a `Cone usage` column; CAESAR II's is an
`Ignore Friction` toggle. Tuba is the only one surveyed that treats a sliding support as
a *state history with a mechanism story*. **This is the pattern the rest of the UI should
follow, and it currently is the exception.**

### 2.2 The trust posture is already a differentiator, and it is already visible

ADR 0002 commits to "generic FE VMIS never implies code utilization". The implementation
holds that line hard: `compliance_role` is stamped on every stress field
(`builders/_results.py:182,196,215,447,902,927,967`), rendered as a badge in the viewport
legend *and* the status strip *and* the field details panel, deliberately three times so it
cannot be scrolled away from the numbers it qualifies.

Now compare that to what the incumbents actually do:

- AutoPIPE **silently sets the ASME NB eq-10 stress ratio to zero** whenever eq 12/13
  govern. The manual repeats this three times across three pages; a reviewer who does not
  read the note sees a *lower* ratio than reality.
- AutoPIPE **omits KHK Seismic Level 2 bends from the colour plot entirely**, silently.
- CAESAR II reports an **allowable of 0** for B31.1 operating cases, which floods
  Eng-Tips with "is this a bug?" threads.
- AutoPIPE's leftover result filters **silently produce blank reports**; the documented
  recovery is a five-step checklist.
- Bentley's own support KB gives the literal review procedure: *generate a text report,
  then Ctrl-F for `**`*.

Every one of those is a case where a tool's display **lies by omission or by a number that
means something other than it says**. Tuba's duplicated compliance badge is the correct
response to exactly that failure mode, and it is already shipped.

**The problem is not the posture. It is that honesty is currently implemented as a
*label* rather than as a *workflow*.** A badge is something you read once and then ignore.
Nothing in the UI currently makes the honest choice the easy choice.

### 2.3 The PyVista path is a plotting convenience, not a review surface

`tuba/plotting/plots.py` gives six `plot_*` functions and four exporters. No clipping, no
threshold, no probe, no section, no animation, no report, no table. It is correctly scoped
as "quick-look & export" per the two-path rule in `AGENTS.md`, and it should stay that
size. Two things are defects rather than scope:

- `plot_reactions` covers **forces only**; moments exist solely on the web path.
- `plot_temperature` writes a single **constant** `TEMP` scalar per element
  (`pipeline.py:532,539`) — it renders the case temperature, not a spatial field, under a
  name that implies a field.
- `plot_deformed_stress` **returns `None silently** when no `.rmed` and no model are
  reachable (`plots.py:520-537`).

---

## 3. The benchmark, stated as a model

The FEA survey converged on a three-layer architecture that every serious tool reaches
from a different direction:

```
Layer 3  VERDICT     code formula -> utilisation -> PASS/FAIL
         SCIA/MIDAS/CSI · Code_Aster POST_RCCM · Autodesk Safety Factor
         ─── the only layer a piping engineer can sign off on ───
Layer 2  REDUCTION   decompose / reduce / extract
         membrane / local membrane / bending / peak
         nodal peak / nodal avg / element centroidal · PATH · POST_RELEVE_T
         ─── where FE stress becomes a code quantity ───
Layer 1  FIELD       contour / iso / path / probe
         every tool
```

**Nobody skips Layer 2 and is right.** Autodesk Inventor skips it and produces a safety
factor that is a material-yield ratio — not a code check. ANSYS Mechanical ships a
Layer-1.5 stress tool (vM/Sy) and is honest in its own documentation that "the reliability
of this failure theory depends on … the representation of stress risers", recommending the
user treat the numbers as nominal and amplify them by a Kt. The pressure-vessel tools
(`POST_RCCM`, Abaqus stress linearisation, Altair) put all their complexity into Layer 2
because there is no shortcut.

Tuba's position:

| Layer | Tuba's state | Verdict |
|---|---|---|
| **1 — Field** | deformed, stress, displacement, reactions (force **and** moment), internal forces, sub-point TUYAU field, clipping, probe, hotspots, saved views | **Complete and then some** |
| **2 — Reduction** | TUYAU sub-point stress at Code_Aster's own section points, with a wall-section rosette, `angle_deg`, `section_profile`, and an explicit "sub-points are measured; the surface between them is interpolated" note. `EFGE_ELNO` internal forces at both element ends. `SIEQ_ELNO` VMIS per element-node. Nothing is *classified*. | **Built the raw material, declined the classification** |
| **3 — Verdict** | none, by ADR | **Deliberate refusal** — but the refusal currently costs more UX than it buys safety |

The middle row is the interesting one. Tuba has, today, everything a code-check layer
needs to *read*: nodal displacements, six-component internal forces at both element ends,
through-wall stress at section points, and `Material.allowable_stress` already on the
material (`tuba/model.py:62`) already printed in the `materials` report table
(`reporting/tables.py:232-237`). What it does not have is anything that turns those into a
ratio. See §6.1 — this is a *decision*, not a capability gap.

---

## 4. Comparison: piping stress software

| | CAESAR II | AutoPIPE | CAEPIPE | START-PROF | **Tuba** |
|---|---|---|---|---|---|
| Primary verdict idiom | `Overstress` (red at ≥100 %), `Stress Colors by Percent` | `Ratio` colour plot, `*` + `FAIL` in Notes | ratio > 1.00 in **white-on-black** | failing cell **red**, max-ratio cell **yellow**, error-code column with hover message | *(none)* |
| Legend bands | user-adjustable, per job | **6 hard-coded**, a top-5 support complaint | threshold filter | n/a | **continuous auto-scaled ramp, 3 ticks** |
| Worst-first list | `Sorted Stresses`, `Max Stress` + Enter to step | crosshairs auto-jump to max, cursor-step | `Sorted Stresses` is the **default idiom** | `Maximum` mode toggle | hotspot list (stress only) |
| Table ↔ 3D | bi-directional (`Select Elements`, `Zoom to Selection`) | bi-directional grid ↔ model | synchronised highlight + `Tab` cycling | live sort in 3D | row → 3D; no finding walk |
| Coordinate-system choice | global vs local (`FX/MZ` vs `fx/mz` — a whole Eng-Tips thread) | **~45 result options** that change what the number means | per-item | **per-table selector**: global / restraint-local / element-local | fixed |
| Inspect down to the equation | no | no | no | **`Show Equations` hover popup + Ctrl-C** | no |
| Envelope across combinations | combination algebra | **envelope of code combinations** | max across all cases per node | `Maximum` across submodes | dropdown only — **no envelope** |
| Stale-result signalling | n/a | Analysis Sets grid flags outdated | n/a | n/a | solver attestation + identity guards |
| Review state | node *labels* | node **annotations** + image gallery | comments + QA block | smart warning window | `Issue` records in scene contract — **unexposed in UI** |
| Cross-panel sync | not persisted | reset each launch | not persisted | n/a | saved views persist |
| Path / X-Y diagram plots | no | no | no | no | **no** (same in FEA-land: only SALOME/Code_Aster's `LIRE_RESU` curve mode) |
| ALI / load-envelope interaction plot | no | no | no | no | no — **unclaimed by the whole category** |
| δ-vs-allowable flexibility plot | no | no | no | no | no — **unclaimed** |

### What the incumbents get right that Tuba does not

1. **A scalar ratio is the universal verdict.** Every tool reduces to
   `demand / allowable`, shown three ways: colour band, sortable table row, and a binary
   text marker. Tuba shows the numerator and no denominator.
2. **Bands, not a continuous ramp.** AutoPIPE's hard-coded 6 bands are the single most
   cited UX complaint in the survey — and the reason is precise, from Bentley's own idea
   portal: *"I don't worry about the difference in stress ratios between 0.15 and 0.25 …
   I care more about the difference between 0.85 and 0.95 which are the same color."*
   Wasted resolution at the bottom, compressed exactly where acceptance limits live.
3. **Filter to only the problems.** CAESAR II `Filters` → `Percent > 80`; CAEPIPE
   `Thresholds`; AutoPIPE `Result > Filters`, which additionally *turns a filter into a
   selection* you can then scope a report with. Tuba has threshold sliders but no
   filter→selection bridge.
4. **The colour plot is driven by the table filter.** AutoPIPE: the 3D colour plot is
   synchronised with the filters applied to the combination column. The picture and the
   table can never disagree. Tuba's threshold filter filters the hotspot *list* only.
5. **Coordinate-system honesty, per table.** START-PROF lets you pick global /
   restraint-local / element-local **per table**, and includes an SRSS `Resultant` column.
   CAESAR II's global-vs-local convention (`FX/MZ` global, `fx/mz` local) has generated
   an entire forum thread of confusion. Tuba documents its right-hand rule for moment
   glyphs (`docs/architecture/moment-glyph-conventions.md`) but offers no switch.

### What Tuba is ahead on

The contact review surface (§2.1), the triplicated compliance caveat, `missing ≠ zero`
through the reporting layer, solver attestation gating in `reporting/builder.py:256-263`
(refusing anything not `result_trust == "verified"`), and the `Issue` data model.

---

## 5. Comparison: structural FEA

| Feature | Who has it | Tuba |
|---|---|---|
| **Contour bands / isovalues** | everyone — SCIA's native display is *isolines*; ANSYS default 9 bands; PrePoMax `Fringe` vs `Continuous` ("**Fringe is best to evaluate convergence**") | continuous ramp only |
| **Path / X-Y diagram plot** | ANSYS `PATH`/`PPATH`/`PDEF`/`PLPATH`, Abaqus XY data objects, COMSOL `Cut Line` + `Table Graph`, SALOME curve mode, Code_Aster `POST_RELEVE_T` / `MACR_LIGN_COUPE` | **none** |
| **Manual legend bounds** | Simcenter `Legend Extremes → Specified`; SimScale tutorial: *"Keep legend maximum value to 40"* — chosen to match the code allowable, not the max; CATI: *"eliminate the 'sea of blue'"* | auto only |
| **Nodal peak vs nodal average** | Nastran: `CENTER` underpredicts peak, `CORNER` recommended; **the difference between peak and average is a free mesh-convergence criterion** | one number, chosen silently |
| **Averaging shown, not hidden** | ANSYS exposes `Unaveraged / Averaged / Nodal Difference / Nodal Fraction / Difference (elemental) / Fraction (elemental)` — documented as a *mesh quality* aid nobody uses | silently averaged (`_results.py:143`, `pipeline.py:504`) |
| **Percentile / reference stress** | COMSOL: define a reference stress exceeded in β=5% of a reference volume; **insensitive to notch radius and mesh**; implementable as `intop1(sigma>sRef)/intop1(1)` | no |
| **Energy / equilibrium sanity check as the headline plot** | LS-DYNA's post-analysis checklist puts it first: *"Is the overall motion believable? Is the total energy sensible? Check hourglass energy"* | none |
| **Free-body reaction balance** | Femap; PrePoMax has to be *worked around* (`RF` history output, `Totals = Only`) | reactions present, balance absent |
| **Derived quantities as named persistent objects** | Abaqus `XYData` tree, COMSOL `Evaluation Group` + `Add as Result Template` | ephemeral slider state |
| **Follower view (camera locked to a deforming point)** | PrePoMax — not in any commercial tool | no |
| **Annotations saved with the model** | PrePoMax `.pmx`; LS-PrePost named views + a recorded `lspost.cfile` command script | saved views yes; notes no |
| **Brief / Summary / Detailed output tiers** | SCIA, CSI, MIDAS; SCIA detailed prints the **code clause and formula** per check | one report tier |
| **Filter All / OK / NG** | MIDAS, CSI "Failed members" tab | threshold only |

### The two FEA findings that should change Tuba's design

**Finding A — the single most consequential display setting in the industry is
averaging, and it is almost never a first-class control.** Nastran's rule is that
**nodal peak is always more conservative** than nodal average, and that **the difference
between them decreases as the mesh is refined** — so the difference *is* a convergence
criterion. Nastran additionally documents a trap that invalidates cross-tool comparison
outright: Simcenter averages the **components** before computing von Mises; Femap computes
von Mises **first** and averages those. Same word, different number.

Tuba currently averages `SIEQ_ELNO` VMIS rows arithmetically per surface node
(`_results.py:143`, stated in the overlay `data.derivation` string) and does not offer the
alternative. This is the honest choice already — the derivation string is stamped into the
scene — but it is a *choice presented as a fact*. Making it a toggle is nearly free given
the data is already parsed per element-node.

**Finding B — peak stress is the #1 complaint in FEA review, and the percentile method is
the cheapest honest escape.** The Eng-Tips consensus is blunt: *"linear static FEA of metal
components are useless as a practical matter if I'm looking to calculate strength. It's too
much judgment to say how big of an area can be overstressed."* And the second-highest-
contour myth gets a direct debunk: *"taking a stress at the next element away is bad
practice as then your results are dependent upon the mesh."* A quantified case: the same
sharp corner on three meshes gives 41.63 → 48.58 → 65.63 MPa.

COMSOL's percentile method resolves it: *"define a reference stress as the value that is
exceeded in a given fraction (for example, 5%) of a reference volume. If this reference
stress is lower than the allowed value, the design is accepted."* Verified insensitive to
notch radius and element type. Tuba's TUYAU sub-point field is exactly where this bites —
welds, shoe corners, tees.

---

## 6. Lessons, ranked

Each is traced to a source and mapped to a concrete surface. Ranked by
`(engineering value) / (effort)`.

### L1 — Move honesty from a badge into the workflow · *highest value, low effort*

**Evidence.** Every "don't lie" failure in the category is silent: AutoPIPE's zeroed
eq-10 ratio, absent KHK bends, CAESAR II's allowable-of-0, blank reports from leftover
filters. The industry's response to each is a manual footnote. Tuba's response is a badge
that is correct and repeatedly ignored.

**Change.** The status strip is the only surface never scrolled away. It currently carries
the compliance caveat, a mesh badge, a solver provenance string, and unit state. Add one
honesty fact that is *load-bearing rather than cautionary*:

- **Reaction balance.** `Σ reaction forces` vs `Σ applied loads + Σ inertia` as a residual
  with a percentage. Femap has this as a free-body tool; PrePoMax has to be *worked
  around*. On a linear elastic model the residual should be at solver tolerance. On a
  contact/friction run it is the single most informative number in the whole result set.
  It is also exactly the defence an engineer needs when a reviewer asks "did this model
  actually hold the load" — the complaint behind *"I can take just about any piping system
  and code it so that it passes or fails"*.
- **Averaging basis as a named fact, not a derivation string.** "Surface von Mises:
  arithmetic mean of `SIEQ_ELNO` element-node rows" belongs in the status strip as a
  short chip, not only in the scene JSON.

**Note on reaction balance:** this is a *consistency* check, not a code check. It asserts
the solve is trustworthy, not that the design is adequate. That framing is safe under
ADR 0002.

### L2 — Discrete bands and a settable legend, with round-number bounds · *high value, low effort*

**Evidence.** §4 item 2 and the Simcenter `Legend Extremes → Specified` pattern. Tuba's
ramp is continuous and auto-scaled to min/max, so the entire visual budget is spent
resolving the bottom of the range and the top band — the singularity — gets the whole
gradient. The three legends in the benchmark that are cited as *good* are the ones with
fixed engineering-meaningful breaks.

**Change.** In `resultReview.js:351` (`SCALAR_RAMP`) / `app.js:1787`
(`renderViewportLegend`):
- Add an `N bands` control alongside the continuous ramp (ANSYS 9, Femap/PrePoMax
  `Fringe`/`Continuous`).
- Add a min/max override with **round-number nudging** — the CATI advice is to *type round
  bounds so band increments are round*. This single affordance is the difference between
  "a rainbow" and "an instrument".
- Per-field, persisted, part of the saved view.

### L3 — A user-declared allowable reference, not a code check · *highest value, medium effort — NEEDS A DECISION*

**This is the one I most want a decision on, because it is where the ADR and the UX
pull hardest against each other.**

**Evidence.** Every piping tool's primary screen is a ratio. Tuba has `Material.allowable_stress`
as a temperature-indexed dict (`tuba/model.py:62`), already surfaced in the `materials`
report table, and never consumed. `SIEQ_ELNO` VMIS is already parsed per element-node.
`EFGE_ELNO` gives six-component internal forces at both element ends. The missing piece is
one division.

**Proposal — and it is deliberately narrower than a code check:**

Compute and display a **"user reference ratio"** = the chosen FE result ÷ the user's own
`Material.allowable_stress` at the running temperature, with the denominator
permanently visible and the source of the denominator named as *"user-entered, not a code
allowable; Tuba has not performed a code check."*

This is not B31J. It is not a code verdict. It is the industry-universal scalar that makes
a stress plot readable, and it is honest because the denominator is visibly the user's own
number. It also has a defensible use: the user who types a 1.5×Sc-equivalent screening
factor is doing exactly the screening every practitioner already does by hand.

**What it would unlock:** the ratio colour plot (the universal idiom), the band legend
with meaningful breaks (L2), the sortable worst-first list, and the "show only > 0.9"
filter — i.e. it converts Tuba's entire display layer from *descriptive* to *diagnostic*
without Tuba claiming a single code equation.

**Counter-argument, stated honestly.** `docs/architecture/b31j-compliance-migration.md`
records the deliberate removal of B31J code checks, and ADR 0002 says generic FE VMIS
never implies code utilization. A ratio against a user number is not a code check, but it
is *adjacent* enough that a careless label would erode the trust the rest of the product
is built on. The mitigation is that the denominator is never hidden and never named
`allowable` in the UI — it is `user reference`, and the caveat rides with it in the same
three places the existing one does.

**This is now written up as [ADR 0007](../adr/0007-user-reference-ratio-is-not-a-code-check.md),
`status: proposed`.** Two things it settled that the sketch above did not:

- The **scene never carries the allowable schedule.** It reaches the `materials` report
  table and the model script and nothing else, so this is a schema addition, not a UI
  change. That is the real cost, and it is why this is a decision rather than a commit.
- The ratio is **unavailable when the load case declares a temperature field**, because
  the uniform `temperature_c` is then not the metal temperature at the hot spot. Per-node
  temperatures exist in the solver path but do not reach the bundle, so the honest answer
  today is unavailable — which means the flagship thermal-split example is one of the
  cases that would *not* get a ratio.

**This is a scope question, not a research question. It should be an ADR, not a
commitment.**

### L4 — Percentile / reference stress for the peak problem · *high value, medium effort*

**Evidence.** §5 Finding B. Tuba's TUYAU sub-point layer is the exact place a reviewer
asks "is that 640 MPa at the shoe a real problem or a mesh artefact?", and today the only
answer is the literal field-mesh advice in
`data-projection-note`: *"Sub-points are measured; the surface between them is
interpolated."* That is a caveat. A β-percentile is a number.

**Change.** On the sub-point field, offer a percentile summary: the stress exceeded in
5% / 1% of the sub-point population, alongside the max, with a one-line note that the
percentile is insensitive to mesh and notch radius. Cheap: the sub-point values are already
in the overlay. High value: it converts the sharpest question in the product into a
defensible answer.

### L5 — Envelope across load cases · *high value, medium effort*

**Evidence.** AutoPIPE reviews "the stress ratio of **an envelope of the code
combinations**"; CAEPIPE computes the max across all cases per node and reports *which*
case produced it; PrePoMax has `ResultFieldOutputEnvelope`; SCIA and SOFiSTiK both have
envelopes. Tuba has a load-case dropdown (`resultReview.js:381`) and a result-step
dropdown (`:406`) but no envelope — the reviewer must step through cases by hand and
remember the worst.

**Change.** An `Envelope` pseudo-result-state: per object, the max across the selected set
of result states, **recording which state won**. The "which case won" is what makes it
review-grade rather than a coincidence. This is the default view a piping engineer wants
and nobody in Tuba offers it.

### L6 — Make the hotspot list walkable, and make the threshold a selection · *high value, low effort*

**Evidence.** AutoPIPE: crosshairs auto-jump to the max-ratio point, `F3` opens the text
window there, **cursor keys step to the next stressed point**, `PgUp/PgDn` switch loads.
CAEPIPE: `Tab` cycles through result items in a **circular** order with synchronised
highlight. Both are keyboard-first *finding walks*, not list browsing. Neither exists in
Tuba. Tuba's hotspot rows already select the 3D object, so the table→3D half is done.

**Change.**
- `n` / `N` (or `Tab`) walks the hotspot list: camera flies to the element, the inspector
  fills, the row highlights. This is the single highest-leverage keyboard affordance
  available and it is nearly free.
- Make the threshold filter **populate a selection**, AutoPIPE-style, so it can scope the
  report as well as the list. Today the filter narrows the list only
  (`resultReview.js:313-314`); the 3D colour plot is not driven by it.

### L7 — Contour bands and a distance measurement · *already shipped*

**Correction, verified 2026-09-29 against `main` @ `9a132b0`.** This finding was wrong.
The measure tool **is** shipped: a "Measure two points" button at `app.js:2519-2524`,
the canvas pick branch at `app.js:3191-3199`, the readout at `app.js:2532-2536`, and
`.measurement-readout` in `styles.css:712`. The original survey read `selection.js` in
isolation and missed the wiring in `app.js`.

**L7 is closed and needs no work.** The lesson is worth keeping anyway: *verify a claimed
gap against the code before building it.* A finding that is really a misread costs more
than one that is true, because it displaces work that was actually needed.

The two parts of this section that are still open are the banding half, which is L2, and
the uncovered-population question behind L4.

### L8 — Path / station diagram plots · **shipped** · *medium value, high effort*

**Evidence.** ANSYS, Abaqus, COMSOL, SALOME, Code_Aster `POST_RELEVE_T` and
`MACR_LIGN_COUPE` all have it; SOFiSTiK's `Result Cut Line` is the same idea. Tuba
had none, on either path — and neither had the piping benchmark. For piping the
natural path plot is **along a run**: one component against station, which answers
"where along this run does it go bad" — a question no 3D contour can.

The review recorded this as "effort is real: a station coordinate system per run,
result interpolation along it, and a plot surface in the viewer that does not
exist yet." **Two of those three turned out not to be true**, and that is why it
shipped in a session rather than a slice:

- There is no station system to build. Each element's geometry asset already
  carries its **sampled centreline** as `generation_config.points`, so arc length
  is the polyline's own length — and a bend contributes its true arc rather than
  the chord between its nodes.
- There is no interpolation to do. The stress overlay's `element_results` already
  holds a value at **both ends** of every element, which is what a structural
  diagram *is*.

Only the plot surface was new, and `contactReview.js` had already established
inline SVG as this product's chart technology. So the whole thing is
`viewer/src/stationDiagram.js` and a drawer panel.

Four refusals, each of which cost a line and each of which is the reason it can
be trusted: a single member is not a run; a tee standing in for a joined wall is
not a member; a component is offered only where both ends carry it, because a plot
that stops where the far end runs out reads as the load vanishing; and a member
with no end forces is a counted gap, not an interpolation.

**The pattern across all three slices: verify the cost before quoting it.** The
measure tool was already shipped (L7). The sub-point payload was already fetched
(twice). The station axis and the end ordinates already existed. Every "effort is
real" in this document was an estimate made from a partial read, and three of them
were wrong.

### L9 — Brief / Summary / Detailed report tiers · *medium value, low effort*

**Evidence.** SCIA: brief = one line per member; summary = all unity checks on **one
page**; detailed = every check **with the code clause and formula reference**. CSI
reports "the identification of the station, load combination, and code-equation". START-PROF
adds an `Show Equations` hover popup with Ctrl-C copy.

Tuba's `EngineeringReviewPackage` already has 13 tables and a `result_summary` table with
`governing_entity_ref` and `governing_location` — the summary tier is essentially free
and already there. What is missing is a **one-page** tier and a per-row "why is this the
governing value" affordance. Recommend a `summary` view that is explicitly one page and
a `diagnostics` band that states the identity/provenance facts the trust model already
computes.

### L10 — Expose the review state machine · **shipped** · *medium value, medium effort*

**Evidence.** Gap G5 in the piping benchmark: **no tool in the category can mark anything
under review, resolved, accepted, or waived.** AutoPIPE has node annotations (a label) and
an image gallery. Codeware has an auto-generated deficiency summary. CAEPIPE has a QA
block, which is a report section, not a workflow. Review state genuinely lives only in
E3D/Tekla markup — tied to CAD objects, not to stress results.

**The correction first, because this section was wrong about its own size.** It
claimed the `Issue` model was 80% built and "the UI exposes none of it." The UI *did*
expose a status select and a comment box (`app.js:appendIssueReviewActions`,
dispatching `setIssueReviewStatus` / `setIssueReviewComment`). What was missing was
narrower and sharper than "a surface":

- **Attribution.** No author, no date. A disposition with neither is a shrug.
- **History.** `status` overwrote, so "examined and then re-opened" — usually the
  interesting part of a review — was unrecoverable.
- **`accepted` and `waived` were absent**, and those are the two decisions a review
  meeting is actually about.
- **No export.** The dispositions died with the tab. *That* was the real gap: a
  competitor can annotate a node; whether this product could hand you a record was
  the open question.

So `viewer/src/reviewRecord.js` adds a transition log, five statuses with `waived`
**requiring a justification**, a self-declared reviewer, and a CSV/JSON export that
leaves with the review. The existing reducer actions are routed through the new
writer, so anything already dispatching them gets attribution and history too.

Three refusals, each the reason it can be trusted. The author is **self-declared**
and the record says so — a static bundle has no authentication, and implying a
signed identity would be a claim the viewer cannot support. A waiver with a blank
reason is **refused with state untouched** rather than writing a half-valid record.
And an **untouched issue is not an `open` disposition**: conflating the two would
overstate how much review has happened, so the tally reports `touched` separately.

The CSV is tested with an RFC 4180 reader rather than a comma count — which is how
the first version of that test was written, and it would have passed a file whose
every column after the comment had shifted. A waiver reason is free text and will
contain a comma, often a quote, and sometimes a line break.

**Still open from this section:** joining dispositions to *result states*. The
`governing_location` on every result row is a precise, stable address, and nothing
yet raises a finding into a recordable disposition. That is the half of L10 the
benchmark identified as unclaimed by the whole category, and it is the next thing
worth doing.

---

## 7. What not to copy

Stealing the wrong thing from a competitor would be a regression against ADR 0002.

1. **Do not ship a bare safety factor.** Inventor's ratio silently changes meaning
   depending on whether the material dialog says Yield or Ultimate — two different
   criteria behind one icon. A ratio in Tuba must always show its denominator and the
   denominator's provenance.
2. **Do not hide the averaging.** Femap and Simcenter compute nodal averages in different
   orders (components-then-vM vs vM-then-average), which makes their numbers
   uncomparable. Tuba's arithmetic mean is fine — it just must be *stated*, and ideally
   switchable.
3. **Do not hard-code legend bands.** AutoPIPE's 6 hard-coded bands are the most-cited
   complaint in the entire survey. Make the bands a control with good defaults, never a
   constant.
4. **Do not smooth FE stress to make it pretty.** The FEniCS thread is unambiguous: making
   a piecewise-constant von Mises field look smooth by interpolating it into a continuous
   space is *"nonphysical manipulation in the post-processing phase"* — though note this
   is about *field order*, not about honest nodal averaging, and `DG1`-style handling is
   legitimate. Tuba's `SIEQ_ELNO` averaging is the honest kind; keep it, and say so.
5. **Do not make a P-δ readout.** P-delta and moment amplification are *seismic steel*
   concepts. Piping's non-linearities are state changes: which supports are in contact,
   which have lifted, which gaps are open, which friction directions have reversed.
   Tuba already models these better than anyone — expose the state, do not invent a
   steel-shaped number.
6. **Do not treat peak stress as a failure criterion.** *"Taking a stress at the next
   element away is bad practice as then your results are dependent upon the mesh."* Peak
   is a fatigue input. L4's percentile is the correct escape; a "second highest" rule is
   a different colour of the same mistake.

---

## 8. Proposed order

| Slice | Lessons | Depends on |
|---|---|---|
| **1 — Cheap legibility** | L2 bands + legend bounds, L6 finding walk + threshold→selection, L1 reaction-consistency + value-basis facts, ~~L7~~ *(already shipped)* | nothing; all additive |
| **2 — The decision** | L3 user reference ratio — **[ADR 0007](../adr/0007-user-reference-ratio-is-not-a-code-check.md)**, `proposed` | needs a material table in the scene |
| **3 — Diagnostic depth** | L5 envelope, L4 reference stress, L9 report tiers | nothing for L4/L5; L3 for the report tiers |
| **4 — Structural** | L8 station diagram plots | ~~a new plot surface~~ *(contactReview.js had one)* |
| **5 — Differentiator** | L10 review state machine | **shipped**; raising a *result* into a disposition is still open |

Slices 1, 3, 4 and 5 shipped on `feat/postprocess-ergonomics`. What remains is
L3 — the user reference ratio, behind ADR 0007, which needs a material table in
the scene — L9's report tiers, and the one part of L10 the whole category is
missing: raising a *finding* into a disposition, so that "this element at this
station was reviewed and waived" is expressible against a result rather than only
against a generated clash.

**L10 is smaller than this document says.** `viewerState.js` already has
`setIssueReviewStatus` and `setIssueReviewComment`, and the scene contract's
`Issue` already carries `status`, `created_by`, `created_at` and `comments`. What
is missing is a surface, not a data model.

### 8.1 Slice 1 — what shipped

Implemented on `feat/postprocess-ergonomics`. All of it is opt-in: a bundle with no scale
override and no band count reads exactly as it did before, because a review tool that
reshapes its own legend on load invalidates the screenshots and muscle memory people
arrived with.

| Lesson | Where | Note |
|---|---|---|
| L2 bands + typed bounds | `viewer/src/legendScale.js`, `resultReview.js:222`, `app.js` `scaleControls` / `scalarRampGradient` | Band count is global; bounds are per field. Round bounds come from a *nearest* nice step, not a rounded-up one, so a request for N bands yields N and the increments stay round — `bandEdges` extends the top edge so nothing is clipped. |
| L6 finding walk | `resultReview.js` `getFindings` / `stepFinding`, `viewerState.js` `focusFinding`, `selection.js` `focusFinding` / `findingFitSpan` | `n` / `N` in the existing `SHORTCUTS` table, so it inherits the modifier and typing-target guards and appears in the `?` overlay. Not `Tab` — that is focus traversal. The walk indexes by object id, so a moved threshold cannot strand it, and it reports "7 of 40" on the active row. The camera is clamped to a window about the selection's centre, because fitting a twenty-metre run whole lands outside the model. |
| L6 threshold → selection | `app.js` `selectFindingsControl` | AutoPIPE-style: a filter becomes a selection the review tables can be scoped to. |
| L1 reaction consistency | `viewer/src/trustFacts.js`, `app.js` `renderBalanceCheck` | Sums reactions against **authored nodal loads only**, carrying the applied forces to the same origin for the moment balance. Self-weight, pressure, line loads and authored fields are **named as excluded** — they are assembled inside Code_Aster and never reach the bundle, so a "balanced" badge over one term of five is the silent-omission failure this whole review is about. Reports a residual, never a verdict. |
| L1 value basis | `trustFacts.js` `getAveragingBasis`, rail "Field details" | What population the number is a maximum over, next to what the field is. |

Two bugs the new tests caught before anything shipped, both worth recording:

- `niceStep` originally rounded *up*, so a request for 6 bands never yielded 6 — only
  fewer — and `0.105` snapped to `0.15`, which is not a round increment at all. Rounding
  to nearest and letting `bandEdges` extend the top edge fixes both.
- The moment residual was a *difference* while the force residual was a *sum*. Both are
  sums-to-zero: at a held node the reaction and the applied load cancel. The difference
  reported 100 N·m for a perfectly balanced 50 N·m couple.

The measure tool was verified rather than rebuilt — see L7 above.

### 8.2 Slice 3 — what shipped

Also on `feat/postprocess-ergonomics`. Both viewer-side and additive: no schema
change, no bundle regeneration, no new Python.

| Lesson | Where | Note |
|---|---|---|
| L5 envelope | `viewer/src/envelope.js`, `coloring.js` `envelopeOption` / `getColoringValues` / `getColoringLegend`, `app.js` `renderEnvelopeNote` | One more field in the existing "colour by" selector, per ADR 0006. Records the governing result step per object and prints it on the hotspot row, which is what turns a maximum into an answer. Ties go to the **earlier** step. Carries a `compliance_role`, so the "derived, not a separate solve" disclaimer rides into all three existing places. |
| L4 reference stress | `resultReview.js` `getReferenceStress`, `app.js` `renderReferenceNote` | 1% and 5% of the wall-point population, read from the per-asset geometry payload. Nearest-rank, no interpolation. Sub-point field only. |

**A lesson repeated, and it is worth more than the feature.** While scoping L4 I
concluded twice that the sub-point glyph body was not rendering in published
bundles — first from a grep for `payload_uri` (the viewer keys off `asset.uri`),
then from noticing the manifest carries only five keys. Both times I was wrong:
`sceneLoader.js:readGeometryPayloads` fetches the per-asset payload in batches of
16, `createViewerState` carries it through, and `renderer.js:2129` merges
`payload.generation_config` over the reduced one. I was one edit away from
"fixing" a bug that does not exist, and from reporting a false regression. The
verification is the only reason it was caught. Two prior claims in this document
came from partial greps; the third did not.

Three more judgement calls worth recording, all of them cases where the honest
answer was less impressive than the available one:

- The envelope is **not offered** when there is no declared quantity to envelope.
  It would have been one line shorter, and it would have offered a maximum of
  nothing on a bundle whose result state could not be resolved.
- `enveloped` is measured in **result steps that contributed**, not in overlays
  matched. The first implementation counted overlays, which disagreed with the
  option's own availability check: a load case can publish two steps and only one
  can carry the quantity, and that is not an envelope.
- A load case that published several steps where only one carries the quantity
  now **says so in the field** rather than presenting a single result as a
  maximum over steps.

---

## 9. Method notes and limits

- Piping sources: Bentley AutoPIPE (direct, high fidelity), CAEPIPE (direct), PASS/START-PROF
  (Wayback), Codeware (change log), Triflex (manual PDF), CAESAR II (search-index — the
  doc site is a JS SPA, so menu strings are quoted from indexed page text, not fetched).
  SigmaPipe and OpenPlant PIPENET turned out **not** to be piping stress post-processors
  (SigmaPipe is a flow simulator; PIPENET hands off to AutoPIPE) and are excluded.
  **Not found, treat any claim as unverified:** ADNEXT Autopipe, Mitsubishi AutoPIPE,
  Stress Analysis Ltd (StrainAnalysis, P-FLAN). "Hexagon 3DGLT" appears to be a
  non-existent product name.
- FEA sources: vendor documentation and manuals, plus forum threads for the pain points.
- One correction worth carrying forward: there is **no `P_CONTROLE` command in Code_Aster**.
  The real limit-analysis surface is `POST_ELEM` (λsup/λinf bounds, validated on the EDF
  LISA benchmark to ~0.1%), `STAT_NON_LINE` / `PILOTAGE` / `ETA_PILOTAGE` (load
  multiplier), and `POST_RCCM` (a genuine pass/fail framework against RCC-M, which
  classifies into Pm / Pl / Pb / Pm+Pb / Sn / Sp with limits at 1.5 Sm and 3 Sm). If Tuba
  ever wants a real verdict layer, `POST_RCCM` is the model and `LISA` is the validation
  case — but that is a different project from this review.
