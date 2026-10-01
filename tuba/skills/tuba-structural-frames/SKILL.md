---
name: tuba-structural-frames
description: Model non-pipe structural frames in Tuba v4 - portal frames, roof trusses, racks, bracing, and any beam/bar/cable assembly Code_Aster solves as a 1D frame. Use when the model has no pipe elements, when a frame or truss is required, or when Code_Aster reports a singular matrix, "matrice singuliere", blocked-twice DOFs, "plus d'une charge repartie", or a missing/NaN von Mises stress on a structural model.
---

# Tuba structural frames

Tuba's public API also models pure structural frames: `beam`, `bar` and `cable`
elements, I-beam, rectangular, bar and cable sections, anchored or restrained
nodes, and a Code_Aster `MECA_STATIQUE` solve. `examples/steel-portal-frame/` is a
worked 7-frame portal-frame hall that solves; read its `model.py` docstring
before starting a new one.

The product contract does not change for a non-pipe model: define in Python,
evaluate with Code_Aster, display the processed results. A structural model that
solves still has **no von Mises stress** (see Result coverage), so report
deflection and reaction and say stress was not computed.

## The four element rules

These are Code_Aster semantics, not Tuba preferences. Each one cost a failed
solve to learn.

**1. `bar` is a pin-jointed truss element - it has no rotational stiffness.**
Code_Aster's `BARRE` carries axial force only, with three translational degrees
of freedom per node. A truss web built from bars alongside beam chords leaves
the assembled matrix rank-deficient, and Code_Aster fails with a singular pivot
naming a *translational* DOF that in fact has stiffness. Change the web to
`beam` elements and the identical geometry solves. Verified by A/B: same nodes,
same coordinates, same loads, only `kind` differing. MUMPS with singular-pivot
detection disabled returned a residual of 9.64 against a 1e-06 tolerance, so
this is a true null space and no solver setting hides it.

**2. Never join two anchored nodes with a member.** Code_Aster refuses it:
`le noeud: 31 composante: DX est bloqué plusieurs fois`. Anchor each base on its
own; connect them through the structure, not with a redundant ground tie.

**3. One distributed load per beam model.** Self-weight is already a
distributed load, so `gravity=True` plus a `line_load` field in the same case
fails with `votre chargement contient plus d'une charge repartie`. Use separate
operations: one for gravity, one for wind.

**4. `cable` is tension-only and makes the solve nonlinear.** Give it a
pretension, and expect redistribution rather than linear superposition.

## Result coverage: no stress on a pipe-free model

Tuba requests Code_Aster's `SIEQ` equivalent-stress field only when the model
contains pipe elements. A pure structural frame therefore has **no von Mises
stress**, and `result.max_von_mises` reads `None` or `NaN` for every member.
Displacements and reactions are real and complete.

Print "not computed", never `0.0` - an absent result is not a zero result.

```python
state = run.result_state
print(len(state.node_displacements), "nodes solved")   # real
print(state.node_reactions)                            # real
print(run.results.element_results[first].max_von_mises)  # None: not computed
```

## Where a section's numbers come from

`properties_for_section` computes a section's area, both second moments, its
torsion constant and its radii of gyration from the section's own geometry - no
catalog lookup, no solver:

```python
from tuba.sections import properties_for_section
p = properties_for_section(model.sections["Column_HE300B"])
p.area_m2, p.iy_m4, p.iz_m4, p.j_m4      # IY is about Y, so IZ is the depthwise one
p.j_is_exact                              # False for an I-beam: J is a thin-wall estimate
```

A rolled I-profile is the exception to "Code_Aster works it out": it has no
primitive, so `tuba/solver/aster_comm.py` writes it as `SECTION='GENERALE'`
with fourteen values taken from `tuba/sections/data/IBeam.output` - a
`macr_cara_poutre` MacroCommand output committed once and not regenerable from a
runnable install, since the command module ships without the runtime that
registers it. `tuba/sections/data/README.md` records that, **and which of its
columns do not mean what their names suggest** - `RY`/`RZ` are extreme-fibre
distances rather than radii of gyration, and `JG` is not the handbook warping
constant.

The native kernel covers four of those fourteen - `A`, `IY`, `IZ`, `JX` - and
agrees with the table to 0.04% or better across all 174 catalog profiles
(`tests/test_section_properties.py` sweeps the whole catalog, it does not sample).
`JX` is the exception and stays one: an open section's Saint-Venant constant is
`1/3 * sum(b t**3)` over the wall mid-lines, and the four root radii are not
separate walls in that sum, so it is bounded at 45% and flagged `j_is_exact=False`
rather than dressed up.

