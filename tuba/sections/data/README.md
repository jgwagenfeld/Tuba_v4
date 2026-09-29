# Section profile data

`IBeam.input` and `IBeam.output` are the rolled-profile tables Tuba's solver
needs for a section that Code_Aster has no primitive for.

## What these files are, and who wrote them

`IBeam.output` is an **Autochar (Sillage) section-characteristics table**, not a
Tuba export. Its 47 columns are Sillage's own: `A`, `CDG_Y`, `CDG_Z`, `IY_G`,
`IZ_G`, `IYZ_G`, `ALPHA`, `Y_MAX`/`Y_MIN`/`Z_MAX`/`Z_MIN`, `R_MAX`, `RY`, `RZ`,
`Y_P`, `Z_P`, `IY_P`, `IZ_P`, `IYR2`, `IZR2`, `IXR2_P`, `JX`, `RT`, `PCTY`,
`PCTZ`, `EY`, `EZ`, `JG`, `AY`, `AZ`, and the `_M` variants in SI. `IBeam.input`
is the matching nominal-geometry input (`NAME, H, B, Tw, Tf, R` in millimetres).

They were generated **offline, once, and committed**. They came into the
repository with the initial baseline snapshot (`886b0f0`) and carry no record of
the tool version, the geometry source, or the command line that produced them.

## Why the file cannot be regenerated from this environment

Autochar ships in the Code_Aster **source** tree, not in a runnable
installation. Verified on the configured WSL runtime:

- It is not a CATIA command. All 270 commands in
  `code_aster/Cata/Commands` were listed; none computes section characteristics.
- It is not installed. `find` over the solver's conda environment returns
  nothing for `*autochar*` or `*sillage*`; only `run_aster` is on `PATH`.

So a run that needs this table cannot rebuild it. There is no `--refresh` for
`IBeam.output`, and there never has been. This is a known, accepted gap rather
than an oversight, and it is the reason the next section matters.

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

## `tuba/sections/properties.py` is the way out

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

The residual on the first three is the difference between Sillage's real rolled
geometry - tapered flanges, true root radii - and the nominal-plate idealisation
the kernel integrates.

The kernel covers four of the fourteen values the solver writes. Extending it to
the remaining ten is the intended route off this file; until that lands, **this
table is the only source for the shear centre and the warping constant, and
`IBeam.output` is the only test oracle the kernel has.** Deleting it would
remove the kernel's independent check, so it stays as a fixture even once the
solver stops reading it.
