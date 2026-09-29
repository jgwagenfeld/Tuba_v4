# Structural frames

Tuba models pure structural frames as well as piping: portal frames, roof
trusses, racks, bracing and any assembly of `beam`, `bar` and `cable` elements
that Code_Aster can solve as a 1D frame. The workflow is unchanged — define the
structure in Python, evaluate it with Code_Aster, display the processed results —
but a pipe-free model behaves differently in two ways that matter, and a few
element semantics will fail a solve if you do not know them.

`examples/steel-portal-frame/` is a worked example: a 7-frame portal-frame hall
with cambered bowstring roof trusses that solves for both gravity and wind. Its
`model.py` docstring records the same findings as this page.

Open it in the studio:

```bash
python -m tuba.cli_studio examples/steel-portal-frame
```

Its committed evidence lives in `evidence/<case>/` and is checked against the
model fingerprint on import, so editing `model.py` correctly invalidates it.

## Result coverage: no stress without pipes

Tuba requests Code_Aster's `SIEQ` equivalent-stress field only when the model
contains pipe elements. A structural frame therefore produces **no von Mises
stress**, and `max_von_mises` is `None` for every member. Displacements and
reactions are real and complete.

| Result | Pipe model | Structural frame |
| --- | --- | --- |
| Node displacements | yes | yes |
| Node reactions | yes | yes |
| Element von Mises stress | yes | **not computed** |

Report the missing stress as "not computed". Never render it as `0.0`: an absent
result is not a zero result, and the difference matters when a reviewer reads the
number as "this member is unstressed".

## Element semantics

These are Code_Aster behaviours, not Tuba preferences.

**`bar` is a pin-jointed truss element.** `BARRE` carries axial force only and
contributes no rotational stiffness, with three translational degrees of freedom
per node. A truss web built from bars alongside beam chords leaves the assembled
stiffness matrix rank-deficient, and Code_Aster fails with a singular pivot that
names a *translational* degree of freedom which in fact has stiffness. Modelling
the same web with beam elements solves it.

This was isolated by a controlled A/B — identical nodes, coordinates and loads,
only the element type differing — and confirmed to be a true null space rather
than a strict pivot tolerance: re-running with MUMPS and singular-pivot detection
disabled returned a residual of 9.64 against a tolerance of 1e-06.

**A solid bar is not a beam section.** Giving a `beam` element a *solid*
`BarSection` makes the exported `AFFE_CARA_ELEM` write a `POUTRE` block whose
`CERCLE` payload has `EP = 0`, which Code_Aster rejects with
`Mauvaise definition de ('R', 'EP')`. A *hollow* `BarSection` is fine on a beam:
a CHS brace is written as `CERCLE` with `R = 0.04, EP = 0.006` and solves, and
`examples/steel-portal-frame` relies on that. The reason a truss web must be
`beam` rather than `bar` is the pin-joint above, not the section type.

**Do not join two anchored nodes.** Code_Aster refuses a doubly blocked degree of
freedom: `le noeud: 31 composante: DX est bloqué plusieurs fois`. Anchor each
support on its own node and connect them through the structure.

**`cable` is tension-only** and makes the solve nonlinear. Give it a pretension
and expect load redistribution rather than linear superposition.

## Authoring frames on resolved nodes

The fluent builder is a piping cursor: `run()` and `beam()` each mint a fresh
node at the far end, so two members meeting at a joint end up on two coincident
nodes. The clash gate reports those as duplicate nodes, and the solver reads the
structure as disconnected.

Resolve nodes by coordinate instead, so a joint has exactly one node id:

```python
def resolve_node(model, point):
    found = model.find_node_by_point(point, tol=1e-9)
    return found if found is not None else model.add_node(point)
```

## Bracing a real frame needs

- **Brace in both directions.** Two parallel planar trusses tied along a single
  chord line can rack against each other.
- **Brace the bottom chord too.** A portal frame's web lies wholly in its
  transverse plane, so it gives the bottom chord no out-of-plane stiffness. Over
  a long clear span the tie line needs its own plan bracing, below the roof
  bracing.
- **One diagonal per braced panel, not an X.** Crossing diagonals physically pass
  through each other, which the self-clash check reports as a hard clash. A
  shared centre node is worse still: a node whose members are all bars has no
  rotational stiffness.
- **Give the truss depth at the springings.** If the top and bottom chords meet
  at the end panels, the end web members run collinear with the chords and the
  clash gate rejects the frame. Offset the top chord above the tie.
- **Watch the weak axis.** For members that must bend out of plane, the catalog
  `IY` is often the weak axis — IPE200 is 1.42e-6 m⁴ against IZ 1.94e-5 m⁴. Set
  `twist_angle` on the element to rotate the section; Tuba writes it to
  Code_Aster as `ANGL_VRIL`. See *Cross-section orientation* below.