Read `p.gyration_y_m` and `p.gyration_z_m` for radii of gyration. They are not
called `RY`/`RZ` precisely because those names are taken: the catalog's `RY` is
half the depth, and a `ry_m` that meant one thing in the catalog and another
here is how a reader ends up checking a beam's shear lag against its depth.

The other six - `AY`, `AZ`, `EY`, `EZ`, `JG`, `RT` - are not all reachable from
the kernel, and the reason is in the data README rather than in the difficulty of
the derivation. `EY`/`EZ` are exactly zero by double symmetry and can be stated
as such. `JG` and `RT` have no oracle to test against, so they are not
hand-rolled. Do not switch the solver onto the native values for anything the
kernel cannot validate.

## Build structural frames on resolved nodes

The fluent builder is a *piping* cursor: `run()` and `beam()` each mint a fresh
node at the far end, so two members meeting at a joint end up on two coincident
nodes. The clash gate reports those as duplicate nodes and the solver reads the
structure as disconnected.

Author a frame with shared endpoint nodes, then validate the completed model:

```python
n1 = model.get_or_create_node((0.0, 0.0, 0.0), tolerance=1e-9)
n2 = model.get_or_create_node((3.0, 0.0, 0.0), tolerance=1e-9)
model.add_element(id="beam_0", type="beam", n1=n1, n2=n2,
                  section=section, material=material, twist_angle=90.0)
model.validate()
```

## Cross-section orientation is load-bearing, not cosmetic

`twist_angle` is exported as `ANGL_VRIL` and it decides **which of an
I-section's two inertias resists which bending**. Leave it at zero and every
horizontal member bends about its weak axis, because for a horizontal member the
local triad is X along the span, Z up, Y transverse, so vertical bending is
bending about local Y - resisted by the catalog `IY`, which for a rolled section
is the *small* one. For IPE200 that is 1.42e-6 against 1.94e-5, a factor of 13.7.

Verify it rather than trusting the reasoning. A fixed IPE200 under a 10 kN
midspan load over 12 m deflects **301.3 mm** at `twist_angle=0` and **22.4 mm**
at `twist_angle=90`, matching `FL^3/(192*E*I)` for the weak and strong axes. On a
vertical HE300B cantilever an X-direction push is weak-axis at 0 and strong-axis
at 90. On the steel-portal-frame hall, 364 members sat in the wrong orientation
and correcting them took wind deflection from 420 mm to 137 mm.

**The twist also decides which column of a section-force table a moment appears
under**, so a table read without it is ambiguous. Established empirically, and
identically for a horizontal member and a vertical column:

| `twist_angle` | shear reported as | moment reported as | resisted by |
|---|---|---|---|
| `0` | `Vz` | `My` | `IY` (weak for a rolled section) |
| `90` | `Vy` | `Mz` | `IZ` (strong) |

For an *inclined* member the local triad is set by its direction, so do not
generalise this table to truss diagonals and bracing - design those axially and
read `N`. Exporting the twist beside the forces (`section-forces.csv` in
`examples/steel-portal-frame/study.py`) is what keeps a table unambiguous.

A `BarSection` is *not* itself a problem on a beam: a hollow CHS is written as
`POUTRE` with `SECTION='CERCLE'` and `CARA=('R','EP')`, and solves. What
Code_Aster rejects is a **solid** bar, where `EP` degenerates to 0 and the
payload becomes an invalid `Mauvaise definition de ('R', 'EP')`. The web of a
truss must be `beam` rather than `bar` for a different and far more important
reason: `BARRE` is pin-jested and carries no moment at all, which is what makes
the stiffness matrix rank-deficient.

## Bracing that a real frame needs

- **Brace in both directions.** Two parallel planar trusses tied only along one
  chord line can rack. Roof plan bracing alone is not enough.
- **Brace the bottom chord too.** A portal frame's web lies wholly in its own
  transverse plane, so it gives the bottom chord no out-of-plane stiffness at
  all. Over a long span the tie line needs its own plan bracing, one tie above
  the roof bracing.
- **One diagonal per braced panel, not an X.** Two diagonals crossing inside a
  panel physically pass through each other, which `check_self` reports as a hard
  clash. A shared centre node is worse: a node whose members are all bars has no
  rotational stiffness.
- **Give the truss real depth at the springings.** If the top and bottom chords
  meet at the end panels the end web members run collinear with the chords and
  the clash gate rejects the frame. Offset the top chord above the tie.
- **Watch the weak axis.** For members that must bend out of plane, the catalog
  `IY` is often the weak axis (IPE200: IY 1.42e-6 against IZ 1.94e-5). Rotate
  the section with `twist_angle`, which Tuba writes as `ANGL_VRIL`. See
  *Cross-section orientation* above.

## Buckling

Do not report "Tuba cannot do buckling". It can, and the solver underneath
(`CALC_MODES(TYPE_RESU='MODE_FLAMB')`, on the same `POU_D_E` beams it already
exports) is not the hard part. A load case asks for it in one line:

