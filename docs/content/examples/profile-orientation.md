# Profile orientation: global and local axes

[Open the solved comparison](../../gallery/profile-orientation-review/index.html)

One model contains three disconnected, identical 3 m IPE100 cantilevers with
0, 45 and 90 degree section roll. All roots are anchored. Gravity is disabled;
the only difference between the members is their roll and physical offset.

Choose either ordinary linear Code_Aster load case:

- **global** applies the same 500 N force in global -Z to every tip. The 0 degree
  member bends about its weak local y axis, the 90 degree member about its strong
  local z axis; the 45 degree member combines both responses.
- **local** applies the same 500 N force in each section's local -z direction.
  Those vectors are resolved to global coordinates before solver export. The
  three displacement vectors expressed in their original local bases match.

The I-section surfaces use solved nodal translations and rotations. The
original outline is a faint reference. The deformation control exaggerates
both translations and rotation vectors by the same factor; it never changes
reported solver values. Section frames remain rigid as that factor changes.

The two independent annotation layers distinguish **Original local basis**
from **Solved section frames**, at root, midspan and tip. Red is local x, green
local y, and blue local z. These are section axes, not the viewer's global axes.

The source example is `examples/code_aster_profile_orientation.py`. Run it to
solve both cases, or pass `--artifact-dir` to import the attested `global` and
`local` folders. The bundle includes both complete evidence chains under
`artifacts/global` and `artifacts/local`, and `orientation-checks.json` records
solved tip translations and rotations. Publication checks their signs and
magnitudes against cantilever bending equations and checks local-load
invariance. These beam results are not a piping-code compliance assessment.

For the committed real solve, tip displacements are:

| Roll | Global case: global Z (mm) | Local case: local z (mm) |
| --- | ---: | ---: |
| 0 degrees | -141.371 | -141.371 |
| 45 degrees | -77.287 | -141.371 |
| 90 degrees | -13.203 | -141.371 |

The 45 degree global case also moves +64.084 mm in global Y. The weak/strong
Z response ratio is 10.708. These are linear POU_D_T results, including shear
flexibility; they are independent of the display exaggeration.