## Cross-section orientation

`twist_angle` is the one structural input that looks cosmetic and is not. It
decides which of an I-section's two inertias resists which bending, and leaving
it at zero puts every horizontal member on its weak axis: for a horizontal member
the local triad is X along the span, Z up, Y transverse, so vertical bending is
bending about local Y, which the catalog `IY` resists — and for a rolled section
`IY` is the smaller of the two.

Measure it rather than reasoning about it. A fixed IPE200 under a 10 kN midspan
load over 12 m deflects **301.3 mm** at `twist_angle=0` and **22.4 mm** at
`twist_angle=90`, matching `FL³/(192·E·I)` for the weak and strong axes. A
vertical HE300B cantilever pushed in X is weak-axis at 0 and strong-axis at 90.
On `examples/steel-portal-frame` this was 364 members, and correcting them took
the wind case from **420 mm to 137 mm** of deflection.

The rotation also decides **which column of a section-force table a result is
reported under**, so a table of `N, Vy, Vz, Mt, My, Mz` is ambiguous without it.
Identically for a horizontal member and a vertical column:

| `twist_angle` | shear | moment | resisted by |
|---|---|---|---|
| `0` | `Vz` | `My` | `IY` — weak for a rolled section |
| `90` | `Vy` | `Mz` | `IZ` — strong |

An inclined member's local triad is set by its own direction, so do not extend
this table to diagonals and bracing; design those axially and read `N`. Export
the twist beside the forces and the table stops being ambiguous —
`examples/steel-portal-frame/study.py` writes `section-forces.csv` with a
`twist_deg` column for exactly this reason.

## What these results are not

**The analysis is first order.** Tuba asks Code_Aster for a linear `MECA_STATIQUE`,
so the geometry is never re-evaluated under load: axial force is computed for the
undeformed shape and no P-Delta (geometric stiffness) term enters the system. For
a slender frame that understates both the true column compression and the sway
amplification, which means **no reported moment is a design moment**.

Tuba does not expose a second-order *solve* for a pure beam frame — `is_nonlinear`
in `tuba/solver/aster_comm.py` is raised only by contacts and cable elements, and
those are exactly the studies a buckling analysis is refused for. A structural
model here answers *how does the frame deflect, how much load reaches the
foundations, and how far is the linearised buckling factor*, and deliberately not
*is any member adequate*.

That is also why section forces, not von Mises, are the deliverable. A member
code consumes N, Vy, Vz, Mt, My, Mz.

## Buckling

A load case can ask for a **linear buckling eigenvalue analysis** of itself. It
still solves as an ordinary static study, and one solve then answers both "how
does this deflect" and "how close is this to buckling":

```python
from tuba.model import BucklingOptions

model.define_operation("Gravity", gravity=True, buckling=BucklingOptions(n_modes=8))
```

A plain dict works too: `buckling={"n_modes": 8}`. The result lands on the
result state, and the factors are read in the solver's own order:

```python
state = run.result_state
state.buckling.critical_factors      # (30.49, 29.19, 28.94, ...)
state.buckling.governing_factor      # 23.87 - the first mode to buckle
state.buckling.governing_mode()      # the mode, with its nodal shape
```

Two artifacts back it, so a reviewer can reopen the numbers:
`study_buckling.json` (the factors, with the raw eigenvalues beside them) and
`study_buckling_modes.csv` (the mode shapes, in the same column layout as a
static `DEPL` table). Both are attested, so evidence exported for a buckling case
fails freshness if the options change.

`BucklingOptions` fields: `n_modes` (how many critical charges),
`modal_subspace` (eigensolver subspace — widen it when a structure has
near-degenerate modes), `method` (`TRI_DIAG`, `SORENSEN`, `JACOBI`), `rigid_modes`,
`stop_on_error` and `mode_shapes`.

The analysis is refused where it would be meaningless, and the refusal is
deliberate rather than a crash:

- **Contact and cable studies are refused.** The geometric stiffness comes from a
  single `SIEF_ELGA` of a *linear* run. On a contact history it is a field over
  increments, and taking one would report a partial prestress as a whole one.
- **A model with no supported degree of freedom is refused.** The elastic matrix
  is assembled with the boundary conditions; with none there is nothing to solve.
- **A study that asked for buckling and produced no factors is an error, not an
  empty result.** Reporting "no instability found" for a failed eigen-solve is
  the one outcome this must never produce.

### What it computes, and what it does not

`CALC_MODES(TYPE_RESU='MODE_FLAMB')` solves `K f = -? K_G f` on the same `POUTRE`
beams the model already exports. `TYPE_RESU='MODE_FLAMB'` is a first-class value
of that command and 35 of Code_Aster's shipped regression cases exercise it
(`ssll403a` is the minimal 1D template). The keyword is `STABILITE`; there is no
command named for buckling in English, and searching for one gives a false
negative that looks like a missing feature.

