# Section profile data

`IBeam.input` and `IBeam.output` are the rolled-profile tables Tuba's solver
needs for a section that Code_Aster has no primitive for.

## What these files are, and who wrote them

`IBeam.output` is a **Code_Aster `macr_cara_poutre` MacroCommand output**, not a
Tuba export. 24 of its 25 distinctive column names appear verbatim in
`code_aster/MacroCommands/macr_cara_poutre_ops.py`, including the SI variants
(`A_M`, `CDG_Y_M`, `IY_G`, `IZ_G`, `IYZ_G`) and every engineering quantity
(`ALPHA`, `Y_MAX`, `R_MAX`, `RY`, `RZ`, `Y_P`, `IY_P`, `JX`, `RT`, `PCTY`,
`PCTZ`, `EY`, `EZ`, `JG`, `AY`, `AZ`). `IBeam.input` is the matching
nominal-geometry input: `NAME, H, B, Tw, Tf, R` in millimetres.

They were generated **once, offline, and committed**. They came into the
repository with the initial baseline snapshot (`886b0f0`) and carry no record of
the code_aster version, the geometry source or the command line that produced
them.

## Why the file cannot be regenerated from this environment

`macr_cara_poutre` is a MacroCommand, so it is not one of the 270 CATIA commands
- that check alone would clear a file that is nevertheless unrunnable here. What
is missing is narrower and was verified on the configured WSL runtime:

- The **operation** module is present:
  `code_aster.MacroCommands.macr_cara_poutre_ops` imports cleanly.
- The **command** module is not. `code_aster.MacroCommands.macr_cara_poutre`
  raises `ModuleNotFoundError`, and no entry in the command registry matches
  `poutre` or `cara`.

So the arithmetic ships without the driver that runs it. There is no
`--refresh` for `IBeam.output` and there never has been.

## What the columns mean, where it is not obvious

Three of the columns do **not** hold the quantity their name suggests in an
engineering handbook, and reading them as if they did would be wrong:

| column | what it holds | check |
| --- | --- | --- |
| `RY`, `RZ` | extreme-fibre distances, **not** radii of gyration | `RY == H/2` and `RZ == B/2` on every I-profile in the table: IPE200 gives 100/50, HE1000B gives 500/150 |
| `JG` | not the standard warping constant | `JG/JX` is not constant across the catalog - 1.9e5 for IPE200, 3.0e6 for HE1000B - and the absolute value is several orders above the handbook `Jw` |
| `IYR2`, `IZR2` | not the warping second moments | small and **negative** on every profile checked (IPE200: -0.0107, -0.0153) |

`EY` and `EZ` are the shear-centre offsets, and they are 33 nm and -8 nm on
IPE200: a doubly symmetric I-section's shear centre *is* its centroid, so these
carry numerical noise rather than information.

This is the reason the kernel below cannot simply take over the solver's fourteen
values. See the last section.

## Why the solver still reads this table

`SX_BEAM` is a general `POUTRE` section: Code_Aster takes the properties
verbatim and Tuba has nothing to compute for it. Fourteen values are written -
`A`, `IY`, `IZ`, `AY`, `AZ`, `EY`, `EZ`, `JX`, `JG`, `IYR2`, `IZR2`, `RY`, `RZ`,
`RT` - and for ten of them there is no other source in the tree. Those ten
include the shear centre (`EY`/`EZ`) and the warping constant (`JG`), which are
classical derivations rather than closed forms.

Every other section shape is *not* a table lookup. Pipes and bars are written as
`SECTION='CERCLE', CARA=('R','EP')` and rectangles as `SECTION='RECTANGLE',
CARA=('HY','HZ',...)`, so Code_Aster derives their characteristics itself.

## How much of the fourteen the native kernel can replace

`tuba.sections.properties` computes a section's area, both second moments, its
torsion constant, its centroid and its radii of gyration from the section's own
geometry, with no catalog lookup and no solver. It is checked against this table
for every one of the 174 profiles in `IBeam.output` by
`tests/test_section_properties.py`:

| quantity | worst disagreement over the catalog |
| --- | --- |
| `A` | 0.040% |
| `IY` | 0.006% |
| `IZ` | 0.028% |
| `JX` | 39.7% (thin-wall estimate, bounded and flagged) |

The residual on the first three is the difference between a real rolled
section's geometry - tapered flanges, true root radii - and the nominal-plate
idealisation the kernel integrates.

The kernel covers four of the fourteen values the solver writes. The other ten
split three ways, and the split is the reason "extend the kernel and drop the
table" is not a single piece of work:

- **Reachable and testable.** `RY`/`RZ` are exactly `H/2` and `B/2` on every
  profile, so the kernel can state them exactly - under a name that does not
  collide with its own radii of gyration. `EY`/`EZ` are the shear-centre
  offsets, which for a doubly symmetric section are exactly zero, and the kernel
  can say so rather than reporting the table's 33 nm.
- **Reachable but only loosely bounded.** `AY`/`AZ` are `macr_cara_poutre`'s own
  sector-decomposition shear areas. They are in cm² and of the right magnitude
  (HE200B: 4.49 and 1.45), but a plate formula does not reproduce them - the
  naive web-and-flange areas for HE200B are 3.06 and 6.0 cm² - so these would be
  bounded estimates in the same way `JX` is, not replacements.
- **Not reachable.** `JG`, `IYR2`, `IZR2` and `RT` do not hold the quantities
  their names imply, per the table above. There is no oracle to test a formula
  against, and the structural-frames skill's own rule - *"Do not trust a
  hand-rolled stiffness matrix you have not self-tested"* - is the right answer
  to an untestable derivation.

So the route off this file is real but partial: the kernel can take over `A`,
`IY`, `IZ` and the two trivial ones, and the rest need either a runnable
`macr_cara_poutre` or a new authority. **Deleting `IBeam.output` is not on the
table while it is also the kernel's only independent check** - the four
quantities it validates are validated by comparing against this file, and
removing the file removes the test.