```python
from tuba.model import BucklingOptions
model.define_operation("Gravity", gravity=True, buckling=BucklingOptions(n_modes=8))
```

`buckling={"n_modes": 8}` also works. The load case still solves as an ordinary
static study; the buckling block is appended, and its geometric stiffness comes
from that same solve's prestress. Read the result off the result state:

```python
state.buckling.critical_factors   # solver order
state.buckling.governing_factor   # the first mode to buckle
state.buckling.governing_mode().node_displacements
```

`governing_factor` is the **smallest** factor, not the first row - the solver
returns them in its own eigenvalue-search order and re-sorting would hide where
they came from.

Three refusals are deliberate, and they are the ones to explain rather than
paper over:

- **Contact and cable studies.** The geometric stiffness is a single
  `SIEF_ELGA` of a *linear* run. On a contact history it is a field over
  increments, and taking one reports a partial prestress as a whole one.
- **No supported degree of freedom.** `RIGI_MECA` is assembled with the
  boundary conditions; with none there is nothing to solve.
- **A declared buckling study that produced no factors.** That is an error, not
  an empty result. Never let a failed eigen-solve read as "did not buckle".

A factor is a **reference load, not a design check**: linearised, no initial
imperfection, built on a first-order prestress that understates column
compression. Quote it as an optimistic bound and say so. A near-zero factor is a
red flag about the model's restraints, not an extra row.

`stop_on_error` defaults to `False` because Code_Aster's default a-posteriori
tolerance is 1e-6, which a real frame often cannot meet although the factors are
converged to 1e-12; the run then raises `ALGELINE5_15` *after* computing usable
factors.

If you ever have to hand-write the chain, four traps, all learned the hard way:

- Insert **before `FIN()`**. `FIN` closes the jeveux memory manager; anything
  after it dies with `code_aster memory manager is not started`.
- `CREA_CHAMP` needs `NUME_ORDRE=1`, else
  `Exactly one argument of ('NUME_ORDRE', 'INST', 'FREQ', ...) is required`.
- `VERI_MODE=_F(STOP_ERREUR='NON')` is usually required; `COEF_DIM_ESPACE` also
  helps. The trade is convergence versus the check, not correctness.
- Reuse Tuba's `.export` and `.mail`. The mesh arrives on Fortran unit 20 via
  `F mail study.mail D 20`; a hand-rolled export gives `Le fichier a lire est
  vide`, and a `.mail` written with CRLF endings fails identically. `CHAR_CRIT` is
  a result *parameter*, so `CREA_TABLE` cannot reach it - it comes from
  `MD.getParameters()` inside the comm's own interpreter.

And the naming trap that started all of this: the keyword is `STABILITE`, not
`BUCKL` or `EIGEN`. Grepping the command directory for English buckling words
finds nothing and looks like a missing feature when it is not.

## Diagnosing a failing structural solve

Do this in order. The named DOF in the error is a starting point, not a
diagnosis.

1. Confirm the runtime first: `python -m tuba.solver.code_aster_doctor --check`.
   A solver problem and a model problem look identical from the outside.
2. Read the real exception in `study.mess`, not the summary line.
3. Bisect against the solver, one feature at a time, from a model you know
   solves. `examples/line-load-studio/model.py` is a small known-good start.
   Change exactly one thing per run: web as bars vs beams, with vs without
   bracing, 2 frames vs 7. The first variant that solves names the cause.
4. Cheap first probe - the diagonal stiffness per node. A zero diagonal is a
   real mechanism. The translational block is the projector sum
   `(E*A/L) n n^T + (12*E*Iy/L^3) m m^T + (12*E*Iz/L^3) p p^T` over the local
   axes `n, m, p`; the rotational block is the same with `L^-1` and `4` instead
   of `L^-3` and `12`. Healthy diagonals plus a singular solve means a *coupling*
   dependency, not a free node.
5. Do not trust a hand-rolled stiffness matrix you have not self-tested against a
   model that demonstrably solves. A wrong DOF index in one bending block
   silently deletes a whole bending plane and invents mechanisms that are not
   there. Check symmetry and one analytic case (a cantilever tip) before reading
   anything into its output.

Report which variant solved and which did not. "The web as bars is the cause" is
a finding worth more than a list of things that were tried.

## Wind and other loads

Tuba computes no design pressure and selects no code. `line_load` is force per
metre in global axes and is the right tool for a known wind load on cladding
transfer members. The `wind` quantity follows Code_Aster's cross-flow rule: it
keeps the component across the member axis, scaled by the sine of the angle
between wind and axis. A large deflection under your chosen load is a result,
not a bug - and not a design verdict.