`STAT_NON_LINE(TYPE='FLAMBEMENT')` covers the second-order form and
`CALC_STABILITE` post-processes a nonlinear run for instability points. Neither is
wired up; the linear eigenvalue analysis is what Tuba exposes.

Two limits on how the numbers may be used:

- A critical factor is a **reference load, not a code check.** It is a linearised
  idealisation of a perfect frame with no initial imperfection, and a real column
  buckles at a fraction of it. Eurocode 3 reduces it by a reduction factor and
  carries a buckling curve on top.
- The factor is only as good as the prestress that produced `K_G`, and that
  prestress is the first-order static result — which understates column
  compression. So the factor is optimistic in a way that compounds with the
  missing imperfection. `examples/steel-portal-frame` reports **24–30**; that is
  an optimistic bound on an idealised frame, not a design margin, and it says
  nothing about member adequacy under the real imperfections.

### Worked example: the portal-frame hall

`examples/steel-portal-frame` runs a buckling analysis on its gravity case. The
spectrum converges with a mean a-posteriori error of 6.1e-13 and the run exits
clean:

| mode | critical factor | a-posteriori error |
|---|---|---|
| 1 | 30.49 | 1.6e-12 |
| 2 | 29.19 | 6.7e-13 |
| 3 | 28.94 | 1.1e-12 |
| 4 | 27.42 | 7.6e-13 |
| 5 | 26.91 | 2.3e-13 |
| 6 | 26.53 | 3.9e-13 |
| 7 | 25.39 | 6.5e-14 |
| 8 | 23.87 | 6.1e-14 |

So the hall's linearised elastic capacity is roughly **24x the gravity load
case**, and it is nowhere near a gravity buckling limit. Code_Aster also warns
that a ninth critical charge exists in the interval and did not compute it — a
near-zero mode consistent with the tie line needing its own plan bracing. A
near-zero critical factor is a red flag about the model's restraints, not a
harmless extra row, so check it before quoting the table.

`stop_on_error` defaults to `False` for a reason: Code_Aster's default
a-posteriori tolerance is 1e-6, which a real frame frequently cannot meet even
though the factors are converged to 1e-12, and the run then raises
`ALGELINE5_15` *after* computing usable factors. Set it to `True` when you want
the strict check and a hard failure instead.

The reference solve in `tests/test_code_aster_buckling_reference.py` pins this
against a closed form: a fixed-free column under a known axial load returns the
fixed-free Euler load to within 5%. A buckling feature that merely runs is not
evidence that it is right.

## Loads

Gravity and a wind line load cannot share a load case. `CALC_CHAMP` accepts a
single distributed load on a beam model, and self-weight already is one, so
`gravity=True` together with a `line_load` field fails with `votre chargement
contient plus d'une charge repartie`. Use one operation per distributed load.

`line_load` is force per metre in global axes, and is the right tool when you
know the load the cladding hands to the purlins and girts. The `wind` quantity
follows Code_Aster's cross-flow rule: it keeps the component across the member
axis, scaled by the sine of the angle between wind and axis.

Tuba computes no design pressure and selects no standard. Section sizes and load
values are engineering inputs owned by whoever holds the structural design; the
solver reports what that structure does under them.

## Diagnosing a failing structural solve

1. Confirm the runtime first: `python -m tuba.solver.code_aster_doctor --check`.
   A broken runtime and a broken model look identical from the outside.
2. Read the exception in `study.mess`, not the summary line. The named degree of
   freedom is a starting point, not a diagnosis.
3. Bisect against the solver, one feature at a time, starting from a model you
   know solves. `examples/line-load-studio/model.py` is a small known-good
   model. Change exactly one thing per run — web as bars versus beams, with and
   without bracing, two frames versus seven. The first variant that solves names
   the cause.
4. A cheap first probe is the per-node diagonal stiffness. A zero diagonal is a
   real mechanism. The translational block is the projector sum
   `(E·A/L)·n·nᵀ + (12·E·Iy/L³)·m·mᵀ + (12·E·Iz/L³)·p·pᵀ` over the local axes;
   the rotational block is the same with `L⁻¹` and `4` in place of `L⁻³` and `12`.
   Healthy diagonals together with a singular solve indicate a coupling
   dependency rather than a free node.
5. Do not trust a hand-rolled stiffness matrix you have not validated against a
   model that demonstrably solves. One wrong degree-of-freedom index in a bending
   block silently deletes an entire bending plane and invents mechanisms that are
   not in the structure.

See also: the `tuba-structural-frames` agent skill, which carries the same rules
in agent-facing form.
